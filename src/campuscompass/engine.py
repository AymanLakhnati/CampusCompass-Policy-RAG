"""A small, auditable RAG baseline; retrieval does not imply answer correctness.

The default path needs only Python. The optional dense path downloads a pinned
Hugging Face encoder and never silently substitutes a different retriever.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import time

STOP = set('a an the is are was were be been to of for in on at by and or with from can could would should do does did how what when where which who i my me we our you your it its this that if as about please tell find explain policy policies university campus'.split())
ALIASES = {'fees':'fee','payments':'payment','deadlines':'deadline','appeals':'appeal','courses':'course','classes':'class','students':'student','scholarships':'scholarship','exams':'exam','books':'book','parking':'park','withdrawal':'withdraw','withdrawing':'withdraw','dropped':'drop','dropping':'drop','extensions':'extension','accommodations':'accommodation','complaints':'complaint','records':'record','refunds':'refund','dorm':'housing','dormitory':'housing','wifi':'wireless'}


def tokenize(text):
    return [ALIASES.get(t, t) for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP and len(t)>1]


def redact_pii(text):
    """Best-effort screening, not a complete privacy or anonymization guarantee."""
    text = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[EMAIL]', text)
    text = re.sub(r'\b(?:\+?\d[\d ()-]{7,}\d)\b', '[NUMBER]', text)
    text = re.sub(r'\b(?:student\s*(?:id|number)|sid)\s*[:#-]?\s*[A-Za-z0-9-]+', '[STUDENT_ID]', text, flags=re.I)
    return text


class PolicyIndex:
    def __init__(self, policies_path, abstention_threshold=0.22):
        self.policies_path = Path(policies_path)
        self.documents = [json.loads(s) for s in self.policies_path.read_text(encoding='utf-8').splitlines() if s.strip()]
        if not self.documents or len({d['id'] for d in self.documents}) != len(self.documents):
            raise ValueError('Corpus must contain policies with unique IDs.')
        self.abstention_threshold = abstention_threshold
        self.mode_thresholds = {}
        self._counts = [Counter(tokenize(d['title']+' '+d['title']+' '+d['text'])) for d in self.documents]
        self._lengths = [sum(c.values()) for c in self._counts]
        self._avg = sum(self._lengths)/len(self._lengths)
        self._df = Counter(t for c in self._counts for t in c)
        self._dense = None

    def _bm25(self, query):
        tokens = tokenize(query)
        n = len(self.documents)
        return [sum(math.log(1+(n-self._df[t]+0.5)/(self._df[t]+0.5)) * c[t]*2.5/(c[t]+1.5*(0.25+0.75*length/self._avg)) for t in tokens if c[t]) for c,length in zip(self._counts,self._lengths)]

    def _tfidf(self, query):
        # This is explicitly a sparse word-vector baseline, not a neural embedding.
        n = len(self.documents)
        def vector(c):
            return {t:(1+math.log(v))*math.log((n+1)/(self._df[t]+1))+1 for t,v in c.items()}
        q = vector(Counter(tokenize(query)))
        qnorm = math.sqrt(sum(v*v for v in q.values())) or 1
        out=[]
        for c in self._counts:
            v=vector(c); norm=math.sqrt(sum(x*x for x in v.values())) or 1
            out.append(sum(value*v.get(t,0) for t,value in q.items())/(qnorm*norm))
        return out

    def _dense_scores(self, query):
        try:
            import truststore
            truststore.inject_into_ssl()
        except ImportError:
            pass
        try:
            import torch
            from transformers import AutoTokenizer, AutoModel
        except ImportError as exc:
            raise RuntimeError('Dense retrieval requires torch and transformers; install requirements-ml.txt.') from exc
        if self._dense is None:
            model_id='sentence-transformers/all-MiniLM-L6-v2'
            revision='c9745ed1d9f207416be6d2e6f8de32d1f16199bf'
            tokenizer=AutoTokenizer.from_pretrained(model_id,revision=revision)
            model=AutoModel.from_pretrained(model_id,revision=revision).eval()
            torch.set_num_threads(min(4,torch.get_num_threads()))
            def embed(texts):
                batch=tokenizer(texts,padding=True,truncation=True,max_length=256,return_tensors='pt')
                with torch.inference_mode():
                    hidden=model(**batch).last_hidden_state
                    mask=batch['attention_mask'].unsqueeze(-1)
                    pooled=(hidden*mask).sum(1)/mask.sum(1).clamp(min=1)
                    return torch.nn.functional.normalize(pooled,p=2,dim=1)
            self._dense=(embed,embed([d['title']+'. '+d['text'] for d in self.documents]))
        embed, vectors=self._dense
        return (embed([query]) @ vectors.T)[0].tolist()

    def retrieve(self, query, mode='bm25', top_k=3):
        query=redact_pii(query)
        if mode=='bm25': scores=self._bm25(query)
        elif mode=='tfidf': scores=self._tfidf(query)
        elif mode=='dense': scores=self._dense_scores(query)
        elif mode in ('hybrid','lexical_hybrid'):
            scores=[0.0]*len(self.documents)
            # Neural hybrid combines BM25 and dense; lexical fusion is separate.
            for values in (self._bm25(query),self._dense_scores(query) if mode=='hybrid' else self._tfidf(query)):
                for rank,i in enumerate(sorted(range(len(values)), key=lambda i:(-values[i],self.documents[i]['id']))):
                    if values[i]>0: scores[i]+=1/(60+rank+1)
        else: raise ValueError('mode must be bm25, tfidf, lexical_hybrid, hybrid, or dense')
        order=sorted(range(len(scores)), key=lambda i:(-scores[i],self.documents[i]['id']))[:max(0,min(top_k,10))]
        return [dict(self.documents[i],score=round(float(scores[i]),6)) for i in order]

    def answer(self, query, mode='bm25', top_k=3):
        start=time.perf_counter()
        redacted=redact_pii(query[:4000])
        hits=self.retrieve(redacted,mode,top_k)
        terms=set(tokenize(redacted))
        confidence= len(terms & set(tokenize(hits[0]['title']+' '+hits[0]['text'])))/max(1,len(terms)) if hits else 0.0
        # Confidence is an overlap heuristic, not a calibrated probability.
        unsafe = bool(re.search(r'ignore\s+(?:all\s+)?(?:previous|instructions)|system\s+prompt|reveal\s+(?:secrets|password)', redacted,re.I))
        threshold=self.mode_thresholds.get(mode,self.abstention_threshold)
        status='abstained' if unsafe or not hits or not terms or confidence<threshold or hits[0]['score']<=0 else 'answered'
        citations=[]
        answer='I could not find enough support in the demonstration policies. Please contact the relevant university office; do not rely on a guessed answer.'
        if status=='answered':
            doc=hits[0]
            sentences=re.split(r'(?<=[.!?])\s+',doc['text'])
            ranked=sorted(enumerate(sentences),key=lambda pair:(-len(terms & set(tokenize(pair[1]))),pair[0]))[:3]
            # Preserve source order and verbatim text, making support inspectable.
            answer=' '.join(s for _,s in sorted(ranked))+f" [{doc['id']}]"
            citations=[{key:doc.get(key,'') for key in ('id','title','department','version','effective_date')}]
        return {'status':status,'answer':answer,'citations':citations,'confidence':round(confidence,4),'confidence_definition':'Fraction of content query tokens present in highest-ranked policy; not a probability.','redacted_query':redacted,'latency_ms':round((time.perf_counter()-start)*1000,3),'mode':mode,'answer_method':'verbatim extractive baseline','retrieved':[{k:d[k] for k in ('id','title','score')} for d in hits]}

    def verify_citations(self, response):
        known={d['id'] for d in self.documents}
        return all(c['id'] in known and '['+c['id']+']' in response['answer'] for c in response['citations'])

    @property
    def corpus_sha256(self):
        return hashlib.sha256(self.policies_path.read_bytes()).hexdigest()
