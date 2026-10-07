"""Install local lab DNS and automatic HTTPS search-environment routes."""
import base64
import json
import os

from common import K3D, ROOT, STATE, apply, guard, k, run
from https_ingress import certificate, expose, route
from preview_access import bind
from preview_routes import DOMAIN

DNS_IMAGE = 'coredns/coredns:1.13.1@sha256:9b9128672209474da07c91439bf15ed704ae05ad918dd6454e5b6ae14e35fee6'
PYTHON_IMAGE = 'python:3.13.7-alpine3.22@sha256:9ba6d8cbebf0fb6546ae71f2a1c14f6ffd2fdab83af7fa5669734ef30ad48844'
NAMESPACE = 'lab-ingress'


def corefile():
    from https_ingress import ENDPOINTS
    fixed = '\n'.join('        127.0.0.1 ' + name + '.localhost' for name in ENDPOINTS)
    return f'''localhost:1053 {{
    errors
    hosts {{
        127.0.0.1 localhost
{fixed}
        ttl 30
    }}
}}
{DOMAIN}:1053 {{
    errors
    template IN A {{
        answer "{{{{ .Name }}}} 30 IN A 127.0.0.1"
    }}
    template IN ANY {{
        rcode NOERROR
    }}
}}
'''


def configure_control_role():
    """Extend an installed control role; DNS can be installed before the control runtime."""
    result = k('get', 'clusterrole/lab-control-namespace-manager', '-o', 'json',
               '--ignore-not-found')
    if not result.stdout.strip():
        print('Control runtime is not installed; retaining DNS and preview routing without its role.')
        return
    base = json.loads(result.stdout)
    for rule in base['rules']:
        if rule.get('resources') == ['clusterroles'] and 'bind' in rule['verbs']:
            rule['resourceNames'] = sorted(set(rule['resourceNames']) | {'lab-preview-route-writer'})
    apply(base)


