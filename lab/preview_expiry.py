"""End only an exact delivery preview lease through the existing coordinator."""
from datetime import datetime, timezone
import json
import re

from common import STATE, k
from lifecycle import Store


def expire(name, fingerprint, expected_expiry):
    """Mark a preview due for cleanup; repeated requests cannot extend its lease."""
    if not re.fullmatch(r'lab-delivery-run-[1-9][0-9]*-[a-f0-9]{8}', name) or \
            not re.fullmatch('[a-f0-9]{64}', fingerprint):
        raise ValueError('Only an exact delivery preview can expire early.')
    identifier = 'delivery:' + name + ':' + fingerprint
    if Store(STATE / 'lifecycle.sqlite3').running_comparison_for(identifier):
        raise ValueError('A running comparison uses this preview. Wait for it to finish.')
    app = k('get', 'application/' + name, '-n', 'argocd', '-o', 'json', '--ignore-not-found')
    if not app.stdout.strip():
        return {'name': name, 'state': 'expired'}
    metadata = json.loads(app.stdout)['metadata']
    if metadata.get('labels', {}).get('lab/delivery') != 'preview' or \
            not metadata.get('annotations', {}).get('lab/preview-expires-at'):
        raise ValueError('Application is not an owned delivery preview.')
    if metadata['annotations']['lab/preview-expires-at'] != expected_expiry:
        raise ValueError('Preview lease changed. Refresh before expiring it.')
    definition = k('get', 'configmap/frozen-definition', '-n', name, '-o', 'json')
    value = json.loads(json.loads(definition.stdout)['data']['definition.json'])
    if value.get('fingerprint') != fingerprint:
        raise ValueError('Preview release changed. Refresh before expiring it.')
    expiry = datetime.now(timezone.utc).isoformat()
    k('annotate', 'application/' + name, '-n', 'argocd',
      'lab/preview-expires-at=' + expiry, '--overwrite')
    return {'name': name, 'state': 'expiring', 'expires_at': expiry}
