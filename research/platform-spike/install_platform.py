import json,secrets,time,urllib.request
from common import *
guard()
apply({'apiVersion':'v1','kind':'Namespace','metadata':{'name':'platform'}})
credentials=STATE/'credentials.json'
if not credentials.exists():credentials.write_text(json.dumps({'username':'lab-admin','password':secrets.token_urlsafe(32)}),encoding='utf-8')
c=json.loads(credentials.read_text())
apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'gitea-admin','namespace':'platform'},'stringData':{key:c[key] for key in ['username','password']}})
apply({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'coredns-custom','namespace':'kube-system'},'data':{'gitea.override':'rewrite name exact gitea.localhost gitea-http.platform.svc.cluster.local\n'}})
k('rollout','restart','deployment/coredns','-n','kube-system')
start=time.monotonic()
r=run([HELM,'upgrade','--install','gitea','gitea-charts/gitea','--version','12.7.0','--namespace','platform','--kubeconfig',str(STATE/'kubeconfig.yaml'),'-f','research/platform-spike/gitea-values.yaml','--wait','--timeout','5m'])
record('gitea-install',{'seconds':round(time.monotonic()-start,3),'chart':'12.7.0','application':'28.0.0'})
print('Gitea installed',flush=True)
for namespace,url in [('argocd','https://raw.githubusercontent.com/argoproj/argo-cd/v3.5.3/manifests/install.yaml'),('elastic-system','https://download.elastic.co/downloads/eck/3.5.0/crds.yaml'),('elastic-system','https://download.elastic.co/downloads/eck/3.5.0/operator.yaml')]:
    apply({'apiVersion':'v1','kind':'Namespace','metadata':{'name':namespace}})
    with urllib.request.urlopen(url,timeout=30) as response:data=response.read().decode()
    r=run(KUBE+['apply','--server-side','-n',namespace,'-f','-'],body=data)
    print('Applied '+url,flush=True)
