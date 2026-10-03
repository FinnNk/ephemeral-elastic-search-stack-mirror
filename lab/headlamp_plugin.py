"""Mount the supplied KServe plugin in Headlamp without extra runtime permissions."""
import hashlib
import json
import tarfile
from pathlib import PurePosixPath

from common import ROOT, apply

ARCHIVE = ROOT / 'lab/headlamp-plugins/headlamp-k8s-kserve-0.1.0-dev.1.tar.gz'
SHA256 = 'f136efde34520715f91678d9fe443fb13fefad717e2d6d7274554027e7f4d697'
CONFIGMAP = 'headlamp-kserve-plugin'


def manifest():
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != SHA256:
        raise ValueError('KServe plugin archive does not match the pinned checksum.')
    data, items = {}, []
    with tarfile.open(ARCHIVE, 'r:gz') as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or path.parts[0] != 'headlamp-kserve':
                raise ValueError('Unexpected plugin archive path.')
            if member.isdir():
                continue
            if not member.isfile() or member.size > 512 * 1024:
                raise ValueError('Unexpected plugin archive member.')
            key = 'file-' + str(len(data))
            data[key] = archive.extractfile(member).read().decode('utf-8')
            items.append({'key': key, 'path': str(path.relative_to('headlamp-kserve'))})
    paths = {item['path'] for item in items}
    if not {'main.js', 'package.json'}.issubset(paths):
        raise ValueError('Plugin archive needs main.js and package.json.')
    metadata = json.loads(next(data[x['key']] for x in items if x['path'] == 'package.json'))
    if (metadata['name'], metadata['version']) != ('@headlamp-k8s/kserve', '0.1.0-dev.1'):
        raise ValueError('Unexpected plugin name or version.')
    return {'apiVersion': 'v1', 'kind': 'ConfigMap',
            'metadata': {'name': CONFIGMAP, 'namespace': 'lab-headlamp',
                         'annotations': {'lab.relevance/plugin-sha256': SHA256}},
            'data': data}, items


def install_plugin():
    obj, _ = manifest()
    apply({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': 'lab-headlamp'}})
    apply(obj)


def plugin_values(values):
    _, items = manifest()
    values.setdefault('volumes', []).append({'name': 'kserve-plugin',
        'configMap': {'name': CONFIGMAP, 'items': items}})
    values.setdefault('volumeMounts', []).append({'name': 'kserve-plugin',
        'mountPath': '/headlamp/plugins/headlamp-kserve', 'readOnly': True})
    values.setdefault('podAnnotations', {})['lab.relevance/plugin-sha256'] = SHA256
    return values
