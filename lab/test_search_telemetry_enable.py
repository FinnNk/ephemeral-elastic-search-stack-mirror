"""Legacy telemetry wiring preserves release fields and runtime credentials."""
import base64
from contextlib import ExitStack
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from observability import enable_search as wiring


class LegacySearchTelemetry(unittest.TestCase):
    def setUp(self):
        self.namespace='lab-delivery-run-158-139cbacf'
        self.fingerprint='a'*64
        self.image='nexus.localhost:18185/search-api@sha256:'+'b'*64
        self.definition={'fingerprint':self.fingerprint,'image':self.image,'index':'frozen-index'}
        self.secret={'data':{'ES_PASSWORD':'private-credential','ES_USER':'private-user'}}
        self.deployment={'spec':{'template':{'metadata':{'labels':{'app':'search'}},'spec':{'containers':[
            {'name':'api','image':self.image,'env':[],'envFrom':[{'secretRef':{'name':'search-access'}}]}]}}}}
        self.values=dict(zip(wiring.ENV_KEYS,(wiring.ENDPOINT,self.namespace,self.image)))
        self.commands=[];self.environment_reads=0
        self.folder=TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(wiring,'STATE',Path(self.folder.name)))
        self.stack.enter_context(patch.object(wiring,'guard'))
        self.apply=self.stack.enter_context(patch.object(wiring,'apply'))
        self.command=self.stack.enter_context(patch.object(wiring,'k',side_effect=self.kubectl))

    def kubectl(self,*args,**kwargs):
        self.commands.append(args)
        value={}
        if args[0]=='exec' and args[1]=='deployment/lab-control':
            return SimpleNamespace(returncode=0,stdout='0')
        if args[:2]==('get','configmap/frozen-definition'):
            value={'data':{'definition.json':json.dumps(self.definition)}}
        elif args[:2]==('get','deployment/search'):value=self.deployment
        elif args[:2]==('get','secret/search-access'):value=self.secret
        elif args[:2]==('get','networkpolicy/search-telemetry-egress'):
            return SimpleNamespace(returncode=1,stdout='',stderr='NotFound')
        elif args[0]=='exec' and args[1]=='deployment/search' and 'json,os' in args[-1]:
            self.environment_reads+=1;value={} if self.environment_reads==1 else self.values
        return SimpleNamespace(returncode=0,stdout=json.dumps(value))

    def test_enable_merges_only_telemetry_settings_and_records_identity(self):
        receipt=wiring.enable(self.namespace,self.fingerprint)
        patches=[json.loads(a[-1]) for a in self.commands if a[:2]==('patch','secret/search-access')]
        self.assertEqual(set(patches[0]['data']),set(wiring.ENV_KEYS))
        self.assertNotIn('private-credential',json.dumps(patches)+json.dumps(receipt))
        self.assertEqual(receipt['fingerprint'],self.fingerprint)
        self.assertFalse(receipt['historical_backfill'])
        self.assertIn(('rollout','restart','deployment/search','-n',self.namespace),self.commands)
        self.assertEqual(self.apply.call_args.args[0],wiring.policy(self.namespace))

    def test_already_active_configuration_needs_no_restart(self):
        self.environment_reads=1
        self.secret['data'].update({k:base64.b64encode(v.encode()).decode() for k,v in self.values.items()})
        wiring.enable(self.namespace,self.fingerprint)
        self.assertFalse(any(a[:2]==('rollout','restart') for a in self.commands))

    def test_changed_release_and_explicit_chart_overrides_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'selected frozen release'):
            wiring.enable(self.namespace,'c'*64)
        self.deployment['spec']['template']['spec']['containers'][0]['env']=[{'name':wiring.ENV_KEYS[0],'value':'http://different:4318'}]
        with self.assertRaisesRegex(ValueError,'different telemetry settings'):
            wiring.enable(self.namespace,self.fingerprint)
        self.apply.assert_not_called()

    def test_active_evaluation_prevents_any_configuration_change(self):
        self.command.side_effect=lambda *a,**k:SimpleNamespace(returncode=0,stdout='1')
        with self.assertRaisesRegex(RuntimeError,'active evaluations'):
            wiring.enable(self.namespace,self.fingerprint)
        self.apply.assert_not_called()
