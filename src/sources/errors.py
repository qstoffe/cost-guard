"""Session-source failures with user-safe diagnostics."""
from __future__ import annotations


class SourceError(RuntimeError):
    """Base failure for source discovery/reading."""


class SourceUnavailableError(SourceError):
    """The requested source is not present or cannot be opened."""


class SourceSchemaError(SourceError):
    """The source exists but does not expose the supported schema contract."""


class SourceDataError(SourceError):
    """Persisted source data cannot be normalized safely."""


class SourceResyncRequiredError(SourceUnavailableError):
    """A non-replayable live stream ended; callers must resnapshot state."""
