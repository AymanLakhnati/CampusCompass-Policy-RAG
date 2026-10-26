"""Run: python app.py; API: POST /api/answer {query, mode, top_k}."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from campuscompass import PolicyIndex
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

ROOT=Path(__file__).resolve().parent


class Handler(BaseHTTPRequestHandler):
    index=None
    generators={}
    generation_lock=threading.Lock()
    def log_message(self,*args):
        pass  # Do not retain URLs, raw questions, or access logs.
    def send_json(self,data,status=200):
        payload=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(payload))); self.end_headers(); self.wfile.write(payload)
    def do_GET(self):
        if self.path=='/api/health': return self.send_json({'status':'ok','policies':len(self.index.documents),'corpus_sha256':self.index.corpus_sha256})
        if self.path=='/api/policies': return self.send_json(self.index.documents)
        if self.path!='/': return self.send_json({'error':'Not found'},404)
        payload=(ROOT/'src'/'campuscompass'/'web.html').read_bytes()
        self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(payload))); self.end_headers(); self.wfile.write(payload)
    def do_POST(self):
        if self.path!='/api/answer': return self.send_json({'error':'Not found'},404)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=16000: return self.send_json({'error':'Body must be between 1 and 16000 bytes.'},413)
            payload=self.rfile.read(length)
            origin=self.headers.get('Origin','')
            if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
                return self.send_json({'error':'Cross-origin requests are disabled.'},403)
            body=json.loads(payload)
            if not isinstance(body,dict): raise ValueError('Request body must be a JSON object.')
            query=body.get('query','')
            if not isinstance(query,str) or not query.strip() or len(query)>4000: raise ValueError('Query must contain 1–4000 characters.')
            top_k=body.get('top_k',3)
            if isinstance(top_k,bool) or not isinstance(top_k,int) or not 1<=top_k<=10: raise ValueError('top_k must be an integer from 1 to 10.')
            if body.get('mode','bm25') not in ('bm25','tfidf','lexical_hybrid','dense','hybrid'): raise ValueError('Unknown retrieval mode.')
            mode=body.get('mode','bm25')
            backend=body.get('backend','extractive')
            if backend not in ('extractive','flan','qwen'): raise ValueError('Unknown answer backend.')
            if backend=='extractive': return self.send_json(self.index.answer(query,mode,top_k))
            # Serialize optional model loading/inference to avoid duplicate GPU/RAM use.
            from campuscompass.llm import LocalGenerator
            with self.generation_lock:
                if backend not in self.generators:
                    import torch
                    self.generators[backend]=LocalGenerator(backend,'cuda' if torch.cuda.is_available() else 'cpu')
                result=self.generators[backend].answer(self.index,query,mode,top_k)
            return self.send_json(result)
        except (ValueError,TypeError,json.JSONDecodeError) as exc: return self.send_json({'error':str(exc)},400)
        except Exception as exc: return self.send_json({'error':'Optional model unavailable or request failed. Install requirements-ml.txt, check internet access for the first model download, or select extractive mode. '+type(exc).__name__},500)


def main():
    parser=argparse.ArgumentParser(description='CampusCompass local policy assistant')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--query',help='Print a JSON answer and exit')
    parser.add_argument('--mode',choices=['bm25','tfidf','lexical_hybrid','hybrid','dense'],default='bm25')
    parser.add_argument('--corpus',type=Path,default=ROOT/'data'/'policies.jsonl')
    parser.add_argument('--backend',choices=['extractive','flan','qwen'],default='extractive')
    args=parser.parse_args(); Handler.index=PolicyIndex(args.corpus,abstention_threshold=.35)
    for config in (ROOT/'results'/'lexical'/'frozen_config.json',ROOT/'results'/'neural'/'frozen_config.json'):
        if config.exists(): Handler.index.mode_thresholds.update(json.loads(config.read_text(encoding='utf-8')).get('thresholds',{}))
    if args.query:
        if args.backend=='extractive': result=Handler.index.answer(args.query,args.mode)
        else:
            from campuscompass.llm import LocalGenerator
            result=LocalGenerator(args.backend).answer(Handler.index,args.query,args.mode)
        print(json.dumps(result,indent=2,ensure_ascii=False)); return
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'CampusCompass running at http://127.0.0.1:{args.port} (Ctrl+C to stop). No query logging.')
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=='__main__': main()
