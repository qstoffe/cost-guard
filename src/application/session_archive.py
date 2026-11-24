"""Session display persistence and pagination over the ready subset."""
from collections import OrderedDict
from dataclasses import replace
from decimal import Decimal, InvalidOperation
import logging
import sqlite3
from uuid import uuid4

from src.analysis.metric_evidence import EMPTY_HISTORY
from src.cache.database import CacheDatabase, cache_paths
from src.cache.web_archive import ArchiveFact, LEGACY_IMPORT, history_rank
from src.cache.web_upgrade import import_web_archive, retire, retire_disposable
from src.reports import web_history_evidence
from src.reports.models import ReportKind, ReportProjection, SessionUsageRow
from src.reports.session_summary import decode_summary, encode_summary

from . import detail_archive
from .projection import project
from .session_catalog_scope import PAGE_SIZE, catalog_window, in_window, row_in_window


LOG = logging.getLogger(__name__)
DOMAIN = 'sessions/1'
LIVE_TAIL_MS = 10 * 60_000


class SessionArchive:
    def __init__(self, storage, legacy=None, *, timezone_id='UTC', upgrade=None):
        self.storage = storage
        self.legacy = legacy
        self.timezone_id = timezone_id
        self.partition = None
        self.rows = {}
        self.authorities = {}
        self.loaded = False
        self.storage_ready = False
        self.upgrade = upgrade
        self.previous_pending = upgrade is not None and upgrade[1] is not None

    def load(self):
        try:
            self.storage.initialize()
            self.storage_ready = True
            return self.read_rows()
        except (sqlite3.Error, OSError):
            LOG.warning('session_archive_read_unavailable')
            return None

    def _import_previous(self, stopping):
        if not self.previous_pending:
            return False
        path = self.upgrade[1]
        try:
            original = import_web_archive(self.storage, path)
        except (sqlite3.Error, OSError):
            LOG.warning('previous_web_history_transfer_incomplete')
            return False
        if not stopping():
            try:
                retire(path, original)
            except OSError:
                LOG.warning('previous_web_history_retirement_pending')
            else:
                self.previous_pending = False
        # Even when retirement is temporarily blocked, committed data can be
        # displayed. Read rows after the attempt, not only after the unlink.
        return original[0] is not None

    def load_legacy(self, stopping):
        from .legacy_history import import_archive
        previous_changed = self._import_previous(stopping)
        retry = self.previous_pending
        try:
            changed = import_archive(self.storage, self.legacy, self.timezone_id, stopping=stopping,
                                     retire_source=self.upgrade is not None)
            if self.upgrade is not None and not stopping():
                root = self.upgrade[0]
                retire_disposable(CacheDatabase(root), cache_paths(root, 2).database)
        except (sqlite3.Error, OSError, TypeError, ValueError):
            LOG.warning('legacy_history_import_incomplete', exc_info=True)
            retry = changed = True  # Some batches may already be committed.
        if (changed or previous_changed) and not stopping():
            try:
                return self.read_rows(legacy_only=not previous_changed), retry
            except (sqlite3.Error, OSError):
                LOG.warning('legacy_history_read_unavailable', exc_info=True)
                retry = True
        return ({}, {}), retry

    @staticmethod
    def prefers(candidate, previous):
        def rank(authority):
            revision, _, _, partition, observed = authority
            return history_rank(partition, observed, revision)
        return rank(candidate) > rank(previous)

    def read_rows(self, *, legacy_only=False):
        decoded, authorities, ranks = {}, {}, {}
        for key, fact in self.storage.history_rows(DOMAIN):
            if legacy_only and not fact.partition.startswith(LEGACY_IMPORT):
                continue
            try:
                row = decode_summary(fact.value['row'])
                if row.session_id != key:
                    continue
            except (AttributeError, KeyError, TypeError, ValueError, InvalidOperation):
                row = recover_summary(key, fact.value.get('row', fact.value))
            if row is None:
                continue
            row = replace(row, running=False)
            prior = decoded.get(key)
            if prior is not None and ranks[key] >= fact.history_rank:
                decoded[key] = retain_readable_fields(prior, row)
            else:
                ranks[key] = fact.history_rank
                decoded[key] = retain_readable_fields(row, prior)
                authorities[key] = (fact.revision, fact.value.get('dependencies'), fact.value.get('models', ()),
                                    fact.partition, fact.observed_ms)
        return decoded, authorities

    def save(self, partition, key, revision, row, observed_ms, dependencies, models, usage, detail):
        try:
            return self.storage.publish_batch(partition, {
                DOMAIN: {key: ArchiveFact(revision, observed_ms, dict(
                    row=encode_summary(row), dependencies=dependencies, models=models))},
                web_history_evidence.DOMAIN: {key: usage},
                detail_archive.DOMAIN: {key: detail},
            })
        except (sqlite3.Error, OSError, ValueError):
            LOG.warning('session_archive_write_unavailable')
            return False


