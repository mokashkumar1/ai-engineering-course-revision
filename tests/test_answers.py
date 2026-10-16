from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from answers import AnswerService,public_results,answer_language


class AnswerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.env=patch.dict(os.environ,{},clear=True);self.env.start()
        self.service=AnswerService(self.root,self.root)
        self.engine=SimpleNamespace(db_path=self.root/'course.sqlite')
        with closing(sqlite3.connect(self.engine.db_path)) as db, db:
            db.execute('CREATE TABLE chunks(id TEXT,lecture_id TEXT,text TEXT)')
            db.execute('INSERT INTO chunks VALUES(?,?,?)',('chunk-1','lecture-020','Private source text: tenant filters isolate customer documents.'))
        self.results=[{'lecture_id':'lecture-020','number':20,'title':'Multi-Tenant RAG',
            'video_id':'example1234','passages':[{'id':'chunk-1','text':'Private source text',
                'truncated':False,'start':100,'end':120,'timestamp_status':'approximate'}]}]

    def tearDown(self):self.env.stop();self.temp.cleanup()

    def configure(self):
        (self.root/'.env').write_text('GROQ_API_KEY=test-key\n')

    def test_language_and_script_are_explicit(self):
        self.assertEqual(answer_language('What is RAG?'),'English')
        self.assertTrue(answer_language('RAG kya hai?').startswith('Roman Urdu'))
        self.assertTrue(answer_language('रैग क्या है?').startswith('Hindi'))
        self.assertTrue(answer_language('راگ کیا ہے؟').startswith('Urdu'))

    def response(self,raw):
        response=SimpleNamespace(status_code=200,json=lambda:{'choices':[{'message':{'content':json.dumps(raw)}}]})
        client=patch('answers.httpx.Client');mock=client.start();self.addCleanup(client.stop)
        mock.return_value.__enter__.return_value.post.return_value=response
        return mock.return_value.__enter__.return_value.post

    def test_no_key_or_no_evidence_never_calls_provider(self):
        with patch('answers.httpx.Client') as http:
            self.assertEqual(self.service.answer('RAG',self.engine,self.results)['status'],'not_configured')
            self.configure()
            self.assertEqual(self.service.answer('RAG',self.engine,[])['status'],'no_evidence')
            http.assert_not_called()

    def test_citations_are_server_owned_and_source_text_is_not_returned(self):
        self.configure();post=self.response({'supported':True,'points':[{'text':'Tenant filters isolate documents.','sources':['S1']}]})
        result=self.service.answer('multi tenant RAG kya hai?',self.engine,self.results)
        self.assertEqual(result['status'],'answered')
        self.assertEqual(result['citations'][0]['youtube_url'],'https://www.youtube.com/watch?v=example1234&t=96s')
        self.assertNotIn('Private source',json.dumps(result))
        self.assertIn('Roman Urdu',post.call_args.kwargs['json']['messages'][0]['content'])
        self.service.answer('multi tenant RAG kya hai?',self.engine,self.results)
        self.assertEqual(post.call_count,1)

    def test_invented_citations_and_invalid_output_are_rejected(self):
        self.configure();self.response({'supported':True,'points':[{'text':'Made up','sources':['S99']}]})
        self.assertEqual(self.service.answer('RAG',self.engine,self.results)['status'],'unavailable')

    def test_quota_is_persistent_and_has_global_cap(self):
        (self.root/'.env').write_text('ANSWER_DAILY_CAP=2\n')
        self.assertTrue(self.service.reserve('client-a'))
        self.assertTrue(self.service.reserve('client-b'))
        restarted=AnswerService(self.root,self.root)
        self.assertFalse(restarted.reserve('client-c'))

    def test_provider_failure_does_not_return_error_body_or_secret(self):
        self.configure()
        with patch('answers.httpx.Client') as http:
            http.return_value.__enter__.return_value.post.return_value.status_code=429
            result=self.service.answer('RAG',self.engine,self.results)
        self.assertEqual(result,{'status':'rate_limited','points':[],'citations':[]})

    def test_public_search_payload_removes_transcript_text_without_mutating_evidence(self):
        result=public_results({'results':self.results})
        self.assertNotIn('text',result['results'][0]['passages'][0])
        self.assertIn('text',self.results[0]['passages'][0])

    def test_api_does_not_expose_transcripts_or_context(self):
        from app import app
        engine=SimpleNamespace(data=self.root,vector=None,lectures={'lecture-020':{}},
            load_semantic=lambda:None,search=lambda *args:{'results':self.results},
            status=lambda:{'answers_enabled':False})
        with patch('app.ROOT',self.root),patch('app.CourseSearch',return_value=engine),TestClient(app) as client:
            result=client.post('/api/search',json={'query':'RAG'})
            self.assertEqual(result.status_code,200)
            self.assertNotIn('Private source',result.text)
            self.assertEqual(client.get('/api/context/chunk-1').status_code,404)
            self.assertEqual(client.get('/.env').status_code,404)
            self.assertEqual(client.get('/search_data/course.sqlite').status_code,404)
            self.assertEqual(client.post('/api/answer',json={'query':'RAG'}).json()['status'],'not_configured')


if __name__=='__main__':unittest.main()
