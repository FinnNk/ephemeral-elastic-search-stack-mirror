"""Compare the frozen baseline with a successful Gitea PR build, then recreate it."""
import argparse, hashlib, json, time
from common import *
from environments import *
from measure import search, wait_search, remove
from data_contract import BlobServiceClient, DEMO_KEY, ResourceExistsError

parser=argparse.ArgumentParser()
parser.add_argument('--run', type=int, required=True, help='Successful Gitea candidate Actions run ID')
args=parser.parse_args()
guard()
build=build_record(args.run)
if (EVIDENCE/'candidate-build.json').exists():
    previous=json.loads((EVIDENCE/'candidate-build.json').read_text())
    if previous['image'] != build['image']: record('candidate-build-before-retention-fix', previous)
record('candidate-build', build)
if (REPO/'environments/spike-candidate.json').exists():
    start=time.monotonic();remove('spike-candidate')
    record('failed-environment-cleanup', {'reason':'ImagePullBackOff: overwritten tag left the original digest unavailable',
        'namespace_removed':True, 'credential_revoked':True, 'seconds':round(time.monotonic()-start,3)})
name='spike-candidate-retained'
start=time.monotonic()
provision_access(name,'spike-frozen-v1'); definition=define(name,build['image']);publish('Create retained candidate digest')
wait_search(name);create_seconds=round(time.monotonic()-start,3)
queries=['running shoes','cotton shirt','ceramic mug','desk lamp','garden gloves','wireless headphones',
         'linen towel','wooden toy','steel pan','leather bag','trainers','unfindableitem']
rows=[]
for query in queries:
    baseline=search('spike-baseline',query);candidate=search(name,query)
    assert baseline is not None and candidate is not None
    rows.append({'query':query,'baseline':baseline['ids'],'candidate':candidate['ids'],'equal':baseline['ids']==candidate['ids']})
assert [r['query'] for r in rows if not r['equal']]==['trainers']
assert rows[-2]['baseline']==[] and len(rows[-2]['candidate'])==10
start=time.monotonic();remove(name);delete_seconds=round(time.monotonic()-start,3)
start=time.monotonic();provision_access(name,'spike-frozen-v1');recreated=define(name,build['image']);publish('Recreate retained candidate definition')
wait_search(name);recreate_seconds=round(time.monotonic()-start,3)
assert recreated['fingerprint']==definition['fingerprint']
assert all(search(name,row['query'])['ids']==row['candidate'] for row in rows)
result={'baseline_build':json.loads((EVIDENCE/'baseline-build.json').read_text()),'candidate_build':build,
        'candidate_definition':definition,'queries':rows,'same_fingerprint_and_results_after_recreation':True,
        'create_seconds':create_seconds,'delete_seconds':delete_seconds,'recreate_seconds':recreate_seconds,'sample_size':1}
client=BlobServiceClient(account_url='http://127.0.0.1:14577/devstoreaccount1',credential=DEMO_KEY)
try:client.create_container('runs')
except ResourceExistsError:pass
payload=json.dumps(result,sort_keys=True).encode();digest=hashlib.sha256(payload).hexdigest()
blob=client.get_blob_client('runs',digest+'/api-comparison.json');blob.upload_blob(payload,overwrite=False)
assert blob.download_blob().readall()==payload
result['report_blob']='runs/'+digest+'/api-comparison.json'
record('api-comparison',result)
print('12 API queries compared; only trainers changed; deleted and recreated candidate returned identical IDs.',flush=True)
