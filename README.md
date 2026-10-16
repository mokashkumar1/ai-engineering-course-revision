# RAG YT RIVISION

Personal AI Engineer course revision assistant. Ask a question in English, Roman Urdu/Hindi, Hindi or Urdu; get a brief course-grounded answer and supporting lecture links. The answer language follows the question. Original transcripts remain internal and are never returned by the browser API.

## Run locally

```powershell
.\Start-Demo.ps1
```

Open http://127.0.0.1:8765. Use one server worker for embedded Qdrant.

Save a Groq key in the local, gitignored `.env` (see `.env.example`). Key changes are picked up without restarting. The default generation model is configurable with `GROQ_MODEL`. Search remains available when no key is configured, Groq is unavailable, or the answer quota runs out.

## Features

- 36 lectures and 1,491 passages, SQLite BM25 plus local multilingual embeddings and embedded Qdrant.
- Short answers from up to six retrieved passages. Every answer point must cite a server-selected source ID. Invalid or invented citation IDs cause the answer to be withheld.
- No outside-course explanation, full transcript, source audio, transcript excerpts, or context endpoint in the public interface.
- Minimal frontend: one question box, a short cited answer, matching lecture moments and playback on demand. No library, corpus counts, filters, dashboard statistics or connection panels.
- Per-client answer limits (5/minute, 30/day), persistent global limit (100/day by default), and one-hour in-memory answer caching. Daily counters survive restarts; a new cloud container can reset ephemeral counters. One generation request at a time limits concurrency. Search has separate limits.

## Honest limitations

Answers are enabled at the user's request, but the frozen benchmark has not been run. Citation validation checks that references exist, not that every claim is correct. Real answer quality and multilingual behavior require a working Groq key and human checks against the lectures.

Timestamps come from existing transcripts. In-range passage times are shown as approximate only for lectures whose unchanged transcript endpoint closely matches measured audio duration. Other lectures open from the beginning. A four-second lead-in is applied for passage playback. Original transcripts remain unchanged; no retranscription is performed.

The embedding model is cached under `.model_cache/`. MP3s are not required at runtime. Existing source audio remains outside this project.

## Deployment

The application includes a `Dockerfile` for containerized deployment (e.g. Docker, Render, or cloud container services).

## Verify

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
node --check frontend/app.js
```

Tests cover transcript privacy, server-owned citations, invalid output, missing credentials, provider failures, persistent limits, retrieval utilities and source-preserving audit behavior. They are development checks, not the course accuracy benchmark.
