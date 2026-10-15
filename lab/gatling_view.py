"""Serve native Gatling assets through the owning operation's frozen evidence."""
import hashlib
import io
import mimetypes
import re
import urllib.parse
import zipfile

from blob_config import service
from delivery_gates import read

MAX_ARCHIVE = 50 * 1024 * 1024
MAX_MEMBER = 8 * 1024 * 1024
MAX_EXPANDED = 100 * 1024 * 1024
REPORT_CSP = (
    "sandbox allow-scripts allow-same-origin; default-src 'none'; "
    "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self' data:; connect-src 'none'; "
    "frame-src 'none'; worker-src 'none'; object-src 'none'; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'"
)


class ReportUnavailable(Exception):
    """The selected operation has no matching native report."""


def canonical_path(value):
    decoded = urllib.parse.unquote(value)
    if not decoded or any(c in decoded for c in ('\\', '\x00', '%', ':')) or \
            any(p in ('', '.', '..') for p in decoded.split('/')):
        raise ValueError('Invalid native report asset path.')
    return decoded


def response(operation, variant, side, asset):
    """Return verified report bytes, MIME type and restrictive response headers."""
    asset = canonical_path(asset)
    if side not in ('baseline', 'candidate'):
        raise ReportUnavailable('Gatling side not found.')
    reference = (operation.get('result') or {}).get('report')
    if not reference:
        raise ReportUnavailable('Native Gatling report is not available.')
    parent = read(reference)
    if parent.get('checks') is not None:
        matches = [c for c in parent['checks'] if c.get('variant') == variant]
        if len(matches) != 1 or not matches[0].get('evidence'):
            raise ReportUnavailable('Variant Gatling report not found.')
        parent = read(matches[0]['evidence'])
    elif variant != 'pair':
        raise ReportUnavailable('Variant Gatling report not found.')
    if parent.get('kind') != 'paired-api-performance':
        reference = parent.get('reports', {}).get('performance')
        if not reference:
            raise ReportUnavailable('Performance report is not available.')
        parent = read(reference)
    summary = parent.get(side) or {}
    sha, blob = summary.get('native_report_sha256'), summary.get('native_report_blob')
    if not sha or not blob:
        raise ReportUnavailable('The driver did not retain a native Gatling report.')
    if not re.fullmatch('[0-9a-f]{64}', sha) or blob != f'runs/{sha}/gatling-report.zip':
        raise ValueError('Native report reference differs from its hash.')
    client = service().get_blob_client('runs', f'{sha}/gatling-report.zip')
    if client.get_blob_properties().size > MAX_ARCHIVE:
        raise ValueError('Native report archive exceeds the size limit.')
    payload = client.download_blob().readall()
    if len(payload) > MAX_ARCHIVE or hashlib.sha256(payload).hexdigest() != sha:
        raise ValueError('Native report bytes differ from their hash or size limit.')
    headers = {'Content-Security-Policy': REPORT_CSP}
    if asset == 'download.zip':
        headers['Content-Disposition'] = f'attachment; filename="gatling-{side}.zip"'
        return payload, 'application/zip', headers
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        entries = archive.infolist()
        if len(entries) > 2048 or sum(i.file_size for i in entries) > MAX_EXPANDED:
            raise ValueError('Native report expanded size exceeds the limit.')
        matches = [i for i in entries if i.filename == asset and not i.is_dir()]
        if len(matches) != 1:
            raise ReportUnavailable('Native report asset not found.')
        member = matches[0]
        if member.file_size > MAX_MEMBER or member.flag_bits & 1:
            raise ValueError('Native report asset exceeds the limit or is encrypted.')
        body = archive.read(member)
    mime = {'.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html',
            '.svg': 'image/svg+xml'}.get('.' + asset.rsplit('.', 1)[-1])
    mime = mime or mimetypes.guess_type(asset)[0] or 'application/octet-stream'
    if mime.startswith('text/'):
        mime += '; charset=utf-8'
    return body, mime, headers
