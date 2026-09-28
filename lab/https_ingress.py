"""Expose the retained lab web UIs through one local HTTPS ingress."""

import argparse
import json
import os
from pathlib import Path
import socket
import sys
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from common import HELM, ROOT, STATE, apply, guard, k, run


CHART_VERSION = '41.6.0'
HOST_PORT = 34443
NODE_PORT = 30443
TLS = STATE / 'https-ingress'
ENDPOINTS = {
    'gitea': ('platform', 'gitea-http', 31800),
    'argocd': ('argocd', 'argocd-server', 80),
    'control': ('lab-control', 'lab-control', 18082),
    'signoz': ('lab-observability', 'signoz', 8080),
    'nexus': ('platform', 'nexus', 8081),
}


def certificate():
    TLS.mkdir(parents=True, exist_ok=True)
    ca_key_path, ca_path = TLS / 'root-key.pem', TLS / 'root.pem'
    key_path, cert_path = TLS / 'edge-key.pem', TLS / 'edge.pem'
    if all(path.exists() for path in (ca_key_path, ca_path, key_path, cert_path)):
        existing = x509.load_pem_x509_certificate(cert_path.read_bytes())
        if existing.not_valid_after_utc > datetime.now(timezone.utc) + timedelta(days=7):
            return cert_path, key_path, ca_path
    now = datetime.now(timezone.utc)
    if ca_key_path.exists() and ca_path.exists():
        ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(), password=None)
        ca = x509.load_pem_x509_certificate(ca_path.read_bytes())
    else:
        ca_key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Relevance lab local CA')])
        ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
              .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=730))
              .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
              .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                  key_encipherment=False, data_encipherment=False, key_agreement=False,
                  key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False),
                  critical=True).sign(ca_key, hashes.SHA256()))
        ca_key_path.write_bytes(ca_key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    key = ec.generate_private_key(ec.SECP256R1())
    names = [x509.DNSName(name + '.localhost') for name in ENDPOINTS]
    leaf = (x509.CertificateBuilder().subject_name(x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, 'gitea.localhost')]))
            .issuer_name(ca.subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=90))
            .add_extension(x509.SubjectAlternativeName(names), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
                           critical=False).sign(ca_key, hashes.SHA256()))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    cert_path.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    if os.name != 'nt':
        ca_key_path.chmod(0o600)
        key_path.chmod(0o600)
    return cert_path, key_path, ca_path


def install_ingress():
    values = ROOT / 'lab' / 'https-traefik-values.yaml'
    run([HELM, 'upgrade', '--install', 'lab-traefik', 'traefik', '--repo',
         'https://traefik.github.io/charts', '--version', CHART_VERSION,
         '--namespace', 'lab-ingress', '--create-namespace', '--values', str(values),
         '--wait', '--timeout', '5m', '--kubeconfig', str(STATE / 'kubeconfig.yaml')])
    k('rollout', 'status', 'deployment/lab-traefik', '-n', 'lab-ingress', '--timeout=180s')


def route(cert_path, key_path):
    import base64
    cert = base64.b64encode(cert_path.read_bytes()).decode()
    key = base64.b64encode(key_path.read_bytes()).decode()
    for name, (namespace, service, port) in ENDPOINTS.items():
        host = name + '.localhost'
        apply({'apiVersion': 'v1', 'kind': 'Secret', 'type': 'kubernetes.io/tls',
               'metadata': {'name': 'lab-edge-tls', 'namespace': namespace},
               'data': {'tls.crt': cert, 'tls.key': key}})
        apply({'apiVersion': 'networking.k8s.io/v1', 'kind': 'Ingress',
               'metadata': {'name': 'lab-https-' + name, 'namespace': namespace,
                            'annotations': {'traefik.ingress.kubernetes.io/router.entrypoints':
                                            'websecure'}},
               'spec': {'ingressClassName': 'traefik',
                        'tls': [{'hosts': [host], 'secretName': 'lab-edge-tls'}],
                        'rules': [{'host': host, 'http': {'paths': [{'path': '/',
                            'pathType': 'Prefix', 'backend': {'service': {'name': service,
                                'port': {'number': port}}}}]}}]}})
    apply({'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy',
           'metadata': {'name': 'lab-https-control', 'namespace': 'lab-control'},
           'spec': {'podSelector': {'matchLabels': {'app': 'lab-control'}},
                    'policyTypes': ['Ingress'],
                    'ingress': [{'from': [{'namespaceSelector': {'matchLabels': {
                        'kubernetes.io/metadata.name': 'lab-ingress'}}}],
                        'ports': [{'protocol': 'TCP', 'port': 18082}]}]}})


def expose():
    k3d = STATE / 'tools' / ('k3d.exe' if os.name == 'nt' else 'k3d')
    if not k3d.exists():
        raise FileNotFoundError(k3d)
    # k3d edits the load-balancer container, preserving the server and its volumes.
    before = run(['docker', 'inspect', 'k3d-relevance-lab-serverlb', '--format',
                  '{{json .HostConfig.PortBindings}}']).stdout
    bindings = json.loads(before)
    if str(NODE_PORT) + '/tcp' not in bindings:
        run([str(k3d), 'cluster', 'edit', 'relevance-lab', '--port-add',
             f'127.0.0.1:{HOST_PORT}:{NODE_PORT}@server:0'])


def configure_gitea():
    values = ROOT / 'research' / 'platform-spike' / 'gitea-values.yaml'
    run([HELM, 'upgrade', 'gitea', 'gitea', '--repo', 'https://dl.gitea.com/charts/',
         '--version', '12.7.0',
         '--namespace', 'platform', '--values', str(values), '--set-string',
         f'gitea.config.server.ROOT_URL=https://gitea.localhost:{HOST_PORT}/',
         '--wait', '--timeout', '5m',
         '--kubeconfig', str(STATE / 'kubeconfig.yaml')])


def verify(ca_path):
    import ssl
    context = ssl.create_default_context(cafile=str(ca_path))
    for name in ENDPOINTS:
        host = name + '.localhost'
        # Some host DNS resolvers do not implement the browser's .localhost rule.
        # Connect to loopback while still validating the real SNI hostname.
        with socket.create_connection(('127.0.0.1', HOST_PORT), timeout=20) as connection:
            with context.wrap_socket(connection, server_hostname=host) as tls:
                tls.sendall(f'GET / HTTP/1.1\r\nHost: {host}:{HOST_PORT}\r\n'
                            'Connection: close\r\n\r\n'.encode())
                status = tls.makefile('rb').readline().decode('ascii', errors='replace')
                if not status.startswith('HTTP/1.1 ') or int(status.split()[1]) >= 400:
                    raise RuntimeError(f'{name} returned {status.strip()}')
        print(name, 'TLS and HTTP response verified')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'verify', 'trust'))
    args = parser.parse_args()
    cert_path, key_path, ca_path = certificate()
    if args.action == 'trust':
        if os.name == 'nt':
            run(['certutil', '-user', '-addstore', 'Root', str(ca_path)])
        elif sys.platform == 'darwin':
            run(['security', 'add-trusted-cert', '-d', '-r', 'trustRoot', '-k',
                 str(Path.home() / 'Library/Keychains/login.keychain-db'), str(ca_path)])
        else:
            raise RuntimeError('Import root.pem into the workstation trust store manually.')
        print('Trusted local CA:', ca_path)
    elif args.action == 'install':
        guard()
        install_ingress()
        route(cert_path, key_path)
        expose()
        verify(ca_path)
        configure_gitea()
        verify(ca_path)
    else:
        verify(ca_path)


if __name__ == '__main__':
    main()