def historical_amount(value):
    try:
        amount = Decimal(value)
        return amount if amount.is_finite() and amount >= 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def historical_int(value, minimum=0):
    return value if type(value) is int and minimum <= value <= 2**53 - 1 else None


def recover_summary(key, value):
    """Decode independently representable scalars without manufacturing zeros."""
    if not isinstance(value, dict) or value.get('session_id', key) != key:
        return None
    title = value.get('title')
    if not isinstance(title, str):
        return None
    model = value.get('model')
    context = historical_int(value.get('context_tokens'))
    return SessionUsageRow(key, title, model if isinstance(model, str) and model else 'N/A',
        value.get('multiple_models') is True, historical_amount(value.get('ccost')),
        historical_int(value.get('prompt_count')), complete=False,
        duration_ms=historical_int(value.get('duration_ms')),
        archived=value.get('archived') is True, last_activity_ms=historical_int(value.get('last_activity_ms'), 1),
        activity_latest_ms=historical_int(value.get('activity_latest_ms'), 1),
        prompt_started_ms=historical_int(value.get('prompt_started_ms'), 1),
        context_tokens=context, context_qualified=False,
        context_detail=(value['context_detail'] if context is not None and isinstance(value.get('context_detail'), str)
                        else 'Session context unavailable.'),
        effort=value['effort'] if isinstance(value.get('effort'), str) else 'N/A',
        effort_qualified=False, model_pending=not model,
        empty_history=value.get('empty_history') is True)


def retain_pending_metrics(row, previous):
    """Display-only last-good fields; pending qualification still blocks sorting."""
    if previous is None:
        return row
    fields = {}
    if not row.context_qualified and row.context_tokens is None:
        fields.update(context_tokens=previous.context_tokens,
            context_detail="Previous same-session Ctx; source acquisition pending.")
    if row.model_pending and row.model == "N/A":
        for name in ("model", "multiple_models", "contributor_models", "main_models", "subagent_models"):
            fields[name] = getattr(previous, name)
    if not row.contributor_models_complete and previous.has_model_details:
        fields["has_model_details"] = True
        if row.linked_agent_count < previous.linked_agent_count:
            fields["linked_agent_count"] = previous.linked_agent_count
            fields["subagent_models"] = previous.subagent_models
    if (row.effort_pending or not row.effort_qualified) and row.effort_key is None:
        for name in ("effort", "effort_key", "effort_contributors", "effort_details_complete"):
            fields[name] = getattr(previous, name)
    return replace(row, **fields)


