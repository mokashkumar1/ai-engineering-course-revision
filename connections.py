"""Verify optional Groq authentication without making an inference request."""
import os
import hashlib
import threading
import time
from pathlib import Path
import httpx


def setting(root,name,default=''):
    value=os.environ.get(name,'').strip()
    if value:return value
    path=Path(root)/'.env'
    if not path.is_file():return default
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line=line.strip().removeprefix('export ')
        key,sep,value=line.partition('=')
        if sep and key.strip()==name:
            value=value.strip()
            return value[1:].split(value[0],1)[0] if value[:1] in ('"',"'") else value.split(' #',1)[0].strip()
    return default


def groq_key(root):return setting(root,'GROQ_API_KEY')


class GroqConnection:
    def __init__(self,root):
        self.root=root;self.lock=threading.Lock();self.checked=None;self.key_fingerprint=None
        self.result={'status':'configured' if groq_key(root) else 'not_configured','message':'Not checked yet','answers_enabled':False}

    def verify(self):
        with self.lock:
            key=groq_key(self.root)
            fingerprint=hashlib.sha256(key.encode()).hexdigest()
            if self.checked is not None and fingerprint==self.key_fingerprint and time.monotonic()-self.checked<60:return self.result
            status='not_configured';message='Add GROQ_API_KEY to the local .env file.'
            if key:
                try:
                    with httpx.Client(timeout=6,follow_redirects=False,trust_env=False) as client:
                        response=client.get('https://api.groq.com/openai/v1/models',headers={'Authorization':'Bearer '+key})
                    if response.status_code==200 and isinstance(response.json().get('data'),list):
                        status='connected';message='API authentication verified. No generation request was made.'
                    elif response.status_code in (401,403):
                        status='rejected';message='Groq rejected this key. Check the key and account permissions.'
                    elif response.status_code==429:
                        status='rate_limited';message='Groq is rate limited. Course search remains available.'
                    else:
                        status='unavailable';message='Groq verification failed. Course search remains available.'
                except (httpx.HTTPError,ValueError,TypeError,AttributeError):
                    status='unavailable';message='Groq could not be reached. Course search remains available.'
            self.result={'status':status,'message':message,'answers_enabled':False};self.checked=time.monotonic();self.key_fingerprint=fingerprint
            return self.result
