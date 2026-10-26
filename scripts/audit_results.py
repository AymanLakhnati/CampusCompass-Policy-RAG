"""Verify saved evidence consistency without TEST inference or model loading."""
import hashlib
import json
import math
import re
import statistics
from evaluate import ROOT, read_jsonl, summarize

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    corpus=ROOT/'data/policies.jsonl'
    benchmark=ROOT/'data/evaluation.jsonl'
    docs={d['id']:d for d in read_jsonl(corpus)}
    questions={q['id']:q for q in read_jsonl(benchmark)}
    checks=[]; preserved={}
    for folder in ('lexical','neural','challenge'):
        directory=ROOT/f'results/{folder}'
        saved=json.loads((directory/'metrics.json').read_text(encoding='utf-8'))
        if folder!='challenge':
            frozen=json.loads((directory/'frozen_config.json').read_text(encoding='utf-8'))
            assert frozen['provenance']['corpus_sha256']==sha(corpus)
            assert frozen['provenance']['benchmark_sha256']==sha(benchmark)
        for mode,metrics in saved['modes'].items():
            path=directory/f'{"predictions" if folder=="challenge" else "test_predictions"}_{mode}.jsonl'
            rows=read_jsonl(path)
            preserved[str(path.relative_to(ROOT))]=sha(path)
            actual=summarize(rows)
            for key,value in actual.items():
                assert value==metrics[key],(folder,mode,key,value,metrics[key])
            for category in metrics['categories'].values():
                assert category['latency_ms_p95']>=category['latency_ms_median']
            if folder!='challenge':
                assert len(rows)==69 and all(r['split']=='test' for r in rows)
                assert metrics['threshold']==frozen['thresholds'][mode]
            checks.append(f'{folder}/{mode}: all summary values recompute exactly; P95 monotonic; predictions hashed')
    normalize=lambda s: re.sub(r'\s+',' ',s.casefold()).strip(' .!?:;"')
    for name in ('llm_experiment.json','qwen_experiment.json'):
        path=ROOT/'results'/name
        if not path.exists(): continue
        obj=json.loads(path.read_text(encoding='utf-8'))
        outputs=obj['outputs']; accepted=[r for r in outputs if r['response']['status']=='answered']
        attempts=[r for r in outputs if r['response'].get('generation_attempted')]
        assert len(outputs)==obj['n']==69
        assert len(attempts)==obj['generation_attempts']
        assert len(accepted)==obj['accepted_answers']
        assert obj['corpus_sha256']==sha(corpus)
        assert obj['abstention_threshold']==.35 and obj['retrieval_mode']=='bm25'
        assert len(accepted)/len(outputs)==obj['answer_coverage']
        assert statistics.mean(r['response']['generation_ms'] for r in attempts)==obj['mean_generation_ms']
        cited=sum(any(c['id'] in r['relevant_ids'] for c in r['response']['citations']) for r in accepted)
        assert cited==obj['correct_cited_policy_among_accepted']
        for row in outputs:
            q=questions[row['id']]
            assert q['split']=='test' and q['relevant_ids']==row['relevant_ids'] and q['answerable']==row['expected_answerable']
        for row in accepted:
            response=row['response']; raw=response['raw_model_output']
            assert response['generation_supported'] and len(raw.split())>=2
            assert any(normalize(raw) in normalize(docs[c['id']]['text']) for c in response['citations'])
        preserved[str(path.relative_to(ROOT))]=sha(path)
        checks.append(f'{name}: {len(outputs)} original TEST IDs, {len(attempts)} generation attempts, {len(accepted)} accepted, {cited} gold-policy citations; all counts/timing means/exact-source gates recompute')
    result={'method':'Read-only recomputation of saved predictions; no retrieval or generation inference.',
      'p95_convention':'Empirical nearest rank ceil(.95*n)-1, zero-based; original floor quantile corrected without reinference.',
      'checks':checks,'preserved_prediction_sha256':preserved,'corpus_sha256':sha(corpus),'benchmark_sha256':sha(benchmark)}
    output=ROOT/'results/audit_checks.json'
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'passed':len(checks),'checks':checks},indent=2))

if __name__=='__main__': main()
