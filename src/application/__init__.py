"""Optional transport-neutral report application; CLI remains independent."""

from .service import ReportApplication
from .contracts import ReportResult, ProgressEvent

__all__ = ["ReportApplication", "ReportResult", "ProgressEvent"]
