"""Opt-in warm-complete idle economy window for the whole-Web benchmark.

Numeric counters only: host CPU/IO/RAM, Live publication count, queued/running
finite jobs, fixture source request counters and report starts. The browser owns
the window boundaries; nothing here changes product scheduling.
"""
import os
import sys
from threading import Event, Thread
import time


class HostIdleTimeline:
    """Host-side one-second samples, taken from the existing resource sampler thread."""

    def __init__(self, jobs, publications, cpu_origin, catalog=None):
        self.jobs, self.publications, self.cpu_origin, self.catalog = jobs, publications, cpu_origin, catalog
        self.rows, self.last = [], float('-inf')

    def _catalog_pending(self):
        # Sessions scalar warming rows still not current, ignoring the slice delay; None where the arm has no such warming.
        catalog = self.catalog
        if catalog is None or not hasattr(catalog, '_targets'):
            return None
        with catalog.lock:
            keys = {key for lease in catalog.leases.values() if catalog._browsing(lease) for key in lease.get('visible', ())}
            if not keys and catalog.warm:
                keys = set(catalog.last_page or sorted(catalog.roots,
                    key=lambda key: (-(catalog.activity.get(key) or 0), key))[:50])
            return sum(not catalog._current(key) for key in keys if key in catalog.roots)

    def sample(self, read):
        if time.monotonic() - self.last < 1:
            return
        self.last = time.monotonic()
        with self.jobs._lock:
            busy = sum(job['status'] in ('queued', 'running') for job in self.jobs._jobs.values())
        own = (read(os.getpid()) if sys.platform == 'win32' else None) or {}
        self.rows.append(dict(wall_ms=int(time.time() * 1000), cpu_seconds=time.process_time() - self.cpu_origin,
            publications=len(self.publications), busy_jobs=busy, catalog_pending=self._catalog_pending(),
            working_set_bytes=own.get('working_set_bytes'),
            read_bytes=own.get('read_bytes'), write_bytes=own.get('write_bytes')))


class SourceCounters:
    """Fixture-source counter samples over the owned pipe; never combined with update control."""

    def __init__(self, snapshot):
        self.snapshot, self.rows, self.stopping = snapshot, [], Event()
        self.thread = Thread(target=self._run, daemon=True)

    def _run(self):
        while not self.stopping.wait(1):
            self.rows.append(dict(wall_ms=int(time.time() * 1000), **self.snapshot()))

    def start(self):
        self.thread.start()

    def stop(self):
        self.stopping.set()
        if self.thread.ident is not None:
            self.thread.join(5)
        if self.thread.is_alive():
            raise RuntimeError('fixture_source_counter_sampler_alive')


def _bounds(rows, start, end):
    inside = [row for row in rows if start <= row['wall_ms'] <= end]
    return inside, (inside[0], inside[-1]) if len(inside) >= 2 else (None, None)


def summarize(window, host_rows, source_rows, imports):
    """Deltas between the first and last sample strictly inside the browser-owned window."""
    start, end = window['start_wall_ms'], window['end_wall_ms']
    inside, (first, last) = _bounds(host_rows, start, end)
    _, (source_first, source_last) = _bounds(source_rows, start, end)
    if first is None or source_first is None:
        return dict(window_seconds=(end - start) / 1000, complete=False)
    seconds = (last['wall_ms'] - first['wall_ms']) / 1000
    source_seconds = (source_last['wall_ms'] - source_first['wall_ms']) / 1000
    requests = {key: value - source_first['requests'].get(key, 0) for key, value in source_last['requests'].items()}
    total = sum(requests.values())
    reports = [report for process in imports for report in process.get('reports', ())
               if start <= (report.get('started_wall_ms') or 0) <= end]
    sets = [row['working_set_bytes'] for row in inside if row['working_set_bytes'] is not None]

    def delta(key):
        return None if first[key] is None or last[key] is None else last[key] - first[key]

    return dict(complete=True, window_seconds=(end - start) / 1000, host_sampled_seconds=seconds,
        host_cpu_seconds=last['cpu_seconds'] - first['cpu_seconds'],
        host_cpu_percent=100 * (last['cpu_seconds'] - first['cpu_seconds']) / seconds if seconds else None,
        host_read_bytes=delta('read_bytes'), host_write_bytes=delta('write_bytes'),
        host_working_set_mib=dict(maximum=max(sets) / 2**20, final=sets[-1] / 2**20) if sets else None,
        live_publications=last['publications'] - first['publications'],
        busy_job_samples=sum(row['busy_jobs'] > 0 for row in inside), samples=len(inside),
        catalog_pending_samples=sum((row.get('catalog_pending') or 0) > 0 for row in inside),
        source_sampled_seconds=source_seconds, source_requests=requests, source_requests_total=total,
        source_requests_per_hour=total * 3600 / source_seconds if source_seconds else None,
        source_bytes=source_last['bytes'] - source_first['bytes'],
        reports_started=sorted(report['kind'] for report in reports),
        report_cpu_seconds=sum(report.get('cpu_seconds') or 0 for report in reports),
        limitation='Host-process counters plus observed report starts; finite children that start and exit '
            'between samples contribute only via their report records. Fixed browser settle precedes the window; '
            'busy_job_samples shows whether warming was actually complete.')
