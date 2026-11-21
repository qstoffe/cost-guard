"""Structural absences that can be proved without another source read."""

EMPTY_HISTORY = "complete_empty_history"


def empty_history(snapshot):
    """An inactive root with no recorded history in this complete revision."""
    return (snapshot is not None and snapshot.complete and bool(snapshot.source_revision)
        and snapshot.root.active is not True and snapshot.sessions == (snapshot.root,)
        and not (snapshot.messages or snapshot.parts or snapshot.events or snapshot.invocations
            or snapshot.background or snapshot.active_contexts or snapshot.context_boundaries))
