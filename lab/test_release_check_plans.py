"""Release-plan accumulation, approval and promotion integrity boundaries."""
import base64
from copy import deepcopy
import json
from datetime import datetime, timezone
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch, Mock

import release_check_plans as plans
from delivery_operations import Operations, validate


def deployment(run, source):
    return {'build_run':run,'fingerprint':str(run)*64,
            'fields':{'source_sha':source,'image':'image-'+str(run),'dataset_release':'esci-gb-v1','dataset_sha256':'d'*64}}


class ReleasePlans(unittest.TestCase):
    def setUp(self):
        self.base,self.middle,self.head='a'*40,'b'*40,'c'*40
        self.baseline,self.candidate=deployment(1,self.base),deployment(2,self.head)
        self.pin={'target':'staging','baseline':self.baseline,'candidate':self.candidate,
                  'primary_query_sets':[{'name':'standard','required':True}],'policy_sha256':'f'*64}
        self.selected={'source_sha':self.head,'selection':[{'variant':'ranker-a','intent':'preserve-results'}],
                       'configuration':{'default_variant':'ranker-a','variants':{'ranker-a':{}}}}
        self.train={'name':'trainers','path':'evaluation/trainers.jsonl','judgements':'evaluation/labels.jsonl','required':True}
        self.season={'name':'seasonal','path':'evaluation/seasonal.jsonl','required':False}
        self.declared={self.base:{'selected':[{'intent':'ranking-change'}],'additional_query_sets':[self.train]},
                       self.middle:{'selected':[{'intent':'ranking-change'}],'additional_query_sets':[self.season]},
                       self.head:{'selected':[{'intent':'preserve-results'}],'additional_query_sets':[self.season]}}
        def data(path,revision):
            if 'labels' in path:return b'{"query_id":"q","product_id":"p","grade":3}\n'
            text='summer' if revision==self.middle else 'winter'
            return json.dumps({'query_id':'q','query':text,'country':'GB','currency':'GBP','filters':{}}).encode()+b'\n'
        self.data=data
        def api(path):
            revision=path.split('ref=')[1]
            return {'content':base64.b64encode(json.dumps(self.declared[revision]).encode()).decode()}
        self.api=api
        self.mocks=[patch.object(plans,'binding',return_value=self.pin),
                    patch.object(plans,'lineage',return_value=(self.base,[{'source_sha':self.middle,'title':'Ranking change'},{'source_sha':self.head,'title':'Footer'}])),
                    patch.object(plans,'source_file',side_effect=data),patch.object(plans,'api',side_effect=api),
                    patch('delivery_variant_selection.source_selection',return_value=self.selected)]
        for mock in self.mocks:mock.start();self.addCleanup(mock.stop)
        self.suggestion=plans.suggest(self.baseline,self.candidate,'staging')

    def edits(self):
        return {'variants':deepcopy(self.suggestion['variants']),
                'suites':[{'id':s['id'],'disposition':'required' if s['required'] else 'report_only','reason':''} for s in self.suggestion['suites']],
                'additional_query_sets':[],'reason':'These checks cover the combined ranking and presentation changes.'}

    def test_accumulates_removed_requirements_and_distinct_versions(self):
        self.assertEqual(len(self.suggestion['suites']),3)
        self.assertEqual([s['name'] for s in self.suggestion['suites']].count('seasonal'),2)
        self.assertTrue(next(s for s in self.suggestion['suites'] if s['name']=='trainers')['required'])
        self.assertEqual(self.suggestion['variants'][0]['intent'],'ranking-change')
        self.assertEqual(self.suggestion['binding']['primary_query_sets'],[{'name':'standard','required':True}])

    def test_freezes_original_historical_bytes_and_required_status(self):
        plan=plans.build_plan(self.suggestion,self.edits(),'reviewer')
        frozen=plans.frozen_additional(plan)
        self.assertEqual(len({i['name'] for i in frozen}),3)
        self.assertEqual({i['queries'][0]['query'] for i in frozen},{'summer','winter'})
        self.assertTrue(next(i for i in frozen if i['source_sha']==self.base)['required'])

    def test_every_inherited_set_needs_a_disposition(self):
        edits=self.edits();edits['suites'].pop()
        with self.assertRaisesRegex(ValueError,'every suggested'):plans.build_plan(self.suggestion,edits,'reviewer')
        edits=self.edits();edits['suites'][0]['id']='x'*64
        with self.assertRaises(ValueError):plans.build_plan(self.suggestion,edits,'reviewer')

    def test_retiring_or_weakening_a_requirement_needs_reason(self):
        for disposition in ('retired','report_only'):
            edits=self.edits();edits['suites'][0]['disposition']=disposition
            with self.assertRaisesRegex(ValueError,'Explain'):plans.build_plan(self.suggestion,edits,'reviewer')
            edits['suites'][0]['reason']='Replaced by the reviewed seasonal requirement for this combined release.'
            plan=plans.build_plan(self.suggestion,edits,'reviewer')
            self.assertEqual(plan['edits']['suites'][0]['disposition'],disposition)

    def test_primary_sets_and_candidate_variants_cannot_be_overridden(self):
        edits=self.edits();edits['primary_query_sets']=[]
        with self.assertRaisesRegex(ValueError,'Unknown'):plans.build_plan(self.suggestion,edits,'reviewer')
        edits=self.edits();edits['variants']=[]
        with self.assertRaisesRegex(ValueError,'every candidate variant'):plans.build_plan(self.suggestion,edits,'reviewer')

    def test_review_can_change_combined_intent_without_changing_configuration(self):
        edits=self.edits();edits['variants'][0]['intent']='preserve-results'
        plan=plans.build_plan(self.suggestion,edits,'reviewer')
        self.assertEqual(plan['edits']['variants'][0]['intent'],'preserve-results')
        self.assertEqual(self.selected['selection'][0]['intent'],'preserve-results')
        self.assertEqual(plan['suggestion']['variants'][0]['intent'],'ranking-change')

    def test_required_set_needs_reference_labels(self):
        edits=self.edits();edits['suites'][1]['disposition']='required'
        with self.assertRaisesRegex(ValueError,'judgement'):plans.build_plan(self.suggestion,edits,'reviewer')

    def test_adds_suites_from_exact_candidate_commit(self):
        edits=self.edits();edits['additional_query_sets']=[{'name':'controls','path':'evaluation/controls.jsonl','required':False}]
        plan=plans.build_plan(self.suggestion,edits,'reviewer')
        self.assertEqual(plan['additional_sets'][0]['source_sha'],self.head)
        self.assertEqual(len(plans.frozen_additional(plan)),4)

    def test_changed_query_bytes_or_binding_invalidate_record(self):
        plan=plans.build_plan(self.suggestion,self.edits(),'reviewer')
        with patch.object(plans,'source_file',return_value=b'{"query_id":"q","query":"changed","country":"GB","currency":"GBP"}\n'):
            with self.assertRaises(ValueError):plans.frozen_additional(plan)
        altered=deepcopy(plan);altered['suggestion']['binding']['policy_sha256']='changed'
        with self.assertRaisesRegex(ValueError,'stale'):plans.validate_record(altered,self.baseline,self.candidate,'staging')

    def test_missing_or_replaced_approval_blocks_every_promotion(self):
        with patch.object(plans,'pulls',return_value=[]):
            with self.assertRaisesRegex(ValueError,'Review and record'):plans.require(self.baseline,self.candidate,'staging')
        plan=plans.build_plan(self.suggestion,self.edits(),'reviewer')
        pr={'number':4,'merged':True,'merged_at':'2026-10-15T10:00:00Z','head':{'sha':'head'},'merge_commit_sha':'merge'}
        payload=json.dumps(plan).encode()
        with patch.object(plans,'pulls',return_value=[pr]),patch.object(plans,'inspect',return_value=(pr,'path',payload,plan)),patch.object(plans,'content',return_value=payload),patch.object(plans,'approval',return_value={'id':10}),patch.object(plans,'validate_record'):
            selected,reference=plans.require(self.baseline,self.candidate,'staging')
            self.assertEqual(selected['selection'],plan['edits']['variants'])
            self.assertEqual(reference['pr'],4)
            with self.assertRaisesRegex(ValueError,'changed'):plans.require(self.baseline,self.candidate,'staging',{'id':'older'})

    def test_only_named_administrator_latest_exact_head_review_counts(self):
        from relevance_decisions import approved_review
        pr={'number':4,'head':{'sha':'head'},'user':{'login':'elastic-agent'}}
        reviews=[{'id':1,'user':{'login':'reviewer'},'state':'APPROVED','commit_id':'old'}]
        with patch('relevance_decisions.api',side_effect=[{'permission':'admin'},reviews]):
            with self.assertRaisesRegex(ValueError,'exact'):approved_review(pr,{'reviewer':'reviewer'})
        reviews.append({'id':2,'user':{'login':'reviewer'},'state':'APPROVED','commit_id':'head'})
        with patch('relevance_decisions.api',side_effect=[{'permission':'admin'},reviews]):
            self.assertEqual(approved_review(pr,{'reviewer':'reviewer'})['id'],2)

    def test_plan_operations_reject_service_accounts_and_validate_shape(self):
        validate({'kind':'suggest-release-plan','run':2,'target':'staging'})
        with self.assertRaises(ValueError):validate({'kind':'propose-release-plan','suggestion':'bad','edits':{}})
        with tempfile.TemporaryDirectory() as folder:
            ops=Operations(Path(folder)/'ops.sqlite3')
            with self.assertRaisesRegex(ValueError,'human'):
                ops.submit({'kind':'accept-release-plan','pr':4},{'username':'actions','is_admin':True,'is_delivery_service':True},'test')

    def test_evaluation_without_plan_never_starts_a_driver(self):
        import delivery_gates
        with patch.object(plans,'require',side_effect=ValueError('Review and record a plan')),patch.object(delivery_gates,'evaluate') as driver:
            with self.assertRaisesRegex(ValueError,'Review and record'):
                delivery_gates.evaluate_variants(self.baseline,self.candidate,target='staging')
            driver.assert_not_called()

    def test_promotion_validation_rejects_legacy_evidence_without_plan(self):
        import delivery_gates
        evidence={'format':1,'state':'pass','baseline':self.baseline['fingerprint'],'candidate':self.candidate['fingerprint'],
                  'completed_at':datetime.now(timezone.utc).isoformat(),'source_sha':self.head}
        with self.assertRaisesRegex(ValueError,'no reviewed release check plan'):
            delivery_gates.validate_variant_evidence(evidence,self.baseline['fingerprint'],self.candidate['fingerprint'],target='staging',baseline_deployment=self.baseline,candidate_deployment=self.candidate)

    def test_primary_groups_are_always_added_to_planned_suites(self):
        from promotion_query_sets import frozen_sets
        plan=plans.build_plan(self.suggestion,self.edits(),'reviewer')
        with patch('primary_query_sets.frozen_sets',return_value=[{'name':'protected','required':True}]):
            frozen=frozen_sets({'_release_plan':plan},self.candidate)
            self.assertEqual(frozen[0],{'name':'protected','required':True})
            self.assertEqual(len(frozen),4)

    def test_recorded_status_checks_main_and_merge_bytes(self):
        plan=plans.build_plan(self.suggestion,self.edits(),'reviewer')
        pr={'number':4,'merged':True,'merge_commit_sha':'merge'}
        with patch.object(plans,'inspect',return_value=(pr,'path',b'approved',plan)),patch.object(plans,'content',return_value=b'changed'):
            with self.assertRaisesRegex(ValueError,'source-control record'):plans.status(4)

    def test_inspection_rejects_unrelated_changes_in_plan_pr(self):
        plan=plans.build_plan(self.suggestion,self.edits(),'reviewer');identifier=plans.digest(plan)
        path=plans.DIRECTORY+identifier+'.json'
        pr={'number':4,'state':'open','base':{'ref':'main'},'head':{'ref':plans.PREFIX+identifier,'sha':'head'}}
        files=[{'filename':path,'status':'added'},{'filename':'targets/staging/deployment.json','status':'changed'}]
        with patch.object(plans,'api',side_effect=[pr,files]),patch.object(plans,'content',return_value=json.dumps(plan).encode()):
            with self.assertRaisesRegex(ValueError,'only its exact'):plans.inspect(4)

    def test_dashboard_recovers_approved_plan_without_operation_history(self):
        plan=plans.build_plan(self.suggestion,self.edits(),'reviewer')
        def env(name,d):return {'name':name,'build_run':d['build_run'],'definition':{**d['fields'],'fingerprint':d['fingerprint']}}
        data={'selected':{'run':2,'source_sha':self.head},'environments':[env('staging',self.baseline),env('integration',self.candidate)]}
        summary={'state':'recorded','id':'plan','pr':4,'url':'https://gitea.test/pulls/4'}
        with patch('release_dashboard.operation_rows',return_value=[]),patch.object(plans,'pulls',return_value=[{'number':4,'merged':True}]),patch.object(plans,'inspect',return_value=({'number':4},'path',b'bytes',plan)),patch.object(plans,'status',return_value=summary),patch.object(plans,'policy_pin',return_value='f'*64):
            value=plans.dashboard_status(data,{'username':'reviewer'})['staging']
            self.assertEqual(value['state'],'recorded');self.assertEqual(value['reviewed_variants'],plan['edits']['variants'])
            data['environments'][0]['definition']['fingerprint']='new baseline'
            self.assertEqual(plans.dashboard_status(data,{'username':'reviewer'})['staging']['state'],'needed')

    def test_checks_cannot_predate_plan_approval(self):
        import delivery_gates
        evidence={'format':1,'state':'pass','baseline':self.baseline['fingerprint'],'candidate':self.candidate['fingerprint'],
                  'completed_at':datetime.now(timezone.utc).isoformat(),'started_at':'2026-10-15T09:00:00Z',
                  'source_sha':self.head,'release_check_plan':{'merged_at':'2026-10-15T10:00:00Z'}}
        with patch.object(plans,'require',return_value=(self.selected,{})):
            with self.assertRaisesRegex(ValueError,'before its checks start'):
                delivery_gates.validate_variant_evidence(evidence,self.baseline['fingerprint'],self.candidate['fingerprint'],target='staging',baseline_deployment=self.baseline,candidate_deployment=self.candidate)

    def test_explicit_legacy_intent_cannot_bypass_release_plan(self):
        import delivery_gates
        with patch.object(delivery_gates,'read',return_value={'kind':'delivery-evidence','intent':'preserve-results'}):
            with self.assertRaisesRegex(ValueError,'reviewed release check plan'):
                delivery_gates.validate_evidence({},self.baseline['fingerprint'],self.candidate['fingerprint'],'preserve-results',target='staging',baseline_deployment=self.baseline,candidate_deployment=self.candidate)

    def test_integration_plan_uses_selected_catalogue_and_manifests(self):
        settings={'dataset_release':'esci-gb-summer','index_recipe_sha256':'a'*64,'query_manifest_sha256':'b'*64,'judgement_manifest_sha256':'c'*64}
        with patch('delivery_runtime.checkout'),patch('delivery_runtime.read_target',return_value=self.baseline),patch('delivery_runtime.resolve',return_value=self.candidate) as resolve,patch('delivery_release.from_run',return_value=({'source_sha':self.head},{},{})):
            plans.scope(2,'integration',settings)
            self.assertEqual(resolve.call_args.kwargs,{'variant_config':self.selected['configuration'],'dataset':'esci-gb-summer','recipe_sha':'a'*64,'query_manifest_sha':'b'*64,'judgement_manifest_sha':'c'*64})

    def test_rollback_lineage_includes_commits_removed_from_baseline(self):
        original=self.mocks[1];original.stop()
        def git(repo,*args):
            if args[0]=='rev-parse':return 'false'
            if args[0]=='fetch':return ''
            if args[0]=='merge-base':return self.head
            if args[0]=='rev-list':return self.middle if args[-1]==self.head+'..'+self.base else ''
            return 'Reverted ranking change'
        with patch.object(plans,'ensure_checkout'),patch.object(plans,'git',side_effect=git):
            _,changes=plans.lineage(self.base,self.head)
        self.assertEqual(changes,[{'source_sha':self.middle,'side':'baseline-only','title':'Reverted ranking change'}])

    def test_record_rechecks_exact_head_before_merging(self):
        plan=plans.build_plan(self.suggestion,self.edits(),'reviewer')
        first={'number':4,'head':{'sha':'approved'}};changed={'number':4,'head':{'sha':'changed'}}
        with patch('delivery_runtime.checkout'),patch.object(plans,'inspect',side_effect=[(first,'path',b'bytes',plan),(changed,'path',b'bytes',plan)]),patch.object(plans,'scope',return_value=(self.baseline,self.candidate)),patch.object(plans,'validate_record'),patch.object(plans,'approval'),patch.object(plans,'merge_demo') as merge:
            with self.assertRaisesRegex(ValueError,'head changed'):plans.record(4)
            merge.assert_not_called()


if __name__=='__main__':unittest.main()
