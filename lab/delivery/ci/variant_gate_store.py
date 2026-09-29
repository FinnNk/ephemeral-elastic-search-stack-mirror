"""Publish and retrieve signed variant gate evidence in the Nexus raw repository."""

import argparse
import base64
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request


def artifact(base, source_sha, name, username, password, content=None):
    build_path = re.fullmatch(r'builds/[0-9a-f]{40}/[1-9][0-9]*-[1-9][0-9]*\.json', name)
    if not re.fullmatch(r'[0-9a-f]{40}', source_sha) or not (
            name in {'report.json', 'attestation.json', 'approvals.json'} or
            build_path and name.split('/')[1] == source_sha):
        raise ValueError('Invalid gate artifact identity.')
    url = base.rstrip('/') + ('/' + name if build_path else
                             '/variant-gates/' + source_sha + '/' + name)
    token = base64.b64encode((username + ':' + password).encode()).decode()
    headers = {'Authorization': 'Basic ' + token,
               'Content-Type': 'application/json'}
    request = urllib.request.Request(url, data=content,
        method='PUT' if content is not None else 'GET', headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if error.code == 404 and content is None:
            return None
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('publish-evidence', 'publish-approval', 'fetch'))
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--attestation', type=Path)
    parser.add_argument('--approval', type=Path)
    parser.add_argument('--directory', type=Path)
    args = parser.parse_args()
    def request(name, content=None):
        return artifact(os.environ['ARTIFACT_URL'], args.source_sha, name,
                        os.environ['NEXUS_USER'], os.environ['NEXUS_PASSWORD'], content)
    def build_receipt(attestation):
        run, attempt = (str(attestation.get(key, '')) for key in
                        ('build_run_id', 'build_attempt'))
        if not re.fullmatch(r'[1-9][0-9]*', run) or not re.fullmatch(
                r'[1-9][0-9]*', attempt):
            raise ValueError('Attestation has no exact source build attempt.')
        payload = request(f'builds/{args.source_sha}/{run}-{attempt}.json')
        import hashlib
        if payload is None or hashlib.sha256(payload).hexdigest() != \
                attestation.get('build_receipt_sha256'):
            raise ValueError('Trusted source build receipt is absent or changed.')
        return payload
    if args.action == 'publish-evidence':
        if not args.report or not args.attestation:
            parser.error('Evidence publication needs a report and attestation.')
        report, attestation = args.report.read_bytes(), args.attestation.read_bytes()
        receipt = json.loads(attestation)
        if receipt.get('source_sha') != args.source_sha or not re.fullmatch(
                '[0-9a-f]{64}', str(receipt.get('report_sha256', ''))):
            raise ValueError('Evidence attestation has another source or malformed digest.')
        import hashlib
        if hashlib.sha256(report).hexdigest() != receipt['report_sha256']:
            raise ValueError('Evidence attestation has another report.')
        build_receipt(receipt)
        for name, payload in (('report.json', report), ('attestation.json', attestation)):
            existing = request(name)
            if existing is not None and existing != payload:
                raise ValueError('Refusing to replace frozen ' + name)
            if existing is None:
                request(name, payload)
            if request(name) != payload:
                raise ValueError('Evidence read-back differs: ' + name)
    elif args.action == 'publish-approval':
        if not args.approval:
            parser.error('Approval publication needs a signed receipt.')
        approval = json.loads(args.approval.read_bytes())
        if approval.get('source_sha') != args.source_sha or \
                approval.get('kind') != 'variant-exception-approval':
            raise ValueError('Approval belongs to another source or contract.')
        existing = request('approvals.json')
        approvals = json.loads(existing) if existing is not None else []
        if not isinstance(approvals, list):
            raise ValueError('Approval index is malformed.')
        if approval not in approvals:
            approvals.append(approval)
            payload = (json.dumps(approvals, sort_keys=True, separators=(',', ':')) + '\n').encode()
            request('approvals.json', payload)
            if request('approvals.json') != payload:
                raise ValueError('Approval read-back differs.')
    else:
        if not args.directory:
            parser.error('Fetch needs an output directory.')
        args.directory.mkdir(parents=True, exist_ok=True)
        for name in ('report.json', 'attestation.json'):
            payload = request(name)
            if payload is None:
                raise ValueError('No frozen gate evidence at the exact source revision: ' + name)
            (args.directory / name).write_bytes(payload)
        (args.directory / 'build-receipt.json').write_bytes(build_receipt(
            json.loads((args.directory / 'attestation.json').read_bytes())))
        (args.directory / 'approvals.json').write_bytes(request('approvals.json') or b'[]')


if __name__ == '__main__':
    main()
