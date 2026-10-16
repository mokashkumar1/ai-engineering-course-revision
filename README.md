# AI Engineering Course Revision Assistant

Personal AI Engineer course revision assistant with a modern dark chat interface, Groq-powered RAG, embedded Qdrant vector search, SQLite BM25, and synchronized YouTube lecture playback.

Ask questions in English, Roman Urdu/Hindi, Hindi, or Urdu; receive brief course-grounded answers with clickable timestamp citations that instantly seek and play the lecture video.

---

## ⚡ Quick Start (New Clones)

### 1. Clone Repository
```bash
git clone https://github.com/mokashkumar1/ai-engineering-course-revision.git
cd ai-engineering-course-revision
```

### 2. Configure Environment (Optional for AI answers)
Copy the example environment file:
```bash
cp .env.example .env
```
Open `.env` and insert your [Groq API Key](https://console.groq.com/):
```env
GROQ_API_KEY=your_groq_api_key_here
```
*(Search continues to work via SQLite BM25 & Qdrant even without a Groq key).*

---

## 🚀 Running the App

### Option A: One-Click (Windows)
Double-click `run.bat` or run:
```cmd
.\run.bat
```
This automatically detects `uv` or `python`, installs required packages, initializes `.env`, and launches `http://127.0.0.1:8000`.

### Option B: Using Astral `uv` (Recommended for fast sync)
```bash
# Sync dependencies into virtual environment
uv sync

# Start development server
uv run uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

### Option C: Standard Python (Windows / macOS / Linux)
```bash
# Create and activate virtual environment
python -m venv .venv

# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start server
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser at **http://127.0.0.1:8000**.

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
