"""Batch V2 message acquisition bracketed by authoritative catalog revisions."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Sequence

from src.domain import SessionSnapshot
from .errors import SourceConcurrentChangeError, SourceDataError
from .opencode_v2_catalog import V2CatalogIndex
from .opencode_v2_events import normalize_event
from .opencode_v2_normalization import normalize_request_invocations

if TYPE_CHECKING:
    from .opencode_v2 import OpenCodeV2Source, _NativeSession


def _read_tree(source: OpenCodeV2Source, tree: Sequence[_NativeSession], root_id: str,
               revision: str) -> SessionSnapshot:
    messages, parts, boundaries, background, contexts = [], [], [], [], []
    notices: set[str] = set()
    for native in tree:
        native_messages, native_parts, native_boundaries, native_background, native_notices, context = source._load_messages(native)
        messages.extend(native_messages)
        parts.extend(native_parts)
        boundaries.extend(native_boundaries)
        background.extend(native_background)
        notices.update(native_notices)
        if context is not None:
            contexts.append(context)
    sessions = tuple(source._normalize_session(item) for item in tree)
    events = tuple(event for message in messages
                   if (event := normalize_event(message, frozenset(notices))) is not None)
    invocations = normalize_request_invocations(messages, source._provenance)
    invocations.sort(key=lambda value: (
        value.completed_at_ms if value.completed_at_ms is not None else value.created_at_ms, value.invocation_id))
    return SessionSnapshot(
        root=next(value for value in sessions if value.session_id == root_id), sessions=sessions,
        messages=tuple(sorted(messages, key=lambda value: (value.created_at_ms, value.message_id))),
        parts=tuple(sorted(parts, key=lambda value: (value.message_id, value.created_at_ms, value.part_id))),
        events=events, invocations=tuple(invocations), source_revision=revision,
        context_boundaries=tuple(boundaries), background=tuple(background), active_contexts=tuple(contexts),
    )


def load_snapshots(source: OpenCodeV2Source, root_ids: Sequence[str]) -> dict[str, SessionSnapshot]:
    """Share brackets, not weakened proofs: every returned tree is equal before/after its messages.

    Unstable trees alone retry; a reused bracket does not consume either fresh
    attempt. Events may invalidate the shared hint but never the local brackets.
    """
    pending = tuple(dict.fromkeys(root_ids))
    complete: dict[str, SessionSnapshot] = {}
    reuse = True
    attempts = 0
    while pending and attempts < 2:
        source._diagnostics["last_snapshot_stage"] = "catalog_before"
        before, reused = source._catalog_before_messages(pending[0], allow_reuse=reuse)
        index = source._catalog_index or V2CatalogIndex(before)
        revisions = {root_id: index.revision(root_id, source._revision) for root_id in pending}
        source._diagnostics["last_snapshot_stage"] = "messages"
        with source.metrics.measure("hydration"):
            snapshots = {root_id: _read_tree(source, index.tree(root_id), root_id, revisions[root_id]) for root_id in pending}
        source.metrics.add("hydrated_roots", len(pending))
        source._diagnostics["last_snapshot_stage"] = "catalog_after"
        after_values = source._list_native_sessions(refresh=True)
        after = source._catalog_index or V2CatalogIndex(after_values)
        unstable = []
        for root_id in pending:
            if root_id not in after.by_id:
                raise SourceConcurrentChangeError("OpenCode V2 session changed while it was being read",
                                                  phase="snapshot", generation="v2")
            revision = after.revision(root_id, source._revision)
            if revision == revisions[root_id]:
                complete[root_id] = replace(snapshots[root_id], source_revision=revision)
            else:
                unstable.append(root_id)
        pending = tuple(unstable)
        if reused:
            reuse = False
            source._diagnostics["snapshot_catalog_reuse_misses"] += bool(pending)
        else:
            attempts += 1
            source._diagnostics["snapshot_revision_rechecks"] += bool(pending)
        reuse = False  # any mismatch requires fresh before AND after brackets
    if pending:
        source._diagnostics["last_snapshot_stage"] = "revision_changed"
        raise SourceConcurrentChangeError("OpenCode V2 session changed repeatedly while it was being read",
                                          phase="snapshot", generation="v2")
    source._diagnostics["last_snapshot_stage"] = "complete"
    return complete
