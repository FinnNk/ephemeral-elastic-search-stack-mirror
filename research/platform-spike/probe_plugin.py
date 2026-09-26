import json,secrets,sys,time
from common import *
from environments import provision_access,elastic
from measure import wait_search
guard()
existing=k('get','secret/spike-plugin-token','-n','argocd','-o','json',check=False)
token=__import__('base64').b64decode(json.loads(existing.stdout)['data']['token']).decode() if existing.returncode==0 else secrets.token_urlsafe(32)
apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'spike-plugin-token','namespace':'argocd','labels':{'app.kubernetes.io/part-of':'argocd'}},'stringData':{'token':token}})
apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'spike-plugin-token','namespace':'platform'},'stringData':{'token':token}})
apply({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'spike-plugin-source','namespace':'platform'},'data':{'plugin.py':(ROOT/'research/platform-spike/plugin.py').read_text(encoding='utf-8-sig')}})
apply({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'spike-plugin','namespace':'argocd'},'data':{'token':'$spike-plugin-token:token','baseUrl':'http://spike-plugin.platform.svc:8080','requestTimeout':'5'}})
apply({'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':'spike-plugin','namespace':'platform'},'spec':{'selector':{'matchLabels':{'app':'spike-plugin'}},'template':{'metadata':{'labels':{'app':'spike-plugin'}},'spec':{'automountServiceAccountToken':False,'containers':[{'name':'plugin','image':'python:3.13.7-alpine3.22','command':['python','/source/plugin.py'],'env':[{'name':'TOKEN','valueFrom':{'secretKeyRef':{'name':'spike-plugin-token','key':'token'}}}],'volumeMounts':[{'name':'source','mountPath':'/source'},{'name':'state','mountPath':'/state'}],'resources':{'requests':{'cpu':'10m','memory':'24Mi'},'limits':{'memory':'96Mi'}}}],'volumes':[{'name':'source','configMap':{'name':'spike-plugin-source'}},{'name':'state','emptyDir':{}}]}}}})
apply({'apiVersion':'v1','kind':'Service','metadata':{'name':'spike-plugin','namespace':'platform'},'spec':{'selector':{'app':'spike-plugin'},'ports':[{'port':8080}]}})
k('rollout','status','deployment/spike-plugin','-n','platform','--timeout=120s')
def state(value):
    run(KUBE+['exec','-i','deployment/spike-plugin','-n','platform','--','sh','-c','cat > /state/desired.json'],body=json.dumps(value))
    k('annotate','applicationset/spike-plugin','-n','argocd','argocd.argoproj.io/application-set-refresh=true','--overwrite',check=False)
state({'environments':[]})
appset=json.loads(k('get','applicationset/search-environments','-n','argocd','-o','json').stdout)
obj={'apiVersion':appset['apiVersion'],'kind':'ApplicationSet','metadata':{'name':'spike-plugin','namespace':'argocd'},'spec':appset['spec']}
obj['spec']['generators']=[{'plugin':{'configMapRef':{'name':'spike-plugin'},'requeueAfterSeconds':5}}]
apply(obj)
baseline=json.loads((EVIDENCE/'baseline-build.json').read_text());definition=json.loads((STATE/'state-source/environments/spike-baseline.json').read_text())
entry={'environment':'spike-plugin-candidate','image':baseline['image'],'index':'spike-frozen-v1','fingerprint':definition['fingerprint']}
start=time.monotonic();provision_access(entry['environment'],entry['index']);state({'environments':[entry]});wait_search(entry['environment']);created=round(time.monotonic()-start,3)
state({'fail':True})
# Wait for an observed generator error, rather than assuming an outage was exercised.
for i in range(30):
    conditions=json.loads(k('get','applicationset/spike-plugin','-n','argocd','-o','json').stdout)['status']['conditions']
    if any(c['type']=='ErrorOccurred' and c['status']=='True' for c in conditions):break
    time.sleep(1)
else:raise AssertionError('Plugin outage not observed')
assert wait_search(entry['environment'])['ids']
state({'environments':[entry]})
recovery_start=time.monotonic()
for i in range(360):
    conditions=json.loads(k('get','applicationset/spike-plugin','-n','argocd','-o','json').stdout)['status']['conditions']
    if any(c['type']=='ErrorOccurred' and c['status']=='False' for c in conditions):break
    time.sleep(1)
else:raise AssertionError('Plugin generator did not recover')
recovery_seconds=round(time.monotonic()-recovery_start,3)
wait_search(entry['environment'])
start=time.monotonic();state({'environments':[]})
for i in range(150):
    if not k('get','namespace',entry['environment'],'--ignore-not-found','-o','name').stdout.strip():break
    time.sleep(1)
else:raise AssertionError('Plugin removal failed')
elastic('/_security/user/'+entry['environment'],'DELETE');elastic('/_security/role/'+entry['environment'],'DELETE')
record('plugin-generator',{'create_seconds':created,'delete_seconds':round(time.monotonic()-start,3),'outage_observed':True,'outage_preserved_workloads':True,'explicit_empty_removed_namespace':True,'sample_size':1,'generator_recovery_seconds':recovery_seconds,'earlier_probe':'Explicit removal after an outage exceeded 150 seconds; namespace was subsequently removed. Recovery now waits for generator success.','state_backend':'spike file; not production metadata storage'})
print('Plugin create/outage/recovery/delete probe passed.',flush=True)
