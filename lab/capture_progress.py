"""Small, thread-safe counters for finite capture Jobs; never log query text."""
import json
import threading
import time


class Progress:
    def __init__(self, total, pacers, interval=1):
        self.total, self.pacers, self.interval = total, pacers, interval
        self.done = self.failed = 0
        self.lock = threading.Lock()
        self.last = -float('inf')
        self.send()

    def completed(self, row):
        with self.lock:
            self.done += 1
            self.failed += int('error' in row)
            self.send()
        return row

    def send(self):
        now = time.monotonic()
        if self.done != self.total and now-self.last < self.interval:
            return
        self.last = now
        pacing = [p.summary() for p in self.pacers.values()]
        event = {'total':self.total, 'completed':self.done, 'failed':self.failed,
                 'retries':sum(p['retries'] for p in pacing),
                 'pacing_wait_seconds':round(sum(p['wait_seconds'] for p in pacing),3)}
        print('LAB_EVALUATION_PROGRESS '+json.dumps(event,sort_keys=True),flush=True)
