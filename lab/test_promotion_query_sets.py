"""Promotion cannot replace its standard suite or omit source-declared checks."""
from copy import deepcopy
from contextlib import ExitStack
import json
import unittest
from unittest.mock import patch

import promotion_query_sets as suites
from query_sets import canonical, freeze, sha
from delivery_gates import evaluate_variants, EvidenceFailure


class PromotionQuerySets(unittest.TestCase):
    def setUp(self):
        self.baseline = {'fingerprint': 'old', 'build_run': 1,
                         'fields': {'image': 'old-image', 'dataset_release': 'esci-gb-v1', 'dataset_sha256': 'a'*64}}
        self.candidate = {'fingerprint': 'new', 'build_run': 2,
                          'fields': {**self.baseline['fields'], 'image': 'new-image'}}
        self.inputs = {'query_manifest_sha256': suites.DEFAULTS['esci-gb-v1']['query-suite'],
                       'judgement_manifest_sha256': suites.DEFAULTS['esci-gb-v1']['judgement-set']}
        self.runtime = {side: {'variant': 'default' if side=='baseline' else 'ranker-a',
                              'configuration_sha256': side+'-config'} for side in ('baseline','candidate')}
        self.selected = {'source_sha': 'c'*40, 'additional_query_sets': [
            {'name': 'seasonal', 'path': 'evaluation/queries/seasonal.jsonl',
             'required': True, 'judgements': 'evaluation/judgements/seasonal.jsonl'},
            {'name': 'exploration', 'path': 'evaluation/queries/exploration.jsonl', 'required': False}]}
        query = {'query_id':'q','query':'shoes','country':'GB','currency':'GBP','filters':{}}
        self.payloads = {item['path']: canonical(query) for item in self.selected['additional_query_sets']}
        self.payloads['evaluation/judgements/seasonal.jsonl'] = canonical({'query_id':'q','product_id':'p','grade':3})
        self.frozen = freeze(self.selected,self.payloads.__getitem__)
        self.standard = {'complete':True,'query_count':1,'changed_query_ids':[],
            'queries':[{'query_id':'q','baseline':{'ndcg_at_10':1},'candidate':{'ndcg_at_10':1}}],
            'metrics': {v:{'nDCG@10':1,'RR@10':1} for v in self.runtime},
            'baseline':{'dataset_sha256':'a'*64}, 'suite_sha256':'d'*64,
            'judgement_coverage':{v:{'fraction':1,'judged':1,'returned':1} for v in self.runtime},
            'result_similarity':{'rbo_at_10_p_0_9':1,'jaccard_at_10':1}}
        self.parent = {'selected_inputs':self.inputs,'reports':{'relevance':{'blob':'standard'}},
            'previews':['lab-old','lab-new'], 'variant_runtime':self.runtime,
            'completed_at':'2026-10-15T00:00:00+00:00'}
        self.store = {'parent': self.parent,'standard':self.standard}
        self.counter=0

    def read(self,ref):
        return deepcopy(self.store[ref['blob']])

    def retain(self,value,name):
        self.counter+=1; key=str(self.counter)
        self.store[key]=deepcopy(value)
        return {'blob':key,'sha256':key}

    def extra_report(self):
        return {'complete': True, 'relevance_available':True, 'judgement_selection':'gate',
            'unqualified_judgements':0, 'variants':suites.pins(self.baseline,self.candidate,self.runtime),
            'baseline_variant':'baseline','query_count':1,
            'metrics':{v:{'nDCG@10':1,'nDCG@5':1} for v in self.runtime},
            'coverage':deepcopy(self.standard['judgement_coverage']),
            'result_changes':{v:{'changed_queries':0} for v in self.runtime},
            'result_similarity':{v:{'rbo_at_10_p_0_9':1,'jaccard_at_10':1} for v in self.runtime},
            'catalogue_sha256':'a'*64, 'query_suite_sha256':self.frozen[0]['query_sha256']}

    def mocks(self,stack):
        stack.enter_context(patch('delivery_gates.read',side_effect=self.read))
        stack.enter_context(patch('delivery_gates.retain',side_effect=self.retain))
        stack.enter_context(patch('input_selection.select',return_value={'queries':[json.loads(self.frozen[0]['query_bytes'])],
            'judgements':[{'query_id':'q','product_id':'p','grade':3}], 'catalogue':{'content':{'sha256':'a'*64}}}))
        stack.enter_context(patch('compare_search.definition',side_effect=lambda env:{'fingerprint':'old' if env=='lab-old' else 'new'}))
        captures=stack.enter_context(patch('evaluation_job.run_variants',return_value=([
            {'query_id':'q','results':{v:{'ids':['p'],'total':1,'variant_id':v} for v in self.runtime}}],{'seconds':1})))
        stack.enter_context(patch('additional_judgements.resolve_extra',side_effect=lambda item,*args:{**item,
            'resolved_references':{'judgements':{'blob':'labels'},'resolution':{'blob':'resolution'}}}))
        stack.enter_context(patch('delivery_source_comparison.retain_input',return_value={'blob':'input'}))
        stack.enter_context(patch('promotion_query_sets.score_extra',side_effect=lambda item,*args:self.extra_report()))
        return captures

    def evaluate(self):
        return suites.evaluate({'blob':'parent'},self.baseline,self.candidate,self.selected,self.frozen,'ranking-change')

    def validate(self,ref):
        suites.validate(ref,self.baseline,self.candidate,self.selected,self.frozen,'ranking-change')

    def test_standard_cannot_be_replaced(self):
        suites.standard_inputs(self.candidate,self.inputs)
        with self.assertRaisesRegex(ValueError,'frozen standard'):
            suites.standard_inputs(self.candidate,{**self.inputs,'query_manifest_sha256':'0'*64})
        for extra in ([],[{'name':'standard','path':'evaluation/queries/other.jsonl'}]):
            if extra:
                with self.assertRaises(ValueError): freeze({'additional_query_sets':extra},self.payloads.__getitem__)

    def test_frozen_source_bytes_are_loaded_at_exact_commit(self):
        with patch('delivery_source_comparison.source_bytes',side_effect=lambda path,rev:self.payloads[path]) as source:
            items=suites.frozen_sets(self.selected)
        self.assertEqual(items,self.frozen)
        self.assertTrue(all(call.args[1]==self.selected['source_sha'] for call in source.call_args_list))

    def test_required_thresholds_and_report_only_failure(self):
        report=self.extra_report()
        self.assertEqual(suites.outcome(report,True,'ranking-change')['state'],'pass')
        report['metrics']['candidate']['nDCG@10']=.99
        self.assertEqual(suites.outcome(report,True,'ranking-change')['state'],'decision_required')
        report['metrics']['candidate']['nDCG@10']=.9
        self.assertEqual(suites.outcome(report,True,'ranking-change')['state'],'blocked')
        report['metrics']['candidate']['nDCG@10']=float('nan')
        self.assertEqual(suites.outcome(report,True,'ranking-change')['state'],'blocked')
        for update in ({'complete':False},{'relevance_available':False},{'unqualified_judgements':1}):
            self.assertEqual(suites.outcome({**self.extra_report(),**update},True,'ranking-change')['state'],'blocked')
        self.assertEqual(suites.outcome({'complete':False},False,'ranking-change'),
                         {'state':'report_only','required':False,'available':False,'used_for_gate':False})

    def test_capture_once_per_extra_and_validate_retained_contract(self):
        with ExitStack() as stack:
            captures=self.mocks(stack)
            ref=self.evaluate();self.validate(ref)
            self.assertEqual(captures.call_count,2)
            parent=self.read(ref);summary=self.read(parent['query_sets_report'])
            self.assertEqual(set(summary['query_sets']),{'standard','seasonal','exploration'})
            self.assertEqual(summary['gate_outcomes']['standard']['state'],'pass')
            self.assertEqual(summary['gate_outcomes']['seasonal']['state'],'pass')
            self.assertEqual(summary['gate_outcomes']['exploration']['state'],'report_only')
            self.assertFalse(summary['combined']['used_for_gate'])
            self.assertEqual(summary['combined']['query_count'],3)
            self.assertEqual(summary['combined']['repeated_request_count'],2)
            self.assertEqual(summary['combined']['metrics']['candidate'],{'nDCG@10':1})
            for change in ('missing','optional','standard','pin','bytes','outcome'):
                altered=deepcopy(summary)
                if change=='missing': del altered['query_sets']['seasonal']
                elif change=='optional': altered['query_set_metadata']['seasonal']['required']=False
                elif change=='standard': altered['query_sets']['standard']['metrics']['candidate']['nDCG@10']=.8
                elif change=='pin': altered['query_sets']['seasonal']['variants']['candidate']['image']='other'
                elif change=='bytes': altered['query_set_metadata']['seasonal']['query_sha256']='other'
                else: altered['gate_outcomes']['seasonal']['state']='report_only'
                self.store[parent['query_sets_report']['blob']]=altered
                with self.subTest(change=change),self.assertRaises(ValueError): self.validate(ref)
            self.store[parent['query_sets_report']['blob']]=summary
            self.validate(ref)
            with self.assertRaisesRegex(ValueError,'missing'): self.validate({'blob':'parent'})

    def test_report_only_capture_failure_is_retained_and_informational(self):
        with ExitStack() as stack:
            captures=self.mocks(stack)
            captures.side_effect=[captures.return_value,RuntimeError('offline')]
            ref=self.evaluate();self.validate(ref)
            value=self.read(self.read(ref)['query_sets_report'])
            self.assertEqual(value['state'],'pass')
            self.assertFalse(value['gate_outcomes']['exploration']['available'])
            self.assertFalse(value['combined']['available'])

    def test_required_failure_is_not_hidden_by_combined_scores(self):
        with ExitStack() as stack:
            captures=self.mocks(stack);captures.side_effect=RuntimeError('offline')
            ref=self.evaluate()
            value=self.read(self.read(ref)['query_sets_report'])
            self.assertEqual(value['state'],'failed')
            value['state']='pass';value['combined']={'available':True,'metrics':{'candidate':{'nDCG@10':1}}}
            self.store[self.read(ref)['query_sets_report']['blob']]=value
            with self.assertRaisesRegex(ValueError,'Required query set seasonal'):self.validate(ref)

    def test_variant_orchestrator_keeps_standard_and_runs_extras_for_each_variant(self):
        from delivery_variant_selection import canonical as config_bytes
        selection = {**self.selected, 'selection': [{'variant':'ranker-a','intent':'ranking-change'},
            {'variant':'ranker-b','intent':'preserve-results'}],
            'configuration':{'default_variant':'ranker-a','variants':{'ranker-a':{},'ranker-b':{}}},
            'selection_sha256':'selection','evaluation_sha256':'layout','configuration_sha256':'config',
            'configuration_sha256_by_variant':{'ranker-a':'candidate-config','ranker-b':'candidate-config'}}
        self.candidate['fields'].update(source_sha=selection['source_sha'],
            variant_config_json=config_bytes(selection['configuration']).decode())
        baseline_pin={'variant':'default','settings':{},'configuration_sha256':'baseline-config',
            'build_run':1,'deployment_fingerprint':'old'}
        with ExitStack() as stack:
            self.mocks(stack)
            stack.enter_context(patch('delivery_variant_selection.source_selection',return_value=selection))
            stack.enter_context(patch('delivery_variant_selection.configured_baseline',return_value=baseline_pin))
            stack.enter_context(patch('delivery_variant_selection.with_variant',side_effect=lambda dep,*args:dep))
            stack.enter_context(patch('delivery_gates.deployment_inputs',return_value=self.inputs))
            standard=stack.enter_context(patch('delivery_gates.evaluate',return_value={'blob':'parent','sha256':'parent'}))
            stack.enter_context(patch('delivery_gates.validate_evidence'))
            stack.enter_context(patch('delivery_gates.validate_variant_evidence'))
            stack.enter_context(patch('promotion_query_sets.frozen_sets',return_value=self.frozen))
            extras=stack.enter_context(patch('promotion_query_sets.evaluate',return_value={'blob':'extra-parent','sha256':'extra-parent'}))
            stack.enter_context(patch('promotion_query_sets.validate'))
            self.store['extra-parent']={**self.parent,'query_sets_report':{'blob':'summary','sha256':'summary'}}
            self.store['summary']={'gate_outcomes':{'standard':{'state':'pass','required':True}}}
            # Each standard probe still executes; an extra-set failure blocks the variant even after it passes.
            extras.side_effect=ValueError('Required query set seasonal has outcome blocked.')
            with self.assertRaises(EvidenceFailure) as failed:
                evaluate_variants(self.baseline,self.candidate)
            root=self.read(failed.exception.reference)
            self.assertIn('seasonal',str(failed.exception))
            self.assertEqual(standard.call_count,2)
            self.assertEqual(extras.call_count,2)
            self.assertEqual(root['state'],'failed')
            self.assertEqual([c['state'] for c in root['checks']],['failed','failed'])
            self.assertTrue(all('seasonal' in c['error'] for c in root['checks']))
            standard.reset_mock()
            stack.enter_context(patch('delivery_gates.deployment_inputs',return_value={**self.inputs,'query_manifest_sha256':'other'}))
            with self.assertRaisesRegex(ValueError,'frozen standard'): evaluate_variants(self.baseline,self.candidate)
            standard.assert_not_called()

    def test_real_scorer_accepts_captured_pins_and_supplied_reference_labels(self):
        self.baseline['fingerprint']='1'*64;self.candidate['fingerprint']='2'*64
        for side,dep in (('baseline',self.baseline),('candidate',self.candidate)):
            dep['fields']['image']='registry/search@sha256:'+'3'*64
            self.runtime[side]['configuration_sha256']='4'*64
        with ExitStack() as stack:
            captures=self.mocks(stack)
            captures.return_value=([{'query_id':'q','results':{v:{'ids':['p'],'total':1,
                'variant_id':v,'configuration_sha256':'4'*64} for v in self.runtime}}],{'seconds':1})
            stack.enter_context(patch('compare_search.definition',side_effect=lambda env:{'fingerprint':('1' if env=='lab-old' else '2')*64}))
            from query_sets import score_extra
            stack.enter_context(patch('promotion_query_sets.score_extra',side_effect=score_extra))
            stack.enter_context(patch('additional_judgements.resolve_extra',side_effect=lambda item,*args:{**item,
                'judgement_selection':'gate' if item['required'] else 'exploratory',
                'resolved_references':{'judgements':{'blob':'labels'},'resolution':{'blob':'resolution'}}}))
            ref=self.evaluate();self.validate(ref)
            value=self.read(self.read(ref)['query_sets_report'])
            self.assertEqual(value['gate_outcomes']['seasonal']['state'],'pass')
            self.assertEqual(value['query_sets']['seasonal']['metrics']['candidate']['nDCG@10'],1)
            self.assertFalse(value['query_sets']['exploration']['relevance_available'])

    def test_multiple_standard_sets_with_no_additional_sets(self):
        self.selected['additional_query_sets']=[]
        item=self.frozen[0]
        item.update(name='primary-seasonal',group='mandatory',
            path='evaluation/mandatory/primary-seasonal.jsonl',judgements='evaluation/mandatory/primary-seasonal-judgements.jsonl',
            query_manifest_sha256='a'*64,judgement_manifest_sha256='b'*64)
        self.frozen=[item]
        group=[{'name':'standard','query_manifest_sha256':self.inputs['query_manifest_sha256'],
            'judgement_manifest_sha256':'b'*64},{'name':'primary-seasonal','query_manifest_sha256':'a'*64,'judgement_manifest_sha256':'b'*64}]
        with ExitStack() as stack:
            self.mocks(stack)
            stack.enter_context(patch('primary_query_sets.configuration',return_value=group))
            resolver=stack.enter_context(patch('additional_judgements.resolve_extra'))
            ref=self.evaluate();self.validate(ref)
            resolver.assert_not_called()
            value=self.read(self.read(ref)['query_sets_report'])
            self.assertEqual(set(value['query_sets']),{'standard','primary-seasonal'})
            self.assertEqual(value['primary_query_sets'],group)
            self.assertTrue(all(v['required'] for v in value['gate_outcomes'].values()))
            altered=self.read(self.read(ref)['query_sets_report']);altered['primary_query_sets'].pop()
            self.store[self.read(ref)['query_sets_report']['blob']]=altered
            with self.assertRaisesRegex(ValueError,'mandatory query sets'): self.validate(ref)

    def test_undeclared_summary_is_refused(self):
        self.parent['query_sets_report']={'blob':'x'}
        with patch('delivery_gates.read',side_effect=self.read),self.assertRaisesRegex(ValueError,'undeclared'):
            suites.validate({'blob':'parent'},self.baseline,self.candidate,self.selected,[],'ranking-change')


if __name__=='__main__': unittest.main()
