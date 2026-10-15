"""Load protected mandatory query suites from the trusted gate policy."""
import json
from copy import deepcopy

from common import ROOT
from input_selection import DEFAULTS, select
from variant_gate import primary_declarations, canonical, sha


def configuration(release):
    """Require a non-empty group whose first set is the catalogue's standard suite."""
    policy = json.loads((ROOT/'lab/delivery/policies/variant-merge-v1.json').read_text(encoding='utf-8'))
    anchor = DEFAULTS[release]['query-suite']
    group = policy.get('primary_query_sets', {}).get(anchor)
    primary_declarations({'primary_query_manifest_sha256':anchor,'primary_query_sets':group}, policy)
    if group[0]['judgement_manifest_sha256'] != DEFAULTS[release]['judgement-set']:
        raise ValueError('The first mandatory suite must retain the standard judgement manifest.')
    return deepcopy(group)


def frozen_sets(release, catalogue_sha):
    """Freeze secondary mandatory suites from verified retained input manifests."""
    from delivery_source_comparison import retained_bytes
    group = configuration(release)
    result = []
    for item in group[1:]:
        inputs = select(release, catalogue_sha, item['query_manifest_sha256'], item['judgement_manifest_sha256'], relevance=True)
        queries = retained_bytes(inputs['query_manifest'])
        labels = retained_bytes(inputs['judgement_manifest'])
        name = item['name']
        result.append({**item, 'group':'mandatory', 'required':True,
            'path':'evaluation/mandatory/'+name+'.jsonl',
            'judgements':'evaluation/mandatory/'+name+'-judgements.jsonl',
            'query_bytes':queries, 'query_sha256':sha(queries), 'queries':inputs['queries'],
            'judgement_bytes':labels, 'judgement_sha256':sha(labels), 'judgements_rows':inputs['judgements'],
            'judgement_selection':inputs['judgement_manifest']['producer'].get('selection','gate')})
    return result


def annotate(report, release):
    """Bind the complete mandatory group into immutable comparison evidence."""
    report['primary_query_manifest_sha256'] = DEFAULTS[release]['query-suite']
    report['primary_query_sets'] = configuration(release)
    metadata = report.get('query_set_metadata', {})
    if 'standard' in metadata: metadata['standard']['group']='mandatory'
    for name, meta in metadata.items():
        meta.setdefault('group','mandatory' if name.startswith('primary-') else 'change-specific')
    return report


def retain_labels(item, retain):
    """Use the selected published snapshot without extending its label population."""
    receipt = {'kind':'frozen-primary-judgements', 'query_manifest_sha256':item['query_manifest_sha256'],
               'judgement_manifest_sha256':item['judgement_manifest_sha256']}
    return {**item, 'resolved_references':{
        'judgements':retain(item['judgement_bytes'],'judgements.jsonl'),
        'resolution':retain(canonical(receipt),'primary-judgements.json')}}
