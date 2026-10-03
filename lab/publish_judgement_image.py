"""Publish the MLflow/KServe and judgement-service image to immutable Nexus tags."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.environ.get('LAB_STATE_DIR', ROOT / '.lab'))


def call(arguments, environment, input_text=None):
    result = subprocess.run(arguments, cwd=ROOT, env=environment, input=input_text,
                            text=True, capture_output=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(arguments[0] + ' failed: ' + result.stderr[-1000:])
    return result.stdout


def source_sha256():
    checksum = hashlib.sha256()
    for path in [ROOT / 'judgements' / 'Dockerfile', ROOT / 'data' / 'contracts.py',
                 *sorted((ROOT / 'judgements').glob('*.py'))]:
        checksum.update(path.relative_to(ROOT).as_posix().encode() + b'\0')
        checksum.update(path.read_bytes())
    return checksum.hexdigest()


def publish(platforms):
    credentials = json.loads((STATE / 'nexus.json').read_text(encoding='utf-8'))['publisher']
    config = STATE / 'judgement-docker-config'
    config.mkdir(exist_ok=True)
    environment = {**os.environ, 'DOCKER_CONFIG': str(config.resolve())}
    call(['docker', 'login', '127.0.0.1:18185', '--username',
          credentials['username'], '--password-stdin'], environment,
         credentials['password'] + '\n')
    source = source_sha256()
    tag = '127.0.0.1:18185/relevance-judge:j1-' + source[:16]
    variants = []
    for architecture in platforms:
        variant = tag + '-' + architecture
        call(['docker', 'buildx', 'build', '--platform', 'linux/' + architecture,
              '--provenance=false', '--load', '-t', variant,
              '-f', 'judgements/Dockerfile', '.'], environment)
        call(['docker', 'push', variant], environment)
        variants.append(variant)
    if len(variants) == 1:
        # A single-platform local run still uses its immutable tag; digest is
        # resolved by Kubernetes after pull and recorded in the smoke evidence.
        published = {'image': variants[0].replace('127.0.0.1', 'nexus.localhost'),
                     'platforms': ['linux/' + platforms[0]], 'source_sha256': source}
    else:
        call(['docker', 'manifest', 'create', '--insecure', tag, *variants], environment)
        output = call(['docker', 'manifest', 'push', '--insecure', '--purge', tag], environment)
        match = re.search(r'sha256:[a-f0-9]{64}', output)
        if match is None:
            raise ValueError('Nexus did not return a multi-platform manifest digest.')
        published = {'image': tag.replace('127.0.0.1', 'nexus.localhost'),
                     'manifest_sha256': match.group(0),
                     'platforms': ['linux/' + architecture for architecture in platforms],
                     'source_sha256': source}
    (STATE / 'judgement-image.json').write_text(json.dumps(published, indent=2),
                                                 encoding='utf-8')
    return published


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platforms', nargs='+', choices=('amd64', 'arm64'),
                        default=['amd64', 'arm64'])
    args = parser.parse_args()
    print(json.dumps(publish(args.platforms), sort_keys=True))
