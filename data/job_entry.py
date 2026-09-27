"""Finite synthetic producer: generate, validate and publish one small pack."""

import json
import os
from pathlib import Path
import time

from generate_example import RELEASE, build
from job_event import emit
from publish import publish


def main():
    started = time.monotonic()
    output = Path('/output')
    release = output / 'release'
    try:
        build(release)
        result = publish(release, output / 'manifests', 'independent-example-v2', RELEASE,
                         blob_url=os.environ['DATA_BLOB_URL'])
    except Exception:
        emit('data-producer', 'data.publish', 'failed', started, source_release=RELEASE)
        raise
    emit('data-producer', 'data.publish', 'complete', started, source_release=RELEASE,
         catalogue_manifest_sha256=result['catalogue']['manifest_sha256'],
         query_manifest_sha256=result['query-suite']['manifest_sha256'],
         judgement_manifest_sha256=result['judgement-set']['manifest_sha256'])
    print(json.dumps({'release': RELEASE, 'artifacts': result}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
