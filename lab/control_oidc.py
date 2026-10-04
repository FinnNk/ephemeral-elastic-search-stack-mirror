"""Verify control API OIDC tokens; never trust forwarded identity headers."""
import json
import os
import ssl
from urllib.request import urlopen
from urllib.parse import urlparse

import jwt


class OIDCIdentity:
    def __init__(self, issuer=None, audience=None, ca_file=None):
        self.issuer = issuer or os.environ['LAB_OIDC_ISSUER']
        self.audience = audience or os.environ.get('LAB_OIDC_AUDIENCE', 'lab-control')
        self.context = ssl.create_default_context(cafile=ca_file or os.environ.get('LAB_OIDC_CA_FILE'))
        if urlparse(self.issuer).scheme != 'https':
            raise ValueError('OIDC issuer must use HTTPS.')
        self.keys = None

    def verify(self, token):
        if self.keys is None:
            with urlopen(self.issuer + '/.well-known/openid-configuration', context=self.context, timeout=8) as response:
                configuration = json.load(response)
            if configuration['issuer'] != self.issuer or urlparse(configuration['jwks_uri']).netloc != urlparse(self.issuer).netloc:
                raise ValueError('OIDC discovery does not match the configured issuer.')
            if urlparse(configuration['jwks_uri']).scheme != 'https':
                raise ValueError('OIDC signing keys must use HTTPS.')
            self.keys = jwt.PyJWKClient(configuration['jwks_uri'], ssl_context=self.context, timeout=8)
        signing_key = self.keys.get_signing_key_from_jwt(token)
        claims = jwt.decode(token, signing_key.key, algorithms=['RS256'], audience=self.audience,
                            issuer=self.issuer, options={'require': ['exp', 'iat', 'sub', 'iss', 'aud']})
        groups = claims.get('groups', [])
        if not isinstance(groups, list) or not all(isinstance(group, str) for group in groups):
            raise ValueError('Invalid OIDC group claim.')
        admin = 'lab-admins' in groups
        delivery = 'lab-delivery-actions' in groups and claims.get('azp') == 'lab-delivery-actions'
        if not admin and not delivery and 'lab-readers' not in groups:
            raise ValueError('A lab group is required.')
        username = claims.get('preferred_username')
        if not isinstance(username, str) or not username or not isinstance(claims['sub'], str) or not claims['sub']:
            raise ValueError('OIDC identity is incomplete.')
        return {'username': username, 'is_admin': admin, 'is_reader': not admin and not delivery,
                'is_delivery_service': delivery,
                'issuer': self.issuer, 'subject': claims['sub'], 'audience': self.audience}
