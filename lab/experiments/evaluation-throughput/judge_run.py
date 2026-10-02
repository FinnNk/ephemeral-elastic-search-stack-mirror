"""Clone the million judgement API with an empty cache, retaining its model pin."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'lab'), str(Path(__file__).parent)]
from common import STATE, apply, guard, k
from compare_search import immutable_blob
from blob_config import signed_read_url
from datetime import datetime, timedelta, timezone
from run import Experiment, IMAGE


def prepare(instance):
    guard()
    namespace = instance.namespace
    resource = json.loads(k('get','deployment/judgement-service-million','-n','lab-models','-o','json').stdout)
    spec = copy.deepcopy(resource['spec']['template']['spec'])
    spec.pop('serviceAccountName',None)
    spec.pop('serviceAccount',None)
    spec['imagePullSecrets'] = [{'name': 'nexus-read'}]
    spec['nodeSelector'] = {'kubernetes.io/hostname': 'k3d-relevance-lab-agent-0'}
    spec['volumes'] = [{**volume} if volume['name'] != 'state' else {'name': 'state', 'emptyDir': {}}
                       for volume in spec['volumes']]
    for name in ('judgement-blob', 'nexus-read'):
        secret = json.loads(k('get','secret/'+name,'-n','lab-models','-o','json').stdout)
        apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':name,'namespace':namespace},
               'type':secret['type'],'data':secret['data']})
    config = json.loads(k('get','configmap/judgement-model-pin','-n','lab-models','-o','json').stdout)
    apply({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'judgement-model-pin','namespace':namespace},
           'data':config['data']})
    apply({'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':'judge','namespace':namespace},
        'spec':{'replicas':1,'selector':{'matchLabels':{'experiment-role':'judge'}},
            'template':{'metadata':{'labels':{'experiment-role':'judge'}},'spec':spec}}})
    apply({'apiVersion':'v1','kind':'Service','metadata':{'name':'judge','namespace':namespace},
        'spec':{'selector':{'experiment-role':'judge'},'ports':[{'port':18086,'targetPort':18086}]}})
    k('rollout','status','deployment/judge','-n',namespace,'--timeout=300s')
    rows = [json.loads(line) for line in (instance.directory/'ledger.jsonl').read_text().splitlines()]
    reference = next(row for row in rows if row['label'].startswith('transport-screen') and not row['errors'])
    captured = json.loads(gzip.decompress((instance.directory/(reference['run_id']+'.json.gz')).read_bytes()))
    pairs = {}
    for row in captured['observations']:
        for answer in row['results'].values():
            for product_id in answer['ids']:
                pairs[(row['query_id'],product_id)] = {'query_id':row['query_id'],'product_id':product_id,
                                                      'request':row['request']}
    # Source lookup is already performed by normal prepare(); resolve only its gaps.
    known = {(row['query_id'],row['product_id']) for row in
             (json.loads(line) for line in (STATE/'releases/retail-gb-1m-v1/judgements.jsonl').read_bytes().splitlines())}
    needed = {key:value for key,value in pairs.items() if key not in known}
    ids = {key[1] for key in needed}
    selection_started = time.monotonic()
    products = {}
    with gzip.open(STATE/'releases/retail-gb-1m-v1/products.jsonl.gz','rt',encoding='utf-8') as stream:
        for line in stream:
            product = json.loads(line)
            if product['product_id'] in ids:
                products[product['product_id']] = product
    product_selection_seconds = time.monotonic()-selection_started
    context = json.loads(k('exec','deployment/judge','-n',namespace,'--','cat','/inputs/context.json').stdout)
    model = json.loads(config['data']['model.json'])
    pack = {'context':context,'model':model,'pairs':[{**pair,'product':products[pair['product_id']]}
                                                   for key,pair in sorted(needed.items())]}
    payload = gzip.compress(json.dumps(pack,sort_keys=True).encode(),mtime=0)
    digest = hashlib.sha256(payload).hexdigest()
    blob = 'evaluation-throughput/'+digest+'-judgement-pack.json.gz'
    immutable_blob('runs',blob,payload)
    record = {'pack_sha256':digest,'pack_blob':'runs/'+blob,'pairs':len(needed),
        'source_known_pairs':len(pairs)-len(needed),'product_selection_seconds':product_selection_seconds,
        'source_observation_run':reference['run_id'],'model':model,
        'url':f'http://judge.{namespace}.svc.cluster.local:18086'}
    (instance.directory/'judgement-context.json').write_text(json.dumps(record,sort_keys=True),encoding='utf-8')
    print(json.dumps(record),flush=True)


def capture(instance,concurrency,label):
    setup = json.loads((instance.directory/'judgement-context.json').read_bytes())
    blob = setup['pack_blob'].removeprefix('runs/')
    spec = {**setup,'pack_url':signed_read_url(blob,datetime.now(timezone.utc)+timedelta(minutes=60),container='runs'),'concurrency':concurrency}
    short = uuid.uuid4().hex[:10]
    config_name,job_name = 'judge-input-'+short,'judge-capture-'+short
    script = Path(__file__).with_name('judge_worker.py').read_text(encoding='utf-8')
    apply({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':config_name,'namespace':instance.namespace},
        'data':{'specification.json':json.dumps(spec),'judge_worker.py':script}})
    job = {'apiVersion':'batch/v1','kind':'Job','metadata':{'name':job_name,'namespace':instance.namespace},
        'spec':{'backoffLimit':0,'activeDeadlineSeconds':300,'template':{'spec':{'restartPolicy':'Never',
        'automountServiceAccountToken':False,'nodeSelector':{'kubernetes.io/hostname':'k3d-relevance-lab-server-0'},
        'containers':[{'name':'judge-client','image':IMAGE,'imagePullPolicy':'Never',
            'command':['python','/input/judge_worker.py'],'resources':instance.metadata['worker_resources'],
            'volumeMounts':[{'name':'input','mountPath':'/input','readOnly':True}]}],
        'volumes':[{'name':'input','configMap':{'name':config_name}}]}}}}
    started = time.monotonic()
    try:
        apply(job)
        k('wait','--for=condition=complete','job/'+job_name,'-n',instance.namespace,'--timeout=300s')
        value = json.loads(k('logs','job/'+job_name,'-n',instance.namespace).stdout)
        value['job_seconds'] = time.monotonic()-started
        value['label'],value['run_id'] = label,short
        with (instance.directory/'judgement-ledger.jsonl').open('a',encoding='utf-8') as handle:
            handle.write(json.dumps(value,sort_keys=True)+'\n')
        print(json.dumps(value),flush=True)
        return value
    finally:
        k('delete','job/'+job_name,'-n',instance.namespace,'--ignore-not-found',check=False)
        k('delete','configmap/'+config_name,'-n',instance.namespace,'--ignore-not-found',check=False)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','capture'))
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--concurrency',type=int,choices=(1,2,4),default=1)
    parser.add_argument('--label',default='screen')
    args=parser.parse_args()
    instance=Experiment(args.directory)
    if args.command=='prepare':prepare(instance)
    else:capture(instance,args.concurrency,args.label)
