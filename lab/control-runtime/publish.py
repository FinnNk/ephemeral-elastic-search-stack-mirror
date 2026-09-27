"""Build and publish the control image to local Nexus by immutable digest."""

import json
import os
from pathlib import Path
import re
import subprocess
import uuid


ROOT = Path(__file__).resolve().parents[2]
STATE = Path(os.environ.get('LAB_STATE_DIR', str(ROOT / '.lab')))


def call(args, *, env=None, input_text=None):
    result = subprocess.run(args, cwd=ROOT, env=env, input=input_text, text=True,
                            capture_output=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(args[0] + ' failed: ' + result.stderr[-800:])
    return result.stdout


def main():
    credentials = json.loads((STATE / 'nexus.json').read_text(encoding='utf-8'))['publisher']
    docker_config = STATE / 'control-docker-config'
    docker_config.mkdir(exist_ok=True)
    environment = {**os.environ, 'DOCKER_CONFIG': str(docker_config.resolve())}
    call(['docker', 'login', '127.0.0.1:18185', '--username',
          credentials['username'], '--password-stdin'], env=environment,
         input_text=credentials['password'] + '\n')
    tag = '127.0.0.1:18185/lab-control:runtime-' + uuid.uuid4().hex[:16]
    variants = []
    for architecture in ('amd64', 'arm64'):
        local = 'lab-control:' + architecture + '-local'
        variant = tag + '-' + architecture
        call(['docker', 'buildx', 'build', '--platform', 'linux/' + architecture,
              '--provenance=false', '--load', '-t', local,
              '-f', 'lab/control-runtime/Dockerfile', '.'],
             env=environment)
        call(['docker', 'tag', local, variant], env=environment)
        call(['docker', 'push', variant], env=environment)
        variants.append(variant)
    call(['docker', 'manifest', 'create', '--insecure', tag, *variants], env=environment)
    output = call(['docker', 'manifest', 'push', '--insecure', '--purge', tag], env=environment)
    match = re.search(r'sha256:[a-f0-9]{64}', output)
    if match is None:
        raise ValueError('Nexus did not return a multi-platform image digest.')
    image = 'nexus.localhost:18185/lab-control@' + match.group(0)
    (STATE / 'control-image.json').write_text(json.dumps({'image': image,
        'tag': tag, 'platforms': ['linux/amd64', 'linux/arm64']}, indent=2), encoding='utf-8')
    print(image)


if __name__ == '__main__':
    main()
