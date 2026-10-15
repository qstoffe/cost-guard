"""Synthetic neutral Watch prompt blocks and canonical event snapshots for ordering tests."""
from dataclasses import replace
from decimal import Decimal

from development.fixtures.session_snapshots import make_snapshot
from src.domain import EventKind, NormalizedEvent
from src.reports.models import PromptProjection, SessionPromptBlock
from src.watch.tracker import WatchRowTracker


def prompt(number, at_ms, **changes):
    return PromptProjection(
        at_ms=at_ms, prompt_number=number, event_id=f"event-{number}",
        label=f"#{number}", preview=f"prompt {number}", model_effort="model",
        ccost=Decimal(0), cost_estimated=False, unresolved_cost=False, calls=0,
        incoming_context_tokens=None, incoming_context_ccost=None,
        extra_ccost=None, token_mix_percent=None, **changes,
    )


def inputs(**sessions):
    base = make_snapshot()
    blocks, snapshots = {}, {}
    for session_id, rows in sessions.items():
        root = replace(base.root, session_id=session_id, title=f"Session {session_id}")
        events = tuple(NormalizedEvent(
            row.event_id, session_id,
            EventKind.COMPACTION if row.is_compaction else EventKind.USER_PROMPT,
            row.at_ms, base.events[0].provenance,
        ) for row in rows)
        blocks[session_id] = SessionPromptBlock(session_id, root.title, tuple(rows), Decimal(0), 0)
        snapshots[session_id] = replace(
            base, root=root, sessions=(root,), events=events,
            messages=(), parts=(), invocations=(),
        )
    return blocks, snapshots


def tracker(*, max_rows=20, recent_seconds=0, session_scope=False):
    return WatchRowTracker(
        started_at_ms=0, recent_seconds=recent_seconds,
        max_rows=max_rows, session_scope=session_scope,
    )
