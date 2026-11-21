"""Bind archive partitions to an already-selected local source, not to a URL."""
from dataclasses import dataclass
from stat import S_ISREG

from src.analysis.cache import dependency_signature
from src.sources.opencode_v1 import OpenCodeV1Source
from src.sources.opencode_v2 import OpenCodeV2Source


@dataclass(frozen=True, slots=True)
class DisplayBinding:
    scope: str
    source_epoch: str


def _file_identity(path):
    if path is None or not path.is_absolute() or path.drive.startswith("\\\\"):
        return None
    metadata = path.stat()
    if not S_ISREG(metadata.st_mode) or not metadata.st_ino:
        return None
    return str(path), metadata.st_dev, metadata.st_ino


def selected_display_binding(selection):
    """Separate stable file ownership from a transient observation epoch.

    For a service with no proven local database identity, never reuse a
    partition after its registration/proof epoch changes. A path alone is
    not proof that there is still the same database at that path.
    """
    source = selection.source
    try:
        if selection.selected == "v1" and isinstance(source, OpenCodeV1Source):
            file = _file_identity(source.database_path)
            if file is None:
                return None
            identity = dependency_signature(("opencode-v1-display", file))
            return DisplayBinding(identity, identity)
        if selection.selected == "v2" and isinstance(source, OpenCodeV2Source):
            source_epoch = source.observation_epoch
            if not source_epoch:
                return None
            file = _file_identity(source.local_database_path)
            identity = dependency_signature(("opencode-v2-display", source.source_instance, file or source_epoch))
            return DisplayBinding(identity, source_epoch)
    except (OSError, ValueError):
        return None  # Unavailable identity must not authorize an old snapshot.
    return None
