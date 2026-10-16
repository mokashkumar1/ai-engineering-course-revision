"""Build the embedded Qdrant store from portable vectors, without retranscription."""
import json
from pathlib import Path
from qdrant_client import QdrantClient,models


def bootstrap(root=Path(__file__).resolve().parent):
    data=root/'search_data'
    client=QdrantClient(path=str(data/'qdrant'))
    try:
        if client.collection_exists('course_passages'):return
        client.create_collection('course_passages',vectors_config=models.VectorParams(size=384,distance=models.Distance.COSINE))
        batch=[]
        with (data/'vectors.jsonl').open(encoding='utf-8') as stream:
            for line in stream:
                batch.append(models.PointStruct(**json.loads(line)))
                if len(batch)>=128:
                    client.upsert('course_passages',points=batch);batch=[]
        if batch:client.upsert('course_passages',points=batch)
        expected=json.loads((data/'manifest.json').read_text())['passages']
        if client.count('course_passages',exact=True).count!=expected:
            raise RuntimeError('Portable index count mismatch')
    finally:client.close()


if __name__=='__main__':bootstrap()
