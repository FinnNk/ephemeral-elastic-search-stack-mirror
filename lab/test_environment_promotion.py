"""Promotion colours require exact evidence, approval and source ancestry."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import environment_promotion as promotion


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.row = {'name': 'lab-delivery-integration', 'source_sha': 'a'*40,
                    'fingerprint': 'c'*64, 'definition': {'source_sha': 'a'*40}}
        self.target = {'name': 'lab-delivery-staging', 'fingerprint': 'd'*64, 'source_sha': 'b'*40}
        self.operation = {'id': 'operation', 'state': 'complete', 'updated_at': '2026-10-09',
            'result': {'pr': 24, 'head_sha': 'head', 'validation': {'passed': True}, 'proposal': {
                'kind': 'promotion', 'target': 'staging', 'base_revision': 'main',
                'expected_target': 'd'*64, 'deployment': {'fingerprint': 'c'*64, 'fields': {'source_sha': 'a'*40}}}}}
        self.reviews = {24: {'state': 'approved', 'head_sha': 'head'}}

    def result(self, relation='newer'):
        return promotion.project(self.row, [self.target], [self.operation], self.reviews,
                                 'main', {24: 'success'}, order=lambda *args: relation)

    def test_approved_exact_release_is_coloured_by_source_order(self):
        for relation, tone in (('newer', 'good'), ('older', 'warn'), ('same', ''), ('unknown', '')):
            with self.subTest(relation=relation):
                result = self.result(relation)
                self.assertEqual(result['state'], 'promotable')
                self.assertEqual(result['tone'], tone)

    def test_absent_evidence_and_unknown_review_are_neutral(self):
        self.assertEqual(promotion.project(self.row, [self.target], [], {}, 'main', {})['state'], 'no_evidence')
        self.reviews = {}
        self.assertEqual(self.result()['tone'], '')

    def test_semver_takes_precedence_but_git_order_remains_visible(self):
        self.row['software_version'] = '1.2.0+build.158.1'
        self.target['software_version'] = '1.1.0+build.999.1'
        result = self.result('older')
        self.assertEqual(result['tone'], 'good')
        self.assertEqual(result['ordering_basis'], 'SemVer')
        self.assertEqual(result['source_order'], 'older')
        self.target['software_version'] = '1.2.0+build.999.1'
        self.assertEqual(self.result()['tone'], '')
        self.row['software_version'] = '1.0.0'
        self.assertEqual(self.result()['tone'], 'warn')

    def test_closed_gates_cannot_be_promotable(self):
        for change in ('failed', 'review', 'target', 'main', 'head', 'fingerprint', 'fields', 'preparation'):
            with self.subTest(change=change):
                self.setUp()
                proposal = self.operation['result']['proposal']
                if change == 'failed': self.operation['result']['validation']['passed'] = False
                if change == 'review': self.reviews[24]['state'] = 'awaiting review'
                if change == 'target': proposal['expected_target'] = 'old'
                if change == 'main': proposal['base_revision'] = 'old'
                if change == 'head': self.reviews[24]['head_sha'] = 'changed'
                if change == 'fingerprint': proposal['deployment']['fingerprint'] = 'other'
                if change == 'fields': proposal['deployment']['fields']['source_sha'] = 'other'
                if change == 'preparation': proposal['kind'] = 'prepare-production'
                self.assertNotEqual(self.result()['state'], 'promotable')

    def test_next_targets_and_active_production(self):
        for row, target in ((self.row, 'staging'), ({'name': 'lab-delivery-staging'}, 'production'),
            ({'name': 'lab-delivery-production-blue', 'slot_role': 'active'}, None),
            ({'name': 'lab-delivery-production-green', 'slot_role': 'inactive'}, 'production'),
            ({'name': 'lab-delivery-run-158-1234abcd'}, 'integration'), ({'name': 'lab-search-test'}, None)):
            self.assertEqual(promotion.next_target(row), target)

    def test_real_git_ancestry_does_not_use_build_order(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(promotion, 'STATE', Path(directory)):
            repo = Path(directory) / promotion.SOURCE
            repo.mkdir()
            def git(*args):
                return subprocess.check_output(['git', '-C', str(repo), '-c', 'user.name=fixture',
                    '-c', 'user.email=fixture@example.invalid', *args], stderr=subprocess.DEVNULL).decode().strip()
            git('init', '-b', 'main')
            git('commit', '--allow-empty', '-m', 'First')
            first = git('rev-parse', 'HEAD')
            git('commit', '--allow-empty', '-m', 'Second')
            second = git('rev-parse', 'HEAD')
            self.assertEqual(promotion.source_order(second, first), 'newer')
            self.assertEqual(promotion.source_order(first, second), 'older')
            self.assertEqual(promotion.source_order(first, first), 'same')
            self.assertEqual(promotion.source_order('f'*40, first), 'unknown')
