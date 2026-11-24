"""Session display persistence and pagination over the ready subset."""
from dataclasses import replace
from decimal import Decimal, InvalidOperation
import json
import logging
import sqlite3
from uuid import uuid4

from src.analysis.metric_evidence import EMPTY_HISTORY
from src.cache.database import CacheDatabase, cache_paths
from src.cache.session_projection import SESSIONS_DOMAIN, SORT_COLUMNS
from src.cache.web_archive import ArchiveFact, LEGACY_IMPORT, history_rank
from src.cache.web_upgrade import import_web_archive, retire, retire_disposable
from src.reports import web_history_evidence
from src.reports.models import ReportKind, ReportProjection, SessionUsageRow
from src.reports.session_summary import decode_summary, encode_summary

from . import detail_archive
from .projection import project
from .session_catalog_scope import PAGE_SIZE, catalog_window


LOG = logging.getLogger(__name__)
DOMAIN = SESSIONS_DOMAIN


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
        self.run = uuid4().hex
        self.upgrade = upgrade
        self.previous_pending = upgrade is not None and upgrade[1] is not None

    def needs_capture(self, key, revision, target, activity, changed):
        old = self.authorities.get(key)
        if old is None or changed and (old[0] != revision or old[3] != target) or activity > old[4]:
            return True
        # A new database can use a different revision encoding for the very
        # same roots. Existing history is not replayed solely for that reason.
        return old[0] != revision and old[3] == target

    def refresh_roots(self, pending, target):
        """Previously acquired roots that need refresh, not historical membership."""
        return {key for key in pending
                if (saved := self.authorities.get(key)) is not None and saved[3] == target
                and (row := self.rows.get(key)) is not None and row.activity_qualified}

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
        from .session_epoch_page import sort_value

        try:
            return self.storage.publish_session(partition, {
                DOMAIN: {key: ArchiveFact(revision, observed_ms, dict(
                    row=encode_summary(row), dependencies=dependencies, models=models))},
                web_history_evidence.DOMAIN: {key: usage},
                detail_archive.DOMAIN: {key: detail},
            }, key, {sort: sort_value(row, sort) for sort in SORT_COLUMNS},
                row.last_activity_ms, row.activity_latest_ms, run=self.run)
        except (sqlite3.Error, OSError, ValueError):
            LOG.warning('session_archive_write_unavailable')
            return False

    def update_runtime(self, *, state, terminal, reset_pending, pending, live):
        values = {key: (start, finish, row.last_activity_ms, row.activity_latest_ms,
                        json.dumps(encode_summary(row), separators=(',', ':')))
                  if entry is not None else None
                  for key, entry in live.items()
                  for row, start, finish in (entry or (None, None, None),)}
        try:
            self.storage.update_sessions_runtime(self.run, state=state, terminal=terminal,
                reset_pending=reset_pending, pending=pending, live=values)
            return True
        except (sqlite3.Error, OSError):
            LOG.warning('session_runtime_write_unavailable')
            return False

    def close_runtime(self):
        if self.storage_ready:
            try:
                self.storage.close_sessions_runtime(self.run)
            except (sqlite3.Error, OSError):
                LOG.warning('session_runtime_close_unavailable')


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


def _display_row(key, data, *, provisional=False):
    try:
        row = decode_summary(data, provisional=provisional)
        return row if row.session_id == key else None
    except (AttributeError, KeyError, TypeError, ValueError, InvalidOperation):
        return recover_summary(key, data)


def cached_page(archive, *, token, offset, sort, direction, period, navigation, now, zone, unit, finish_grace):
    """One committed snapshot for ready rows, Live overlays and period coverage."""
    window = catalog_window(period, zone, now)
    try:
        total, offset, facts, live, cached, runtime, pending = archive.storage.sessions_page(
            offset=offset, size=PAGE_SIZE, sort=sort, direction=direction, start_ms=window.start_ms,
            end_ms=window.end_ms, run=archive.run, finish_cutoff=now - finish_grace + 1)
    except (sqlite3.Error, OSError):
        total, offset, facts, live, cached, runtime, pending = 0, 0, (), (), None, ('cache_recovering', False), (False, 0)
    shown = []
    for key, payload, running_since, _, saved in live:
        row = _display_row(key, json.loads(payload), provisional=running_since is not None)
        if row is not None:
            shown.append((replace(row, running=running_since is not None), bool(saved)))
    for key, fact in facts:
        row = _display_row(key, fact.value.get('row'))
        if row is not None:
            shown.append((replace(row, running=False), True))
    view = session_view(tuple(row for row, _ in shown), zone, unit)
    for value, (row, saved) in zip(view['session_usage'], shown):
        value['indexed'] = saved
        value['has_summary'] = saved
        value['new_arrival'] = False
        value['catalog_activity_ms'] = None
        value['activity_state'] = 'ready' if row.running or row.last_activity_ms is not None else 'unavailable'
        value['metric_state'] = 'pending' if row.running and not saved else 'ready'
        value['metric_states'] = dict.fromkeys(('model', 'effort', 'ccost', 'prompts', 'duration', 'ctx'),
                                                value['metric_state'])
        if row.running:
            for key, known in (
                ('model', not row.model_pending and row.model != 'N/A'), ('effort', row.effort_key is not None),
                ('ccost', row.ccost is not None), ('prompts', row.prompt_count is not None),
                ('duration', row.duration_ms is not None), ('ctx', row.context_tokens is not None),
            ):
                value['metric_states'][key] = 'ready' if known else 'pending'
        if row.empty_history and saved and not row.running:
            value['metric_absences'] = dict.fromkeys(('model', 'ctx', 'activity'), EMPTY_HISTORY)
    state, terminal = runtime or ('loading', False)
    complete, unavailable = pending
    progress = dict(cached=cached, complete=state == 'observed' and complete and not terminal,
                    remaining=None, unavailable=unavailable,
                    recovering=state in ('source_unavailable', 'cache_recovering') and not terminal,
                    terminal=bool(terminal))
    return dict(cache_first=True, cache_events=archive.storage.notify_sessions is not None,
                token=token or uuid4().hex, epoch=archive.run, offset=offset, total=total,
                size=PAGE_SIZE, page_reused=True, retained_order=False,
                membership_pending=not progress['complete'] or bool(unavailable), candidate_navigation=True,
                order_state='verified', state='observed', period=period, sort=sort, direction=direction,
                pending_sort=False, indexed=cached, navigation=navigation, history_progress=progress,
                view=view, source=dict(identity='shared-history'))


def session_view(rows, zone, unit):
    report = ReportProjection(ReportKind.SESSIONS, 'Sessions', 'OpenCode', (), session_usage=rows)
    return project(report, zone, unit).to_json()
