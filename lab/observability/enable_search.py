"""Enable existing Search API instrumentation on a legacy delivery environment."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import STATE, apply, guard, k

ENDPOINT = 'http://lab-otel-gateway.lab-observability.svc.cluster.local:4318'
ENV_KEYS = ('OTEL_EXPORTER_OTLP_ENDPOINT', 'LAB_DEPLOYMENT_TIER', 'LAB_RELEASE_SHA')
OWNER = 'search-observability'


def policy(namespace):
    return {'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy',
        'metadata':{'name':'search-telemetry-egress','namespace':namespace,'labels':{'lab/owner':OWNER}},
        'spec':{'podSelector':{'matchLabels':{'app':'search'}},'policyTypes':['Egress'],
            'egress':[{'to':[{'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':'lab-observability'}},
                'podSelector':{'matchLabels':{'app':'lab-otel-gateway'}}}],
                'ports':[{'port':4318,'protocol':'TCP'}]}]}}


def enable(namespace, fingerprint):
    """Record and enable telemetry wiring without rewriting frozen release fields."""
    if not re.fullmatch(r'lab-delivery-(?:integration|staging|run-[1-9][0-9]*-[a-f0-9]{8})',namespace) or \
            not re.fullmatch('[0-9a-f]{64}',fingerprint):
        raise ValueError('Choose an Integration/Staging or delivery-preview namespace and its exact fingerprint.')
    guard()
    idle = k('exec','deployment/lab-control','-n','lab-control','-c','api','--','python','-c',
        "import sqlite3; from delivery_operations import Operations; "
        "c=sqlite3.connect('/state/lifecycle.sqlite3'); "
        "print(len(Operations().active())+c.execute(\"select count(*) from comparisons where state='running'\").fetchone()[0])")
    if idle.stdout.strip() != '0':
        raise RuntimeError('Wait for active evaluations and comparisons to finish before enabling telemetry.')
    definition=json.loads(json.loads(k('get','configmap/frozen-definition','-n',namespace,'-o','json').stdout)['data']['definition.json'])
    deployment=json.loads(k('get','deployment/search','-n',namespace,'-o','json').stdout)
    containers=deployment['spec']['template']['spec']['containers']
    api=next(c for c in containers if c['name']=='api')
    if definition['fingerprint'] != fingerprint or api['image'] != definition['image'] or \
            deployment['spec']['template']['metadata'].get('labels',{}).get('app') != 'search':
        raise ValueError('The API does not match the selected frozen release.')
    values=dict(zip(ENV_KEYS,(ENDPOINT,namespace,api['image'])))
    for entry in api.get('env',[]):
        if entry['name'] in values and entry.get('value') != values[entry['name']]:
            raise ValueError('The chart declares different telemetry settings; review those settings first.')
    k('exec','deployment/search','-n',namespace,'--','python','-c',
      "import importlib.util; assert importlib.util.find_spec('opentelemetry.sdk'); "
      "assert importlib.util.find_spec('opentelemetry.exporter.otlp.proto.http')")
    secret=json.loads(k('get','secret/search-access','-n',namespace,'-o','json').stdout)
    if not any(e.get('secretRef',{}).get('name')=='search-access' for e in api.get('envFrom',[])):
        raise ValueError('The API does not use the supported runtime configuration secret.')
    existing=k('get','networkpolicy/search-telemetry-egress','-n',namespace,'-o','json',check=False)
    if existing.returncode and 'notfound' not in existing.stderr.lower():
        raise RuntimeError('Existing telemetry policy ownership could not be checked.')
    if existing.returncode == 0 and json.loads(existing.stdout)['metadata'].get('labels',{}).get('lab/owner') != OWNER:
        raise ValueError('Telemetry policy name is owned by another installer.')
    config_sha=hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
    # Merge only these non-secret runtime settings. Do not replace credentials or
    # alter kubectl's last-applied configuration for the credential owner.
    patch={'metadata':{'annotations':{'lab/telemetry-config-sha256':config_sha}},
           'data':{key:base64.b64encode(value.encode()).decode() for key,value in values.items()}}
    changed=any(secret.get('data',{}).get(key)!=value for key,value in patch['data'].items())
    apply(policy(namespace))
    k('patch','secret/search-access','-n',namespace,'--type=merge','-p',json.dumps(patch))
    observed_code='import json,os; print(json.dumps({key:os.environ.get(key) for key in '+repr(ENV_KEYS)+'}))'
    observed=json.loads(k('exec','deployment/search','-n',namespace,'--','python','-c',observed_code).stdout)
    if observed != values:
        k('rollout','restart','deployment/search','-n',namespace)
        k('rollout','status','deployment/search','-n',namespace,'--timeout=120s')
        observed=json.loads(k('exec','deployment/search','-n',namespace,'--','python','-c',observed_code).stdout)
    if observed != values:
        raise RuntimeError('Search API telemetry settings did not become active.')
    current=json.loads(json.loads(k('get','configmap/frozen-definition','-n',namespace,'-o','json').stdout)['data']['definition.json'])
    if current != definition:
        raise RuntimeError('The frozen release changed during telemetry activation.')
    receipt={'namespace':namespace,'fingerprint':fingerprint,'image':api['image'],
        'telemetry_config':values,'telemetry_config_sha256':config_sha,'configuration_changed':changed,
        'activated_at':datetime.now(timezone.utc).isoformat(),'historical_backfill':False}
    folder=STATE/'activation-receipts';folder.mkdir(parents=True,exist_ok=True)
    (folder/(namespace+'-telemetry.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--namespace',required=True)
    parser.add_argument('--fingerprint',required=True)
    args=parser.parse_args()
    print(json.dumps(enable(args.namespace,args.fingerprint),indent=2))
