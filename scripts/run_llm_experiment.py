"""Reproducible CPU generation experiment; save actual outputs and timing.

Use --limit 12 for a smoke experiment. Full test split is the default.
Model download and loading time is recorded separately from inference latency.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import argparse
import datetime
import json
import platform
import statistics
import time
from campuscompass.engine_v1 import PolicyIndex
from campuscompass.llm_v1 import LocalGenerator, MODEL_ID, MODEL_REVISION


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--limit',type=int,default=0)
    p.add_argument('--split',choices=['dev','test'],default='test')
    p.add_argument('--mode',choices=['bm25','dense','hybrid'],default='bm25')
    p.add_argument('--backend',choices=['flan','qwen'],default='flan')
    p.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    p.add_argument('--output',type=Path,default=ROOT/'results'/'llm_experiment.json')
    args=p.parse_args()
    experiment_start=datetime.datetime.now(datetime.timezone.utc)
    experiment_clock=time.perf_counter()
    index=PolicyIndex(ROOT/'data'/'policies.jsonl')
    config=ROOT/'results'/('neural' if args.mode in ('dense','hybrid') else 'lexical')/'frozen_config.json'
    if config.exists():
        obj=json.loads(config.read_text(encoding='utf-8'))
        # Different evaluation releases may persist threshold as a scalar or dict.
        value=obj.get('thresholds',{}).get(args.mode)
        if isinstance(value,(int,float)): index.abstention_threshold=value
        elif isinstance(value,dict) and 'threshold' in value: index.abstention_threshold=value['threshold']
    rows=[json.loads(line) for line in (ROOT/'data'/'evaluation.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    rows=[r for r in rows if r['split']==args.split]
    if args.limit: rows=rows[:args.limit]
    print('Loading pinned model backend '+args.backend,flush=True)
    generator=LocalGenerator(args.backend,args.device)
    outputs=[]
    for row in rows:
        result=generator.answer(index,row['query'],mode=args.mode)
        outputs.append({'id':row['id'],'expected_answerable':row['answerable'],'relevant_ids':row['relevant_ids'],'expected_terms':row.get('expected_terms',[]),'response':result})
        print(row['id'],result['status'],result.get('raw_model_output'),flush=True)
    answered=[r for r in outputs if r['response']['status']=='answered']
    generations=[r for r in outputs if r['response'].get('generation_attempted')]
    correct_cited=sum(any(c['id'] in r['relevant_ids'] for c in r['response']['citations']) for r in answered)
    report={'experiment':'Actual deterministic local generation; exact-source gate','model_id':generator.model_id,'model_revision':generator.revision,'device':args.device,'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'python':platform.python_version(),'platform':platform.platform(),'corpus_sha256':index.corpus_sha256,'retrieval_mode':args.mode,'abstention_threshold':index.abstention_threshold,'split':args.split,'n':len(outputs),'load_seconds':round(generator.load_seconds,3),'generation_attempts':len(generations),'accepted_answers':len(answered),'correct_cited_policy_among_accepted':correct_cited,'answer_coverage':len(answered)/len(outputs) if outputs else 0,'mean_generation_ms':statistics.mean(r['response']['generation_ms'] for r in generations) if generations else None,'notes':['No answer quality or entailment claim follows from exact-substring support.','Expected term checks are synthetic checks, not a validated human correctness rating.','Raw model output is retained only for public synthetic evaluation questions. The app does not log live questions.'],'outputs':outputs}
    report.update(started_utc=experiment_start.isoformat(),elapsed_seconds=round(time.perf_counter()-experiment_clock,3),median_generation_ms=statistics.median(r['response']['generation_ms'] for r in generations) if generations else None)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print('Saved '+str(args.output),flush=True)

if __name__=='__main__': main()
