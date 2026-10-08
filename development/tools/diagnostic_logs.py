"""Bounded collection of Cost Guard-owned diagnostic logs.

A ZIP is committed and CRC-verified before any unchanged, inactive log is
removed. Never follow symlinks, scan unrelated files, or remove active writes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import time
from zipfile import ZipFile, ZIP_DEFLATED

_MAX_FILES = 128
_MAX_FILE_BYTES = 512 * 1024
_MAX_TOTAL_BYTES = 4 * 1024 * 1024
_QUIET_SECONDS = 60
_OWNED = {
    "errors": re.compile(r"cost-guard-errors-\d{4}-\d{2}-\d{2}\.log\Z"),
    "crashes": re.compile(r"cost-guard-crash-\d{8}-\d{6}-\d+(?:-\d+)?\.txt\Z"),
    "recovery": re.compile(r"watch-recovery\.json\Z"),
}


def _owned_files(root: Path):
    base = root / "diagnostics"
    count = 0
    for folder, name_pattern in _OWNED.items():
        directory = base / folder
        if directory.is_symlink():
            continue
        try:
            entries = sorted(directory.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for path in entries[:2048]:
            if count >= _MAX_FILES:
                return
            if name_pattern.fullmatch(path.name) and not path.is_symlink() and path.is_file():
                count += 1
                yield path, f"logs/{folder}/{path.name}"
    # Backward compatibility with v80.15's misplaced root-level recovery log.
    legacy = base / "watch-recovery.json"
    if count < _MAX_FILES and not legacy.is_symlink() and legacy.is_file():
        yield legacy, "logs/recovery/legacy-watch-recovery.json"


def _fingerprint(path: Path, body: bytes):
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, hashlib.sha256(body).digest()


def create_bundle(path: Path, *, root: Path, json_bytes: bytes, text_bytes: bytes, include_logs: bool = True) -> dict[str, int]:
    """Build, verify and atomically publish the ZIP; then prune quiet archived logs."""
    path = Path(path)
    root = Path(root)
    temp = path.with_name(path.name + ".incomplete")
    records = []
    included = skipped = total = 0
    try:
        with ZipFile(temp, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            archive.writestr("diagnostics.json", json_bytes)
            archive.writestr("summary.txt", text_bytes)
            for candidate, zip_name in (_owned_files(root) if include_logs else ()):
                try:
                    start = candidate.stat()
                    if not candidate.is_file() or start.st_size > _MAX_FILE_BYTES or total + start.st_size > _MAX_TOTAL_BYTES:
                        skipped += 1
                        continue
                    raw = candidate.read_bytes()
                    before = (start.st_dev, start.st_ino, start.st_size, start.st_mtime_ns)
                    after = candidate.stat()
                    if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != before or len(raw) != start.st_size:
                        skipped += 1
                        continue
                    archive.writestr(zip_name, raw)
                    records.append((candidate, zip_name, _fingerprint(candidate, raw)))
                    total += len(raw)
                    included += 1
                except OSError:
                    skipped += 1
        with ZipFile(temp, "r") as archive:
            if archive.testzip() is not None or not {"diagnostics.json", "summary.txt"}.issubset(archive.namelist()):
                raise ValueError("Diagnostic ZIP verification failed")
            if archive.read("diagnostics.json") != json_bytes or archive.read("summary.txt") != text_bytes:
                raise ValueError("Diagnostic ZIP contents changed during creation")
        temp.replace(path)  # no log cleanup without a verified published bundle
    except BaseException:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    removed = 0
    cutoff = time.time() - _QUIET_SECONDS
    for candidate, zip_name, fingerprint in records:
        try:
            stat = candidate.stat()
            # A recent write may belong to an active Watch process.
            if stat.st_mtime >= cutoff or candidate.is_symlink():
                continue
            data = candidate.read_bytes()
            if _fingerprint(candidate, data) != fingerprint:
                continue
            candidate.unlink()
            removed += 1
        except OSError:
            pass
    return {"archived_logs": included, "skipped_logs": skipped,
            "removed_logs": removed, "retained_logs": included - removed}
