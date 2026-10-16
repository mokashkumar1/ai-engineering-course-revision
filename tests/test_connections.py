import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from connections import GroqConnection,groq_key


class ConnectionTests(unittest.TestCase):
    def test_missing_key_does_not_make_network_request(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True),patch('connections.httpx.Client') as client:
            result=GroqConnection(tmp).verify()
            self.assertEqual(result['status'],'not_configured')
            client.assert_not_called()

    def test_verified_connection_keeps_answers_disabled_and_key_private(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True),patch('connections.httpx.Client') as factory:
            (Path(tmp)/'.env').write_text('GROQ_API_KEY="unit-test-private-key"\n',encoding='utf-8')
            client=factory.return_value.__enter__.return_value
            client.get.return_value.status_code=200
            client.get.return_value.json.return_value={'data':[{'id':'test-model'}]}
            connection=GroqConnection(tmp);result=connection.verify()
            self.assertEqual(result['status'],'connected')
            self.assertFalse(result['answers_enabled'])
            self.assertNotIn('unit-test-private-key',json.dumps(result))
            connection.verify()
            self.assertEqual(client.get.call_count,1)
            self.assertFalse(factory.call_args.kwargs['follow_redirects'])

    def test_changed_key_invalidates_cached_rejection(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True),patch('connections.httpx.Client') as factory:
            path=Path(tmp)/'.env';path.write_text('GROQ_API_KEY=first-test-key\n',encoding='utf-8')
            client=factory.return_value.__enter__.return_value
            client.get.return_value.status_code=401
            connection=GroqConnection(tmp)
            self.assertEqual(connection.verify()['status'],'rejected')
            path.write_text('GROQ_API_KEY=second-test-key\n',encoding='utf-8')
            client.get.return_value.status_code=200;client.get.return_value.json.return_value={'data':[]}
            self.assertEqual(connection.verify()['status'],'connected')
            self.assertEqual(client.get.call_count,2)

    def test_env_parser_handles_quotes_and_comments(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True):
            path=Path(tmp)/'.env';path.write_text('GROQ_API_KEY="test-key" # note\n',encoding='utf-8')
            self.assertEqual(groq_key(tmp),'test-key')
