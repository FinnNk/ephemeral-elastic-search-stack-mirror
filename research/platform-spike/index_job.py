"""Finite indexing worker; the job receives one Blob URL and one index credential."""
import base64, hashlib, json, os, ssl, urllib.request

with urllib.request.urlopen(os.environ['DATASET_URL'], timeout=30) as response:
    data = response.read()
assert hashlib.sha256(data).hexdigest() == os.environ['DATASET_SHA256']
lines = []
for line in data.decode().splitlines():
    product = json.loads(line)
    lines.extend([json.dumps({'index': {'_id': product['product_id']}}), line])
auth = base64.b64encode((os.environ['ES_USER'] + ':' + os.environ['ES_PASSWORD']).encode()).decode()
request = urllib.request.Request(
    'https://shared-es-http.platform.svc:9200/' + os.environ['ES_INDEX'] + '/_bulk?refresh=true',
    data=('\n'.join(lines) + '\n').encode(),
    headers={'Authorization': 'Basic ' + auth, 'Content-Type': 'application/x-ndjson'},
)
with urllib.request.urlopen(request, context=ssl.create_default_context(cafile='/es-ca/tls.crt'), timeout=60) as response:
    result = json.load(response)
assert not result['errors']
print(json.dumps({'indexed': len(lines) // 2, 'dataset_sha256': os.environ['DATASET_SHA256']}))
