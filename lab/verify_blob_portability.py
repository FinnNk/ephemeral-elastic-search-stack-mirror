"""Live local Floci read/write and immutable-hash check for the configured Blob client."""
import hashlib
import json
import sys
import uuid

sys.path.insert(0, 'research/platform-spike')
from blob_config import service, settings, signed_read_url
from azure.core.exceptions import ResourceExistsError
from common import record
from datetime import datetime, timedelta, timezone
from urllib.request import urlopen


def main():
    account = service()
    account_url, container, pod_url, local = settings()
    assert local, 'This live smoke is scoped to the local Floci emulator.'
    try:
        account.create_container(container)
    except ResourceExistsError:
        pass
    payload = b'{"release":"portability-probe","synthetic":true}\n'
    digest = hashlib.sha256(payload).hexdigest()
    name = 'portability-probes/' + uuid.uuid4().hex + '/manifest.json'
    blob = account.get_blob_client(container, name)
    try:
        blob.upload_blob(payload, overwrite=False)
        try:
            blob.upload_blob(b'changed', overwrite=False)
        except ResourceExistsError:
            pass
        else:
            raise AssertionError('Immutable Blob overwrite was accepted.')
        assert hashlib.sha256(blob.download_blob().readall()).hexdigest() == digest
        signed = signed_read_url(name, datetime.now(timezone.utc) + timedelta(minutes=15))
        # The in-cluster hostname is not resolvable on the host; use the loopback forward.
        signed = signed.replace(pod_url + '/', account_url + '/', 1)
        with urlopen(signed, timeout=30) as response:
            assert hashlib.sha256(response.read()).hexdigest() == digest
        result = {'local_floci': True, 'container': container, 'sha256': digest,
                  'read_write_roundtrip': True, 'conditional_overwrite_denied': True,
                  'signed_read': True}
        record('blob-portability', result)
        print(json.dumps(result, indent=2))
    finally:
        blob.delete_blob()


if __name__ == '__main__':
    main()
