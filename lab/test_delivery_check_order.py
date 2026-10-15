"""Required functional and query-set failures must prevent the Gatling run."""
from contextlib import ExitStack
from copy import deepcopy
import unittest
from unittest.mock import patch

import delivery_gates as gates


class DeliveryCheckOrder(unittest.TestCase):
    def setUp(self):
        self.baseline={'fingerprint':'B','fields':{'dataset_release':'esci-gb-v1','dataset_sha256':'catalogue'}}
        self.candidate={**self.baseline,'fingerprint':'C'}
        self.inputs={'catalogue_manifest_sha256':'catalogue','query_manifest_sha256':'queries','judgement_manifest_sha256':'labels'}
        self.store={}
        self.calls=[]
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for name,value in [('deployment_inputs',self.inputs),('search',{'variant_id':'default','configuration_sha256':'config'})]:
            self.stack.enter_context(patch.object(gates,name,return_value=value))
        self.stack.enter_context(patch.object(gates,'preview',side_effect=lambda d:{'name':'lab-'+d['fingerprint']}))
        self.stack.enter_context(patch.object(gates,'definition',side_effect=lambda n:{'fingerprint':n.removeprefix('lab-')}))
        self.stack.enter_context(patch.object(gates,'retain',side_effect=self.retain))
        self.stack.enter_context(patch.object(gates,'read',side_effect=lambda ref:deepcopy(self.store[ref['blob']])))
        self.functional=self.stack.enter_context(patch.object(gates,'evaluate_pair',side_effect=self.capture))
        self.performance=self.stack.enter_context(patch.object(gates,'evaluate_performance_pair',side_effect=self.load))

    def retain(self,value,filename):
        key=str(len(self.store));self.store[key]=deepcopy(value)
        return {'blob':key,'sha256':key}

    def summary(self,value):
        ref=self.retain(value,'report.json')
        return {'report_blob':ref['blob'],'report_sha256':ref['sha256']}

    def capture(self,first,second,mode,**kwargs):
        self.calls.append(mode)
        return self.summary({'baseline':{'fingerprint':'B'},'candidate':{'fingerprint':'C'},
            'mode':mode,'scope':'full','complete':True,'query_count':1,'completed_query_count':1,
            'verdict':'measured' if mode=='relevance' else 'unchanged','judgement_sha256':'labels',
            'query_manifest_sha256':'queries','judgement_manifest_sha256':'labels'})

    def load(self,*args,**kwargs):
        self.calls.append('performance')
        return self.summary({'baseline':{'fingerprint':'B'},'candidate':{'fingerprint':'C'},
            'kind':'paired-api-performance','valid':True,'same_workload':True,'warmup_ready':True,
            'verdict':'within-budget','measured_phases':{'normal':{}}})

    def test_all_functional_and_declared_sets_precede_performance(self):
        def suites(ref):
            self.calls.append('query-sets')
            return self.retain({**self.store[ref['blob']],'query_sets_report':{'blob':'suite-report'}},'parent.json')
        ref=gates.evaluate(self.baseline,self.candidate,'ranking-change',before_performance=suites)
        self.assertEqual(self.calls,['result-regression','relevance','query-sets','performance'])
        parent=self.store[ref['blob']]
        self.assertEqual(set(parent['reports']),{'result-regression','relevance','performance'})
        self.assertEqual(parent['query_sets_report'],{'blob':'suite-report'})
        self.assertEqual(parent['performance_status'],'completed')

    def test_incomplete_standard_capture_retains_failure_and_skips_load(self):
        def incomplete(*args,**kwargs):
            summary=self.capture(*args,**kwargs)
            self.store[summary['report_blob']]['complete']=False
            return summary
        self.functional.side_effect=incomplete
        with self.assertRaises(gates.EvidenceFailure) as failure:
            gates.evaluate(self.baseline,self.candidate,'ranking-change')
        parent=self.store[failure.exception.reference['blob']]
        self.assertEqual(parent['performance_status'],'not_run')
        self.assertEqual(set(parent['reports']),{'result-regression'})
        self.performance.assert_not_called()
        with self.assertRaisesRegex(ValueError,'All three'):
            gates.validate_evidence(failure.exception.reference,'B','C','ranking-change')

    def test_required_query_set_failure_keeps_its_report_and_skips_load(self):
        def suites(ref):
            updated=self.retain({**self.store[ref['blob']],'query_sets_report':{'blob':'blocked-suite'}},'parent.json')
            raise gates.EvidenceFailure('Required set blocked',updated)
        with self.assertRaisesRegex(gates.EvidenceFailure,'Required set') as failure:
            gates.evaluate(self.baseline,self.candidate,'ranking-change',before_performance=suites)
        self.assertEqual(self.store[failure.exception.reference['blob']]['query_sets_report'],{'blob':'blocked-suite'})
        self.performance.assert_not_called()

    def test_missing_frozen_relevance_stops_before_performance(self):
        def unavailable(*args,**kwargs):
            summary=self.capture(*args,**kwargs)
            if args[2]=='relevance':
                self.store[summary['report_blob']]['judgement_sha256']=None
            return summary
        self.functional.side_effect=unavailable
        with self.assertRaisesRegex(gates.EvidenceFailure,'Frozen relevance') as failure:
            gates.evaluate(self.baseline,self.candidate,'ranking-change')
        self.assertEqual(set(self.store[failure.exception.reference['blob']]['reports']),{'result-regression','relevance'})
        self.performance.assert_not_called()
