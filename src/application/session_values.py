"""Detail-only display authority; never changes raw report accounting or history.

Capture once alongside the immutable report, not on each transferred row page.
Only pending fields may reuse a browser's prior qualified display observation.
"""
from .projection import identity

INVALID_REASONS = frozenset({
    "source_identity_changed", "session_missing", "http_auth_failure",
    "authentication_required", "host_identity_changed",
})


def value_authority(history, source):
    snapshot, fresh = history.snapshot, history.fresh_snapshot
    if snapshot is None or fresh is None:
        return None
    # SessionHistory resets its subclass on incompatible source/config/pricing
    # dependencies. This epoch therefore never bridges such a reset.
    provenance = snapshot.root.provenance
    scope = identity((provenance.source_type, provenance.source_generation, provenance.source_instance,
        getattr(source, "observation_epoch", None), snapshot.root.session_id, history.value_epoch))
    authoritative = fresh.complete and not history.retained
    old = history.value_usage
    withdrawn = frozenset(
        item.initiating_event_id for item in fresh.invocations
        if fresh.complete and old.get((item.session_id, item.invocation_id), frozenset())
        - set(item.tokens.known_fields))
    # Partial transport/projection cannot erase the qualification against which
    # a later complete source correction must be compared. Keep field names only.
    history.value_usage = {(item.session_id, item.invocation_id):
        frozenset(item.tokens.known_fields) if fresh.complete else
        old.get((item.session_id, item.invocation_id), frozenset()) | frozenset(item.tokens.known_fields)
        for item in snapshot.invocations}
    block = history.report.prompt_blocks[0]
    running = any(row.in_progress for row in block.rows)

    def state(known, *, corrected=False):
        if corrected and not known:
            return "invalidated"
        if known and authoritative:
            return "known"
        return "pending" if running or not authoritative else "unavailable"

    totals = dict(
        total_calls=state(True),
        duration_ms=state(block.duration_ms is not None),
        total_ccost=state(block.comparison_cost_complete, corrected=bool(withdrawn)),
        total_ictx_cost_text=state(block.total_ictx_cost_text.endswith("%"), corrected=bool(withdrawn)),
        total_extra_cost_text=state(block.total_extra_cost_text.endswith("%"), corrected=bool(withdrawn)),
        total_mix_text=state(bool(block.total_mix_text) and block.total_mix_text != "N/A",
                             corrected=bool(withdrawn)),
    )
    rows = {row.event_id: ("invalidated" if withdrawn and row.token_mix_percent is None else
        "known" if row.token_mix_percent is not None and authoritative else
        "pending" if row.in_progress or not authoritative else "unavailable") for row in block.rows}
    return dict(scope=scope, totals=totals, rows=rows)
