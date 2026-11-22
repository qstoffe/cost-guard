"""Bounded local preparation of period-specific Stats request populations."""
import sqlite3
from collections import deque
from contextlib import AbstractContextManager
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from src.analysis.ai_stats import windows
from src.cache.display_usage_reader import USAGE_SLICE

from .archive_exact_cost import ExactCost


class PopulationState(Enum):
    MORE = "more"
    STALE = "stale"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class PopulationObservation:
    tokens: int | None
    usage_gap: bool
    ccost: Decimal | None
    pricing: str | None  # A proved zero-usage/request cost has no price dependency.
    subagent: bool

    @classmethod
    def decode(cls, tokens, gap, ccost, pricing, subagent):
        return cls(int(tokens) if tokens is not None else None, bool(gap),
                   Decimal(ccost) if ccost is not None else None, pricing, bool(subagent))


@dataclass(frozen=True, slots=True)
class PopulationPage:
    keys: tuple[bytes, ...]
    observations: tuple[PopulationObservation, ...]
    next_cursor: bytes | None


_STAGE = """
    CREATE TABLE roots (
        id TEXT PRIMARY KEY, last_end INTEGER, missing_recipe INTEGER NOT NULL DEFAULT 0
    ) WITHOUT ROWID;
    CREATE INDEX roots_missing_recipe ON roots(last_end) WHERE missing_recipe=1;
    CREATE TABLE candidates (
        key BLOB PRIMARY KEY, root TEXT NOT NULL, session TEXT NOT NULL,
        clock INTEGER, ordinal INTEGER NOT NULL, message BLOB NOT NULL,
        slot BLOB NOT NULL, fork BLOB, observed TEXT, usage_gap INTEGER NOT NULL, ccost TEXT, pricing TEXT
    ) WITHOUT ROWID;
    CREATE TABLE eligible (
        period TEXT NOT NULL, key BLOB NOT NULL, message BLOB NOT NULL, slot BLOB NOT NULL,
        PRIMARY KEY(period,key)
    ) WITHOUT ROWID;
    CREATE INDEX eligible_slot ON eligible(period,message,slot);
    CREATE TABLE trees (
        period TEXT NOT NULL, fork BLOB NOT NULL, root TEXT NOT NULL, count INTEGER NOT NULL,
        ordinal INTEGER NOT NULL, session TEXT NOT NULL,
        PRIMARY KEY(period,fork,root)
    ) WITHOUT ROWID;
    CREATE INDEX winners ON trees(period,fork,count DESC,ordinal,session,root);
    CREATE TABLE reconciled (
        period TEXT NOT NULL, key BLOB NOT NULL, PRIMARY KEY(period,key)
    ) WITHOUT ROWID;
    CREATE TABLE accepted (
        period TEXT NOT NULL, key BLOB NOT NULL, PRIMARY KEY(period,key)
    ) WITHOUT ROWID;
"""
_INTERVAL_PAGES_PER_TURN = 8


