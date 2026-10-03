"""Install the Headlamp Kubernetes UI and create a separate human lab identity."""
import argparse
import json

from common import HELM, ROOT, STATE, apply, guard, k, run
from https_ingress import certificate, route, verify
from install_preview_urls import corefile

NAMESPACE = 'lab-headlamp'
CHART_VERSION = '0.45.0'
USER = 'headlamp-owner'
URL = 'https://headlamp.localhost:34443/'


def install():
    guard()
    k('get', 'deployment/lab-traefik', '-n', 'lab-ingress')
    k('get', 'configmap/lab-preview-code', '-n', 'lab-ingress')
    run([HELM, 'upgrade', '--install', 'headlamp', 'headlamp', '--repo',
         'https://kubernetes-sigs.github.io/headlamp/', '--version', CHART_VERSION,
         '--namespace', NAMESPACE, '--create-namespace', '--values',
         str(ROOT / 'lab/headlamp-values.yaml'), '--wait', '--timeout', '5m',
         '--kubeconfig', str(STATE / 'kubeconfig.yaml')])
    apply({'apiVersion': 'v1', 'kind': 'ServiceAccount',
           'metadata': {'name': USER, 'namespace': NAMESPACE},
           'automountServiceAccountToken': False})
    apply({'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'ClusterRoleBinding',
           'metadata': {'name': USER},
           'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'ClusterRole',
                       'name': 'cluster-admin'},
           'subjects': [{'kind': 'ServiceAccount', 'name': USER, 'namespace': NAMESPACE}]})
    cert, key, ca = certificate()
    route(cert, key)
    # Patch only DNS: preserve the preview controller's code and running watches.
    k('patch', 'configmap/lab-preview-code', '-n', 'lab-ingress', '--type=merge',
      '-p', json.dumps({'data': {'Corefile': corefile()}}))
    k('rollout', 'restart', 'deployment/lab-dns', '-n', 'lab-ingress')
    k('rollout', 'status', 'deployment/lab-dns', '-n', 'lab-ingress', '--timeout=120s')
    verify(ca, ['headlamp'])
    print(URL)
    print('Run python lab/install_headlamp.py token to obtain a one-hour login token.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'token'))
    args = parser.parse_args()
    if args.action == 'install':
        install()
    else:
        guard()
        # Intentionally printed only by this explicit user command, never by installation.
        print(k('create', 'token', USER, '-n', NAMESPACE, '--duration=1h').stdout.strip())


if __name__ == '__main__':
    main()
