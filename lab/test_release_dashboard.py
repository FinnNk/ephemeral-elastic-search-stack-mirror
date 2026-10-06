"""Release identity, honest state and read-only snapshot behaviour."""
import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import release_dashboard as dashboard


def deployment(run=158, fingerprint='f'*64):
    return {'build_run':run,'fingerprint':fingerprint,'fields':{'software_release_id':str(run)*20,
        'source_sha':'a'*40,'image':'search@sha256:'+'c'*64,'index':'catalogue'}}


def receipt(target='staging', run=158):
    return {'target':target,'state':'verified','deployment':deployment(run),
            'verified_at':'2026-10-06T15:00:00+00:00','seconds':1.4,'git_revision':'b'*40}


def environment(name, run=158, active=False, ready=True):
    d=deployment(run)
    return {'name':name,'definition':{**d['fields'],'fingerprint':d['fingerprint'],'environment':'lab-delivery-'+name},
            'active':active,'ready':ready,'slot':name.removeprefix('production-') if name.startswith('production-') else None}


def operation(kind='promotion', run=158, state='complete', target='staging'):
    return {'id':'1'*32,'request':{'kind':kind,'run':run,'target':target},'state':state,
            'progress':'Complete','error':None,'result':{'pr':24,'proposal':{'kind':'promotion','target':target,'deployment':deployment(run)}},
            'created_at':'2026-10-06T14:00:00+00:00','updated_at':'2026-10-06T14:02:00+00:00'}


