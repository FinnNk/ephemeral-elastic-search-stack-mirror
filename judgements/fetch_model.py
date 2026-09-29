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
    for path in sorted(item for item in root.rglob('*') if item.is_file() and
                       item.relative_to(root).as_posix() != '.model-identity.json'):
        value.update(path.relative_to(root).as_posix().encode())
        value.update(b'\0')
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                value.update(block)
    return value.hexdigest()


def fetch(source, destination):
    uri = model_uri(source)
    destination = Path(destination)
    parsed = urlparse(source)
    expected = parse_qs(parsed.query).get('sha256')
    if expected is None or len(expected) != 1 or not re_full_sha(expected[0]):
        raise ValueError('Registered model needs one pinned SHA-256 digest.')
    identity = {'name': parsed.netloc, 'version': parsed.path.strip('/'),
                'artifact_sha256': expected[0]}
    if destination.exists() and any(destination.iterdir()):
        receipt = destination / '.model-identity.json'
        if not receipt.is_file() or json.loads(receipt.read_text()) != identity or \
                not (destination / 'MLmodel').is_file() or \
                tree_digest(destination) != expected[0]:
            raise ValueError('Existing model bytes differ from the pinned version.')
        return {'uri': uri, **identity}
    import mlflow
    destination.mkdir(parents=True, exist_ok=True)
    downloaded = Path(mlflow.artifacts.download_artifacts(artifact_uri=uri))
    if not (downloaded / 'MLmodel').is_file():
        raise ValueError('Registered artefact is not an MLflow model.')
    if tree_digest(downloaded) != expected[0]:
        raise ValueError('Registered model bytes differ from the pinned digest.')
    for item in downloaded.iterdir():
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    if tree_digest(destination) != expected[0]:
        raise ValueError('Copied model bytes differ from the pinned digest.')
    (destination / '.model-identity.json').write_text(json.dumps(identity, sort_keys=True))
    return {'uri': uri, **identity}


def re_full_sha(value):
    return len(value) == 64 and all(character in '0123456789abcdef' for character in value)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    import json
    print(json.dumps(fetch(args.source, args.destination), sort_keys=True))
