"""Compare the previous fixed retries with shared pacing on a disposable HTTP API."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time
from urllib import error, request

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adaptive_pacing import Pacer


def trial(adaptive, capacity, count=48, recover_after=None):
    lock = threading.Lock()
    stats = {'active': 0, 'attempts': 0, 'overloaded': 0, 'peak_active': 0}

    class API(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            with lock:
                stats['attempts'] += 1
                limit = 8 if recover_after and stats['attempts'] > recover_after else capacity
                busy = stats['active'] >= limit
                if busy:
                    stats['overloaded'] += 1
                else:
                    stats['active'] += 1
                    stats['peak_active'] = max(stats['peak_active'], stats['active'])
            if not busy:
                time.sleep(.08)
            body = b'{"ids":[]}'
            self.send_response(503 if busy else 200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            finally:
                if not busy:
                    with lock:
                        stats['active'] -= 1

    server = ThreadingHTTPServer(('127.0.0.1', 0), API)
    server.daemon_threads = True
    server.request_queue_size = 32
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}/search'
    pacer = Pacer()

    def capture(_index):
        try:
            if adaptive:
                pacer.fetch(url, {})
            else:
                for attempt in range(3):
                    try:
                        with request.urlopen(url, timeout=10) as response:
                            json.load(response)
                        break
                    except (error.URLError, TimeoutError) as failure:
                        if isinstance(failure, error.HTTPError):
                            failure.close()
                            if failure.code < 500:
                                raise
                        if attempt == 2:
                            raise
                        time.sleep(.2 * (attempt + 1))
            return True
        except (error.URLError, TimeoutError):
            return False

    started = time.monotonic()
    try:
        with ThreadPoolExecutor(max_workers=8) as workers:
            completed = list(workers.map(capture, range(count)))
        seconds = time.monotonic() - started
        return {'method': 'adaptive' if adaptive else 'fixed-retry', 'capacity': capacity,
                'recover_after_attempts': recover_after,
                'query_count': count, 'workers': 8, 'seconds': round(seconds, 4),
                'failed_queries': completed.count(False), 'attempts': stats['attempts'],
                'overloaded': stats['overloaded'], 'peak_active': stats['peak_active'],
                'pacing': pacer.summary() if adaptive else None}
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    trials = [trial(adaptive, capacity, recover_after=recovery) for capacity, recovery in
              ((8, None), (2, None), (2, 16))
              for _repeat in range(3) for adaptive in (False, True)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'service_delay_seconds': .08, 'trials': trials},
                                     indent=2) + '\n', encoding='utf-8')
    print(json.dumps(trials, indent=2))


if __name__ == '__main__':
    main()
