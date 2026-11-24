"""Optional Web metadata for the measured databases, independent of report scope."""
from pathlib import Path
import sqlite3
from stat import S_ISREG

from src.application.session_archive import DOMAIN as SESSION_DOMAIN
from src.cache.web_archive import WebArchive
from src.sources.errors import SourceError
from src.sources.opencode_v1 import OpenCodeV1Source
from src.sources.opencode_v2 import OpenCodeV2Source
from src.sources.selection import SourceSelection


def _main_file_size(path: Path | None) -> int | None:
    if path is None or not path.is_absolute() or path.drive.startswith("\\\\"):
        return None
    try:
        metadata = path.stat()
        return metadata.st_size if S_ISREG(metadata.st_mode) else None
    except (OSError, ValueError):
        return None


def _opencode_facts(selection: SourceSelection | None) -> tuple[int | None, int | None, int | None]:
    size = roots = children = None
    if selection is not None:
        source = selection.source
        if selection.selected == "v1" and isinstance(source, OpenCodeV1Source):
            size = _main_file_size(source.database_path)
            if size is not None:
                try:
                    roots, children = source.database_session_counts()
                except (OSError, ValueError, SourceError):
                    pass  # An unreadable count must not discard the known size.
        elif selection.selected == "v2" and isinstance(source, OpenCodeV2Source):
            try:
                size = _main_file_size(source.local_database_path)
            except (OSError, ValueError, RuntimeError):
                pass  # Local path discovery is independent of catalog availability.
            roots, children = source.database_session_counts() or (None, None)
    return size, roots, children


def database_sizes(selection: SourceSelection | None, cache_path: Path, *,
                   archive: WebArchive | None = None) -> dict[str, int | str | None]:
    opencode_size, opencode_roots, opencode_children = _opencode_facts(selection)
    cache_size = _main_file_size(archive.path if archive is not None else cache_path)
    cache_roots = None
    if archive is not None and cache_size is not None:
        try:
            cache_roots = archive.history_item_count(SESSION_DOMAIN)
        except (OSError, ValueError, sqlite3.Error):
            pass
    return {
        "opencode_bytes": opencode_size, "opencode_main_sessions": opencode_roots,
        "opencode_subagent_sessions": opencode_children, "cache_bytes": cache_size,
        "cache_main_sessions": cache_roots, "cache_subagent_sessions": None,
        "cache_kind": "web_history" if archive is not None else "analysis",
    }
