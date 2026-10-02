"""Check CA preservation, replacement and configuration without touching user trust."""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
import git_ca


def ca(name):
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.now(timezone.utc)
    return (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256()).public_bytes(serialization.Encoding.PEM))


class Trust(unittest.TestCase):
    def test_preserves_standard_roots_and_deduplicates_lab_root(self):
        standard, lab = ca('standard'), ca('lab')
        result, count = git_ca.bundle('# Standard roots — certificate comments\n'.encode('utf-8') + standard + lab, lab)
        self.assertEqual(count, 2)
        self.assertIn(standard.strip(), result)
        self.assertEqual(result.count(lab.strip()), 1)

    def test_rejects_private_keys_and_incomplete_certificates(self):
        lab = ca('lab')
        for value in (b'-----BEGIN PRIVATE KEY-----', b'-----BEGIN CERTIFICATE-----\nbroken'):
            with self.assertRaises(ValueError):
                git_ca.bundle(value, lab)

    def test_refresh_preserves_base_and_replaces_old_lab_ca(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            base, root, output = [folder / name for name in ('base.pem', 'root.pem', 'owned.pem')]
            standard, old, new = ca('standard'), ca('old'), ca('new')
            base.write_bytes(standard); root.write_bytes(old)
            with patch.dict(os.environ, {'GIT_CONFIG_GLOBAL': str(folder / 'gitconfig')}):
                git_ca.install(root, output, base)
                first = output.read_bytes()
                git_ca.install(root, output)
                self.assertEqual(output.read_bytes(), first)
                root.write_bytes(new)
                git_ca.install(root, output)
                self.assertEqual(base.read_bytes(), standard)
                self.assertIn(new.strip(), output.read_bytes())
                self.assertNotIn(old.strip(), output.read_bytes())
                self.assertEqual(git_ca.git('config', '--global', '--get', 'http.sslBackend'), 'openssl')
                self.assertEqual(git_ca.git('config', '--global', '--get', 'http.sslCAInfo'), output.as_posix())


if __name__ == '__main__':
    unittest.main()
