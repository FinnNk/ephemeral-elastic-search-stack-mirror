"""Grant the preview router access within one lab search namespace."""
from common import apply


def bind(namespace):
    apply({'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'RoleBinding',
        'metadata': {'name': 'lab-preview-routes', 'namespace': namespace},
        'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'ClusterRole',
                    'name': 'lab-preview-route-writer'},
        'subjects': [{'kind': 'ServiceAccount', 'name': 'lab-preview-routes', 'namespace': 'lab-ingress'}]})
