"""Bounded finite work, with a killable one-shot service ownership boundary."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import json
import multiprocessing
from multiprocessing.connection import wait
import os
import re
from threading import Event, RLock, Thread
import time
from uuid import uuid4

from src.reports import ReportKind, ReportRequest

MAX_RESULT_BYTES = 8 * 1024 * 1024
MAX_JOBS = 16
MAX_PENDING = 4


@dataclass(frozen=True, slots=True)
class ModelsPriceRefresh(ReportRequest):
    """Web-only explicit pricing action, distinct from a cached Normal capture."""


def parse_report(value):
    page_fields = {"session_page_size", "session_offset", "session_catalog_revision"}
    comparison_fields = {'comparison_offset', 'comparison_revision'}
    if not isinstance(value, dict) or set(value) - ({"kind", "session_id", "date_text", "session_limit", "stats_scope"} | page_fields | comparison_fields):
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
    if ('stats_scope' in value and kind is not ReportKind.AI_STATS
            or stats_scope not in ('30-days', 'month', 'all')):
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
                         comparison_offset=comparison_offset, comparison_revision=comparison_revision)


class ProgressRelay:
    """Keep only the latest callback between bounded IPC publications; no timer/queue."""

    def __init__(self, sender, *, clock=time.monotonic):
        self.sender = sender
        self.clock = clock
        self.last_sent = float("-inf")
        self.pending = None

    def observe(self, event):
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
        relay = ProgressRelay(sender)
        result = application(request).execute(request, progress=relay.observe).to_json()
        relay.flush()
        payload = json.dumps(result, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii")
        if len(payload) > MAX_RESULT_BYTES:
            sender.send(("error", "result_too_large"))
        else:
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
    The hard deadline also bounds providers whose normal request timeout fails.
    """

    def __init__(self, *, target=run_report, deadline=120, context=None):
        self._context = context or multiprocessing.get_context("spawn")
        self._target = target
        self._deadline = deadline
        self._lock = RLock()
        self._jobs = OrderedDict()
        self._active = None
        self._closed = False
        self.analysis = "not_requested"
        self.source = "not_acquired"
        self.accounts = "not_acquired"

    def submit(self, request):
        with self._lock:
            if self._closed:
                raise RuntimeError("stopping")
            for key, job in self._jobs.items():
                if job["request"] == request and job["status"] in {"queued", "running"}:
                    return key
                if (request.kind in {ReportKind.TOKEN_MIX, ReportKind.AI_STATS, ReportKind.COMPARISONS} and job["request"] == request
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
            self._jobs[key] = dict(request=request, status="queued", result=None, error=None, progress=None)
            return key

    def snapshot(self, key):
        with self._lock:
            job = self._jobs.get(key)
            if job is None:
                return None
            return dict(id=key, status=job["status"], progress=job["progress"] or {
                        "phase": job["status"], "completed": 0, "total": None},
                        result=job["result"], error=job["error"])

    def readiness(self):
        with self._lock:
            return dict(http="ready", analysis=self.analysis, source=self.source, accounts=self.accounts)

    def updates(self):
        with self._lock:
            return {"readiness": self.readiness(), "jobs": [
                dict(id=key, status=job["status"], progress=job["progress"])
                for key, job in self._jobs.items()]}

    def _stop(self):
        if self._active is None:
            return
        _, process, receiver, _ = self._active
        if process.is_alive():
            process.terminate()
        process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join(timeout=1)
        receiver.close()
        process.close()
        self._active = None

    def cancel(self, key):
        with self._lock:
            job = self._jobs.get(key)
            if job is None:
                return False
            if job["status"] in {"queued", "running"}:
                if self._active and self._active[0] == key:
                    self._stop()
                job["status"] = "cancelled"
                self.analysis = "cancelled"
            return True

    def tick(self):
        with self._lock:
            if self._closed:
                return
            if self._active:
                key, process, receiver, started = self._active
                job = self._jobs[key]
                if time.monotonic() - started > self._deadline:
                    job.update(status="failed", error="report_timeout")
                    self.analysis = "failed"
                    self._stop()
                elif receiver.poll():
                    try:
                        # Coalesce bounded bursts. One message per host turn can
                        # backpressure a deep scan until its hard deadline even
                        # when analysis itself is fast. Never unbound this drain:
                        # HTTP/control/cancellation must retain scheduling turns.
                        for _ in range(64):
                            kind, payload = receiver.recv()
                            if kind != "progress":
                                break
                            sequence = (job["progress"] or {}).get("sequence", 0) + 1
                            job["progress"] = dict(payload, sequence=sequence)
                            if not receiver.poll():
                                return
                        else:
                            return
                        if kind == "result":
                            job["result"] = json.loads(payload)
                            result = job["result"]
                            job["status"] = "failed" if result["error"] else "complete"
                            job["finished_at"] = time.monotonic()
                            self.source = result["source"]["status"]
                            self.accounts = ("not_requested" if job["request"].kind is not ReportKind.NORMAL
                                             or isinstance(job["request"], ModelsPriceRefresh)
                                             else "reported" if not result["error"] else "unavailable")
                        else:
                            job.update(status="failed", error=payload)
                    except (EOFError, OSError, ValueError, KeyError):
                        job.update(status="failed", error="report_unavailable")
                    self.analysis = job["status"]
                    self._stop()
                elif not process.is_alive():
                    job.update(status="failed", error="report_unavailable")
                    self.analysis = "failed"
                    self._stop()
            if self._active is None:
                for key, job in sorted(self._jobs.items(), key=lambda item: item[1]["request"].kind in {ReportKind.TOKEN_MIX, ReportKind.AI_STATS, ReportKind.COMPARISONS}):
                    if job["status"] != "queued":
                        continue
                    receiver, sender = self._context.Pipe(duplex=False)
                    process = self._context.Process(target=run_owned_report,
                                                    args=(self._target, sender, job["request"]),
                                                    name="cost-guard-report", daemon=True)
                    try:
                        process.start()
                    except Exception:
                        receiver.close()
                        sender.close()
                        process.close()
                        job.update(status="failed", error="worker_unavailable")
                        self.analysis = "failed"
                        return
                    sender.close()
                    self._active = key, process, receiver, time.monotonic()
                    job["status"] = "running"
                    self.analysis = "loading"
                    break

    def close(self):
        with self._lock:
            self._closed = True
            self._stop()
            for job in self._jobs.values():
                if job["status"] in {"queued", "running"}:
                    job["status"] = "cancelled"
