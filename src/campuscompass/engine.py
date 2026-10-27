"""V2 facet-aware retrieval and verbatim evidence. V1 lives in engine_v1.py.

Confidence is lexical coverage OR neural cosine according to retrieval mode.
Neither is a probability, entailment judgment, or proof of relevance.
"""
from __future__ import annotations
from datetime import date
import json
from pathlib import Path
import re
import threading
import time
from .engine_v1 import PolicyIndex as V1PolicyIndex, tokenize, redact_pii

ENGINE_VERSION='2.0'
MODES=('bm25','tfidf','lexical_hybrid','dense','hybrid')
FIELDS=('id','title','department','version','effective_date','text')


def validate_request(query,mode='bm25',top_k=3):
    if not isinstance(query,str) or not query.strip() or len(query)>4000:
        raise ValueError('query must contain 1–4000 characters.')
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',query):
        raise ValueError('query contains unsupported control characters.')
    if not isinstance(mode,str) or mode not in MODES:
        raise ValueError('Unknown retrieval mode.')
    if type(top_k) is not int or not 1<=top_k<=10:
        raise ValueError('top_k must be an integer from 1 to 10.')


def safety_reason(query):
    """English intent patterns; no student-record or credential lookup exists."""
    q=query.casefold()
    if re.search(r'ignore\s+(?:(?:all|the|your)\s+)*(?:previous|prior|above|system|instructions)|(?:reveal|print|repeat|show|expose)\s+(?:the\s+|your\s+)?system\s+prompt|(?:act|pretend)\s+as\s+(?:an?\s+)?(?:admin|system)|(?:override|bypass)\s+(?:the\s+)?(?:guard|safety|instructions)',q):
        return 'instruction_override','The question requests an instruction override. Only policy questions are supported.'
    procedural=bool(re.search(r'\b(reset|recover|change|forgot|compromised|report|protect|secure)\b',q))
    if not procedural and re.search(r'\b(password|passphrase|api[ -]?key|secret[ -]?key|access[ -]?token|credentials)\b',q):
        return 'secret_request','Passwords, access tokens, and credentials cannot be retrieved. Ask about the public recovery procedure.'
    private=bool(re.search(r'\bmy\s+(?:grades|gpa|transcript|medical records)|\b(grades?|gpa|disciplinary|medical|health|bank|financial)\s+(?:records?|history|details|results)|\b(?:someone|another student|classmate|roommate|other student)\b.{0,70}\b(grades?|gpa|records?|address|phone)|\b(?:grades?|gpa|records?)\b.{0,50}\b(?:another|classmate|roommate)|\b[\w]+[’\x27]s\s+(?:grades?|gpa|transcript|medical|disciplinary)|\bstudent\s*(?:id|number)\s*[:#-]?\s*[\w-]+.{0,60}\b(grades?|gpa|records?)',q))
    process=bool(re.search(r'\b(how|procedure|process|request|correct|appeal|rights|privacy|protect|policy)\b',q))
    direct=bool(re.search(r'\b(show|reveal|retrieve|list|give me|tell me|look up|lookup|what (?:is|are))\b',q))
    third_party=bool(re.search(r'\b(?:classmate|roommate|another student|someone else)\b|\b[\w]+[’\x27]s\s+(?:grades?|gpa|transcript|medical|disciplinary)',q))
    if private and (third_party or not process):
        return 'private_record_request','This assistant searches public fictional policies and cannot disclose or look up individual student records.'
    return None


