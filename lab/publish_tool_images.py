"""Publish independent producer/evaluator image manifests to local Nexus."""

import json
import os
from pathlib import Path
import re
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.lab'
IMAGES = {'lab-data-producer': 'data/Dockerfile',
          'lab-evaluator': 'evaluation/Dockerfile'}


def call(arguments, environment, input_text=None):
    result = subprocess.run(arguments, cwd=ROOT, env=environment, input=input_text,
                            text=True, capture_output=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(arguments[0] + ' failed: ' + result.stderr[-800:])
    return result.stdout


def main():
    credentials = json.loads((STATE / 'nexus.json').read_text(encoding='utf-8'))['publisher']
    config = STATE / 'tool-docker-config'
    config.mkdir(exist_ok=True)
    environment = {**os.environ, 'DOCKER_CONFIG': str(config.resolve())}
    call(['docker', 'login', '127.0.0.1:18185', '--username',
          credentials['username'], '--password-stdin'], environment,
         credentials['password'] + '\n')
    published = {}
    for name, dockerfile in IMAGES.items():
        tag = '127.0.0.1:18185/' + name + ':7j-' + uuid.uuid4().hex[:16]
        variants = []
        for architecture in ('amd64', 'arm64'):
            local = name + ':' + architecture + '-local'
            variant = tag + '-' + architecture
            call(['docker', 'buildx', 'build', '--platform', 'linux/' + architecture,
                  '--provenance=false', '--load', '-t', local, '-f', dockerfile, '.'], environment)
            call(['docker', 'tag', local, variant], environment)
            call(['docker', 'push', variant], environment)
            variants.append(variant)
        call(['docker', 'manifest', 'create', '--insecure', tag, *variants], environment)
        output = call(['docker', 'manifest', 'push', '--insecure', '--purge', tag], environment)
        match = re.search(r'sha256:[a-f0-9]{64}', output)
        if match is None:
            raise ValueError('Nexus did not return a multi-platform digest for ' + name)
        published[name] = {'image': 'nexus.localhost:18185/' + name + '@' + match.group(0),
                           'tag': tag, 'platforms': ['linux/amd64', 'linux/arm64']}
    (STATE / 'tool-images-7j.json').write_text(json.dumps(published, indent=2), encoding='utf-8')
    print(json.dumps({name: value['image'] for name, value in published.items()}, indent=2))


if __name__ == '__main__':
    main()
