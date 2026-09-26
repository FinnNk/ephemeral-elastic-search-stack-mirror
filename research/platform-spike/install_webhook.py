import json,secrets
from common import *
from gitea import api
guard();c=json.loads((STATE/'credentials.json').read_text());secret=c.setdefault('webhook_secret',secrets.token_urlsafe(32));(STATE/'credentials.json').write_text(json.dumps(c),encoding='utf-8')
apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'webhook-secret','namespace':'platform'},'stringData':{'secret':secret}})
apply({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'webhook-source','namespace':'platform'},'data':{'webhook.py':(ROOT/'research/platform-spike/webhook.py').read_text(encoding='utf-8-sig')}})
apply({'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':'webhook','namespace':'platform'},'spec':{'selector':{'matchLabels':{'app':'webhook'}},'template':{'metadata':{'labels':{'app':'webhook'}},'spec':{'automountServiceAccountToken':False,'containers':[{'name':'webhook','image':'python:3.13.7-alpine3.22','command':['python','/source/webhook.py'],'env':[{'name':'SECRET','valueFrom':{'secretKeyRef':{'name':'webhook-secret','key':'secret'}}}],'volumeMounts':[{'name':'source','mountPath':'/source'}],'resources':{'requests':{'cpu':'10m','memory':'24Mi'},'limits':{'memory':'96Mi'}}}],'volumes':[{'name':'source','configMap':{'name':'webhook-source'}}]}}}})
apply({'apiVersion':'v1','kind':'Service','metadata':{'name':'webhook','namespace':'platform'},'spec':{'selector':{'app':'webhook'},'ports':[{'port':8080}]}})
k('rollout','status','deployment/webhook','-n','platform','--timeout=120s')
for repo in ['search-spike','environment-state']:
    path='/repos/elastic-agent/'+repo+'/hooks'
    existing=next((h for h in api(path) if h['config'].get('url')=='http://webhook.platform.svc.cluster.local:8080/'),None)
    hook=api(path+('/'+str(existing['id']) if existing else ''),'PATCH' if existing else 'POST',{'type':'gitea','active':True,'events':['push','pull_request'],'config':{'url':'http://webhook.platform.svc.cluster.local:8080/','content_type':'json','secret':secret}})
    print('Configured signed Gitea hook',repo,hook['id'])
