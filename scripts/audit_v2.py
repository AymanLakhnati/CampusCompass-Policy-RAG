"""Read-only V2 evidence audit: no model loading, retrieval, or generation.

Writes only a separate audit receipt. Existing frozen predictions remain unchanged.
"""
import argparse
import json
from pathlib import Path
from evaluate_v2 import ROOT, sha, read_jsonl, build_row, summarize, check_v1_manifest, audit_questions, write_json

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'results/v2',help='Results directory to check, not a prediction destination.')
    args=parser.parse_args(); output=args.output
    preserved=check_v1_manifest(output); questions=audit_questions(output)
    config=json.loads((output/'frozen_config.json').read_text(encoding='utf-8'))
    assert config['engine_sha256']==sha(ROOT/'src/campuscompass/engine.py')
    assert config['inherited_engine_v1_sha256']==sha(ROOT/'src/campuscompass/engine_v1.py')
    assert config['corpus_sha256']==sha(ROOT/'data/policies.jsonl')
    assert config['benchmark_sha256']==sha(ROOT/'data/evaluation.jsonl')
    assert config['audit_sha256']==sha(ROOT/'data/v2_audit.jsonl')
    docs={d['id']:d for d in read_jsonl(ROOT/'data/policies.jsonl')}
    original={q['id']:q for q in read_jsonl(ROOT/'data/evaluation.jsonl')}
    audit={q['id']:q for q in questions}
    tuning=json.loads((output/'dev_tuning_v2.json').read_text(encoding='utf-8'))
    for mode,item in tuning.items():
        selected=max(item['candidates'],key=lambda r:(r['answerability_balanced_accuracy'],r['unsupported_rejection'],r['complete_evidence_rate_all_supported'],-r['threshold']))
        assert selected==item['selected'] and selected['threshold']==config['thresholds'][mode]
        dev=read_jsonl(output/f'dev_zero_threshold_predictions_{mode}.jsonl')
        assert len(dev)==37 and all(r['split']=='dev' for r in dev)
    recorded=json.loads((output/'metrics_v2.json').read_text(encoding='utf-8'))
    checks=[]; hashes={}
    for path in sorted(output.glob('*_predictions_*.jsonl')):
        version,label=path.stem.split('_',2)[:2]
        if version not in ('v1','v2') or label not in ('audit','regression'): continue
        mode=path.stem.split('_predictions_',1)[1]
        rows=read_jsonl(path)
        assert len(rows)==(40 if label=='audit' else 69)
        expected=audit if label=='audit' else original
        assert len({r['id'] for r in rows})==len(rows)
        for row in rows:
            gold=expected[row['id']]
            assert row['query']==gold['query'] and row['relevant_ids']==gold['relevant_ids'] and row['answerable']==gold['answerable']
            prediction=row['prediction']; citations={c['id'] for c in prediction['citations']}
            rebuilt=build_row(gold,prediction,row['raw_query_retrieved'],docs,mode,row['wall_latency_ms'],row.get('retrieval_latency_ms'))
            for field in ('accepted','answerability_correct','gold_evidence_coverage','relevant_citation_precision','complete_gold_evidence','verbatim_supported'):
                assert row[field]==rebuilt[field],(path.name,row['id'],field)
            assert row['accepted']==(prediction['status']=='answered')
            assert row['complete_gold_evidence']==bool(row['answerable'] and row['accepted'] and set(gold['relevant_ids'])<=citations)
            if row['accepted']:
                assert citations and citations<=set(docs)
                assert all('['+pid+']' in prediction['answer'] for pid in citations)
            if version=='v2':
                assert prediction['threshold']==config['thresholds'][mode]
                for evidence in prediction['evidence']:
                    assert evidence['id'] in docs
                    assert all(excerpt in docs[evidence['id']]['text'] for excerpt in evidence['excerpts'])
        computed=summarize(rows); saved=recorded['runs'][f'{version}_{label}_{mode}']
        for key,value in computed.items(): assert saved[key]==value,(path.name,key)
        assert computed['latency_ms_p95']>=computed['latency_ms_median']
        hashes[path.name]=sha(path); checks.append(path.name+': labels, counts, citations, source excerpts, thresholds and all summary values verified')
    for path in sorted(output.glob('llm_audit_*.json')):
        obj=json.loads(path.read_text(encoding='utf-8'))
        provenance=obj['provenance']; assert provenance['engine_sha256']==config['engine_sha256']
        assert provenance['llm_sha256']==sha(ROOT/'src/campuscompass/llm.py')
        rows=read_jsonl(path.with_suffix('.jsonl'))
        assert len(rows)==40 and {r['id'] for r in rows}==set(audit)
        assert obj['generation_attempts']==sum(bool(r['prediction'].get('generation_attempted')) for r in rows)
        assert obj['generation_source_candidates']==sum(len(r['prediction'].get('generation_evidence',[])) for r in rows)
        computed=summarize(rows)
        for key,value in computed.items(): assert obj['metrics'][key]==value,(path.name,key)
        for row in rows:
            assert row['query']==audit[row['id']]['query']
            prediction=row['prediction']
            if prediction['status']=='answered':
                assert prediction['generation_supported'] and prediction['generation_attempted']
                evidence=prediction['generation_evidence']
                assert {g['source_id'] for g in evidence}=={c['id'] for c in prediction['citations']}
                assert all(g['source_supported'] and g['source_excerpt'] in docs[g['source_id']]['text'] for g in evidence)
        hashes[path.with_suffix('.jsonl').name]=sha(path.with_suffix('.jsonl'))
        checks.append(path.name+': full40 model outputs, attempt/candidate/acceptance counts and per-source canonical membership verified')
    receipt={'method':'Read-only evidence recomputation; no model inference. Same project internal audit, not external certification.',
      'v1_files_preserved':preserved,'engine_sha256':config['engine_sha256'],'audit_sha256':config['audit_sha256'],
      'checks':checks,'prediction_sha256':hashes,'limits':'Gold source IDs, citation completeness and exact source membership are not semantic answer correctness. Audit was withheld from engineer until source freeze but authored by project evaluation agent familiar with V1.'}
    write_json(output/'audit_receipt_v2.json',receipt)
    print(json.dumps({'v1_files_preserved':preserved,'passed_groups':len(checks),'checks':checks},indent=2))

if __name__=='__main__': main()
