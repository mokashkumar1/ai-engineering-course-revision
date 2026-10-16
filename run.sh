#!/usr/bin/env bash
set -e

echo "============================================================"
echo "      AI ENGINEERING COURSE REVISION ASSISTANT"
echo "============================================================"

# 1. Setup .env
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "[*] Creating .env from .env.example..."
        cp .env.example .env
        echo "[!] Notice: Add your GROQ_API_KEY to .env for AI answers."
    fi
fi

# 2. Check for uv
if command -v uv &> /dev/null; then
    echo "[*] Detected 'uv' - syncing environment..."
    uv sync
    echo "[*] Starting server on http://127.0.0.1:8000 ..."
    uv run uvicorn app:app --host 127.0.0.1 --port 8000 --reload
    exit 0
fi

# 3. Fallback to standard Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Neither 'uv' nor 'python3' was found."
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "[*] Creating virtual environment (.venv)..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

echo "[*] Starting server on http://127.0.0.1:8000 ..."
python3 -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
