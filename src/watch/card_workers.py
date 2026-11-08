"""Bounded isolated Web capture work, with immutable per-session publications."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from queue import SimpleQueue
from threading import Event
import time

from src.pricing.base import PricingUnavailableError
from src.reports.watch_capture import capture_rows
from src.sources.errors import SourceError
from .skill_registry import active_skill_origins
from .tools import observe_tools, RUNNING_VISIBLE_AFTER_MS
from .source_reads import SourceReads


@dataclass(frozen=True, slots=True)
class CardResult:
    session_id: str
    generation: int
    phase: str
    value: object = None
    captured_at_ms: int | None = None


@dataclass(frozen=True, slots=True)
class CardRequest:
    root: object
    generation: int
    previous: object = None
    focal_ids: tuple = ()
    historical: bool = False
    batchable: bool = True


class _BatchReplay(Exception):
    """Scheduling overrun, not evidence of a source outage."""


class CardWorkers:
    """No queued futures: admission is bounded, while logical cards are uncapped.

    The caller owns generations and scheduling. Every job creates fresh analysis,
    SQLite and pricing on its worker. The explicit Web V2 seam may exclusively
    retain that worker's source; other callers and guidance keep fresh sources.
    No worker borrows the coordinator's mutable ReportService.
    """
    def __init__(self, factory, workers=4, *, batch_size=1, batch_hydration_seconds=2.0, readers=None):
        if batch_size not in (1, 2, 3) or batch_hydration_seconds <= 0:
            raise ValueError('Card batches require size 1..3 and a positive hydration budget')
        self.factory = factory
        self.limit = workers
        self.batch_size = batch_size
        self.batch_hydration_seconds = batch_hydration_seconds
        self.history_limit = max(1, workers - 1)
        self.history_jobs = set()
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="cost-guard-cards")
        self.results = SimpleQueue()
        self.jobs = {}
        self.stopping = Event()
        self.completed = Event()
        self.reads = SourceReads()
        self.readers = readers
        self.defer_guidance = False

    @contextmanager
    def _service(self, now_ms):
        if self.readers is not None:
            with self.readers.borrow() as reader:
                service = self.factory(now_ms, reader=reader)
                try:
                    yield service
                finally:
                    service.close_accounts()
        else:
            service = self.factory(now_ms)
            try:
                with self.reads.using(service.source):
                    yield service
            finally:
                service.close_accounts()

    def submit_guidance(self, key, produce):
        if (self.stopping.is_set() or key in self.jobs or len(self.jobs) >= self.limit or
                len(self.history_jobs) >= self.history_limit):
            return None
        future = self.pool.submit(produce)
        self.jobs[key] = future
        self.history_jobs.add(key)
        future.add_done_callback(lambda _future: self.completed.set())
        return future

    def submit(self, root, generation, now_ms, previous=None, focal_ids=()):
        key = root.session_id
        if self.stopping.is_set() or key in self.jobs or len(self.jobs) >= self.limit:
            return False
        future = self.pool.submit(self._capture, root, generation, now_ms, previous, focal_ids)
        self.jobs[key] = future
        future.add_done_callback(lambda _future: self.completed.set())
        return True

    def submit_many(self, requests, now_ms):
        accepted, batch = [], []
        def flush():
            if not batch:
                return
            group = tuple(batch)
            future = self.pool.submit(self._capture_batch, group, now_ms)
            for request in group:
                key = request.root.session_id
                self.jobs[key] = future
                self.history_jobs.add(key)
                accepted.append(key)
            future.add_done_callback(lambda _future: self.completed.set())
            batch.clear()
        for request in requests:
            key = request.root.session_id
            if (self.stopping.is_set() or key in self.jobs or
                    len(self.jobs) + len(batch) >= self.limit):
                continue
            if request.historical and len(self.history_jobs) + len(batch) >= self.history_limit:
                continue
            if request.historical and request.batchable and self.batch_size > 1:
                batch.append(request)
                if len(batch) == self.batch_size:
                    flush()
            else:
                flush()
                if self.submit(request.root, request.generation, now_ms, request.previous, request.focal_ids):
                    accepted.append(key)
                    if request.historical:
                        self.history_jobs.add(key)
        flush()
        return tuple(accepted)

    def _publish(self, root, generation, phase, value=None, captured_at_ms=None):
        if not self.stopping.is_set():
            self.results.put(CardResult(root.session_id, generation, phase, value, captured_at_ms))

    def _capture(self, root, generation, now_ms, previous, focal_ids):
        started = time.monotonic()
        try:
            with self._service(now_ms) as service:
                options = {'defer_guidance': True} if self.defer_guidance else {}
                capture, item = capture_rows(service, root, previous, focal_ids, **options)
                snapshot = item.snapshot
                origins = active_skill_origins(service.source, snapshot, capture)
                tools = tuple((row.event_id, observe_tools(snapshot, row.event_id,
                    is_compaction=False, now_ms=now_ms + RUNNING_VISIBLE_AFTER_MS,
                    skill_origins_by_session=origins)) for row in capture.rows)
                self._publish(root, generation, "rows", (capture, tools, snapshot), now_ms)
        except (SourceError, PricingUnavailableError) as error:
            self._publish(root, generation, "unavailable", error, now_ms)
        finally:
            self._publish(root, generation, "timing", time.monotonic() - started)

    def _capture_batch(self, requests, now_ms):
        if len(requests) == 1:
            request = requests[0]
            self._capture(request.root, request.generation, now_ms, request.previous, request.focal_ids)
            return
        started, hydration_started = time.monotonic(), None
        service = None
        pending = {request.root.session_id for request in requests}
        def progress(stage, completed, total):
            nonlocal hydration_started
            if stage != 'messages':
                hydration_started = None
            elif hydration_started is None:
                hydration_started = time.monotonic()
                pending.update(request.root.session_id for request in requests)
            elif pending and completed < total and time.monotonic() - hydration_started >= self.batch_hydration_seconds:
                # Cancel the owned transport before the source joins its readers.
                # Slots remain occupied until the group future actually finishes.
                from .source_reads import cancel_source
                cancel_source(service.source)
                raise _BatchReplay()
        try:
            with self._service(now_ms) as service:
                loader = getattr(service.source, 'load_card_snapshots', None)
                snapshots, failures = (loader(tuple(request.root.session_id for request in requests),
                    progress=progress, on_root=pending.discard)
                    if callable(loader) else ({}, {}))
                if failures and self.readers is not None:
                    self.readers.discard(service.source)
                for request in requests:
                    root, generation = request.root, request.generation
                    try:
                        if root.session_id in failures:
                            raise failures[root.session_id]
                        options = {'fresh': snapshots[root.session_id]} if callable(loader) else {}
                        if self.defer_guidance:
                            options['defer_guidance'] = True
                        capture, item = capture_rows(service, root, request.previous, request.focal_ids,
                            **options)
                        snapshot = item.snapshot
                        origins = active_skill_origins(service.source, snapshot, capture)
                        tools = tuple((row.event_id, observe_tools(snapshot, row.event_id,
                            is_compaction=False, now_ms=now_ms + RUNNING_VISIBLE_AFTER_MS,
                            skill_origins_by_session=origins)) for row in capture.rows)
                        self._publish(root, generation, 'rows', (capture, tools, snapshot), now_ms)
                    except (SourceError, PricingUnavailableError) as error:
                        if self.readers is not None:
                            self.readers.discard(service.source)
                        self._publish(root, generation, 'unavailable', error, now_ms)
        except _BatchReplay:
            for request in requests:
                self._publish(request.root, request.generation, 'replay',
                    request.root.session_id in pending, now_ms)
        except (SourceError, PricingUnavailableError) as error:
            for request in requests:
                self._publish(request.root, request.generation, 'unavailable', error, now_ms)
        finally:
            for request in requests:
                self._publish(request.root, request.generation, 'timing', time.monotonic() - started)

    def drain(self):
        # Snapshot completion before draining results. Every reclaimed future has
        # already queued all results and completed cleanup; a racing completion
        # keeps its permits until the next owner turn, even if rows arrive now.
        completed = {future for future in self.jobs.values() if future.done()}
        for future in completed:
            future.result()  # Unexpected software faults retain the host's fatal boundary.
        for key, future in tuple(self.jobs.items()):
            if future in completed:
                del self.jobs[key]
                self.history_jobs.discard(key)
        values = []
        while not self.results.empty():
            values.append(self.results.get())
        return values

    def cancel(self):
        self.stopping.set()
        self.completed.set()
        self.reads.cancel()
        if self.readers is not None:
            self.readers.cancel()

    def close(self):
        self.cancel()
        try:
            self.pool.shutdown(wait=True, cancel_futures=True)
            for future in set(self.jobs.values()):
                if not future.cancelled():
                    future.result()
        finally:
            if self.readers is not None:
                self.readers.close()
