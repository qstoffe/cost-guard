"""Process-local observed root history; source omissions are not deletion proof.

Never persists a ledger or inserts retained evidence into the shared source/cache.
Canonical identities replace observations, so a late request is valued once.
"""
from dataclasses import replace

from src.analysis.duration import accumulated_duration, execution_duration
from src.analysis.causal import TOOL_CALLS_CONTINUATION_GRACE_MS
from src.domain import MessageRole

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
    # Persisted attempt ends cannot be undone by a later omission of the idle
    # row. Keep them on that assistant identity; causal analysis still admits
    # newer assistant attempts, later tools and genuinely active children.
    ended = {(message.session_id, message.message_id): message.termination
        for message in previous.messages if message.termination is not None}
    fields["messages"] = tuple(replace(message, termination=ended[key])
        if (key := (message.session_id, message.message_id)) in ended
        and (message.termination is None or
            message.termination.completed_at_ms < ended[key].completed_at_ms)
        else message for message in fields["messages"])
    # Message-embedded parts must agree with the flat canonical parts collection.
    parts = {}
    for part in fields["parts"]:
        parts.setdefault((part.session_id, part.message_id), []).append(part)
    fields["messages"] = tuple(replace(message,
        parts=tuple(parts.get((message.session_id, message.message_id), message.parts)))
        for message in fields["messages"])
    return replace(current, **fields, complete=current.complete and not missing), missing


_LIFECYCLE_FIELDS = (
    "in_progress", "aborted", "watch_error", "completed_successfully", "abort_reason",
    "abort_time_ms", "terminal_time_ms", "duration_ms", "execution_duration_ms",
    "background_kinds", "background_started_ms", "background_only", "ended_after_tool_calls",
)


def analyze_observed(service, previous, fresh):
    """Retain usage, but derive execution from proven complete current evidence."""
    snapshot, retained = retain_snapshot(previous, fresh)
    bundle = service._analyze_snapshot(snapshot)
    if not retained or not fresh.complete:
        return snapshot, bundle, retained
    # Preserve durable ends on present attempts, never omitted live children,
    # tools or messages. Reuse causal analysis, not another lifecycle heuristic.
    messages = {(message.session_id, message.message_id): message for message in snapshot.messages}
    current_messages = tuple(replace(message,
        termination=messages[(message.session_id, message.message_id)].termination)
        for message in fresh.messages)
    present = {(message.session_id, message.message_id) for message in fresh.messages}
    ended_starts = tuple(message for key, message in messages.items() if key not in present
        and message.role is MessageRole.USER and message.termination is not None)
    ended_ids = {(message.session_id, message.message_id) for message in ended_starts}
    # A failed pre-response attempt has no assistant to carry its durable end.
    # Keep only that boundary, not omitted active tools/children or their status.
    current = replace(fresh, messages=current_messages + ended_starts,
        events=union(fresh.events, tuple(event for event in snapshot.events
            if (event.session_id, event.event_id) in ended_ids),
            lambda event: (event.session_id, event.event_id)))
    authoritative = service._analyze_snapshot(current)
    current_prompts = {record.prompt_id: record for record in authoritative.prompts}
    prompts = []
    for record in bundle.prompts:
        actual = current_prompts.get(record.prompt_id)
        if actual is not None:
            record = replace(record, **{name: getattr(actual, name) for name in _LIFECYCLE_FIELDS})
        elif record.in_progress:
            # Complete reclassification, e.g. zero-call/compaction. Keep history
            # without inventing a successful/failed outcome or end timestamp.
            record = replace(record, in_progress=False, aborted=False, watch_error=False,
                completed_successfully=False, abort_reason="", abort_time_ms=0,
                terminal_time_ms=0, execution_duration_ms=None, background_kinds=(),
                background_started_ms=0, background_only=False, ended_after_tool_calls=False)
        prompts.append(record)
    return snapshot, replace(bundle, prompts=tuple(prompts), cacheable=False), retained


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
        self.dependencies = None

    def acquire(self, service, session_id):
        root = service.root_for_session(session_id)
        if root is None:
            return None, "session_missing"
        dependencies = (root.provenance.source_generation, root.provenance.source_instance,
                        service._dependencies(service._load_catalog()),
                        service._load_comparison_catalog().analysis_signature)
        if self.dependencies is not None and self.dependencies != dependencies:
            self.__init__()  # Another source/config/price revision is not retained history.
        self.dependencies = dependencies
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
        # Analyze locally, not through the persistent derived cache: retained evidence
        # must never masquerade as a complete current source revision.
        snapshot, bundle, missing = analyze_observed(service, self.snapshot, fresh)
        item = AnalyzedRoot(root, bundle, False, snapshot)
        block = service._prompt_block(item, snapshot_running_metrics=True)
        observed = {event.event_id for event in fresh.events}
        previous = {row.event_id: row for row in self.report.prompt_blocks[0].rows} if self.report else {}
        row_observations = dict(self.row_observations)
        rows = []
        for row in block.rows:
            if row.event_id in observed:
                row_observations[row.event_id] = service.now_ms
            elif row.event_id in previous and not fresh.complete:
                old = previous[row.event_id]
                # Omitted evidence cannot advance execution time or prove an end.
                row = replace(row, duration_ms=old.duration_ms, in_progress=old.in_progress,
                              completed_at_ms=old.completed_at_ms, aborted=old.aborted,
                               completed_successfully=old.completed_successfully, watch_error=old.watch_error)
            if row.event_id in previous and not row.in_progress and row.completed_at_ms is None:
                old = previous[row.event_id]
                row = replace(row, duration_ms=(max(old.duration_ms or 0, service.now_ms - old.at_ms)
                    if old.in_progress else old.duration_ms))
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
