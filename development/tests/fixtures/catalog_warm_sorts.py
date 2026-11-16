"""Owned 48-candidate Today cohort: 46 matches, one running, one old start-only."""
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone

from .synthetic_month import SyntheticMonthSource, make_root_snapshot

NOW = int(datetime(2026, 11, 16, 14, 30, tzinfo=timezone.utc).timestamp() * 1000)
DAY = 86_400_000


class WarmSortSource(SyntheticMonthSource):
    def __init__(self):
        super().__init__(48, 1, month_start_ms=NOW - 3 * 3_600_000, running_roots=1)
        self.reads = Counter()
        for index, snapshot in tuple(enumerate(self.snapshots.values())):
            if index == 1 or index >= 46:
                start = NOW - (14 * 60 + 25) * 60_000 if index == 1 else NOW - DAY
                snapshot = make_root_snapshot(index, 1, month_start_ms=start - index * 60_000)
            root = replace(snapshot.root, active=index == 0, updated_at_ms=NOW - 1000)
            if index == 1:
                snapshot = replace(snapshot, messages=(*snapshot.messages[:-1],
                    replace(snapshot.messages[-1], completed_at_ms=None, finish_reason=None)), invocations=())
            self.snapshots[root.session_id] = replace(snapshot, root=root, sessions=(root,), complete=True)

    def load_session_snapshot(self, session_id):
        self.reads[session_id] += 1
        return super().load_session_snapshot(session_id)

    def stream(self, sequence):
        snapshot = self.snapshots["root-0000"]
        root = replace(snapshot.root, updated_at_ms=NOW + sequence)
        self.snapshots[root.session_id] = replace(snapshot, root=root, sessions=(root,),
            invocations=tuple(replace(item, tokens=replace(item.tokens, output=1000 + sequence))
                for item in snapshot.invocations),
            source_revision=f"stream-{sequence}")

    def finish(self):
        from src.domain import TerminalEvidence, TerminalOutcome
        snapshot = self.snapshots["root-0000"]
        root = replace(snapshot.root, active=False, updated_at_ms=NOW)
        self.snapshots[root.session_id] = replace(snapshot, root=root, sessions=(root,),
            messages=(*snapshot.messages[:-1], replace(snapshot.messages[-1],
                termination=TerminalEvidence(NOW - 100, TerminalOutcome.SUCCESS))), source_revision="finished")
