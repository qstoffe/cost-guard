"""Private scalar reference from complete global snapshots, independent of Watch.

Shares canonical lifecycle analysis, not optimized card acquisition, retained card
state, ranking/publication code, pricing or product cache. Callers own the reader.
Raw identities/revisions stay in memory; summary() is safe numeric evidence.
"""
from collections import Counter
from dataclasses import dataclass
import time

from src.analysis.causal import build_prompt_records, TOOL_CALLS_CONTINUATION_GRACE_MS
from src.sources.errors import SourceError


@dataclass(frozen=True, slots=True)
class RootFact:
    revision: str
    prompt_id: str | None
    finished_ms: int | None
    running: bool
    review_ms: int | None


def reduce_snapshot(snapshot, now_ms):
    records = build_prompt_records(snapshot, tracked_provider=None, now_ms=now_ms)
    representative = max((row for row in records if not row.in_progress),
        key=lambda row: (row.terminal_time_ms or 0,
            0 if row.terminal_time_ms else row.prompt_time_ms, row.prompt_id), default=None)
    # Conservative future canonical time boundary; no payload is retained to
    # reanalyze it later. Other source changes are revision-driven, never age proof.
    reviews = [row.completed_at_ms + TOOL_CALLS_CONTINUATION_GRACE_MS + 1
        for row in snapshot.messages if row.finish_reason == 'tool-calls'
        and row.completed_at_ms is not None
        and row.completed_at_ms + TOOL_CALLS_CONTINUATION_GRACE_MS >= now_ms]
    return RootFact(snapshot.source_revision, representative.prompt_id if representative else None,
        (representative.terminal_time_ms or None) if representative else None,
        any(row.in_progress for row in records), min(reviews, default=None))


class HistoryReference:
    def __init__(self, source, *, clock_ms=None):
        self.source = source
        self.clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self.facts, self.revisions = {}, {}
        self.epoch = None
        self.ready = False
        self.hydrated = self.epoch_invalidations = 0
        self.errors = Counter()

    def _epoch(self):
        refresh = getattr(self.source, 'refresh_observation_epoch', None)
        if callable(refresh):
            refresh()
        return self.source.observation_epoch

    def _catalog(self):
        sessions = self.source.list_sessions()
        roots = [row.session_id for row in sessions
            if row.parent_session_id is None and row.archived_at_ms is None]
        if len(set(roots)) != len(roots):
            raise RuntimeError('reference_duplicate_root')
        return dict(self.source.get_session_tree_revisions(roots))

    def _valid(self, key, revision, now):
        fact = self.facts.get(key)
        return (fact is not None and fact.revision == revision
            and (fact.review_ms is None or now < fact.review_ms))

    def _same_epoch(self):
        if self._epoch() == self.epoch and self.epoch is not None:
            return True
        self.facts.clear()
        self.ready = False
        self.epoch_invalidations += 1
        return False

    def refresh(self, *, deadline=None, progress=None):
        """One bounded-memory reconciliation pass; deadline only censors this probe."""
        self.ready = False
        before = self._catalog()
        epoch = self._epoch()
        if epoch is None:
            raise RuntimeError('reference_epoch_unavailable')
        if self.epoch is not None and epoch != self.epoch:
            self.facts.clear()
            self.epoch_invalidations += 1
        self.epoch = epoch
        self.revisions = before
        now = self.clock_ms()
        dirty = sorted(key for key, revision in before.items() if not self._valid(key, revision, now))
        for offset in range(0, len(dirty), 3):
            if deadline is not None and time.monotonic() >= deadline:
                return False
            keys = dirty[offset:offset + 3]
            try:
                snapshots = self.source.load_session_snapshots(keys)
            except SourceError as error:
                self.errors[str(error.code)] += len(keys)
                if error.terminal:
                    raise
                continue
            if not self._same_epoch():
                return False
            for key in keys:
                snapshot = snapshots.get(key)
                if snapshot is not None and snapshot.complete and snapshot.root.session_id == key:
                    self.facts[key] = reduce_snapshot(snapshot, self.clock_ms())
                    self.hydrated += 1
                else:
                    self.errors['incomplete_snapshot'] += 1
            # Drop the entire hydrated batch before the next read.
            del snapshots, snapshot
            if progress is not None:
                progress(self.summary())
        after = self._catalog()
        self.revisions = after
        self.facts = {key: fact for key, fact in self.facts.items() if key in after}
        if not self._same_epoch():
            return False
        now = self.clock_ms()
        self.ready = all(self._valid(key, revision, now) for key, revision in after.items())
        return self.ready

    def expected(self, *, mini=False):
        now = self.clock_ms()
        if not self.ready or not all(self._valid(key, revision, now) for key, revision in self.revisions.items()):
            return None
        eligible = [(key, fact.prompt_id, fact.finished_ms) for key, fact in self.facts.items()
            if fact.prompt_id is not None and not fact.running]
        newest = sorted(eligible, key=lambda row: (-(row[2] or 0), row[0]))[:5]
        ordered = tuple(sorted(newest, key=lambda row: (row[2] or 0, row[0], row[1])))
        return ordered[-3:] if mini else ordered

    def matches(self, proof):
        expected = self.expected()
        return bool(expected is not None and proof and proof['verified']
            and proof['epoch'] == self.epoch and proof['revisions'] == self.revisions
            and tuple(proof['rows']) == expected)

    def summary(self):
        now = self.clock_ms()
        valid = sum(self._valid(key, revision, now) for key, revision in self.revisions.items())
        return dict(roots=len(self.revisions), verified_scalars=valid,
            missing=len(self.revisions) - valid, hydrated_roots=self.hydrated,
            epoch_invalidations=self.epoch_invalidations, failures=dict(self.errors))
