"""Canonical prompt capture for Web cards; no acquisition loop or transport.

One isolated service reads/analyzes a root once, preserving causal and context
evidence for the focal row. Fresh source evidence is handed off for independent
incremental session-cost work; no aggregate blocks this row publication.
"""
from dataclasses import dataclass, replace

from src.analysis.session_activity import activity_fields
from src.domain import EventKind
from src.reports.sampling import AnalyzedRoot
from .session_history import analyze_observed
from .prompt_rows import PromptRowProjector
from .prompts import _coherent_watch_deltas
from .watch_context import card_context


@dataclass(frozen=True, slots=True)
class WatchCapture:
    session_id: str
    title: str
    rows: tuple
    latest_ms: int
    observed_at_ms: int
    retained: bool = False
    observed_ids: frozenset = frozenset()
    context: object = None
    authoritative: bool = False
    cost_snapshot: object = None
    context_handoffs: tuple = ()
    duration_intervals: tuple = ()
    context_comparable_ids: frozenset = frozenset()
    catalog_prompt: tuple | None = None
    catalog_prompt_ends: frozenset = frozenset()

    @property
    def history_row(self):
        """Latest supported finish; unknown endings fill spare history slots only."""
        terminal = [row for row in self.rows if not row.in_progress]
        return max(terminal, key=lambda row: (row.completed_at_ms or 0,
            0 if row.completed_at_ms else row.at_ms, row.event_id), default=None)


def mini_context_handoffs(projector, rows):
    """Authorize display continuity only before a comparable first root request.

    The browser must already have displayed this exact source-owned predecessor
    value. This neither supplies an estimate nor changes Full Watch arithmetic.
    An unbound new model is pending, not proof of a model change; known identity
    conflicts and explicit boundaries retire the predecessor immediately.
    """
    records = projector.bundle.prompts
    by_id = {row.event_id: row for row in rows}
    handoffs = []
    for current in records:
        row = by_id.get(current.prompt_id)
        prior = current.pre_prompt_entry
        if (row is None or row.watch_next_context_tokens is not None or not current.in_progress
                or current.execution_unverified or current.aborted or current.watch_error
                or current.prompt_kind == 'subtask' or prior is None
                or any(entry.session_id == current.session_id for entry in current.entries)
                or projector.epochs.active_prompt(current) is not True
                or projector.epochs.active_entry(prior) is not True
                or (current.main_model_id and current.main_model_id != prior.model.model)
                or (current.main_provider_id and current.main_provider_id != prior.model.provider)
                or projector.epochs.retired(current.session_id, prior.completed_at_ms)
                or any(item.session_id == current.session_id and item.kind is EventKind.COMPACTION
                       and item.created_at_ms >= prior.completed_at_ms for item in projector.snapshot.events)):
            continue
        previous = next((item for item in records if item.last_root_entry == prior), None)
        before = by_id.get(previous.prompt_id) if previous is not None else None
        if (before is not None and previous.session_id == current.session_id
                and not before.execution_unverified and not before.aborted
                and not before.watch_error and before.watch_next_context_tokens is not None):
            handoffs.append((current.prompt_id, (previous.prompt_id, before.watch_next_context_tokens)))
    return tuple(handoffs)


def running_context_rows(rows, context, comparable_ids):
    """Join only proven same-prompt operands, including a retained footer."""
    return tuple(replace(row, watch_delta_context_tokens=(
        context.tokens - row.incoming_context_tokens
        if context is not None and context.owner_id == row.event_id
        and context.context_state != 'invalidated' and context.tokens is not None
        and row.event_id in comparable_ids and row.incoming_context_tokens is not None else None))
        if row.in_progress else row for row in rows)


