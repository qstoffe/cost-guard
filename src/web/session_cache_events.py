"""Coalescible Sessions change hints; no row data crosses the event channel."""
from heapq import heappop, heappush
import sqlite3
from threading import Lock
from time import time_ns

from src.analysis.timezones import calendar_periods


class SessionCacheEvents:
    def __init__(self, hub, zone, next_ready_activity=None):
        self.hub = hub
        self.zone = zone
        self.lock = Lock()
        self.starts = {}
        self.periods = {}
        self.sequence = 0
        self.next_ready_activity = next_ready_activity
        self.stored_due = 0
        self.stored_ready = False
        self.future = []
        self.future_times = set()

    def committed(self, times=None):
        self._notify(committed=True, times=times)

    def schedule_expiries(self, times):
        now = time_ns() // 1_000_000
        with self.lock:
            self._schedule_future(times, now)

    def _schedule_future(self, times, now):
        for at in times:
            if at > now and at not in self.future_times:
                self.future_times.add(at)
                heappush(self.future, at)

    def roll_calendar(self, *, storage_ready=False):
        self.stored_ready = storage_ready
        self._notify(committed=False, times=())

    def _notify(self, *, committed, times):
        now = time_ns() // 1_000_000
        with self.lock:
            starts = dict(calendar_periods(self.zone, now))
            changed = {period for period in starts if period not in self.starts or
                       starts[period] != self.starts[period]}
            self.starts = starts
            due = []
            if not committed and self.stored_ready and self.stored_due is not None and now >= self.stored_due:
                if self.stored_due:
                    due.append(self.stored_due)
                try:
                    self.stored_due = self.next_ready_activity(now) if self.next_ready_activity else None
                except (OSError, sqlite3.Error):
                    self.stored_due = now + 1000
            while self.future and self.future[0] <= now:
                at = heappop(self.future)
                self.future_times.remove(at)
                due.append(at)
            if times is not None:
                self._schedule_future(times, now)
                due.extend(at for at in times if at <= now)
            if committed:
                if times is None:
                    changed.update(starts)
                else:
                    changed.add('all')
            if due:
                changed.update(period for period, lower in starts.items() if
                               lower is None or any(lower <= at for at in due))
            if not changed:
                return
            self.sequence += 1
            self.periods.update(dict.fromkeys(changed, self.sequence))
            self.hub.publish('sessions_cache', dict(revision=self.sequence, periods=dict(self.periods)))
