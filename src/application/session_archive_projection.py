"""Project only qualified Sessions presentation facts, without re-reading history."""
from dataclasses import dataclass

from src.cache.display_history import ACQUIRED_SCALAR_FIELDS, SessionChange, SessionCheckpoint, SessionFact

from .model_help import session_model_help

MODEL_HELP_BYTES = 4096


def bounded_model_help(row):
    text = session_model_help(row, qualify_effort=True)
    encoded = text.encode("utf-8")
    if len(encoded) <= MODEL_HELP_BYTES:
        return text
    suffix = "\n\nAdditional model details omitted; contributing model coverage may be incomplete."
    prefix = encoded[:MODEL_HELP_BYTES - len(suffix)].decode("utf-8", errors="ignore")
    # A recorded identifier and any associated effort qualification are a unit.
    return prefix.rpartition("\n• ")[0].rstrip() + suffix


@dataclass(frozen=True, slots=True)
class SessionPublication:
    """Proof carried by the acquisition owner from admission to publication."""

    session_id: str
    source_revision: str
    observation_epoch: str
    checkpoint: SessionCheckpoint | None

    def project(self, row, *, current_revision, current_epoch, dependency=None, usage=None):
        if (row.session_id != self.session_id or not self.source_revision or not self.observation_epoch
                or self.source_revision != current_revision or self.observation_epoch != current_epoch):
            return None
        # Keep transient liveness out of the durable historical slice. Its
        # display requires independent current-host evidence.
        if row.running:
            return None
        fields = set()
        activity_origin = None
        if row.activity_qualified:
            fields.update(("activity_ms", "latest_activity_ms", "prompt_started_ms", "activity_origin"))
            if row.last_activity_ms is not None:
                activity_origin = "finish"
            elif row.prompt_started_ms is not None:
                activity_origin = "start"
            else:
                activity_origin = "no-prompt"
        if not row.model_pending:
            fields.update(("model", "model_help", "has_model_details"))
        if row.complete:
            fields.update(("prompts", "duration_ms"))
            if not row.ccost_unavailable:
                fields.add("ccost")
        if row.context_qualified:
            fields.update(("context_tokens", "context_detail"))
        fact = SessionFact(
            session_id=row.session_id, revision=self.source_revision, title=row.title,
            activity_ms=row.last_activity_ms, latest_activity_ms=row.activity_latest_ms,
            model=(row.model if row.model != "N/A" else row.selected_display_model) or None,
            ccost=row.ccost, prompts=row.prompt_count, duration_ms=row.duration_ms, context_tokens=row.context_tokens,
            prompt_started_ms=row.prompt_started_ms, activity_origin=activity_origin,
            context_detail=row.context_detail if row.context_qualified else None,
            model_help=bounded_model_help(row) if not row.model_pending else None,
            has_model_details=row.has_model_details if not row.model_pending else None,
        )
        complete = fields == ACQUIRED_SCALAR_FIELDS
        return SessionChange(fact, self.checkpoint.revision if self.checkpoint else None,
                              frozenset(fields), dependency if complete else None,
                              self.checkpoint.progress if self.checkpoint else 0,
                              empty_history=row.empty_history and row.complete and row.activity_qualified,
                              request_roster=usage)
