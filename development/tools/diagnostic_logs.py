"""Privacy-safe diagnostics logs and verified single-file ZIP publishing."""
from __future__ import annotations

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
    "errors": re.compile(r"cost-guard-(?:errors|metadata)-\d{4}-\d{2}-\d{2}\.log\Z"),
    "crashes": re.compile(r"cost-guard-crash-\d{8}-\d{6}-\d+(?:-\d+)?\.txt\Z"),
    "recovery": re.compile(r"(?:(?:watch-recovery|watch-observations|model-metadata)\.json|cost-guard-metadata-\d{4}-\d{2}-\d{2}\.log)\Z"),
}
# Live retry/health state is archived but never pruned: deleting it would
# reset the metadata backoff and erase the evidence of an ongoing failure.
# Bounded Watch observations likewise keep source-error history across bundles.
_LIVE_STATE = frozenset({"model-metadata.json", "watch-observations.json"})


def _owned_files(root: Path):
    count = 0
    # Only the owned metadata file, never arbitrary cache/database contents.
    state = root / "cache" / "state" / "model-metadata.json"
    if not any(p.is_symlink() for p in (state, state.parent, state.parent.parent)) and state.is_file():
        count += 1
        yield state, "state/model-metadata.json"
    for base in (root / "logs", root / "diagnostics"):
        if base.is_symlink():
            continue
        for folder, pattern in _OWNED.items():
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
                if pattern.fullmatch(path.name) and not path.is_symlink() and path.is_file():
                    count += 1
                    prefix = "legacy-" if base.name == "diagnostics" else ""
                    yield path, f"logs/{folder}/{prefix}{path.name}"
    legacy = root / "diagnostics" / "watch-recovery.json"
    if count < _MAX_FILES and not legacy.is_symlink() and legacy.is_file():
        yield legacy, "logs/recovery/legacy-watch-recovery.json"


def _fingerprint(path: Path, body: bytes):
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, hashlib.sha256(body).digest()


def _prune_old_bundles(path: Path) -> int:
    """Remove only owned historic timestamped packages after publishing new ZIP."""
    count = 0
    for old in list(path.parent.glob("cost-guard-diagnostics-????????-??????.zip"))[:256]:
        if old.is_symlink() or not old.is_file():
            continue
        try:
            old.unlink()
            count += 1
        except OSError:
            pass
    return count


def create_bundle(path: Path, *, root: Path, json_bytes: bytes, text_bytes: bytes,
                  include_logs: bool = True, cleanup_old: bool = True) -> dict[str, int]:
    """Verify ZIP and publish atomically before pruning historic archives/logs."""
    path = Path(path)
    root = Path(root)
    # Unique staging filenames; never two processes writing one temp path.
    staging = path.with_name(path.name + f".{os.getpid()}.{time.time_ns()}.incomplete")
    records = []
    included = skipped = total = 0
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(staging, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
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
                    records.append((candidate, _fingerprint(candidate, raw)))
                    included += 1
                    total += len(raw)
                except OSError:
                    skipped += 1
        with ZipFile(staging) as archive:
            if archive.testzip() is not None or not {"diagnostics.json", "summary.txt"}.issubset(archive.namelist()):
                raise ValueError("Diagnostic ZIP CRC validation failed")
            if archive.read("diagnostics.json") != json_bytes or archive.read("summary.txt") != text_bytes:
                raise ValueError("Diagnostic ZIP verification failed")
        staging.replace(path)
    except BaseException:
        try:
            staging.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    removed = 0
    for candidate, fingerprint in records:
        try:
            if (candidate.name in _LIVE_STATE or candidate.is_symlink()
                    or candidate.stat().st_mtime >= time.time() - _QUIET_SECONDS):
                continue
            if _fingerprint(candidate, candidate.read_bytes()) == fingerprint:
                candidate.unlink()
                removed += 1
        except OSError:
            pass
    historic = _prune_old_bundles(path) if cleanup_old else 0
    return {"archived_logs": included, "skipped_logs": skipped, "removed_logs": removed,
            "retained_logs": included - removed, "old_archives_removed": historic}
