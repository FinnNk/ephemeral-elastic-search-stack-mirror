"""Blob configuration shared by local Floci and a future Azure deployment."""
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from common import STATE
sys.path.insert(0, str(STATE / 'python-libs'))
from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas

# Public emulator key from Floci 0.13.0 application.yml. Never use it for Azure.
DEMO_KEY = 'Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=='
DEFAULT_URL = 'http://127.0.0.1:14577/devstoreaccount1'
DEFAULT_POD_URL = 'http://floci.platform.svc:4577/devstoreaccount1'


def settings():
    account_url = os.environ.get('LAB_BLOB_ACCOUNT_URL', DEFAULT_URL).rstrip('/')
    container = os.environ.get('LAB_BLOB_CONTAINER', 'datasets')
    local = account_url == DEFAULT_URL
    pod_url = os.environ.get('LAB_BLOB_POD_URL', DEFAULT_POD_URL if local else account_url).rstrip('/')
    if not local and (urlparse(account_url).scheme != 'https' or
                      urlparse(pod_url).scheme != 'https'):
        raise ValueError('Azure Blob account and Pod URLs must use HTTPS.')
    if not container or '/' in container:
        raise ValueError('LAB_BLOB_CONTAINER must be one container name.')
    return account_url, container, pod_url, local


def credential(local):
    if local:
        return DEMO_KEY
    from azure.identity import DefaultAzureCredential
    return DefaultAzureCredential()


def service():
    account_url, _, _, local = settings()
    return BlobServiceClient(account_url=account_url, credential=credential(local))


def signed_read_url(blob_name, expiry):
    account_url, container, pod_url, local = settings()
    if local:
        sas = generate_blob_sas('devstoreaccount1', container, blob_name, account_key=DEMO_KEY,
                                permission=BlobSasPermissions(read=True), expiry=expiry)
    else:
        client = service()
        delegation = client.get_user_delegation_key(datetime.now(timezone.utc) - timedelta(minutes=5),
                                                    expiry)
        account = urlparse(account_url).hostname.split('.')[0]
        sas = generate_blob_sas(account, container, blob_name, user_delegation_key=delegation,
                                permission=BlobSasPermissions(read=True), expiry=expiry)
    return f'{pod_url}/{container}/{blob_name}?{sas}'
