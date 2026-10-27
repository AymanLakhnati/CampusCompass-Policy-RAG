"""V2 evaluator math and evidence preservation, without neural model loading."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('evaluation_v2',ROOT/'scripts/evaluate_v2.py')
evaluation=importlib.util.module_from_spec(spec); spec.loader.exec_module(evaluation)

class V2EvaluationTests(unittest.TestCase):
    def make_row(self,answerable=True,cited=('P01',),gold=('P01','P02'),confidence=.8):
        docs={'P01':{'text':'First rule. Retain this exception.'},'P02':{'text':'Second rule.'}}
        prediction={'status':'answered','answer':' '.join(docs[pid]['text']+' ['+pid+']' for pid in cited),
                    'citations':[{'id':pid} for pid in cited],'confidence':confidence}
        example={'id':'X','split':'dev','query':'A question','relevant_ids':list(gold) if answerable else [],'answerable':answerable,'category':'fixture','expected_terms':[]}
        return evaluation.build_row(example,prediction,['P01','P02','P03'],docs,'bm25',1.0)

    def test_complete_multi_source_is_not_any_hit(self):
        partial=self.make_row()
        complete=self.make_row(cited=('P01','P02'))
        self.assertEqual(partial['gold_evidence_coverage'],.5)
        self.assertFalse(partial['complete_gold_evidence'])
        self.assertTrue(complete['complete_gold_evidence'])
        self.assertTrue(complete['verbatim_supported'])

    def test_authentic_copy_can_be_unsupported_acceptance(self):
        row=self.make_row(answerable=False)
        summary=evaluation.summarize([row])
        self.assertTrue(row['verbatim_supported'])
        self.assertEqual(summary['unsupported_accepts'],1)
        self.assertEqual(summary['answerability_accuracy'],0)
        self.assertIn('Not measured',summary['semantic_answer_accuracy'])

    def test_calibration_reads_only_dev_and_preserves_objective(self):
        import campuscompass
        class FakeIndex:
            mode_thresholds={}
            abstention_threshold=.35
            def __init__(self,*args): self.mode_thresholds={}
            def retrieve(self,*args,**kwargs): return []
        rows=[self.make_row(cited=('P01','P02'),confidence=.55),
              self.make_row(answerable=False,confidence=.30)]
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(campuscompass,'PolicyIndex',FakeIndex),patch.object(evaluation,'collect',return_value=rows) as collect:
                evaluation.calibrate(Path(tmp),['bm25'])
            examples=collect.call_args.args[1]
            self.assertEqual(len(examples),37)
            self.assertTrue(all(q['split']=='dev' for q in examples))
            saved=json.loads((Path(tmp)/'frozen_config.json').read_text())
            self.assertEqual(saved['thresholds']['bm25'],.325)
            self.assertEqual(saved['audit_sha256'],evaluation.sha(ROOT/'data/v2_audit.jsonl'))

    def test_frozen_v1_evidence_and_audit_contract(self):
        output=ROOT/'results/v2'
        self.assertGreaterEqual(evaluation.check_v1_manifest(output),27)
        questions=evaluation.audit_questions(output)
        self.assertEqual(len(questions),40)
        self.assertEqual(sum(q['answerable'] for q in questions),28)
        self.assertEqual(len({q['id'] for q in questions}),40)

    def test_existing_output_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'recorded.json'; path.write_text('original')
            with self.assertRaises(RuntimeError): evaluation.protected(path)
            self.assertEqual(path.read_text(),'original')

    def test_fresh_reproduction_initialization_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            evaluation.initialize(directory)
            self.assertTrue((directory/'audit_freeze.json').exists())
            self.assertTrue((directory/'reference_code/engine_v1.py').exists())
            with self.assertRaises(RuntimeError): evaluation.initialize(directory)
            self.assertEqual(len(evaluation.audit_questions(directory)),40)

if __name__=='__main__': unittest.main()
