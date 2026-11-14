"""Bounded finite work, with a killable one-shot service ownership boundary."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, replace
import json
import multiprocessing
from multiprocessing.connection import wait
import os
import re
from threading import Event, RLock, Thread
import time
from uuid import uuid4

from src.reports import ReportKind, ReportRequest
from . import stats_jobs
from . import history_jobs
from .report_control import ManagedReport, Quantum

MAX_RESULT_BYTES = 8 * 1024 * 1024
MAX_JOBS = 16
MAX_PENDING = 4


class ReportWorkerStopError(RuntimeError):
    """Owned child exit is unconfirmed; keep its handles and stop the host."""


@dataclass(frozen=True, slots=True)
class ModelsPriceRefresh(ReportRequest):
    """Web-only explicit pricing action, distinct from a cached Normal capture."""


def parse_report(value):
    page_fields = {"session_page_size", "session_offset", "session_catalog_revision"}
    comparison_fields = {'comparison_offset', 'comparison_revision'}
    if not isinstance(value, dict) or set(value) - ({"kind", "session_id", "date_text", "session_limit", "stats_scope", "token_mix_scope"} | page_fields | comparison_fields):
        raise ValueError("invalid_request")
    kind = ReportKind(value.get("kind"))
    comparison_offset = value.get('comparison_offset', 0)
    comparison_revision = value.get('comparison_revision')
    if (comparison_fields & set(value) and kind is not ReportKind.COMPARISONS
            or type(comparison_offset) is not int or not 0 <= comparison_offset <= 1_000_000 or comparison_offset % 10
            or comparison_revision is not None and (not isinstance(comparison_revision, str)
                or not re.fullmatch(r'[0-9a-f]{64}', comparison_revision))
            or comparison_offset and comparison_revision is None):
        raise ValueError('invalid_request')
    stats_scope = value.get('stats_scope', '30-days')
    token_mix_scope = value.get('token_mix_scope', 'all')
    if ('token_mix_scope' in value and kind is not ReportKind.TOKEN_MIX
            or token_mix_scope not in ('today', '7-days', '30-days', 'month', 'all')):
        raise ValueError('invalid_request')
    if ('stats_scope' in value and kind is not ReportKind.AI_STATS
            or stats_scope not in ('today', '7-days', '30-days', 'month', 'all')):
        raise ValueError('invalid_request')
    session = value.get("session_id", "")
    date = value.get("date_text", "")
    limit = value.get("session_limit", 20 if kind is ReportKind.SESSIONS else None)
    size = value.get("session_page_size")
    offset = value.get("session_offset", 0)
    revision = value.get("session_catalog_revision")
    if (page_fields & set(value) and kind is not ReportKind.SESSIONS
            or size is not None and (type(size) is not int or not 1 <= size <= 100)
            or type(offset) is not int or not 0 <= offset <= 1_000_000
            or revision is not None and (not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{64}", revision))
            or offset and (size is None or revision is None)):
        raise ValueError("invalid_request")
    if size is not None and "session_limit" not in value:
        limit = None
    if (not isinstance(session, str) or not isinstance(date, str) or len(date) > 32
            or len(session) > 200 or any(ord(c) < 32 for c in session + date)
            or (limit is not None and (type(limit) is not int or not 1 <= limit <= 10000))):
        raise ValueError("invalid_request")
    if (kind is ReportKind.SESSION) != bool(session) or (kind is ReportKind.DATE) != bool(date):
        raise ValueError("invalid_request")
    if (session and not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", session)
            or "session_limit" in value and kind is not ReportKind.SESSIONS):
        raise ValueError("invalid_request")
    if date:
        from src.analysis import local_report_range
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?::\d{4}-\d{2}-\d{2})?", date):
            raise ValueError("invalid_request")
        try:
            local_report_range(date, "UTC")
        except (ValueError, OverflowError) as exc:
            raise ValueError("invalid_request") from exc
    return ReportRequest(kind, session_id=session or None, date_text=date or None, session_limit=limit,
                         session_page_size=size, session_offset=offset, session_catalog_revision=revision, stats_scope=stats_scope,
                          comparison_offset=comparison_offset, comparison_revision=comparison_revision,
                          token_mix_scope=token_mix_scope)


class ProgressRelay:
    """Keep only the latest callback between bounded IPC publications; no timer/queue."""

    def __init__(self, sender, *, clock=time.monotonic, quantum=None):
        self.sender = sender
        self.clock = clock
        self.last_sent = float("-inf")
        self.pending = None
        self.quantum = quantum

    def observe(self, event):
        if self.quantum:
            self.quantum.checkpoint()
        self.pending = event.to_json()
        if self.clock() - self.last_sent >= 0.1:
            self.flush()

    def flush(self):
        if self.pending is not None:
            self.sender.send(("progress", self.pending))
            self.pending = None
            self.last_sent = self.clock()


def run_report(sender, request):
    """Spawn entry: own all mutable service/account/source state; no inherited hooks."""
    try:
        from .composition import application
        quantum = Quantum(sender, request.quantum_seconds) if isinstance(request, ManagedReport) else None
        relay = ProgressRelay(sender, quantum=quantum)
        app = application(request, read_admission=quantum.admit_read,
            history_checkpoint=lambda value: sender.send(('checkpoint', value))) if quantum else application(request)
        if quantum:
            quantum.admit()
        result = app.execute(request, progress=relay.observe).to_json()
        relay.flush()
        started = time.perf_counter()
        payload = json.dumps(result, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii")
        if len(payload) > MAX_RESULT_BYTES:
            sender.send(("error", "result_too_large"))
        else:
            if request.kind is ReportKind.AI_STATS:
                sender.send(('metrics', dict(serialization_ms=(time.perf_counter() - started) * 1000,
                                             result_bytes=len(payload))))
            sender.send(("result", payload))
    except Exception:
        # No exception text, paths, private source fields or credentials on IPC.
        sender.send(("error", "report_unavailable"))
    finally:
        sender.close()


def run_owned_report(target, sender, request):
    """Even a crashed/force-stopped Web parent must not orphan a blocked report.

    multiprocessing's exact parent sentinel is a kernel handle/pipe, not a PID
    lookup. This safety thread owns no analysis and exits this child only.
    """
    parent = multiprocessing.parent_process()
    if parent is None:
        raise RuntimeError("report_parent_unavailable")
    finished = Event()

    def watch_parent():
        try:
            while not finished.is_set():
                if wait([parent.sentinel], timeout=0.25):
                    os._exit(1)  # Parent is gone: never continue orphaned acquisition.
        except BaseException:
            os._exit(1)  # Lost ownership proof cannot mean keep running.

    monitor = Thread(target=watch_parent, name="cost-guard-report-parent", daemon=True)
    monitor.start()
    try:
        target(sender, request)
    finally:
        finished.set()
        monitor.join(timeout=1)


class ReportJobs:
    """HTTP callers serialize bookkeeping only, never analysis. Poll from host loop.

    Cancellation terminates only this owner's process (including a blocked scan).
    Each process owns one fresh ReportApplication; never share live account work.
    Elapsed analysis time is not a source failure. Individual integrations own
    I/O timeouts; cooperative quanta and explicit cancellation own scheduling.
    """

    def __init__(self, *, target=run_report, context=None):
        self._context = context or multiprocessing.get_context("spawn")
        self._target = target
        self._lock = RLock()
        self._jobs = OrderedDict()
        self._active = None
        self._parked = {}
        # Children that already delivered valid terminal IPC; reaped without
        # delaying publication. Exact owners stay here until exit is confirmed.
        self._retiring = []
        self._closed = False
        self._failure = None
        self.analysis = "not_requested"
        self.source = "not_acquired"
        self.accounts = "not_acquired"

    def submit(self, request):
        with self._lock:
            self._check_failure()
            if self._closed:
                raise RuntimeError("stopping")
            for key, job in self._jobs.items():
                if (isinstance(job['request'], ManagedReport) != isinstance(request, ManagedReport)
                        or getattr(job['request'], 'source_identity', '') != getattr(request, 'source_identity', '')):
                    continue
                if stats_jobs.is_stats(job) and request.kind is ReportKind.AI_STATS:
                    if job['status'] in {'queued', 'running'}:
                        # At most the five validated scopes; priority never erases
                        # an earlier logical goal or creates another job/worker.
                        job['goals'] = tuple(dict.fromkeys((*job['goals'], request.stats_scope)))
                        job['request'] = request
                        return key
                    if (not isinstance(request, ManagedReport) and job['status'] == 'complete' and stats_jobs.ready(job, request.stats_scope)
                            and time.monotonic() - job.get('finished_at', 0) < 60):
                        return key
                if job["request"] == request and job["status"] in {"queued", "running"}:
                    return key
                if (not isinstance(request, ManagedReport) and request.kind in {ReportKind.TOKEN_MIX, ReportKind.COMPARISONS} and job["request"] == request
                        and job["status"] == "complete" and time.monotonic() - job.get("finished_at", 0) < 60):
                    # Coalesce staggered tab freshness checks as well as in-flight work.
                    # Retain the actual observation timestamp; reuse is not new acquisition.
                    return key
            if sum(j["status"] in {"queued", "running"} for j in self._jobs.values()) >= MAX_PENDING:
                raise RuntimeError("busy")
            while len(self._jobs) >= MAX_JOBS:
                victim = next(k for k, j in self._jobs.items() if j["status"] not in {"queued", "running"})
                del self._jobs[victim]
            key = uuid4().hex
            self._jobs[key] = dict(request=request, status="queued", result=None, error=None, progress=None,
                                   queued_at=time.monotonic(), priority=1, served_at=0)
            if request.kind is ReportKind.AI_STATS:
                self._jobs[key]['goals'] = (request.stats_scope,)
            return key

    def snapshot(self, key):
        with self._lock:
            self._check_failure()
            job = self._jobs.get(key)
            if job is None:
                return None
            return dict(id=key, status=job["status"], progress=job["progress"] or {
                        "phase": job["status"], "completed": 0, "total": None},
                        result=job["result"], error=job["error"],
                        work={name: job.get(name, 0) for name in
                              ('slices', 'queue_ms', 'worker_ms', 'serialization_ms', 'result_bytes')})

    def readiness(self):
        with self._lock:
            self._check_failure()
            return dict(http="ready", analysis=self.analysis, source=self.source, accounts=self.accounts)

    def updates(self):
        with self._lock:
            return {"readiness": self.readiness(), "jobs": [
                dict(id=key, status=job["status"], progress=job["progress"])
                for key, job in self._jobs.items()]}

    def _check_failure(self):
        if self._failure is not None:
            raise self._failure

    def prioritize(self, priorities):
        """Host policy only. Browsers cannot set worker counts or raw priorities."""
        with self._lock:
            for key, job in self._jobs.items():
                job['priority'] = priorities.get(key, 1)

    def select_scope(self, key, scope):
        """Foreground intent changes the next Stats slice, not its saved goals."""
        if scope not in ('today', '7-days', '30-days', 'month', 'all'):
            raise ValueError('invalid_request')
        with self._lock:
            job = self._jobs.get(key)
            if job and stats_jobs.is_stats(job) and job['status'] in {'queued', 'running'}:
                job['goals'] = tuple(dict.fromkeys((*job['goals'], scope)))
                job['request'] = replace(job['request'], stats_scope=scope)

    def _park(self):
        key, process, receiver, started = self._active
        job = self._jobs[key]
        elapsed = max(0, time.monotonic() - started)
        job['worker_ms'] = job.get('worker_ms', 0) + elapsed * 1000
        job['served_at'] = time.monotonic()
        job['not_before'] = time.monotonic() + (min(1, elapsed * 4) if job['priority'] >= 2 else 0)
        job['status'] = 'queued'
        job['admitted'] = True  # Parked work is never a startup interruption candidate.
        self._parked[key] = process, receiver
        self._active = None

    def _confirm_exit(self, process, *, grace):
        """Bounded natural/terminate/kill escalation; True only after confirmed exit."""
        if grace:
            process.join(timeout=1)
        if process.is_alive():
            process.terminate()
            process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join(timeout=1)
        return not process.is_alive()

    def _stop(self, *, owner=None):
        owner = owner or self._active
        if owner is None:
            return
        key, process, receiver, started = owner
        job = self._jobs[key]
        # Cancel/shutdown/invalid IPC never take the natural-exit grace.
        if not self._confirm_exit(process, grace=False):
            self._failure = self._failure or ReportWorkerStopError('report_worker_stop_timeout')
            job.update(status='failed', error='report_worker_stop_timeout')
            self.analysis = 'failed'
            raise self._failure  # Retain receiver, process and _active ownership.
        receiver.close()
        process.close()
        job['worker_ms'] = job.get('worker_ms', 0) + max(0, time.monotonic() - started) * 1000
        if self._active is owner:
            self._active = None

    def _retire(self):
        """Publish before teardown; the exact finished owner keeps bounded exit escalation."""
        key, process, receiver, started = self._active
        now = time.monotonic()
        job = self._jobs[key]
        job['worker_ms'] = job.get('worker_ms', 0) + max(0, now - started) * 1000
        self._retiring.append(dict(process=process, receiver=receiver, stage=0, deadline=now + 1))
        self._active = None

    def _reap(self):
        """Nonblocking: 1s natural grace, then terminate, kill and a latched failure."""
        now = time.monotonic()
        for owner in tuple(self._retiring):
            process = owner['process']
            if not process.is_alive():
                owner['receiver'].close()
                process.close()
                self._retiring.remove(owner)
            elif now >= owner['deadline']:
                if owner['stage'] == 2:
                    self._failure = self._failure or ReportWorkerStopError('report_worker_stop_timeout')
                    self.analysis = 'failed'
                    raise self._failure  # Owner remains retained for close().
                (process.terminate if owner['stage'] == 0 else process.kill)()
                owner.update(stage=owner['stage'] + 1, deadline=now + 1)

    def _close_retiree(self, owner):
        process = owner['process']
        if not self._confirm_exit(process, grace=owner['stage'] == 0):
            self._failure = self._failure or ReportWorkerStopError('report_worker_stop_timeout')
            self.analysis = 'failed'
            raise self._failure
        owner['receiver'].close()
        process.close()
        self._retiring.remove(owner)

    def cancel(self, key):
        with self._lock:
            self._check_failure()
            job = self._jobs.get(key)
            if job is None:
                return False
            if job["status"] in {"queued", "running"}:
                if key in self._parked:
                    process, receiver = self._parked[key]
                    self._stop(owner=(key, process, receiver, time.monotonic()))
                    del self._parked[key]
                if self._active and self._active[0] == key:
                    self._stop()
                job["status"] = "cancelled"
                self.analysis = "cancelled"
            return True

    def tick(self):
        with self._lock:
            self._check_failure()
            if self._closed:
                return
            if self._active:
                self._tick_active()
            self._reap()
            if self._active is None:
                self._start_next()

    def _can_spawn(self):
        # Retirees stay resident: beyond one retiring child only parked work may resume.
        return len(self._retiring) <= 1 and len(self._parked) + len(self._retiring) < MAX_PENDING

    def _interrupt_startup(self):
        """A never-admitted background startup yields once to runnable foreground work.

        Admitted, parked, requested or promoted work is never interrupted. The
        logical job keeps its identity, observation time, goals and durable
        progress; another interruption needs subsequent durable progress.
        """
        key, process, receiver, started = self._active
        job = self._jobs[key]
        if job.get('admitted', True) or job.get('priority', 1) < 2 or job.get('startup_interrupted'):
            return False
        if not self._runnable_waiting(key, 0):
            return False
        self._stop()  # Confirmed exit before replacement; no natural grace.
        job.update(status='queued', queued_at=time.monotonic(), startup_interrupted=True,
                   startup_interruptions=job.get('startup_interruptions', 0) + 1)
        return True

    def _runnable_waiting(self, active, priority):
        now = time.monotonic()
        return any(key != active and job['status'] == 'queued' and job.get('priority', 1) <= priority
                   and now >= job.get('not_before', 0) and (key in self._parked or self._can_spawn())
                   for key, job in self._jobs.items())

    def _grant(self, job, receiver):
        """Requested work runs unparked until contention; background stays paced every quantum."""
        free = job.get('priority', 1) < 2
        receiver.send('free' if free else 'run')
        job.update(admitted=True, free=free, yield_requested=False)

    def _tick_active(self):
        if self._interrupt_startup():
            return
        key, process, receiver, started = self._active
        job = self._jobs[key]
        finished = False
        try:
            if job.get('free') and not job.get('yield_requested') and (
                    job.get('priority', 1) >= 2 or self._runnable_waiting(key, job.get('priority', 1))):
                receiver.send('yield')  # At most one outstanding request; honored at the next quantum.
                job['yield_requested'] = True
            if receiver.poll():
                if not self._receive(job, receiver):
                    return
                if self._active is None:
                    return
                finished = True
            elif process.is_alive():
                return
            else:
                job.update(status='failed', error='report_unavailable')
        except (EOFError, OSError, ValueError, KeyError, TypeError):
            job.update(status='failed', error='report_unavailable')
        self.analysis = job['status']
        if finished:
            self._retire()
        else:
            self._stop()

    def _receive(self, job, receiver):
        # Bounded bursts preserve host/control turns and avoid IPC backpressure.
        for _ in range(64):
            kind, payload = receiver.recv()
            if kind == 'progress':
                sequence = (job['progress'] or {}).get('sequence', 0) + 1
                job['progress'] = dict(payload, sequence=sequence)
            elif kind == 'yield' and payload is None and isinstance(job['request'], ManagedReport):
                self._park()
                return True
            elif kind == 'admit' and payload is None and isinstance(job['request'], ManagedReport):
                if not job.get('admitted', True):
                    self._grant(job, receiver)
            elif kind == 'metrics':
                for name in ('serialization_ms', 'result_bytes'):
                    job[name] = job.get(name, 0) + payload[name]
            elif kind == 'checkpoint':
                history_jobs.checkpoint(job, payload)
                job.pop('startup_interrupted', None)
            elif kind == 'result':
                result = json.loads(payload)
                if history_jobs.managed(job) and (result.get('error') or {}).get('code') == 'history_continue':
                    history_jobs.resume(job)
                    return True
                expected = getattr(job['request'], 'source_identity', '')
                if expected and result.get('source', {}).get('identity') != expected and not result.get('error'):
                    job.update(status='failed', error='source_identity_changed', result=None)
                    return True
                stats_jobs.accept(job, result)
                if not job.get('stalls'):
                    job.pop('startup_interrupted', None)  # An advancing slice is durable progress.
                if job['status'] in {'failed', 'complete'}:
                    job['finished_at'] = time.monotonic()
                self.source = result['source']['status']
                self.accounts = ('not_requested' if job['request'].kind is not ReportKind.NORMAL
                                 or isinstance(job['request'], ModelsPriceRefresh)
                                 else 'reported' if not result['error'] else 'unavailable')
                return True
            elif kind == 'error' and isinstance(payload, str):
                job.update(status='failed', error=payload)
                return True
            else:
                raise ValueError('invalid_report_message')
            if not receiver.poll():
                return False
        return False

    def _start_next(self):
        for key, job in sorted(self._jobs.items(), key=lambda item: (
                item[1].get('priority', 1), item[1].get('served_at', 0),
                item[1]['request'].kind in {ReportKind.TOKEN_MIX, ReportKind.AI_STATS, ReportKind.COMPARISONS},
                item[1]['queued_at'])):
            if (job['status'] != 'queued' or job.get('priority', 1) >= 3
                    or 'not_before' in job and time.monotonic() < job['not_before']):
                continue
            if key in self._parked:
                process, receiver = self._parked[key]
                # Transfer ownership before the uncertain write. A broken pipe
                # must not lose the only handles to a still-running child.
                self._active = key, process, receiver, time.monotonic()
                del self._parked[key]
                try:
                    self._grant(job, receiver)
                except (EOFError, OSError, ValueError):
                    job.update(status='failed', error='report_unavailable')
                    self._stop()
                    return
                job['status'] = 'running'
                break
            if not self._can_spawn():
                continue
            receiver, sender = self._context.Pipe(duplex=isinstance(job['request'], ManagedReport))
            request = stats_jobs.request(job, key)
            if isinstance(request, ManagedReport) and request.kind is not ReportKind.AI_STATS:
                job.setdefault('observation_ms', int(time.time() * 1000))
                request = replace(request, observation_ms=job['observation_ms'],
                                  history_batch_size=job.get('history_batch_size', 64))
            process = self._context.Process(target=run_owned_report,
                args=(self._target, sender, request), name='cost-guard-report', daemon=True)
            try:
                process.start()
            except Exception:
                receiver.close()
                sender.close()
                process.close()
                job.update(status='failed', error='worker_unavailable')
                self.analysis = 'failed'
                return
            sender.close()
            now = time.monotonic()
            job['queue_ms'] = job.get('queue_ms', 0) + max(0, now - job['queued_at']) * 1000
            job['slices'] = job.get('slices', 0) + 1
            self._active = key, process, receiver, now
            job['status'] = 'running'
            self.analysis = 'loading'
            # Requested work is admitted up front; only background startup awaits its grant.
            job.update(admitted=not isinstance(request, ManagedReport), free=False, yield_requested=False)
            if isinstance(request, ManagedReport) and job.get('priority', 1) < 2:
                try:
                    self._grant(job, receiver)
                except (EOFError, OSError, ValueError):
                    job.update(status='failed', error='report_unavailable')
                    self._stop()
            break

    def close(self):
        with self._lock:
            self._closed = True
            failures = []

            def attempt(stop):
                try:
                    stop()
                except ReportWorkerStopError as exc:
                    failures.append(exc)  # Retain that owner; still try every other one.

            def parked(key):
                process, receiver = self._parked[key]
                self._stop(owner=(key, process, receiver, time.monotonic()))
                del self._parked[key]
            try:
                attempt(self._stop)
                for key in tuple(self._parked):
                    attempt(lambda key=key: parked(key))
                for owner in tuple(self._retiring):
                    attempt(lambda owner=owner: self._close_retiree(owner))
                if failures:
                    raise failures[0]
            finally:
                for job in self._jobs.values():
                    if job["status"] in {"queued", "running"}:
                        job["status"] = "cancelled"
