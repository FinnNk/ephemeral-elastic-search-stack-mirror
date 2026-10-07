"""Verify retained transport preserves source identity and recovers failed downloads."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zstandard
import esci_sources as sources


class RetainedSources(unittest.TestCase):
    def fixture(self, root, encoding='identity'):
        raw = b'original product records\n' * 20
        item = {'file': 'products.parquet', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'url': 'https://original.example/products'}
        payload = zstandard.ZstdCompressor().compress(raw) if encoding == 'zstd' else raw
        parts = [payload] if encoding == 'zstd' else [payload[:50], payload[50:]]
        assets = [{'name': 'products.parquet.part' + str(i), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for i, data in enumerate(parts)]
        (root / 'data').mkdir()
        (root / 'data/esci-sources.json').write_text(json.dumps({'files': [item]}), encoding='utf-8')
        manifest = root / 'manifest.json'
        manifest.write_text(json.dumps({'schema_version': 1, 'repository': 'FinnNk/esci-s', 'release': 'lab-sources-v1', 'files': [{**item, 'encoding': encoding, 'assets': assets}]}), encoding='utf-8')
        return raw, parts, manifest

    def test_identity_chunks_and_zstd_reconstruct_exact_original(self):
        for encoding in ('identity', 'zstd'):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                raw, parts, manifest = self.fixture(root, encoding)
                with patch.object(sources, 'ROOT', root), patch.object(sources.urllib.request, 'urlopen', side_effect=[io.BytesIO(data) for data in parts]) as remote:
                    sources.restore(root / 'cache', manifest)
                    self.assertEqual((root / 'cache/products.parquet').read_bytes(), raw)
                    sources.restore(root / 'cache', manifest)
                    self.assertEqual(remote.call_count, len(parts))

    def test_failed_later_asset_reuses_verified_first_chunk(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw, parts, manifest = self.fixture(root)
            with patch.object(sources, 'ROOT', root):
                with patch.object(sources.urllib.request, 'urlopen', side_effect=[io.BytesIO(parts[0]), OSError('offline')]):
                    with self.assertRaises(OSError):
                        sources.restore(root / 'cache', manifest)
                self.assertFalse((root / 'cache/products.parquet').exists())
                with patch.object(sources.urllib.request, 'urlopen', return_value=io.BytesIO(parts[1])) as remote:
                    sources.restore(root / 'cache', manifest)
                    self.assertEqual(remote.call_count, 1)
                self.assertEqual((root / 'cache/products.parquet').read_bytes(), raw)

    def test_corrupt_download_never_publishes_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw, parts, manifest = self.fixture(root)
            with patch.object(sources, 'ROOT', root), patch.object(sources.urllib.request, 'urlopen', return_value=io.BytesIO(b'x' * len(parts[0]))):
                with self.assertRaisesRegex(ValueError, 'checksum'):
                    sources.restore(root / 'cache', manifest)
            self.assertFalse((root / 'cache/products.parquet').exists())
            self.assertFalse(list((root / 'cache').rglob('*.download')))

    def test_changed_source_identity_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw, parts, manifest = self.fixture(root)
            value = json.loads(manifest.read_text(encoding='utf-8'))
            value['files'][0]['sha256'] = '0' * 64
            manifest.write_text(json.dumps(value), encoding='utf-8')
            with patch.object(sources, 'ROOT', root), patch.object(sources.urllib.request, 'urlopen') as remote:
                with self.assertRaisesRegex(ValueError, 'identity'):
                    sources.restore(root / 'cache', manifest)
                remote.assert_not_called()


if __name__ == '__main__':
    unittest.main()
