"""Legacy V1 evaluator. V2 uses evaluate_v2.py and separate results/v2 outputs.

Tune refusal on DEV; freeze configuration; evaluate TEST and save raw predictions.

No API keys or paid judge are used. Retrieval and deterministic extractive answers
are evaluated, not the optional language model. Run optional LLM tests separately.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import re
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from campuscompass.engine_v1 import PolicyIndex


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def retrieval_scores(gold, ranked):
    """Macro recall gives partial credit on multi-document queries."""
    gold=set(gold)
    if not gold:
        return {}
    return {'recall_at_1':len(gold & set(ranked[:1]))/len(gold),
            'recall_at_3':len(gold & set(ranked[:3]))/len(gold),
            'hit_at_1':float(bool(gold & set(ranked[:1]))),
            'hit_at_3':float(bool(gold & set(ranked[:3]))),
            'complete_at_3':float(gold <= set(ranked[:3])),
            'mrr_at_3':next((1/(i+1) for i,pid in enumerate(ranked[:3]) if pid in gold),0.0)}


def verbatim_support(answer, citations, documents):
    """Checks copied sentences only; it cannot certify relevance or completeness."""
    clean=re.sub(r'\s*\[P\d+\]', '', answer).strip()
    sentences=[s.strip() for s in re.split(r'(?<=[.!?])\s+', clean) if s.strip()]
    texts=[documents[c['id']]['text'] for c in citations if c['id'] in documents]
    return bool(sentences and texts) and all(any(sentence in text for text in texts) for sentence in sentences)


def collect(index, examples, mode):
    docs={d['id']:d for d in index.documents}
    rows=[]
    for example in examples:
        started=time.perf_counter()
        prediction=index.answer(example['query'],mode=mode,top_k=3)
        elapsed=(time.perf_counter()-started)*1000
        ranked=[hit['id'] for hit in prediction['retrieved']]
        answered=prediction['status']=='answered'
        citations=[c['id'] for c in prediction['citations']]
        gold=set(example['relevant_ids'])
        row=dict(example,mode=mode,prediction=prediction,wall_latency_ms=round(elapsed,3),
                 answerability_correct=answered==example['answerable'],
                 relevant_citation_fraction=(len(set(citations)&gold)/len(citations) if citations else None),
                 cited_gold_coverage=(len(set(citations)&gold)/len(gold) if gold else None),
                 verbatim_supported=verbatim_support(prediction['answer'],prediction['citations'],docs) if answered else None,
                 topic_term_fraction=(sum(term.lower() in prediction['answer'].lower() for term in example['expected_terms'])/len(example['expected_terms']) if example['expected_terms'] and answered else None))
        row.update(retrieval_scores(gold,ranked))
        rows.append(row)
    return rows


def mean(values):
    return statistics.mean(values) if values else None


def nearest_rank_percentile(values, probability):
    """Empirical percentile: sorted[ceil(p*n)-1], bounded at p=0."""
    if not 0 <= probability <= 1:
        raise ValueError('Probability must be between zero and one.')
    return sorted(values)[max(0,math.ceil(probability*len(values))-1)] if values else None


def summarize(rows):
    positive=[r for r in rows if r['answerable']]
    negative=[r for r in rows if not r['answerable']]
    answered=[r for r in rows if r['prediction']['status']=='answered']
    supported_answered=[r for r in answered if r['answerable']]
    tp=sum(r['prediction']['status']=='answered' for r in positive)
    tn=sum(r['prediction']['status']=='abstained' for r in negative)
    result={'n':len(rows),'answerable_n':len(positive),'unanswerable_n':len(negative),
      'answered_n':len(answered),'answerability_accuracy':mean([float(r['answerability_correct']) for r in rows]),
      'answerable_acceptance':tp/len(positive) if positive else None,
      'unanswerable_rejection':tn/len(negative) if negative else None,
      'answer_precision':tp/len(answered) if answered else None,
      'coverage':len(answered)/len(rows) if rows else None,
      'false_accepts':len(negative)-tn,'false_abstentions':len(positive)-tp,
      'relevant_citation_precision':mean([r['relevant_citation_fraction'] for r in answered]),
      'gold_citation_coverage_answerable':mean([r['cited_gold_coverage'] or 0 for r in positive]),
      'verbatim_support_rate_answered':mean([float(r['verbatim_supported']) for r in answered]),
      'topic_terms_fraction_answered':mean([r['topic_term_fraction'] for r in supported_answered if r['topic_term_fraction'] is not None]),
      'latency_ms_median':statistics.median([r['wall_latency_ms'] for r in rows]) if rows else None,
      'latency_ms_p95':nearest_rank_percentile([r['wall_latency_ms'] for r in rows],.95)}
    for key in ('recall_at_1','recall_at_3','hit_at_1','hit_at_3','complete_at_3','mrr_at_3'):
        result[key]=mean([r[key] for r in positive])
    if positive and negative:
        result['answerability_balanced_accuracy']=(result['answerable_acceptance']+result['unanswerable_rejection'])/2
    return result


def bootstrap(rows,key,iterations=2000,seed=42):
    values=[float(r[key]) for r in rows if key in r and r[key] is not None]
    if not values: return None
    rng=random.Random(seed)
    samples=sorted(statistics.mean(rng.choices(values,k=len(values))) for _ in range(iterations))
    return [samples[int(.025*iterations)],samples[min(iterations-1,int(.975*iterations))]]


def tune(index,dev,mode):
    # Retrieve once: changing threshold affects only the refusal gate, not retrieval.
    index.abstention_threshold=0.0
    rows=collect(index,dev,mode)
    candidates=[]
    for threshold in [i/20 for i in range(1,19)]:
        for row in rows:
            pred=row['prediction']
            accepted=pred['status']=='answered' and pred['confidence']>=threshold
            row['_accepted']=accepted
        pos=[r for r in rows if r['answerable']]; neg=[r for r in rows if not r['answerable']]
        tpr=mean([float(r['_accepted']) for r in pos]); tnr=mean([float(not r['_accepted']) for r in neg])
        balanced=(tpr+tnr)/2
        candidates.append(dict(threshold=threshold,balanced_accuracy=balanced,answerable_acceptance=tpr,unanswerable_rejection=tnr))
    # Prefer rejection, then lower threshold, only when the main DEV score ties.
    best=max(candidates,key=lambda row:(row['balanced_accuracy'],row['unanswerable_rejection'],-row['threshold']))
    return best,candidates


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modes',nargs='+',default=['bm25','tfidf','lexical_hybrid'])
    parser.add_argument('--output',type=Path,default=ROOT/'results')
    parser.add_argument('--overwrite',action='store_true',help='Explicitly replace a completed benchmark; never use for TEST-based tuning.')
    args=parser.parse_args(argv)
    args.output.mkdir(parents=True,exist_ok=True)
    completed=args.output/'metrics.json'
    if completed.exists() and not args.overwrite:
        parser.error('Results already exist. Use a fresh --output or deliberate --overwrite.')
    examples=read_jsonl(ROOT/'data/evaluation.jsonl')
    dev=[q for q in examples if q['split']=='dev']; test=[q for q in examples if q['split']=='test']
    index=PolicyIndex(ROOT/'data/policies.jsonl')
    provenance={'corpus_sha256':index.corpus_sha256,'benchmark_sha256':hashlib.sha256((ROOT/'data/evaluation.jsonl').read_bytes()).hexdigest(),
      'seed':42,'dev_n':len(dev),'test_n':len(test),'test_use':'One evaluation pass per mode after dev-only threshold selection. Same project authors wrote corpus and benchmark; not independent validation.',
      'answer_method':'deterministic verbatim extractive baseline; optional LLM not scored here',
      'latency':'Wall-clock answer() time; model/index warmup excluded; sequential local runs; hardware-specific.',
      'metric_caveats':'Sentence support is verbatim membership, not entailment or relevance. Topic-term fraction is a broad topic diagnostic, not exact match or correctness. Macro retrieval recall uses answerable queries only. Bootstrap CIs are query-level percentile intervals, small authored sample, not a population guarantee.'}
    configuration={}; tuning={}
    # All model selection completes before any TEST predictions are collected.
    for mode in args.modes:
        index.retrieve('course withdrawal',mode=mode,top_k=3)
        best,candidates=tune(index,dev,mode)
        configuration[mode]=best['threshold']; tuning[mode]={'selected':best,'candidates':candidates}
    (args.output/'frozen_config.json').write_text(json.dumps(dict(provenance=provenance,thresholds=configuration),indent=2),encoding='utf-8')
    (args.output/'dev_tuning.json').write_text(json.dumps(tuning,indent=2),encoding='utf-8')
    results={'provenance':provenance,'modes':{}}
    for mode in args.modes:
        index.abstention_threshold=configuration[mode]
        rows=collect(index,test,mode)
        (args.output/f'test_predictions_{mode}.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
        metrics=summarize(rows)
        metrics['threshold']=configuration[mode]
        metrics['bootstrap_95_ci']={key:bootstrap(rows,key) for key in ('recall_at_1','recall_at_3','mrr_at_3','answerability_correct')}
        metrics['categories']={cat:summarize([r for r in rows if r['category']==cat]) for cat in sorted({r['category'] for r in rows})}
        results['modes'][mode]=metrics
        print(mode,json.dumps({k:metrics[k] for k in ('threshold','recall_at_1','recall_at_3','mrr_at_3','answerability_accuracy','false_accepts','false_abstentions')}))
    completed.write_text(json.dumps(results,indent=2),encoding='utf-8')
    failures=[]
    for mode in args.modes:
        for r in read_jsonl(args.output/f'test_predictions_{mode}.jsonl'):
            if not r['answerability_correct'] or r.get('complete_at_3',1)<1 or (r['answerable'] and (r['cited_gold_coverage'] or 0)<1):
                failures.append({'mode':mode,'id':r['id'],'query':r['query'],'gold':r['relevant_ids'],'retrieved':[h['id'] for h in r['prediction']['retrieved']],'status':r['prediction']['status'],'citations':r['prediction']['citations']})
    (args.output/'failures.json').write_text(json.dumps(failures,indent=2),encoding='utf-8')
    return results

if __name__=='__main__': main()
