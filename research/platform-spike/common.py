"""Shared helpers for explicitly scoped, local research commands."""
import json,os,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
STATE=Path(os.environ.get('LAB_STATE_DIR', str(ROOT/'.lab')))
EVIDENCE=STATE/'evidence'
IN_CLUSTER=os.environ.get('LAB_IN_CLUSTER')=='1'
KUBE=['kubectl'] if IN_CLUSTER else ['kubectl','--kubeconfig',str(STATE/'kubeconfig.yaml')]
_bundled_helm=STATE/'tools'/('helm.exe' if os.name=='nt' else 'helm')
HELM=str(_bundled_helm) if _bundled_helm.exists() else shutil.which('helm') or 'helm'
def run(args,body=None,check=True):
    r=subprocess.run(args,input=body,text=True,encoding='utf-8',capture_output=True,cwd=ROOT)
    if check and r.returncode:raise RuntimeError(f'{args[0]} failed: {r.stderr[-2500:]}')
    return r

def k(*args,body=None,check=True):return run(KUBE+list(args),body=None if body is None else json.dumps(body),check=check)
def guard():
    if IN_CLUSTER:
        expected=os.environ.get('LAB_CLUSTER_UID')
        if not expected:
            raise RuntimeError('LAB_CLUSTER_UID is required inside the cluster.')
        observed=json.loads(k('get','namespace','kube-system','-o','json').stdout)['metadata']['uid']
        if observed!=expected:
            raise RuntimeError('Control Pod is connected to a different cluster.')
    else:
        assert k('config','current-context').stdout.strip()=='k3d-relevance-lab','Wrong cluster'
def apply(obj):
    if IN_CLUSTER and obj.get('kind')=='Namespace':
        name=obj['metadata']['name']
        if not name.startswith(('lab-','retail-','spike-')):
            raise RuntimeError('Control runtime cannot bind a non-lab namespace.')
        existing=k('get','namespace',name,'-o','json',check=False)
        if existing.returncode:
            result=k('create','-f','-',body=obj)
            existing=k('get','namespace',name,'-o','json')
        else:
            result=existing
        labels=json.loads(existing.stdout)['metadata'].get('labels',{})
        for key,value in obj['metadata'].get('labels',{}).items():
            if labels.get(key)!=value:
                raise RuntimeError('Existing lab namespace has different labels: '+name)
        k('apply','-f','-',body={'apiVersion':'rbac.authorization.k8s.io/v1',
            'kind':'RoleBinding','metadata':{'name':'lab-control-runtime','namespace':name},
            'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'ClusterRole',
                       'name':'lab-control-environment'},
            'subjects':[{'kind':'ServiceAccount','name':'lab-control',
                         'namespace':'lab-control'}]})
        return result
    return k('apply','-f','-',body=obj)
def record(name,value):
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    (EVIDENCE/(name+'.json')).write_text(json.dumps(value,indent=2),encoding='utf-8')
