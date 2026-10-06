import unittest
from unittest.mock import patch
from comparison_evaluator import evaluate_comparison
from variant_gate import canonical, sha


class EvaluatorTests(unittest.TestCase):
    def test_retained_comparison_scores_without_resolution(self):
        labels = [{'query_id':'q','product_id':'p','grade':3}]
        payload = b''.join(canonical(row) for row in labels)
        item = {'name':'extra','judgement_bytes':payload,'judgements_rows':labels,
                'resolved_references':{'judgements':{'sha256':sha(payload)}}}
        standard = {'metrics':{'baseline':{'nDCG@10':.9}}}
        with patch('comparison_evaluator.evaluate', return_value=standard), \
             patch('comparison_evaluator.score_extra', return_value={'metrics':{'baseline':{'nDCG@10':.8}}}), \
             patch('comparison_evaluator.assemble', side_effect=lambda base,*args:base), \
             patch('comparison_evaluator.resolve_extra') as resolve:
            one, frozen = evaluate_comparison({}, {'extra':{}}, [item], {}, b'{}', [], {}, None, resolve_missing=False)
            two, _ = evaluate_comparison({}, {'extra':{}}, frozen, {}, b'{}', [], {}, None, resolve_missing=False)
            self.assertEqual(one['metrics'], two['metrics'])
            resolve.assert_not_called()
            changed = {**item, 'judgement_bytes':b'changed'}
            with self.assertRaisesRegex(ValueError, 'unchanged retained'):
                evaluate_comparison({}, {'extra':{}}, [changed], {}, b'{}', [], {}, None, resolve_missing=False)

    def test_new_comparison_resolves_once_per_suite_before_scoring_all_variants(self):
        item = {'name':'extra'}
        order = []
        with patch('comparison_evaluator.evaluate', return_value={}), \
             patch('comparison_evaluator.resolve_extra', side_effect=lambda *args: (order.append('resolve') or item)), \
             patch('comparison_evaluator.score_extra', side_effect=lambda *args: (order.append('score') or {})), \
             patch('comparison_evaluator.assemble', return_value={}):
            evaluate_comparison({}, {'extra':{}}, [item], {}, b'{}', [], {}, None)
        self.assertEqual(order, ['resolve','score'])


if __name__ == '__main__':unittest.main()
