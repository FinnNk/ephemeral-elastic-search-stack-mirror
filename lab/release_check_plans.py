"""Review accumulated release checks against one exact destination baseline."""
import base64
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import re
from urllib.parse import quote

from common import ROOT, STATE
from delivery_provider import SOURCE, DESIRED, api, endpoint, git, ensure_checkout, pull_request, merge_demo
from delivery.ci.release import canonical

PREFIX = 'check-plan/'
DIRECTORY = 'release-check-plans/'
KINDS = {'suggest-release-plan', 'propose-release-plan', 'accept-release-plan'}
INTENTS = {'ranking-change', 'preserve-results'}


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


@lru_cache(maxsize=16)
def source_file(path, revision):
    from delivery_source_comparison import source_bytes
    return source_bytes(path, revision)


def policy_pin():
    return hashlib.sha256((ROOT/'lab/delivery/policies/variant-merge-v1.json').read_bytes()).hexdigest()


def binding(baseline, candidate, target):
    from primary_query_sets import configuration
    from delivery_variant_selection import configured_baseline
    if target not in ('integration', 'staging', 'production'):
        raise ValueError('Choose an Integration, Staging or Production check plan.')
    return {'target': target, 'baseline': baseline, 'candidate': candidate,
            'baseline_variant': configured_baseline(baseline),
            'primary_query_sets': configuration(candidate['fields']['dataset_release']),
            'policy_sha256': policy_pin()}


def scope(run, target, settings=None):
    """Resolve the same frozen candidate that the promotion worker will check."""
    from delivery_runtime import checkout, read_target, resolve
    from delivery_variant_selection import source_selection
    checkout()
    baseline = read_target(target)
    if target == 'production':
        from production_release import state, live, inactive
        slots = live(state())
        candidate = slots['slots'].get(inactive(slots))
        if not candidate or candidate['build_run'] != run:
            raise ValueError('Prepare this build in the inactive production slot before planning its checks.')
    elif target == 'staging':
        candidate = read_target('integration')
        if candidate['build_run'] != run:
            raise ValueError('Verify this build in Integration before planning Staging checks.')
    else:
        from delivery_release import from_run
        receipt, _, _ = from_run(run)
        selection = source_selection(receipt['source_sha'])
        options = settings or {}
        candidate = resolve(run, variant_config=selection['configuration'], **{
            argument: options[field] for field, argument in (
                ('dataset_release','dataset'),('index_recipe_sha256','recipe_sha'),
                ('query_manifest_sha256','query_manifest_sha'),
                ('judgement_manifest_sha256','judgement_manifest_sha')) if options.get(field)})
    if candidate == baseline:
        raise ValueError('This release is already declared in the selected destination.')
    return baseline, candidate


def lineage(base, head):
    """Use complete Git ancestry; never silently truncate accumulated changes."""
    ensure_checkout(SOURCE)
    if git(SOURCE, 'rev-parse', '--is-shallow-repository') == 'true':
        git(SOURCE, 'fetch', '--unshallow', 'origin')
    git(SOURCE, 'fetch', '--no-tags', 'origin', base, head)
    common = git(SOURCE, 'merge-base', base, head)
    incoming = git(SOURCE, 'rev-list', '--reverse', base + '..' + head).splitlines()
    outgoing = git(SOURCE, 'rev-list', '--reverse', head + '..' + base).splitlines() if common != base else []
    revisions = [*outgoing, *incoming]
    if len(revisions) > 250:
        raise ValueError('More than 250 source commits need review. Split the release review into smaller increments.')
    return common, [{'source_sha': revision, 'side':'baseline-only' if revision in outgoing else 'candidate',
                     'title': git(SOURCE, 'show', '-s', '--format=%s', revision)}
                    for revision in revisions]


def freeze_one(item, revision):
    from query_sets import freeze
    return freeze({'additional_query_sets': [item]}, lambda path: source_file(path, revision))[0]


