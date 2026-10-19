"""Checkout portability and guarded recovery preserve frozen data identities."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from common import ROOT
from data.contracts import canonical
import catalogue_portability as portability


class CheckoutBytes(unittest.TestCase):
    def test_real_git_checkout_preserves_frozen_bytes_with_both_autocrlf_modes(self):
        paths = ('data/import_esci.py', 'lab/release_million.py',
                 'lab/profiles/esci-informed-uk-v1.json', 'judgements/noop_model.py',
                 'lab/search_target.py',
                 'lab/gatling/src/test/java/lab/relevance/SyntheticSearchSimulation.java',
                 'lab/headlamp-gateway/envoy-base-values.yaml',
                 'lab/headlamp-gateway/envoy-inference-values.yaml')
        self.assertEqual(hashlib.sha256((ROOT / paths[0]).read_bytes()).hexdigest(),
                         portability.IMPORTER)
        # Golden source identities are from retained Windows evidence, not
        # recomputed from whichever checkout the fixture happens to receive.
        golden = {
            paths[1]: '5b35cc8b8cf631622f97dd610ab67e63f289de77b2527db260b6eac30ce17652',
            paths[2]: '98ffa360c406a4929ee47540a124b4b1428a9cb2f1b077b16f55885f7af8a95b',
            paths[3]: 'a92149212463ea72bc07b298deaca5785df7e5f1bfc0befcbe80c1664df2d5b7',
            paths[4]: '769627e2dd904802b52c87734b6965da1dbf52a62874bd02513b125cc8a981e8',
            paths[5]: '6e51c863f63adc5851074a85e37a42d879ffb3454eee07b00e322d699f181592',
        }
        for name, expected_hash in golden.items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected_hash)
        vendor = json.loads((ROOT / 'lab/headlamp-gateway/sources.json').read_text(encoding='utf-8'))
        for name, reference in vendor['values'].items():
            self.assertEqual(hashlib.sha256((ROOT / 'lab/headlamp-gateway' / name).read_bytes()).hexdigest(),
                             reference['sha256'])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def git(*args):
                return subprocess.run(['git', '-C', str(root), *args], check=True,
                                      capture_output=True)
            git('init', '-q')
            (root / '.gitattributes').write_bytes((ROOT / '.gitattributes').read_bytes())
            expected = {}
            for name in paths:
                payload = (ROOT / name).read_bytes()
                expected[name] = payload
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
            git('add', '.gitattributes', *paths)
            for mode in ('false', 'true', 'input'):
                output = root / ('checkout-' + mode)
                output.mkdir()
                git('-c', 'core.autocrlf=' + mode, '-c', 'core.eol=lf',
                    'checkout-index', '--all', '--force', '--prefix=' + output.as_posix() + '/')
                for name, payload in expected.items():
                    self.assertEqual((output / name).read_bytes(), payload, (mode, name))


class Recovery(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.state = Path(self.temporary.name)
        self.importer = self.state / 'importer.py'
        self.importer.write_bytes(b'producer\r\n')
        self.digest = hashlib.sha256(self.importer.read_bytes()).hexdigest()
        self.base = self.state / 'releases' / 'base'
        self.base.mkdir(parents=True)
        hashes = {}
        for name in ('products.jsonl.gz', 'queries.jsonl', 'judgements.jsonl'):
            payload = ('fixture ' + name).encode()
            (self.base / name).write_bytes(payload)
            hashes[name] = hashlib.sha256(payload).hexdigest()
        self.fixed = {'release': 'base', 'importer_sha256': self.digest, 'sha256': hashes}
        self.old = {**self.fixed, 'importer_sha256': portability.LF_IMPORTER}
        (self.base / 'manifest.json').write_bytes(canonical(self.old))
        self.expected = hashlib.sha256(canonical(self.fixed)).hexdigest()
        self.old_sha = hashlib.sha256(canonical(self.old)).hexdigest()
        self.derived = self.state / 'releases' / 'derived'
        self.derived.mkdir()
        for name in hashes:
            (self.derived / name).write_bytes((self.base / name).read_bytes())
        self.manifest = {'release': 'derived', 'sha256': hashes,
                         'producer': {'name': 'esci-demo-timeline-v1',
                                      'source_manifest_sha256': self.old_sha}}
        (self.derived / 'manifest.json').write_bytes(canonical(self.manifest))
        self.artifacts = self.state / 'artifacts-reference' / 'derived'
        self.artifacts.mkdir(parents=True)
        (self.artifacts / 'catalogue.json').write_bytes(canonical({'producer': self.manifest['producer']}))
        for name, value in [('IMPORTER', self.digest), ('MANIFESTS', {'base': self.expected}),
                            ('DERIVED', ('derived',))]:
            patcher = patch.object(portability, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_recovery(self):
        portability.reconcile(self.state, self.importer)

    def test_repairs_only_metadata_and_retains_derived_outputs_then_resumes(self):
        before = {name: (self.base / name).read_bytes() for name in self.fixed['sha256']}
        self.run_recovery()
        self.assertEqual((self.base / 'manifest.json').read_bytes(), canonical(self.fixed))
        self.assertEqual(before, {name: (self.base / name).read_bytes() for name in before})
        saved = self.state / 'portability-recovery'
        self.assertEqual((saved / ('base-' + self.old_sha + '.manifest.json')).read_bytes(), canonical(self.old))
        self.assertTrue((saved / 'releases-derived' / 'manifest.json').is_file())
        self.assertTrue((saved / 'artifacts-reference-derived' / 'catalogue.json').is_file())
        self.assertFalse(self.derived.exists())
        self.run_recovery()

    def test_tampered_data_refuses_before_any_write(self):
        (self.derived / 'queries.jsonl').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'bytes differ'):
            self.run_recovery()
        self.assertEqual((self.base / 'manifest.json').read_bytes(), canonical(self.old))
        self.assertFalse((self.state / 'portability-recovery').exists())

    def test_other_metadata_difference_cannot_be_accepted(self):
        (self.base / 'manifest.json').write_bytes(canonical({**self.old, 'extra': 'changed'}))
        with self.assertRaisesRegex(ValueError, 'beyond checkout line endings'):
            self.run_recovery()
        self.assertTrue(self.derived.exists())

    def test_orphan_artifacts_after_interrupted_move_are_retained(self):
        self.run_recovery()
        saved = self.state / 'portability-recovery' / 'artifacts-reference-derived'
        saved.rename(self.artifacts)
        self.run_recovery()
        self.assertTrue(saved.is_dir())

    def test_unexpected_importer_and_mixed_artifacts_are_rejected(self):
        self.importer.write_bytes(b'other')
        with self.assertRaisesRegex(ValueError, 'importer bytes differ'):
            self.run_recovery()
        self.importer.write_bytes(b'producer\r\n')
        (self.artifacts / 'judgement-set.json').write_bytes(canonical({'producer': {}}))
        with self.assertRaisesRegex(ValueError, 'Mixed retained'):
            self.run_recovery()
        self.assertEqual((self.base / 'manifest.json').read_bytes(), canonical(self.old))


if __name__ == '__main__':
    unittest.main()
