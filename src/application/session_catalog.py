"""Shared live catalog, bounded scalar indexing and stable server-side page epochs.

HTTP reads never acquire history. Metric ordering is admitted only with keys for
every root; an unindexed root is not a canonically unknown metric.
"""
from collections import OrderedDict
from dataclasses import replace
from functools import cmp_to_key
from threading import Lock
import time
from uuid import uuid4

from src.analysis.cache import dependency_signature
from src.domain.session_tree import root_activity
from src.pricing.base import PricingUnavailableError
from src.reports.models import ReportKind, ReportProjection, SessionUsageRow
from src.reports.session_summary import session_summary
from src.sources.errors import SourceError

from .projection import project

SORTS = ("activity", "name", "model", "ccost", "prompts", "duration")


def sort_value(row, key):
    return {"activity": row.last_activity_ms, "name": row.title.casefold(),
        "model": "multiple models" if row.multiple_models else row.model.casefold() if row.model != "N/A" else None,
        "ccost": row.ccost if row.complete else None, "prompts": row.prompt_count,
        "duration": row.duration_ms}[key]


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
    def __init__(self, *, clock=time.monotonic):
        self.clock = clock
        self.lock = Lock()
        self.roots = OrderedDict()
        self.rows = {}
        self.revisions = {}
        self.valid = {}
        self.attempted = {}
        self.activity = {}
        self.active = frozenset()
        self.leases = OrderedDict()
        self.state = "loading"
        self.dependencies = None
        self.timezone_id = "UTC"
        self.unit = "credits"
        self.turn = 0
        self.checked_at = -100

    def observe(self, observation, *, unavailable=False):
        with self.lock:
            if unavailable or observation is None:
                self.state = "source_unavailable"
                return
            previous_roots = self.roots
            self.roots = OrderedDict((root.session_id, root) for root in observation.sessions
                                     if root.parent_session_id is None)
            self.activity = root_activity(observation.sessions)
            self.active = observation.live_candidates
            self.revisions = dict(observation.revisions)
            self.rows = {key: row for key, row in self.rows.items() if key in self.roots}
            self.valid = {key: value for key, value in self.valid.items()
                           if key in self.roots and value[0] == self.revisions.get(key)
                           and previous_roots[key].provenance == self.roots[key].provenance}
            self.state = "observed"

    def _current(self, key):
        value = self.valid.get(key)
        return (value is not None and value[0] == self.revisions.get(key)
                and (key not in self.active and not self.rows[key].running or self.clock() - value[1] <= 15))

    def needed(self):
        with self.lock:
            browsing = any(self.clock() - lease["touched"] <= 300 for lease in self.leases.values())
            work = any((not self._current(key) or key in self.active or self.rows[key].running)
                       and self.clock() - self.attempted.get(key, -100) >= 5 for key in self.roots)
            return self.state == "observed" and browsing and (work or self.clock() - self.checked_at >= 60)

    def _candidate(self):
        # Alternate priority admission and oldest-attempt admission. Busy/new
        # roots cannot permanently starve cold historical keys (or vice versa).
        candidates = [key for key in self.roots if self.clock() - self.attempted.get(key, -100) >= 5
                      and (not self._current(key) or key in self.active or self.rows[key].running)]
        if not candidates:
            return None
        self.turn += 1
        visible = {key for lease in self.leases.values() for key in lease.get("visible", ())}
        priority = [key for key in candidates if key in visible or key in self.active]
        pool = priority if self.turn % 2 and priority else candidates
        return min(pool, key=lambda key: (self.attempted.get(key, -100), key))

    def tick(self, service):
        dependencies = dependency_signature((service._dependencies(service._load_catalog()),
                                              service._load_comparison_catalog().analysis_signature))
        with self.lock:
            self.checked_at = self.clock()
            if dependencies != self.dependencies:
                self.valid.clear()
                self.dependencies = dependencies
            self.timezone_id = service.timezone_id
            self.unit = service.config.get("ccostDisplayUnit", "credits")
        start = self.clock()
        for _ in range(4):
            with self.lock:
                if self.state != "observed":
                    return
                key = self._candidate()
                if key is None:
                    return
                root, revision = self.roots[key], self.revisions.get(key)
                active = key in self.active or bool(self.rows.get(key) and self.rows[key].running)
                self.attempted[key] = self.clock()
            try:
                row, actual = session_summary(service, root, revision, active=active)
            except (SourceError, PricingUnavailableError):
                continue
            with self.lock:
                if (key in self.roots and root.provenance == self.roots[key].provenance
                        and revision == self.revisions.get(key) and actual == revision):
                    self.rows[key] = row
                    self.valid[key] = actual, self.clock()
            # One slow root is bounded by the source transport; no additional
            # work is admitted after the slice budget. Details have their own lane.
            if self.clock() - start >= 2:
                return

    def _rows(self):
        rows = []
        for key, root in self.roots.items():
            value = self.rows.get(key) or SessionUsageRow(key, root.title or "Untitled session", "N/A", False,
                                                        None, None, complete=False)
            rows.append(replace(value, title=root.title or "Untitled session",
                last_activity_ms=self.activity.get(key), archived=root.archived_at_ms is not None))
        return rows

    def page(self, *, token=None, offset=0, sort="activity", direction=-1, epoch=None):
        with self.lock:
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
            indexed = sum(self._current(key) for key in self.roots)
            pending = sort not in ("activity", "name") and indexed != len(self.roots)
            if offset == 0:
                applied = "activity" if pending else sort
                order = -1 if pending else direction
                rows = ordered(self._rows(), applied, order)
                latest = next(reversed(lease["epochs"]), None)
                previous = lease["epochs"].get(latest)
                if previous is not None and previous[1:] == (applied, order) and tuple(
                        row.session_id for row in previous[0]) == tuple(row.session_id for row in rows):
                    epoch = latest
                else:
                    epoch = uuid4().hex
                    lease["epochs"][epoch] = rows, applied, order
                while len(lease["epochs"]) > 8:
                    lease["epochs"].popitem(last=False)
            else:
                if epoch not in lease["epochs"]:
                    raise KeyError("catalog_expired")
                rows, applied, order = lease["epochs"][epoch]
            selected = rows[offset:offset + 50]
            lease["visible"] = tuple(row.session_id for row in selected)
            # Older pages retain membership/order; only independently observed
            # values may change. Deleted rows retain their epoch evidence.
            fresh = {row.session_id: row for row in self._rows()}
            selected = tuple(fresh.get(row.session_id, row) for row in selected)
            report = ReportProjection(ReportKind.SESSIONS, "Sessions", "OpenCode", (), session_usage=selected)
            result = project(report, self.timezone_id, self.unit).to_json()
            for row in result["session_usage"]:
                row["indexed"] = self._current(row["session_id"]) if row["session_id"] in self.roots else False
            return dict(token=token, epoch=epoch, offset=offset, total=len(rows), size=50,
                sort=applied, direction=order, pending_sort=pending, indexed=indexed,
                available=len(self.roots), state=self.state, view=result)

    def _expire(self):
        for token, lease in tuple(self.leases.items()):
            if self.clock() - lease["touched"] > 300:
                del self.leases[token]
