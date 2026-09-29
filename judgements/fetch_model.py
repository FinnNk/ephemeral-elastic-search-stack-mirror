"""KServe storage initializer for an exact MLflow registered-model version."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from urllib.parse import parse_qs, urlparse


def model_uri(source):
    parsed = urlparse(source)
    if parsed.scheme != 'mlflow-registry' or not parsed.netloc:
        raise ValueError('Expected mlflow-registry://name/version.')
    version = parsed.path.strip('/')
    if not version.isdecimal() or int(version) < 1 or '/' in version:
        raise ValueError('An exact numeric registered-model version is required.')
    return f'models:/{parsed.netloc}/{version}'


def tree_digest(directory):
    """Hash paths and bytes, so a model version also pins its artefact content."""
    root = Path(directory)
    value = hashlib.sha256()
    for path in sorted(item for item in root.rglob('*') if item.is_file()):
        value.update(path.relative_to(root).as_posix().encode())
        value.update(b'\0')
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                value.update(block)
    return value.hexdigest()


def fetch(source, destination):
    import mlflow
    uri = model_uri(source)
    destination = Path(destination)
    if any(destination.iterdir()) if destination.exists() else False:
        raise ValueError('Model destination is not empty.')
    destination.mkdir(parents=True, exist_ok=True)
    downloaded = Path(mlflow.artifacts.download_artifacts(artifact_uri=uri))
    if not (downloaded / 'MLmodel').is_file():
        raise ValueError('Registered artefact is not an MLflow model.')
    expected = parse_qs(urlparse(source).query).get('sha256')
    if expected is not None and (len(expected) != 1 or
                                 tree_digest(downloaded) != expected[0]):
        raise ValueError('Registered model bytes differ from the pinned digest.')
    for item in downloaded.iterdir():
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    identity = {'name': urlparse(source).netloc,
                'version': urlparse(source).path.strip('/'),
                'artifact_sha256': tree_digest(destination)}
    (destination / '.model-identity.json').write_text(json.dumps(identity, sort_keys=True))
    return {'uri': uri, **identity}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    import json
    print(json.dumps(fetch(args.source, args.destination), sort_keys=True))
