"""Checks evaluator math and benchmark integrity, without downloading models."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('project_evaluate',ROOT/'scripts/evaluate.py')
evaluation=importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)

class EvaluationTests(unittest.TestCase):
    def test_multi_policy_recall_is_not_any_hit(self):
        score=evaluation.retrieval_scores(['A','B'],['A','C','D'])
        self.assertEqual(score['recall_at_3'],.5)
        self.assertEqual(score['hit_at_3'],1)
        self.assertEqual(score['complete_at_3'],0)
        self.assertEqual(score['mrr_at_3'],1)

    def test_reciprocal_rank_and_no_gold(self):
        self.assertEqual(evaluation.retrieval_scores(['B'],['A','B','C'])['mrr_at_3'],.5)
        self.assertEqual(evaluation.retrieval_scores([],['A']),{})

    def test_verbatim_check_rejects_fabrication(self):
        docs={'P01':{'text':'Students may borrow books. Returns are due Friday.'}}
        self.assertTrue(evaluation.verbatim_support('Returns are due Friday. [P01]',[{'id':'P01'}],docs))
        self.assertFalse(evaluation.verbatim_support('Returns are due Monday. [P01]',[{'id':'P01'}],docs))
        self.assertFalse(evaluation.verbatim_support('Returns are due Friday. [P99]',[{'id':'P99'}],docs))

    def test_bootstrap_deterministic(self):
        rows=[{'x':x} for x in [0,1,.5,1]]
        self.assertEqual(evaluation.bootstrap(rows,'x',100),evaluation.bootstrap(rows,'x',100))

    def test_nearest_rank_percentiles_include_small_sample_tail(self):
        self.assertEqual(evaluation.nearest_rank_percentile([1,9],.95),9)
        self.assertEqual(evaluation.nearest_rank_percentile([4],.95),4)
        self.assertEqual(evaluation.nearest_rank_percentile(list(range(1,70)),.95),66)
        self.assertIsNone(evaluation.nearest_rank_percentile([],.95))
        with self.assertRaises(ValueError):
            evaluation.nearest_rank_percentile([1],1.01)

    def test_threshold_tunes_only_given_development_rows(self):
        class Index:
            abstention_threshold=.22
        dev=[{'id':'DEV_ONLY'}]
        rows=[{'answerable':True,'prediction':{'status':'answered','confidence':.8}},
              {'answerable':False,'prediction':{'status':'answered','confidence':.5}}]
        index=Index()
        with patch.object(evaluation,'collect',return_value=rows) as collect:
            selected,candidates=evaluation.tune(index,dev,'bm25')
        collect.assert_called_once_with(index,dev,'bm25')
        self.assertEqual(selected['threshold'],.55)
        self.assertEqual(selected['balanced_accuracy'],1)
        self.assertEqual(len(candidates),18)

    def test_benchmark_contract(self):
        docs=evaluation.read_jsonl(ROOT/'data/policies.jsonl')
        queries=evaluation.read_jsonl(ROOT/'data/evaluation.jsonl')
        ids={d['id'] for d in docs}
        self.assertEqual(len(docs),30)
        self.assertEqual(len(ids),30)
        self.assertEqual(len(queries),106)
        self.assertEqual(sum(q['split']=='dev' for q in queries),37)
        self.assertEqual(sum(q['split']=='test' for q in queries),69)
        self.assertEqual(len({q['query'] for q in queries}),len(queries))
        for q in queries:
            self.assertEqual(q['answerable'],bool(q['relevant_ids']))
            self.assertTrue(set(q['relevant_ids'])<=ids)
            self.assertIn(q['split'],('dev','test'))
        self.assertTrue(any(len(q['relevant_ids'])>1 for q in queries))
        self.assertTrue(any(q['category']=='adversarial' for q in queries))

if __name__=='__main__': unittest.main()
