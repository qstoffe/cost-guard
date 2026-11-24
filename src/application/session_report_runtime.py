"""Build writer-side Sessions coverage and Live deltas from the catalog."""


def _pending_value(catalog, key, active):
    if key in active or key not in catalog.roots:
        return None
    if catalog._archive_unavailable(key):
        return catalog.activity.get(key), True
    if key in catalog.history_pending:
        previous = catalog.archive.authorities.get(key)
        if previous is None or previous[3] != catalog.archive_target:
            return catalog.history_pending[key], False
    return None


def _live_value(catalog, key):
    if key not in catalog.roots:
        return None
    if catalog._running(key):
        row, = catalog._rows((key,))
        return (row, row.prompt_started_ms, None) if row.prompt_started_ms is not None else None
    finish = catalog.recent_finishes.get(key)
    if finish is not None and key in catalog.archive.rows:
        row, = catalog._rows((key,))
        return row, None, finish
    return None


def publish_report_runtime(catalog, keys=None):
    """Publish under the caller's catalog lock; report reads do not enter it."""
    if not catalog.archive.loaded:
        return
    status = catalog.state, catalog.index_terminal
    live_roots = catalog.running_roots | catalog.recent_finishes.keys()
    live_keys = live_roots | catalog.report_live.keys() if keys is None else keys
    live = {}
    for key in live_keys:
        value = _live_value(catalog, key)
        if catalog.report_live.get(key) != value:
            live[key] = value
    if keys is None:
        pending_keys = (catalog.history_pending.keys() | catalog.report_pending.keys() |
                        catalog.archive_rejections.keys() | catalog.failures.keys())
    else:
        pending_keys = keys
    active = catalog.active | catalog.running_roots | catalog.live_arrivals
    pending = {}
    for key in pending_keys:
        value = _pending_value(catalog, key, active)
        if catalog.report_pending.get(key) != value:
            pending[key] = value
    if status == catalog.report_status and not pending and not live:
        return
    if catalog.archive.update_runtime(state=status[0], terminal=status[1], reset_pending=False,
                                      pending=pending, live=live):
        catalog.report_status = status
        for published, changes in ((catalog.report_pending, pending), (catalog.report_live, live)):
            for key, value in changes.items():
                if value is None:
                    published.pop(key, None)
                else:
                    published[key] = value
        catalog.wake_revision += 1
