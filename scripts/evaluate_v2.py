"""Versioned V2 calibration and evaluation. V1 evidence is never overwritten.

Stages: baseline (new audit using frozen V1), calibrate (DEV only), evaluate
(reused TEST regression plus fresh audit after source/config freeze), summarize.
This is a project-authored engineering-blind audit, not external validation.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import statistics
import sys
import time

from evaluate import ROOT, read_jsonl, retrieval_scores, verbatim_support, nearest_rank_percentile, bootstrap
sys.path.insert(0,str(ROOT/'src'))

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write_json(path,obj): Path(path).write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
def save_rows(path,rows): Path(path).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
def protected(path):
    if Path(path).exists(): raise RuntimeError(f'Refusing to overwrite recorded evidence: {path}')

def check_v1_manifest(output):
    manifest=json.loads((output/'v1_evidence_manifest.json').read_text(encoding='utf-8'))
    for relative,digest in manifest['sha256'].items():
        if sha(ROOT/'results'/relative)!=digest: raise RuntimeError(f'V1 evidence changed: {relative}')
    return len(manifest['sha256'])

def audit_questions(output):
    frozen=json.loads((output/'audit_freeze.json').read_text(encoding='utf-8'))
    if sha(ROOT/'data/v2_audit.jsonl')!=frozen['audit_sha256']: raise RuntimeError('Frozen new audit questions changed.')
    return read_jsonl(ROOT/'data/v2_audit.jsonl')

def initialize(output):
    """Seed a fresh reproduction directory; never alter the reference evidence."""
    source=ROOT/'results/v2'
    if output.resolve()==source.resolve():
        raise RuntimeError('The reference results directory is already initialized. Choose a new --output directory.')
    if any(output.iterdir()):
        raise RuntimeError('Initialization requires an empty output directory; existing files are preserved.')
    for name in ('audit_freeze.json','v1_evidence_manifest.json'):
        shutil.copyfile(source/name,output/name)
    shutil.copytree(source/'reference_code',output/'reference_code',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    check_v1_manifest(output); audit_questions(output)
    print('Initialized fresh reproduction directory:',output,flush=True)

def collect(index,examples,mode,raw_retrieval=True):
    docs={d['id']:d for d in index.documents}
    rows=[]
    for example in examples:
        if raw_retrieval:
            start=time.perf_counter()
            raw=index.retrieve(example['query'],mode=mode,top_k=3)
            retrieval_ms=(time.perf_counter()-start)*1000
        start=time.perf_counter()
        prediction=index.answer(example['query'],mode=mode,top_k=3)
        wall_ms=(time.perf_counter()-start)*1000
        if not raw_retrieval:
            raw=prediction['retrieved']; retrieval_ms=None
        row=build_row(example,prediction,[d['id'] for d in raw],docs,mode,wall_ms,retrieval_ms)
        rows.append(row)
    return rows

def build_row(example,prediction,ranked,docs,mode,wall_ms,retrieval_ms=None):
    accepted=prediction['status']=='answered'
    cited={c['id'] for c in prediction['citations']}
    gold=set(example['relevant_ids'])
    source_copy=verbatim_support(prediction['answer'],prediction['citations'],docs) if accepted else None
    return dict(example,mode=mode,prediction=prediction,raw_query_retrieved=ranked,
      wall_latency_ms=round(wall_ms,3),retrieval_latency_ms=round(retrieval_ms,3) if retrieval_ms is not None else None,
      accepted=accepted,answerability_correct=accepted==example['answerable'],
      gold_evidence_coverage=len(cited&gold)/len(gold) if gold and accepted else 0.0 if gold else None,
      relevant_citation_precision=len(cited&gold)/len(cited) if cited else None,
      complete_gold_evidence=bool(gold and accepted and gold<=cited),
      verbatim_supported=source_copy,
      **retrieval_scores(gold,ranked))

def average(values): return statistics.mean(values) if values else None
def summarize(rows):
    positives=[r for r in rows if r['answerable']]; negatives=[r for r in rows if not r['answerable']]
    accepted=[r for r in rows if r['accepted']]; accepted_positive=[r for r in positives if r['accepted']]
    false_accepts=sum(r['accepted'] for r in negatives)
    false_refusals=sum(not r['accepted'] for r in positives)
    tpr=average([float(r['accepted']) for r in positives]); tnr=average([float(not r['accepted']) for r in negatives])
    result={'n':len(rows),'answerable_n':len(positives),'unsupported_n':len(negatives),
      'accepted_n':len(accepted),'answer_coverage':len(accepted)/len(rows) if rows else None,
      'answerability_accuracy':average([float(r['answerability_correct']) for r in rows]),
      'answerable_acceptance':tpr,'unsupported_rejection':tnr,
      'answerability_balanced_accuracy':(tpr+tnr)/2 if tpr is not None and tnr is not None else None,
      'unsupported_accepts':false_accepts,'false_refusals':false_refusals,
      'gold_evidence_coverage':average([r['gold_evidence_coverage'] for r in positives]),
      'complete_evidence_rate_all_supported':average([float(r['complete_gold_evidence']) for r in positives]),
      'complete_evidence_rate_accepted_supported':average([float(r['complete_gold_evidence']) for r in accepted_positive]),
      'gold_citation_precision_accepted':average([r['relevant_citation_precision'] for r in accepted]),
      'verbatim_support_rate_accepted':average([float(r['verbatim_supported']) for r in accepted]),
      'latency_ms_median':statistics.median([r['wall_latency_ms'] for r in rows]) if rows else None,
      'latency_ms_p95':nearest_rank_percentile([r['wall_latency_ms'] for r in rows],.95),
      'semantic_answer_accuracy':'Not measured: exact-source membership and gold policy coverage do not establish entailment, relevance of each sentence, or a correct decision.'}
    for key in ('recall_at_1','recall_at_3','hit_at_1','hit_at_3','complete_at_3','mrr_at_3'):
        result[key]=average([r[key] for r in positives])
    result['bootstrap_95_ci']={key:bootstrap(positives if key=='complete_gold_evidence' else rows,key) for key in ('recall_at_3','mrr_at_3','answerability_correct','complete_gold_evidence')}
    return result

def baseline(output,modes):
    source=output/'reference_code/engine_v1.py'
    freeze=json.loads((output/'audit_freeze.json').read_text(encoding='utf-8'))
    assert sha(source)==freeze['v1_engine_sha256']
    spec=importlib.util.spec_from_file_location('frozen_campuscompass_v1',source)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    index=module.PolicyIndex(ROOT/'data/policies.jsonl')
    audit=audit_questions(output)
    for mode in modes:
        destination=output/f'v1_audit_predictions_{mode}.jsonl'; protected(destination)
        old='neural' if mode in ('dense','hybrid') else 'lexical'
        config=json.loads((ROOT/f'results/{old}/frozen_config.json').read_text(encoding='utf-8'))
        index.abstention_threshold=config['thresholds'][mode]
        index.retrieve('library borrowing',mode=mode,top_k=3)
        save_rows(destination,collect(index,audit,mode))
        # Reuse original TEST observations; never rerun them to inflate before/after.
        destination=output/f'v1_regression_predictions_{mode}.jsonl'; protected(destination)
        documents={d['id']:d for d in index.documents}
        original=read_jsonl(ROOT/f'results/{old}/test_predictions_{mode}.jsonl')
        rows=[build_row(r,r['prediction'],[d['id'] for d in r['prediction']['retrieved']],documents,mode,r['wall_latency_ms']) for r in original]
        save_rows(destination,rows)
        print('V1 audit baseline',mode,flush=True)

def calibrate(output,modes):
    protected(output/'frozen_config.json')
    from campuscompass import PolicyIndex
    index=PolicyIndex(ROOT/'data/policies.jsonl')
    dev=[q for q in read_jsonl(ROOT/'data/evaluation.jsonl') if q['split']=='dev']
    grid=[round(.20+i*.025,6) for i in range(17)]
    candidates={}; thresholds={}
    for mode in modes:
        index.mode_thresholds[mode]=0.0; index.abstention_threshold=0.0
        index.retrieve('library borrowing',mode=mode,top_k=3)
        rows=collect(index,dev,mode)
        save_rows(output/f'dev_zero_threshold_predictions_{mode}.jsonl',rows)
        scores=[]
        for threshold in grid:
            simulated=copy.deepcopy(rows)
            for row in simulated:
                accept=row['accepted'] and row['prediction']['confidence']>=threshold
                row['accepted']=accept
                row['answerability_correct']=accept==row['answerable']
                if not accept:
                    row['gold_evidence_coverage']=0.0 if row['answerable'] else None
                    row['complete_gold_evidence']=False
            metrics=summarize(simulated)
            scores.append({'threshold':threshold,**{key:metrics[key] for key in ('answerability_balanced_accuracy','unsupported_rejection','complete_evidence_rate_all_supported','answerable_acceptance')}})
        selected=max(scores,key=lambda row:(row['answerability_balanced_accuracy'],row['unsupported_rejection'],row['complete_evidence_rate_all_supported'],-row['threshold']))
        thresholds[mode]=selected['threshold']; candidates[mode]={'selected':selected,'candidates':scores}
        print('DEV selected',mode,selected,flush=True)
    write_json(output/'dev_tuning_v2.json',candidates)
    config={'engine_version':getattr(index,'engine_version','2.0'),'thresholds':thresholds,
      'engine_sha256':sha(ROOT/'src/campuscompass/engine.py'),'corpus_sha256':sha(ROOT/'data/policies.jsonl'),
      'inherited_engine_v1_sha256':sha(ROOT/'src/campuscompass/engine_v1.py'),
      'benchmark_sha256':sha(ROOT/'data/evaluation.jsonl'),'audit_sha256':sha(ROOT/'data/v2_audit.jsonl'),
      'calibration':{'split':'dev','n':len(dev),'grid':grid,'objective':'Maximize balanced answerability accuracy; ties: unsupported rejection, complete gold evidence coverage, then lower threshold.',
      'method':'DEV inference once at threshold0; simulate only pass/refusal from minimum facet confidence. Engineer confirmed threshold does not change facets/ranking/source choices; all selected sources are identical whenever all facets pass.',
      'test_policy':'V1 TEST was observed during V1 engineering. Reused TEST is regression only. New audit questions were frozen before V2 results and withheld from implementation engineer; same project team, not externally independent.'},
      'runtime':{'python':sys.version,'platform':platform.platform()}}
    write_json(output/'frozen_config.json',config)

def evaluate(output,modes):
    from campuscompass import PolicyIndex
    config=json.loads((output/'frozen_config.json').read_text(encoding='utf-8'))
    for key,path in [('engine_sha256',ROOT/'src/campuscompass/engine.py'),('inherited_engine_v1_sha256',ROOT/'src/campuscompass/engine_v1.py'),('corpus_sha256',ROOT/'data/policies.jsonl'),('benchmark_sha256',ROOT/'data/evaluation.jsonl'),('audit_sha256',ROOT/'data/v2_audit.jsonl')]:
        if config[key]!=sha(path): raise RuntimeError(f'Frozen {key} changed; do not evaluate a different engine without a new version.')
    audit=audit_questions(output)
    regression=[q for q in read_jsonl(ROOT/'data/evaluation.jsonl') if q['split']=='test']
    index=PolicyIndex(ROOT/'data/policies.jsonl'); index.mode_thresholds.update(config['thresholds'])
    for mode in modes:
        index.retrieve('library borrowing',mode=mode,top_k=3)
        for label,questions in [('regression',regression),('audit',audit)]:
            destination=output/f'v2_{label}_predictions_{mode}.jsonl'; protected(destination)
            rows=collect(index,questions,mode)
            save_rows(destination,rows)
            print('V2',label,mode,json.dumps({k:v for k,v in summarize(rows).items() if k in ('recall_at_3','answerability_accuracy','unsupported_accepts','false_refusals','complete_evidence_rate_all_supported')}),flush=True)

def report(output):
    result={'provenance':{'audit_design':json.loads((output/'audit_freeze.json').read_text(encoding='utf-8')),
      'comparability':'V1 regression predictions reused byte-for-byte as observations, V2 TEST is regression only. New audit baseline and V2 evaluated at frozen mode-specific thresholds. Latencies are sequential warm local observations, not an isolated benchmark; V1 historical regression latency came from the original session.',
      'retrieval':'Raw whole-query top3 retrieval, not facet-expanded response evidence. Multi-policy completeness separately checks all gold IDs cited in accepted response.',
      'source_support':'Sentence membership is a mechanical copy check, not entailment. Gold source completeness is not semantic answer accuracy.'},'runs':{}}
    lines=['# V2 measured comparison','',result['provenance']['comparability'],'',
      '| Set | Version / mode | R@3 | Answerable accepted | Unsupported accepted | Gold evidence complete | Median / p95 ms |',
      '|---|---|---:|---:|---:|---:|---:|']
    for version in ('v1','v2'):
        for label in ('regression','audit'):
            for path in sorted(output.glob(f'{version}_{label}_predictions_*.jsonl')):
                mode=path.stem.split('_predictions_',1)[1]
                rows=read_jsonl(path); summary=summarize(rows)
                summary['categories']={category:summarize([r for r in rows if r['category']==category]) for category in sorted({r['category'] for r in rows})}
                key=f'{version}_{label}_{mode}'; result['runs'][key]=summary
                accepted=summary['answerable_n']-summary['false_refusals']
                complete=sum(r['complete_gold_evidence'] for r in rows if r['answerable'])
                lines.append(f"| {label} | {version} / {mode} | {summary['recall_at_3']:.4f} | {accepted}/{summary['answerable_n']} | {summary['unsupported_accepts']}/{summary['unsupported_n']} | {complete}/{summary['answerable_n']} | {summary['latency_ms_median']:.2f} / {summary['latency_ms_p95']:.2f} |")
    lines.extend(['','The audit contains 40 newly written project-authored questions, including 28 supported and 12 unsupported requests. Its wording was withheld from the implementation engineer until V2 freeze. It is not externally independent, and its author knew V1 failures. The reused TEST set cannot validate generalization after engineering informed by V1 results. No settings may be changed based on audit scores and still be described as evaluated on an untouched audit.','',
      'Gold evidence complete means an accepted response cites every annotated required policy. It does not prove every condition was interpreted correctly. Unsupported acceptance, false refusal, complete evidence and source membership are separate measures. Bootstrap intervals and category diagnostics are in metrics_v2.json.'])
    write_json(output/'metrics_v2.json',result)
    (output/'EVALUATION_V2.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['initialize','baseline','calibrate','evaluate','summarize'],required=True)
    parser.add_argument('--modes',nargs='+',choices=['bm25','tfidf','lexical_hybrid','dense','hybrid'],default=['bm25','tfidf','lexical_hybrid','dense','hybrid'])
    parser.add_argument('--output',type=Path,default=ROOT/'results/v2')
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    if args.stage=='initialize':
        initialize(args.output)
        return
    check_v1_manifest(args.output)
    {'baseline':baseline,'calibrate':calibrate,'evaluate':evaluate,'summarize':lambda out,modes:report(out)}[args.stage](args.output,args.modes)
    check_v1_manifest(args.output)

if __name__=='__main__': main()
