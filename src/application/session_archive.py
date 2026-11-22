"""Session display persistence and pagination over the ready subset."""
from collections import OrderedDict
from decimal import InvalidOperation
import logging
import sqlite3
from uuid import uuid4

from src.analysis.metric_evidence import EMPTY_HISTORY
from src.cache.web_archive import ArchiveFact
from src.reports.models import ReportKind, ReportProjection
from src.reports.session_summary import ALGORITHM, decode_summary, encode_summary

from .projection import project
from .session_catalog_scope import PAGE_SIZE, catalog_window, in_window, row_in_window


LOG = logging.getLogger(__name__)
DOMAIN = f'sessions/{ALGORITHM}'
LIVE_TAIL_MS = 10 * 60_000


class SessionArchive:
    def __init__(self, storage):
        self.storage = storage
        self.partition = None
        self.rows = {}
        self.authorities = {}

    def load(self, partition):
        decoded, authorities = {}, {}
        try:
            self.storage.initialize()
            facts = self.storage.read(partition, DOMAIN)
        except (sqlite3.Error, OSError):
            LOG.warning('session_archive_read_unavailable')
            return None
        for key, fact in facts.items():
            try:
                row = decode_summary(fact.value['row'])
                if row.session_id != key or row.running or not row.activity_qualified:
                    continue
                decoded[key] = row
                authorities[key] = fact.revision, fact.value['dependencies'], fact.value['models']
            except (KeyError, TypeError, ValueError, InvalidOperation):
                continue
        return decoded, authorities

    def save(self, partition, key, revision, row, observed_ms, dependencies, models):
        try:
            self.storage.publish(partition, DOMAIN, {
                key: ArchiveFact(revision, observed_ms, dict(
                    row=encode_summary(row), dependencies=dependencies, models=models)),
            })
        except (sqlite3.Error, OSError, ValueError):
            LOG.warning('session_archive_write_unavailable')
            return False
        return True


def cached_page(catalog, ordered, *, token, offset, sort, direction, period, navigation):
    """Current offsets address the latest cached order, not source qualification."""
    archive = catalog.archive
    catalog._expire()
    lease = catalog.leases.get(token)
    if lease is None:
        if len(catalog.leases) >= 32:
            raise RuntimeError('catalog_busy')
        token = uuid4().hex
        lease = catalog.leases[token] = dict(epochs=OrderedDict(), cache_epoch=uuid4().hex)
    lease.update(touched=catalog.clock(), sort=sort, period=period)
    if 'interest_until' in lease:
        lease['interest_until'] = catalog.clock() + 90
    window = catalog_window(period, catalog.timezone_id, catalog.clock_ms())
    cache_key = (window.identity, catalog.wake_revision, catalog.generation, sort, direction)
    rows = catalog.orders.get(cache_key)
    if rows is None:
        active_rows = catalog._rows(catalog.rows.keys() | catalog.running_roots | catalog.recent_arrivals.keys())
        retained = (row for key, row in archive.rows.items() if key not in catalog.rows)
        available = {row.session_id: row for row in (*retained, *active_rows)
                     if period == 'all' or row_in_window(row, window) or (
                         row.session_id in catalog.recent_arrivals
                         and in_window(catalog.activity.get(row.session_id), window))}
        rows = ordered(available.values(), sort, direction)
        catalog.orders[cache_key] = rows
        while len(catalog.orders) > 24:
            catalog.orders.popitem(last=False)
    offset = min(offset, max(0, (len(rows) - 1) // PAGE_SIZE) * PAGE_SIZE)
    shown = rows[offset:offset + PAGE_SIZE]
    lease['visible'] = tuple(row.session_id for row in shown)
    title = ReportProjection(ReportKind.SESSIONS, 'Sessions', 'OpenCode', (), session_usage=shown)
    view = project(title, catalog.timezone_id, catalog.unit).to_json()
    for value, row in zip(view['session_usage'], shown):
        key = row.session_id
        saved = key in archive.rows or key in catalog.rows
        current = key in catalog.roots and catalog._current(key)
        value['indexed'] = saved
        value['has_summary'] = saved
        value['new_arrival'] = key in catalog.recent_arrivals and not saved
        value['activity_state'] = ('ready' if row.running or catalog._activity_current(key)
            else 'retained' if row.last_activity_ms is not None else 'pending' if not saved else 'unavailable')
        value['catalog_activity_ms'] = (catalog.activity.get(key) if value['new_arrival'] and
            in_window(catalog.activity.get(key), window) else None)
        value['metric_state'] = 'ready' if current else 'retained' if saved else 'pending'
        value['metric_states'] = dict.fromkeys(('model', 'effort', 'ccost', 'prompts', 'duration', 'ctx'),
                                               value['metric_state'])
        if not row.context_qualified:
            value['metric_states']['ctx'] = 'retained' if row.context_tokens is not None else 'pending'
        if row.model_pending and row.model == 'N/A':
            value['metric_states']['model'] = 'pending'
        if row.empty_history and saved and not row.running:
            value['metric_absences'] = dict.fromkeys(('model', 'ctx', 'activity'), EMPTY_HISTORY)
    cached = sum(row.session_id in archive.rows or row.session_id in catalog.rows for row in rows)
    cutoff = window.end_ms - LIVE_TAIL_MS
    pending = catalog.history_pending
    if catalog.observed is None or catalog.state == 'source_unavailable':
        complete = False
    elif window.start_ms is None:
        complete = not any(at is None or at < cutoff for at in pending.values())
    else:
        complete = not any(at is None or window.start_ms <= at < cutoff for at in pending.values())
    progress = dict(cached=cached, complete=complete, remaining=None)
    return dict(cache_first=True, token=token, epoch=lease['cache_epoch'], offset=offset, total=len(rows),
                size=PAGE_SIZE, page_reused=True, retained_order=False, membership_pending=False,
                candidate_navigation=True, order_state='verified', state='observed', period=period,
                sort=sort, direction=direction, pending_sort=False, indexed=cached,
                navigation=navigation, history_progress=progress, view=view)
