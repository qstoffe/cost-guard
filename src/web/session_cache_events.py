"""Coalescible Sessions change hints; no row data crosses the event channel."""
from threading import Lock
from time import time_ns

from src.analysis.timezones import calendar_periods


class SessionCacheEvents:
    def __init__(self, hub, zone):
        self.hub = hub
        self.zone = zone
        self.lock = Lock()
        self.starts = {}
        self.periods = {}
        self.sequence = 0

    def committed(self, times=None):
        self._notify(committed=True, times=times)

    def roll_calendar(self):
        self._notify(committed=False, times=())

    def _notify(self, *, committed, times):
        now = time_ns() // 1_000_000
        with self.lock:
            starts = dict(calendar_periods(self.zone, now))
            changed = {period for period in starts if period not in self.starts or
                       starts[period] != self.starts[period]}
            self.starts = starts
            if committed:
                changed.update(period for period, lower in starts.items() if times is None or
                               lower is None or any(lower <= at for at in times))
            if not changed:
                return
            self.sequence += 1
            self.periods.update(dict.fromkeys(changed, self.sequence))
            self.hub.publish('sessions_cache', dict(revision=self.sequence, periods=dict(self.periods)))