class Projection(unittest.TestCase):
    def project(self, rows=(), receipts=(), environments=None, reviews=None, run=158):
        return dashboard.project(run,list(rows),list(receipts),environments or {},reviews or {},[],[])

    def test_verification_requires_exact_fields_and_ready_rollout(self):
        result=self.project(receipts=[receipt()],environments={'staging':environment('staging')})
        self.assertEqual(result['stages'][1]['state'],'verified')
        altered=environment('staging');altered['definition']['image']='wrong-image'
        self.assertEqual(self.project(receipts=[receipt()],environments={'staging':altered})['stages'][1]['state'],'previously verified')
        not_ready=environment('staging',ready=False)
        self.assertEqual(self.project(receipts=[receipt()],environments={'staging':not_ready})['stages'][1]['state'],'deploying')

    def test_prepared_candidate_does_not_mark_production_verified(self):
        result=self.project(receipts=[receipt()],environments={'production-green':environment('production-green')})
        self.assertEqual(result['stages'][2]['state'],'prepared')
        self.assertEqual(result['stages'][3]['state'],'pending')

    def test_preparation_uses_candidate_not_active_deployment(self):
        row=operation('prepare-production',target='production')
        row['request']={'kind':'prepare-production'}
        row['result']['proposal'].update(kind='prepare-production',deployment=deployment(108),candidate=deployment(158))
        result=self.project(rows=[row],reviews={24:{'number':24,'state':'approved','url':'/pr/24'}})
        self.assertEqual(result['stages'][2]['state'],'approved')
        self.assertEqual(result['stages'][3]['state'],'pending')
        self.assertEqual(len(result['activity']),1)

    def test_current_approval_and_merge_are_separate_from_deployment(self):
        for state in ('awaiting review','approved','merged','changes requested'):
            result=self.project(rows=[operation()],reviews={24:{'number':24,'state':state,'url':'/pr/24'}})
            self.assertEqual(result['stages'][1]['state'],state)
            self.assertIsNone(result['stages'][1]['verification'])

    def test_failed_retry_visible_and_not_masked_by_old_success(self):
        failed=operation(state='failed');failed['error']='Performance budget missed'
        older=operation();older['id']='2'*32
        result=self.project(rows=[failed,older])
        self.assertEqual(result['stages'][1]['state'],'failed')
        self.assertEqual(len(result['activity']),2)

    def test_unbound_failure_not_attributed_to_current_candidate(self):
        row=operation('release-production',state='failed',target='production')
        row['request']={'kind':'release-production','intent':'ranking-change'};row['result']={}
        result=self.project(rows=[row],receipts=[receipt()],environments={'production-green':environment('production-green')})
        self.assertEqual(result['activity'],[])
        self.assertEqual(result['stages'][2]['state'],'prepared')
        self.assertEqual(len(result['unbound_operations']),1)

    def test_same_build_with_other_release_id_not_attached(self):
        # A conflicting fingerprint alone must never join a current definition.
        env=environment('staging');env['definition']['software_release_id']='different'
        result=self.project(receipts=[receipt()],environments={'staging':env})
        self.assertIsNone(result['stages'][1]['environment'])

    def test_same_build_different_inputs_do_not_form_one_successful_journey(self):
        old=receipt('integration');old['deployment']['fingerprint']='e'*64
        old['deployment']['fields']['index']='old-index'
        current=receipt('staging')
        env=environment('staging')
        result=self.project(receipts=[old,current],environments={'staging':env})
        self.assertEqual(result['fingerprint'],'f'*64)
        self.assertEqual(result['stages'][0]['state'],'pending')
        self.assertEqual(result['stages'][1]['state'],'verified')

    def test_no_data_and_unknown_run(self):
        value=dashboard.project(None,[],[],{}, {},[],[])
        self.assertIsNone(value['selected'])
        with self.assertRaises(ValueError):self.project()

    def test_unready_observed_release_is_not_reported_as_undeployed(self):
        value=self.project(receipts=[receipt()],environments={'staging':environment('staging',ready=False)})
        self.assertEqual(value['releases'][0]['state'],'rollout incomplete')
        self.assertEqual(value['releases'][0]['environments'],['staging'])

    def test_saved_check_failure_and_unavailable_evidence_remain_explicit(self):
        stages=[{'title':'Staging','check_operation':{'evidence':{'sha256':'f'*64,'blob':'runs/report'},'report_url':'/operation/report'}}]
        with patch('delivery_gates.read',side_effect=[{'reports':{'performance':{'sha256':'e'*64,'blob':'runs/performance'}}}, {'verdict':'budget-missed'}]):
            dashboard.check_results(stages,[])
            self.assertEqual(stages[0]['checks'][0]['verdict'],'budget-missed')
        notices=[]
        with patch('delivery_gates.read',side_effect=RuntimeError('unavailable')):
            dashboard.check_results(stages,notices)
        self.assertEqual(stages[0]['checks'],[])
        self.assertEqual(len(notices),1)

    def test_missing_database_is_not_created_and_rows_are_owner_filtered(self):
        with TemporaryDirectory() as folder,patch.object(dashboard,'STATE',Path(folder)):
            self.assertEqual(dashboard.operation_rows({'username':'alice'}),[])
            self.assertFalse((Path(folder)/'delivery-operations.sqlite3').exists())
            db=sqlite3.connect(str(Path(folder)/'delivery-operations.sqlite3'))
            db.execute('CREATE TABLE operations(id,owner,request,state,progress,result,error,created_at,updated_at,identity)')
            for owner in ('alice','bob'):
                db.execute('INSERT INTO operations VALUES(?,?,?,?,?,?,?,?,?,?)',(owner,owner,'{"kind":"verify"}','complete','Complete','{}',None,'now','now','{"secret":"must not leak"}'))
            db.commit();db.close()
            rows=dashboard.operation_rows({'username':'alice'})
            self.assertEqual([r['id'] for r in rows],['alice'])
            self.assertNotIn('identity',rows[0])
            self.assertEqual(len(dashboard.operation_rows({'username':'reader','is_reader':True})),2)

    def test_source_gate_must_match_original_head_and_precede_merge(self):
        pr={'number':33,'merged':True,'merge_commit_sha':'a'*40,'head':{'sha':'b'*40},'merged_at':'2026-10-06T15:00:00Z','title':'Search change'}
        row=operation();row['result'].update(source_pr=33,source_sha='b'*40,gate={'state':'pass'})
        with patch.object(dashboard,'api',return_value=[pr]):
            result=dashboard.source_merge({'source_sha':'a'*40},[row],[])
            self.assertEqual(result['gate']['state'],'pass')
            row['updated_at']='2026-10-06T16:00:00+00:00'
            self.assertIsNone(dashboard.source_merge({'source_sha':'a'*40},[row],[])['gate'])
            row['updated_at']='2026-10-06T14:00:00+00:00';row['result']['source_sha']='wrong'
            self.assertIsNone(dashboard.source_merge({'source_sha':'a'*40},[row],[])['gate'])

    def test_review_ignores_old_head_and_dismissed_approvals(self):
        pr={'head':{'sha':'head'},'state':'open'}
        reviews=[{'id':1,'user':{'login':'a'},'state':'APPROVED','commit_id':'old'},
                 {'id':2,'user':{'login':'b'},'state':'APPROVED','commit_id':'head','dismissed':True}]
        with patch.object(dashboard,'api',side_effect=[pr,reviews]):
            self.assertEqual(dashboard.review(24)['state'],'awaiting review')

    def test_get_only_snapshot_and_provider_outage(self):
        calls=[]
        def read_api(path,*args,**kwargs):
            self.assertFalse(args);self.assertFalse(kwargs);calls.append(path)
            raise RuntimeError('provider unavailable')
        with patch.object(dashboard,'api',side_effect=read_api),patch.object(dashboard,'operation_rows',return_value=[]), \
                patch.object(dashboard,'records',return_value=[]),patch.object(dashboard,'observed',return_value=({},['Cluster status unavailable'])):
            value=dashboard.snapshot({'username':'alice'})
            self.assertIsNone(value['selected'])
            self.assertIn('Source build status is unavailable.',value['notices'])
            self.assertTrue(calls)


if __name__=='__main__':unittest.main()
