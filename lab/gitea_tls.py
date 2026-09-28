"""Use the lab CA for Gitea HTTPS without replacing trust for other services."""

import os
import ssl
import urllib.request


def context():
    value = ssl.create_default_context()
    ca_file = os.environ.get('LAB_GITEA_CA_FILE')
    if ca_file:
        value.load_verify_locations(cafile=ca_file)
    return value


def open_url(request, timeout=30):
    return urllib.request.urlopen(request, context=context(), timeout=timeout)
