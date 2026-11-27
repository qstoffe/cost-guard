"""Project Accounts history without requiring a current quota roster."""
from collections import defaultdict
from dataclasses import replace
from functools import lru_cache

from src.analysis.account_timeline import period_start
from src.analysis.account_timeline_cost import TimelineValuation
from src.analysis.period_ccost import PeriodCCostIndex, usage_provider
from src.application.account_timeline import AccountSeries, timeline_view
from src.application.contracts import ObjectValue, record
from src.application.projection import identity
from src.domain.session_tree import root_activity
from src.pricing.catalog import PricingCatalog


def history_roster(entries, current):
    routes = defaultdict(set)
    for entry in entries:
        if (ref := entry.account_ref) is not None:
            routes[ref.key].add(usage_provider(entry.model.provider or ref.provider_id))
    known = {series.account_key for series in current}
    live = tuple(replace(item, routes=tuple(sorted(set(item.routes) | routes[item.account_key])))
                  for item in current)
    # Historical-only series use recorded attribution, not any share of current
    # account balances, unassigned usage, or native quota.
    retired = tuple(AccountSeries(identity(key), key, f'{usage_provider(key[1])} account',
                                  tuple(sorted(value)), ())
                    for key, value in sorted(routes.items(), key=lambda item: identity(item[0]))
                    if key not in known)
    return live + retired


class ArchivedAccountTimeline:
    def __init__(self, usage):
        self.usage = usage
        self.index = self.month_index = self.index_key = None
        self.roster_key = self.reference = self.reference_signature = None
        self.roster = ()
        self.initial_periods = set()
        self.pending_periods = set()

    def step(self, scope, observation, periods, roster, zone, catalog, prices, migration_gap, now_ms, *,
             unavailable_history=frozenset(), live_roots=frozenset(), pending_history=frozenset(),
             source_available=False, progress_roots=None, defer_while_loading=frozenset(), **_):
        if not self.usage.archive.path.is_file():
            return {}, True, False
        cursor, facts, more = self.usage.snapshot(seconds=0.8 if defer_while_loading else 0.2)
        deferred = defer_while_loading if more else frozenset()
        periods = tuple(name for name in periods if name not in deferred)
        self.initial_periods = set(deferred)
        if not periods:
            # There is already a committed chart for every requested period.
            # Rebuild the index once from the hydrated facts, not per cursor slice.
            self.pending_periods = self.initial_periods.copy()
            return {}, more, False
        catalog = prices() or catalog or PricingCatalog(())
        candidates = frozenset((route, item.account_key) for item in roster for route, _ in item.allocation)
        identities = tuple(replace(item, month=None) for item in roster)
        roster_key = cursor, identities
        index_key = cursor, catalog.analysis_signature, catalog.reference_stale, candidates
        if self.index_key != index_key or self.roster_key != roster_key:
            entries = tuple(entry for fact in facts.values() for entry in fact.accounts or ())
        if self.roster_key != roster_key:
            self.roster = history_roster(entries, identities)
            self.roster_key = roster_key
        if self.index_key != index_key:
            if self.reference_signature != catalog.analysis_signature:
                # The analysis signature covers the rate and model fields used by
                # exact reference valuation. Cache request values only, not
                # estimates or coverage. Avoid eviction in full history scans.
                self.reference = lru_cache(maxsize=None)(catalog.reference_valuation)
                self.reference_signature = catalog.analysis_signature
            valuation = TimelineValuation(catalog, reference=self.reference)
            self.index, self.month_index = PeriodCCostIndex.archived_timeline(
                entries, valuation, timeline_accounts=candidates)
            self.index_key = index_key
        months = {item.key: item.month for item in roster}
        display_roster = tuple(replace(item, month=months.get(item.key)) for item in self.roster)
        sessions, root_by_session = (observation.sessions, observation.root_by_session) if observation else ((), {})
        activity = root_activity(sessions, root_by_session)
        first = {}
        for item in sessions:
            key = root_by_session.get(item.session_id, item.session_id)
            first[key] = min(first.get(key, item.created_at_ms), item.created_at_ms)
        waiting_keys = (pending_history | live_roots) - (unavailable_history - live_roots)
        unknown_keys = unavailable_history | {key for key in first
                                             if key not in facts or facts[key].accounts is None}
        spans = {key: (first[key], max(first[key] + 1, (activity.get(key) or now_ms) + 1))
                 for key in first if key in waiting_keys or key in unknown_keys}
        unavailable = tuple(span for key, span in spans.items() if key not in waiting_keys)
        waiting = [span for key, span in spans.items() if key in waiting_keys]
        live_progress, refresh_roots = progress_roots if progress_roots is not None else (live_roots, frozenset())
        historical = {key: span for key, span in spans.items() if key in waiting_keys and key not in live_progress}
        gaps = tuple((item.first_ms, item.last_ms + 1) for item in migration_gap.sessions
                     ) if migration_gap and migration_gap.has_gap else ()
        stamps = {key: tuple(entry.completed_at_ms for entry in fact.accounts or ()
                            if 0 < entry.completed_at_ms <= now_ms)
                   for key, fact in facts.items()}
        # A qualified complete catalog can prove days without any candidates.
        # Without a current catalog we have values, not proof of absence.
        oldest = 0 if source_available and observation is not None and not more else None
        starts = {name: period_start(name, now_ms, zone) for name in periods}
        values = {}
        for name, start in starts.items():
            initial = [span for key, span in historical.items() if span[1] > start and (
                key not in refresh_roots or not any(at >= start for at in stamps.get(key, ())))]
            if more or initial:
                self.initial_periods.add(name)
            value = timeline_view(name, now_ms, zone, display_roster, self.index, first_covered_ms=oldest,
                   gaps=gaps + unavailable, pending=waiting, initial_pending=initial,
                  price_revision=catalog.diagnostic_signature, month_index=self.month_index)
            progress = dict(cached=sum(any(at >= start for at in times) for times in stamps.values()),
                              complete=source_available and name not in self.initial_periods, remaining=None,
                              recovering=not source_available,
                             unavailable=sum(end >= start for _, end in unavailable))
            values[name] = ObjectValue(value.fields + (('history_progress', record(**progress)),))
        self.pending_periods = self.initial_periods.copy()
        return values, bool(waiting) or more, False