def suggest(baseline, candidate, target):
    from delivery_variant_selection import source_selection
    from query_sets import declarations
    selected = source_selection(candidate['fields']['source_sha'])
    base, head = baseline['fields']['source_sha'], candidate['fields']['source_sha']
    common, changes = lineage(base, head)
    suites, missing, intents = {}, [], []
    # Baseline suites are inherited regression obligations, even when a later
    # commit deleted their declarations. Historical bytes remain available.
    for revision in dict.fromkeys([base, *[c['source_sha'] for c in changes], head]):
        try:
            raw = api(endpoint(SOURCE, '/contents/gate/selection.json?ref=' + revision))
        except Exception as error:
            from gitea import GiteaHTTPError
            if isinstance(error, GiteaHTTPError) and error.status_code == 404:
                missing.append(revision)
                continue
            raise
        declared = json.loads(base64.b64decode(raw['content']))
        if not isinstance(declared,dict):raise ValueError('Historical gate selection must be a JSON object: '+revision)
        if revision != base:
            intents += [i.get('intent') for i in declared.get('selected', [])]
        for item in declarations(declared):
            frozen = freeze_one(item, revision)
            identity = {'name':item['name'], 'query_sha256':frozen['query_sha256'],
                        'judgement_sha256':frozen.get('judgement_sha256')}
            identifier = digest(identity)
            pin = {**item, **identity, 'id':identifier, 'source_sha':revision,
                   'required':item.get('required',False), 'origins':[]}
            existing = suites.setdefault(identifier, pin)
            existing['required'] |= item.get('required',False)
            existing['origins'].append(revision)
    suggested_intent = 'ranking-change' if 'ranking-change' in intents else 'preserve-results'
    return {'binding':binding(baseline,candidate,target), 'changes':changes,
            'ancestry':{'merge_base':common,'diverged':common != base,'missing_declarations':missing},
            'variants':[{'variant':i['variant'],'intent':suggested_intent} for i in selected['selection']],
            'suites':list(suites.values())}


def build_plan(suggestion, edits, reviewer):
    """Account for every inherited suite; protected primary sets are not editable."""
    from query_sets import declarations
    if not isinstance(edits,dict) or set(edits)-{'variants','suites','additional_query_sets','reason'}:
        raise ValueError('Unknown release check plan settings.')
    if not isinstance(edits.get('reason'),str) or not 20 <= len(edits['reason'].strip()) <= 4000:
        raise ValueError('Explain the release check selection in 20–4,000 characters.')
    variants = edits.get('variants',[])
    if (not isinstance(variants,list) or any(not isinstance(i,dict) or set(i)!={'variant','intent'} or
            i.get('intent') not in INTENTS for i in variants) or
            len(variants)!=len(suggestion['variants']) or
            {i['variant'] for i in variants}!={i['variant'] for i in suggestion['variants']}):
        raise ValueError('Keep every candidate variant and explicitly select its release intent.')
    decisions = edits.get('suites',[])
    if not isinstance(decisions,list) or len(decisions)!=len(suggestion['suites']):
        raise ValueError('Account for every suggested query set.')
    indexed = {}
    for decision in decisions:
        if (not isinstance(decision,dict) or set(decision)-{'id','disposition','reason'} or
                not re.fullmatch('[a-f0-9]{64}',str(decision.get('id',''))) or decision.get('id') in indexed or decision.get('disposition') not in ('required','report_only','retired') or
                not isinstance(decision.get('reason',''),str) or len(decision.get('reason',''))>2000):
            raise ValueError('Give each suggested set one valid disposition and a bounded reason.')
        indexed[decision['id']] = decision
    if set(indexed)!={i['id'] for i in suggestion['suites']}:
        raise ValueError('Suggested query-set identities differ.')
    for item in suggestion['suites']:
        decision = indexed[item['id']]
        if (decision['disposition']=='retired' or item['required'] and decision['disposition']!='required') and len(decision.get('reason','').strip())<20:
            raise ValueError('Explain retiring or weakening an inherited set in at least 20 characters.')
        if decision['disposition']=='required' and not item.get('judgements'):
            raise ValueError('Required sets need reviewed judgement files; add a replacement and explain retiring the old set.')
    additions = declarations({'additional_query_sets':edits.get('additional_query_sets',[])})
    count = sum(i['disposition']!='retired' for i in decisions)+len(additions)
    if count>8:
        raise ValueError('Keep at most eight active additional sets; explicitly retire superseded sets.')
    frozen_additions=[]
    source=suggestion['binding']['candidate']['fields']['source_sha']
    for item in additions:
        frozen=freeze_one(item,source)
        frozen_additions.append({**item,'source_sha':source,'query_sha256':frozen['query_sha256'],
                                 'judgement_sha256':frozen.get('judgement_sha256')})
    return {'kind':'release-check-plan','schema_version':1,'suggestion':suggestion,
            'edits':deepcopy(edits),'additional_sets':frozen_additions,'reviewer':reviewer}


