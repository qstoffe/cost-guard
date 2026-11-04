"""One bounded background lane for shared, persisted session CCost reconciliation."""
from concurrent.futures import ThreadPoolExecutor
import sqlite3

from src.analysis.session_cost import reconcile_session_cost
from src.pricing.base import PricingUnavailableError
from src.sources.errors import SourceError


class SessionCosts:
    def __init__(self, factory):
        self.factory = factory
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cost-guard-session-cost")
        self.job = None
        self.identity = None

    def submit(self, session_id, generation, snapshot, now_ms):
        if self.job is not None:
            return False
        self.identity = (session_id, generation)
        self.job = self.pool.submit(self._capture, snapshot, now_ms)
        return True

    def _capture(self, snapshot, now_ms):
        service = None
        try:
            service = self.factory(now_ms)
            return reconcile_session_cost(service.cache_repository, snapshot, service._load_comparison_catalog())
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

    def close(self):
        self.pool.shutdown(wait=True, cancel_futures=True)
        if self.job is not None and not self.job.cancelled():
            self.job.result()
