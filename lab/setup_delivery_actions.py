"""Configure scoped Actions credentials and device sign-in for remote lab delivery."""
import json
from urllib.parse import urlencode

from common import STATE, apply, guard, k
from delivery_provider import SOURCE, api as source_api, endpoint
from install_oidc import ISSUER, admin_token, api, realm, vault_secret
from keyvault import external_secret, floci_forward, seed, source_name, value_of, vault_request
from nexus import credentials
from delivery.ci.release import digest
from common import ROOT


def clients(secret):
    audience = {'name': 'lab-control-audience', 'protocol': 'openid-connect',
        'protocolMapper': 'oidc-audience-mapper', 'config': {'included.client.audience': 'lab-control',
            'access.token.claim': 'true', 'id.token.claim': 'false'}}
    common = {'protocol': 'openid-connect', 'enabled': True, 'standardFlowEnabled': False,
              'directAccessGrantsEnabled': False}
    return [
        {**common, 'clientId': 'lab-delivery-cli', 'publicClient': True,
         'attributes': {'oauth2.device.authorization.grant.enabled': 'true'},
         'protocolMappers': [realm()['clients'][0]['protocolMappers'][0], audience]},
        {**common, 'clientId': 'lab-delivery-actions', 'publicClient': False, 'secret': secret,
         'serviceAccountsEnabled': True, 'fullScopeAllowed': False,
         'protocolMappers': [audience, {'name': 'delivery-scope', 'protocol': 'openid-connect',
            'protocolMapper': 'oidc-hardcoded-claim-mapper', 'config': {'claim.name': 'groups',
                'claim.value': '["lab-delivery-actions"]', 'jsonType.label': 'JSON',
                'access.token.claim': 'true', 'id.token.claim': 'false'}}]}]


def install():
    """Run after the accepted source workflows and coordinator image are installed."""
    guard()
    secret = value_of(vault_secret('platform', 'delivery-actions-client', ['clientSecret']), 'clientSecret')
    token = admin_token()
    for definition in clients(secret):
        found = api('/admin/realms/relevance-lab/clients?' + urlencode({'clientId': definition['clientId']}), token=token)
        if found:
            api('/admin/realms/relevance-lab/clients/' + found[0]['id'], 'PUT', {**found[0], **definition}, token)
        else:
            api('/admin/realms/relevance-lab/clients', 'POST', definition, token)
    publisher = credentials()['publisher']
    values = {'LAB_NEXUS_PUBLISH_USER': publisher['username'], 'LAB_NEXUS_PUBLISH_PASSWORD': publisher['password']}
    with floci_forward() as base:
        for name in ('LAB_VARIANT_EVIDENCE_KEY', 'LAB_VARIANT_APPROVAL_KEY'):
            record = vault_request(base, 'lab-variant-gate-' + name.lower().replace('_', '-'))
            if record is None:
                raise ValueError('Set up the variant gate keys before remote Actions.')
            values[name] = record['value']
        for name, value in values.items():
            seed(base, source_name('lab-control', 'delivery-publisher', name), value)
    external_secret('lab-control', 'delivery-publisher', list(values))
    apply({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {
        'name': 'delivery-runner-ca', 'namespace': 'platform'}, 'data': {
            'root.pem': (STATE / 'https-ingress/root.pem').read_text(encoding='ascii')}})
    patch = {'spec': {'template': {'spec': {'containers': [
        {'name': name, 'envFrom': [{'configMapRef': {'name': 'lab-control-config'}},
                                 {'secretRef': {'name': 'delivery-publisher'}}]}
        for name in ('api', 'delivery-watcher')]}}}}
    k('patch', 'deployment/lab-control', '-n', 'lab-control', '--type=strategic', '-p', json.dumps(patch))
    source_api(endpoint(SOURCE, '/actions/secrets/LAB_DELIVERY_CLIENT_SECRET'), 'PUT', {'data': secret})
    edge = json.loads(k('get', 'service/lab-oidc-edge', '-n', 'lab-ingress', '-o', 'json').stdout)['spec']['clusterIP']
    existing = {row['name'] for row in source_api(endpoint(SOURCE, '/actions/variables'))}
    for name, value in {'LAB_DELIVERY_URL': 'https://control.localhost:34443',
                        'LAB_OIDC_ISSUER': ISSUER, 'LAB_OIDC_EDGE_IP': edge,
                        'LAB_DELIVERY_CLIENT_SHA256': digest((ROOT / 'lab/delivery/ci/lab_delivery.py').read_bytes())}.items():
        source_api(endpoint(SOURCE, '/actions/variables/' + name), 'PUT' if name in existing else 'POST', {'value': value})
    # Signing belongs to the coordinator. Source workflows receive only the
    # delivery client credential and their existing release publishing credential.
    for name in ('LAB_VARIANT_EVIDENCE_KEY', 'LAB_VARIANT_APPROVAL_KEY'):
        source_api(endpoint(SOURCE, '/actions/secrets/' + name), 'DELETE')
    k('rollout', 'status', 'deployment/lab-control', '-n', 'lab-control', '--timeout=240s')
    print('Remote delivery authentication configured. Run ci/lab_delivery.py login to sign in.')


if __name__ == '__main__':
    install()