def frozen_additional(plan):
    result=[]
    decisions={i['id']:i for i in plan['edits']['suites']}
    for item in plan['suggestion']['suites']:
        decision=decisions[item['id']]
        if decision['disposition']=='retired':continue
        # Keep distinct versions of a suite separate in the evidence.
        value={k:item[k] for k in ('name','path','judgements') if k in item}
        value['name']=item['name'][:22]+'-'+item['id'][:8]
        value['required']=decision['disposition']=='required'
        result.append((value,item))
    result += [({k:i[k] for k in ('name','path','judgements','required') if k in i},i)
               for i in plan['additional_sets']]
    # Check collisions and the same active-set contract as source declarations.
    from query_sets import declarations
    declarations({'additional_query_sets':[value for value,_ in result]})
    frozen=[]
    for value,pin in result:
        item=freeze_one(value,pin['source_sha'])
        if item['query_sha256']!=pin['query_sha256'] or item.get('judgement_sha256')!=pin.get('judgement_sha256'):
            raise ValueError('A planned query set differs from its frozen source bytes.')
        frozen.append({**item,'source_sha':pin['source_sha'],'group':'change-specific'})
    return frozen


def validate_record(plan, baseline, candidate, target):
    if plan.get('kind')!='release-check-plan' or plan.get('schema_version')!=1:
        raise ValueError('Invalid release check plan format.')
    fresh=suggest(baseline,candidate,target)
    if plan != build_plan(fresh,plan.get('edits'),plan.get('reviewer')):
        raise ValueError('Release check plan is stale or its accumulated source selection changed.')
    frozen_additional(plan)
    return plan


def content(path, revision):
    value=api(endpoint(DESIRED,'/contents/'+path+'?ref='+quote(revision,safe='')))
    return base64.b64decode(value['content'])


def inspect(number):
    pr=api(endpoint(DESIRED,'/pulls/'+str(number)))
    branch=pr['head']['ref']
    identifier=branch.removeprefix(PREFIX)
    if pr['base']['ref']!='main' or not branch.startswith(PREFIX) or not re.fullmatch('[a-f0-9]{64}',identifier):
        raise ValueError('Choose a release check plan PR to main.')
    if pr['state']!='open' and not pr.get('merged'):
        raise ValueError('The plan PR was closed without merging.')
    path=DIRECTORY+identifier+'.json';payload=content(path,pr['head']['sha']);plan=json.loads(payload)
    files=api(endpoint(DESIRED,'/pulls/'+str(number)+'/files?limit=100'))
    if digest(plan)!=identifier or len(files)!=1 or files[0].get('filename')!=path or files[0].get('status')!='added':
        raise ValueError('A plan PR must add only its exact content-addressed plan record.')
    return pr,path,payload,plan


def approval(pr,plan):
    from relevance_decisions import approved_review
    return approved_review(pr,{'reviewer':plan['reviewer']})


def status(number):
    pr,path,payload,plan=inspect(number)
    if pr.get('merged') and (content(path,'main')!=payload or content(path,pr['merge_commit_sha'])!=payload):
        raise ValueError('Recorded plan differs from its approved source-control record.')
    approved=False
    try:approval(pr,plan);approved=True
    except ValueError:pass
    return {'pr':number,'state':'recorded' if pr.get('merged') and approved else 'approved' if approved else 'awaiting review',
            'id':digest(plan),'url':'https://gitea.localhost:34443/elastic-agent/delivery-state/pulls/'+str(number)}


