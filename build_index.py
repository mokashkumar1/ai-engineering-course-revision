"""Index existing course text; no transcription and no Groq requests."""
import argparse
import csv
import hashlib
import json
import math
import sqlite3
import uuid
from datetime import datetime,timezone
from pathlib import Path

from course_audit import digest, read_json
from search_engine import ROOT, DATA, MODEL, COLLECTION, chunks, clean_title, expand, topic


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--semantic',action='store_true',help='add multilingual embeddings in local Qdrant')
    args=parser.parse_args()
    DATA.mkdir(exist_ok=True)
    reports=sorted((ROOT/'audit_runs').glob('*/audit_report.json'))
    if not reports:parser.error('Run course_audit.py first.')
    report_path=reports[-1];audit=read_json(report_path)
    audit_rows={l['index']:l for l in audit['lectures']}
    with (report_path.parent/'lecture_mapping.csv').open(encoding='utf-8-sig',newline='') as stream:
        mapping={int(row['filename_index']):row for row in csv.DictReader(stream)}
    files=sorted((ROOT/'transcripts').glob('*.json'))
    signature=hashlib.sha256(('window45-v1|'+digest(report_path)+''.join(digest(p) for p in files)).encode()).hexdigest()
    manifest_path=DATA/'manifest.json'
    if manifest_path.exists():
        old=read_json(manifest_path)
        if old.get('source_signature')==signature and (not args.semantic or old.get('semantic')):
            print('Index already matches sources; nothing rebuilt.',flush=True);return
    db=sqlite3.connect(DATA/'course.sqlite')
    db.executescript('''
        DROP TABLE IF EXISTS lectures; DROP TABLE IF EXISTS segments; DROP TABLE IF EXISTS chunks;
        DROP TABLE IF EXISTS lecture_fts; DROP TABLE IF EXISTS passage_fts;
        CREATE TABLE lectures(id TEXT PRIMARY KEY,number INTEGER,title TEXT,topic TEXT,duration REAL,video_id TEXT,mapping_status TEXT,timing_eligible INTEGER);
        CREATE TABLE segments(lecture_id TEXT,position INTEGER,start REAL,end REAL,text TEXT,PRIMARY KEY(lecture_id,position));
        CREATE INDEX segment_lookup ON segments(lecture_id,start,end);
        CREATE TABLE chunks(id TEXT PRIMARY KEY,lecture_id TEXT,start REAL,end REAL,text TEXT,first_segment INTEGER,last_segment INTEGER,source_hash TEXT);
        CREATE VIRTUAL TABLE lecture_fts USING fts5(lecture_id UNINDEXED,text);
        CREATE VIRTUAL TABLE passage_fts USING fts5(chunk_id UNINDEXED,lecture_id UNINDEXED,text);
    ''')
    documents=[];chunk_ids=[];payloads=[]
    for path in files:
        data=read_json(path);number=int(path.name.split(' - ',1)[0]);lecture_id=f'lecture-{number:03d}'
        source_hash=digest(path);entry=audit_rows.get(number,{});mapped=mapping.get(number,{})
        duration=entry.get('mp3_duration_seconds');end=entry.get('last_segment_end')
        fresh=entry.get('source_files',{}).get(path.name)==source_hash
        reliable=bool(fresh and duration and end is not None and abs(end-duration)<=2 and not entry.get('flag_counts',{}).get('non_monotonic_start'))
        title=clean_title(path.stem)
        db.execute('INSERT INTO lectures VALUES(?,?,?,?,?,?,?,?)',(lecture_id,number,title,topic(number),duration,mapped.get('video_id'),mapped.get('status','unverified'),int(reliable)))
        db.execute('INSERT INTO lecture_fts VALUES(?,?)',(lecture_id,expand(title)))
        for i,s in enumerate(data['segments']):
            if isinstance(s,dict) and isinstance(s.get('text'),str) and all(isinstance(s.get(k),(int,float)) and math.isfinite(s[k]) for k in ('start','end')):
                db.execute('INSERT INTO segments VALUES(?,?,?,?,?)',(lecture_id,i,s['start'],s['end'],s['text']))
        count=0
        for group in chunks(data['segments']):
            first,last=group[0][0],group[-1][0];start,end=group[0][1]['start'],group[-1][1]['end']
            text=' '.join(s['text'].strip() for _,s in group).strip()
            if not text:continue
            chunk_id=str(uuid.uuid5(uuid.NAMESPACE_URL,f'{lecture_id}:{source_hash}:{first}:{last}:window45-v1'))
            db.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?)',(chunk_id,lecture_id,start,end,text,first,last,source_hash))
            db.execute('INSERT INTO passage_fts VALUES(?,?,?)',(chunk_id,lecture_id,expand(text)))
            documents.append(title+'\n'+text[:2000]);chunk_ids.append(chunk_id);payloads.append({'lecture_id':lecture_id,'text':text,'start':start,'end':end,'video_id':mapped.get('video_id'),'title':title})
            count+=1
        print(f'{lecture_id}: {count} passages; timing {"approximate" if reliable else "lecture-only"}',flush=True)
    db.commit();db.close()
    manifest={'source_signature':signature,'passages':len(documents),'semantic':False,'model':None,
              'built_at_utc':datetime.now(timezone.utc).isoformat(),'source_report':str(report_path)}
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    if args.semantic:
        from fastembed import TextEmbedding
        from qdrant_client import QdrantClient,models
        model=TextEmbedding(MODEL,cache_dir=str(ROOT/'.model_cache'),threads=4,providers=['CPUExecutionProvider'],local_files_only=True)
        client=QdrantClient(path=str(DATA/'qdrant'))
        try:
            if client.collection_exists(COLLECTION):client.delete_collection(COLLECTION)
            client.create_collection(COLLECTION,vectors_config=models.VectorParams(size=384,distance=models.Distance.COSINE))
            for start in range(0,len(documents),32):
                vectors=list(model.passage_embed(documents[start:start+32],batch_size=16))
                client.upsert(COLLECTION,points=[models.PointStruct(id=chunk_ids[start+i],vector=v.tolist(),payload=payloads[start+i]) for i,v in enumerate(vectors)])
                print(f'Indexed {min(start+32,len(documents))}/{len(documents)} multilingual passages',flush=True)
            manifest.update(semantic=True,model=MODEL)
            manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        finally:client.close()
    print('Course text index ready. Original transcripts unchanged.',flush=True)


if __name__=='__main__':main()
