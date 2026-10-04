import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from control_oidc import OIDCIdentity


class SignedIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.provider = OIDCIdentity('https://identity.example/realm', 'lab-control')
        self.provider.keys = Mock(get_signing_key_from_jwt=Mock(return_value=SimpleNamespace(key=self.key.public_key())))
        self.claims = {'iss': self.provider.issuer, 'aud': 'lab-control', 'sub': 'immutable-user',
                       'iat': int(time.time()), 'exp': int(time.time()) + 60,
                       'preferred_username': 'renamable-user', 'groups': ['lab-readers']}

    def verify(self, claims=None, key=None):
        return self.provider.verify(jwt.encode(claims or self.claims, key or self.key, algorithm='RS256'))

    def test_reader_and_administrator(self):
        self.assertTrue(self.verify()['is_reader'])
        self.claims['groups'] = ['lab-admins']
        self.assertTrue(self.verify()['is_admin'])
        self.assertEqual(self.verify()['subject'], 'immutable-user')

    def test_invalid_signed_claims(self):
        for field, value in [('exp', int(time.time()) - 1), ('iss', 'https://other.example/realm'),
                             ('aud', 'another-app'), ('groups', []), ('groups', 'lab-admins'),
                             ('preferred_username', ''), ('sub', '')]:
            with self.subTest(field=field), self.assertRaises((ValueError, jwt.PyJWTError)):
                self.verify({**self.claims, field: value})

    def test_forged_signature(self):
        with self.assertRaises(jwt.InvalidSignatureError):
            self.verify(key=rsa.generate_private_key(public_exponent=65537, key_size=2048))

    def test_actions_group_requires_the_scoped_client(self):
        self.claims['groups'] = ['lab-delivery-actions']
        self.claims['azp'] = 'lab-delivery-actions'
        identity = self.verify()
        self.assertTrue(identity['is_delivery_service'])
        self.assertFalse(identity['is_admin'])
        self.assertFalse(identity['is_reader'])
        self.claims['azp'] = 'another-client'
        with self.assertRaises(ValueError):
            self.verify()

    def test_http_issuer_rejected(self):
        with self.assertRaises(ValueError):
            OIDCIdentity('http://identity.example/realm', 'lab-control')
