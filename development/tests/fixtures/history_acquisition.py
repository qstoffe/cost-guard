"""Deterministic four-root capture slices with finite source-fault injection."""
from collections import Counter

from src.reports.watch_capture import capture_rows
from src.watch.card_workers import CardResult


class CaptureWorkers:
    limit = 4

    def __init__(self, service, failures=None):
        self.service = service
        self.jobs = {}
        self.failures = failures or {}
        self.attempts = Counter()

    def submit(self, root, generation, now_ms, previous=None, focal_ids=()):
        self.jobs[root.session_id] = (root, generation, now_ms, previous, focal_ids)
        return True

    def drain(self):
        pending, self.jobs = self.jobs, {}
        results = []
        for key, (root, generation, now_ms, previous, focal_ids) in pending.items():
            self.attempts[key] += 1
            failures = self.failures.get(key, [])
            if failures:
                results.append(CardResult(key, generation, 'unavailable', failures.pop(0)))
                continue
            capture, item = capture_rows(self.service, root, previous, focal_ids)
            results.append(CardResult(key, generation, 'rows', (capture, (), item.snapshot), now_ms))
        return results
