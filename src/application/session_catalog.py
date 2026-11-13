"""Shared live catalog, bounded scalar indexing and stable server-side page epochs.

HTTP reads never acquire history. Metric ordering is admitted only with keys for
every period-eligible root; an unindexed root is not a canonically unknown metric.
"""
from collections import OrderedDict
from dataclasses import replace
from functools import cmp_to_key
from threading import Lock
import time
from uuid import uuid4

from src.analysis.cache import dependency_signature
from src.analysis.model_identity import payload_current
from src.domain.session_tree import root_activity
from src.pricing.base import PricingUnavailableError
from src.reports.models import ReportKind, ReportProjection, SessionUsageRow
from src.reports.session_summary import session_summary
from src.sources.errors import SourceError

from .projection import project
from .session_catalog_scope import CatalogEpoch, PAGE_SIZE, catalog_window, population

SORTS = ("activity", "name", "model", "effort", "ccost", "prompts", "duration", "ctx")


def effort_sort(key):
    if key is None:
        return None
    levels = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "default", "multiple")
    return (levels.index(key) if key in levels else len(levels), key)


def sort_value(row, key):
    return {"activity": row.last_activity_ms, "name": row.title.casefold(),
        "model": "multiple models" if row.multiple_models else row.model.casefold() if row.model != "N/A" else None,
        "effort": effort_sort(row.effort_key),
        "ccost": row.ccost if row.complete else None, "prompts": row.prompt_count,
        "duration": row.duration_ms, "ctx": row.context_tokens if row.context_qualified else None}[key]


def ordered(rows, key, direction):
    def compare(left, right):
        a, b = sort_value(left, key), sort_value(right, key)
        if a is None or b is None:
            result = (a is None) - (b is None)
        else:
            result = ((a > b) - (a < b)) * direction
        return result or ((left.session_id > right.session_id) - (left.session_id < right.session_id))
    return tuple(sorted(rows, key=cmp_to_key(compare)))


