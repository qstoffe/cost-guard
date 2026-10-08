"""Atomic metadata-state persistence with non-destructive legacy migration.

Diagnostics reads without migration. Runtime owners copy legacy state into
cache/state before changing it; the legacy copy is never deleted. If cache
writes fail, an existing valid legacy state remains a writable fallback.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import time

STATE_FILE = Path("cache/state/model-metadata.json")
LEGACY_STATE_FILE = Path("logs/recovery/model-metadata.json")


def _read(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return {}
    return raw if isinstance(raw, dict) and raw.get("schema") == 1 else {}


def read_state(root: Path | None) -> dict:
    if root is None:
        return {}
    return _read(Path(root) / STATE_FILE) or _read(Path(root) / LEGACY_STATE_FILE)


def _write(path: Path, state: dict, *, exclusive: bool = False) -> bool:
    temp = path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
        if exclusive:
            # Atomic create-if-absent: a concurrent runtime's newer state wins.
            os.link(temp, path)
        else:
            temp.replace(path)
        return True
    except OSError:
        return False
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def migrate_state(root: Path | None) -> None:
    if root is None or _read(Path(root) / STATE_FILE):
        return
    legacy = _read(Path(root) / LEGACY_STATE_FILE)
    if legacy:
        _write(Path(root) / STATE_FILE, legacy, exclusive=True)


def persist_state(root: Path | None, state: dict) -> None:
    if root is None:
        return
    if not _write(Path(root) / STATE_FILE, state):
        legacy = Path(root) / LEGACY_STATE_FILE
        if _read(legacy):
            _write(legacy, state)