class PolicyIndex(V1PolicyIndex):
    def __init__(self,policies_path,abstention_threshold=.35):
        path=Path(policies_path)
        try:
            docs=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
            for d in docs:
                if not isinstance(d,dict) or set(d)!=set(FIELDS): raise ValueError('Each policy must have exactly the documented six fields.')
                if any(not isinstance(d[k],str) or not d[k].strip() for k in FIELDS): raise ValueError('Policy fields must be nonempty strings.')
                if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{1,39}',d['id']): raise ValueError('Invalid policy ID.')
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',d['effective_date']): raise ValueError('effective_date must use YYYY-MM-DD.')
                date.fromisoformat(d['effective_date'])
                if len(d['text'])>20000: raise ValueError('A policy exceeds the 20,000-character document limit.')
        except (json.JSONDecodeError,KeyError,TypeError) as exc:
            raise ValueError('Invalid policy corpus schema.') from exc
        if not isinstance(abstention_threshold,(int,float)) or isinstance(abstention_threshold,bool) or not 0<=abstention_threshold<=1:
            raise ValueError('abstention_threshold must be between zero and one.')
        super().__init__(path,abstention_threshold)
        self._retrieval_lock=threading.RLock()

    def retrieve(self,query,mode='bm25',top_k=3):
        validate_request(query,mode,top_k)
        query=redact_pii(query)
        with self._retrieval_lock:
            bm25=self._bm25(query)
            tfidf=self._tfidf(query)
            dense=self._dense_scores(query) if mode in ('dense','hybrid') else None
        if mode=='bm25': scores=bm25
        elif mode=='tfidf': scores=tfidf
        elif mode=='dense': scores=dense
        else:
            scores=[0.0]*len(self.documents)
            for values in (bm25,dense if mode=='hybrid' else tfidf):
                for rank,i in enumerate(sorted(range(len(values)),key=lambda i:(-values[i],self.documents[i]['id']))):
                    if values[i]>0: scores[i]+=1/(61+rank)
        order=sorted(range(len(scores)),key=lambda i:(-scores[i],self.documents[i]['id']))[:top_k]
        return [dict(self.documents[i],score=round(float(scores[i]),6),rank=rank+1,
                     component_scores={'bm25':round(bm25[i],6),'tfidf':round(tfidf[i],6),'dense_cosine':round(dense[i],6) if dense is not None else None})
                for rank,i in enumerate(order)]

    def _facets(self,query):
        clean=re.sub(r'\bmy\s+(?:email|student id|phone)\s+is\s+\[[A-Z_]+\][.!]?','',query,flags=re.I).strip()
        parts=re.split(r'\s+(?:and|also|as well as)\s+|\s*;\s*',clean,flags=re.I)
        if len(parts)<=1: return [clean]
        title_terms=set(t for d in self.documents for t in tokenize(d['title']))
        useful=[]
        for part in parts:
            terms=set(tokenize(part))
            if len(terms)>=2 or (terms & title_terms): useful.append(part.strip())
            else: return [clean]
        return useful[:4] if 1<len(useful)<=4 else [clean]

    def _relevance(self,facet,hit,mode):
        if mode in ('dense','hybrid'):
            return max(0.0,float(hit['component_scores']['dense_cosine'] or 0))
        terms=set(tokenize(re.sub(r'\[[A-Z_]+\]','',facet)))
        return len(terms & set(tokenize(hit['title']+' '+hit['text'])))/max(1,len(terms))

    def answer(self,query,mode='bm25',top_k=3):
        validate_request(query,mode,top_k)
        start=time.perf_counter()
        redacted=redact_pii(query)
        threshold=self.mode_thresholds.get(mode,self.abstention_threshold)
        metric='dense_cosine' if mode in ('dense','hybrid') else 'lexical_token_coverage'
        trace=[{'stage':'privacy_screen','result':'redacted' if redacted!=query else 'no_pattern_detected','detail':'Best-effort email, telephone and student-ID patterns; no raw query is logged.'}]
        safety=safety_reason(query)
        hits=[]; selected={}; facets=[]; scores=[]
        if safety:
            code,message=safety
            trace.append({'stage':'intent_guard','result':'refused','reason':code})
        else:
            trace.append({'stage':'intent_guard','result':'passed','detail':'Public policy scope only; English pattern rules are not a complete security boundary.'})
            planned=self._facets(redacted)
            trace.append({'stage':'query_plan','result':'multi_policy' if len(planned)>1 else 'single_question','facet_count':len(planned)})
            primary=self.retrieve(redacted,mode,top_k)
            pool={d['id']:d for d in primary}
            for facet in planned:
                candidates=self.retrieve(facet,mode,top_k) if len(planned)>1 else primary
                top=candidates[0] if candidates else None
                confidence=self._relevance(facet,top,mode) if top else 0.0
                supported=bool(top and top['score']>0 and tokenize(facet) and confidence>=threshold)
                scores.append(confidence)
                facets.append({'query':facet,'source_id':top['id'] if top else None,'relevance':round(confidence,6),'metric':metric,'threshold':threshold,'supported':supported})
                for doc in candidates: pool.setdefault(doc['id'],doc)
                if supported: selected[top['id']]=top
            hits=list(selected.values())+[d for pid,d in pool.items() if pid not in selected]
            hits=hits[:10]
            complete=bool(facets and all(f['supported'] for f in facets))
            code='supported_evidence' if complete else 'insufficient_relevance'
            message='\n\n'.join(d['text']+' ['+d['id']+']' for d in selected.values()) if complete else 'The collection does not support every part of this question above the selected relevance threshold. Inspect the candidate policies below or contact the relevant office.'
            trace.append({'stage':'relevance_gate','result':'passed' if complete else 'abstained','metric':metric,'threshold':threshold,'supported_facets':sum(f['supported'] for f in facets),'total_facets':len(facets),'detail':'Cosine is used directly for neural modes; lexical overlap is not a neural veto.'})
            trace.append({'stage':'evidence_assembly','result':'verbatim_policy_paragraphs','selected_ids':list(selected),'detail':'Complete short policy paragraphs preserve nearby exceptions and conditions. Relevance and completeness still require human judgment.'})
        answered=not safety and bool(facets and all(f['supported'] for f in facets))
        citations=[{k:d[k] for k in FIELDS if k!='text'} for d in selected.values()] if answered else []
        evidence=[]
        for rank,d in enumerate(hits):
            evidence.append({**{k:d[k] for k in FIELDS if k!='text'},'rank':rank+1,'score':d['score'],'component_scores':d['component_scores'],'selected':d['id'] in selected,'reason':'Supports a query facet above threshold' if d['id'] in selected else 'Retrieved candidate; relevance is unverified','excerpts':[d['text']],'source_text':d['text']})
        return {'engine_version':ENGINE_VERSION,'status':'answered' if answered else 'abstained','decision_reason':code,'answer':message,'citations':citations,
                'confidence':round(min(scores) if scores else 0.0,6),'confidence_definition':('Minimum best-policy encoder cosine across query facets.' if metric=='dense_cosine' else 'Minimum query-facet token coverage in its best retrieved policy.')+' Heuristic, not a probability or entailment judgment.',
                'confidence_metric':metric,'threshold':threshold,'redacted_query':redacted,'latency_ms':round((time.perf_counter()-start)*1000,3),'mode':mode,'answer_method':'V2 complete-policy verbatim evidence extraction',
                'retrieved':[{k:d[k] for k in ('id','title','score','component_scores')} for d in hits], 'evidence':evidence,'decision_trace':trace,
                'coverage':{'facets':facets,'total':len(facets),'supported':sum(f['supported'] for f in facets),'complete':answered},'corpus_sha256':self.corpus_sha256}

    def verify_citations(self,response):
        known={d['id']:d for d in self.documents}
        citations=response.get('citations',[])
        if response.get('status')=='answered' and not citations: return False
        if any(c.get('id') not in known or '['+c['id']+']' not in response.get('answer','') for c in citations): return False
        for e in response.get('evidence',[]):
            if e.get('id') not in known or any(excerpt not in known[e['id']]['text'] for excerpt in e.get('excerpts',[])): return False
        return True
