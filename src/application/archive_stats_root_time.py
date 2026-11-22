"""Measured-only longest root and peak simultaneous distinct roots."""
from dataclasses import dataclass

from src.cache.display_stats_time import StatsRootTime
from src.cache.display_usage_reader import USAGE_SLICE


@dataclass(slots=True)
class _RootScope:
    start: int
    root_ms: int = 0
    longest: int = 0
    longest_root: str | None = None
    peak: int = 0

    def finish_root(self, root):
        # Input order is lexicographic by root; an earlier tie stays selected.
        if self.root_ms > self.longest:
            self.longest_root, self.longest = root, self.root_ms
        self.root_ms = 0

    def result(self):
        if self.longest_root is not None:
            return StatsRootTime(self.longest_root, self.longest, self.peak)
        return None


class MeasuredRootTime:
    def __init__(self, db, scopes):
        self._db = db
        self._scopes = {period: _RootScope(start or 0) for period, start in scopes.items()}
        db.execute("""
            CREATE TABLE root_spans(root TEXT, start INTEGER, end INTEGER,
            PRIMARY KEY(root,start,end)) WITHOUT ROWID
        """)
        db.execute("CREATE TABLE edges(clock INTEGER PRIMARY KEY, delta INTEGER NOT NULL)")

    def stage(self, spans):
        self._db.executemany("INSERT OR IGNORE INTO root_spans VALUES(?,?,?)", spans)

    def reduce(self):
        yield from self._roots()
        yield from self._edges()

    def _roots(self):
        after, pending, current = ("", 0, 0), None, None
        while True:
            page = self._db.execute("""
                SELECT root,start,end FROM root_spans
                WHERE (root,start,end)>(?,?,?) ORDER BY root,start,end LIMIT ?
            """, (*after, USAGE_SLICE)).fetchall()
            if not page:
                break
            for root, left, right in page:
                if pending and root == current and left <= pending[1]:
                    pending = pending[0], max(right, pending[1])
                else:
                    if pending:
                        self._add_span(*pending)
                        if root != current:
                            self._finish_root(current)
                    current, pending = root, (left, right)
                yield True
            after = page[-1]
        if pending:
            self._add_span(*pending)
            self._finish_root(current)

    def _add_span(self, left, right):
        self._db.executemany("""
            INSERT INTO edges VALUES(?,?) ON CONFLICT(clock) DO UPDATE SET delta=delta+excluded.delta
        """, ((left, 1), (right, -1)))
        for scope in self._scopes.values():
            scope.root_ms += max(0, right - max(left, scope.start))

    def _finish_root(self, root):
        for scope in self._scopes.values():
            scope.finish_root(root)

    def _edges(self):
        active, after = 0, 0
        while True:
            page = self._db.execute("""
                SELECT clock,delta FROM edges WHERE clock>? ORDER BY clock LIMIT ?
            """, (after, USAGE_SLICE)).fetchall()
            if not page:
                return
            for clock, delta in page:
                # Apply the combined change only after scoring the half-open
                # segment. A simultaneous end/start cannot inflate concurrency.
                if active:
                    for scope in self._scopes.values():
                        if clock > max(after, scope.start):
                            scope.peak = max(scope.peak, active)
                active += delta
                after = clock
                yield True

    def rows(self):
        return {period: scope.result() for period, scope in self._scopes.items()}
