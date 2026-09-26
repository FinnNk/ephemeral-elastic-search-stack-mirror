import base64,json,os,shutil,subprocess
from common import *
from gitea import api
c=json.loads((STATE/'credentials.json').read_text())
repo=STATE/'search-source'
if not (repo/'.git').exists():
    shutil.copytree(ROOT/'research/platform-spike/fixture',repo,dirs_exist_ok=True)
    for args in [['init','-b','main'],['add','.'],['-c','user.name=elastic-agent','-c','user.email=elastic-agent@lab.invalid','commit','-m','Add baseline search fixture'],['remote','add','origin','http://127.0.0.1:31800/elastic-agent/search-spike.git']]:
        r=subprocess.run(['git','-C',str(repo),*args],capture_output=True,text=True,encoding='utf-8');assert r.returncode==0,r.stderr
basic=base64.b64encode(('elastic-agent:'+c['build_token']).encode()).decode()
env=os.environ.copy();env.update({'GIT_CONFIG_COUNT':'2','GIT_CONFIG_KEY_0':'http.extraHeader','GIT_CONFIG_VALUE_0':'Authorization: Basic '+basic,'GIT_CONFIG_KEY_1':'credential.helper','GIT_CONFIG_VALUE_1':'','GIT_TERMINAL_PROMPT':'0'})
r=subprocess.run(['git','-C',str(repo),'push','--set-upstream','origin','main'],env=env,capture_output=True,text=True,encoding='utf-8')
assert r.returncode==0,r.stderr.replace(basic,'[redacted]')
print('Baseline source pushed to Gitea; build queued.')
print(json.dumps(api('/repos/elastic-agent/search-spike/actions/runs'))[:600])
for name,port,target in [('elasticsearch',19200,'svc/shared-es-http'),('floci',14577,'svc/floci')]:
    destination='9200' if name=='elasticsearch' else '4577'
    log=open(STATE/(name+'-forward.log'),'a',encoding='utf-8')
    proc=subprocess.Popen(KUBE+['-n','platform','port-forward',target,f'{port}:{destination}','--address','127.0.0.1'],stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    (STATE/(name+'-forward.pid')).write_text(str(proc.pid))
print('Started loopback-only Elasticsearch and Floci research forwards.')
