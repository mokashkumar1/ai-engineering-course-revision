"""Fetch the private course index at runtime; credentials never enter Git or images."""
import os
from pathlib import Path
import shutil
import sys
import zipfile

from huggingface_hub import hf_hub_download
from bootstrap_index import bootstrap


def main():
    root=Path(__file__).resolve().parent;data=root/'search_data';data.mkdir(exist_ok=True)
    if not (data/'manifest.json').exists():
        archive=hf_hub_download(os.environ['COURSE_DATA_REPO'],'course-index.zip',repo_type='dataset',
            token=os.environ['HF_TOKEN'],cache_dir='/tmp/course-download')
        with zipfile.ZipFile(archive) as bundle:
            for name in ('course.sqlite','manifest.json','vectors.jsonl'):
                with bundle.open(name) as source,(data/name).open('wb') as target:
                    shutil.copyfileobj(source,target)
    bootstrap(root)
    # Drop downloader/import memory before loading the embedding model.
    os.execv(sys.executable,[sys.executable,'-m','uvicorn','app:app','--host','0.0.0.0',
        '--port',os.environ.get('PORT','10000'),'--workers','1','--no-proxy-headers'])


if __name__=='__main__':main()
