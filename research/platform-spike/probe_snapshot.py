"""Exercise snapshot/restore against Floci on the separate engine-version cluster."""
import hashlib,json,time
from common import *
from data_contract import elastic,ResourceExistsError
from blob_config import service,settings
guard()
client=service()
try:client.create_container('snapshots')
except ResourceExistsError:pass
manifest=json.loads((EVIDENCE/'dataset.json').read_text());data=client.get_blob_client(settings()[1],manifest['sha256']+'/products.jsonl').download_blob().readall();assert hashlib.sha256(data).hexdigest()==manifest['sha256']
def es(path,method='GET',body=None,raw=False):return elastic(path,method,body,raw=raw,cluster='version-experiment',port=19201)
index='spike-version-v1';es('/'+index,'PUT',{'settings':{'number_of_replicas':0},'mappings':{'properties':{'product_id':{'type':'keyword'},'title':{'type':'text'}}}})
lines=[]
for line in data.decode().splitlines():
    p=json.loads(line);lines.extend([json.dumps({'index':{'_id':p['product_id']}}),line])
start=time.monotonic();bulk=es('/'+index+'/_bulk?refresh=true','POST','\n'.join(lines)+'\n',raw=True);assert not bulk['errors'];bulk_seconds=round(time.monotonic()-start,3)
results={'engine':'9.5.3','dataset_sha256':manifest['sha256'],'bulk_seconds':bulk_seconds}
try:
    results['repository']=es('/_snapshot/floci-spike','PUT',{'type':'azure','settings':{'client':'lab','container':'snapshots','base_path':'version-spike'}})
    results['verification']=es('/_snapshot/floci-spike/_verify','POST')
    start=time.monotonic();snapshot=es('/_snapshot/floci-spike/frozen-v1?wait_for_completion=true','PUT',{'indices':index,'include_global_state':False});results['snapshot_seconds']=round(time.monotonic()-start,3);results['snapshot_state']=snapshot['snapshot']['state'];assert results['snapshot_state']=='SUCCESS'
    start=time.monotonic();results['restore']=es('/_snapshot/floci-spike/frozen-v1/_restore?wait_for_completion=true','POST',{'indices':index,'include_global_state':False,'rename_pattern':index,'rename_replacement':'spike-restored-v1'})
    results['restore_seconds']=round(time.monotonic()-start,3)
    es('/spike-restored-v1/_refresh','POST');results['restored_count']=es('/spike-restored-v1/_count')['count'];assert results['restored_count']==10000
    body={'size':10,'query':{'match':{'title':'running shoes'}},'sort':[{'_score':'desc'},{'product_id':'asc'}]}
    ids=lambda name:[h['_id'] for h in es('/'+name+'/_search','POST',body)['hits']['hits']]
    assert ids(index)==ids('spike-restored-v1');results['identical_top_10']=True
except Exception as e:
    results['error']=str(e)
    if hasattr(e,'read'):results['error_body']=e.read().decode()[:3000]
record('snapshot-compatibility',results);print(json.dumps(results),flush=True)
