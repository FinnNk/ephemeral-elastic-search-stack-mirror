"""Build a separate analyser variant from the frozen Blob, using a Kubernetes Job."""
import json, secrets, time
from datetime import datetime, timedelta, timezone
from common import *
from data_contract import elastic, DEMO_KEY
from azure.storage.blob import generate_blob_sas, BlobSasPermissions

guard()
index = 'spike-analyser-v2'
manifest = json.loads((EVIDENCE / 'dataset.json').read_text())
password = secrets.token_urlsafe(24)
started = time.monotonic()
elastic('/' + index, 'PUT', {
    'settings': {'number_of_replicas': 0, 'analysis': {'analyzer': {'retail': {'type': 'standard', 'stopwords': ['model']}}}},
    'mappings': {'properties': {'product_id': {'type': 'keyword'}, 'title': {'type': 'text', 'analyzer': 'retail'}}},
})
elastic('/_security/role/spike-indexer', 'PUT', {'indices': [{'names': [index], 'privileges': ['write']} ]})
elastic('/_security/user/spike-indexer', 'PUT', {'password': password, 'roles': ['spike-indexer']})
blob = manifest['sha256'] + '/products.jsonl'
sas = generate_blob_sas('devstoreaccount1', 'datasets', blob, account_key=DEMO_KEY,
    permission=BlobSasPermissions(read=True), expiry=datetime.now(timezone.utc) + timedelta(minutes=15))
apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'index-job', 'namespace': 'platform'}, 'stringData': {
    'ES_USER': 'spike-indexer', 'ES_PASSWORD': password, 'ES_INDEX': index,
    'DATASET_URL': 'http://floci.platform.svc:4577/devstoreaccount1/datasets/' + blob + '?' + sas,
    'DATASET_SHA256': manifest['sha256'],
}})
cert = json.loads(k('get', 'secret/shared-es-http-certs-public', '-n', 'platform', '-o', 'json').stdout)['data']
apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'index-ca', 'namespace': 'platform'}, 'data': cert})
apply({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'index-job', 'namespace': 'platform'},
       'data': {'index_job.py': (ROOT / 'research/platform-spike/index_job.py').read_text()}})
apply({'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': {'name': 'spike-index', 'namespace': 'platform'},
       'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 120, 'template': {'spec': {
           'automountServiceAccountToken': False, 'restartPolicy': 'Never',
           'containers': [{'name': 'index', 'image': 'python:3.13.7-alpine3.22', 'command': ['python', '/source/index_job.py'],
               'envFrom': [{'secretRef': {'name': 'index-job'}}],
               'resources': {'requests': {'cpu': '100m', 'memory': '64Mi'}, 'limits': {'cpu': '1', 'memory': '256Mi'}},
               'securityContext': {'runAsNonRoot': True, 'runAsUser': 1000, 'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}},
               'volumeMounts': [{'name': 'source', 'mountPath': '/source'}, {'name': 'ca', 'mountPath': '/es-ca'}]}],
           'volumes': [{'name': 'source', 'configMap': {'name': 'index-job'}}, {'name': 'ca', 'secret': {'secretName': 'index-ca'}}],
       }}}})
try:
    k('wait', '--for=condition=complete', 'job/spike-index', '-n', 'platform', '--timeout=135s')
    result = json.loads(k('logs', 'job/spike-index', '-n', 'platform').stdout)
    assert result['indexed'] == 10000
    elastic('/' + index + '/_settings', 'PUT', {'index.blocks.write': True})
    counts = {name: elastic('/' + name + '/_search', 'POST', {'query': {'match': {'title': 'model'}}})['hits']['total']['value']
              for name in ['spike-frozen-v1', index]}
    assert counts == {'spike-frozen-v1': 10000, index: 0}, counts
    record('index-job', {'index': index, 'dataset_sha256': manifest['sha256'], 'count': result['indexed'],
        'seconds': round(time.monotonic() - started, 3), 'query_model_hits': counts,
        'blob_access': '15-minute read SAS for one object', 'es_privileges': 'write on dedicated index only',
        'write_block_after_indexing': True, 'sample_size': 1})
    print('Dedicated analyser index built and frozen; expected search difference verified.')
finally:
    elastic('/_security/user/spike-indexer', 'DELETE')
    elastic('/_security/role/spike-indexer', 'DELETE')
    k('delete', 'secret/index-job', '-n', 'platform', '--ignore-not-found')
