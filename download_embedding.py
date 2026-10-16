"""Fetch public, original embedding assets during the Docker image build."""
from pathlib import Path
from huggingface_hub import hf_hub_download

if __name__=='__main__':
    target=Path(__file__).resolve().parent/'.model_cache'/'compact'
    for repo,filename in [
        ('Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q','model_optimized.onnx'),
        ('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2','sentencepiece.bpe.model')]:
        hf_hub_download(repo,filename,local_dir=target)
