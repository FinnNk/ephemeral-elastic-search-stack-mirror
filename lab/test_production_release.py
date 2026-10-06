"""Production routing, stale evidence and service-target capture contracts."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import unittest
from unittest.mock import Mock, patch

from delivery_runtime import fingerprint
from delivery.ci.release import canonical
import production_release as release
from delivery_operations import validate
import variant_capture_worker as worker


def deployment(image='a'):
    fields = {'index': 'frozen-index', 'dataset_sha256': 'b'*64,
        'catalogue_manifest_sha256': 'c'*64, 'mapping_sha256': 'd'*64,
        'index_recipe_sha256': 'e'*64, 'engine': '9.5.4',
        'request_context': {'country':'GB','currency':'GBP'},
        'image':'nexus.test/search@sha256:'+image*64}
    return {'fields':fields,'fingerprint':fingerprint(fields),'build_run':1}


def chart(dep, name):
    return '\n---\n'.join(json.dumps(d) for d in [
        {'kind':'Namespace','apiVersion':'v1','metadata':{'name':name}},
        {'kind':'Deployment','apiVersion':'apps/v1','metadata':{'name':'search','namespace':name},
         'spec':{'selector':{'matchLabels':{'app':'search'}},'template':{'metadata':{'labels':{'app':'search'}},
                 'spec':{'containers':[{'image':dep['fields']['image']}]}}}},
        {'kind':'Service','apiVersion':'v1','metadata':{'name':'search','namespace':name},
         'spec':{'selector':{'app':'search'},'ports':[{'port':8080}]}},
        {'kind':'ConfigMap','apiVersion':'v1','metadata':{'name':'frozen-definition','namespace':name},
         'data':{'definition.json':json.dumps(release.entry(dep,name))}}])


class ProductionReleaseTests(unittest.TestCase):
    def setUp(self):
        self.slots = release.initial(deployment())
        self.slots['slots']['green'] = deployment('f')

    def test_preparation_and_switch_preserve_both_exact_images(self):
        before = deepcopy(self.slots)
        docs = release.documents(self.slots, chart)
        self.assertEqual(self.slots,before)
        deployments = {d['metadata']['name']:d for d in docs if d['kind']=='Deployment'}
        self.assertEqual(set(deployments),{'search-blue','search-green'})
        stable = next(d for d in docs if d['kind']=='Service' and d['metadata']['name']=='search')
        self.assertEqual(stable['spec']['selector'],{'app':'search','release-slot':'blue'})
        self.slots['active']='green'
        after=release.documents(self.slots,chart)
        self.assertEqual(deployments,{d['metadata']['name']:d for d in after if d['kind']=='Deployment'})
        stable=next(d for d in after if d['kind']=='Service' and d['metadata']['name']=='search')
        self.assertEqual(stable['spec']['selector']['release-slot'],'green')
        self.assertEqual(stable['metadata']['annotations']['argocd.argoproj.io/sync-wave'],'1')

    def test_different_index_or_catalogue_is_rejected(self):
        for key in release.CATALOGUE_FIELDS:
            other=deepcopy(self.slots);other['slots']['green']['fields'][key]='different'
            other['slots']['green']['fingerprint']=fingerprint(other['slots']['green']['fields'])
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'same concrete'):
                release.validate_state(other)

    def test_final_evidence_cannot_be_reused_after_switch(self):
        report={'complete':True,'completed_at':datetime.now(timezone.utc).isoformat(),
            'production_slots_sha256':hashlib.sha256(canonical(self.slots)).hexdigest(),
            'production_baseline':self.slots['slots']['blue']['fingerprint'],
            'production_candidate':self.slots['slots']['green']['fingerprint']}
        with patch('delivery_gates.read',return_value=report),patch.object(release,'frozen_catalogue'):
            release.validate_final({},self.slots)
            other=deepcopy(self.slots);other['active']='green'
            with self.assertRaisesRegex(ValueError,'stale'):
                release.validate_final({},other)

    def test_write_block_is_required(self):
        with patch('data_contract.elastic',return_value={'frozen-index':{'settings':{'index':{'blocks':{'write':'true'}}}}}):
            release.frozen_catalogue(deployment())
        with patch('data_contract.elastic',return_value={'frozen-index':{'settings':{'index':{}}}}),self.assertRaisesRegex(ValueError,'Pause catalogue'):
            release.frozen_catalogue(deployment())

    def test_capture_calls_active_service_and_candidate_slot(self):
        row={'query':'lamp','country':'GB','currency':'GBP','filters':{}}
        answer={**row,'ids':['p1'],'total':1,'variant_id':'ranker-a','configuration_sha256':'a'*64}
        for name,service in [('active','search'),('candidate','search-green')]:
            pacer=Mock();pacer.fetch.return_value=answer
            result=worker.request(name,{'environment':release.NAMESPACE,'service':service,
                'selection':'default','variant_id':'ranker-a','configuration_sha256':'a'*64},row,pacer)
            self.assertIn('http://'+service+'.'+release.NAMESPACE+'.svc.cluster.local',pacer.fetch.call_args.args[0])
            self.assertNotIn('X-Lab-Variant',pacer.fetch.call_args.args[1])
            self.assertEqual(result['variant_id'],name)

    def test_named_operations_have_bounded_fields(self):
        validate({'kind':'prepare-production'})
        validate({'kind':'release-production','intent':'ranking-change'})
        with self.assertRaises(ValueError):
            validate({'kind':'prepare-production','command':'kubectl'})

    def test_declared_selector_without_matching_ready_endpoint_is_rejected(self):
        service={'spec':{'selector':{'app':'search','release-slot':'blue'}}}
        for endpoints in ([], [{'conditions':{'ready':True},'targetRef':{'name':'search-green-old'}}],
                          [{'conditions':{'ready':False},'targetRef':{'name':'search-blue-new'}}]):
            responses=[Mock(stdout=json.dumps(service)), Mock(stdout=json.dumps({'items':[{'endpoints':endpoints}]}))]
            with self.subTest(endpoints=endpoints), patch.object(release,'frozen_catalogue'), \
                    patch.object(release,'k',side_effect=responses), self.assertRaisesRegex(ValueError,'route has not reached'):
                release.live(self.slots)

    def test_preparation_cannot_switch_the_active_route(self):
        before=release.initial(deployment())
        after=deepcopy(self.slots);after['active']='green'
        proposal={'previous_slots':before,'slots':after,'candidate':deployment('f'),
                  'deployment':deployment()}
        with patch.object(release,'git',return_value=''), patch.object(release,'read_target',return_value=deployment()), \
                self.assertRaisesRegex(ValueError,'leave the active release'):
            release.inspect_preparation({},proposal,'base','head',[],'proposals/fixture.json')

    def test_rendered_proposal_cannot_add_unrelated_files(self):
        with self.assertRaisesRegex(ValueError,'outside its declared slots'):
            release.validate_files('head',self.slots,
                [release.PATH,'targets/production/rendered/search.yaml','targets/staging/deployment.json'],set())


if __name__=='__main__':
    unittest.main()
