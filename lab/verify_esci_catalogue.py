"""Verify real catalogue capture with two exact source builds in disposable environments."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

from common import STATE, apply, guard, k
from catalogue import DEFAULT_RELEASE
from delivery_release import from_run
from environments import REPO, define, git, provision_access
from setup_nexus import image_secret
from deploy_candidate import wait_healthy
from compare_search import definition
from search_probe import search
from input_selection import DEFAULTS, fetch_manifest
from index_recipe import catalogue_recipe, publish as publish_recipe
from shared_index import ensure_shared_index
from data_contract import elastic
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'evaluation'),str(Path(__file__).resolve().parents[1]/'data')]
from capture import capture
from offline import evaluate


def verify(baseline_run, candidate_run, release=DEFAULT_RELEASE, gatling_probe=False):
    guard()
    if git('status','--porcelain'):
        raise ValueError('Desired-state checkout has local changes.')
    before = git('branch','--show-current')
    suffix = uuid.uuid4().hex[:8]
    output = STATE / ('esci-verification-' + suffix)
    output.mkdir()
    catalogue = fetch_manifest('catalogue',DEFAULTS[release]['catalogue'])
    recipe = catalogue_recipe(release,'shared',catalogue,elastic('/')['version']['number'])
    recipe_sha = publish_recipe(recipe)
    index = ensure_shared_index(release,recipe['product_sha256'],recipe_sha)['index']
    names = ('lab-esci-before-'+suffix,'lab-esci-after-'+suffix)
    records = [from_run(run)[0] for run in (baseline_run,candidate_run)]
    settings = {'field_boosts':{'title':4,'product_type':3,'brand':2,'description':1}}
    variants = {}
    entries = {}
    created = []
    branch = 'verification/esci-' + suffix
    try:
        git('switch','-c',branch)
        for name,record,variant in zip(names,records,('ranker-baseline','ranker-a')):
            config={'default_variant':variant,'variants':{variant:settings}}
            entries[name]=define(name,record['image'],index,recipe['product_sha256'],
                                 variant_config=config,image_pull_secret='nexus-read')
            variants[variant]={'environment':name,'environment_fingerprint':entries[name]['fingerprint'],
                               'configuration_sha256':hashlib.sha256(json.dumps(settings,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                               'selection':'default'}
        git('add','environments','definitions')
        git('commit','-m','Pin disposable ESCI source-build comparisons')
        revision=git('rev-parse','HEAD');git('push','-u','origin',branch)
        parent=json.loads(k('get','application/lab-variant-managed','-n','argocd','-o','json').stdout)
        for name in names:
            provision_access(name,index,registry=False)
            created.append(name)
            image_secret(name)
            spec=copy.deepcopy(parent['spec'])
            spec['destination']['namespace']=name
            spec['source']['targetRevision']=revision
            spec['source']['helm']['parameters']=[{'name':key,'value':str(entries[name][key])}
                for key in ('environment','image','index','fingerprint','variant_config_b64','image_pull_secret')]
            apply({'apiVersion':'argoproj.io/v1alpha1','kind':'Application',
                   'metadata':{'name':name,'namespace':'argocd','labels':{'lab/experiment':'esci-verification'},
                               'finalizers':['resources-finalizer.argocd.argoproj.io']},'spec':spec})
            wait_healthy(name)
            assert definition(name)==entries[name]
        selection={'kind':'search-variant-set','schema_version':1,'default_variant':'ranker-a',
                   'baseline_variant':'ranker-baseline','variants':variants}
        (output/'variant-set.json').write_text(json.dumps(selection,sort_keys=True,separators=(',',':')),encoding='utf-8')
        manifests=STATE/'artifacts-reference'/release
        source=STATE/'releases'/release
        started=time.monotonic()
        observations,reference=capture(output/'variant-set.json',source/'queries.jsonl',
                                     manifests/'query-suite.json',manifests/'catalogue.json')
        (output/'observations.json').write_bytes(observations)
        report=evaluate(output/'observations.json',source/'judgements.jsonl',
                        Path(__file__).resolve().parents[1]/'evaluation/specs/proxy-v1.json',
                        manifests/'catalogue.json',manifests/'query-suite.json',manifests/'judgement-set.json')
        (output/'report.json').write_text(json.dumps(report,sort_keys=True,separators=(',',':')),encoding='utf-8')
        sample=search(names[1],'running shoes')
        assert sample and sample['ids']
        assert elastic('/'+index+'/_count')['count']==catalogue['record_count']
        summary={'release':release,'count':catalogue['record_count'],'build_runs':[baseline_run,candidate_run],
                 'source_shas':[record['source_sha'] for record in records],
                 'index':index,'recipe_sha256':recipe_sha,'query_count':report['query_count'],
                 'result_changes':report['result_changes'],'result_similarity':report['result_similarity'],
                 'coverage':report['coverage'],'metrics':report['metrics'],
                 'capture_and_score_seconds':round(time.monotonic()-started,3),'observation':reference,
                 'sample_ids':sample['ids'],'output':str(output)}
        if gatling_probe:
            from run_gatling_job import run
            summary['gatling_probe'] = {side: run('probe', side, environment=name, release_id=release)
                for side, name in zip(('baseline', 'candidate'), names)}
        (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        return summary
    finally:
        for name in created:
            k('delete','application/'+name,'-n','argocd','--ignore-not-found','--wait=true','--timeout=120s',check=False)
            k('delete','namespace/'+name,'--ignore-not-found','--wait=true','--timeout=120s',check=False)
            elastic('/_security/user/'+name,'DELETE')
            elastic('/_security/role/'+name,'DELETE')
        git('switch',before)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-run',required=True,type=int)
    parser.add_argument('--candidate-run',required=True,type=int)
    parser.add_argument('--gatling-probe', action='store_true')
    args=parser.parse_args()
    print(json.dumps(verify(args.baseline_run,args.candidate_run,gatling_probe=args.gatling_probe),indent=2))
