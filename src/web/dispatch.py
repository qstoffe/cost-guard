"""One host-owned demand registry, bounded warm results and staggered due times.

Live keeps its independent protected acquisition owners. This coordinator admits
only finite default reports, never account providers, pages 2..N or detail scans.
Browser leases describe demand, not worker capacity or source identity.
"""
from collections import OrderedDict
from threading import RLock
import time

from src.analysis.cache import dependency_signature
from src.analysis import local_day_start_ms
from src.reports import ReportKind, ReportRequest
from .report_control import ManagedReport

FINITE = (ReportKind.NORMAL, ReportKind.AI_STATS, ReportKind.TOKEN_MIX, ReportKind.COMPARISONS)
SECTIONS = {'models', 'watch', 'accounts', 'sessions', 'session', 'token-mix', 'ai-stats', 'comparisons', 'settings'}
MAX_ENTRIES = 12
LEASE_SECONDS = 90
MAX_AGE_MS = 3_600_000


def source_identity(selection):
    return dependency_signature((selection.selected, getattr(selection.source, 'source_instance', None)))


def usable(result, now_ms):
    if not result or result.get('error') or not result.get('view'):
        return False
    observed = result.get('source', {}).get('observed_at_ms')
    scope = result.get('scope', {})
    if scope.get('kind') == 'ai-stats' and scope.get('local_day_start_ms') != local_day_start_ms(
            scope.get('timezone_id', 'UTC'), now_ms=now_ms):
        return False
    return (type(observed) is int and 0 <= now_ms - observed <= MAX_AGE_MS
            and result['source'].get('status') in {'acquired', 'partial'})


def cadence(request, result, foreground):
    if request.kind is ReportKind.NORMAL:
        qualified = (result or {}).get('view', {}).get('model_comparison_sample_size', 0)
        return 3600 if qualified >= 100 else 900 if foreground else 2700
    if request.kind is ReportKind.AI_STATS:
        return 900 if foreground else 1800
    return 300 if foreground else 1200


