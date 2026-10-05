"""Mount pinned Headlamp plugins without additional runtime permissions."""
import hashlib
import json
import tarfile
from pathlib import PurePosixPath

from common import ROOT, apply

ARCHIVE = ROOT / 'lab/headlamp-plugins/headlamp-k8s-kserve-0.1.0-dev.29.tar.gz'
SHA256 = '0c2d59910e48be35fc3912efe2bcd33ad6dcfc262345c5cc38bbc075d2d46f0d'
CONFIGMAP = 'headlamp-kserve-plugin'
PROMETHEUS_ARCHIVE = ROOT / 'lab/headlamp-plugins/prometheus-0.9.1-kserve.1.tar.gz'
PROMETHEUS_SHA256 = '1d1c88351bcd959888c1f6a87c0571f0a01f0757eb45e762bec68ab2d7f65648'
PROMETHEUS_CONFIGMAP = 'headlamp-prometheus-plugin'


def _manifest(archive_path, checksum, directory, name, version, configmap):
    """Check the original archive and map its text assets to one ConfigMap."""
    if hashlib.sha256(archive_path.read_bytes()).hexdigest() != checksum:
        raise ValueError('Plugin archive does not match the pinned checksum.')
    data, items = {}, []
    with tarfile.open(archive_path, 'r:gz') as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != directory:
                raise ValueError('Unexpected plugin archive path.')
            if member.isdir():
                continue
            if not member.isfile() or member.size > 512 * 1024:
                raise ValueError('Unexpected plugin archive member.')
            key = 'file-' + str(len(data))
            relative = str(path.relative_to(directory))
            if any(item['path'] == relative for item in items):
                raise ValueError('Duplicated plugin archive path.')
            data[key] = archive.extractfile(member).read().decode('utf-8')
            items.append({'key': key, 'path': relative})
    if not {'main.js', 'package.json'}.issubset({item['path'] for item in items}):
        raise ValueError('Plugin archive needs main.js and package.json.')
    metadata = json.loads(next(data[x['key']] for x in items if x['path'] == 'package.json'))
    if (metadata['name'], metadata['version']) != (name, version):
        raise ValueError('Unexpected plugin name or version.')
    return {'apiVersion': 'v1', 'kind': 'ConfigMap',
            'metadata': {'name': configmap, 'namespace': 'lab-headlamp',
                         'annotations': {'lab.relevance/plugin-sha256': checksum}},
            'data': data}, items


def manifest():
    return _manifest(ARCHIVE, SHA256, 'headlamp-kserve', '@headlamp-k8s/kserve',
                     '0.1.0-dev.29', CONFIGMAP)


def prometheus_manifest():
    return _manifest(PROMETHEUS_ARCHIVE, PROMETHEUS_SHA256, 'prometheus', 'prometheus',
                     '0.9.1-kserve.1', PROMETHEUS_CONFIGMAP)


def install_plugin():
    manifests = [manifest(), prometheus_manifest()]
    apply({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': 'lab-headlamp'}})
    for obj, _ in manifests:
        apply(obj)


def plugin_values(values):
    for volume, directory, factory, checksum, annotation in (
            ('kserve-plugin', '/headlamp/plugins/headlamp-kserve', manifest, SHA256, 'plugin-sha256'),
            ('prometheus-plugin', '/headlamp/static-plugins/prometheus', prometheus_manifest, PROMETHEUS_SHA256,
             'prometheus-plugin-sha256')):
        obj, items = factory()
        values.setdefault('volumes', []).append({'name': volume,
            'configMap': {'name': obj['metadata']['name'], 'items': items}})
        values.setdefault('volumeMounts', []).append({'name': volume,
            'mountPath': directory, 'readOnly': True})
        values.setdefault('podAnnotations', {})['lab.relevance/' + annotation] = checksum
    return values
