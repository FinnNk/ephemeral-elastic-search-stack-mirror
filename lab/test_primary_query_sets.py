"""Mandatory groups are protected, non-empty and independently gated."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import primary_query_sets as primary
from input_selection import DEFAULTS
from query_sets import declarations
from variant_gate import primary_declarations, additional_suite_states, canonical, sha


class PrimaryQuerySets(unittest.TestCase):
    def setUp(self):
        self.anchor=DEFAULTS['esci-gb-v1']['query-suite']
        self.group=[{'name':'standard','query_manifest_sha256':self.anchor,
            'judgement_manifest_sha256':DEFAULTS['esci-gb-v1']['judgement-set']},
            {'name':'primary-seasonal','query_manifest_sha256':'a'*64,'judgement_manifest_sha256':'b'*64}]
        self.policy=json.loads((primary.ROOT/'lab/delivery/policies/variant-merge-v1.json').read_text(encoding='utf-8'))
        self.policy['primary_query_sets']={self.anchor:self.group}
        self.report={'primary_query_manifest_sha256':self.anchor,'primary_query_sets':deepcopy(self.group)}

    def test_groups_require_one_or_more_unique_pinned_sets(self):
        self.assertEqual(len(primary_declarations(self.report,self.policy)),1)
        for group in ([],self.group*2,[{**self.group[0],'name':'optional'}],
                      [self.group[0],{**self.group[1],'query_manifest_sha256':'invalid'}]):
            with self.subTest(group=group):
                p={**self.policy,'primary_query_sets':{self.anchor:group}}
                with self.assertRaises(ValueError):primary_declarations({**self.report,'primary_query_sets':group},p)
        with self.assertRaisesRegex(ValueError,'missing'):
            primary_declarations({},self.policy)
        altered=deepcopy(self.report);altered['primary_query_sets'].pop()
        with self.assertRaisesRegex(ValueError,'omitted'):primary_declarations(altered,self.policy)

    def test_change_specific_group_may_be_empty_but_cannot_shadow_primary(self):
        self.assertEqual(declarations({}),[])
        self.assertEqual(len(declarations({'additional_query_sets':[
            {'name':'summer','path':'evaluation/queries/summer.jsonl'},
            {'name':'winter','path':'evaluation/queries/winter.jsonl'}]})),2)
        with self.assertRaises(ValueError):declarations({'additional_query_sets':[
            {'name':'primary-seasonal','path':'evaluation/queries/replacement.jsonl','required':False}]})

    def test_configured_group_is_loaded_from_policy_and_freezes_both_manifests(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'lab/delivery/policies';folder.mkdir(parents=True)
            (folder/'variant-merge-v1.json').write_text(json.dumps(self.policy),encoding='utf-8')
            with patch.object(primary,'ROOT',root):
                self.assertEqual(primary.configuration('esci-gb-v1'),self.group)
                rows=[{'query_id':'q','query':'summer','country':'GB','currency':'GBP','filters':{}}]
                labels=[{'query_id':'q','product_id':'p','grade':3}]
                selected={'queries':rows,'judgements':labels,'query_manifest':{'content':{'object':'queries'}},
                    'judgement_manifest':{'content':{'object':'labels'},'producer':{'selection':'gate'}}}
                with patch.object(primary,'select',return_value=selected) as select,patch('delivery_source_comparison.retained_bytes',side_effect=lambda m:canonical(rows[0] if m['content']['object']=='queries' else labels[0])):
                    frozen=primary.frozen_sets('esci-gb-v1','c'*64)
                select.assert_called_once_with('esci-gb-v1','c'*64,'a'*64,'b'*64,relevance=True)
                self.assertTrue(frozen[0]['required']);self.assertEqual(frozen[0]['group'],'mandatory')
                self.assertEqual(frozen[0]['judgements_rows'],labels)
                self.policy['primary_query_sets'][self.anchor]=[]
                (folder/'variant-merge-v1.json').write_text(json.dumps(self.policy),encoding='utf-8')
                with self.assertRaises(ValueError):primary.configuration('esci-gb-v1')

    def test_primary_failure_blocks_even_with_zero_change_specific_sets(self):
        declaration=primary_declarations(self.report,self.policy)[0]
        suite={'complete':True,'variants':{'baseline':{},'candidate':{}},'baseline_variant':'baseline',
            'catalogue_sha256':'c'*64,'query_suite_sha256':'d'*64,'relevance_available':True,
            'judgement_selection':'gate','unqualified_judgements':0,'query_count':2,
            'metrics':{'baseline':{'nDCG@10':1},'candidate':{'nDCG@10':1}},
            'delta_from_baseline':{'candidate':{'nDCG@10':0}},
            'coverage':{v:{'fraction':1} for v in ('baseline','candidate')},
            'result_changes':{'candidate':{'changed_queries':0,'fraction':0}}}
        report={**self.report,'variants':suite['variants'],'baseline_variant':'baseline','catalogue_sha256':'c'*64,
            'query_sets':{'standard':{},'primary-seasonal':suite},
            'query_set_metadata':{'standard':{'required':True},'primary-seasonal':{
                **declaration,'query_sha256':'d'*64,'judgement_sha256':'e'*64}},
            'additional_query_sets_selection_sha256':sha(canonical([]))}
        states=additional_suite_states(report,{},self.policy,'candidate','ranking-change')
        self.assertEqual(states[0]['state'],'pass')
        suite['metrics']['candidate']['nDCG@10']=.5
        suite['delta_from_baseline']['candidate']['nDCG@10']=-.5
        report['combined']={'metrics':{'candidate':{'nDCG@10':1}}}
        states=additional_suite_states(report,{},self.policy,'candidate','ranking-change')
        self.assertEqual(states[0]['state'],'blocked')
        report['query_set_metadata']['primary-seasonal']['required']=False
        with self.assertRaisesRegex(ValueError,'settings differ'):
            additional_suite_states(report,{},self.policy,'candidate','ranking-change')
        del report['query_sets']['primary-seasonal']
        with self.assertRaises(ValueError):additional_suite_states(report,{},self.policy,'candidate','ranking-change')

    def test_current_catalogues_all_have_a_non_empty_group(self):
        for release in DEFAULTS:
            with self.subTest(release=release):self.assertGreaterEqual(len(primary.configuration(release)),1)


if __name__=='__main__':unittest.main()