class DataDispatcher:
    def __init__(self, jobs, *, clock=time.monotonic, wall_clock=time.time):
        self.jobs, self.clock, self.wall_clock = jobs, clock, wall_clock
        self.lock = RLock()
        self.entries = OrderedDict()
        self.tabs = OrderedDict()
        self.initialized = False
        self.identity = ''
        self.next_background = 0
        self.blocked_since = None
        self.source_error = None
        self.source_terminal = False
        self.price_actions = set()
        self.ready = False
        self.warm_allowed = False

    def price_refresh(self, key):
        with self.lock:
            self.price_actions.add(key)

    def invalidate(self):
        """Known projection dependency changed; no stale completed-job reuse."""
        with self.lock:
            for entry in self.entries.values():
                if entry['job']:
                    self.jobs.cancel(entry['job'])
                entry.update(job=None, result=None, result_id=None, due=0,
                             terminal=False, error=None, failures=0)

    def _prices(self):
        for key in tuple(self.price_actions):
            snapshot = self.jobs.snapshot(key)
            if not snapshot or snapshot['status'] in {'complete', 'failed', 'cancelled'}:
                self.price_actions.discard(key)
                if snapshot and snapshot['status'] == 'complete' and not (snapshot.get('result') or {}).get('error'):
                    self.invalidate()

    def _entry(self, request):
        if request not in self.entries:
            while len(self.entries) >= MAX_ENTRIES:
                victim = next((key for key, value in self.entries.items()
                               if not value['job'] and key not in self._foreground()), None)
                if victim is None:
                    raise RuntimeError('busy')
                del self.entries[victim]
            self.entries[request] = dict(job=None, result=None, result_id=None, due=0,
                failures=0, terminal=False, requested=False, error=None, finished=0)
        self.entries.move_to_end(request)
        return self.entries[request]

    def interest(self, tab, section, visible, request=None):
        with self.lock:
            self._expire()
            if tab not in self.tabs and len(self.tabs) >= 16:
                raise RuntimeError('busy')
            self.tabs[tab] = dict(section=section, visible=visible, request=request, touched=self.clock())
            if request:
                entry = self._entry(request)
                entry['requested'] = not bool(entry['result'])
                if visible and entry['job'] and request.kind is ReportKind.AI_STATS and hasattr(self.jobs, 'select_scope'):
                    self.jobs.select_scope(entry['job'], request.stats_scope)
                if entry['result'] and not entry['failures']:
                    entry['due'] = min(entry['due'], entry['finished'] + cadence(request, entry['result'], True))
            if not self.initialized:
                self.initialized = True
                for kind in FINITE:
                    self._entry(ReportRequest(kind))
            return {'lease_seconds': LEASE_SECONDS}

    def _expire(self):
        for tab, value in tuple(self.tabs.items()):
            if self.clock() - value['touched'] >= LEASE_SECONDS:
                del self.tabs[tab]

    def _foreground(self):
        return {tab['request'] for tab in self.tabs.values() if tab['visible'] and tab['request']}

    def lookup(self, request, *, retry=False):
        with self.lock:
            entry = self._entry(request)
            self._collect()
            entry['requested'] = not bool(entry['result'])
            if entry['result'] and not usable(entry['result'], int(self.wall_clock() * 1000)) and not entry['failures']:
                entry['due'] = 0
            if retry and not entry['job']:
                entry.update(terminal=False, due=0, failures=0, error=None)
            if (self.ready and not entry['job'] and not entry['terminal'] and self.clock() >= entry['due']
                    and (not entry['result'] or not usable(entry['result'], int(self.wall_clock() * 1000)) or retry)):
                self._submit(request, entry)
            result = entry['result']
            valid = usable(result, int(self.wall_clock() * 1000))
            blocked = self.source_error
            return dict(id=entry['job'] or (entry['result_id'] if valid else None), result=result if valid else None,
                stale=bool(result and not valid), error=blocked or entry['error'],
                terminal=self.source_terminal or entry['terminal'])

    def _submit(self, request, entry):
        managed = ManagedReport(**{name: getattr(request, name) for name in ReportRequest.__dataclass_fields__},
                                source_identity=self.identity)
        entry['job'] = self.jobs.submit(managed)

    def _collect(self):
        for request, entry in self.entries.items():
            key = entry['job']
            if not key:
                continue
            snapshot = self.jobs.snapshot(key)
            if snapshot is None:
                entry['job'] = None
                continue
            result = snapshot.get('result')
            ready = (result and not result.get('error') and result.get('view') and
                (request.kind is not ReportKind.AI_STATS or any(
                    row['period'] == request.stats_scope for row in result['view'].get('ai_stats', ()))))
            if ready:
                entry.update(result=result, result_id=key, failures=0, error=None)
            if snapshot['status'] in {'queued', 'running'}:
                continue
            entry['job'] = None
            if snapshot['status'] == 'complete' and ready:
                delay = cadence(request, result, request in self._foreground())
                # Stable per-product spread; missed periods coalesce to one turn.
                spread = int(dependency_signature(str(request))[:4], 16) % 90
                entry.update(due=self.clock() + delay + spread, terminal=False, finished=self.clock(), requested=False)
            else:
                error = (result or {}).get('error') or {}
                entry['error'] = error.get('code') or snapshot.get('error') or 'report_unavailable'
                if entry['error'] == 'source_identity_changed':
                    entry['result'] = None
                entry['failures'] += 1
                retryable = error.get('retryable') is True
                entry['terminal'] = not retryable or entry['failures'] >= 3
                entry['due'] = self.clock() + min(3600, 60 * 2 ** entry['failures'])

    def tick(self, *, identity=None, ready=True, error=None, terminal=False):
        with self.lock:
            identity = self.identity if identity is None else identity
            ready = ready and bool(identity)
            self.ready = ready
            self._expire()
            if self.identity and identity and self.identity != identity:
                for entry in self.entries.values():
                    if entry['job']:
                        self.jobs.cancel(entry['job'])
                self.entries.clear()
                self.initialized = False
            self.identity = identity
            self._prices()
            self._collect()
            if not ready:
                if self.blocked_since is None:
                    self.blocked_since = self.clock()
                self.source_terminal = terminal or self.clock() - self.blocked_since >= 120
                # A selected source can still be waiting for its first healthy
                # Live observation. Identity alone is not report readiness.
                self.source_error = error or ('source_wait_timeout' if self.source_terminal else 'source_starting')
                if self.source_terminal:
                    for entry in self.entries.values():
                        if entry['job']:
                            self.jobs.cancel(entry['job'])
                            entry['job'] = None
            else:
                self.blocked_since = self.source_error = None
                self.source_terminal = False
            foreground = self._foreground()
            if not ready:
                self.warm_allowed = False
                self._prioritize(foreground)
                return
            for request in foreground:
                entry = self._entry(request)
                if entry['result'] and not usable(entry['result'], int(self.wall_clock() * 1000)) and not entry['failures']:
                    entry['due'] = 0
                if not entry['job'] and not entry['terminal'] and self.clock() >= entry['due']:
                    try:
                        self._submit(request, entry)
                    except RuntimeError:
                        break
            # Never start speculative work ahead of incomplete foreground demand.
            waiting = any(not usable(self._entry(request)['result'], int(self.wall_clock() * 1000))
                          for request in foreground)
            self.warm_allowed = self.initialized and not waiting
            background = any(entry['job'] and request not in foreground for request, entry in self.entries.items())
            if self.initialized and not waiting and not background and self.clock() >= self.next_background:
                due = [(request, entry) for request, entry in self.entries.items()
                       if request not in foreground and not entry['job'] and not entry['terminal']
                       and self.clock() >= entry['due']]
                if due:
                    request, entry = min(due, key=lambda pair: pair[1]['due'])
                    try:
                        self._submit(request, entry)
                        self.next_background = self.clock() + 15
                    except RuntimeError:
                        pass  # Reserved admission remains with requested work.
            self._prioritize(foreground)

    def _prioritize(self, foreground):
        priorities = {}
        for request, entry in self.entries.items():
            key = entry['job']
            if key:
                priority = 0 if request in foreground else 1 if entry['requested'] else 2
                priorities[key] = min(priorities.get(key, 3), priority) if self.ready else 3
        self.jobs.prioritize(priorities)
