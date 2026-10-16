"""Course retrieval: SQLite keyword search + optional local Qdrant vectors.

Existing transcript timestamps are evidence candidates, never certified alignment.
No audio or secrets are read by the web application's search path.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
import threading
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from connections import setting

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "search_data"
MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION = "course_passages"
STOP = set("a an the to of in on and or is are was were be this that it how what why when where does do can i you me my your explain tell about please course engineer engineering ai free episode weeks week introduction intro understand kya kaise kyun mujhe samjhao batao hai hain hota hoti ka ki ke ko se mein aur par ye yeh ko samjha करता करती कैसे क्या है हैं में को से और मुझे बताओ समझाओ होता होती यह बारे समझाएं".split())
STOP.update("work works working kaam karta karti lecture lectures video videos काम करते".split())
ALIASES = {
    "rag": ["रैग", "राग", "आरएजी", "retrieval augmented generation"],
    "multi tenant": ["multi-tenant", "multitenant", "multi tenancy", "मल्टी टेनेंट", "मल्टी टेनन्ट"],
    "embeddings": ["embedding", "एम्बेडिंग", "एम्बेडिंग्स", "इम्बेडिंग"],
    "chunking": ["chunks", "चंकिंग", "चंक्स"],
    "prompt": ["प्रॉम्प्ट", "प्राम्प्ट"],
    "tokens": ["token", "टोकन", "टोकन्स"],
    "qdrant": ["quadrant", "क्वाड्रेंट", "क्यूड्रेंट", "क्वाड्रन्ट"],
    "agents": ["agent", "एजेंट", "एजेन्ट", "एजेंट्स"],
    "multi agents": ["multi-agent", "multi agent", "मल्टी एजेंट", "मल्टी एजेन्ट"],
    "langgraph": ["lang graph", "लैंगग्राफ", "लैंग ग्राफ"],
    "mcp": ["एमसीपी", "एम सी पी", "model context protocol"],
    "evaluation": ["evaluate", "इवैल्यूएशन", "मूल्यांकन"],
    "tools": ["tool", "टूल्स", "टूल"],
    "streaming": ["स्ट्रीमिंग"],
    "pydantic": ["पाइडेंटिक", "पायडेंटिक"],
    "react": ["रीएक्ट", "रीऐक्ट", "रीएक्ट"],
    "temperature": ["टेम्परेचर", "तापमान"],
    "system role": ["सिस्टम रोल"],
    "json": ["जेसन", "जेएसओएन"],
}


def normalize(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().replace("-", " ").split())


def expand(text):
    normalized = normalize(text)
    additions = []
    for canonical, aliases in ALIASES.items():
        if any(re.search(r"(?<!\w)" + re.escape(normalize(a)) + r"(?!\w)", normalized)
               for a in [canonical, *aliases]):
            additions.append(canonical)
    return normalized + " " + " ".join(additions)


def terms(text):
    return list(dict.fromkeys(t for t in re.findall(r"[a-z0-9]+|[\u0900-\u097f]+|[\u0600-\u06ff]+", expand(text))
                             if t not in STOP and len(t)>1))[:32]


def clean_title(stem):
    title = re.sub(r"^\d+\s*[-.]\s*", "", stem)
    title = re.sub(r"\s*[｜|]\s*(?:Free\s+)?AI\s+Engin(?:eer|ner).*", "", title, flags=re.I)
    title = re.sub(r"\s*[｜|]\s*8\s*Weeks.*", "", title, flags=re.I)
    title = re.sub(r"^(?:Episode|Ep)\s*[:：]?\s*\d+\s*[:：.\-]?\s*", "", title, flags=re.I)
    return title.strip(" ｜|:")


def topic(index):
    return "Foundations" if index<=14 else "RAG" if index<=23 else "Agents" if index<=34 else "MCP"


def chunks(segments, window=45):
    """Consecutive original segments, max 45 s, one-segment overlap."""
    group = []
    for i, segment in enumerate(segments):
        if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
            continue
        start,end = segment.get("start"), segment.get("end")
        if not isinstance(start,(int,float)) or not isinstance(end,(int,float)) or not math.isfinite(start) or not math.isfinite(end) or start<0 or end<=start:
            continue
        if group and (end-group[0][1]["start"]>window or start<group[-1][1]["start"]):
            yield group
            previous = group[-1]
            group = [previous] if end-previous[1]["start"]<=window else []
        group.append((i,segment))
    if group:
        yield group


def timing_status(lecture, start, end):
    duration = lecture.get("duration")
    if not duration or start<0 or end>duration or end<=start:
        return "unavailable"
    return "approximate" if lecture.get("timing_eligible") else "unreliable"


def connect(path=DATA/"course.sqlite"):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    return db


class CourseSearch:
    def __init__(self, data=DATA):
        self.data = Path(data)
        self.db_path = self.data/"course.sqlite"
        self.manifest = json.loads((self.data/"manifest.json").read_text(encoding="utf-8"))
        with connect(self.db_path) as db:
            self.lectures = {row["id"]:dict(row) for row in db.execute("SELECT * FROM lectures ORDER BY number")}
        self.model = self.vector = None
        self.semantic_status = "not_built"
        self.lock = threading.Lock()

    def load_semantic(self):
        if not self.manifest.get("semantic"):
            return
        try:
            if setting(ROOT,'EMBEDDING_RUNTIME','fastembed')=='compact':
                from compact_embedding import CompactEmbedding
                self.model=CompactEmbedding(ROOT/'.model_cache')
            else:
                from fastembed import TextEmbedding
                self.model = TextEmbedding(MODEL, cache_dir=str(ROOT/".model_cache"), threads=4,
                                           providers=["CPUExecutionProvider"], local_files_only=True)
            from qdrant_client import QdrantClient
            self.vector = QdrantClient(path=str(self.data/"qdrant"))
            self.semantic_status = "ready"
        except Exception:
            self.semantic_status = "unavailable_keyword_search_active"
            self.model = None
            if self.vector:
                self.vector.close()
            self.vector = None

    def status(self):
        return {"lectures":len(self.lectures), "hours":round(sum(l["duration"] or 0 for l in self.lectures.values())/3600,1),
                "passages":self.manifest["passages"], "semantic":self.semantic_status,
                "timestamps":"approximate_or_unavailable", "benchmark":"not_validated", "answers_enabled":False}

    def catalogue(self):
        return [{k:row[k] for k in ("id","number","title","topic","duration","video_id","mapping_status","timing_eligible")} for row in self.lectures.values()]

    def search(self, query, lecture_ids=None, selected_topic=None, limit=6):
        before = time.perf_counter()
        query_terms = terms(query)
        if not query_terms:
            return {"results":[],"state":"no_strong_match","elapsed_ms":0,"mode":self.semantic_status}
        informative=set(query_terms)-{'multi','system','systems'} or set(query_terms)
        allowed = {id for id,l in self.lectures.items() if (not lecture_ids or id in lecture_ids) and (not selected_topic or l["topic"]==selected_topic)}
        if not allowed:
            return {"results":[],"state":"no_strong_match","elapsed_ms":0,"mode":self.semantic_status}
        expression = " OR ".join('"'+token.replace('"','""')+'"' for token in query_terms)
        ids = sorted(allowed)
        placeholders = ",".join("?" for _ in ids)
        with connect(self.db_path) as db:
            title_rows = db.execute(f"SELECT lecture_id,bm25(lecture_fts) AS rank FROM lecture_fts WHERE lecture_fts MATCH ? AND lecture_id IN ({placeholders}) ORDER BY rank LIMIT 36", [expression,*ids]).fetchall()
            passage_rows = db.execute(f"SELECT chunk_id,bm25(passage_fts) AS rank FROM passage_fts WHERE passage_fts MATCH ? AND lecture_id IN ({placeholders}) ORDER BY rank LIMIT 80", [expression,*ids]).fetchall()
            scores = defaultdict(float)
            lexical_ids = {row["chunk_id"] for row in passage_rows}
            for rank,row in enumerate(passage_rows,1):
                scores[row["chunk_id"]] += 1/(60+rank)
            dense_scores = {}
            if self.vector and self.model:
                try:
                    from qdrant_client import models
                    with self.lock:
                        vector = next(self.model.query_embed([query])).tolist()
                        hits = self.vector.query_points(COLLECTION, query=vector, limit=80,
                            query_filter=models.Filter(must=[models.FieldCondition(key="lecture_id",match=models.MatchAny(any=ids))]),
                            with_payload=True).points
                    for rank,hit in enumerate(hits,1):
                        if hit.score>=.40:
                            chunk_id = str(hit.id)
                            scores[chunk_id] += 1/(60+rank)
                            dense_scores[chunk_id] = hit.score
                except Exception:
                    self.semantic_status = "unavailable_keyword_search_active"
            title_ranks = {row["lecture_id"]:i for i,row in enumerate(title_rows,1)}
            title_documents=[set(terms(l['title'])) for l in self.lectures.values()]
            weights={term:1+math.log((len(title_documents)+1)/(1+sum(term in title for title in title_documents))) for term in query_terms}
            grouped = defaultdict(list)
            if scores:
                keys=list(scores)
                # This corpus is small; use batches under SQLite's variable limit.
                for offset in range(0,len(keys),400):
                    batch=keys[offset:offset+400]
                    for row in db.execute("SELECT * FROM chunks WHERE id IN ("+",".join("?" for _ in batch)+")",batch):
                        row=dict(row)
                        if row["lecture_id"] in allowed:
                            row["score"]=scores[row["id"]]
                            row["lexical"]=row["id"] in lexical_ids and bool(set(terms(row['text'])).intersection(informative))
                            row["dense_score"]=dense_scores.get(row["id"],0)
                            grouped[row["lecture_id"]].append(row)
            results=[]
            for lecture_id in set(grouped)|set(title_ranks):
                lecture=self.lectures[lecture_id]
                title_terms=set(terms(lecture["title"]))
                coverage=sum(weights[t] for t in title_terms.intersection(informative))/sum(weights.values())
                passages=sorted(grouped.get(lecture_id,[]),key=lambda p:p["score"],reverse=True)
                selected=[]
                for passage in passages:
                    if any(min(passage["end"],p["end"])-max(passage["start"],p["start"])>0 for p in selected):
                        continue
                    selected.append(passage)
                    if len(selected)==2:break
                title_match=lecture_id in title_ranks and bool(title_terms.intersection(informative))
                best=selected[0]["score"] if selected else 0
                max_dense=max((p["dense_score"] for p in selected),default=0)
                if not title_match and not any(p["lexical"] for p in selected) and max_dense<.65:
                    continue
                score=best+(.1*selected[1]["score"] if len(selected)>1 else 0)+(2/(60+title_ranks[lecture_id]) if title_match else 0)+.12*coverage
                excerpts=[]
                for passage in selected:
                    status=timing_status(lecture,passage["start"],passage["end"])
                    excerpts.append({"id":passage["id"],"text":passage["text"][:300],"truncated":len(passage["text"])>300,
                        "start":passage["start"] if status=="approximate" else None,"end":passage["end"] if status=="approximate" else None,
                        "timestamp_status":status,"source":"existing_transcript"})
                video=lecture["video_id"]
                results.append({"lecture_id":lecture_id,"number":lecture["number"],"title":lecture["title"],"topic":lecture["topic"],
                    "duration":lecture["duration"],"video_id":video,"mapping_status":lecture["mapping_status"],
                    "youtube_url":f"https://www.youtube.com/watch?v={video}" if video else None,
                    "match_type":"Title + transcript" if title_match and selected else "Lecture title" if title_match else "Transcript passage",
                    "timestamp_status":"approximate" if lecture["timing_eligible"] else "unreliable",
                    "passages":excerpts,"_score":score})
        results.sort(key=lambda row:(-row["_score"],row["number"]))
        for row in results:row.pop("_score")
        return {"query":query,"results":results[:limit],"state":"matches" if results else "no_strong_match",
                "elapsed_ms":round((time.perf_counter()-before)*1000),"mode":"hybrid" if self.semantic_status=="ready" else "keyword",
                "notice":"Existing transcripts; timestamps are approximate. Search quality has not passed the benchmark."}

    def context(self, chunk_id):
        with connect(self.db_path) as db:
            row=db.execute("SELECT * FROM chunks WHERE id=?",(chunk_id,)).fetchone()
            if not row:return None
            lecture=self.lectures[row["lecture_id"]]
            segments=db.execute("SELECT text FROM segments WHERE lecture_id=? AND end>=? AND start<=? ORDER BY position",
                                (row["lecture_id"],max(0,row["start"]-30),row["end"]+30)).fetchall()
            text=" ".join(s["text"] for s in segments)
            return {"text":text[:1200],"truncated":len(text)>1200,"lecture_id":row["lecture_id"],
                    "timestamp_status":timing_status(lecture,row["start"],row["end"])}