class SessionCatalog:
    def __init__(self, *, clock=time.monotonic, clock_ms=lambda: int(time.time() * 1000), timezone_id="UTC"):
        self.clock = clock
        self.clock_ms = clock_ms
        self.lock = Lock()
        self.roots = OrderedDict()
        self.rows = {}
        self.revisions = {}
        self.valid = {}
        self.attempted = {}
        self.failures = {}
        self.failure_counts = {}
        self.failure_reasons = {}
        self.generation = 0
        self.metrics = dict(cache_hits=0, cache_misses=0, attempts=0, retries=0, settled=0)
        self.work = None
        self.work_sequence = 0
        self.activity = {}
        self.activity_index = ()
        self.active = frozenset()
        self.prompt_activity = {}
        self.watch_activity = {}
        self.leases = OrderedDict()
        self.state = "loading"
        self.dependencies = None
        self.model_dependencies = {}
        self.timezone_id = timezone_id
        self.unit = "credits"
        self.turn = 0
        self.checked_at = -100
        self.index_unavailable = False
        self.warm = False
        self.last_page = ()
        self.background_due = 0
        self.observed = None
        self.last_observation = None

    def enable_warm(self, enabled=True):
        with self.lock:
            self.warm = enabled

    def interest(self, token, visible):
        with self.lock:
            lease = self.leases.get(token)
            if lease is None:
                raise KeyError('catalog_expired')
            lease['interest_until'] = self.clock() + 90 if visible else self.clock()

    def _browsing(self, lease):
        return (self.clock() < lease['interest_until'] if 'interest_until' in lease
                else self.clock() - lease['touched'] <= 300)

    def _targets(self):
        browsing = [lease for lease in self.leases.values() if self._browsing(lease)]
        selected = {key for lease in browsing for key in lease.get('visible', ())}
        for lease in browsing:
            if not lease.get('pinned') and lease.get('sort') not in (None, 'activity', 'name'):
                lease['candidates'] = self._population(lease['period'])[1]
                selected.update(lease['candidates'])
        if browsing:
            return selected & self.roots.keys()
        if not self.warm or self.clock() < self.background_due:
            return set()
        return set(self.last_page or sorted(self.roots,
            key=lambda key: (-(self.activity.get(key) or 0), key))[:PAGE_SIZE]) & self.roots.keys()

    def _population(self, period):
        window = catalog_window(period, self.timezone_id, self.clock_ms())
        return window, population(self.roots, self.activity_index, window)

    def observe(self, observation, *, unavailable=False, timezone_id=None):
        with self.lock:
            if timezone_id is not None:
                self.timezone_id = timezone_id
            if unavailable or observation is None:
                self.state = "source_unavailable"
                return
            if observation is self.last_observation:
                return  # Publishing the same old catalog cannot renew source age.
            self.last_observation = observation
            previous_roots = self.roots
            self.roots = OrderedDict((root.session_id, root) for root in observation.sessions
                                     if root.parent_session_id is None)
            if any(previous_roots[key].provenance != root.provenance
                   for key, root in self.roots.items() if key in previous_roots):
                for lease in self.leases.values():
                    lease['epochs'].clear()
                self.last_page = ()
            self.activity = root_activity(observation.sessions)
            self.activity_index = tuple(sorted((at, key) for key, at in self.activity.items()
                if key in self.roots and type(at) is int and at > 0))
            self.active = observation.live_candidates
            previous_revisions = self.revisions
            self.revisions = dict(observation.revisions)
            if (tuple(previous_roots) != tuple(self.roots) or any(
                    key not in previous_roots or previous_roots[key] != root
                    for key, root in self.roots.items()) or previous_revisions != self.revisions):
                self.generation += 1
            self.rows = {key: row for key, row in self.rows.items() if key in self.roots}
            self.valid = {key: value for key, value in self.valid.items()
                           if key in self.roots and value[0] == self.revisions.get(key)
                             and previous_roots[key].provenance == self.roots[key].provenance}
            # An authoritative unchanged revision validates stable scalar facts;
            # navigation and failed observations never renew this proof.
            self.valid = {key: (value[0], self.clock()) if key not in self.active and not self.rows[key].running
                          else value for key, value in self.valid.items()}
            self.rows = {key: row for key, row in self.rows.items()
                          if previous_roots[key].provenance == self.roots[key].provenance}
            self.model_dependencies = {key: value for key, value in self.model_dependencies.items()
                                       if key in self.rows}
            self.prompt_activity = {key: value for key, value in self.prompt_activity.items()
                if key in self.roots and previous_roots[key].provenance == self.roots[key].provenance}
            self.failures = {key: failure for key, failure in self.failures.items()
                             if key in self.roots and previous_roots[key].provenance == self.roots[key].provenance
                              and failure[0] == self.revisions.get(key)}
            self.failure_counts = {key: value for key, value in self.failure_counts.items() if key in self.failures}
            self.failure_reasons = {key: value for key, value in self.failure_reasons.items() if key in self.failures}
            self.state = "observed"
            self.observed = self.clock()

    def observe_prompts(self, evidence):
        """Canonical Watch captures only: root identity, lifecycle and original age.

        Repeated publication never renews a capture. Candidates are admission hints,
        not proof; scalar/pricing acquisition cannot invalidate independent proof.
        """
        with self.lock:
            self.watch_activity = {root.session_id: (self.clock() - age, running)
                for root, running, age in evidence if 0 <= age <= 15
                and root.session_id in self.roots
                and root.provenance == self.roots[root.session_id].provenance}

    def _running(self, key, fallback):
        if self.state != "observed" or key not in self.roots:
            return False
        signals = [value for value in (self.prompt_activity.get(key), self.watch_activity.get(key))
                   if value is not None and 0 <= self.clock() - value[0] <= 15]
        return max(signals, key=lambda value: (value[0], not value[1]))[1] if signals else fallback

    def _current(self, key):
        value = self.valid.get(key)
        return (not self.index_unavailable and value is not None and value[0] == self.revisions.get(key)
                and 0 <= self.clock() - value[1] <= 3600
                and (key not in self.active and not self.rows[key].running or self.clock() - value[1] <= 15))

    def needed(self):
        with self.lock:
            targets = self._targets()
            if self.index_unavailable:
                return self.state == "observed" and bool(targets) and self.clock() - self.checked_at >= 30
            work = any(self._eligible(key) for key in targets)
            return self.state == "observed" and bool(targets) and (work or self.clock() - self.checked_at >= 60)

    def index_failed(self):
        with self.lock:
            self.index_unavailable = True
            self.checked_at = self.clock()

    def _eligible(self, key):
        failure = self.failures.get(key)
        if failure and failure[1]:
            return False  # Unsupported/auth failures require changed source evidence.
        delay = 30 if failure else 5
        return (self.clock() - self.attempted.get(key, -100) >= delay
                and (not self._current(key) or key in self.active or self.rows[key].running
                     or not self.rows[key].context_qualified and self._requested(key, 'ctx')
                     or not self.rows[key].effort_qualified and self._requested(key, 'effort')))

    def _requested(self, key, sort):
        return any(lease.get('sort') == sort and self._browsing(lease)
            and key in lease.get('candidates', ()) for lease in self.leases.values())

    def _candidate(self):
        # Only requested rows, or scoped scalar keys required by a requested
        # metric sort. Activity/name navigation never hydrates pages 2..N.
        candidates = [key for key in self._targets() if self._eligible(key)]
        if not candidates:
            return None
        self.turn += 1
        visible = dict.fromkeys(key for lease in sorted(self.leases.values(), key=lambda item: -item["touched"])
                                if self._browsing(lease) for key in lease.get("visible", ()))
        priority = [key for key in visible if key in candidates]
        if self.turn % 8 and priority:
            return min(priority, key=lambda key: (self._current(key), self.attempted.get(key, -100)))
        return min(candidates, key=lambda key: (self.attempted.get(key, -100), key))

    def tick(self, service):
        dependencies = dependency_signature((service._dependencies(service._load_catalog()),
                                              service._load_comparison_catalog().diagnostic_signature))
        with self.lock:
            self.checked_at = self.clock()
            self.index_unavailable = False
            if dependencies != self.dependencies:
                self.valid.clear()
                self.failures.clear()
                self.failure_counts.clear()
                self.failure_reasons.clear()
                self.generation += 1
                self.dependencies = dependencies
            self.timezone_id = service.timezone_id
            self.unit = service.config.get("ccostDisplayUnit", "credits")
        start = self.clock()
        with self.lock:
            targets = self._targets()
            identities = {key: self.model_dependencies[key] for key in targets
                          if key in self.valid and key in self.model_dependencies}
        # Native model/default observations can change without a history revision.
        # Validate only this lane's eligible roots, using the source's bounded catalog.
        changed = [key for key, values in identities.items() if not payload_current(service.source, values)]
        with self.lock:
            for key in changed:
                self.valid.pop(key, None)
                self.failures.pop(key, None)
                self.attempted.pop(key, None)
            if changed:
                self.generation += 1
        for _ in range(4):
            with self.lock:
                if self.state != "observed":
                    return
                key = self._candidate()
                if key is None:
                    break
                root, revision = self.roots[key], self.revisions.get(key)
                active = key in self.active or bool(self.rows.get(key) and self.rows[key].running)
                self.attempted[key] = self.clock()
                self.metrics['attempts'] += 1
                self.metrics['retries'] += int(key in self.failures)
                retrying = key in self.failures
            try:
                identity_values = []
                row, actual = session_summary(service, root, revision, active=active, metrics=self.metrics,
                    on_stage=lambda stage: self._stage(stage, retrying),
                    on_dependencies=identity_values.extend)
            except (SourceError, PricingUnavailableError) as error:
                with self.lock:
                    if key in self.roots and revision == self.revisions.get(key):
                        self.failures[key] = revision, isinstance(error, SourceError) and error.terminal
                        self.failure_counts[key] = self.failure_counts.get(key, 0) + 1
                        self.failure_reasons[key] = str(error.code) if isinstance(error, SourceError) else 'pricing_unavailable'
            else:
                with self.lock:
                    if (key in self.roots and root.provenance == self.roots[key].provenance
                            and revision == self.revisions.get(key)):
                        if actual == revision:
                            self.rows[key] = row
                            self.model_dependencies[key] = identity_values
                            self.valid[key] = actual, self.clock()
                            self.prompt_activity[key] = self.attempted[key], row.running
                            partial = ('context' if not row.context_qualified and self._requested(key, 'ctx') else
                                       'effort' if not row.effort_qualified and self._requested(key, 'effort') else None)
                            if partial:
                                self.failures[key] = revision, False
                                self.failure_counts[key] = self.failure_counts.get(key, 0) + 1
                                self.failure_reasons[key] = 'partial_source_' + partial
                            else:
                                self.failures.pop(key, None)
                                self.failure_counts.pop(key, None)
                                self.failure_reasons.pop(key, None)
                        else:
                            self.failures[key] = revision, False
                            self.failure_counts[key] = self.failure_counts.get(key, 0) + 1
                            self.failure_reasons[key] = 'concurrent_source_change'
            finally:
                with self.lock:
                    self.work = None
                    self.metrics['settled'] += 1
            # One slow root is bounded by the source transport; no additional
            # work is admitted after the slice budget. Details have their own lane.
            if self.clock() - start >= 2:
                break
        with self.lock:
            if not any(self._browsing(lease) for lease in self.leases.values()):
                self.background_due = self.clock() + (15 if any(
                    not self._current(key) for key in targets if key in self.roots) else 900)

    def _stage(self, stage, retrying):
        # One scalar lane owns these actual call boundaries, never a browser clock.
        with self.lock:
            self.work_sequence += 1
            self.work = dict(stage=stage, retrying=retrying, active=True, sequence=self.work_sequence)

    def _rows(self, keys):
        rows = []
        now = self.clock_ms()
        for key in keys:
            root = self.roots[key]
            value = self.rows.get(key) or SessionUsageRow(key, root.title or "Untitled session", "N/A", False,
                                                        None, None, complete=False)
            if key in self.rows and (key not in self.valid or self.valid[key][0] != self.revisions.get(key)):
                value = replace(value, context_tokens=None,
                    context_detail="Source revision changed; waiting for current session context.")
            activity = self.activity.get(key)
            rows.append(replace(value, title=root.title or "Untitled session",
                last_activity_ms=activity if type(activity) is int and 0 < activity <= now else None,
                archived=root.archived_at_ms is not None))
        return rows

    def _key_current(self, key, sort):
        return (self._current(key) and not (sort == 'model' and self.rows[key].model_pending)
                and not (sort == 'effort' and (self.rows[key].effort_pending or not self.rows[key].effort_qualified))
                and not (sort == 'ctx' and not self.rows[key].context_qualified))

    def _progress(self, sort, pending, selected, indexed, pinned, candidates):
        keys = candidates if pending else tuple(row.session_id for row in selected)
        completed = indexed if pending else sum(self._current(key) for key in keys)
        failed = [key for key in keys if key in self.failures and
                  (self.failures[key][1] or self.failure_counts.get(key, 0) >= 3)]
        reason = ('source_unavailable' if self.state == 'source_unavailable' else
                  'index_unavailable' if self.index_unavailable else
                  self.failure_reasons.get(failed[0], 'source_key_unavailable') if failed else None)
        return dict(generation=self.generation, phase='index' if pending else 'page',
            status='failed' if reason else 'pending' if pending or completed < len(keys) else 'ready',
            completed=completed, total=len(keys), reason=reason,
            failed=len(failed), waiting=sum(key in self.failures for key in keys),
            pinned=pinned, metrics=dict(self.metrics),
            revalidating=sum(key in self.rows and not self._key_current(key, sort) for key in keys),
            work=dict(self.work) if self.work else dict(active=False, sequence=self.work_sequence,
                stage='waiting_retry' if any(key in self.failures for key in keys) else
                      'queued' if pending or completed < len(keys) else 'ready'))

    def page(self, *, token=None, offset=0, sort="activity", direction=-1, epoch=None, period="today"):
        with self.lock:
            window, candidates = self._population(period)
            self._expire()
            if token is None:
                if len(self.leases) >= 32:
                    raise RuntimeError("catalog_busy")
                token = uuid4().hex
                self.leases[token] = dict(touched=self.clock(), epochs=OrderedDict())
            lease = self.leases.get(token)
            if lease is None:
                raise KeyError("catalog_expired")
            lease["touched"] = self.clock()
            if 'interest_until' in lease:
                lease['interest_until'] = self.clock() + 90
            indexed = sum(self._key_current(key, sort) for key in candidates)
            pending = sort not in ("activity", "name") and indexed != len(candidates)
            if offset == 0:
                applied = "activity" if pending else sort
                order = -1 if pending else direction
                rows = ordered(self._rows(candidates), applied, order)
                latest = next(reversed(lease["epochs"]), None)
                previous = lease["epochs"].get(latest)
                if (previous is not None and (previous.sort, previous.direction) == (applied, order)
                        and previous.window.identity == window.identity and tuple(
                        row.session_id for row in previous.rows) == tuple(row.session_id for row in rows)):
                    epoch = latest
                    window = previous.window
                else:
                    epoch = uuid4().hex
                    lease["epochs"][epoch] = CatalogEpoch(rows, applied, order, window)
                while len(lease["epochs"]) > 8:
                    lease["epochs"].popitem(last=False)
            else:
                if epoch not in lease["epochs"]:
                    raise KeyError("catalog_expired")
                snapshot = lease["epochs"][epoch]
                rows, applied, order = snapshot.rows, snapshot.sort, snapshot.direction
                if (applied != sort or order != direction or snapshot.window.period != period
                        or snapshot.window.timezone_id != self.timezone_id):
                    raise KeyError('catalog_expired')
                window = snapshot.window
                candidates = tuple(row.session_id for row in rows)
                indexed = sum(self._key_current(key, sort) for key in candidates)
                # These global keys were already qualified when the epoch was
                # published. New arrivals must not invalidate its older pages.
                pending = False
                if offset >= len(rows):
                    raise KeyError('catalog_expired')
                if any(row.session_id not in self.roots for row in rows[offset:offset + PAGE_SIZE]):
                    raise KeyError('catalog_expired')
            lease.update(sort=sort, period=period, candidates=candidates, pinned=offset > 0)
            selected = rows[offset:offset + PAGE_SIZE]
            lease["visible"] = tuple(row.session_id for row in selected)
            self.last_page = lease['visible']
            # Older pages retain membership/order; only independently observed
            # values may change. Deleted rows retain their epoch evidence.
            fresh = {row.session_id: row for row in self._rows(lease['visible'])}
            selected = tuple(fresh.get(row.session_id, row) for row in selected)
            report = ReportProjection(ReportKind.SESSIONS, "Sessions", "OpenCode", (), session_usage=selected)
            result = project(report, self.timezone_id, self.unit).to_json()
            for row in result["session_usage"]:
                key = row["session_id"]
                current = key in self.roots and self._current(key)
                row["indexed"] = current
                row["has_summary"] = key in self.rows or row["prompt_count"] is not None
                unavailable = self.index_unavailable or self.state == "source_unavailable" or key in self.failures or key not in self.roots
                row["metric_state"] = ("retained" if row["has_summary"] else "unavailable") if unavailable else (
                    "ready" if current else "retained" if row["has_summary"] else "pending")
                row["running"] = self._running(key, bool(row["running"] and current and not unavailable))
                row["metric_states"] = {name: row["metric_state"] for name in ("model", "effort", "ccost", "prompts", "duration", "ctx")}
                if current and not self.rows[key].context_qualified:
                    row["metric_states"]["ctx"] = "unavailable"
                if key in self.rows and (key not in self.valid or self.valid[key][0] != self.revisions.get(key)):
                    row["metric_states"]["ctx"] = "unavailable" if unavailable else "pending"
                if row["running"] and not unavailable and self.rows.get(key) and self.rows[key].model_pending:
                    row["metric_states"]["model"] = "pending"
                if current and not self.rows[key].effort_qualified:
                    row["metric_states"]["effort"] = "unavailable"
                if row["running"] and not unavailable and self.rows.get(key) and self.rows[key].effort_pending:
                    row["metric_states"]["effort"] = "pending"
            return dict(token=token, epoch=epoch, offset=offset, total=len(rows), size=PAGE_SIZE,
                period=period, window=dict(start_ms=window.start_ms, end_ms=window.end_ms, timezone_id=window.timezone_id),
                sort=applied, direction=order, pending_sort=pending, indexed=indexed,
                available=len(candidates), state=self.state, view=result,
                requested_sort=sort, requested_direction=direction,
                progress=self._progress(sort, pending, selected, indexed, offset > 0, candidates),
                age_ms=None if self.observed is None else int(max(0, self.clock() - self.observed) * 1000),
                page_ready=sum(self._current(row.session_id) for row in selected if row.session_id in self.roots))

    def _expire(self):
        for token, lease in tuple(self.leases.items()):
            if self.clock() - lease["touched"] > 300:
                del self.leases[token]
