"""One optional finite lane, owned/ticked/closed by the existing Web host."""
import json
from threading import RLock
import time

from src.benchmarks import fetch_snapshot, parse_pages, SOURCE_URL
from src.cache.benchmark import BenchmarkCache
from src.application.projection import benchmark_view
from src.reports import ReportRequest
from .jobs import ReportJobs


def run_benchmark(sender, request):
    try:
        result = dict(error=None, source=dict(status='acquired'), benchmark=fetch_snapshot())
        sender.send(('result', json.dumps(result, allow_nan=False).encode('ascii')))
    except Exception:
        sender.send(('error', 'benchmark_unavailable'))
    finally:
        sender.close()


class BenchmarkLane:
    def __init__(self, root, *, jobs=None, clock=time.monotonic, wall_clock=time.time):
        self.jobs = jobs or ReportJobs(target=run_benchmark)
        self.cache = BenchmarkCache(root)
        self.clock, self.wall_clock = clock, wall_clock
        self.lock = RLock()
        self.snapshot = None
        self.job = None
        self.requested = False
        self.forced = False
        self.next_due = 0
        self.started = 0
        self.failures = 0
        self.error = None
        self.cached = self.cache.read()
        if self.cached:
            try:
                self.snapshot = self._parse(self.cached)
            except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
                self.cached = None

    def _parse(self, value):
        if value.get('schema') != 1 or value['fetched_at_ms'] > int(self.wall_clock() * 1000):
            raise ValueError('benchmark_cache_identity')
        return parse_pages(value['pages'], value['fetched_at_ms'])

    def view(self, references=(), *, timezone_id='UTC'):
        with self.lock:
            self.requested = True
            value = benchmark_view(self.snapshot, references, now_ms=int(self.wall_clock() * 1000), timezone_id=timezone_id)
            return dict(**value, source_url=SOURCE_URL, unavailable=self.error is not None,
                refreshing=self.forced or self.job is not None)

    def refresh(self):
        """Coalesce manual demand, bypassing only automatic freshness/backoff."""
        with self.lock:
            self.requested = True
            if self.job is None:
                self.forced = True

    def tick(self):
        with self.lock:
            now = self.clock()
            self.jobs.tick()  # Reap terminal children even during the 24-hour quiet period.
            if self.job:
                state = self.jobs.snapshot(self.job)
                if state and state['status'] in {'queued', 'running'} and now - self.started < 25:
                    return
                try:
                    if not state or state['status'] != 'complete':
                        raise ValueError('benchmark_unavailable')
                    value = state['result']['benchmark']
                    snapshot = self._parse(value)
                    self.cache.put(value)
                    self.cached, self.snapshot = value, snapshot
                    self.failures, self.error = 0, None
                    self.next_due = now + 86400
                except (ValueError, KeyError, TypeError, AttributeError, OSError, RecursionError):
                    self.failures = min(6, self.failures + 1)
                    self.error = 'benchmark_unavailable'
                    self.next_due = now + min(21600, 300 * 2 ** self.failures)
                finally:
                    self.jobs.cancel(self.job)
                    self.job = None
            fresh = self.snapshot and 0 <= int(self.wall_clock() * 1000) - self.snapshot.fetched_at_ms < 86400000
            if self.forced or self.requested and not fresh and now >= self.next_due:
                self.job = self.jobs.submit(ReportRequest())
                self.forced = False
                self.started = now
                self.jobs.tick()

    def close(self):
        self.jobs.close()
