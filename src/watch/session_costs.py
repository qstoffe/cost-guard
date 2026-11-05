"""One bounded background lane for shared, persisted session CCost reconciliation."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import sqlite3

from src.analysis.session_cost import reconcile_session_cost, session_cost_source_key
from src.pricing.base import PricingUnavailableError
from src.sources.errors import SourceError


@dataclass(slots=True)
class SessionCostState:
    """Retain a scalar baseline across capture eviction, not unbounded history."""
    evidence: object = None
    source_key: object = None
    validated_key: object = None
    value: object = None
    failed: bool = False
    catalog_unavailable: bool = False
    valuation_revision: str | None = None
    turn: int = 0
    retry_at_ms: int = 0

    def observe(self, snapshot):
        if snapshot is None:
            return
        key = session_cost_source_key(snapshot)
        if key != self.source_key:
            self.retry_at_ms = 0
        self.evidence, self.source_key = snapshot, key

    @property
    def needs_work(self):
        return (self.value is None or self.failed or self.validated_key != self.source_key
            or self.value.valuation_revision != self.valuation_revision)

    @property
    def status(self):
        if self.failed or self.catalog_unavailable:
            return "unavailable"
        if self.value is None:
            return "loading"
        if not self.value.source_complete:
            return "partial"
        return "checking" if self.needs_work else "observed"


class SessionCosts:
    def __init__(self, factory, resources_factory=None):
        self.factory = factory
        self.resources_factory = resources_factory
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cost-guard-session-cost")
        self.job = None
        self.identity = None
        self.checked_at_ms = 0
        self.catalog_due_ms = 0
        self.catalog_signature = None
        self.catalog_unavailable = False
        self.turn = 0

    def submit(self, session_id, generation, snapshot, now_ms):
        if self.job is not None:
            return False
        self.identity = (session_id, generation)
        self.checked_at_ms = now_ms
        self.job = self.pool.submit(self._capture, snapshot, now_ms)
        return True

    def _capture(self, snapshot, now_ms):
        service = None
        try:
            if self.resources_factory is not None:
                repository, catalog = self.resources_factory()
                return catalog.analysis_signature if snapshot is None else reconcile_session_cost(repository, snapshot, catalog)
            service = self.factory(now_ms)
            catalog = service._load_comparison_catalog()
            return catalog.analysis_signature if snapshot is None else reconcile_session_cost(service.cache_repository, snapshot, catalog)
        except (SourceError, PricingUnavailableError, sqlite3.Error, OSError):
            return None
        finally:
            if service is not None:
                service.close_accounts()

    def drain(self):
        if self.job is None or not self.job.done():
            return None
        value = (*self.identity, self.job.result())
        self.job = self.identity = None
        return value

    def _accept(self, states, result, now_ms):
        key, source_key, value = result
        if key is None or value is not None:
            self.catalog_unavailable = value is None
            self.catalog_due_ms = self.checked_at_ms + (5000 if value is None else 60000)
            if value is not None:
                self.catalog_signature = value if key is None else value.valuation_revision
        state = states.get(key)
        # Generation clocks are not cost revisions. A completed older revision of
        # this same source is still a useful baseline while the latest catches up.
        if state is None or state.source_key is None or state.source_key[:4] != source_key[:4]:
            return
        if value is None:
            state.failed = True
            state.retry_at_ms = now_ms + 5000
        else:
            state.value, state.validated_key = value, source_key
            state.failed = False

    def tick(self, states, visible, now_ms):
        result = self.drain()
        if result is not None:
            self._accept(states, result, now_ms)
        for state in states.values():
            state.valuation_revision = self.catalog_signature
            state.catalog_unavailable = self.catalog_unavailable
        # One cheap shared identity check per existing Wake period. An unchanged
        # catalog submits no per-root snapshot/fingerprint/valuation/cache work.
        if self.catalog_signature is not None and now_ms >= self.catalog_due_ms:
            if self.submit(None, None, None, now_ms):
                return
        for key in sorted(visible, key=lambda key: (states[key].turn, key)):
            state = states[key]
            if state.evidence is None or not state.needs_work or now_ms < state.retry_at_ms:
                continue
            if self.submit(key, state.source_key, state.evidence, now_ms):
                self.turn += 1
                state.turn = self.turn
                break

    def close(self):
        self.pool.shutdown(wait=True, cancel_futures=True)
        if self.job is not None and not self.job.cancelled():
            self.job.result()
