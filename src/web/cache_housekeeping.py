"""Host-loop cache work: actual browser demand, then infrequent spare-capacity pruning."""
from collections import deque
from contextlib import contextmanager
from threading import Lock
import time

from src.cache.database import CacheDatabase
from src.cache.lifecycle import CacheLifecycle
from src.cache.session_scope import root_key

DEMAND_BATCHES = 128


class CacheHousekeeping:
    def __init__(self, root, *, clock=time.monotonic, lifecycle=None, defer_demand=False):
        self.clock = clock
        self.started = None
        self.due = 0
        self.touch_due = 0
        self.lifecycle = lifecycle or CacheLifecycle(CacheDatabase(root))
        self.demand = deque(maxlen=DEMAND_BATCHES) if defer_demand else None
        self.request_lock = Lock()
        self.requests = 0
        self.epoch = 0

    def start(self):
        self.started = self.clock()
        self.due = self.started + 3600

    @contextmanager
    def request(self, path):
        # Streams have their own lifetime and cannot make the host permanently busy.
        tracked = path != '/api/events'
        if tracked:
            with self.request_lock:
                self.requests += 1
                self.epoch += 1
        try:
            yield
        finally:
            if tracked:
                with self.request_lock:
                    self.requests -= 1

    def _request_activity(self):
        with self.request_lock:
            return self.requests, self.epoch

    def delivered(self, host, path, value):
        """Only the visible shipped UI marks this boundary; probes/API reads do not."""
        if not isinstance(value, dict) or not host.live:
            return
        if path == '/api/interest':
            return  # Interest is handled with its validated request by dispatch_http.
        result = value.get('result')
        if path.startswith('/api/jobs/') or path == '/api/data':
            if (isinstance(result, dict) and result.get('view') and not result.get('error')
                    and result.get('source', {}).get('identity') == host.dispatcher.identity):
                self.use_roots(host, (row['session_id'] for row in result.get('source', {}).get('revisions', ())))
        elif path == '/api/sessions':
            self.use_roots(host, (row['session_id'] for row in value.get('view', {}).get('session_usage', ())
                if row.get('has_summary')))
        elif path == '/api/detail' and isinstance(result, dict):
            self.use_roots(host, (row['session_id'] for row in result.get('view', {}).get('prompt_blocks', ())))

    def use_roots(self, host, ids):
        catalog = host.live.catalog
        if self.demand is not None:
            # Catalog observations replace the root map as a whole. Read its
            # published reference once and defer lifecycle locks/SQLite to the host.
            roots = catalog.roots
            keys = tuple(root_key(root.provenance, key) for key in ids
                         if (root := roots.get(key)) is not None)
            if keys:
                self.demand.append(keys)
            return
        with catalog.lock:
            roots = [root_key(catalog.roots[key].provenance, key) for key in ids if key in catalog.roots]
        self.lifecycle.note_use(roots)

    def collect_demand(self):
        if self.demand is None:
            return
        for _ in range(DEMAND_BATCHES):
            try:
                roots = self.demand.popleft()
            except IndexError:
                return
            self.lifecycle.note_use(roots)

    @staticmethod
    def _busy(host, coordinator):
        driver = host.live.driver
        if (host.stopping.is_set() or host.live.working.is_set() or not host.live.observed.is_set()
                or driver.error or driver.resync or driver.hints or driver.monotonic() + 0.1 >= driver.deadline
                or driver.frame is not None and driver.frame.active_count):
            return True
        if any(job['status'] in {'queued', 'running'} for job in host.jobs.updates()['jobs']):
            return True
        if (coordinator.card_workers.jobs or coordinator.session_costs.job is not None
                or any(getattr(coordinator, name) is not None for name in ('history_job', 'detail_job', 'catalog_job'))
                or coordinator.report_service.accounts_pending):
            return True
        with host.dispatcher.lock:
            if host.dispatcher.price_actions or any(tab['visible'] and (tab['request'] or tab['section'] in
                    {'sessions', 'session'}) for tab in host.dispatcher.tabs.values()):
                return True
        with host.live.details.lock:
            if any(host.live.details.clock() - lease['touched'] <= 300 for lease in host.live.details.leases.values()):
                return True
        with host.live.catalog.lock:
            if any(host.live.catalog._browsing(lease) for lease in host.live.catalog.leases.values()):
                return True
        return False

    def use_watch(self, host, *, history=False):
        driver = host.live.driver if host.live else None
        frame = driver.frame if driver else None
        if frame is not None:
            cards = (*frame.active_cards, *(frame.history_cards if history else ()))
            self.use_roots(host, (card.session_id for card in cards))

    def tick(self, host):
        self.collect_demand()
        now = self.clock()
        if now >= self.touch_due:
            self.lifecycle.flush()
            self.touch_due = now + 1
        if (self.started is None or now - self.started < 3600 or now < self.due or self._request_activity()[0]
                or not host.dispatcher
                or not host.live or host.live.driver is None):
            return
        coordinator = host.live.driver.coordinator
        if self._busy(host, coordinator):
            return
        catalog = host.live.catalog
        with catalog.lock:
            observation = catalog.last_observation
            if (catalog.state != 'observed' or catalog.observed is None
                    or not 0 <= catalog.clock() - catalog.observed <= 15 or observation is None):
                return
            protected = observation.active_candidates | observation.live_candidates
            frame = coordinator._last_projection
            if frame is not None:
                protected |= {card.session_id for card in (*frame.active_cards, *frame.history_cards)}
            revisions = {root_key(root.provenance, key): catalog.revisions[key]
                for key, root in catalog.roots.items() if key not in protected and key in catalog.revisions}
        requests, epoch = self._request_activity()
        if requests or self.demand:
            return

        def allowed():
            return (self._request_activity() == (0, epoch) and not self.demand and catalog.last_observation is observation
                and coordinator.catalog_observation is observation and not self._busy(host, coordinator))
        # One bounded attempt per day, including busy/cancel/error; no contention loop.
        self.due = now + 86400
        self.lifecycle.prune(revisions, allowed=allowed)
