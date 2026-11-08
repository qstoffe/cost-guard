"""Batch V2 message acquisition bracketed by authoritative catalog revisions."""
from __future__ import annotations

from dataclasses import replace
from concurrent.futures import CancelledError, FIRST_COMPLETED, ThreadPoolExecutor, wait
from threading import Event
from typing import TYPE_CHECKING, Sequence

from src.domain import SessionSnapshot
from .errors import FailureCode, SourceConcurrentChangeError, SourceDataError, SourceError, SourceSnapshotMemberError
from .opencode_v2_catalog import V2CatalogIndex
from .opencode_v2_events import normalize_event
from .opencode_v2_normalization import normalize_request_invocations

if TYPE_CHECKING:
    from .opencode_v2 import OpenCodeV2Source, _NativeSession


def _read_tree(source: OpenCodeV2Source, tree: Sequence[_NativeSession], root_id: str,
               revision: str, stopped: Event | None = None) -> SessionSnapshot:
    messages, parts, boundaries, background, contexts = [], [], [], [], []
    notices: set[str] = set()
    for native in tree:
        if stopped is not None and stopped.is_set():
            raise CancelledError()
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


def _read_trees(source, index, pending, revisions, *, workers, progress, failures=None, on_root=None, identify_members=False):
    """At most four submitted trees; join all owned reads, including failure paths."""
    snapshots = {}
    def accept(root_id, read):
        try:
            snapshots[root_id] = read()
        except SourceError as error:
            if identify_members:
                raise SourceSnapshotMemberError(root_id, error) from error
            if failures is None or error.code in {
                    FailureCode.AUTH, FailureCode.VERSION, FailureCode.REGISTRATION_INVALID,
                    FailureCode.REGISTRATION_MISSING, FailureCode.REGISTRATION_UNREADABLE}:
                raise
            failures[root_id] = error
        if on_root is not None:
            on_root(root_id)

    if failures is None and (workers == 1 or len(pending) == 1):
        for root_id in pending:
            accept(root_id, lambda: _read_tree(source, index.tree(root_id), root_id, revisions[root_id]))
            progress('messages', len(snapshots), len(pending))
        return snapshots
    stopped = Event()
    roots = iter(pending)
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='cost-guard-v2-history') as pool:
        active = {}

        def submit():
            root_id = next(roots, None)
            if root_id is not None:
                future = pool.submit(_read_tree, source, index.tree(root_id), root_id, revisions[root_id], stopped)
                active[future] = root_id

        try:
            for _ in range(min(workers, len(pending))):
                submit()
            while active:
                finished, _ = wait(active, timeout=.1, return_when=FIRST_COMPLETED)
                if not finished:
                    progress('messages', len(snapshots), len(pending))
                for future in finished:
                    root_id = active.pop(future)
                    accept(root_id, future.result)
                    progress('messages', len(snapshots), len(pending))
                for _ in finished:
                    submit()
        finally:
            stopped.set()
            for future in active:
                future.cancel()
    return snapshots


def global_bracket(source, root_ids, *, allow_reuse, failures=None):
    """Return the exact complete-global index for this observation, explicitly."""
    values, reused = source._catalog_before_messages(root_ids[0], allow_reuse=allow_reuse)
    return source._catalog_index or V2CatalogIndex(values), reused


def load_snapshots(source: OpenCodeV2Source, root_ids: Sequence[str], *, workers: int = 1,
                    progress=None, available_only: bool = False, failures=None, on_root=None,
                    identify_members: bool = False, brackets=None) -> dict[str, SessionSnapshot]:
    """Share brackets, not weakened proofs: every returned tree is equal before/after its messages.

    Unstable trees alone retry; a reused bracket does not consume either fresh
    attempt. Events may invalidate the shared hint but never the local brackets.
    """
    pending = tuple(dict.fromkeys(root_ids))
    progress = progress or (lambda _stage, _completed, _total: None)
    complete: dict[str, SessionSnapshot] = {}
    bracket = brackets or (lambda roots, **options: global_bracket(source, roots, **options))
    reuse = True
    attempts = 0
    while pending and attempts < 2:
        source._diagnostics["last_snapshot_stage"] = "catalog_before"
        progress('catalog-before', 0, len(pending))
        index, reused = bracket(pending, allow_reuse=reuse, failures=failures)
        revisions = {}
        for root_id in pending:
            if failures is not None and root_id not in index.by_id:
                failures.setdefault(root_id, SourceConcurrentChangeError('History root left the catalog', phase='snapshot'))
            else:
                revisions[root_id] = index.revision(root_id, source._revision)
        pending = tuple(revisions)
        if not pending:
            break
        source._diagnostics["last_snapshot_stage"] = "messages"
        progress('messages', 0, len(pending))
        with source.metrics.measure("hydration"):
            snapshots = _read_trees(source, index, pending, revisions, workers=workers, progress=progress,
                                    failures=failures, on_root=on_root, identify_members=identify_members)
        source.metrics.add("hydrated_roots", len(snapshots))
        source._diagnostics["last_snapshot_stage"] = "catalog_after"
        progress('catalog-after', 0, len(pending))
        after, _reused = bracket(pending, allow_reuse=False, failures=failures)
        unstable = []
        for root_id in pending:
            if root_id not in snapshots:
                continue  # Watch-only local failure: siblings still require this after-bracket.
            if root_id not in after.by_id:
                if failures is not None:
                    failures.setdefault(root_id, SourceConcurrentChangeError('History root left the catalog', phase='snapshot'))
                    continue
                raise SourceConcurrentChangeError("OpenCode V2 session changed while it was being read",
                                                  phase="snapshot", generation="v2")
            revision = after.revision(root_id, source._revision)
            if revision == revisions[root_id]:
                complete[root_id] = replace(snapshots[root_id], source_revision=revision, complete=True)
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
    if pending and not available_only:
        source._diagnostics["last_snapshot_stage"] = "revision_changed"
        failure = SourceConcurrentChangeError("OpenCode V2 session changed repeatedly while it was being read",
                                              phase="snapshot", generation="v2")
        if identify_members:
            raise SourceSnapshotMemberError(pending[0], failure) from failure
        raise failure
    if failures is not None:
        for root_id in pending:
            failures[root_id] = SourceConcurrentChangeError('History revision changed repeatedly', phase='snapshot')
    source._diagnostics["last_snapshot_stage"] = "partial" if pending else "complete"
    return complete
