"""Registered model hashes must agree between Windows packaging and Linux serving."""

import hashlib
from pathlib import Path
import tempfile
import unittest

from fetch_model import tree_digest


class ModelDigestTests(unittest.TestCase):
    def test_posix_case_sensitive_order_and_identity_exclusion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('a', 'MLmodel', 'z'):
                (root / name).write_bytes(name.encode())
            (root / '.model-identity.json').write_text('ignored')
            expected = hashlib.sha256(b'MLmodel\0MLmodela\0az\0z').hexdigest()
            self.assertEqual(tree_digest(root), expected)


if __name__ == '__main__':
    unittest.main()
