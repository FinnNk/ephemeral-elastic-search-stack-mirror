"""Release actions retain review rules and reject stale queued selections."""
from copy import deepcopy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import release_control as control
from delivery_operations import Operations

ADMIN = {'username': 'reviewer', 'is_admin': True}


def fixture():
    fields = {'source_sha':'a'*40, 'dataset_release':'esci-gb-v1', 'index_recipe_sha256':'b'*64,
              'query_manifest_sha256':'c'*64, 'judgement_manifest_sha256':'d'*64}
    env = {'name':'integration','definition':{**fields,'fingerprint':'e'*64},'ready':True,'active':False,'slot':None}
    return {'selected':{'run':158,'source_sha':'a'*40,'release_id':'f'*64},'release':fields,
            'build':{'conclusion':'success'},'notices':[], 'environments':[env],
            'stages':[{'name':'integration','state':'verified','environment':env},
                      {'name':'staging','state':'pending','environment':None},
                      {'name':'candidate','state':'pending','environment':None},
                      {'name':'production','state':'pending','environment':None}],
            'active_production':None,'activity':[]}


class ReleaseActions(unittest.TestCase):
    def test_readers_and_service_identities_have_no_actions(self):
        for identity in ({'username':'reader','is_reader':True}, {**ADMIN,'is_delivery_service':True}):
            self.assertFalse(any(a['enabled'] for a in control.choices(fixture(), identity)['actions']))
            with self.assertRaises(PermissionError):control.submit({},identity,'same')

    def test_staging_requires_current_integration(self):
        data=fixture();self.assertTrue(next(a for a in control.choices(data,ADMIN)['actions'] if a['name']=='staging')['enabled'])
        data['stages'][0]['state']='previously verified'
        self.assertFalse(next(a for a in control.choices(data,ADMIN)['actions'] if a['name']=='staging')['enabled'])

    def test_unavailable_provider_and_unsuccessful_build_fail_closed(self):
        for key,value in [('notices',['Unavailable']),('build',{'conclusion':'failure'})]:
            data=fixture();data[key]=value
            self.assertFalse(any(a['enabled'] for a in control.choices(data,ADMIN)['actions']))

    def test_busy_or_existing_proposal_prevents_duplicate_checks(self):
        data=fixture();data['activity']=[{'state':'queued'}]
        self.assertFalse(any(a['enabled'] for a in control.choices(data,ADMIN)['actions']))
        data=fixture();data['stages'][1]['review_operation']={'pr':{'state':'awaiting review'}}
        self.assertFalse(next(a for a in control.choices(data,ADMIN)['actions'] if a['name']=='staging')['enabled'])

    def test_manifest_selection_is_forwarded(self):
        value=control.payload(fixture(),'staging','ranking-change')
        self.assertEqual(value['query_manifest'],'c'*64);self.assertEqual(value['judgement_manifest'],'d'*64)

    def test_context_ignores_refresh_time_and_duplicate_review_observations(self):
        data=fixture();a=control.context(data);data['updated_at']='later'
        self.assertEqual(a,control.context(data))
        review={'number':24,'state':'approved','head_sha':'h'*40}
        data['activity']=[{'pr':review}];a=control.context(data);data['activity'].append({'pr':review})
        self.assertEqual(a,control.context(data));data['activity'][1]={'pr':{**review,'head_sha':'i'*40}}
        self.assertNotEqual(a,control.context(data))

    def test_execution_detects_target_or_approval_drift(self):
        data=fixture();binding={'identity':ADMIN,'request':{'run':158,'context':control.context(data)}}
        with patch.object(control,'snapshot',return_value=data):control.validate_binding(binding)
        data['environments'][0]['definition']['fingerprint']='z'*64
        with patch.object(control,'snapshot',return_value=data),self.assertRaises(ValueError):control.validate_binding(binding)

    def test_retry_is_durable_even_after_context_changes(self):
        data=fixture();request={'run':158,'action':'staging','intent':'ranking-change','context':control.context(data)}
        with tempfile.TemporaryDirectory() as folder,patch('delivery_operations.STATE',Path(folder)),patch.object(control,'snapshot',return_value=data):
            first=control.submit(request,ADMIN,'stable-request');again=control.submit(request,ADMIN,'stable-request')
            self.assertEqual(first['id'],again['id']);self.assertEqual(len(Operations().active()),1)
            data['notices']=['Provider unavailable']
            self.assertEqual(control.submit(request,ADMIN,'stable-request')['id'],first['id'])
            with self.assertRaises(ValueError):control.submit({**request,'intent':'preserve-results'},ADMIN,'stable-request')

    def test_stale_submission_creates_no_operation(self):
        with tempfile.TemporaryDirectory() as folder,patch('delivery_operations.STATE',Path(folder)),patch.object(control,'snapshot',return_value=fixture()):
            with self.assertRaises(ValueError):control.submit({'run':158,'action':'staging','intent':'ranking-change','context':'0'*64},ADMIN,'stale')
            self.assertEqual(Operations().active(),[])

    def test_approved_proposal_must_belong_to_selected_release(self):
        data=fixture();data['activity']=[{'pr':{'number':24,'state':'approved','head_sha':'f'*40}}]
        request={'run':158,'action':'deploy','intent':'ranking-change','pr':25,'context':control.context(data)}
        with tempfile.TemporaryDirectory() as folder,patch('delivery_operations.STATE',Path(folder)),patch.object(control,'snapshot',return_value=data):
            with self.assertRaises(ValueError):control.submit(request,ADMIN,'wrong-pr')

    def test_rollback_needs_previously_verified_retained_slot(self):
        data=fixture();active={'name':'production-blue','definition':{'fingerprint':'a'*64},'ready':True,'active':True,'slot':'blue'}
        retained={**active,'name':'production-green','active':False,'slot':'green','definition':{'fingerprint':'b'*64}}
        data['environments']=[active,retained];data['active_production']=active;data['stages'][3].update(state='verified',environment=active)
        self.assertFalse(next(a for a in control.choices(data,ADMIN)['actions'] if a['name']=='rollback')['enabled'])
        retained['rollback_verified']=True
        self.assertTrue(next(a for a in control.choices(data,ADMIN)['actions'] if a['name']=='rollback')['enabled'])

    def test_worker_stops_stale_action_before_running_checks(self):
        import delivery_operations
        data=fixture();binding={'request':{'run':158,'action':'staging','context':control.context(data)},'identity':ADMIN}
        with tempfile.TemporaryDirectory() as folder,patch('delivery_operations.STATE',Path(folder)),patch('release_control.validate_binding',side_effect=ValueError('Target moved')),patch('delivery_cli.execute') as execute:
            store=Operations();row=store.submit({'kind':'promotion','target':'staging','run':158,'intent':'ranking-change'},ADMIN,'worker',release_binding=binding)
            delivery_operations.execute_next()
            self.assertEqual(store.get(row['id'])['state'],'failed')
            execute.assert_not_called()

    def test_internal_binding_cannot_be_supplied_to_generic_operations(self):
        from delivery_operations import validate
        with self.assertRaises(ValueError):validate({'kind':'prepare-production','_release_binding':{}})


if __name__ == '__main__':unittest.main()
