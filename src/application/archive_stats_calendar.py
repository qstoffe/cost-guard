"""Measured-only calendar rollups over a stream of disjoint, ordered spans."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.analysis.ai_stats import calendar_bounds
from src.analysis.timezones import resolve_timezone
from src.cache.display_stats_time import StatsCalendar, StatsTimeRow


@dataclass(slots=True)
class _CalendarScope:
    working: int = 0
    night: int = 0
    busiest_day: int = 0
    busiest_ms: int = 0
    previous: int = 0
    consecutive: int = 0
    streak: int = 0

    def add(self, day, working, night):
        self.working += working
        self.night += night
        self.consecutive = self.consecutive + 1 if self.previous + 1 == day else 1
        self.streak = max(self.streak, self.consecutive)
        self.previous = day
        if working > self.busiest_ms:
            self.busiest_day, self.busiest_ms = day, working

    def row(self, period, start):
        if not self.working:
            return StatsTimeRow(period, start, None)
        return StatsTimeRow(period, start, self.working,
                            StatsCalendar(self.busiest_day, self.busiest_ms, self.night, self.streak))


class MeasuredCalendar:
    def __init__(self, zone, scopes):
        self._tz = resolve_timezone(zone)
        self._scopes = tuple((period, start, _CalendarScope()) for period, start in scopes.items())
        self._day = self._bounds = None
        self._day_counts = {}

    def add_span(self, left, right):
        """Yield after each local day fragment, including very long executions."""
        day = datetime.fromtimestamp(left / 1000, timezone.utc).astimezone(self._tz).date()
        while True:
            if day != self._day:
                self._finish_day()
                self._day, self._bounds = day, calendar_bounds(day, self._tz)
            dawn, day_start, night_start, end = self._bounds
            for period, start, _state in self._scopes:
                low, high = max(left, dawn, start or 0), min(right, end)
                if high > low:
                    working, overnight = self._day_counts.get(period, (0, 0))
                    night = max(0, min(high, day_start) - low) + max(0, high - max(low, night_start))
                    self._day_counts[period] = working + high - low, overnight + night
            yield True
            if right <= end:
                break
            day += timedelta(days=1)

    def _finish_day(self):
        if self._day_counts:
            day = self._day.toordinal()
            for period, _start, state in self._scopes:
                if period in self._day_counts:
                    state.add(day, *self._day_counts[period])
            self._day_counts.clear()

    def rows(self):
        self._finish_day()
        return tuple(state.row(period, start) for period, start, state in self._scopes)
