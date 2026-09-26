import json,os,subprocess,time
from common import *
from data_contract import DEMO_KEY
guard()
apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'snapshot-azure','namespace':'platform'},'stringData':{'azure.client.lab.account':'devstoreaccount1','azure.client.lab.key':DEMO_KEY}})
obj=json.loads(k('get','elasticsearch/shared','-n','platform','-o','json').stdout)
spec=obj['spec'];spec['version']='9.5.3';spec['secureSettings']=[{'secretName':'snapshot-azure'}]
spec['nodeSets'][0]['config'].update({'azure.client.lab.endpoint':'http://floci.platform.svc:4577/devstoreaccount1','azure.client.lab.timeout':'5s','azure.client.lab.max_retries':0})
spec['nodeSets'][0]['podTemplate']['spec']['nodeSelector']={'kubernetes.io/hostname':'k3d-relevance-lab-agent-0'}
start=time.monotonic();apply({'apiVersion':obj['apiVersion'],'kind':obj['kind'],'metadata':{'name':'version-experiment','namespace':'platform'},'spec':spec})
for i in range(180):
    es=json.loads(k('get','elasticsearch/version-experiment','-n','platform','-o','json').stdout)
    if es.get('status',{}).get('health')=='green':break
    time.sleep(1)
else:raise TimeoutError('Separate engine did not become ready')
record('separate-engine',{'version':'9.5.3','main_cluster_version':'9.5.4','seconds':round(time.monotonic()-start,3),'health':es['status']['health']})
log=open(STATE/'version-forward.log','a');proc=subprocess.Popen(KUBE+['-n','platform','port-forward','svc/version-experiment-es-http','19201:9200','--address','127.0.0.1'],stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0);(STATE/'version-forward.pid').write_text(str(proc.pid))
print('Separate ECK engine version is ready for the snapshot compatibility probe.',flush=True)