def propose(suggestion,edits,identity):
    from delivery_runtime import checkout
    if not identity.get('is_admin') or identity.get('is_reader') or identity.get('is_delivery_service'):
        raise PermissionError('A human administrator must propose a release check plan.')
    pin=suggestion['binding'];baseline,candidate=scope(pin['candidate']['build_run'],pin['target'],pin['candidate']['fields'])
    if binding(baseline,candidate,pin['target'])!=pin:
        raise ValueError('The destination, candidate or policy changed. Suggest a new plan.')
    plan=build_plan(suggestion,edits,identity['username'])
    validate_record(plan,baseline,candidate,pin['target'])
    identifier=digest(plan);branch=PREFIX+identifier;path=DIRECTORY+identifier+'.json'
    checkout()
    existing=next((p for p in pulls() if p['head']['ref']==branch),None)
    if existing:return {'run':candidate['build_run'],'target':pin['target'],'plan':plan,**status(existing['number'])}
    git(DESIRED,'switch','-c',branch)
    try:
        from delivery_runtime import LOCAL
        from delivery_json import write_json
        folder=LOCAL/DIRECTORY;folder.mkdir(exist_ok=True)
        write_json(LOCAL/path,plan)
        git(DESIRED,'add',path);git(DESIRED,'commit','-m','Review release checks for '+pin['target'])
        git(DESIRED,'push','origin',branch)
    finally:git(DESIRED,'switch','main')
    body='Review the release check plan in `'+path+'`.\n\nBaseline build '+str(baseline['build_run'])+' → candidate build '+str(candidate['build_run'])+' ('+pin['target']+').\n\nAll protected primary sets remain required. Review inherited suites, retirements and each variant intent. '+identity['username']+' must approve this exact head, then choose **Record approved plan** in the release dashboard. Recording this plan does not deploy.\n\n[Open release dashboard](https://control.localhost:34443/release-dashboard?run='+str(candidate['build_run'])+')'
    pr=pull_request(DESIRED,branch,'Release check plan: '+pin['target']+' build '+str(candidate['build_run']),body)
    api(endpoint(DESIRED,'/statuses/'+pr['head']['sha']),'POST',{'context':'delivery/validation','state':'success','description':'Release check plan inputs verified; exact-head human review required','target_url':pr['html_url']})
    return {'run':candidate['build_run'],'target':pin['target'],'plan':plan,**status(pr['number'])}


def record(number):
    from delivery_runtime import checkout
    checkout();pr,path,payload,plan=inspect(number)
    pin=plan['suggestion']['binding'];baseline,candidate=scope(pin['candidate']['build_run'],pin['target'],pin['candidate']['fields'])
    validate_record(plan,baseline,candidate,pin['target']);review=approval(pr,plan)
    if not pr.get('merged'):
        current=inspect(number)[0]
        if current['head']['sha']!=pr['head']['sha']:raise ValueError('Plan head changed before recording approval.')
        approval(current,plan);pr=merge_demo(DESIRED,number,pr['head']['sha'])
    if content(path,'main')!=payload or content(path,pr['merge_commit_sha'])!=payload:
        raise ValueError('Merged plan bytes differ from the approved head.')
    checkout()
    return {'run':candidate['build_run'],'target':pin['target'],'plan':plan,**status(number)}


def pulls():
    result=[]
    for page in range(1,11):
        rows=api(endpoint(DESIRED,'/pulls?state=all&limit=100&page='+str(page)))
        result += [p for p in rows if p['head']['ref'].startswith(PREFIX)]
        if len(rows)<100:return result
    raise ValueError('Release check plan history exceeds the bounded lookup; narrow the retained plan catalogue.')


def require(baseline,candidate,target,reference=None):
    """Every promotion entry point checks merged, reviewed, current plan bytes."""
    expected=binding(baseline,candidate,target)
    matches=[]
    for pr in pulls():
        if not pr.get('merged'):continue
        checked,path,payload,plan=inspect(pr['number'])
        if plan['suggestion']['binding']!=expected:continue
        if content(path,'main')!=payload or content(path,pr['merge_commit_sha'])!=payload:
            raise ValueError('Recorded plan differs from its approved source-control record.')
        review=approval(checked,plan)
        matches.append((pr,plan,review))
    if not matches:raise ValueError('Review and record a release check plan for this exact candidate and destination before running promotion checks.')
    pr,plan,review=max(matches,key=lambda item:(item[0].get('merged_at') or '',item[0]['number']))
    ref={'id':digest(plan),'pr':pr['number'],'head_sha':pr['head']['sha'],
         'merge_sha':pr['merge_commit_sha'],'merged_at':pr['merged_at'],'review_id':review['id'],'reviewer':plan['reviewer'],
         'url':'https://gitea.localhost:34443/elastic-agent/delivery-state/pulls/'+str(pr['number'])}
    if reference is not None and reference!=ref:
        raise ValueError('The reviewed release check plan changed; fresh checks are required.')
    validate_record(plan,baseline,candidate,target)
    from delivery_variant_selection import source_selection
    selected=source_selection(candidate['fields']['source_sha'])
    return {**selected,'selection':deepcopy(plan['edits']['variants']),'_release_plan':plan},ref


