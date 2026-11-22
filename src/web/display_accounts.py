"""Accounts reference-cost publisher on the shared catalog executor."""
import sqlite3
from threading import Lock
import time

from src.analysis.account_timeline import period_start
from src.application.archive_account_history import AccountHistoryPublication, ArchiveAccountHistory, archived_account_roster


class DisplayAccounts:
    def __init__(self, archive, *, clock=time.monotonic):
        self.archive = archive
        self._clock = clock
        self._state = None  # Live-owned offer; catalog navigation never mutates it.
        self._building = None
        self._probe_at = 0
        self._last_offer = None
        self._signal = Lock()

    def offer(self, accounts, *, verified):
        """Native quota/balance data do not cross into the historical archive."""
        views = self.archive.views
        if views is None or not verified:
            return  # Transient outage can still serve already committed history.
        try:
            roster = archived_account_roster(accounts)
        except ValueError:
            return  # An unqualified account list cannot invalidate a saved roster.
        binding = self.archive.sessions.clear_fence
        with self._signal:
            if self.archive.views is not views or self.archive.sessions.clear_fence != binding:
                return
            if roster is None:
                self._state = None
            elif self._state != (views, binding, roster):
                self._state = (views, binding, roster)

    def pending(self):
        return self._last_offer is not self._state or (
            self._state is not None and (self._building is not None or self._clock() >= self._probe_at))

    def reset(self):
        with self._signal:
            self._state = None

    def advance(self, now_ms, *, active):
        state = self._state
        if state is not self._last_offer:
            self._building = None
            self._last_offer = state
        if state is None:
            return
        views, fence, accounts = state

        def eligible():
            return (self._state is state and self.archive.views is views and
                    self.archive.sessions.clear_fence == fence and active())

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
                self._building = None
                self._probe_at = self._clock() + 2
        except (OSError, sqlite3.Error, ArithmeticError, ValueError):
            self._building = None
            self._probe_at = self._clock() + 5

    def close(self):
        self._building = None
