"""Project only qualified Sessions presentation facts, without re-reading history."""
from dataclasses import dataclass

from src.cache.display_history import SessionChange, SessionFact


@dataclass(frozen=True, slots=True)
class SessionPublication:
    """Proof carried by the acquisition owner from admission to publication."""

    session_id: str
    source_revision: str
    observation_epoch: str
    archived_revision: str | None

    def project(self, row, *, current_revision, current_epoch):
        if (row.session_id != self.session_id or not self.source_revision or not self.observation_epoch
                or self.source_revision != current_revision or self.observation_epoch != current_epoch):
            return None
        # Keep transient liveness out of the durable historical slice. Its
        # display requires independent current-host evidence.
        if row.running:
            return None
        fields = set()
        if row.activity_qualified:
            fields.update(("activity_ms", "latest_activity_ms"))
        if not row.model_pending:
            fields.add("model")
        if row.complete:
            fields.update(("ccost", "prompts", "duration_ms"))
        if row.context_qualified:
            fields.add("context_tokens")
        fact = SessionFact(
            session_id=row.session_id, revision=self.source_revision, title=row.title,
            activity_ms=row.last_activity_ms, latest_activity_ms=row.activity_latest_ms,
            model=(row.model if row.model != "N/A" else row.selected_display_model) or None,
            ccost=row.ccost, prompts=row.prompt_count, duration_ms=row.duration_ms, context_tokens=row.context_tokens,
        )
        return SessionChange(fact, self.archived_revision, frozenset(fields))
