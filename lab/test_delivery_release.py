"""Consequential release-integrity boundaries, independent of Nexus availability."""
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import json
from unittest.mock import patch

from delivery.ci.release import bundle, canonical, digest, validate
from delivery_release import validate_bundle
import delivery_release


class ReleaseIntegrityTests(unittest.TestCase):
    def test_original_receipt_bytes_survive_verification(self):
        receipt = {'release_id': 'r', 'source_sha': 'a' * 40, 'event_kind': 'pull_request',
                   'source_repository': 'elastic-agent/delivery-source', 'image': 'image',
                   'run_id': 106, 'run_attempt': 1}
        payload = json.dumps(receipt, indent=3).encode()  # Deliberately not canonical.
        run = {'status': 'completed', 'conclusion': 'success', 'head_sha': 'a' * 40,
               'event': 'pull_request', 'id': 106, 'run_attempt': 1}
        with patch.object(delivery_release, 'api', return_value=run), \
                patch.object(delivery_release, 'request', return_value=payload), \
                patch.object(delivery_release, 'load', return_value=(receipt, {})):
            self.assertEqual(delivery_release.from_run_bytes(106)[3], payload)

    def fixture(self, root):
        worker = b'print("indexer")\n'
        contract = {'engine_version': '9.5.4', 'definitions': [{'mappings': {}, 'settings': {}}],
                    'indexer_image': 'python@sha256:' + '1' * 64, 'indexer_source_sha256': digest(worker)}
        files = {'chart/Chart.yaml': b'name: search\n', 'chart/templates/environment.yaml': b'kind: Deployment\n',
                 'contracts/index.json': canonical(contract), 'contracts/indexer.py': worker,
                 'app/app.py': b'print("API")\n', 'app/index.html': b'<html></html>'}
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        content, hashes = bundle(root)
        release = {'format': 1, 'source_sha': 'a' * 40, 'source_repository': 'owner/source',
                   'image': 'registry/search@sha256:' + 'b' * 64, 'bundle_sha256': digest(content),
                   'files': hashes, 'index_contract': contract}
        return release, content

    def test_repeat_bundle_and_modified_query_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release, content = self.fixture(root)
            validate(release)
            self.assertEqual(content, bundle(root)[0])
            validate_bundle(release, content)
            (root / 'app/app.py').write_bytes(b'print("changed ranking")')
            self.assertNotEqual(digest(content), digest(bundle(root)[0]))
            with self.assertRaisesRegex(ValueError, 'checksum'):
                validate_bundle(release, bundle(root)[0])

    def test_mutable_image_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            release, _ = self.fixture(Path(directory))
            release['image'] = 'registry/search:main'
            with self.assertRaisesRegex(ValueError, 'digest'):
                validate(release)

    def test_tampered_index_contract_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            release, content = self.fixture(Path(directory))
            release['index_contract']['engine_version'] = '10.0.0'
            with self.assertRaisesRegex(ValueError, 'contract differs'):
                validate_bundle(release, content)

    def test_traversal_rejected_even_with_matching_archive_hash(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            info = tarfile.TarInfo('../outside')
            info.size = 1
            archive.addfile(info, io.BytesIO(b'x'))
        content = stream.getvalue()
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            validate_bundle({'bundle_sha256': digest(content)}, content)


if __name__ == '__main__':
    unittest.main()
