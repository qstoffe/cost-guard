"""Window-by-window account coverage on Web's existing isolated history reader."""
from dataclasses import dataclass, field
from queue import SimpleQueue
from threading import Event

from src.analysis.daily_usage import DailyUsage
from src.application.session_quota import source_scope
from src.domain.session_tree import root_activity
from src.reports.accounts import AccountPeriodHistory


@dataclass(frozen=True, slots=True)
class DailyAccountHistory:
    accounts: AccountPeriodHistory
    usage: DailyUsage | None
    source: tuple
    roots: dict


@dataclass(slots=True)
class AccountHistoryProgress:
    starts: tuple[int, ...]
    scope_start_ms: int
    day_start_ms: int
    restart: Event = field(default_factory=Event)
    updates: SimpleQueue = field(default_factory=SimpleQueue)


def acquire_windows(service, history, sessions, snapshots, now_ms, active_roots, source, *, closed, progress):
    service.enable_watch_accounts(record_evidence=False, history=history)
    day = service.prepare_watch_account_history(snapshots)
    roots = service.watch_history_candidates(sessions, active_root_ids=active_roots, live_root_ids=active_roots)
    activity = root_activity(sessions)
    active = set(active_roots)
    ordered = sorted(roots, key=lambda root: (root.session_id not in active, -activity[root.session_id]))
    # Stop batches at consumer boundaries. An unreadable older root must not
    # prevent publishing a newer window that has already been acquired.
    published_since = None
    offset = 0
    while True:
        if closed():
            return None
        next_root = ordered[offset] if offset < len(ordered) else None
        if next_root is None:
            covered_since = history.scope_start_ms
        elif next_root.session_id in active:
            covered_since = None
        else:
            covered_since = max(history.scope_start_ms, activity[next_root.session_id] + 1)
        starts = progress.starts if progress is not None else ()
        window_ready = covered_since is not None and any(
            covered_since <= start and (published_since is None or start < published_since) for start in starts)
        if next_root is None or window_ready:
            if source_scope(service.source) != source:
                return None
            service.publish_watch_history(covered_since_ms=covered_since)
            service.project_watch_accounts(snapshots, history_through_ms=now_ms)
            value = DailyAccountHistory(service.watch_account_history(),
                service.project_watch_today() if covered_since <= day else None, source, dict(history.chart_roots))
            if next_root is None:
                return value
            published_since = covered_since
            progress.updates.put(value)
        if progress is not None and progress.restart.is_set():
            return None
        end = min(offset + 4, len(ordered))
        for index in range(offset + 1, end):
            first, following = next_root.session_id, ordered[index].session_id
            if ((first in active) != (following in active) or first not in active
                    and any(activity[following] < start <= activity[first] for start in starts)):
                end = index
                break
        service.watch_history_batch(ordered[offset:end])
        offset = end
