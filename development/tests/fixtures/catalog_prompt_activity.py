"""Synthetic 01:18 prompt versus 01:52 metadata; no private session history."""
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

from src.watch.web_coordinator import publish_catalog_prompts

from .synthetic_month import make_root_snapshot


def publish_verified_capture(catalog, snapshot, capture):
    entry = SimpleNamespace(snapshot=snapshot, capture=capture, source_status=SimpleNamespace(failed_at=None),
                            generation=1, verified_generation=1)
    publish_catalog_prompts(catalog, SimpleNamespace(sessions={snapshot.root.session_id: entry}))


def at(clock):
    return int(datetime.fromisoformat("2026-11-15T" + clock).replace(tzinfo=timezone.utc).timestamp() * 1000)


def finished_snapshot(index=0, finished=None, metadata=None):
    finished = at("01:18:00") if finished is None else finished
    snapshot = make_root_snapshot(index, 1, month_start_ms=finished - 300 - index * 60_000)
    root = replace(snapshot.root, active=False, updated_at_ms=metadata or at("01:52:00"))
    return replace(snapshot, root=root, sessions=(root,), complete=True)
