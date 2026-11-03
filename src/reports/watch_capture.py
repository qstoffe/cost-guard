"""Canonical prompt capture for Web cards; no acquisition loop or transport.

One isolated service reads/analyzes a root once, preserving causal and context
evidence for the focal row. No full-session aggregate projection is acquired.
"""
from dataclasses import dataclass, replace

from src.analysis.token_mix import MIX_FIELDS
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


def capture_rows(service, root, previous=None, focal_ids=()):
    fresh = service.source.load_session_snapshot(root.session_id)
    snapshot, bundle, retained = analyze_observed(service, previous, fresh)
    item = AnalyzedRoot(root, bundle, False, snapshot)
    projector = PromptRowProjector(snapshot=snapshot, bundle=bundle, catalog=service._load_catalog(),
        config=service.config, watch_duration=True, snapshot_running_metrics=True)
    records = sorted(bundle.prompts, key=lambda row: (row.prompt_time_ms, row.prompt_id))
    # One shared slice per session, including each concurrent focal prompt's
    # context and its preceding anchor for coherent CLI Watch deltas.
    selected = set(range(max(0, len(records) - 6), len(records)))
    for index, record in enumerate(records):
        if record.in_progress or record.prompt_id in focal_ids:
            selected.update(range(max(0, index - 5), index + 1))
    rows = []
    for index in sorted(selected):
        record = records[index]
        row = projector.prompt(record)
        # Completed CLI rows retain their historical rounding/coverage behavior.
        # Watch must not present missing categories as observed zero-token usage.
        if any(not set(MIX_FIELDS).issubset(entry.tokens.known_fields) for entry in record.entries):
            row = replace(row, token_mix_percent=None)
        rows.append(row)
    rows = _coherent_watch_deltas(rows, epochs=projector.epochs, session_id=root.session_id,
        subtask_ids=frozenset(record.prompt_id for record in records if record.prompt_kind == "subtask"))
    return WatchCapture(root.session_id, root.title or root.session_id, tuple(rows),
        max((record.prompt_time_ms for record in records), default=0), service.now_ms, retained,
        frozenset(event.event_id for event in fresh.events),
        card_context(projector, root.session_id, service._threshold_multiplier), fresh.complete), item
