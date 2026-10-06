"""Host portability and retained-state checks using disposable files only."""
import importlib.util
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import common
import mac_preflight

spec = importlib.util.spec_from_file_location('transfer_install', Path(__file__).parent / 'control-runtime/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class MacTransfer(unittest.TestCase):
    def test_path_tools_without_bundled_executables(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(common, 'STATE', Path(temporary)), \
                patch.object(common.os, 'name', 'posix'), patch.object(common.shutil, 'which', return_value='/opt/homebrew/bin/k3d'):
            self.assertEqual(common.host_tool('k3d'), '/opt/homebrew/bin/k3d')

    def test_manifest_support_is_not_inferred_from_a_tag(self):
        self.assertEqual(mac_preflight.platforms({'config': {'digest': 'example'}}), [])
        self.assertEqual(mac_preflight.platforms({'Descriptor': {'platform': {'os': 'linux', 'architecture': 'amd64'}}}), ['linux/amd64'])
        self.assertEqual(mac_preflight.platforms({'manifests': [
            {'platform': {'os': 'linux', 'architecture': 'arm64'}},
            {'platform': {'os': 'unknown', 'architecture': 'unknown'}},
        ]}), ['linux/arm64'])

    def test_both_databases_preserve_uncheckpointed_operations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, destination = root / 'source', root / 'destination'
            source.mkdir()
            for name in ('releases', 'state-source', 'delivery-state', 'delivery', 'evidence'):
                (source / name).mkdir()
                (source / name / 'example.json').write_text('{}', encoding='utf-8')
            connections = []
            try:
                for name in ('lifecycle.sqlite3', 'delivery-operations.sqlite3'):
                    connection = sqlite3.connect(source / name)
                    connections.append(connection)
                    connection.execute('pragma journal_mode=wal')
                    connection.execute('create table retained(value text)')
                    connection.execute('insert into retained values (?)', ('queued operation',))
                    connection.commit()
                bundle = root / 'backup.tar.gz'
                with patch.object(installer, 'STATE', source):
                    digest = installer.write_bundle(bundle)
                with tarfile.open(bundle) as archive:
                    self.assertIn('delivery-operations.sqlite3', archive.getnames())
                    self.assertNotIn('delivery-operations.sqlite3-wal', archive.getnames())
                with patch.object(installer, 'STATE', destination):
                    self.assertEqual(installer.import_bundle(bundle), digest)
                    with self.assertRaisesRegex(ValueError, 'State already exists'):
                        installer.import_bundle(bundle)
                for name in ('lifecycle.sqlite3', 'delivery-operations.sqlite3'):
                    with closing(sqlite3.connect(destination / name)) as restored:
                        self.assertEqual(restored.execute('select value from retained').fetchone()[0], 'queued operation')
                # The PVC exporter uses this same script after its writers stop.
                with patch.object(sys, 'argv', ['checkpoint', str(source)]):
                    exec(installer.CHECKPOINT_SCRIPT, {})
                for name in ('lifecycle.sqlite3', 'delivery-operations.sqlite3'):
                    wal = source / (name + '-wal')
                    self.assertTrue(not wal.exists() or wal.stat().st_size == 0)
            finally:
                for connection in connections:
                    connection.close()


if __name__ == '__main__':
    unittest.main()
