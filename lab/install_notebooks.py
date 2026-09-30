"""Install the fixed notebook namespace and network policy with the lab operator."""

from common import apply, guard
from setup_nexus import image_secret

NAMESPACE = 'lab-notebooks'


def install():
    guard()
    apply({'apiVersion': 'v1', 'kind': 'Namespace',
           'metadata': {'name': NAMESPACE, 'labels': {'lab/owner': 'exploratory-notebooks'}}})
    apply({'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'RoleBinding',
           'metadata': {'name': 'lab-control-runtime', 'namespace': NAMESPACE},
           'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'ClusterRole',
                       'name': 'lab-control-environment'},
           'subjects': [{'kind': 'ServiceAccount', 'name': 'lab-control',
                         'namespace': 'lab-control'}]})
    image_secret(NAMESPACE)
    apply({'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy',
           'metadata': {'name': 'notebook-blob-egress', 'namespace': NAMESPACE},
           'spec': {'podSelector': {'matchLabels': {'app': 'lab-notebook'}},
                    'policyTypes': ['Ingress', 'Egress'], 'ingress': [],
                    'egress': [
                        {'to': [{'namespaceSelector': {'matchLabels': {
                            'kubernetes.io/metadata.name': 'kube-system'}}}],
                         'ports': [{'port': 53, 'protocol': 'UDP'}, {'port': 53, 'protocol': 'TCP'}]},
                        {'to': [{'namespaceSelector': {'matchLabels': {
                            'kubernetes.io/metadata.name': 'platform'}},
                                 'podSelector': {'matchLabels': {'app': 'floci'}}}],
                         'ports': [{'port': 4577, 'protocol': 'TCP'}]}]}})
    apply({'apiVersion': 'v1', 'kind': 'Namespace',
           'metadata': {'name': NAMESPACE, 'labels': {'lab/owner': 'exploratory-notebooks'},
                        'annotations': {'lab/notebook-policy': 'v1'}}})


if __name__ == '__main__':
    install()
