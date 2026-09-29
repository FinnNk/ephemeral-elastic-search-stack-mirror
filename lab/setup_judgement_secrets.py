"""Create model-registry and judgement-input credentials in Floci Key Vault."""

import json
import secrets
import subprocess

from common import STATE, apply, guard
from keyvault import (external_secret, floci_forward, source_name,
                      vault_request)
from blob_config import DEMO_KEY

NAMESPACE = 'lab-models'


def put(base, name, key, value):
    remote = source_name(NAMESPACE, name, key)
    current = vault_request(base, remote)
    if current is None or current['value'] != value:
        vault_request(base, remote, 'PUT', value)


def configure():
    guard()
    apply({'apiVersion': 'v1', 'kind': 'Namespace',
           'metadata': {'name': NAMESPACE,
                        'labels': {'app.kubernetes.io/part-of': 'relevance-lab'}}})
    s3 = json.loads((STATE / 'snapshot-s3.json').read_text(encoding='utf-8'))
    with floci_forward() as base:
        password_key = source_name(NAMESPACE, 'mlflow-db', 'password')
        existing = vault_request(base, password_key)
        password = existing['value'] if existing else secrets.token_urlsafe(30)
        uri = 'postgresql+psycopg2://mlflow:' + password + '@mlflow-postgres.lab-models.svc:5432/mlflow'
        put(base, 'mlflow-db', 'password', password)
        put(base, 'mlflow-db', 'uri', uri)
        put(base, 'mlflow-s3', 'AWS_ACCESS_KEY_ID', s3['access_key'])
        put(base, 'mlflow-s3', 'AWS_SECRET_ACCESS_KEY', s3['secret_key'])
        connection = ('DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;'
                      'AccountKey=' + DEMO_KEY + ';'
                      'BlobEndpoint=http://floci.platform.svc:4577/devstoreaccount1;')
        put(base, 'judgement-blob', 'DATA_BLOB_CONNECTION_STRING', connection)
    external_secret(NAMESPACE, 'mlflow-db', ['password', 'uri'])
    external_secret(NAMESPACE, 'mlflow-s3', ['AWS_ACCESS_KEY_ID',
                                            'AWS_SECRET_ACCESS_KEY'])
    external_secret(NAMESPACE, 'judgement-blob', ['DATA_BLOB_CONNECTION_STRING'])
    external_secret(NAMESPACE, 'nexus-read', ['.dockerconfigjson'],
                    secret_type='kubernetes.io/dockerconfigjson')
    details = json.loads(subprocess.run(['docker', 'inspect', 'relevance-snapshot-store'],
        capture_output=True, text=True, encoding='utf-8', check=True).stdout)[0]
    address = details['NetworkSettings']['Networks']['k3d-relevance-lab']['IPAddress']
    apply({'apiVersion': 'v1', 'kind': 'Service',
           'metadata': {'name': 'model-artifacts', 'namespace': NAMESPACE},
           'spec': {'ports': [{'name': 's3', 'port': 8333, 'targetPort': 8333}]}})
    apply({'apiVersion': 'discovery.k8s.io/v1', 'kind': 'EndpointSlice',
           'metadata': {'name': 'model-artifacts', 'namespace': NAMESPACE,
                        'labels': {'kubernetes.io/service-name': 'model-artifacts',
                                   'endpointslice.kubernetes.io/managed-by': 'relevance-lab'}},
           'addressType': 'IPv4', 'ports': [{'name': 's3', 'port': 8333,
                                           'protocol': 'TCP'}],
           'endpoints': [{'addresses': [address], 'conditions': {'ready': True}}]})
    return {'namespace': NAMESPACE, 'secrets': ['mlflow-db', 'mlflow-s3',
                                                'judgement-blob', 'nexus-read'],
            's3_service': 'model-artifacts'}


if __name__ == '__main__':
    print(json.dumps(configure(), sort_keys=True))
