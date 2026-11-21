"""Independent Web projection of main SQLite file lengths, not database contents."""
from pathlib import Path
from stat import S_ISREG

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


def database_sizes(selection: SourceSelection | None, cache_path: Path | None) -> dict[str, int | None]:
    opencode_path = None
    if selection is not None:
        source = selection.source
        try:
            if selection.selected == "v1" and isinstance(source, OpenCodeV1Source):
                opencode_path = source.database_path
            elif selection.selected == "v2" and isinstance(source, OpenCodeV2Source):
                opencode_path = source.local_database_path
        except (OSError, ValueError, RuntimeError):
            # Local data-directory resolution can fail independently of the cache.
            pass
    return {"opencode_bytes": _main_file_size(opencode_path), "cache_bytes": _main_file_size(cache_path)}
