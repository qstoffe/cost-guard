"""One pinned, cooperative reduction of measured overlap-safe execution."""
import sqlite3

from src.analysis.ai_stats import windows
from src.cache.display_stats_time import StatsTimeRow, StatsTimeStamp
from src.cache.display_usage_reader import USAGE_SLICE


class ArchiveStatsTime:
    def __init__(self, source, zone, now_ms):
        self.source, self.zone, self.now_ms = source, zone, now_ms
        self.scopes = dict(windows(zone, now_ms))
        self._totals = dict.fromkeys(self.scopes)
        self._version = self._input = self._next_end = self._pending = None
        self._output = (0, 0)
        self._reading = True
        self.publication = None
        self._db = sqlite3.connect("")
        try:
            self._db.execute("PRAGMA cache_size=-512")
            self._db.execute("CREATE TABLE spans(start INTEGER, end INTEGER, PRIMARY KEY(start,end)) WITHOUT ROWID")
        except BaseException:
            self.close()
            raise

    def close(self):
        if self._db is not None:
            self._db.close()
            self._db = None

    def step(self, history, *, eligible):
        """False means finished (published or obsolete); no full-history step."""
        try:
            if eligible() and self._step(history, eligible):
                return True
        except BaseException:
            self.close()
            raise
        self.close()
        return False

    def _step(self, history, eligible):
        if self._reading:
            return self._stage(history)
        page = self._db.execute("""
            SELECT start,end FROM spans WHERE (start,end)>(?,?)
            ORDER BY start,end LIMIT ?
        """, (*self._output, USAGE_SLICE)).fetchall()
        if page:
            for left, right in page:
                self._merge(left, right)
            self._output = page[-1]
            return True
        if self._pending:
            self._count(*self._pending)
        stamp = StatsTimeStamp(self._version, self.zone, self.now_ms, self._next_end)
        rows = tuple(StatsTimeRow(period, start, self._totals[period]) for period, start in self.scopes.items())
        self.publication = history.publish_stats_time(self.source, stamp, rows, eligible=eligible)
        return False

    def _stage(self, history):
        evidence = history.stats_geometry(self.source, expected=self._version, after=self._input)
        if evidence is None:
            return False
        spans = []
        for row in evidence.intervals:
            if (row.provisional or row.start_ms is None or row.start_ms <= 0
                    or row.duration_ms is None or row.duration_ms <= 0):
                continue
            end = row.start_ms + row.duration_ms
            if end > (1 << 63) - 1:
                continue  # Unsupported clock geometry cannot become a durable deadline.
            if end <= self.now_ms:
                spans.append((row.start_ms, end))
            elif self._next_end is None or end < self._next_end:
                self._next_end = end
        with self._db:
            self._db.executemany("INSERT OR IGNORE INTO spans VALUES(?,?)", spans)
        self._version = evidence.version
        self._input = evidence.next_cursor
        self._reading = self._input is not None
        return True

    def _merge(self, left, right):
        if self._pending:
            start, finish = self._pending
            if left <= finish:
                self._pending = start, max(right, finish)
                return
            self._count(start, finish)
        self._pending = left, right

    def _count(self, left, right):
        for period, start in self.scopes.items():
            span = right - max(left, start or 0)
            if span > 0:
                self._totals[period] = (self._totals[period] or 0) + span
