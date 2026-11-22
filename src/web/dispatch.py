"""One host-owned demand registry, bounded warm results and staggered due times.

Live keeps its independent protected acquisition owners. This coordinator admits
only finite default reports, never account providers, pages 2..N or detail scans.
Browser leases describe demand, not worker capacity or source identity.
"""
from collections import OrderedDict
from threading import RLock
import time

from src.analysis.cache import dependency_signature
from src.analysis.ai_stats import POLICY as STATS_POLICY, windows
from src.reports import ReportKind, ReportRequest
from .jobs import MAX_PENDING
from .report_control import ManagedReport

FINITE = (ReportKind.NORMAL, ReportKind.AI_STATS, ReportKind.TOKEN_MIX)
DEFAULT_REQUESTS = tuple(ReportRequest(kind) for kind in FINITE)
BACKGROUND_STAGGER = 15
RECENT_SECONDS = 1800
SECTIONS = {'models', 'watch', 'accounts', 'sessions', 'session', 'token-mix', 'ai-stats', 'settings'}
MAX_ENTRIES = 12
LEASE_SECONDS = 90
WORKER_INTERRUPTS = {'report_unavailable', 'worker_unavailable', 'cancelled'}
SOURCE_BLOCKERS = {'http_auth_failure', 'source_permission_denied', 'registration_invalid',
                   'registration_unreadable', 'unsupported_schema', 'unsupported_version'}


def source_identity(selection):
    return dependency_signature((selection.selected, getattr(selection.source, 'source_instance', None)))


def usable(result, now_ms):
    """Qualified historical data remain deliverable; cadence owns refresh age."""
    if not result or result.get('error') or not result.get('view'):
        return False
    if result['view'].get('kind') == 'ai-stats' and result['view'].get('ai_stats_policy') != STATS_POLICY:
        return False  # A prior derived schema must regenerate, never relax browser validation.
    observed = result.get('source', {}).get('observed_at_ms')
    return (type(observed) is int and 0 <= observed <= now_ms
             and result['source'].get('status') in {'acquired', 'partial'})


def current_result(request, result, now_ms):
    if not usable(result, now_ms):
        return False
    if request.kind is not ReportKind.TOKEN_MIX:
        return True
    view = result['view']
    period = view.get('token_mix_period') or {}
    if view.get('kind') != 'token-mix' or period.get('period') != request.token_mix_scope:
        return False
    if period.get('coverage') not in {None, 'partial', 'unknown'}:
        return False
    if request.token_mix_scope == 'all':
        return True
    try:
        zone = view['timezone_id']
        return isinstance(zone, str) and period.get('start_ms') == dict(windows(zone, now_ms))[request.token_mix_scope]
    except (KeyError, ValueError, OverflowError):
        return False


def token_mix_coverage(result):
    period = (result or {}).get('view', {}).get('token_mix_period') or {}
    return {'unknown': 0, 'partial': 1}.get(period.get('coverage'), 2)


def cache_only_reports(owner):
    return frozenset(kind for kind, feature in
                     ((ReportKind.TOKEN_MIX, 'cached_mix_enabled'), (ReportKind.AI_STATS, 'cached_stats_enabled'),
                      (ReportKind.NORMAL, 'cached_models_enabled'), (ReportKind.ALL_MODELS, 'cached_models_enabled'))
                     if getattr(owner, feature, False))


def cadence(request, result, foreground):
    if request.kind is ReportKind.NORMAL:
        qualified = (result or {}).get('view', {}).get('model_comparison_sample_size', 0)
        return 3600 if qualified >= 100 else 900 if foreground else 2700
    if request.kind is ReportKind.AI_STATS:
        return 900 if foreground else 1800
    return 300 if foreground else 1200


