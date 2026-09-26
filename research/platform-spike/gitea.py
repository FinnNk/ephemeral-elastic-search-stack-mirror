"""Gitea setup for the local spike. Credentials stay under .lab/."""
import base64,json,secrets,urllib.request,urllib.error
from common import *
BASE='http://127.0.0.1:31800/api/v1'
def api(path,method='GET',body=None,identity='agent'):
    c=json.loads((STATE/'credentials.json').read_text())
    if identity=='agent':c=c['agent']
    auth='Basic '+base64.b64encode((c['username']+':'+c['password']).encode()).decode()
    req=urllib.request.Request(BASE+path,method=method,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':auth,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            data=r.read();return json.loads(data) if data else None
    except urllib.error.HTTPError as e:raise RuntimeError(f'Gitea {method} {path}: {e.code}') from None
if __name__=='__main__':
    guard();c=json.loads((STATE/'credentials.json').read_text())
    if 'agent' not in c:
        agent={'username':'elastic-agent','password':secrets.token_urlsafe(32)}
        api('/admin/users','POST',{'username':agent['username'],'password':agent['password'],'email':'elastic-agent@lab.invalid','must_change_password':False},identity='admin')
        c['agent']=agent;(STATE/'credentials.json').write_text(json.dumps(c),encoding='utf-8')
    for name in ['search-spike','environment-state','ephemeral-elastic-search-stack']:
        repos=api('/user/repos')
        if not any(r['name']==name for r in repos):api('/user/repos','POST',{'name':name,'private':True,'default_branch':'main','auto_init':False})
        api('/repos/elastic-agent/'+name,'PATCH',{'has_actions':name=='search-spike'})
    if 'build_token' not in c:
        token=api('/users/elastic-agent/tokens','POST',{'name':'local-spike-build','scopes':['write:repository','write:package']})['sha1']
        c['build_token']=token;(STATE/'credentials.json').write_text(json.dumps(c),encoding='utf-8')
    api('/repos/elastic-agent/search-spike/actions/secrets/BUILD_TOKEN','PUT',{'data':c['build_token']})
    registration=api('/repos/elastic-agent/search-spike/actions/runners/registration-token','POST')['token']
    apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'runner-registration','namespace':'platform'},'stringData':{'token':registration}})
    print('Created private local repositories, agent identity and repository-scoped runner registration.')
