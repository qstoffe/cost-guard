"""Admit local-only AI Stats work in bounded turns of the catalog lane."""
import sqlite3
import time

from src.analysis.ai_stats import windows

from .archive_stats_time import ArchiveStatsTime
from .archive_stats_tokens import ArchiveStatsTokens


class ArchiveStatsRefresh:
    def __init__(self, *, clock=time.monotonic):
        self._clock = clock
        self._binding = None
        self._turn = 0
        self._lanes = (
            _Lane(ArchiveStatsTime, "stats_time_due"),
            _Lane(ArchiveStatsTokens, "stats_tokens_due"),
        )

    def due(self, binding):
        """Only an in-memory hint; the Live thread never opens SQLite here."""
        return binding != self._binding or binding is not None and any(
            lane.probe_at <= self._clock() for lane in self._lanes)

    def advance(self, history, source, zone, binding, now_ms, *, eligible):
        if self._binding != binding:
            self.withdraw()
            self._binding = binding
        if not eligible():
            self.withdraw()
            return None
        for _ in self._lanes:
            index = self._turn
            self._turn = (index + 1) % len(self._lanes)
            lane = self._lanes[index]
            if self._clock() >= lane.probe_at:
                return lane.advance(history, source, zone, now_ms, self._clock, eligible)
        return None

    def withdraw(self):
        # Temp SQLite belongs to the same executor that advances the reducer.
        for lane in self._lanes:
            lane.close()
            lane.probe_at = 0
        self._binding = None
        self._turn = 0


class _Lane:
    def __init__(self, start, probe):
        self.start, self.probe = start, probe
        self.build = None
        self.probe_at = 0

    def advance(self, history, source, zone, now_ms, clock, eligible):
        try:
            scopes = windows(zone, now_ms)
            if self.build is not None and (self.build.scopes != dict(scopes) or now_ms < self.build.now_ms):
                self.close()
            if self.build is None:
                if not getattr(history, self.probe)(source, zone, scopes, now_ms):
                    self.probe_at = clock() + 5
                    return None
                self.build = self.start(source, zone, now_ms)
            if self.build.step(history, eligible=eligible):
                return None
            publication = self.build.publication
            self.close()
            self.probe_at = clock() + (2 if publication is None else 5)
            return publication
        except (OSError, sqlite3.Error):
            self.close()
            self.probe_at = clock() + 5
            return None

    def close(self):
        if self.build is not None:
            self.build.close()
            self.build = None
