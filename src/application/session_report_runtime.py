"""Build writer-side Sessions coverage and Live deltas from the catalog."""
from dataclasses import replace

from src.cache.session_projection import TERMINAL_HIGHLIGHT_MS


def _pending_value(catalog, key, live_roots):
    if key not in catalog.roots:
        return None
    if catalog._archive_unavailable(key):
        return catalog.activity.get(key), True
    if key in live_roots:
        return None
    if key in catalog.history_pending:
        previous = catalog.archive.authorities.get(key)
        if previous is None or previous[3] != catalog.archive_target:
            return catalog.history_pending[key], False
    return None


def _live_value(catalog, key):
    if key not in catalog.roots:
        catalog.report_live_costs.pop(key, None)
        return None
    if catalog._running(key):
        row, = catalog._rows((key,), compatible_archive=True)
        row = _with_live_cost(row, catalog.report_live_costs.get(key), catalog.revisions.get(key))
        return (row, row.prompt_started_ms, None) if row.prompt_started_ms is not None else None
    handoff = catalog.terminal_handoffs.get(key)
    if handoff is None:
        catalog.report_live_costs.pop(key, None)
        return None
    if key not in catalog.finalize_roots:
        catalog.report_live_costs.pop(key, None)
        if catalog.clock_ms() >= handoff.observed_ms + TERMINAL_HIGHLIGHT_MS:
            catalog.terminal_handoffs.pop(key, None)
            return None
        if handoff.outcome is None:
            return None
        return catalog.archive.rows[key], None, (handoff.observed_ms, handoff.outcome, None)
    row, = catalog._rows((key,), compatible_archive=True)
    row = _with_live_cost(row, catalog.report_live_costs.get(key), catalog.revisions.get(key))
    start, prompt_id = handoff.identity
    finish = row.last_activity_ms if (row.prompt_started_ms, row.activity_prompt_id) == handoff.identity else None
    row = replace(row, running=False, prompt_started_ms=start, activity_prompt_id=prompt_id, last_activity_ms=finish,
                  complete=False, ccost_complete=False, ccost_retained=row.ccost is not None)
    state = 'unavailable' if catalog._archive_unavailable(key) else 'pending'
    return row, None, (handoff.observed_ms, handoff.outcome, state)


def _with_live_cost(row, offer, revision):
    if offer is None:
        return row
    cost, current = offer
    complete = cost.total.complete and cost.source_complete
    amount = cost.total.known_ccost if cost.total.priced_requests or complete else None
    # The scalar lane trails the Watch valuation independently. Do not bounce
    # back to that older subtotal while the next same-tree capture is pending.
    if amount is None and row.ccost is not None:
        return row
    return replace(row, ccost=amount, ccost_complete=complete,
        ccost_retained=amount is not None and (not current or cost.source_revision != revision),
        ccost_unavailable=cost.total.unavailable, main_ccost=cost.main_ccost,
        subagent_ccost=cost.subagent_ccost, cost_groups=cost.groups)


def publish_report_runtime(catalog, keys=None):
    """Publish under the caller's catalog lock; report reads do not enter it."""
    if not catalog.archive.loaded:
        return
    state = 'observed' if catalog.history_observed() else catalog.state
    status = state, catalog.index_terminal
    live_roots = catalog.running_roots | catalog.terminal_handoffs.keys()
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
    progress_live_roots = catalog.history_progress_live_roots()
    pending = {}
    for key in pending_keys:
        value = _pending_value(catalog, key, progress_live_roots)
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
