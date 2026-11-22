"""One pinned, cooperative reduction of measured overlap-safe execution."""
from dataclasses import replace
import sqlite3

from src.analysis.ai_stats import windows
from src.cache.display_stats_time import StatsTimeStamp
from src.cache.display_usage_reader import USAGE_SLICE

from .archive_stats_calendar import MeasuredCalendar
from .archive_stats_root_time import MeasuredRootTime


class ArchiveStatsTime:
    def __init__(self, source, zone, now_ms):
        self.source, self.zone, self.now_ms = source, zone, now_ms
        self.scopes = dict(windows(zone, now_ms))
        self._calendar = MeasuredCalendar(zone, self.scopes)
        self._version = self._input = self._next_end = self._output = None
        self._reading = True
        self.publication = None
        self._db = sqlite3.connect("")
        try:
            self._db.execute("PRAGMA cache_size=-512")
            self._db.execute("CREATE TABLE spans(start INTEGER, end INTEGER, PRIMARY KEY(start,end)) WITHOUT ROWID")
            self._root_time = MeasuredRootTime(self._db, self.scopes)
        except BaseException:
            self.close()
            raise

    def close(self):
        if self._output is not None:
            self._output.close()
            self._output = None
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
        if self._output is None:
            self._output = self._reduce_turns()
        with self._db:
            finished = any(not next(self._output, False) for _ in range(USAGE_SLICE))
        if finished:
            return self._publish(history, eligible)
        return True

    def _publish(self, history, eligible):
        stamp = StatsTimeStamp(self._version, self.zone, self.now_ms, self._next_end)
        root_time = self._root_time.rows()
        rows = tuple(replace(row, roots=root_time[row.period]) for row in self._calendar.rows())
        self.publication = history.publish_stats_time(self.source, stamp, rows, eligible=eligible)
        return False

    def _stage(self, history):
        evidence = history.stats_geometry(self.source, expected=self._version, after=self._input)
        if evidence is None:
            return False
        spans = []
        for root, row in zip(evidence.roots, evidence.intervals, strict=True):
            if (row.provisional or row.start_ms is None or row.start_ms <= 0
                    or row.duration_ms is None or row.duration_ms <= 0):
                continue
            end = row.start_ms + row.duration_ms
            if end > (1 << 63) - 1:
                continue  # Unsupported clock geometry cannot become a durable deadline.
            if end <= self.now_ms:
                spans.append((root, row.start_ms, end))
            elif self._next_end is None or end < self._next_end:
                self._next_end = end
        with self._db:
            self._db.executemany("INSERT OR IGNORE INTO spans VALUES(?,?)", ((a, b) for _, a, b in spans))
            self._root_time.stage(spans)
        self._version = evidence.version
        self._input = evidence.next_cursor
        self._reading = self._input is not None
        return True

    def _reduce_turns(self):
        after, pending = (0, 0), None
        while True:
            page = self._db.execute("""
                SELECT start,end FROM spans WHERE (start,end)>(?,?) ORDER BY start,end LIMIT ?
            """, (*after, USAGE_SLICE)).fetchall()
            if not page:
                break
            for left, right in page:
                if pending and left <= pending[1]:
                    pending = pending[0], max(right, pending[1])
                else:
                    if pending:
                        yield from self._calendar.add_span(*pending)
                    pending = left, right
                yield True
            after = page[-1]
        if pending:
            yield from self._calendar.add_span(*pending)
        yield from self._root_time.reduce()