class ArchiveStatsPopulation(AbstractContextManager):
    """Stage keys only; this cannot publish a total or claim source coverage.

    For a period, proven-old roots are excluded first, then step/message
    reconciliation and fork ranking run on the remaining roots. Event-time
    filtering is last, even when the excluded event is a newer step.
    """

    def __init__(self, source, zone, now_ms):
        self.source, self.now_ms = source, now_ms
        self.scopes = dict(windows(zone, now_ms))
        self.version = None
        self.next_completion = None
        self._gaps = set()
        self._ready = False
        self._db = sqlite3.connect("")
        try:
            self._db.execute("PRAGMA cache_size=-512")
            self._db.executescript(_STAGE)
            self._turns = self._prepare()
            next(self._turns)
        except BaseException:
            self.close()
            raise

    def step(self, history, *, eligible):
        if self._db is None or self._ready:
            raise RuntimeError("stats_population_not_preparing")
        try:
            if eligible():
                with self._db:
                    state = self._turns.send(history)
                if state is PopulationState.MORE:
                    return state
                if state is PopulationState.READY and eligible():
                    self._ready = True
                    return state
        except BaseException:
            self.close()
            raise
        self.close()
        return PopulationState.STALE

    @property
    def gaps(self):
        return frozenset(self._gaps)

    def page(self, period, *, after=None):
        if not self._ready or self._db is None or period not in self.scopes:
            raise ValueError("stats_population_not_available")
        rows = self._db.execute("""
            SELECT a.key,c.observed,c.usage_gap,c.ccost,c.pricing,c.session<>c.root FROM accepted AS a
            CROSS JOIN candidates AS c ON c.key=a.key
            WHERE a.period=? AND a.key>? ORDER BY a.key LIMIT ?
        """, (period, after or b"", USAGE_SLICE + 1)).fetchall()
        entries = rows[:USAGE_SLICE]
        keys = tuple(row[0] for row in entries)
        observations = tuple(PopulationObservation.decode(*row[1:]) for row in entries)
        return PopulationPage(keys, observations, keys[-1] if len(rows) > USAGE_SLICE else None)

    def close(self):
        if hasattr(self, "_turns"):
            self._turns.close()
        if self._db is not None:
            self._db.close()
            self._db = None

    def __exit__(self, *exc):
        self.close()

    def _prepare(self):
        history = yield
        roots, root_after, interval_after = deque(), None, None
        while True:
            evidence = history.stats_roots(self.source, expected=self.version, after=root_after)
            if evidence is None:
                yield PopulationState.STALE
                return
            self.version = evidence.version
            root_after = evidence.next_cursor
            roots.extend(evidence.roots)
            self._db.executemany("INSERT INTO roots(id,last_end) VALUES(?,?)",
                                 ((row.root, None if row.usage_pending else 0) for row in roots))
            history = yield PopulationState.MORE
            while roots:
                for _ in range(_INTERVAL_PAGES_PER_TURN):
                    root = roots[0].root
                    batch = history.stats_intervals(self.source, root, expected=self.version, after=interval_after)
                    if batch is None:
                        yield PopulationState.STALE
                        return
                    self._extend_root(root, _page_end(batch.intervals))
                    interval_after = batch.next_cursor
                    if interval_after is None:
                        roots.popleft()
                        if not roots:
                            break
                history = yield PopulationState.MORE
            if root_after is None:
                break

        after = None
        while True:
            batch = history.stats_candidates(self.source, expected=self.version, after=after)
            if batch is None:
                yield PopulationState.STALE
                return
            for candidate in batch.entries:
                self._stage(candidate)
            after = batch.next_cursor
            history = yield PopulationState.MORE
            if after is None:
                break

        self._record_recipe_gaps()
        yield from self._admit_roots()
        yield from self._reconcile_messages()
        yield from self._select_forks()
        # The commit owner must independently check this pin inside its write
        # transaction. A final read prevents handing out a known-obsolete page.
        history = yield PopulationState.MORE
        valid = history.stats_version(self.source, expected=self.version) is not None
        yield PopulationState.READY if valid else PopulationState.STALE

    def _extend_root(self, root, end):
        # SQLite scalar max propagates NULL: unknown never proves outside.
        return self._db.execute("UPDATE roots SET last_end=max(last_end,?) WHERE id=?", (end, root)).rowcount

    def _stage(self, candidate):
        usage = candidate.usage
        if usage.clock_ms is not None and usage.clock_ms > self.now_ms:
            if self.next_completion is None or usage.clock_ms < self.next_completion:
                self.next_completion = usage.clock_ms
        if candidate.tree is None or not self._extend_root(candidate.tree, usage.clock_ms):
            self._gaps.update(self.scopes)
            return
        if candidate.identity is None:
            # A missing, undated or out-of-window request can still be a step
            # replacing a fallback if the entire root cannot be excluded.
            self._db.execute("UPDATE roots SET missing_recipe=1 WHERE id=?", (candidate.tree,))
            return
        recipe = candidate.identity
        known = usage.known & 0b1111
        observed = sum(volume for index, volume in enumerate(usage.tokens[:4]) if known & (1 << index))
        if known & 0b1000:
            observed += usage.tokens[4]  # Canonical observed Stats output includes reasoning once.
        ccost, pricing = _reference_cost(usage, known)
        self._db.execute("INSERT INTO candidates VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (
            usage.request_key, candidate.tree, usage.session_id, usage.clock_ms, candidate.ordinal,
            recipe.message_key, recipe.step_key or b"", candidate.fork, str(observed) if known else None,
            known != 0b1111, ccost, pricing))

    def _record_recipe_gaps(self):
        missing = "SELECT last_end FROM roots INDEXED BY roots_missing_recipe WHERE missing_recipe=1"
        undated = self._db.execute(missing + " AND last_end IS NULL LIMIT 1").fetchone()
        if undated:
            self._gaps.update(self.scopes)
            return
        latest = self._db.execute(missing + " ORDER BY last_end DESC LIMIT 1").fetchone()
        if latest:
            self._gaps.update(period for period, start in self.scopes.items()
                              if start is None or latest[0] >= start)

    def _candidate_pages(self):
        after = b""
        while rows := self._db.execute("""
            SELECT key,message,slot,root.last_end FROM candidates AS candidate
            CROSS JOIN roots AS root ON root.id=candidate.root
            WHERE key>? ORDER BY key LIMIT ?
        """, (after, USAGE_SLICE)).fetchall():
            yield rows
            after = rows[-1][0]

    def _admit_roots(self):
        for page in self._candidate_pages():
            self._db.executemany("INSERT INTO eligible VALUES(?,?,?,?)", (
                (period, key, message, slot)
                for key, message, slot, end in page
                for period, start in self.scopes.items()
                if start is None or end is None or end >= start))
            yield PopulationState.MORE

    def _reconcile_messages(self):
        after = ("", b"")
        while rows := self._db.execute("""
            SELECT period,e.key,e.message,e.slot,c.fork,c.root,c.ordinal,c.session
            FROM eligible AS e CROSS JOIN candidates AS c ON c.key=e.key
            WHERE (period,e.key)>(?,?) ORDER BY period,e.key LIMIT ?
        """, (*after, USAGE_SLICE)).fetchall():
            for period, key, message, slot, fork, root, ordinal, session in rows:
                if not slot and self._db.execute("""
                    SELECT 1 FROM eligible WHERE period=? AND message=? AND slot>? LIMIT 1
                """, (period, message, b"")).fetchone():
                    continue
                aliases = self._db.execute("""
                    SELECT key FROM eligible WHERE period=? AND message=? AND slot=? LIMIT 2
                """, (period, message, slot)).fetchall()
                if len(aliases) > 1:
                    # These physical facts share a logical slot. Deriving a
                    # new merged token vector/fork from opaque keys is unsafe.
                    self._gaps.add(period)
                    continue
                self._db.execute("INSERT INTO reconciled VALUES(?,?)", (period, key))
                if fork is not None:
                    self._rank_tree(period, fork, root, ordinal, session)
            after = rows[-1][:2]
            yield PopulationState.MORE

    def _rank_tree(self, period, fork, root, ordinal, session):
        self._db.execute("""
            INSERT INTO trees VALUES(?,?,?,1,?,?)
            ON CONFLICT(period,fork,root) DO UPDATE SET count=count+1,
                ordinal=CASE WHEN (excluded.ordinal,excluded.session)<(ordinal,session)
                             THEN excluded.ordinal ELSE ordinal END,
                session=CASE WHEN (excluded.ordinal,excluded.session)<(ordinal,session)
                             THEN excluded.session ELSE session END
        """, (period, fork, root, ordinal, session))

    def _select_forks(self):
        after = ("", b"")
        while rows := self._db.execute("""
            SELECT r.period,r.key,c.root,c.fork,c.clock
            FROM reconciled AS r CROSS JOIN candidates AS c ON c.key=r.key
            WHERE (r.period,r.key)>(?,?) ORDER BY r.period,r.key LIMIT ?
        """, (*after, USAGE_SLICE)).fetchall():
            for period, key, root, fork, clock in rows:
                start = self.scopes[period]
                if clock is None:
                    self._gaps.add(period)
                    continue
                if clock > self.now_ms or start is not None and clock < start:
                    continue
                if fork is not None and not self._wins(period, fork, root):
                    continue
                self._db.execute("INSERT INTO accepted VALUES(?,?)", (period, key))
            after = rows[-1][:2]
            yield PopulationState.MORE

    def _wins(self, period, fork, root):
        rows = self._db.execute("""
            SELECT root, count, ordinal, session FROM trees WHERE period=? AND fork=?
            ORDER BY count DESC,ordinal,session,root LIMIT 2
        """, (period, fork)).fetchall()
        if len(rows) == 2 and rows[0][1:] == rows[1][1:]:
            # The original insertion order is not evidenced for an exact tie.
            self._gaps.add(period)
            return False
        return rows[0][0] == root


def _page_end(intervals):
    end = 0
    for interval in intervals:
        if (interval.start_ms is None or interval.start_ms <= 0 or interval.duration_ms is None
                or interval.duration_ms < 0 or interval.provisional):
            return None
        end = max(end, interval.start_ms + interval.duration_ms)
        if end >= 1 << 63:
            return None
    return end


def _reference_cost(usage, known):
    if known == 0b1111 and not any(usage.tokens):
        return "0", None
    if usage.category_costs is None or not usage.pricing:
        return None, None
    amount = ExactCost()
    for value in usage.category_costs:
        amount.add(value)
    return str(amount.amount()), usage.pricing