def dashboard_status(data, identity):
    """Project saved suggestions and plan PRs without mutating Git checkouts."""
    from release_dashboard import operation_rows
    selected=data.get('selected') or {}
    rows=operation_rows(identity)
    catalogue=None
    result={}
    for action in ('integration','staging','release','rollback'):
        target=action if action in ('integration','staging') else 'production'
        current=next((e for e in data.get('environments',[]) if e['name']==target),None) if target!='production' else data.get('active_production')
        retained=next((e for e in data.get('environments',[]) if e.get('slot') and not e.get('active')),None)
        run=(retained or {}).get('build_run') if action=='rollback' else selected.get('run')
        source=(retained or {}).get('definition',{}).get('source_sha') if action=='rollback' else selected.get('source_sha')
        value={'state':'needed','run':run,'target':target}
        if not run or not current:
            result[action]={**value,'state':'unavailable'};continue
        if action in ('integration','staging') and any(s.get('name')==action and s.get('state')=='verified' for s in data.get('stages',[])):
            result[action]={**value,'state':'current'};continue
        candidate_environment = (next((e for e in data.get('environments',[]) if e['name']=='integration'),None) if target=='staging' else retained if target=='production' else None)
        if target!='integration' and (not candidate_environment or candidate_environment.get('build_run')!=run):
            result[action]={**value,'state':'unavailable','error':
                'Verify this build in Integration first.' if target=='staging' else 'Prepare and deploy this build in the inactive production slot first.'}
            continue
        def matches(row):
            record=row.get('result') or {}
            suggestion=record.get('suggestion') or (record.get('plan') or {}).get('suggestion')
            if not suggestion:return False
            pin=suggestion['binding']
            return (pin['target']==target and pin['candidate']['build_run']==run and
                pin['candidate']['fields']['source_sha']==source and
                pin['baseline']['fingerprint']==current['definition']['fingerprint'] and
                pin['policy_sha256']==policy_pin() and (not candidate_environment or
                pin['candidate']['fingerprint']==candidate_environment['definition']['fingerprint']))
        saved=[r for r in rows if r['request']['kind'] in KINDS and matches(r)]
        draft=next((r for r in saved if r['request']['kind']=='suggest-release-plan' and r['state']=='complete'),None)
        if draft:value.update(state='suggested',suggestion_id=draft['id'],suggestion=draft['result']['suggestion'])
        proposal=next((r for r in saved if r['result'].get('pr')),None)
        if proposal:
            try:
                summary=status(proposal['result']['pr']);value.update(summary,plan_id=summary['id'],reviewed_variants=proposal['result']['plan']['edits']['variants'],reviewed_edits=proposal['result']['plan']['edits'])
            except (RuntimeError,OSError,ValueError,KeyError):
                value.update(state='unavailable',error='The plan PR or its review could not be verified.')
        else:
            # The reviewed record survives loss or pruning of the operations DB.
            if catalogue is None:
                catalogue=[]
                for pr in pulls():
                    if pr.get('merged') or pr.get('state')=='open':
                        try:
                            checked,_,_,plan=inspect(pr['number'])
                            catalogue.append((checked,plan))
                        except (RuntimeError,OSError,ValueError,KeyError):
                            continue
            for pr,plan in sorted(catalogue,key=lambda item:item[0]['number'],reverse=True):
                if matches({'result':{'plan':plan}}):
                    try:
                        summary=status(pr['number'])
                        value.update(summary,plan_id=summary['id'],reviewed_variants=plan['edits']['variants'],reviewed_edits=plan['edits'])
                        break
                    except (RuntimeError,OSError,ValueError,KeyError):
                        value.update(state='unavailable',error='The recorded plan could not be verified.')
        pending=next((r for r in rows if r['request']['kind'] in KINDS and r['state'] in ('accepted','queued','running') and (
            r['request'].get('run')==run and r['request'].get('target')==target or
            draft and r['request'].get('suggestion')==draft['id'] or
            proposal and r['request'].get('pr')==proposal['result'].get('pr'))),None)
        if pending:value.update(state='working',operation_url='/api/delivery/operations/'+pending['id'])
        result[action]=value
    return result
