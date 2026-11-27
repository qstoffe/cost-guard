"""Recency and ownership of newly discovered session roots."""

ARRIVAL_SECONDS = 120


def recent_live_roots(arrivals, activity, now, latest):
    # Old roots discovered in bulk must not jump the recency queue.
    cutoff = latest - ARRIVAL_SECONDS * 1000
    return {key for key, discovered in arrivals.items()
            if now - discovered < ARRIVAL_SECONDS and cutoff <= activity.get(key, 0) <= latest}


def retain_live_arrivals(live, roots, previous, added, since_ms, now_ms):
    # Use the continuous interval, not the previous observation. A late
    # discovery of a root created during this interval is still Live work.
    retained = {key for key in live if key in roots and roots[key].provenance == previous[key].provenance}
    if since_ms is not None:
        retained.update(key for key in added if since_ms <= roots[key].created_at_ms <= now_ms)
    return retained
