"""Process-local observed root history; source omissions are not deletion proof.

Never persists a ledger or inserts retained evidence into the shared source/cache.
Canonical identities replace observations, so a late request is valued once.
"""
from dataclasses import replace

from src.analysis.duration import accumulated_duration, execution_duration
from src.analysis.causal import TOOL_CALLS_CONTINUATION_GRACE_MS

from .sampling import AnalyzedRoot


def union(previous, current, key):
    values = {key(item): item for item in previous}
    values.update((key(item), item) for item in current)
    return tuple(values.values())


def retain_snapshot(previous, current):
    if previous is None:
        return current, False
    fields = {}
    missing = False
    identities = {"sessions": "session_id", "messages": "message_id", "parts": "part_id",
                  "events": "event_id", "invocations": "invocation_id",
                  "context_boundaries": "boundary_id", "background": "activity_id"}
    for name, attribute in identities.items():
        key = lambda item: (item.session_id, getattr(item, attribute))
        old, new = getattr(previous, name), getattr(current, name)
        missing |= bool({key(item) for item in old} - {key(item) for item in new})
        fields[name] = union(old, new, key)
    # Message-embedded parts must agree with the flat canonical parts collection.
    parts = {}
    for part in fields["parts"]:
        parts.setdefault((part.session_id, part.message_id), []).append(part)
    fields["messages"] = tuple(replace(message,
        parts=tuple(parts.get((message.session_id, message.message_id), message.parts)))
        for message in fields["messages"])
    return replace(current, **fields), missing


class SessionHistory:
    def __init__(self):
        self.snapshot = None
        self.revision = None
        self.report = None
        self.retained = False
        self.running = False
        self.row_observations = {}
        self.omitted_ids = frozenset()
        self.fresh_snapshot = None
        self.lifecycle_due_ms = 2**63

    def acquire(self, service, session_id):
        root = service.root_for_session(session_id)
        if root is None:
            return None, "session_missing"
        revision = service.source.get_session_tree_revision(root.session_id)
        if self.report is not None and revision == self.revision and not self.running and root.active is not True:
            return self.report, ("archived" if root.archived_at_ms is not None else
                                 "history_retained" if self.retained else "observed")
        fresh = service.source.load_session_snapshot(root.session_id)
        if fresh == self.fresh_snapshot and service.now_ms < self.lifecycle_due_ms:
            # Identical running evidence needs only the shared execution clock,
            # not attribution, token/context projection or reference valuation.
            old = self.report.prompt_blocks[0]
            rows = tuple(replace(row, duration_ms=execution_duration(row.at_ms, service.now_ms))
                if row.in_progress and row.event_id not in self.omitted_ids else row for row in old.rows)
            block = replace(old, rows=rows,
                            duration_ms=accumulated_duration((row.at_ms, row.duration_ms) for row in rows))
            self.report = replace(self.report, prompt_blocks=(block,))
            return self.report, "history_retained" if self.retained else "observed"
        snapshot, missing = retain_snapshot(self.snapshot, fresh)
        # Analyze locally, not through the persistent derived cache: retained evidence
        # must never masquerade as a complete current source revision.
        bundle = service._analyze_snapshot(snapshot)
        item = AnalyzedRoot(root, bundle, False, snapshot)
        block = service._prompt_block(item, snapshot_running_metrics=True)
        observed = {event.event_id for event in fresh.events}
        previous = {row.event_id: row for row in self.report.prompt_blocks[0].rows} if self.report else {}
        row_observations = dict(self.row_observations)
        rows = []
        for row in block.rows:
            if row.event_id in observed:
                row_observations[row.event_id] = service.now_ms
            elif row.event_id in previous:
                old = previous[row.event_id]
                # Omitted evidence cannot advance execution time or prove an end.
                row = replace(row, duration_ms=old.duration_ms, in_progress=old.in_progress,
                              completed_at_ms=old.completed_at_ms, aborted=old.aborted,
                              completed_successfully=old.completed_successfully, watch_error=old.watch_error)
            rows.append(row)
        block = replace(block, rows=tuple(rows),
                        duration_ms=accumulated_duration((row.at_ms, row.duration_ms) for row in rows))
        self.snapshot = snapshot
        self.fresh_snapshot = fresh
        self.lifecycle_due_ms = min((message.completed_at_ms + TOOL_CALLS_CONTINUATION_GRACE_MS + 1
            for message in fresh.messages if message.finish_reason == "tool-calls"
            and message.completed_at_ms is not None
            and message.completed_at_ms + TOOL_CALLS_CONTINUATION_GRACE_MS + 1 > service.now_ms), default=2**63)
        self.row_observations = row_observations
        self.omitted_ids = frozenset(row.event_id for row in rows if row.event_id not in observed)
        self.revision = revision
        self.retained = missing
        self.running = any(row.in_progress and row.event_id in observed for row in block.rows)
        self.report = service.session_detail_projection(session_id, root, block)
        return self.report, ("archived" if root.archived_at_ms is not None else
                             "history_retained" if missing else "observed")
