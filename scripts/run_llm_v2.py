"""Run a pinned local model on the full frozen V2 audit after engine/config freeze.

Outputs are actual generation, and accepted source copying is not answer accuracy.
V1 raw model evidence is never overwritten. No benchmark tuning is performed.
"""
import argparse
import datetime
import json
from pathlib import Path
import time
from evaluate_v2 import ROOT, sha, protected, write_json, save_rows, audit_questions, build_row, summarize, check_v1_manifest
from campuscompass import PolicyIndex
from campuscompass.llm import LocalGenerator

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend',choices=['flan','qwen'],default='qwen')
    parser.add_argument('--device',choices=['cpu','cuda'],default='cuda')
    parser.add_argument('--mode',choices=['bm25','dense','hybrid'],default='dense')
    parser.add_argument('--output',type=str,default='')
    parser.add_argument('--results-dir',type=Path,default=ROOT/'results/v2',help='Initialized V2 results directory containing its frozen configuration.')
    args=parser.parse_args()
    output=args.results_dir; check_v1_manifest(output)
    config=json.loads((output/'frozen_config.json').read_text(encoding='utf-8'))
    if sha(ROOT/'src/campuscompass/engine.py')!=config['engine_sha256']: raise RuntimeError('Engine changed since freeze.')
    if sha(ROOT/'src/campuscompass/engine_v1.py')!=config['inherited_engine_v1_sha256']: raise RuntimeError('Inherited retrieval source changed since freeze.')
    destination=output/(args.output or f'llm_audit_{args.backend}_{args.mode}.json')
    protected(destination)
    predictions=destination.with_suffix('.jsonl'); protected(predictions)
    questions=audit_questions(output)
    index=PolicyIndex(ROOT/'data/policies.jsonl'); index.mode_thresholds.update(config['thresholds'])
    index.retrieve('library borrowing',mode=args.mode,top_k=3)
    generator=LocalGenerator(args.backend,args.device)
    # The adapter is a separate component from frozen retrieval; record its hash.
    source_hash=sha(ROOT/'src/campuscompass/llm.py')
    docs={d['id']:d for d in index.documents}
    rows=[]
    for question in questions:
        ranked=[d['id'] for d in index.retrieve(question['query'],mode=args.mode,top_k=3)]
        start=time.perf_counter()
        prediction=generator.answer(index,question['query'],mode=args.mode,top_k=3)
        wall_ms=(time.perf_counter()-start)*1000
        row=build_row(question,prediction,ranked,docs,args.mode,wall_ms)
        # Phrases may omit sentence punctuation; canonical source substring must
        # be checked per source rather than treating joined excerpts as one sentence.
        if row['accepted']:
            evidence=prediction.get('generation_evidence',[])
            row['verbatim_supported']=bool(evidence) and all(g.get('source_excerpt') and g['source_excerpt'] in docs[g['source_id']]['text'] for g in evidence)
        rows.append(row)
        print(question['id'],prediction['status'],prediction.get('decision_reason'),flush=True)
    if source_hash!=sha(ROOT/'src/campuscompass/llm.py'): raise RuntimeError('LLM source changed during inference.')
    attempts=[r for r in rows if r['prediction'].get('generation_attempted')]
    report={'provenance':{'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'engine_sha256':config['engine_sha256'],'llm_sha256':source_hash,'audit_sha256':config['audit_sha256'],
      'model_id':generator.model_id,'model_revision':generator.revision,'backend':args.backend,'device':args.device,'retrieval_mode':args.mode,'threshold':config['thresholds'][args.mode],
      'model_load_seconds':generator.load_seconds,'design':'Full40 newly authored frozen audit. No selection or tuning on outputs; same project team, not external validation.',
      'interpretation':'Per-source canonical substring membership and gold policy evidence coverage are not semantic answer accuracy.'},
      'metrics':summarize(rows),'generation_attempts':len(attempts),'generation_source_candidates':sum(len(r['prediction'].get('generation_evidence',[])) for r in attempts),
      'raw_outputs_preserved':predictions.name}
    report['metrics']['categories']={category:summarize([r for r in rows if r['category']==category]) for category in sorted({r['category'] for r in rows})}
    save_rows(predictions,rows); write_json(destination,report)
    check_v1_manifest(output)
    print(json.dumps({'accepted':report['metrics']['accepted_n'],'attempts':len(attempts),'unsupported_accepts':report['metrics']['unsupported_accepts'],'complete_evidence_rate_all_supported':report['metrics']['complete_evidence_rate_all_supported']}),flush=True)

if __name__=='__main__': main()
