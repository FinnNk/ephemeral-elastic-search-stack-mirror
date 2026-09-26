"""Loopback-only UI and API for the local environment lifecycle foundation."""
import json
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, 'research/platform-spike')
from common import STATE
from measure import search
from lifecycle import DATASET, local_lifecycle, parse_stamp, utcnow

PORT = 18082
UI = Path(__file__).with_name('control-ui.html')


def route(path):
    return urllib.parse.urlparse(path).path.rstrip('/') or '/'


class Handler(BaseHTTPRequestHandler):
    controller = None

    def send_bytes(self, status, payload, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, status, value):
        self.send_bytes(status, json.dumps(value).encode(), 'application/json; charset=utf-8')

    def path_parts(self):
        return route(self.path).strip('/').split('/')

    def do_GET(self):
        parts = self.path_parts()
        if parts == ['']:
            return self.send_bytes(200, UI.read_bytes(), 'text/html; charset=utf-8')
        if parts == ['api', 'health']:
            return self.send_json(200, {'ready': True})
        if parts == ['api', 'datasets']:
            manifest = json.loads((STATE / 'releases' / DATASET / 'manifest.json').read_text())
            return self.send_json(200, [{'release': DATASET, 'manifest': manifest}])
        if parts == ['api', 'environments']:
            return self.send_json(200, self.controller.store.all())
        if len(parts) >= 3 and parts[:2] == ['api', 'environments']:
            row = self.controller.store.get(parts[2])
            if row is None:
                return self.send_json(404, {'error': 'Environment not found.'})
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
                if not query or len(query) > 150:
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
        return json.loads(self.rfile.read(size))

    def do_POST(self):
        parts = self.path_parts()
        try:
            payload = self.body()
            if parts == ['api', 'environments']:
                row = self.controller.create(payload['name'], payload['build_run'])
                return self.send_json(201 if row['state'] == 'ready' else 202, row)
            if len(parts) == 4 and parts[:2] == ['api', 'environments']:
                if parts[3] == 'activity':
                    return self.send_json(200, self.controller.activity(parts[2]))
                if parts[3] == 'reconcile':
                    return self.send_json(200, self.controller.reconcile(parts[2]))
        except KeyError:
            return self.send_json(404, {'error': 'Environment or required field not found.'})
        except (ValueError, json.JSONDecodeError) as error:
            return self.send_json(400, {'error': str(error)})
        except RuntimeError:
            return self.send_json(502, {'error': 'Local build or cluster operation failed.'})
        return self.send_json(404, {'error': 'Not found.'})

    def do_DELETE(self):
        parts = self.path_parts()
        try:
            self.body()
            if len(parts) == 3 and parts[:2] == ['api', 'environments']:
                return self.send_json(200, self.controller.delete(parts[2]))
        except KeyError:
            return self.send_json(404, {'error': 'Environment not found.'})
        except (ValueError, json.JSONDecodeError) as error:
            return self.send_json(400, {'error': str(error)})
        return self.send_json(404, {'error': 'Not found.'})


def reconcile_loop(controller, stop):
    while not stop.wait(60):
        try:
            controller.expire()
        except Exception as error:
            print('Lifecycle reconciliation failed:', type(error).__name__, file=sys.stderr, flush=True)


def serve():
    controller = local_lifecycle()
    Handler.controller = controller
    stop = threading.Event()
    threading.Thread(target=reconcile_loop, args=(controller, stop), daemon=True).start()
    with ThreadingHTTPServer(('127.0.0.1', PORT), Handler) as server:
        print(f'Local lifecycle UI: http://127.0.0.1:{PORT}/', flush=True)
        try:
            server.serve_forever()
        finally:
            stop.set()


if __name__ == '__main__':
    serve()
