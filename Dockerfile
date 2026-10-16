FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/home/user
RUN useradd -m -u 1000 user
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=user:user app.py answers.py connections.py search_engine.py bootstrap_index.py ./
COPY --chown=user:user frontend/ ./frontend/
COPY --chown=user:user search_data/course.sqlite search_data/manifest.json search_data/vectors.jsonl ./search_data/
RUN chown -R user:user /app
USER user
RUN python bootstrap_index.py
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',cache_dir='.model_cache',providers=['CPUExecutionProvider'])"
EXPOSE 7860
CMD ["python","-m","uvicorn","app:app","--host","0.0.0.0","--port","7860","--workers","1","--no-proxy-headers"]
