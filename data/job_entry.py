"""Finite synthetic producer: generate, validate and publish one small pack."""

import json
import os
from pathlib import Path

from generate_example import RELEASE, build
from publish import publish


def main():
    output = Path('/output')
    release = output / 'release'
    build(release)
    result = publish(release, output / 'manifests', 'independent-example-v1',
                     blob_url=os.environ['DATA_BLOB_URL'])
    print(json.dumps({'release': RELEASE, 'artifacts': result}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
