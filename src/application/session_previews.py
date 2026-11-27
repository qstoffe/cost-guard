"""Bounded preview projections for the Full and Mini Watch displays."""
from heapq import nsmallest

from src.watch.models import SessionPreview


# Maximum Mini viewport (10) plus a small scrollback window. The card
# scheduler still owns bounded source admission; this shortlist is in-memory.
MINI_PREVIEW_LIMIT = 15


def preview_activity(catalog, key, now):
    current = catalog._activity_current(key)
    at = catalog.rows[key].last_activity_ms if current else catalog.activity.get(key)
    return (at if type(at) is int and 0 < at <= now else None), current


def terminal_activity(catalog, key, watch_finish_ms, now):
    fallback, from_events = preview_activity(catalog, key, now)
    if fallback is not None and (watch_finish_ms is None or (from_events and fallback > watch_finish_ms)):
        return fallback, 'events' if from_events else 'catalog'
    return watch_finish_ms, None


def live_previews(catalog, excluded, limit):
    """Reuse current scalar facts, not a browser's pinned epoch.

    The caller holds the catalog lock. Catalog metadata estimates activity,
    not prompt completion. Next-context has a separate owner.
    """
    limit = max(0, min(MINI_PREVIEW_LIMIT, limit))
    if catalog.last_observation is None or not limit:
        return ()
    excluded = set(excluded) | catalog.active
    now = catalog.clock_ms()

    def total_scope(key):
        return (catalog.revisions.get(key), catalog.roots[key].provenance,
                catalog.last_observation.source_epoch, catalog.dependencies, catalog.timezone_id)

    def candidate(key):
        row = catalog.rows.get(key)
        failure = catalog.failures.get(key)
        rejected = bool(failure and failure[1])
        current = key in catalog.valid and catalog.valid[key][0] == catalog.revisions.get(key) and not rejected
        if key in excluded or catalog._running(key):
            return None
        at, activity_current = preview_activity(catalog, key, now)
        scope = total_scope(key)
        previous = None if rejected else catalog.preview_totals.get(key)
        total = (row.ccost if current and row is not None and row.complete else
                 previous[1] if previous is not None and previous[0] == scope else None)
        if total is not None:
            total_state = ("retained" if catalog.state != 'observed' or catalog.index_unavailable or failure
                           or not current or not row.complete else "ready")
        elif catalog.index_terminal or rejected:
            total_state = "unavailable"
        elif failure or catalog.index_unavailable or catalog.state == 'source_unavailable':
            total_state = "retrying"
        else:
            total_state = "partial" if current else "pending"
        return SessionPreview(key, catalog.roots[key].title or "Untitled session", at,
                              "events" if activity_current else "catalog",
                              total, total is not None, total_state=total_state)

    # Bounded top-K output/memory; no full-history sort or capture.
    selected = tuple(nsmallest(limit, (value for key in catalog.roots
        if (value := candidate(key)) is not None),
        key=lambda value: (-(value.activity_ms or 0), value.session_id)))
    catalog.preview_totals = {value.session_id: (total_scope(value.session_id), value.total_ccost)
                              for value in selected if value.total_ccost is not None}
    return selected


def archived_previews(candidates, limit):
    """Rank a captured copy of ready rows outside the catalog lock."""
    selected = nsmallest(limit, candidates, key=lambda row: (
        -(row.activity_latest_ms or row.last_activity_ms or 0), row.session_id))
    return tuple(SessionPreview(row.session_id, row.title, row.last_activity_ms or row.activity_latest_ms,
                                'events' if row.last_activity_ms else 'catalog', row.ccost, row.complete,
                                hydration_state='retained', total_state='retained' if row.ccost is not None
                                else 'unavailable', empty_history=row.empty_history) for row in selected)
