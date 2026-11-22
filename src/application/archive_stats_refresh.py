"""Admit local-only AI Stats work in bounded turns of the catalog lane."""
import sqlite3
import time

from src.analysis.ai_stats import windows

from .archive_stats_time import ArchiveStatsTime


class ArchiveStatsRefresh:
    def __init__(self, *, clock=time.monotonic):
        self._clock = clock
        self._probe_at = 0
        self._binding = None
        self._time = None

    def due(self, binding):
        """Only an in-memory hint; the Live thread never opens SQLite here."""
        return binding != self._binding or binding is not None and self._clock() >= self._probe_at

    def advance(self, history, source, zone, binding, now_ms, *, eligible):
        if self._binding != binding:
            self.withdraw()
            self._binding = binding
        if not eligible():
            self.withdraw()
            return None
        try:
            scopes = windows(zone, now_ms)
            if self._time is not None and (self._time.scopes != dict(scopes) or now_ms < self._time.now_ms):
                self._close_build()
            if self._time is None:
                if not history.stats_time_due(source, zone, scopes, now_ms):
                    self._probe_at = self._clock() + 5
                    return None
                self._time = ArchiveStatsTime(source, zone, now_ms)
            if self._time.step(history, eligible=eligible):
                return None
            publication = self._time.publication
            self._close_build()
            self._probe_at = self._clock() + (2 if publication is None else 5)
            return publication
        except (OSError, sqlite3.Error):
            self._close_build()
            self._probe_at = self._clock() + 5
            return None

    def _close_build(self):
        if self._time is not None:
            self._time.close()
            self._time = None

    def withdraw(self):
        # Temp SQLite belongs to the same executor that advances the reducer.
        self._close_build()
        self._binding = None
        self._probe_at = 0
