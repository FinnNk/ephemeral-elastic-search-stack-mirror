"""Verify SemVer precedence, immutable publication and source-tag identity."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from delivery.ci import release
from delivery.ci.versioning import parse, compare, declared, build_version
import delivery_versions
from gitea import GiteaHTTPError
import test_delivery_release


class VersionTests(unittest.TestCase):
    def test_official_precedence_sequence_and_numeric_order(self):
        values = ['1.0.0-alpha', '1.0.0-alpha.1', '1.0.0-alpha.beta', '1.0.0-beta',
                  '1.0.0-beta.2', '1.0.0-beta.11', '1.0.0-rc.1', '1.0.0', '1.0.1', '1.1.0', '1.10.0', '2.0.0']
        for left, right in zip(values, values[1:]):
            self.assertEqual(compare(left, right), -1)
            self.assertEqual(compare(right, left), 1)
        self.assertEqual(compare('1.0.0+build.10', '1.0.0+build.20'), 0)
        self.assertEqual(compare('1.0.0-pr.31.10.1', '1.0.0-pr.31.2.1'), 1)

    def test_invalid_versions_are_rejected(self):
        for version in ('1.2', 'v1.2.3', '01.2.3', '1.2.3-01', '1.2.3+', '1.2.3-foo..bar', None):
            with self.subTest(version=version), self.assertRaises(ValueError): parse(version)

    def test_declared_version_and_build_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, 'VERSION'): declared(root)
            (root/'VERSION').write_text('1.2.0\n')
            self.assertEqual(declared(root), '1.2.0')
            (root/'VERSION').write_text('1.2.0-rc.1\n')
            with self.assertRaises(ValueError): declared(root)
        self.assertEqual(build_version('1.2.0', 'push', 158, 1), '1.2.0+build.158.1')
        self.assertEqual(build_version('1.2.0', 'pull_request', 157, 2, 31), '1.2.0-pr.31.157.2')
        with self.assertRaises(ValueError): build_version('1.2.0', 'pull_request', 157, 1)

    def test_version_file_is_part_of_the_verified_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            test_delivery_release.ReleaseIntegrityTests().fixture(root)
            (root/'VERSION').write_bytes(b'1.0.0\n')
            content, files = release.bundle(root)
            self.assertEqual(files['VERSION'], release.digest(b'1.0.0\n'))
            (root/'VERSION').write_bytes(b'1.1.0\n')
            self.assertNotEqual(content, release.bundle(root)[0])

    def test_main_publication_reserves_source_tree_before_build_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            test_delivery_release.ReleaseIntegrityTests().fixture(root)
            (root/'VERSION').write_bytes(b'1.0.0\n')
            (root/'image-metadata.json').write_text(json.dumps({'containerimage.digest': 'sha256:'+'a'*64}))
            environment = {'SOURCE_SHA': 'b'*40, 'SOURCE_TREE': 'c'*40, 'SOURCE_REPOSITORY': 'elastic-agent/delivery-source',
                'EVENT_KIND': 'push', 'RUN_ID': '158', 'RUN_ATTEMPT': '1', 'REGISTRY': 'registry',
                'ARTIFACT_URL': 'https://artifacts.test', 'NEXUS_USER': 'fixture', 'NEXUS_PASSWORD': 'fixture'}
            calls = []
            with patch.object(release.Path, 'cwd', return_value=root), patch.dict(release.os.environ, environment), \
                    patch.object(release, 'publish', side_effect=lambda base,path,content,*args: calls.append((path,content))):
                release.main()
            self.assertEqual(calls[-2][0], 'versions/1.0.0.json')
            claim = json.loads(calls[-2][1])
            self.assertEqual(claim['source_tree'], 'c'*40)
            self.assertNotIn('source_sha', claim)  # Empty commits can reuse a source tree.
            self.assertTrue(calls[-1][0].startswith('builds/'))
            with patch.object(release.Path, 'cwd', return_value=root), patch.dict(release.os.environ, environment), \
                    patch.object(release, 'publish', side_effect=lambda base,path,*args: (_ for _ in ()).throw(ValueError('immutable')) if path.startswith('versions/') else None):
                with self.assertRaises(ValueError): release.main()

    def test_preview_does_not_reserve_stable_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            test_delivery_release.ReleaseIntegrityTests().fixture(root)
            (root/'VERSION').write_bytes(b'1.0.0\n')
            (root/'image-metadata.json').write_text(json.dumps({'containerimage.digest': 'sha256:'+'a'*64}))
            env={'SOURCE_SHA':'b'*40,'SOURCE_TREE':'c'*40,'SOURCE_REPOSITORY':'elastic-agent/delivery-source',
                'EVENT_KIND':'pull_request','PR_NUMBER':'31','RUN_ID':'157','RUN_ATTEMPT':'1',
                'REGISTRY':'registry','ARTIFACT_URL':'https://artifacts.test','NEXUS_USER':'fixture','NEXUS_PASSWORD':'fixture'}
            with patch.object(release.Path,'cwd',return_value=root),patch.dict(release.os.environ,env),patch.object(release,'publish') as put:
                release.main()
            claim = next(c for c in put.call_args_list if c.args[1].startswith('versions/'))
            self.assertTrue(claim.args[5])
            self.assertEqual(json.loads(put.call_args.args[2])['version'],'1.0.0-pr.31.157.1')

    def tag_fixture(self):
        return {'event_kind':'push','release_id':'d'*64}, {'version':'1.0.0+build.158.1','declared_version':'1.0.0',
            'source_repository':'elastic-agent/delivery-source','source_sha':'a'*40,'source_tree':'b'*40}

    def test_tag_is_created_once_and_rebuild_does_not_move_it(self):
        receipt, descriptor=self.tag_fixture()
        claim=release.canonical({'version':'1.0.0','source_repository':descriptor['source_repository'],'source_tree':'b'*40})
        commit={'commit':{'tree':{'sha':'b'*40}}}
        responses=[commit,GiteaHTTPError('GET','/tags/v1.0.0',404),{}, {'commit':{'sha':'a'*40}},commit]
        with patch.object(delivery_versions,'request',return_value=claim), patch.object(delivery_versions,'api',side_effect=responses) as api:
            self.assertEqual(delivery_versions.ensure_tag(receipt,descriptor)['tag'],'v1.0.0')
            self.assertEqual(api.call_args_list[2].args[1],'POST')
        # A different commit with the same tree keeps the original tag target.
        descriptor['source_sha']='c'*40
        with patch.object(delivery_versions,'request',return_value=claim), patch.object(delivery_versions,'api',side_effect=[commit,{'commit':{'sha':'a'*40}},commit]) as api:
            self.assertEqual(delivery_versions.ensure_tag(receipt,descriptor)['source_sha'],'a'*40)
            self.assertTrue(all(len(c.args)==1 for c in api.call_args_list))

    def test_conflicting_tag_or_version_claim_is_rejected(self):
        receipt, descriptor=self.tag_fixture()
        with patch.object(delivery_versions,'request',return_value=b'other'),patch.object(delivery_versions,'api') as api:
            with self.assertRaises(ValueError):delivery_versions.ensure_tag(receipt,descriptor)
            api.assert_not_called()
        claim=release.canonical({'version':'1.0.0','source_repository':descriptor['source_repository'],'source_tree':'b'*40})
        with patch.object(delivery_versions,'request',return_value=claim),patch.object(delivery_versions,'api',side_effect=[
                {'commit':{'tree':{'sha':'b'*40}}},{'commit':{'sha':'e'*40}},{'commit':{'tree':{'sha':'f'*40}}}]):
            with self.assertRaisesRegex(ValueError,'retarget'):delivery_versions.ensure_tag(receipt,descriptor)
