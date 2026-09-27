"""Shared helpers for explicitly scoped, local research commands."""
import json,os,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
STATE=ROOT/'.lab'; EVIDENCE=STATE/'evidence'
KUBE=['kubectl','--kubeconfig',str(STATE/'kubeconfig.yaml')]
_bundled_helm=STATE/'tools'/('helm.exe' if os.name=='nt' else 'helm')
HELM=str(_bundled_helm) if _bundled_helm.exists() else shutil.which('helm') or 'helm'
def run(args,body=None,check=True):
    r=subprocess.run(args,input=body,text=True,encoding='utf-8',capture_output=True,cwd=ROOT)
    if check and r.returncode:raise RuntimeError(f'{args[0]} failed: {r.stderr[-2500:]}')
    return r

def k(*args,body=None,check=True):return run(KUBE+list(args),body=None if body is None else json.dumps(body),check=check)
def guard():
    assert k('config','current-context').stdout.strip()=='k3d-relevance-lab','Wrong cluster'
def apply(obj):return k('apply','-f','-',body=obj)
def record(name,value):
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    (EVIDENCE/(name+'.json')).write_text(json.dumps(value,indent=2),encoding='utf-8')
