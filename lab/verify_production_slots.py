"""Rehearse production slots in an isolated namespace, using four real lab queries.

Run inside the control API container under its writer lock. The fixture uses the
current production image in both slots to test routing, capture and shared scoring;
it does not approve or activate a new production release.
"""
from copy import deepcopy
import json
from datetime import datetime, timedelta, timezone
import time
import uuid
from unittest.mock import patch

from common import STATE, k
from delivery_runtime import writer, checkout, read_target, access, application, LOCAL
from delivery_provider import DESIRED, git
from delivery_gates import read
from input_selection import select
import production_release as release
from search_probe import search

NAME = 'lab-delivery-release-check'


def endpoints():
    value = json.loads(k('get','endpointslices','-n',NAME,'-l',
                        'kubernetes.io/service-name=search','-o','json').stdout)
    return sorted(e['targetRef']['name'] for item in value['items']
                  for e in item.get('endpoints',[]) if e.get('conditions',{}).get('ready'))


def deploy(value, branch):
    path='previews/'+NAME
    git(DESIRED,'switch',branch)
    folder=LOCAL/path;folder.mkdir(parents=True,exist_ok=True)
    (folder/'search.yaml').write_text(release.render_state(value),encoding='utf-8')
    git(DESIRED,'add',path)
    git(DESIRED,'commit','-m','Rehearse isolated production slot '+value['active'])
    revision=git(DESIRED,'rev-parse','HEAD')
    git(DESIRED,'push','origin',branch)
    git(DESIRED,'switch','main')
    application(NAME,path,revision,(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        obj=json.loads(k('get','application/'+NAME,'-n','argocd','-o','json').stdout)
        status=obj.get('status',{})
        if (status.get('sync',{}).get('revision')==revision and
                status.get('sync',{}).get('status')=='Synced' and
                status.get('health',{}).get('status')=='Healthy'):
            release.live(value)
            return revision
        time.sleep(2)
    raise TimeoutError('Isolated Argo slot deployment did not finish.')


def main():
    with writer():
        checkout()
        branch='preview/production-slot-rehearsal-'+uuid.uuid4().hex[:8]
        git(DESIRED,'switch','-c',branch)
        git(DESIRED,'switch','main')
        current = read_target('production')
        release.frozen_catalogue(current)
        before = search('lab-delivery-production')
        value = release.initial(current)
        value['slots']['green'] = deepcopy(current)
        inputs = select(current['fields']['dataset_release'],current['fields']['dataset_sha256'],
            current['fields']['query_manifest_sha256'],current['fields']['judgement_manifest_sha256'],relevance=True)
        inputs = {**inputs,'queries':inputs['queries'][:4]}
        inputs['judgements']=[r for r in inputs['judgements'] if r['query_id'] in {q['query_id'] for q in inputs['queries']}]
        access(NAME,current)
        try:
            with patch.object(release,'NAMESPACE',NAME):
                deploy(value,branch)
                blue=endpoints()
                assert blue and all(name.startswith('search-blue-') for name in blue),blue
                with patch.object(release,'state',return_value=value),patch.object(release,'checkout'), \
                        patch('input_selection.select',return_value=inputs):
                    reference=release.final_check(print)
                report=read(reference)
                assert report['complete'] and report['query_count']==4
                release.validate_final(reference,value)
                value['active']='green'
                deploy(value,branch)
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    green=endpoints()
                    if green and all(name.startswith('search-green-') for name in green):break
                    time.sleep(1)
                else:raise AssertionError('Route did not select the green Pods.')
                release.live(value)
                assert blue!=green
                assert search(NAME)['ids']==before['ids']
                try:release.validate_final(reference,value)
                except ValueError:pass
                else:raise AssertionError('Old final evidence accepted after route switch.')
                result={'passed':True,'namespace':NAME,'query_count':4,'same_image_fixture':True,
                    'blue_endpoints':blue,'green_endpoints':green,'final_report':reference,
                    'coverage':report['coverage'],'metrics':report['metrics'],
                    'resolution':report.get('judgement_resolution',{}).get('execution'),
                    'production_unchanged':search('lab-delivery-production')['ids']==before['ids']}
                assert result['production_unchanged']
                print(json.dumps(result,sort_keys=True))
        finally:
            git(DESIRED,'switch','main')
            try:
                k('delete','application/'+NAME,'-n','argocd','--ignore-not-found','--wait=false')
                k('delete','namespace',NAME,'--ignore-not-found','--wait=true','--timeout=90s')
            finally:
                from data_contract import elastic
                elastic('/_security/user/'+NAME,'DELETE')
                elastic('/_security/role/'+NAME,'DELETE')


if __name__=='__main__':
    main()