def retain_readable_fields(new, old):
    if old is None:
        return new
    retain = ('prompt_count', 'duration_ms', 'context_tokens')
    if not new.activity_qualified:
        retain += ('last_activity_ms', 'activity_latest_ms', 'prompt_started_ms')
    fields = {name: getattr(old, name) for name in retain
              if getattr(new, name) is None and getattr(old, name) is not None}
    if new.ccost is None and old.ccost is not None:
        fields.update({name: getattr(old, name) for name in (
            'ccost', 'main_ccost', 'subagent_ccost', 'cost_groups', 'ccost_unavailable')})
    if new.model == 'N/A' and old.model != 'N/A':
        fields.update({name: getattr(old, name) for name in (
            'model', 'multiple_models', 'contributor_models', 'main_models', 'subagent_models',
            'has_model_details', 'selected_display_model')})
    if new.effort == 'N/A' and old.effort != 'N/A':
        fields.update(effort=old.effort, effort_key=old.effort_key, effort_contributors=old.effort_contributors)
    if 'context_tokens' in fields:
        fields.update(context_detail=old.context_detail, context_qualified=False)
    return replace(new, **fields) if fields else new


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
        active = catalog.rows.keys() | catalog.running_roots | catalog.recent_finishes.keys() | catalog._new_live_roots()
        active_rows = catalog._rows(active)
        retained = (row for key, row in archive.rows.items() if key not in active)
        available = {row.session_id: row for row in (*retained, *active_rows)
                     if period == 'all' or row_in_window(row, window, catalog.recent_finishes.get(row.session_id)) or (
                         row.session_id in catalog.recent_arrivals and row.session_id not in catalog.prompt_activity
                         and in_window(catalog.activity.get(row.session_id), window))}
        rows = ordered(available.values(), sort, direction, catalog.recent_finishes)
        catalog.orders[cache_key] = rows
        while len(catalog.orders) > 24:
            catalog.orders.popitem(last=False)
    offset = min(offset, max(0, (len(rows) - 1) // PAGE_SIZE) * PAGE_SIZE)
    shown = rows[offset:offset + PAGE_SIZE]
    lease['visible'] = tuple(row.session_id for row in shown)
    view = session_view(shown, catalog.timezone_id, catalog.unit)
    for value, row in zip(view['session_usage'], shown):
        key = row.session_id
        saved = key in archive.rows or key in catalog.rows
        current = key in catalog.roots and catalog._current(key)
        value['indexed'] = saved
        value['has_summary'] = saved
        value['new_arrival'] = key in catalog.recent_arrivals and key not in catalog.prompt_activity and not saved
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
    live = catalog.history_live_roots()
    # The recent tail is not a substitute for coverage on a cold cache. It
    # only suppresses the spinner for rows whose activity is already known.
    missing = any(key not in live and (at is None or in_window(at, window)) and (
        at is None or at < cutoff or not catalog._activity_current(key))
        for key, at in pending.items())
    complete = archive.loaded and catalog.observed is not None and not missing
    unavailable = sum(key not in live and (catalog.activity.get(key) is None or
                      in_window(catalog.activity.get(key), window))
                      for key in catalog.unavailable_history())
    # A storage outage is not proof of a zero-sized archive. The independent
    # legacy import reports pending until its first attempt can inventory it.
    restoring = not archive.loaded and catalog.archive_retry_at == 0
    importing = archive.loaded and archive.legacy is not None and not catalog.legacy_done
    recovering = not archive.loaded and not restoring or importing and catalog.legacy_retry_at > catalog.clock()
    progress = dict(cached=cached if archive.loaded or cached else None, complete=bool(complete and not importing),
                    remaining=None, unavailable=unavailable, recovering=recovering)
    return dict(cache_first=True, token=token, epoch=lease['cache_epoch'], offset=offset, total=len(rows),
                 size=PAGE_SIZE, page_reused=True, retained_order=False, membership_pending=not progress['complete'],
                candidate_navigation=True, order_state='verified', state='observed', period=period,
                sort=sort, direction=direction, pending_sort=False, indexed=cached,
                navigation=navigation, history_progress=progress, view=view,
                source=dict(identity='shared-history'))


def session_view(rows, zone, unit):
    report = ReportProjection(ReportKind.SESSIONS, 'Sessions', 'OpenCode', (), session_usage=rows)
    return project(report, zone, unit).to_json()
