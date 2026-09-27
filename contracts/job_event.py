"""Small structured completion event shared by independent finite Jobs.

The event goes to scoped Kubernetes stdout collection. It has no network client,
credential access, query text or product content.
"""

from datetime import datetime, timezone
import json
import os
import re
import time


_SHA256 = re.compile(r'[0-9a-f]{64}\Z')
_SAFE_FIELDS = frozenset({
    'catalogue_manifest_sha256', 'query_manifest_sha256',
    'judgement_manifest_sha256', 'observation_sha256',
    'specification_sha256', 'report_sha256', 'source_release',
})


def emit(service, operation, state, started, **fields):
    """Write one bounded event; ignore any field outside the explicit contract."""
    event = {'event': 'lab.operation.completed', 'service': service,
             'operation': operation, 'state': state,
             'job_name': os.environ.get('LAB_JOB_NAME', '')[:63],
             'duration_ms': round((time.monotonic() - started) * 1000, 3),
             'observed_at': datetime.now(timezone.utc).isoformat()}
    for key, value in fields.items():
        if key not in _SAFE_FIELDS or not isinstance(value, str):
            continue
        if key.endswith('_sha256') and not _SHA256.fullmatch(value):
            continue
        if key == 'source_release' and (len(value) > 80 or not value.isprintable()):
            continue
        event[key] = value
    print(json.dumps(event, sort_keys=True), flush=True)
