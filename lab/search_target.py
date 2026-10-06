"""Resolve fixed delivery slots to their own Search API endpoints."""

def coordinates(name):
    if name in ('lab-delivery-production-blue', 'lab-delivery-production-green'):
        return 'lab-delivery-production', 'search-' + name.rsplit('-', 1)[1]
    return name, 'search'


def api_url(name):
    namespace, service = coordinates(name)
    return 'http://' + service + '.' + namespace + '.svc.cluster.local:8080'
