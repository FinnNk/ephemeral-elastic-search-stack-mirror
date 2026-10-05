"""Publish the pinned GitHub App credential helper for Gitea push mirrors."""
import importlib.util
import json
import os
from pathlib import Path
import re
import uuid

ROOT = Path(__file__).resolve().parents[2]
STATE = Path(os.environ.get('LAB_STATE_DIR', str(ROOT / '.lab')))


def main():
    spec = importlib.util.spec_from_file_location('control_publish', ROOT / 'lab/control-runtime/publish.py')
    publisher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(publisher)
    credentials = json.loads((STATE / 'nexus.json').read_text(encoding='utf-8'))['publisher']
    config = STATE / 'mirror-docker-config'
    config.mkdir(exist_ok=True)
    environment = {**os.environ, 'DOCKER_CONFIG': str(config.resolve())}
    publisher.call(['docker', 'login', '127.0.0.1:18185', '--username', credentials['username'],
                    '--password-stdin'], env=environment, input_text=credentials['password'] + '\n')
    tag = '127.0.0.1:18185/github-app-credential:build-' + uuid.uuid4().hex[:16]
    variants = []
    for architecture in ('amd64', 'arm64'):
        variant = tag + '-' + architecture
        publisher.call(['docker', 'buildx', 'build', '--platform', 'linux/' + architecture,
                        '--provenance=false', '--load', '-t', variant,
                        '-f', 'lab/github-mirror/Dockerfile', '.'], env=environment)
        publisher.call(['docker', 'push', variant], env=environment)
        variants.append(variant)
    publisher.call(['docker', 'manifest', 'create', '--insecure', tag, *variants], env=environment)
    output = publisher.call(['docker', 'manifest', 'push', '--insecure', '--purge', tag], env=environment)
    digest = re.search(r'sha256:[a-f0-9]{64}', output)
    if not digest:
        raise RuntimeError('Nexus did not return an image digest.')
    record = {'image': 'nexus.localhost:18185/github-app-credential@' + digest.group(),
              'source': '44092188bcdbbc209317424429489b2335793617',
              'platforms': ['linux/amd64', 'linux/arm64']}
    (STATE / 'github-mirror').mkdir(exist_ok=True)
    (STATE / 'github-mirror/image.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(record['image'])


if __name__ == '__main__':
    main()
