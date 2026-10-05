"""Loopback-only UI and API for the local environment lifecycle."""
import hashlib
import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from common import STATE
from blob_config import service
from search_probe import search, parse_filters
from lifecycle import ActiveComparisonError, DATASET, RELEASES, local_lifecycle, parse_stamp, utcnow
from index_candidate import available_kinds
from input_selection import DEFAULTS
from control_identity import GiteaIdentity, Sessions, expired_cookie, session_cookie
from operation_telemetry import configure as configure_telemetry, request_span, response_status
from preview_routes import url as preview_url

PORT = 18082
UI = Path(__file__).with_name('control-ui.html')
DRAIN = STATE / 'control-drain'


class ControlServer(ThreadingHTTPServer):
    request_queue_size = 64
    daemon_threads = True


def route(path):
    return urllib.parse.urlparse(path).path.rstrip('/') or '/'


def environment_view(row):
    return {**row, 'browser_url': preview_url(row['name']) if row['state'] == 'ready' else None}


class Handler(BaseHTTPRequestHandler):
    controller = None
    sessions = None
    identity_provider = None
    canonical_host = None
    oidc_provider = None
    public_url = None

    def send_bytes(self, status, payload, content_type, extra_headers=None):
        response_status(status)
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy',
            "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; base-uri 'none'; form-action 'self'")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, status, value, extra_headers=None):
        self.send_bytes(status, json.dumps(value).encode(), 'application/json; charset=utf-8', extra_headers)

    def path_parts(self):
        return route(self.path).strip('/').split('/')

    def host_allowed(self):
        if self.command == 'GET' and route(self.path) == '/api/health':
            return True
        if self.canonical_host is None or self.headers.get('Host') == self.canonical_host:
            return True
        if self.command == 'GET':
            self.send_response(307)
            self.send_header('Location', (self.public_url or 'http://' + self.canonical_host) + self.path)
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
        else:
            self.send_json(421, {'error': 'Open the control UI on localhost.'})
        return False

    def identity(self):
        authorization = self.headers.get('Authorization', '')
        if self.oidc_provider:
            try:
                if not authorization.startswith('Bearer '):
                    return None
                return self.oidc_provider.verify(authorization[7:])
            except Exception:
                return None
        return self.sessions.get(self.headers.get('Cookie'))

    @staticmethod
    def visible(row, identity):
        return bool(row) and (identity['is_admin'] or identity.get('is_reader', False) or row['owner'] == identity['username'])

    def comparison_visible(self, row, identity):
        return bool(row) and self.visible(self.controller.store.get(row['baseline_id']), identity) and \
            self.visible(self.controller.store.get(row['candidate_id']), identity)

    def do_GET(self):
        with request_span('GET', route(self.path), self.headers):
            return self._do_GET()

    def _do_GET(self):
        if not self.host_allowed():
            return
        parts = self.path_parts()
        if parts == ['']:
            return self.send_bytes(200, UI.read_bytes(), 'text/html; charset=utf-8')
        if parts == ['control_lists.js']:
            return self.send_bytes(200, UI.with_name('control_lists.js').read_bytes(),
                                   'text/javascript; charset=utf-8')
        if parts == ['relevance-decision']:
            return self.send_bytes(200, UI.with_name('relevance-decision.html').read_bytes(),
                                   'text/html; charset=utf-8')
        if parts == ['api', 'health']:
            return self.send_json(503 if DRAIN.exists() else 200, {'ready': not DRAIN.exists()})
        if parts == ['api', 'auth']:
            return self.send_json(200, {'oidc': self.oidc_provider is not None, 'login_url': '/oauth2/start?rd=/', 'logout_url': '/oauth2/sign_out?rd=/oauth2/sign_in'})
        identity = self.identity()
        if identity is None:
            return self.send_json(401, {'error': 'Sign in to the lab.'})
        if parts == ['api', 'me']:
            return self.send_json(200, {key: value for key, value in identity.items() if key != 'expires_at'})
        if parts[:3] == ['api', 'delivery', 'operations'] and len(parts) in (4, 5):
            from delivery_operations import Operations
            row = Operations().get(parts[3])
            if row is None:
                return self.send_json(404, {'error': 'Delivery operation not found.'})
            if not self.visible(row, identity):
                return self.send_json(403, {'error': 'Delivery operation belongs to another owner.'})
            if len(parts) == 4:
                return self.send_json(200, row)
            if parts[4] == 'report' and (row.get('result') or {}).get('report'):
                reference = row['result']['report']
                container, name = reference['blob'].split('/', 1)
                payload = service().get_blob_client(container, name).download_blob().readall()
                if hashlib.sha256(payload).hexdigest() != reference['sha256']:
                    return self.send_json(502, {'error': 'Frozen delivery report hash differs.'})
                return self.send_bytes(200, payload, 'application/json; charset=utf-8')
            return self.send_json(409, {'error': 'Delivery report is not available.'})
        if identity.get('is_delivery_service'):
            return self.send_json(403, {'error': 'Actions identity is restricted to delivery operations.'})
        if parts == ['api', 'datasets']:
            releases = []
            for release_id in RELEASES:
                path = STATE / 'releases' / release_id / 'manifest.json'
                if path.exists():
                    releases.append({'release': release_id,
                                     'manifest': json.loads(path.read_text(encoding='utf-8'))})
            return self.send_json(200, releases)
        if parts == ['api', 'index-kinds']:
            return self.send_json(200, {release_id: available_kinds(release_id) for release_id in RELEASES})
        if parts == ['api', 'input-sets']:
            return self.send_json(200, DEFAULTS)
        if parts == ['api', 'notebooks']:
            from notebook_task import available
            return self.send_json(200, available())
        if parts == ['api', 'environments']:
            return self.send_json(200, [environment_view(row) for row in self.controller.store.all() if self.visible(row, identity)])
        if parts == ['api', 'comparisons']:
            return self.send_json(200, [row for row in self.controller.store.all_comparisons()
                                        if self.comparison_visible(row, identity)])
        if len(parts) >= 3 and parts[:2] == ['api', 'comparisons']:
            row = self.controller.store.get_comparison(parts[2])
            if row is None:
                return self.send_json(404, {'error': 'Comparison not found.'})
            if not self.comparison_visible(row, identity):
                return self.send_json(403, {'error': 'Comparison belongs to another owner.'})
            if len(parts) == 3:
                return self.send_json(200, environment_view(row))
            if len(parts) == 4 and parts[3] == 'report':
                if not row['report_blob']:
                    return self.send_json(409, {'error': 'Comparison has no saved report.'})
                container, blob_name = row['report_blob'].split('/', 1)
                account = service()
                payload = account.get_blob_client(container, blob_name).download_blob().readall()
                if hashlib.sha256(payload).hexdigest() != row['report_sha256']:
                    return self.send_json(502, {'error': 'Saved report hash differs from its record.'})
                return self.send_bytes(200, payload, 'application/json; charset=utf-8')
            if len(parts) == 4 and parts[3] == 'notebook':
                notebook = (row.get('summary') or {}).get('notebook') or {}
                if notebook.get('state') != 'complete':
                    return self.send_json(409, {'error': 'Comparison has no executed notebook.'})
                container, blob_name = notebook['executed_blob'].split('/', 1)
                payload = service().get_blob_client(container, blob_name).download_blob().readall()
                if hashlib.sha256(payload).hexdigest() != notebook['executed_sha256']:
                    return self.send_json(502, {'error': 'Executed notebook hash differs from its record.'})
                return self.send_bytes(200, payload, 'application/x-ipynb+json')
        if len(parts) >= 3 and parts[:2] == ['api', 'environments']:
            row = self.controller.store.get(parts[2])
            if row is None:
                return self.send_json(404, {'error': 'Environment not found.'})
            if not self.visible(row, identity):
                return self.send_json(403, {'error': 'Environment belongs to another owner.'})
            if len(parts) == 3:
                return self.send_json(200, row)
            if len(parts) == 4 and parts[3] == 'search':
                if DRAIN.exists():
                    return self.send_json(503, {'error': 'Control service is moving; retry shortly.'})
                if self.headers.get('X-Lab-Intent') != '1':
                    return self.send_json(400, {'error': 'Search requires X-Lab-Intent: 1.'})
                if row['state'] != 'ready':
                    return self.send_json(409, {'error': 'Environment is not ready.'})
                if utcnow() >= parse_stamp(row['expires_at']):
                    return self.send_json(409, {'error': 'Environment lease has expired.'})
                params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query, keep_blank_values=True)
                query = params.get('q', [''])[0]
                if not query.strip() or len(query) > 150:
                    return self.send_json(400, {'error': 'Enter a search term of 1–150 characters.'})
                try:
                    encoded = params.get('filters', ['{}'])
                    if len(encoded) != 1:
                        raise ValueError('Supply filters once.')
                    filters = parse_filters(encoded[0])
                    country = params.get('country', ['GB'])
                    currency = params.get('currency', ['GBP'])
                    if country != ['GB'] or currency != ['GBP']:
                        raise ValueError('This catalogue supports GB and GBP only.')
                except ValueError as error:
                    return self.send_json(400, {'error': str(error)})
                try:
                    answer = search(row['name'], query, filters=filters)
                except RuntimeError:
                    answer = None
                if answer is None:
                    return self.send_json(502, {'error': 'Search API did not return a result.'})
                if answer.get('filters') != filters:
                    return self.send_json(502, {'error': 'Search API returned different filters.'})
                try:
                    self.controller.activity(row['id']) if not identity.get('is_reader', False) else None
                except ValueError:
                    return self.send_json(409, {'error': 'Environment lease has expired.'})
                return self.send_json(200, answer)
        return self.send_json(404, {'error': 'Not found.'})

    def body(self):
        if self.headers.get('X-Lab-Intent') != '1' or self.headers.get('Content-Type') != 'application/json':
            raise ValueError('Use the local UI or send JSON with X-Lab-Intent: 1.')
        size = int(self.headers.get('Content-Length', '0'))
        if size < 0 or size > 4096:
            raise ValueError('Request body is too large.')
        value = json.loads(self.rfile.read(size))
        if not isinstance(value, dict):
            raise ValueError('Send a JSON object.')
        return value

    def do_POST(self):
        with request_span('POST', route(self.path), self.headers):
            return self._do_POST()

    def _do_POST(self):
        if not self.host_allowed():
            return
        if DRAIN.exists():
            return self.send_json(503, {'error': 'Control service is moving; retry shortly.'})
        parts = self.path_parts()
        try:
            payload = self.body()
            if parts == ['api', 'login']:
                if self.oidc_provider:
                    return self.send_json(403, {'error': 'Use OIDC sign-in; local recovery uses the operator CLI.'})
                identity = self.identity_provider.verify(payload['username'], payload['password'])
                token = self.sessions.create(identity)
                return self.send_json(200, identity, {'Set-Cookie': session_cookie(token)})
            identity = self.identity()
            if identity is None:
                return self.send_json(401, {'error': 'Sign in to the lab.'})
            if parts == ['api', 'logout']:
                self.sessions.discard(self.headers.get('Cookie'))
                return self.send_json(200, {'signed_out': True}, {'Set-Cookie': expired_cookie()})
            if identity.get('is_reader', False):
                return self.send_json(403, {'error': 'Reader accounts cannot change lab resources.'})
            if parts == ['api', 'delivery', 'operations']:
                if not identity['is_admin'] and not identity.get('is_delivery_service'):
                    return self.send_json(403, {'error': 'Delivery operations require a lab administrator.'})
                if payload.get('kind') == 'request-exception' and (
                        identity.get('is_delivery_service') or not identity['is_admin']):
                    return self.send_json(403, {'error': 'A human administrator must request a relevance decision.'})
                from delivery_operations import Operations
                store = Operations()
                row = store.submit(payload, identity, self.headers.get('Idempotency-Key'))
                if payload.get('pr') and row['state'] == 'accepted':
                    from delivery_source_comparison import status
                    status(payload['source_sha'], 'pending', row['progress'], row['id'])
                    store.update(row['id'], state='queued', progress=row['progress'])
                    row = store.get(row['id'])
                return self.send_json(202, row)
            if identity.get('is_delivery_service'):
                return self.send_json(403, {'error': 'Actions identity is restricted to delivery operations.'})
            if parts == ['api', 'environments', 'batch']:
                rows = self.controller.create_many(payload['names'], payload['build_run'],
                    owner=identity['username'], release_id=payload.get('release_id', DATASET))
                return self.send_json(201 if all(row['state'] == 'ready' for row in rows) else 202, rows)
            if parts == ['api', 'environments']:
                row = self.controller.create(payload['name'], payload['build_run'], owner=identity['username'],
                                             index_kind=payload.get('index_kind', 'shared'),
                                             release_id=payload.get('release_id', DATASET),
                                             index_recipe_sha256=payload.get('index_recipe_sha256') or None)
                return self.send_json(201 if row['state'] == 'ready' else 202, row)
            if parts == ['api', 'comparisons']:
                first = self.controller.store.get(payload['baseline_id'])
                second = self.controller.store.get(payload['candidate_id'])
                if not self.visible(first, identity) or not self.visible(second, identity):
                    return self.send_json(403, {'error': 'Comparison environment belongs to another owner.'})
                row = self.controller.compare(payload['baseline_id'], payload['candidate_id'], payload['mode'],
                                              profile=payload.get('profile', 'probe'),
                                              scope=payload.get('scope', 'full'),
                                              query_manifest_sha=payload.get('query_manifest_sha256') or None,
                                              judgement_manifest_sha=payload.get('judgement_manifest_sha256') or None,
                                              notebook=payload.get('notebook') or None)
                return self.send_json(201 if row['state'] == 'complete' else 202, row)
            if len(parts) == 4 and parts[:2] == ['api', 'environments']:
                if not self.visible(self.controller.store.get(parts[2]), identity):
                    return self.send_json(403, {'error': 'Environment belongs to another owner.'})
                if parts[3] == 'activity':
                    return self.send_json(200, self.controller.activity(parts[2]))
                if parts[3] == 'reconcile':
                    return self.send_json(200, self.controller.reconcile(parts[2]))
        except KeyError:
            return self.send_json(400, {'error': 'A required field is missing.'})
        except (ValueError, json.JSONDecodeError) as error:
            return self.send_json(400, {'error': str(error)})
        except RuntimeError:
            return self.send_json(502, {'error': 'Local build or cluster operation failed.'})
        return self.send_json(404, {'error': 'Not found.'})

    def do_DELETE(self):
        with request_span('DELETE', route(self.path), self.headers):
            return self._do_DELETE()

    def _do_DELETE(self):
        if not self.host_allowed():
            return
        if DRAIN.exists():
            return self.send_json(503, {'error': 'Control service is moving; retry shortly.'})
        parts = self.path_parts()
        try:
            payload = self.body()
            identity = self.identity()
            if identity is None:
                return self.send_json(401, {'error': 'Sign in to the lab.'})
            if identity.get('is_reader', False):
                return self.send_json(403, {'error': 'Reader accounts cannot change lab resources.'})
            if identity.get('is_delivery_service'):
                return self.send_json(403, {'error': 'Actions identity cannot delete resources.'})
            if parts == ['api', 'environments', 'batch']:
                instance_ids = payload['ids']
                if not isinstance(instance_ids, list) or any(
                        not self.visible(self.controller.store.get(instance_id), identity)
                        for instance_id in instance_ids):
                    return self.send_json(403, {'error': 'An environment belongs to another owner.'})
                return self.send_json(200, self.controller.delete_many(instance_ids))
            if len(parts) == 3 and parts[:2] == ['api', 'environments']:
                if not self.visible(self.controller.store.get(parts[2]), identity):
                    return self.send_json(403, {'error': 'Environment belongs to another owner.'})
                return self.send_json(200, self.controller.delete(parts[2]))
        except KeyError:
            return self.send_json(404, {'error': 'Environment not found.'})
        except ActiveComparisonError as error:
            return self.send_json(409, {'error': str(error)})
        except (ValueError, json.JSONDecodeError) as error:
            return self.send_json(400, {'error': str(error)})
        return self.send_json(404, {'error': 'Not found.'})


def serve():
    configure_telemetry('lab-control-api')
    controller = local_lifecycle(recover_comparisons=True)
    Handler.controller = controller
    Handler.sessions = Sessions()
    Handler.identity_provider = GiteaIdentity()
    if os.environ.get('LAB_OIDC_ISSUER'):
        from control_oidc import OIDCIdentity
        Handler.oidc_provider = OIDCIdentity()
    public_url = os.environ.get('LAB_CONTROL_PUBLIC_URL', f'http://localhost:{PORT}/').rstrip('/')
    Handler.canonical_host = urllib.parse.urlparse(public_url).netloc
    Handler.public_url = public_url
    bind_address = os.environ.get('LAB_CONTROL_BIND', '127.0.0.1')
    with ControlServer((bind_address, PORT), Handler) as server:
        print(f'Lifecycle UI: {public_url}/', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    serve()
