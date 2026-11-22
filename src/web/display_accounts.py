"""Accounts reference-cost publisher on the shared catalog executor."""
import sqlite3
from threading import Lock
import time
from uuid import uuid4

from src.analysis.account_timeline import DAY_MS, period_start
from src.analysis.cache import dependency_signature
from src.analysis.timezones import local_day_start_ms
from src.application.account_timeline import archived_timeline_view
from src.application.archive_account_history import (
    AccountHistoryPublication, ArchiveAccountHistory, archived_account_roster, roster_signature,
)
from src.reports.accounts import account_display_labels
from src.reports.models import AccountProjection


def _valid_until(period, now_ms, zone, rows, view):
    if period == "7-days":
        start = period_start(period, now_ms, zone)
        return min((row.start + DAY_MS * 7 + 1 for row in rows
                    if row.start >= start and row.subtotal is not None), default=None)
    if period == "month" and view["future_buckets"]:
        return view["buckets"][-1][1]
    return local_day_start_ms(zone, now_ms=now_ms, days_ago=-1)


class DisplayAccounts:
    def __init__(self, archive, publish, *, clock=time.monotonic):
        self.archive = archive
        self._publish = publish
        self._clock = clock
        self._state = None  # Background identity offer; catalog navigation never mutates it.
        self._deadline = None
        self._building = None
        self._probe_at = 0
        self._last_offer = None
        self._signal = Lock()
        self._marks = {}

    def offer(self, accounts, *, verified):
        """Native quota/balance data do not cross into the historical archive."""
        target = self.target()
        if target is not None and verified:
            self._offer(target, accounts, None)

    def target(self):
        views = self.archive.views
        return (views, self.archive.sessions.clear_fence) if views is not None else None

    def offer_identity(self, target, account, deadline):
        """Accept only a result pinned before the status observation began."""
        snapshots = (account,) if account is not None and account.ref.account_id and deadline is not None else ()
        accounts = tuple(AccountProjection(snapshot, label) for snapshot, label in account_display_labels(snapshots))
        self._offer(target, accounts, deadline)

    def _offer(self, target, accounts, deadline):
        try:
            roster = archived_account_roster(accounts)
            labels = tuple((bytes.fromhex(dependency_signature(item.account.key)), str(item.label)[:256])
                           for item in accounts if roster is not None)
        except ValueError:
            roster, labels = None, ()
        labels = tuple(dict(labels).items())
        with self._signal:
            if self.target() != target:
                return
            if not roster:
                if self._state is not None:
                    self._reset()
                return
            state = (*target, roster, labels)
            changed = self._state is None or self._state[:4] != state or not self._current()
            renewed = deadline != self._deadline
            if changed:
                self._state = (*state, uuid4().hex)
                self._marks = {}
            self._deadline = deadline
            if changed or renewed:
                self._announce(self._state[4])

    def _current(self):
        deadline = self._deadline
        return deadline is None or deadline.active(self._clock(), int(time.time() * 1000))

    def pending(self):
        return self._last_offer is not self._state or (
            self._state is not None and (self._building is not None or self._clock() >= self._probe_at))

    def reset(self):
        with self._signal:
            self._reset()

    def announce_binding(self, views):
        with self._signal:
            if self.archive.views is views and self._state is None:
                self._announce(views.binding)

    def _reset(self):
        self._state = None
        self._deadline = None
        self._marks = {}
        self._announce(self.scope())

    def _announce(self, scope):
        value = dict(scope=scope, marks=self._marks.copy())
        if self._deadline is not None:
            value["proof_expires_ms"] = self._deadline.wall_ms
        self._publish("accounts-cache", value)

    def snapshot(self, period, now_ms):
        views = self.archive.views
        fence = self.archive.sessions.clear_fence
        state = self._state
        if views is None:
            return None

        def eligible():
            return self._state is state and self.archive.views is views and self.archive.sessions.clear_fence == fence

        if state is None or not self._current():
            # A verified source, without a current provider roster, may read
            # an empty chart but must not borrow an archived account identity.
            self.archive.history.source_state(views.source)
            if not eligible():
                return None
            return dict(scope=views.binding, revision=0, expires_ms=None, view=None,
                        series=(), ready=False, acquiring=False, unchanged=False)
        if state[:2] != (views, fence):
            return None
        _, _, accounts, labels, scope = state
        value, epoch = self.archive.history.read_account_chart(
            views.source, views.timezone_id, roster_signature(accounts), period, now_ms)
        view = expires = None
        if value is not None:
            version, as_of, rows = value
            if version.archive_epoch == epoch:
                view = archived_timeline_view(period, as_of, now_ms, views.timezone_id, labels, rows)
                if view is not None:
                    view = view.to_json()
                    expires = _valid_until(period, now_ms, views.timezone_id, rows, view)
        if not eligible() or not self._current():
            return None
        return dict(scope=scope, revision=value[1] if view is not None else 0, expires_ms=expires,
                    view=view,
                    series=tuple(dict(id=key.hex(), account=label) for key, label in labels),
                    ready=True, acquiring=False, unchanged=False)

    def scope(self):
        views = self.archive.views
        if views is None:
            return None
        state = self._state
        if state is None or not self._current():
            return views.binding
        return state[4] if state[:2] == (views, self.archive.sessions.clear_fence) else None

    def advance(self, now_ms, *, active):
        state = self._state
        if state is not self._last_offer:
            self._building = None
            self._last_offer = state
        if state is None:
            return
        views, fence, accounts, _, scope = state

        def eligible():
            return (self._state is state and self.archive.views is views and
                    self.archive.sessions.clear_fence == fence and self._current() and active())

        if not eligible():
            self._building = None
            self._probe_at = self._clock() + 5
            return
        history = self.archive.history
        day = period_start("today", now_ms, views.timezone_id)
        try:
            if self._building is not None:
                built_at = self._building.build.now_ms
                if built_at > now_ms or built_at < day:
                    self._building = None
            if self._building is None:
                if history.cleanup_account_buckets(views.source):
                    self._probe_at = self._clock()
                    return
                if not accounts:
                    self._probe_at = self._clock() + 5
                    return
                build = ArchiveAccountHistory(views.source, views.timezone_id, now_ms, accounts)
                if not history.account_history_due(views.source, build.zone, build.roster, now_ms,
                                                    max(day, now_ms - 300_000)):
                    self._probe_at = self._clock() + 5
                    return
                self._building = AccountHistoryPublication(build)
            if not self._building.step(history, eligible=eligible):
                if self._building.published:
                    with self._signal:
                        if eligible():
                            self._marks = self._building.marks()
                            self._announce(scope)
                self._building = None
                self._probe_at = self._clock() + 2
        except (OSError, sqlite3.Error, ArithmeticError, ValueError):
            self._building = None
            self._probe_at = self._clock() + 5

    def close(self):
        self._building = None
