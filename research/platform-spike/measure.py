"""Measure Git-file ApplicationSet creation and deletion against real searches."""
import argparse,json,time,urllib.parse
from common import *
from environments import *
def search(name,query='running shoes'):
    code='import urllib.request; print(urllib.request.urlopen('+repr('http://search.'+name+'.svc.cluster.local:8080/search?country=GB&currency=GBP&q='+urllib.parse.quote(query))+',timeout=3).read().decode())'
    r=k('exec','search-probe','-n','platform','--','python','-c',code,check=False)
    if r.returncode:return None
    return json.loads(r.stdout)
def wait_search(name,timeout=150):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        result=search(name)
        if result and result.get('ids')==[f'p{i:06d}' for i in range(0,100,10)]:return result
        time.sleep(0.5)
    raise TimeoutError(name)
def remove(name):
    (REPO/'environments'/f'{name}.json').unlink();publish('Remove '+name)
    end=time.monotonic()+150
    while time.monotonic()<end:
        r=k('get','namespace',name,'--ignore-not-found','-o','name')
        if not r.stdout.strip():break
        time.sleep(0.5)
    else:raise TimeoutError('cleanup '+name)
    elastic('/_security/user/'+name,'DELETE');elastic('/_security/role/'+name,'DELETE')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repetitions',type=int,default=20);a=p.parse_args();guard()
    image=json.loads((EVIDENCE/'baseline-build.json').read_text())['image']
    secret=json.loads(k('get','secret','registry-read','-n','spike-baseline','-o','json').stdout)
    apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'registry-read','namespace':'platform'},'type':secret['type'],'data':secret['data']})
    apply({'apiVersion':'apps/v1','kind':'DaemonSet','metadata':{'name':'warm-image','namespace':'platform'},'spec':{'selector':{'matchLabels':{'app':'warm-image'}},'template':{'metadata':{'labels':{'app':'warm-image'}},'spec':{'imagePullSecrets':[{'name':'registry-read'}],'containers':[{'name':'warm','image':image,'command':['sleep','300'],'resources':{'requests':{'cpu':'5m','memory':'8Mi'},'limits':{'memory':'32Mi'}}}]}}}})
    k('rollout','status','daemonset/warm-image','-n','platform','--timeout=120s');k('delete','daemonset/warm-image','-n','platform','--wait=true')
    records=[]
    for i in range(a.repetitions):
        name=f'spike-measure-{i:02d}';row={'name':name};start=time.monotonic()
        try:
            provision_access(name,'spike-frozen-v1');definition=define(name,image);publish('Create '+name)
            result=wait_search(name);row.update({'create_seconds':round(time.monotonic()-start,3),'fingerprint':definition['fingerprint'],'ids':result['ids']})
            deployed=json.loads(k('get','deployment','search','-n',name,'-o','json').stdout)
            assert deployed['spec']['template']['spec']['containers'][0]['image']==image
            start=time.monotonic();remove(name);row['delete_seconds']=round(time.monotonic()-start,3);row['passed']=True
        except Exception as e:row.update({'passed':False,'error':str(e)})
        records.append(row);record('git-lifecycle-measurements',records);print(json.dumps(row),flush=True)
        if not row['passed']:raise RuntimeError(row)
