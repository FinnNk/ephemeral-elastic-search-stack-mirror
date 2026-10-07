"""Build native CPU images with corporate CA trust and retain immutable Nexus receipts."""
import hashlib
import json
import os
import platform
from pathlib import Path
import re
import shutil
import tempfile

from common import ROOT, STATE
from fresh_install import execute, private_json

DOCKERFILES = {'lab-control': 'lab/control-runtime/Dockerfile',
               'lab-notebook': 'lab/notebook/Dockerfile',
               'lab-data-producer': 'data/Dockerfile', 'lab-evaluator': 'evaluation/Dockerfile',
               'relevance-judge': 'judgements/Dockerfile', 'lab-gatling': None}


def trusted_dockerfile(source):
    """Add verified public/corporate roots before package downloads in the build."""
    lines = source.splitlines()
    position = next(i for i, line in enumerate(lines) if line.startswith('FROM ')) + 1
    lines[position:position] = [
        'COPY fresh-ca.pem /usr/local/share/ca-certificates/fresh-lab.crt',
        'RUN cat /usr/local/share/ca-certificates/fresh-lab.crt >> /etc/ssl/certs/ca-certificates.crt',
        'ENV SSL_CERT_FILE=/usr/local/share/ca-certificates/fresh-lab.crt PIP_CERT=/usr/local/share/ca-certificates/fresh-lab.crt REQUESTS_CA_BUNDLE=/usr/local/share/ca-certificates/fresh-lab.crt CURL_CA_BUNDLE=/usr/local/share/ca-certificates/fresh-lab.crt']
    return '\n'.join(lines) + '\n'


def gatling_dockerfile():
    """Keep Maven's pinned base and add corporate roots to Java's separate trust store."""
    source = (ROOT / 'lab/run_gatling.py').read_text(encoding='utf-8')
    base = re.search(r"DEFAULT_IMAGE = '([^']+)'", source).group(1)
    return trusted_dockerfile('FROM ' + base + '\n') + (
        "RUN mkdir -p /tmp/fresh-java-ca && "
        "awk '/-----BEGIN CERTIFICATE-----/{n++} n{print > (\"/tmp/fresh-java-ca/ca-\" n \".pem\")}' "
        "/usr/local/share/ca-certificates/fresh-lab.crt && "
        "for cert in /tmp/fresh-java-ca/*.pem; do keytool -importcert -cacerts "
        "-storepass changeit -noprompt -alias fresh-$(basename \"$cert\") -file \"$cert\"; done && "
        "rm -rf /tmp/fresh-java-ca\n")


def main():
    credentials = json.loads((STATE / 'nexus.json').read_text(encoding='utf-8'))['publisher']
    config = STATE / 'fresh-docker-config'
    config.mkdir(mode=0o700, exist_ok=True)
    if os.name != 'nt':
        config.chmod(0o700)
    environment = {**os.environ, 'DOCKER_CONFIG': str(config.resolve())}
    architecture = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'amd64', 'amd64': 'amd64'}.get(platform.machine().lower())
    if not architecture:
        raise ValueError('Unsupported host architecture: ' + platform.machine())
    receipts_path = STATE / 'fresh-images.json'
    receipts = json.loads(receipts_path.read_text(encoding='utf-8')) if receipts_path.exists() else {}
    try:
        execute(['docker', 'login', '127.0.0.1:18185', '--username', credentials['username'],
                 '--password-stdin'], env=environment, body=credentials['password'] + '\n')
        with tempfile.TemporaryDirectory(prefix='fresh-image-', dir=STATE) as temporary:
            context = Path(temporary)
            for name in ('lab', 'data', 'evaluation', 'judgements', 'contracts'):
                shutil.copytree(ROOT / name, context / name,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
            shutil.copyfile(STATE / 'host-ca-bundle.pem', context / 'fresh-ca.pem')
            checksum = hashlib.sha256()
            for path in sorted(context.rglob('*')):
                if path.is_file():
                    checksum.update(path.relative_to(context).as_posix().encode() + b'\0' + path.read_bytes())
            source = checksum.hexdigest()
            for name, original in DOCKERFILES.items():
                if receipts.get(name, {}).get('source_sha256') == source and receipts[name].get('architecture') == architecture:
                    print('Retained image: ' + name, flush=True)
                    continue
                dockerfile = context / (name + '.Dockerfile')
                dockerfile.write_text(trusted_dockerfile((ROOT / original).read_text(encoding='utf-8')) if original else gatling_dockerfile(), encoding='utf-8')
                tag = '127.0.0.1:18185/' + name + ':fresh-' + source[:16] + '-' + architecture
                print('Building ' + name + ' for linux/' + architecture, flush=True)
                execute(['docker', 'buildx', 'build', '--platform', 'linux/' + architecture,
                         '--provenance=false', '--load', '-t', tag, '-f', str(dockerfile), str(context)],
                        env=environment, live=True)
                execute(['docker', 'push', tag], env=environment, live=True)
                digests = json.loads(execute(['docker', 'image', 'inspect', tag,
                    '--format', '{{json .RepoDigests}}'], env=environment))
                matches = [value for value in digests if value.startswith('127.0.0.1:18185/' + name + '@sha256:')]
                if len(matches) != 1 or not re.fullmatch(r'.+@sha256:[0-9a-f]{64}', matches[0]):
                    raise ValueError('Published image digest is ambiguous: ' + name)
                receipts[name] = {'image': matches[0].replace('127.0.0.1', 'nexus.localhost', 1),
                                  'source_sha256': source, 'architecture': architecture}
                private_json(receipts_path, receipts)
    finally:
        # Do not retain a publisher password in a Docker auth file.
        (config / 'config.json').unlink(missing_ok=True)
    for name, filename in [('lab-control', 'control-image.json'), ('lab-notebook', 'notebook-image.json')]:
        private_json(STATE / filename, receipts[name])
    private_json(STATE / 'tool-images-7j.json', {name: receipts[name] for name in ('lab-data-producer', 'lab-evaluator')})
    judge = dict(receipts['relevance-judge'])
    # Keep a tagged digest for the generated MLflow chart values.
    judge['image'] = judge['image'].replace('/relevance-judge@', '/relevance-judge:fresh-' + judge['source_sha256'][:16] + '@')
    private_json(STATE / 'judgement-image.json', judge)


if __name__ == '__main__':
    main()
