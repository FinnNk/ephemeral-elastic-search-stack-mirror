"""Shared per-API pacing for finite functional captures; never used by Gatling."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import math
import threading
import time
from urllib import error, request

TRANSIENT = frozenset((429, 500, 502, 503, 504))


def retry_after(value):
    """Interpret either HTTP Retry-After form; malformed values use local backoff."""
    if value is None:
        return None
    try:
        seconds = float(value)
        return max(0, seconds) if math.isfinite(seconds) else None
    except (ValueError, TypeError):
        try:
            stamp = parsedate_to_datetime(value)
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            return max(0, (stamp - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return None


class Pacer:
    """Keep worker count fixed; space launches after overload and recover on success."""

    def __init__(self):
        self.changed = threading.Condition()
        self.interval = self.next_at = self.pause_until = 0
        self.adjust_after = 0
        self.healthy = 0
        self.stats = {'attempts': 0, 'retries': 0, 'transient_failures': 0,
                      'terminal_failures': 0, 'wait_seconds': 0, 'peak_interval_seconds': 0}

    def before(self, deadline):
        """Wait before reserving a launch so new overload signals affect waiting workers."""
        started = time.monotonic()
        with self.changed:
            while True:
                now = time.monotonic()
                ready = max(self.next_at, self.pause_until, now)
                if ready >= deadline:
                    raise TimeoutError('Capture request exhausted its retry/pacing budget.')
                if ready <= now:
                    self.next_at = now + self.interval
                    self.stats['attempts'] += 1
                    self.stats['wait_seconds'] += now - started
                    return max(0.001, min(10, deadline - now))
                self.changed.wait(ready - now)

    def success(self):
        with self.changed:
            self.healthy += 1
            if self.healthy >= 8:
                self.interval = self.interval / 2 if self.interval > .01 else 0
                self.healthy = 0
                self.changed.notify_all()

    def failure(self, delay, retrying):
        with self.changed:
            self.healthy = 0
            now = time.monotonic()
            # One concurrent burst is one capacity signal. Avoid multiplying
            # the slowdown eight times before any worker can observe it.
            if now >= self.adjust_after:
                self.interval = min(.25, max(.05, self.interval * 2))
                self.adjust_after = now + .2
            self.pause_until = max(self.pause_until, now + delay)
            self.stats['transient_failures'] += 1
            self.stats['retries'] += int(retrying)
            self.stats['peak_interval_seconds'] = max(self.stats['peak_interval_seconds'], self.interval)
            self.changed.notify_all()

    def summary(self):
        with self.changed:
            return {**self.stats, 'wait_seconds': round(self.stats['wait_seconds'], 6),
                    'final_interval_seconds': self.interval}

    def fetch(self, url, headers, budget=30):
        """Make fresh GETs with three attempts, a finite budget and shared backoff."""
        deadline = time.monotonic() + budget
        try:
            for attempt in range(3):
                timeout = self.before(deadline)
                try:
                    with request.urlopen(request.Request(url, headers=headers), timeout=timeout) as response:
                        value = json.load(response)
                    self.success()
                    return value
                except error.HTTPError as failure:
                    if failure.code not in TRANSIENT:
                        failure.close()
                        raise
                    delay = retry_after(failure.headers.get('Retry-After'))
                    failure.close()
                    self.failure(delay if delay is not None else .2 * (attempt + 1), attempt < 2)
                    if attempt == 2:
                        raise
                except (error.URLError, TimeoutError):
                    self.failure(.2 * (attempt + 1), attempt < 2)
                    if attempt == 2:
                        raise
        except Exception:
            with self.changed:
                self.stats['terminal_failures'] += 1
            raise
