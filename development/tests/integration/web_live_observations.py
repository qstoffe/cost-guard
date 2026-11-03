"""Probe-only, bounded metadata timings; no personal payloads or runtime telemetry."""
from collections import Counter
from contextlib import contextmanager, ExitStack
from functools import wraps
import json
import multiprocessing
from pathlib import Path
import sys
from threading import Lock, enumerate as threads, get_ident
import time
import traceback
from unittest.mock import patch


class ProbeObservations:
    def __init__(self):
        self.started = time.monotonic()
        self.lock = Lock()
        self.pending = {}
        self.completed = Counter()
        self.maximum = Counter()
        self.errors = Counter()
        self.last_completed = {}
        self.stage = 'startup'
        self.http_maximum = 0
        self.http_requests = 0

    @contextmanager
    def phase(self, name):
        key = get_ident(), name
        started = time.monotonic()
        with self.lock:
            self.pending[key] = started
        try:
            yield
        except BaseException:
            with self.lock:
                self.errors[name] += 1
            raise
        finally:
            seconds = time.monotonic() - started
            with self.lock:
                self.pending.pop(key, None)
                self.completed[name] += 1
                self.maximum[name] = max(self.maximum[name], round(seconds, 4))
                self.last_completed[name] = round(time.monotonic() - self.started, 4)
                if name.startswith('http.'):
                    self.http_requests += 1
                    self.http_maximum = max(self.http_maximum, round(seconds, 4))

    def wrapper(self, original, name):
        @wraps(original)
        def wrapped(*args, **kwargs):
            with self.phase(name):
                return original(*args, **kwargs)
        return wrapped

    @contextmanager
    def installed(self):
        from src.application.live import LiveRuntime
        from src.accounts.acquisition import AccountAcquisition
        from src.accounts.refresh_loop import AccountRefreshLoop
        from src.reports.service import ReportService
        from src.watch.today_ccost import WatchTodayCCost
        from src.watch.web_coordinator import WebWatchCoordinator
        from src.watch.card_workers import CardWorkers
        from src.web.host import WebHost
        from src.web.jobs import ReportJobs
        from src.web.events import EventHub
        from src.web.http import LoopbackServer
        with ExitStack() as stack:
            for owner, methods in (
                (WebHost, ('close',)), (LiveRuntime, ('close', '_publish_frame')),
                (AccountAcquisition, ('close',)), (AccountRefreshLoop, ('close',)),
                (WebWatchCoordinator, ('_account_history', '_detail_capture', 'close')),
                (CardWorkers, ('_capture', 'close')), (ReportJobs, ('tick', 'close')),
                (EventHub, ('close',)), (LoopbackServer, ('server_close',)),
                (WatchTodayCCost, ('schedule_history', 'advance_history')),
                (ReportService, ('watch_history_batch', 'project_watch_today', 'publish_watch_history')),
            ):
                for method in methods:
                    name = owner.__name__ + '.' + method
                    stack.enter_context(patch.object(owner, method, self.wrapper(getattr(owner, method), name)))
            yield

    def snapshot(self, host):
        now = time.monotonic()
        with self.lock:
            result = dict(elapsed_seconds=round(now - self.started, 4), completed=dict(self.completed),
                max_seconds=dict(self.maximum), errors=dict(self.errors),
                last_completed_seconds=dict(self.last_completed), stage=self.stage,
                pending=[dict(phase=phase, seconds=round(now - started, 4))
                         for (_, phase), started in self.pending.items()],
                http_requests=self.http_requests, http_max_seconds=self.http_maximum)
        owned = [thread for thread in threads() if thread.name.startswith('cost-guard-')]
        frames = sys._current_frames()
        result.update(owned_threads=len(owned), owned_processes=len(multiprocessing.active_children()),
            stacks=[dict(thread=thread.name, frames=[dict(file=Path(frame.filename).name,
                function=frame.name, line=frame.lineno)
                for frame in traceback.extract_stack(frames[thread.ident])[-8:]])
                for thread in owned if thread.ident in frames])
        if host.live and host.live.driver:
            coordinator = host.live.driver.coordinator
            if hasattr(coordinator, 'card_workers'):
                result['work'] = dict(card_jobs=len(coordinator.card_workers.jobs),
                    history_pending=bool(coordinator.history_job and not coordinator.history_job.done()),
                    detail_pending=bool(coordinator.detail_job and not coordinator.detail_job.done()),
                    daily_published=coordinator.daily_usage is not None)
                result['source'] = coordinator.selection.selected
        return result


def failure_metadata(error, phase):
    # Never emit arbitrary exception text (HTTP exceptions can embed private data).
    code = str(error) if type(error) is RuntimeError and str(error).startswith('probe_') else None
    return dict(phase=phase, type=type(error).__name__, code=code,
        category='http_timeout' if isinstance(error, TimeoutError) else
                 'source_unavailable' if code == 'probe_source_unavailable' else
                 'daily_pending' if code == 'probe_daily_timeout' else
                 'assertion' if isinstance(error, AssertionError) else 'probe_or_runtime_failure')


@contextmanager
def probe_lifecycle(host, streams, observations):
    primary = None
    try:
        yield
    except BaseException as error:
        primary = error
        print(json.dumps(dict(primary_failure=failure_metadata(error, observations.stage),
                              before_cleanup=observations.snapshot(host))), flush=True)
        raise
    finally:
        cleanup = []
        for action in [lambda: host.stop('menu'),
                       *(action for connection, response in streams
                         for action in (response.close, connection.close)), host.close]:
            try:
                action()
            except BaseException as error:
                cleanup.append(error)
        print(json.dumps(dict(phases=observations.snapshot(host), cleanup_failures=[
            failure_metadata(error, 'cleanup') for error in cleanup])), flush=True)
        if cleanup:
            raise BaseExceptionGroup('probe primary and cleanup failures' if primary else 'probe cleanup failures',
                                     ([primary] if primary else []) + cleanup) from None