def install():
    guard()
    k('get', 'deployment/lab-traefik', '-n', NAMESPACE)
    cert, key, ca = certificate()
    route(cert, key)
    apply({'apiVersion': 'v1', 'kind': 'Secret', 'type': 'kubernetes.io/tls',
        'metadata': {'name': 'lab-preview-tls', 'namespace': NAMESPACE},
        'data': {'tls.crt': base64.b64encode(cert.read_bytes()).decode(),
                 'tls.key': base64.b64encode(key.read_bytes()).decode()}})
    apply({'apiVersion': 'traefik.io/v1alpha1', 'kind': 'TLSStore',
        'metadata': {'name': 'default', 'namespace': NAMESPACE},
        'spec': {'defaultCertificate': {'secretName': 'lab-preview-tls'}}})
    apply({'apiVersion': 'v1', 'kind': 'ConfigMap',
        'metadata': {'name': 'lab-preview-code', 'namespace': NAMESPACE},
        'data': {'preview_routes.py': (ROOT / 'lab/preview_routes.py').read_text(encoding='utf-8'),
                 'Corefile': corefile()}})
    apply({'apiVersion': 'v1', 'kind': 'ServiceAccount',
        'metadata': {'name': 'lab-preview-routes', 'namespace': NAMESPACE}})
    apply({'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'ClusterRole',
        'metadata': {'name': 'lab-preview-discovery'}, 'rules': [
            {'apiGroups': [''], 'resources': ['namespaces'], 'verbs': ['list']}]})
    apply({'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'ClusterRoleBinding',
        'metadata': {'name': 'lab-preview-discovery'},
        'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'ClusterRole', 'name': 'lab-preview-discovery'},
        'subjects': [{'kind': 'ServiceAccount', 'name': 'lab-preview-routes', 'namespace': NAMESPACE}]})
    # This reusable role is granted through RoleBindings in search namespaces only.
    apply({'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'ClusterRole',
        'metadata': {'name': 'lab-preview-route-writer'}, 'rules': [
            {'apiGroups': [''], 'resources': ['services'], 'resourceNames': ['search'], 'verbs': ['get']},
            {'apiGroups': ['networking.k8s.io'], 'resources': ['ingresses', 'networkpolicies'],
             'verbs': ['create']},
            {'apiGroups': ['networking.k8s.io'], 'resources': ['ingresses', 'networkpolicies'],
             'resourceNames': ['lab-preview'], 'verbs': ['get', 'patch', 'delete']}]})
    for namespace in json.loads(k('get', 'namespaces', '-l', 'lab=search-spike', '-o', 'json').stdout)['items']:
        bind(namespace['metadata']['name'])
    # The existing control namespace manager may grant this specific role to new previews.
    configure_control_role()
    for name, image, command in (
            ('lab-dns', DNS_IMAGE, ['/coredns', '-conf', '/config/Corefile']),
            ('lab-preview-routes', PYTHON_IMAGE, ['python', '/config/preview_routes.py'])):
        container = {'name': name, 'image': image, 'command': command,
            'resources': {'requests': {'cpu': '10m', 'memory': '24Mi'},
                          'limits': {'cpu': '200m', 'memory': '64Mi'}},
            'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                                'capabilities': {'drop': ['ALL']}},
            'volumeMounts': [{'name': 'config', 'mountPath': '/config', 'readOnly': True},
                             {'name': 'tmp', 'mountPath': '/tmp'}]}
        if name == 'lab-dns':
            # Verified against the pinned image: dropping this capability prevents
            # executing /coredns (EPERM), even with a high listener port. This is
            # also the upstream Helm chart's non-root security configuration.
            container['securityContext']['capabilities']['add'] = ['NET_BIND_SERVICE']
            container['readinessProbe'] = {'tcpSocket': {'port': 1053}, 'periodSeconds': 5}
        else:
            container['readinessProbe'] = {'exec': {'command': ['python', '-c',
                "import os,time; assert time.time()-os.stat('/tmp/ready').st_mtime < 30"]}, 'periodSeconds': 5}
        apply({'apiVersion': 'apps/v1', 'kind': 'Deployment',
            'metadata': {'name': name, 'namespace': NAMESPACE},
            'spec': {'replicas': 1, 'strategy': {'type': 'Recreate'},
                'selector': {'matchLabels': {'app': name}},
                'template': {'metadata': {'labels': {'app': name}}, 'spec': {
                    'serviceAccountName': 'lab-preview-routes',
                    'automountServiceAccountToken': name == 'lab-preview-routes',
                    'securityContext': {'runAsNonRoot': True, 'runAsUser': 10001},
                    'containers': [container], 'volumes': [
                        {'name': 'config', 'configMap': {'name': 'lab-preview-code'}},
                        {'name': 'tmp', 'emptyDir': {'sizeLimit': '1Mi'}}]}}}})
    apply({'apiVersion': 'v1', 'kind': 'Service',
        'metadata': {'name': 'lab-dns', 'namespace': NAMESPACE},
        'spec': {'type': 'NodePort', 'selector': {'app': 'lab-dns'}, 'ports': [
            {'name': protocol.lower(), 'port': 53, 'targetPort': 1053,
             'nodePort': 30053, 'protocol': protocol} for protocol in ('UDP', 'TCP')]}})
    for name in ('lab-dns', 'lab-preview-routes'):
        k('rollout', 'restart', 'deployment/' + name, '-n', NAMESPACE)
        k('rollout', 'status', 'deployment/' + name, '-n', NAMESPACE, '--timeout=120s')
    expose()
    bindings = json.loads(run(['docker', 'inspect', 'k3d-relevance-lab-serverlb',
                               '--format', '{{json .HostConfig.PortBindings}}']).stdout)
    for protocol in ('udp', 'tcp'):
        if '30053/' + protocol not in bindings:
            run([K3D,
                 'cluster', 'edit', 'relevance-lab', '--port-add',
                 f'127.0.0.1:53:30053/{protocol}@server:0'])
    print('DNS: 127.0.0.1:53 (UDP and TCP); preview HTTPS: *.' + DOMAIN + ':34443')
    print('Next: configure workstation domain DNS; see docs/workstation-access.md.')
    print('Existing CA retained at:', ca)


if __name__ == '__main__':
    install()
