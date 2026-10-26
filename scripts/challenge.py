"""Exploratory challenge suite authored after the initial frozen TEST evaluation.

These diagnostics are not an independent test and must not tune configuration.
The quoted-document injection is simulated in query text, not a poisoned index.
"""
import argparse
import hashlib
import json
from pathlib import Path
from evaluate import ROOT, PolicyIndex, read_jsonl, collect, summarize

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modes',nargs='+',default=['bm25','hybrid'])
    parser.add_argument('--output',type=Path,default=ROOT/'results/challenge')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    if (args.output/'metrics.json').exists(): parser.error('Use a fresh --output to preserve prior evidence.')
    questions=read_jsonl(ROOT/'data/challenge.jsonl')
    result={'provenance':{'design':'18 exploratory diagnostic prompts authored AFTER inspecting original TEST failures. No tuning; frozen thresholds loaded. Not independent confirmation.','simulated_indirect':'Malicious instructions are quoted in the query, not injected into a retrieval document.','corpus_sha256':hashlib.sha256((ROOT/'data/policies.jsonl').read_bytes()).hexdigest(),'challenge_sha256':hashlib.sha256((ROOT/'data/challenge.jsonl').read_bytes()).hexdigest()},'modes':{}}
    index=PolicyIndex(ROOT/'data/policies.jsonl')
    for mode in args.modes:
        run='neural' if mode in ('dense','hybrid') else 'lexical'
        configuration=json.loads((ROOT/f'results/{run}/frozen_config.json').read_text(encoding='utf-8'))
        index.abstention_threshold=configuration['thresholds'][mode]
        index.retrieve('course withdrawal',mode=mode,top_k=3)
        rows=collect(index,questions,mode)
        metrics=summarize(rows)
        metrics['threshold']=index.abstention_threshold
        metrics['categories']={cat:summarize([r for r in rows if r['category']==cat]) for cat in sorted({r['category'] for r in rows})}
        result['modes'][mode]=metrics
        (args.output/f'predictions_{mode}.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
        print(mode,json.dumps({key:metrics[key] for key in ('answerability_accuracy','false_accepts','false_abstentions','recall_at_3')}))
    (args.output/'metrics.json').write_text(json.dumps(result,indent=2),encoding='utf-8')

if __name__=='__main__': main()
