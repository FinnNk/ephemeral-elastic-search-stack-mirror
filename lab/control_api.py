"""Loopback-only UI and API for the local environment lifecycle."""
import hashlib
import json
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, 'research/platform-spike')
from common import STATE
from blob_config import service
from measure import search
from lifecycle import ActiveComparisonError, DATASET, RELEASES, local_lifecycle, parse_stamp, utcnow
from index_candidate import available_kinds
from control_identity import GiteaIdentity, Sessions, expired_cookie, session_cookie

PORT = 18082
UI = Path(__file__).with_name('control-ui.html')


class ControlServer(ThreadingHTTPServer):
    request_queue_size = 64
    daemon_threads = True


def route(path):
    return urllib.parse.urlparse(path).path.rstrip('/') or '/'


class Handler(BaseHTTPRequestHandler):
    controller = None
    sessions = None
    identity_provider = None
    canonical_host = None

    def send_bytes(self, status, payload, content_type, extra_headers=None):
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
        if self.canonical_host is None or self.headers.get('Host') == self.canonical_host:
            return True
        if self.command == 'GET':
            self.send_response(307)
            self.send_header('Location', 'http://' + self.canonical_host + self.path)
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
        else:
            self.send_json(421, {'error': 'Open the control UI on localhost.'})
        return False

    def identity(self):
        return self.sessions.get(self.headers.get('Cookie'))

    @staticmethod
    def visible(row, identity):
        return bool(row) and (identity['is_admin'] or row['owner'] == identity['username'])

    def comparison_visible(self, row, identity):
        return bool(row) and self.visible(self.controller.store.get(row['baseline_id']), identity) and \
            self.visible(self.controller.store.get(row['candidate_id']), identity)

    def do_GET(self):
        if not self.host_allowed():
            return
        parts = self.path_parts()
        if parts == ['']:
            return self.send_bytes(200, UI.read_bytes(), 'text/html; charset=utf-8')
        if parts == ['api', 'health']:
            return self.send_json(200, {'ready': True})
        identity = self.identity()
        if identity is None:
            return self.send_json(401, {'error': 'Sign in with Gitea.'})
        if parts == ['api', 'me']:
            return self.send_json(200, {'username': identity['username'], 'is_admin': identity['is_admin']})
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
        if parts == ['api', 'environments']:
            return self.send_json(200, [row for row in self.controller.store.all() if self.visible(row, identity)])
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
                return self.send_json(200, row)
            if len(parts) == 4 and parts[3] == 'report':
                if not row['report_blob']:
                    return self.send_json(409, {'error': 'Comparison has no saved report.'})
                container, blob_name = row['report_blob'].split('/', 1)
                account = service()
                payload = account.get_blob_client(container, blob_name).download_blob().readall()
                if hashlib.sha256(payload).hexdigest() != row['report_sha256']:
                    return self.send_json(502, {'error': 'Saved report hash differs from its record.'})
                return self.send_bytes(200, payload, 'application/json; charset=utf-8')
        if len(parts) >= 3 and parts[:2] == ['api', 'environments']:
            row = self.controller.store.get(parts[2])
            if row is None:
                return self.send_json(404, {'error': 'Environment not found.'})
            if not self.visible(row, identity):
                return self.send_json(403, {'error': 'Environment belongs to another owner.'})
            if len(parts) == 3:
                return self.send_json(200, row)
            if len(parts) == 4 and parts[3] == 'search':
                if self.headers.get('X-Lab-Intent') != '1':
                    return self.send_json(400, {'error': 'Search requires X-Lab-Intent: 1.'})
                if row['state'] != 'ready':
                    return self.send_json(409, {'error': 'Environment is not ready.'})
                if utcnow() >= parse_stamp(row['expires_at']):
                    return self.send_json(409, {'error': 'Environment lease has expired.'})
                query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('q', [''])[0]
                if not query.strip() or len(query) > 150:
                    return self.send_json(400, {'error': 'Enter a search term of 1–150 characters.'})
                try:
                    answer = search(row['name'], query)
                except RuntimeError:
                    answer = None
                if answer is None:
                    return self.send_json(502, {'error': 'Search API did not return a result.'})
                try:
                    self.controller.activity(row['id'])
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
        if not self.host_allowed():
            return
        parts = self.path_parts()
        try:
            payload = self.body()
            if parts == ['api', 'login']:
                identity = self.identity_provider.verify(payload['username'], payload['password'])
                token = self.sessions.create(identity)
                return self.send_json(200, identity, {'Set-Cookie': session_cookie(token)})
            identity = self.identity()
            if identity is None:
                return self.send_json(401, {'error': 'Sign in with Gitea.'})
            if parts == ['api', 'logout']:
                self.sessions.discard(self.headers.get('Cookie'))
                return self.send_json(200, {'signed_out': True}, {'Set-Cookie': expired_cookie()})
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
                                              scope=payload.get('scope', 'full'))
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
        if not self.host_allowed():
            return
        parts = self.path_parts()
        try:
            payload = self.body()
            identity = self.identity()
            if identity is None:
                return self.send_json(401, {'error': 'Sign in with Gitea.'})
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
    controller = local_lifecycle(recover_comparisons=True)
    Handler.controller = controller
    Handler.sessions = Sessions()
    Handler.identity_provider = GiteaIdentity()
    Handler.canonical_host = f'localhost:{PORT}'
    with ControlServer(('127.0.0.1', PORT), Handler) as server:
        print(f'Local lifecycle UI: http://localhost:{PORT}/', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    serve()
