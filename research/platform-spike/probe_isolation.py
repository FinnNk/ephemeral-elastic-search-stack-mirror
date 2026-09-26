"""Run the same cross-node ingress/RBAC probe on an explicitly named lab cluster."""
import argparse,json,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--kubeconfig',required=True);p.add_argument('--name',choices=['k3d','kind'],required=True);a=p.parse_args()
expected={'k3d':'k3d-relevance-lab','kind':'kind-relevance-kind'}[a.name]
def k(*args,body=None,check=True):
    r=subprocess.run(['kubectl','--kubeconfig',a.kubeconfig,*args],input=None if body is None else json.dumps(body),text=True,capture_output=True)
    if check and r.returncode:raise RuntimeError(r.stderr)
    return r
assert k('config','current-context').stdout.strip()==expected
nodes=json.loads(k('get','nodes','-o','json').stdout)['items'];names=[n['metadata']['name'] for n in nodes]
server=next(n for n in names if 'agent' in n or 'worker' in n);client=next(n for n in names if n!=server)
items=[]
for ns in ['spike-net-a','spike-net-b']:
    items.append({'apiVersion':'v1','kind':'Namespace','metadata':{'name':ns,'labels':{'spike':'network-probe'}}})
    items.append({'apiVersion':'v1','kind':'Pod','metadata':{'name':'client','namespace':ns},'spec':{'nodeName':client,'containers':[{'name':'client','image':'busybox:1.37.0','command':['sleep','3600']}],'restartPolicy':'Never'}})
items += [{'apiVersion':'v1','kind':'Pod','metadata':{'name':'server','namespace':'spike-net-a','labels':{'app':'server'}},'spec':{'nodeName':server,'containers':[{'name':'server','image':'nginx:1.29.1-alpine','ports':[{'containerPort':80}]}]}}, {'apiVersion':'v1','kind':'Service','metadata':{'name':'server','namespace':'spike-net-a'},'spec':{'selector':{'app':'server'},'ports':[{'port':80}]}}]
k('apply','-f','-',body={'apiVersion':'v1','kind':'List','items':items})
for ns in ['spike-net-a','spike-net-b']:k('wait','--for=condition=Ready','pod','--all','-n',ns,'--timeout=120s')
service=json.loads(k('get','svc','server','-n','spike-net-a','-o','json').stdout)['spec']['clusterIP']
def probe(ns):
    r=k('exec','-n',ns,'client','--','wget','-q','-T','3','-O','/dev/null','http://'+service,check=False)
    return {'allowed':r.returncode==0,'exit_code':r.returncode,'detail':r.stderr.strip()}
results={'cluster':a.name,'nodes':{'client':client,'server':server},'before':{n:probe(n) for n in ['spike-net-a','spike-net-b']}}
assert all(r['allowed'] for r in results['before'].values()),results
policy={'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':{'name':'server-access','namespace':'spike-net-a'},'spec':{'podSelector':{'matchLabels':{'app':'server'}},'policyTypes':['Ingress'],'ingress':[]}}
k('apply','-f','-',body=policy);time.sleep(3)
results['deny_all']={n:probe(n) for n in ['spike-net-a','spike-net-b']}
policy['spec']['ingress']=[{'from':[{'podSelector':{}}],'ports':[{'port':80,'protocol':'TCP'}]}]
k('apply','-f','-',body=policy);time.sleep(3)
results['same_namespace']={n:probe(n) for n in ['spike-net-a','spike-net-b']}
results['rbac_cross_namespace']=k('auth','can-i','get','secrets','-n','spike-net-b','--as=system:serviceaccount:spike-net-a:default',check=False).stdout.strip()
results['network_policy_enforced']=not any(r['allowed'] for r in results['deny_all'].values()) and results['same_namespace']['spike-net-a']['allowed'] and not results['same_namespace']['spike-net-b']['allowed']
Path('.lab/evidence/'+a.name+'-isolation.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results))
k('delete','namespace','spike-net-a','spike-net-b','--wait=true','--timeout=90s')
