"""Bounded isolated Web capture work, with immutable per-session publications."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from queue import SimpleQueue
from threading import Event
import time

from src.pricing.base import PricingUnavailableError
from src.reports.watch_capture import capture_rows, capture_totals
from src.sources.errors import SourceError
from .skill_registry import active_skill_origins
from .tools import observe_tools, RUNNING_VISIBLE_AFTER_MS


@dataclass(frozen=True, slots=True)
class CardResult:
    session_id: str
    generation: int
    phase: str
    value: object = None
    captured_at_ms: int | None = None


class CardWorkers:
    """No queued futures: admission is bounded, while logical cards are uncapped.

    The caller owns generations and scheduling. Every job creates its service,
    source, SQLite connections and pricing integration on its own worker thread.
    No worker borrows the coordinator's mutable ReportService.
    """
    def __init__(self, factory, workers=4):
        self.factory = factory
        self.limit = workers
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="cost-guard-cards")
        self.results = SimpleQueue()
        self.jobs = {}
        self.stopping = Event()

    def submit(self, root, generation, now_ms, previous=None, focal_ids=()):
        key = root.session_id
        if key in self.jobs or len(self.jobs) >= self.limit:
            return False
        self.jobs[key] = self.pool.submit(self._capture, root, generation, now_ms, previous, focal_ids)
        return True

    def _publish(self, root, generation, phase, value=None, captured_at_ms=None):
        if not self.stopping.is_set():
            self.results.put(CardResult(root.session_id, generation, phase, value, captured_at_ms))

    def _capture(self, root, generation, now_ms, previous, focal_ids):
        started = time.monotonic()
        service = None
        try:
            service = self.factory(now_ms)
            capture, item = capture_rows(service, root, previous, focal_ids)
            snapshot = item.snapshot
            origins = active_skill_origins(service.source, snapshot, capture)
            tools = tuple((row.event_id, observe_tools(snapshot, row.event_id,
                is_compaction=False, now_ms=now_ms + RUNNING_VISIBLE_AFTER_MS,
                skill_origins_by_session=origins)) for row in capture.rows)
            self._publish(root, generation, "rows", (capture, tools, snapshot), now_ms)
            if not self.stopping.is_set():
                self._publish(root, generation, "totals", capture_totals(service, item), now_ms)
        except (SourceError, PricingUnavailableError):
            self._publish(root, generation, "unavailable", captured_at_ms=now_ms)
        finally:
            if service is not None:
                service.close_accounts()
            self._publish(root, generation, "timing", time.monotonic() - started)

    def drain(self):
        values = []
        while not self.results.empty():
            values.append(self.results.get())
        for key, future in tuple(self.jobs.items()):
            if future.done():
                future.result()  # Unexpected software faults retain the host's fatal boundary.
                del self.jobs[key]
        return values

    def close(self):
        self.stopping.set()
        self.pool.shutdown(wait=True, cancel_futures=True)
        for future in self.jobs.values():
            if not future.cancelled():
                future.result()