def capture_rows(service, root, previous=None, focal_ids=(), *, fresh=None, defer_guidance=False):
    if fresh is None:
        fresh = service.source.load_session_snapshot(root.session_id)
    snapshot, bundle, retained = analyze_observed(service, previous, fresh)
    item = AnalyzedRoot(root, bundle, False, snapshot)
    projector = PromptRowProjector(snapshot=snapshot, bundle=bundle, catalog=service._load_catalog(),
        config=service.config, watch_duration=True, snapshot_running_metrics=True)
    records = sorted(bundle.prompts, key=lambda row: (row.prompt_time_ms, row.prompt_id))
    # One shared slice per session, including each concurrent focal prompt's
    # context and its preceding anchor for coherent CLI Watch deltas.
    selected = set(range(max(0, len(records) - 6), len(records)))
    finished = [(record.terminal_time_ms, record.prompt_id, index)
        for index, record in enumerate(records) if not record.in_progress and record.terminal_time_ms]
    if finished:
        index = max(finished)[-1]
        selected.update(range(max(0, index - 5), index + 1))
    for index, record in enumerate(records):
        if record.in_progress or record.prompt_id in focal_ids:
            selected.update(range(max(0, index - 5), index + 1))
    rows = []
    for index in sorted(selected):
        record = records[index]
        row = projector.prompt(record)
        rows.append(row)
    rows = _coherent_watch_deltas(rows, epochs=projector.epochs, session_id=root.session_id,
        subtask_ids=frozenset(record.prompt_id for record in records if record.prompt_kind == "subtask"))
    signature = ''
    if defer_guidance:
        from .context_guidance import guidance_semantics
        signature = guidance_semantics(service, projector.catalog, service._load_comparison_catalog())
    context = card_context(projector, root.session_id, service._threshold_multiplier,
        defer_guidance=defer_guidance, guidance_signature=signature,
        source_epoch=(getattr(service.source, 'observation_epoch', None) or '') if defer_guidance else '')
    by_id = {record.prompt_id: record for record in records}
    comparable_ids = set()
    for row in rows:
        record = by_id[row.event_id]
        first = next((entry for entry in record.entries if entry.session_id == root.session_id), None)
        comparable = (row.in_progress and not row.execution_unverified and context.owner_id == row.event_id
            and context.context_state != 'invalidated'
            and row.incoming_context_tokens is not None and first is not None
            and projector.epochs.active_prompt(record) is not False and projector.epochs.active_entry(first) is not False
            and not projector.epochs.crossed(root.session_id, record.prompt_time_ms, None)
            and not any(item.session_id == root.session_id and item.created_at_ms >= record.prompt_time_ms
                for item in bundle.compactions)
            and context.context_provider == first.model.provider and context.context_model == first.model.model)
        if comparable:
            comparable_ids.add(row.event_id)
    rows = running_context_rows(rows, context, comparable_ids)
    # Same overlap/dedup semantics as Sessions, over the entire analyzed root,
    # not the six-row card slice. Reuse these intervals for clock-only ticks.
    intervals = (tuple((record.prompt_time_ms, record.execution_duration_ms, record.in_progress)
        for record in bundle.prompts) + tuple((record.created_at_ms, record.duration_ms, False)
                 for record in bundle.compactions)) if fresh.complete else ()
    catalog_prompt = None
    ended = set()
    if fresh.complete:
        # The display may retain old rows, but only the fresh tree can bind
        # current execution. analyze_observed already requalifies the records.
        activity = activity_fields(AnalyzedRoot(root, bundle, False, fresh),
                                   on_prompt_ends=ended.update if not retained else None)
        if activity['running']:
            catalog_prompt = (activity['activity_prompt_id'], activity['prompt_started_ms'])
    return WatchCapture(root.session_id, root.title or root.session_id, tuple(rows),
        max((record.prompt_time_ms for record in records), default=0), service.now_ms, retained,
        frozenset(event.event_id for event in fresh.events),
        context, fresh.complete, fresh,
        mini_context_handoffs(projector, rows) if fresh.complete and not retained else (),
        intervals, frozenset(comparable_ids), catalog_prompt, frozenset(ended)), item
