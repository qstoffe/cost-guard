"""Two-phase canonical capture for Web cards; no acquisition loop or transport.

One isolated service reads/analyzes a root once. Recent rows are published before
the optional complete-session projection. Nothing sums the five displayed rows.
"""
from dataclasses import dataclass, replace

from src.reports.sampling import AnalyzedRoot
from src.reports.session_history import retain_snapshot
from .prompt_rows import PromptRowProjector
from .prompts import _coherent_watch_deltas


@dataclass(frozen=True, slots=True)
class WatchCapture:
    session_id: str
    title: str
    rows: tuple
    latest_ms: int
    observed_at_ms: int
    retained: bool = False
    observed_ids: frozenset = frozenset()


def capture_rows(service, root, previous=None, focal_ids=()):
    fresh = service.source.load_session_snapshot(root.session_id)
    snapshot, retained = retain_snapshot(previous, fresh)
    bundle = service._analyze_snapshot(snapshot)
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
    rows = [projector.prompt(records[index]) for index in sorted(selected)]
    rows = _coherent_watch_deltas(rows, epochs=projector.epochs, session_id=root.session_id,
        subtask_ids=frozenset(record.prompt_id for record in records if record.prompt_kind == "subtask"))
    return WatchCapture(root.session_id, root.title or root.session_id, tuple(rows),
        max((record.prompt_time_ms for record in records), default=0), service.now_ms, retained,
        frozenset(event.event_id for event in fresh.events)), item


def capture_totals(service, item):
    # This exact full-history owner includes compaction, child attribution and
    # accumulated_duration's overlap-safe interval union. Discard its large rows.
    return replace(service._prompt_block(item, snapshot_running_metrics=True), rows=())
