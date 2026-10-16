"""Local search demo. Run with one worker; Qdrant embedded is process-local."""
from contextlib import asynccontextmanager
from collections import defaultdict,deque
import threading
import time

from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field

from search_engine import CourseSearch,ROOT
from connections import GroqConnection
from answers import AnswerService,public_results


@asynccontextmanager
async def lifespan(app):
    engine=CourseSearch()
    engine.load_semantic()
    app.state.engine=engine
    app.state.groq=GroqConnection(ROOT)
    app.state.answers=AnswerService(ROOT,engine.data)
    yield
    if engine.vector:engine.vector.close()


app=FastAPI(title='RAG YT RIVISION',docs_url=None,redoc_url=None,lifespan=lifespan)
app.mount('/assets',StaticFiles(directory=ROOT/'frontend'),name='assets')
requests_by_ip=defaultdict(deque)
rate_lock=threading.Lock()


@app.middleware('http')
async def avoid_stale_ui(request,call_next):
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    return response


def connection_state(request):
    engine=request.app.state.engine
    catalogue=engine.catalogue()
    return {'search':{'status':'connected','lectures':len(catalogue),'passages':engine.manifest['passages']},
        'qdrant':{'status':'connected' if engine.vector is not None else 'unavailable','mode':'embedded local','semantic':engine.semantic_status},
        'youtube':{'status':'mapped','videos':sum(bool(l['video_id']) for l in catalogue),'title_review_needed':sum(l['mapping_status']!='verified' for l in catalogue)},
        'groq':{**request.app.state.groq.result,'answers_enabled':request.app.state.answers.available()},'answers_enabled':request.app.state.answers.available(),'app_url':str(request.base_url).rstrip('/')}


@app.get('/api/connections')
def connections(request:Request):return connection_state(request)


@app.post('/api/connections/check')
def check_connections(request:Request):
    request.app.state.groq.verify()
    return connection_state(request)


class SearchRequest(BaseModel):
    query:str=Field(min_length=2,max_length=500)
    lecture_ids:list[str]=Field(default_factory=list,max_length=36)
    topic:str|None=None
    limit:int=Field(default=6,ge=1,le=12)


@app.get('/')
def home():return FileResponse(ROOT/'frontend'/'index.html')


@app.get('/api/status')
def status(request:Request):
    result=request.app.state.engine.status()
    result['answers_enabled']=request.app.state.answers.available()
    return result


@app.get('/api/lectures')
def lectures(request:Request):return request.app.state.engine.catalogue()


@app.post('/api/search')
def search(body:SearchRequest,request:Request):
    now=time.monotonic();ip=request.client.host if request.client else 'local'
    with rate_lock:
        queue=requests_by_ip[ip]
        while queue and now-queue[0]>=86400:queue.popleft()
        if len(queue)>=1000 or sum(now-t<60 for t in queue)>=30:
            raise HTTPException(429,'Search limit reached. Please try again later.',headers={'Retry-After':'60'})
        queue.append(now)
    engine=request.app.state.engine
    if body.topic and body.topic not in {'Foundations','RAG','Agents','MCP'}:
        raise HTTPException(422,'Unknown topic')
    if any(id not in engine.lectures for id in body.lecture_ids):raise HTTPException(422,'Unknown lecture')
    return public_results(engine.search(body.query.strip(),body.lecture_ids,body.topic,body.limit))


@app.get('/api/context/{chunk_id}')
def context(chunk_id:str,request:Request):
    raise HTTPException(404,'Transcript context is internal.')


@app.post('/api/answer')
def answer(body:SearchRequest,request:Request):
    # Apply the same validation and request limits as search; evidence is never client supplied.
    result=search(body,request)
    return request.app.state.answers.answer(body.query.strip(),request.app.state.engine,
        result['results'],request.client.host if request.client else 'local')


@app.get('/healthz')
def health(request:Request):
    return {'status':'ok','lectures':len(request.app.state.engine.lectures),
            'semantic':request.app.state.engine.semantic_status}