class DataDispatcher:
    def __init__(self, jobs, *, clock=time.monotonic, wall_clock=time.time, cache_only_mix=False,
                 cache_only_stats=False, models=None):
        self.jobs, self.clock, self.wall_clock = jobs, clock, wall_clock
        self.lock = RLock()
        self.entries = OrderedDict()
        self.tabs = OrderedDict()
        self._visible_leases = ()
        self.initialized = False
        self.identity = ''
        self.projection_epoch = 0
        self.next_background = 0
        self.source_error = None
        self.source_terminal = False
        self.price_actions = set()
        self.ready = False
        self.warm_allowed = False
        self.models = models
        self.model_binding = None
        self.default_requests = tuple(request for request in DEFAULT_REQUESTS
                                      if (not cache_only_mix or request.kind is not ReportKind.TOKEN_MIX)
                                      and (not cache_only_stats or request.kind is not ReportKind.AI_STATS))

    def price_refresh(self, key):
        with self.lock:
            self.price_actions.add(key)

    def invalidate(self):
        """Known projection dependency changed; no stale completed-job reuse."""
        with self.lock:
            self.projection_epoch += 1
            if self.models is not None:
                self.models.invalidate_prices(int(self.wall_clock() * 1000))
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
                victim = next((key for key, value in self.entries.items() if not value['job']
                               and key not in self.default_requests and key not in self._foreground()), None)
                if victim is None:
                    raise RuntimeError('busy')
                del self.entries[victim]
            self.entries[request] = dict(job=None, result=None, result_id=None, due=0,
                failures=0, terminal=False, requested=False, error=None, finished=0, visited=None)
        self.entries.move_to_end(request)
        return self.entries[request]

    def interest(self, tab, section, visible, request=None, *, history=False, account_period=None):
        with self.lock:
            self._expire()
            if tab not in self.tabs and len(self.tabs) >= 16:
                raise RuntimeError('busy')
            self.tabs[tab] = dict(section=section, visible=visible, request=request, history=history,
                                  account_period=account_period, touched=self.clock())
            self._visible_leases = tuple((lease['section'], lease['touched'] + LEASE_SECONDS)
                                         for lease in self.tabs.values() if lease['visible'])
            if request:
                entry = self._entry(request)
                entry['requested'] = not bool(entry['result'])
                if visible:
                    entry['visited'] = self.clock()
                if visible and entry['job'] and request.kind is ReportKind.AI_STATS and hasattr(self.jobs, 'select_scope'):
                    self.jobs.select_scope(entry['job'], request.stats_scope)
                if entry['result'] and not entry['failures']:
                    entry['due'] = min(entry['due'], entry['finished'] + cadence(request, entry['result'], True))
            return {'lease_seconds': LEASE_SECONDS}

    def account_timeline_foreground(self):
        with self.lock:
            self._expire()
            return frozenset(tab['account_period'] for tab in self.tabs.values()
                             if tab['visible'] and tab['account_period'])

    def _expire(self):
        for tab, value in tuple(self.tabs.items()):
            if self.clock() - value['touched'] >= LEASE_SECONDS:
                del self.tabs[tab]

    def visible_sections(self):
        # Live reads this immutable snapshot without entering the finite jobs lock.
        now = self.clock()
        return frozenset(section for section, expires in self._visible_leases if now < expires)

    def _foreground(self):
        requests = {tab['request'] for tab in self.tabs.values() if tab['visible'] and tab['request']}
        if self.model_binding is not None and 'models' in self.visible_sections():
            requests.add(ReportRequest(ReportKind.NORMAL))
        return requests

    def lookup(self, request, *, retry=False):
        with self.lock:
            entry = self._entry(request)
            self._collect()
            entry['requested'] = not bool(entry['result'])
            valid = current_result(request, entry['result'], int(self.wall_clock() * 1000))
            if entry['result'] and not valid and not entry['failures']:
                entry['due'] = 0
            if retry and not entry['job']:
                entry.update(terminal=False, due=0, failures=0, error=None)
            if (self.ready and not entry['job'] and not entry['terminal'] and self.clock() >= entry['due']
                    and (not valid or retry)):
                self._submit(request, entry)
            result = entry['result']
            blocked = self.source_error
            active = self.jobs.snapshot(entry['job']) if entry['job'] else None
            refresh = ('stopped' if self.source_terminal or entry['terminal'] else
                'waiting' if not self.ready else active['status'] if active else
                'delayed' if entry['failures'] else 'scheduled')
            return dict(id=entry['job'] or (entry['result_id'] if valid else None), result=result if valid else None,
                result_id=entry['result_id'] if valid else None, refresh=refresh,
                stale=bool(result and not valid), error=blocked or entry['error'],
                terminal=self.source_terminal or entry['terminal'],
                source_identity=self.identity, projection_epoch=self.projection_epoch)

    def _submit(self, request, entry):
        managed = ManagedReport(**{name: getattr(request, name) for name in ReportRequest.__dataclass_fields__},
                                source_identity=self.identity,
                                models_scope=self.model_binding[0].source if self._cached_models(request) else '')
        entry['job'] = self.jobs.submit(managed)
        if (request in self._foreground() and request.kind is ReportKind.AI_STATS
                and hasattr(self.jobs, 'select_scope')):
            self.jobs.select_scope(entry['job'], request.stats_scope)

    def _cached_models(self, request):
        return self.models is not None and request.kind is ReportKind.NORMAL

    def _sync_models(self):
        if self.models is None:
            return
        bound = self.models.binding()
        if self.model_binding == bound:
            return
        self.model_binding = bound
        entry = self.entries.pop(ReportRequest(ReportKind.NORMAL), None)
        if entry and entry['job']:
            self.jobs.cancel(entry['job'])
        if bound is not None:
            self._entry(ReportRequest(ReportKind.NORMAL))

    def _offer_models(self, request, snapshot, result, ready):
        if not self._cached_models(request):
            return ready, False
        if snapshot['status'] != 'complete' or not ready:
            return False, False
        now = int(self.wall_clock() * 1000)
        if self.model_binding is None or not current_result(request, result, now):
            return False, False
        epoch = self.projection_epoch
        accepted = self.models.offer(self.model_binding, result, eligible=lambda: self.projection_epoch == epoch)
        return accepted, False  # Data/benchmark HTTP cannot borrow the worker payload.

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
            work = ((result or {}).get('view') or {}).get('ai_stats_work') or {}
            scoped = work.get('scopes', {})
            old_schema = (request.kind is ReportKind.AI_STATS and result and result.get('view') and
                result['view'].get('kind') == 'ai-stats' and result['view'].get('ai_stats_policy') != STATS_POLICY)
            if request.kind is ReportKind.AI_STATS and scoped:
                ready = ready and scoped.get(request.stats_scope, {}).get('ready') is True
            ready = ready and not old_schema
            replace_result, degraded = ready, False
            if self._cached_models(request):
                ready, replace_result = self._offer_models(request, snapshot, result, ready)
            token_mix = request.kind is ReportKind.TOKEN_MIX
            if token_mix and ready:
                now = int(self.wall_clock() * 1000)
                ready = snapshot['status'] == 'complete' and current_result(request, result, now)
                coverage = token_mix_coverage(result)
                degraded = coverage < 2
                replace_result = ready and (not current_result(request, entry['result'], now)
                    or coverage == 2 or coverage > token_mix_coverage(entry['result']))
            if replace_result:
                entry.update(result=result, result_id=key, failures=0, error=None)
            if snapshot['status'] in {'queued', 'running'}:
                continue
            entry['job'] = None
            if snapshot['status'] == 'complete' and ready:
                delay = cadence(request, result, request in self._foreground())
                # Stable per-product spread; missed periods coalesce to one turn.
                spread = int(dependency_signature(str(request))[:4], 16) % 90
                if degraded:
                    delay, spread = 30, spread % 15  # Reconcile coverage sooner on the low-priority lane.
                if self._cached_models(request):
                    boundary = result['source'].get('model_price_boundary_ms')
                    if type(boundary) is int:
                        remaining = (boundary - int(self.wall_clock() * 1000)) / 1000
                        delay, spread = min(delay, max(30, remaining)), 0
                entry.update(due=self.clock() + delay + spread, terminal=False, finished=self.clock(), requested=False)
            elif token_mix and snapshot['status'] == 'complete' and result and not result.get('error'):
                period = (result.get('view') or {}).get('token_mix_period') or {}
                observed = result.get('source', {}).get('observed_at_ms')
                if period.get('period') == request.token_mix_scope and type(observed) is int and current_result(request, result, observed):
                    # An overnight slice may finish its original observation.
                    # Do not display it under today's controls; admit a new one.
                    entry.update(due=self.clock() + 2, terminal=False, error=None)
                else:
                    entry.update(terminal=True, error='report_invalid_result')
            else:
                error = (result or {}).get('error') or {}
                entry['error'] = error.get('code') or snapshot.get('error') or (
                    'ai_stats_schema_changed' if old_schema else 'ai_stats_no_progress'
                    if request.kind is ReportKind.AI_STATS and snapshot['status'] == 'complete' else 'report_unavailable')
                if entry['error'] == 'source_identity_changed':
                    entry['result'] = None
                entry['failures'] = min(12, entry['failures'] + 1)
                retryable = (error.get('retryable') is True or entry['error'] in {'ai_stats_no_progress', 'ai_stats_schema_changed'} or
                    not error and entry['error'] in WORKER_INTERRUPTS)
                entry['terminal'] = not retryable
                pending = entry['error'] in {'concurrent_source_change', 'history_revision_churn',
                    'ai_stats_revision_churn', 'ai_stats_checkpoint_busy', 'history_checkpoint_busy',
                    'report_cache_busy', 'session_catalog_changed', 'ai_stats_schema_changed'}
                entry['due'] = self.clock() + (min(60, 2 ** entry['failures']) if pending else
                    min(3600, 60 * 2 ** entry['failures']))

    def tick(self, *, identity=None, ready=True, error=None, terminal=False):
        with self.lock:
            identity = self.identity if identity is None else identity
            ready = ready and bool(identity)
            recovered_source = ready and not self.ready
            self.ready = ready
            self._expire()
            if self.identity and identity and self.identity != identity:
                for entry in self.entries.values():
                    if entry['job']:
                        self.jobs.cancel(entry['job'])
                self.entries.clear()
                self.projection_epoch += 1
                self.initialized = False
            self.identity = identity
            self._sync_models()
            self._prices()
            self._collect()
            if not ready:
                self.source_terminal = terminal
                # A selected source can still be waiting for its first healthy
                # Live observation. Identity alone is not report readiness.
                self.source_error = error or 'source_starting'
                if self.source_terminal:
                    for entry in self.entries.values():
                        if entry['job']:
                            self.jobs.cancel(entry['job'])
                            entry['job'] = None
            else:
                self.source_error = None
                self.source_terminal = False
                if recovered_source:
                    self.next_background = self.clock() + BACKGROUND_STAGGER
                    for entry in self.entries.values():
                        if entry['terminal'] and entry['error'] in SOURCE_BLOCKERS:
                            entry.update(terminal=False, due=0, error=None, failures=0)
            foreground = self._foreground()
            if not ready:
                self.warm_allowed = False
                self._prioritize(foreground)
                return
            if not self.initialized:
                self.initialized = True
                self.next_background = self.clock() + BACKGROUND_STAGGER
                for request in self.default_requests:
                    self._entry(request)
            self.warm_allowed = True
            for request in foreground:
                entry = self._entry(request)
                if entry['result'] and not current_result(request, entry['result'], int(self.wall_clock() * 1000)) and not entry['failures']:
                    entry['due'] = 0
                if not entry['job'] and not entry['terminal'] and self.clock() >= entry['due']:
                    try:
                        self._submit(request, entry)
                    except RuntimeError:
                        break
            self._warm(foreground)
            self._prioritize(foreground)

    def _warm(self, foreground):
        now = self.clock()
        if now < self.next_background:
            return
        active = {entry['job'] for request, entry in self.entries.items() if request in foreground}
        background = {entry['job'] for request, entry in self.entries.items()
                      if request not in foreground and entry['job']} - active
        if len(background) >= MAX_PENDING - 1:
            return  # Keep room for newly visible work (coalesced scopes count once).
        due = []
        for request, entry in self.entries.items():
            default = request in self.default_requests
            recent = entry['visited'] is not None and now - entry['visited'] < RECENT_SECONDS
            optional = recent and ((request.kind is ReportKind.AI_STATS and request.stats_scope != 'all')
                                   or (request.kind is ReportKind.TOKEN_MIX and request.token_mix_scope != 'all'))
            if (request not in foreground and not entry['job'] and not entry['terminal']
                    and (not self._cached_models(request) or self.model_binding is not None)
                    and now >= entry['due'] and (default or optional)):
                due.append((not default, entry['due'], request, entry))
        if not due:
            return
        _, _, request, entry = min(due, key=lambda item: item[:2])
        try:
            self._submit(request, entry)
            self.next_background = now + BACKGROUND_STAGGER
        except RuntimeError:
            pass  # Do not displace admitted work.

    def _prioritize(self, foreground):
        priorities = {}
        chart_visible = any(tab['visible'] and tab['account_period'] for tab in self.tabs.values())
        for request, entry in self.entries.items():
            key = entry['job']
            if key:
                ready_mix = request.kind is ReportKind.TOKEN_MIX and current_result(
                    request, entry['result'], int(self.wall_clock() * 1000))
                priority = 2 if ready_mix else 0 if request in foreground else 1 if entry['requested'] and not chart_visible else 2
                priorities[key] = min(priorities.get(key, 3), priority) if self.ready else 3
        self.jobs.prioritize(priorities)
