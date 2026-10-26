"""Exercise the real local HTTP boundary without downloading any models."""
from http.server import ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import threading
import unittest
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('campuscompass_app',ROOT/'app.py')
app=importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.Handler.index=app.PolicyIndex(ROOT/'data'/'policies.jsonl',abstention_threshold=.35)
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        cls.url='http://127.0.0.1:'+str(cls.server.server_port)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=2)
    def request(self,data,headers=None):
        req=urllib.request.Request(self.url+'/api/answer',data=json.dumps(data).encode(),headers={'Content-Type':'application/json',**(headers or {})})
        return urllib.request.urlopen(req,timeout=5)
    def test_actual_answer_endpoint_and_citation(self):
        with self.request({'query':'How do I appeal a grade?','mode':'bm25'}) as r:
            result=json.load(r)
        self.assertEqual(result['status'],'answered')
        self.assertEqual(result['citations'][0]['id'],'P05')
    def test_cross_origin_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request({'query':'grade appeal'},headers={'Origin':'https://example.org'})
        self.assertEqual(error.exception.code,403)
    def test_invalid_mode_and_empty_question(self):
        for data in ({'query':'grade appeal','mode':'unknown'},{'query':''},[],None,{'query':'grade appeal','top_k':True}):
            with self.assertRaises(urllib.error.HTTPError) as error: self.request(data)
            self.assertEqual(error.exception.code,400)
    def test_health_endpoint(self):
        with urllib.request.urlopen(self.url+'/api/health') as r: result=json.load(r)
        self.assertEqual(result['policies'],30)
        self.assertEqual(len(result['corpus_sha256']),64)

if __name__=='__main__': unittest.main()
