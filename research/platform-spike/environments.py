"""Publish pinned environments through Gitea and Argo CD for measured probes."""
import base64,hashlib,json,os,re,secrets,shutil,subprocess,time,urllib.request
from common import *
from gitea import BASE as GITEA_API_URL, api
from data_contract import elastic
REPO=STATE/'state-source'
GITEA_GIT_URL=os.environ.get('LAB_GITEA_GIT_URL','http://127.0.0.1:31800').rstrip('/')
def git(*args,cwd=REPO):
    c=json.loads((STATE/'credentials.json').read_text())
    auth=base64.b64encode(('elastic-agent:'+c['build_token']).encode()).decode()
    env=os.environ.copy();env.update({'GIT_CONFIG_COUNT':'2','GIT_CONFIG_KEY_0':'http.extraHeader','GIT_CONFIG_VALUE_0':'Authorization: Basic '+auth,'GIT_CONFIG_KEY_1':'credential.helper','GIT_CONFIG_VALUE_1':''})
    r=subprocess.run(['git','-C',str(cwd),'-c','user.name=elastic-agent','-c','user.email=elastic-agent@lab.invalid',*args],env=env,text=True,encoding='utf-8',capture_output=True)
    if r.returncode:raise RuntimeError(r.stderr.replace(auth,'[redacted]'))
    return r.stdout.strip()
def publish(message):
    git('add','.');git('commit','-m',message);git('push','origin','main')
    k('annotate','applicationset/search-environments','-n','argocd','argocd.argoproj.io/application-set-refresh=true','--overwrite',check=False)
def build_record(run_id):
    runinfo=api(f'/repos/elastic-agent/search-spike/actions/runs/{run_id}')
    assert runinfo['conclusion']=='success'
    job=api(f'/repos/elastic-agent/search-spike/actions/runs/{run_id}/jobs')['jobs'][0]
    c=json.loads((STATE/'credentials.json').read_text())['agent'];auth=base64.b64encode((c['username']+':'+c['password']).encode()).decode()
    req=urllib.request.Request(f'{GITEA_API_URL}/repos/elastic-agent/search-spike/actions/jobs/{job["id"]}/logs',headers={'Authorization':'Basic '+auth})
    with urllib.request.urlopen(req) as r:log=r.read().decode()
    image=re.findall(r'gitea.localhost:31800/elastic-agent/search-spike@sha256:[a-f0-9]{64}',log)[-1]
    return {'run':run_id,'source_sha':runinfo['head_sha'],'image':image,'started_at':job['started_at'],'completed_at':job['completed_at']}
def provision_access(name,index,read_indices=None):
    apply({'apiVersion':'v1','kind':'Namespace','metadata':{'name':name,'labels':{'lab':'search-spike'}}})
    existing=k('get','secret/search-access','-n',name,'-o','json',check=False)
    password=(base64.b64decode(json.loads(existing.stdout)['data']['ES_PASSWORD']).decode()
              if existing.returncode==0 else secrets.token_urlsafe(24))
    elastic('/_security/role/'+name,'PUT',{'indices':[{'names':read_indices or [index],'privileges':['read','view_index_metadata']}]})
    elastic('/_security/user/'+name,'PUT',{'password':password,'roles':[name]})
    apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'search-access','namespace':name},'stringData':{'ES_USER':name,'ES_PASSWORD':password}})
    cert=json.loads(k('get','secret','shared-es-http-certs-public','-n','platform','-o','json').stdout)['data']
    apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'es-ca','namespace':name},'data':cert})
    c=json.loads((STATE/'credentials.json').read_text())
    if 'read_token' not in c:
        c['read_token']=api('/users/elastic-agent/tokens','POST',{'name':'spike-image-read','scopes':['read:package']})['sha1']
        (STATE/'credentials.json').write_text(json.dumps(c),encoding='utf-8')
    docker={'auths':{'gitea.localhost:31800':{'auth':base64.b64encode(('elastic-agent:'+c['read_token']).encode()).decode()}}}
    apply({'apiVersion':'v1','kind':'Secret','type':'kubernetes.io/dockerconfigjson','metadata':{'name':'registry-read','namespace':name},'stringData':{'.dockerconfigjson':json.dumps(docker)}})
def define(name,image,index='spike-frozen-v1',dataset_sha256=None,mapping_sha256=None,
           index_recipe_sha256=None):
    if dataset_sha256 is None:
        dataset=json.loads((EVIDENCE/'dataset.json').read_text())
        dataset_sha256=dataset['sha256']
    definition={'image':image,'index':index,'dataset_sha256':dataset_sha256,'engine':'9.5.4'}
    if mapping_sha256 is not None:definition['mapping_sha256']=mapping_sha256
    if index_recipe_sha256 is not None:definition['index_recipe_sha256']=index_recipe_sha256
    fingerprint=hashlib.sha256(json.dumps(definition,sort_keys=True).encode()).hexdigest()
    entry={**definition,'fingerprint':fingerprint,'environment':name}
    (REPO/'definitions').mkdir(exist_ok=True);(REPO/'environments').mkdir(exist_ok=True)
    (REPO/'definitions'/f'{fingerprint}.json').write_text(json.dumps(definition,indent=2),encoding='utf-8')
    (REPO/'environments'/f'{name}.json').write_text(json.dumps(entry,indent=2),encoding='utf-8')
    return entry
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=int,required=True,help='Successful baseline Gitea Actions run ID');args=parser.parse_args()
    guard()
    if not (REPO/'.git').exists():
        REPO.mkdir(exist_ok=True);shutil.copytree(ROOT/'research/platform-spike/chart',REPO/'chart',dirs_exist_ok=True)
        git('init','-b','main');git('remote','add','origin',GITEA_GIT_URL+'/elastic-agent/environment-state.git')
    from keyvault import managed
    if not managed('argocd', 'gitea-state-repo'):
        c=json.loads((STATE/'credentials.json').read_text())
        apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'gitea-state-repo','namespace':'argocd','labels':{'argocd.argoproj.io/secret-type':'repository'}},'stringData':{'type':'git','url':'https://gitea-internal.lab-ingress.svc.cluster.local/elastic-agent/environment-state.git','username':'elastic-agent','password':c['build_token']}})
    apply({'apiVersion':'v1','kind':'Pod','metadata':{'name':'search-probe','namespace':'platform'},'spec':{'automountServiceAccountToken':False,'containers':[{'name':'probe','image':'python:3.13.7-alpine3.22','command':['sleep','86400'],'resources':{'requests':{'cpu':'10m','memory':'24Mi'},'limits':{'cpu':'250m','memory':'96Mi'}}}]}})
    baseline=build_record(args.run);record('baseline-build',baseline)
    provision_access('spike-baseline','spike-frozen-v1');define('spike-baseline',baseline['image']);publish('Create frozen baseline')
    k('apply','-f','research/platform-spike/applicationset.yaml')
    print('Baseline desired state published; Argo CD owns its workloads.')
