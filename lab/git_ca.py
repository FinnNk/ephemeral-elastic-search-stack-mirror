"""Create a user-owned OpenSSL CA bundle for Git, then configure Git to use it."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import ssl
import subprocess


DEFAULT_OUTPUT = Path.home() / '.config/relevance-lab/git-ca-bundle.pem'
PEM = re.compile(rb'-----BEGIN CERTIFICATE-----\s*.*?-----END CERTIFICATE-----', re.S)


def git(*args, required=True):
    result = subprocess.run(['git', *args], capture_output=True, text=True, encoding='utf-8')
    if required and result.returncode:
        raise ValueError(result.stderr.strip() or 'Git configuration failed.')
    return result.stdout.strip()


def certificates(payload):
    if b'PRIVATE KEY' in payload:
        raise ValueError('Use public CA certificates, not private keys.')
    blocks = PEM.findall(payload)
    if not blocks or len(blocks) != payload.count(b'-----BEGIN CERTIFICATE-----'):
        raise ValueError('CA file contains no certificates or an incomplete PEM certificate.')
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cadata=b'\n'.join(blocks).decode('ascii'))
    return blocks


def bundle(base, root):
    roots = certificates(root)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cadata=b'\n'.join(roots).decode('ascii'))
    if len(roots) != 1 or context.cert_store_stats()['x509_ca'] != 1:
        raise ValueError('Select one public lab CA certificate.')
    retained = {}
    for block in certificates(base) + roots:
        der = ssl.PEM_cert_to_DER_cert(block.decode('ascii'))
        retained[hashlib.sha256(der).hexdigest()] = block
    return b'\n'.join(retained.values()) + b'\n', len(retained)


def install(root, output=DEFAULT_OUTPUT, base=None):
    root, output = Path(root).resolve(), Path(output).resolve()
    record = output.with_suffix('.json')
    if base is None:
        if record.exists():
            base = json.loads(record.read_text(encoding='utf-8'))['base_bundle']
        else:
            base = git('config', '--path', '--get', 'http.sslCAInfo', required=False)
            if not base:
                base = ssl.get_default_verify_paths().cafile
    if not base:
        raise ValueError('Git has no configured CA bundle. Supply --base-bundle with your standard PEM CA bundle.')
    base = Path(base).resolve()
    if output in (root, base) or base == root:
        raise ValueError('Keep the output, standard CA bundle and lab root at separate paths.')
    payload, count = bundle(base.read_bytes(), root.read_bytes())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    record.write_text(json.dumps({'base_bundle': str(base), 'lab_root': str(root)}, indent=2) + '\n', encoding='utf-8')
    git('config', '--global', 'http.sslBackend', 'openssl')
    git('config', '--global', 'http.sslCAInfo', output.as_posix())
    return output, count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path, help='Public root.pem supplied by the lab operator')
    parser.add_argument('--base-bundle', type=Path, help='Standard/corporate PEM roots; default: current Git CA file')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        output, count = install(args.root, args.output, args.base_bundle)
    except (ValueError, OSError, ssl.SSLError) as error:
        parser.exit(1, str(error) + '\n')
    print(f'Git OpenSSL trust configured: {output} ({count} distinct certificates)')
    print('Clone: git clone https://gitea.localhost:34443/elastic-agent/delivery-source.git')
    print('Browser trust is separate; see docs/workstation-access.md.')


if __name__ == '__main__':
    main()
