"""Privacy-safe diagnostics logs and verified single-file ZIP publishing."""
from __future__ import annotations

import os
from pathlib import Path
import time
from zipfile import ZipFile, ZIP_DEFLATED

from src.log_paths import WRITE_LOCK, file_lock, log_root, owned_files, safe_path

_MAX_FILES = 128
_MAX_FILE_BYTES = 512 * 1024
_MAX_TOTAL_BYTES = 4 * 1024 * 1024


def _owned_files(root: Path):
    count = 0
    # Only the owned metadata file, never arbitrary cache/database contents.
    state = root / "cache" / "state" / "model-metadata.json"
    if safe_path(root, state) and state.is_file():
        count += 1
        yield state, "state/model-metadata.json"
    for path, kind in owned_files(root):
        if kind == "bundles":
            continue
        if count >= _MAX_FILES:
            return
        if path.name == "model-metadata.json" and state.is_file():
            continue  # Authoritative cache state wins, never a mixed-era status file.
        count += 1
        if path.is_relative_to(log_root(root)):
            prefix = ""
        elif path.is_relative_to(root / "logs"):
            prefix = "legacy-root/"
        else:
            prefix = "legacy-diagnostics/"
        yield path, f"logs/{kind}/{prefix}{path.name}"
    legacy = root / "diagnostics" / "watch-recovery.json"
    if count < _MAX_FILES and safe_path(root, legacy) and legacy.is_file():
        yield legacy, "logs/recovery/legacy-watch-recovery.json"


def create_bundle(path: Path, *, root: Path, json_bytes: bytes, text_bytes: bytes,
                  include_logs: bool = True, cleanup_old: bool = True) -> dict[str, int]:
    """Verify and publish atomically. Retention belongs solely to daily maintenance.

    cleanup_old is retained for callers; bundling never prunes even a custom output.
    Logical logs/ ZIP member names are stable; legacy paths are explicitly labelled.
    """
    path = Path(path)
    root = Path(root)
    # Unique staging filenames; never two processes writing one temp path.
    staging = path.with_name(path.name + f".{os.getpid()}.{time.time_ns()}.incomplete")
    seen = set()
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
                    with WRITE_LOCK, candidate.open("rb") as source, file_lock(source):
                        raw = source.read(_MAX_FILE_BYTES + 1)
                    before = (start.st_dev, start.st_ino, start.st_size, start.st_mtime_ns)
                    after = candidate.stat()
                    if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != before or len(raw) != start.st_size:
                        skipped += 1
                        continue
                    identity = (candidate.name, raw)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    archive.writestr(zip_name, raw)
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

    return {"archived_logs": included, "skipped_logs": skipped, "removed_logs": 0,
            "retained_logs": included, "old_archives_removed": 0}
