"""Read the FR000778 display store without acquiring or writing OpenCode data."""
from contextlib import closing
from decimal import Decimal
import json
import logging
import re
import sqlite3

from src.analysis.cache import dependency_signature
from src.cache.web_archive import ArchiveFact, LEGACY_IMPORT
from src.cache.web_upgrade import retire, snapshot_stamp
from src.reports.models import PromptProjection, ReportKind, ReportProjection, SessionPromptBlock
from src.reports.web_history_evidence import DOMAIN as USAGE

from .detail_archive import DOMAIN as DETAIL
from .projection import identity, project
from .session_archive import DOMAIN as SESSIONS, historical_amount, historical_int


APPLICATION_ID = 0x43474448
VERSION = 1
LEDGER = 'legacy-import/1'
BATCH_SIZE = 32
SESSION_ID = re.compile(r'[A-Za-z0-9_-]{1,200}')
LOG = logging.getLogger(__name__)
UNREADABLE = (AttributeError, IndexError, KeyError, TypeError, ValueError, OverflowError)


def import_archive(archive, path, zone, *, stopping=lambda: False, retire_source=False):
    if retire_source and (path.is_symlink() or path.is_file() and path.samefile(archive.path)):
        raise OSError('old display store aliases destination')
    original = snapshot_stamp(path)
    if original[0] is None:
        if retire_source and not stopping():
            retire(path, original)
        return
    stamp = dependency_signature((VERSION, *original[0], original[1]))
    if archive.import_checkpoint(LEDGER, 'snapshot') == stamp:
        if retire_source and not stopping():
            retire(path, original)
        return
    with closing(sqlite3.connect(path.absolute().as_uri() + '?mode=ro', uri=True, timeout=0.2)) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        if (db.execute('PRAGMA application_id').fetchone()[0],
                db.execute('PRAGMA user_version').fetchone()[0]) != (APPLICATION_ID, VERSION):
            supported = False
        else:
            supported = True
        db.row_factory = sqlite3.Row
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_schema WHERE type IN ('table', 'view')")}
        sessions = db.execute('SELECT * FROM sessions ORDER BY source, session_id') if supported and 'sessions' in tables else None
        while sessions is not None and not stopping() and (batch := sessions.fetchmany(BATCH_SIZE)):
            partitions = {}
            for row in batch:
                key = row['session_id']
                if not isinstance(key, str) or not SESSION_ID.fullmatch(key):
                    continue
                part = LEGACY_IMPORT + ':' + dependency_signature(row['source'])
                result = partitions.setdefault(part, {SESSIONS: {}, DETAIL: {}, USAGE: {}})
                evidence = _summary(dict(row))
                # The old scalar table did not record a capture clock. Use the
                # newest known history clock, not import time, for overlap detection.
                at = max((evidence.get(name) or 0 for name in (
                    'last_activity_ms', 'activity_latest_ms', 'prompt_started_ms')), default=0)
                revision = str(row['revision'])
                result[SESSIONS][key] = ArchiveFact(revision, at, dict(row=evidence))
                if {'archive_prompt_history', 'archive_prompt_state'} <= tables:
                    try:
                        detail = _detail(db, row, evidence, zone)
                    except UNREADABLE:
                        LOG.debug('legacy_detail_unreadable')
                    else:
                        if detail is not None:
                            result[DETAIL][key] = ArchiveFact(revision, at, detail)
                if {'archive_requests', 'archive_request_rosters', 'archive_request_membership',
                    'archive_countable_requests'} <= tables:
                    try:
                        usage = _usage(db, tables, row)
                    except UNREADABLE:
                        LOG.debug('legacy_usage_unreadable')
                    else:
                        if usage is not None:
                            result[USAGE][key] = ArchiveFact(revision, at, usage)
            for partition, domains in partitions.items():
                archive.import_batch(partition, domains)
    # Finish only after every bounded publication. A changed source file is
    # eligible again, and repeated batches update identities rather than add rows.
    if not stopping() and snapshot_stamp(path) == original:
        archive.record_import_checkpoint(LEDGER, 'snapshot', stamp)
        if retire_source:
            if archive.import_checkpoint(LEDGER, 'snapshot') != stamp:
                raise sqlite3.DatabaseError('legacy transfer checkpoint not readable')
            # Read the newly committed representation, not merely a writer's
            # successful return. Unsupported fields may legitimately be absent.
            with archive._connect() as verified:
                verified.execute('SELECT value FROM facts WHERE domain=? LIMIT 1', (SESSIONS,)).fetchone()
            retire(path, original)
    elif not stopping() and retire_source:
        raise OSError('legacy history changed during import')
    return True


def _summary(row):
    value = dict(session_id=row['session_id'], title=row['title'])
    mask = row.get('field_evidence')
    # Bit assignments are the old disk format, not the new DTO ordering.
    for bit, (old, new) in enumerate((
            ('activity_ms', 'last_activity_ms'), ('model', 'model'), ('ccost', 'ccost'),
            ('prompts', 'prompt_count'), ('duration_ms', 'duration_ms'), ('context_tokens', 'context_tokens'),
            ('latest_activity_ms', 'activity_latest_ms'), ('prompt_started_ms', 'prompt_started_ms'),
            ('activity_origin', 'activity_origin'), ('catalog_activity_ms', 'catalog_activity_ms'),
            ('unused', 'unused'), ('context_detail', 'context_detail'), ('model_help', 'model_help'),
            ('has_model_details', 'has_model_details'))):
        if row.get(old) is not None and (type(mask) is not int or mask & (1 << bit)):
            value[new] = row[old]
    if type(mask) is int and mask & (1 << 10):
        value['empty_history'] = True
    return value


def _mix(raw):
    try:
        mix = tuple(int(part) for part in raw.split(','))
        return mix if len(mix) == 4 and all(0 <= part <= 100 for part in mix) else None
    except (AttributeError, ValueError):
        return None


def _prompt(raw):
    cost = historical_amount(raw['observed_cost'])
    incoming = historical_amount(raw['incoming_cost'])
    extra = historical_amount(raw['extra_cost'])
    outcome = raw['outcome']
    return PromptProjection(at_ms=historical_int(raw['start_ms'], 1) or 0,
        prompt_number=historical_int(raw['number']), label='Prompt', preview='',
        model_effort=raw['model'] or 'N/A', ccost=cost, cost_estimated=False,
        unresolved_cost=not raw['cost_complete'], calls=historical_int(raw['calls']),
        incoming_context_tokens=historical_int(raw['context_tokens']), incoming_context_ccost=incoming,
        extra_ccost=extra, token_mix_percent=_mix(raw['mix']), event_id=raw['event_id'],
        duration_ms=historical_int(raw['duration_ms']), watch_model=raw['model'] or '',
        watch_effort=raw['effort'] or '', completed_at_ms=historical_int(raw['finish_ms'], 1),
        is_compaction=raw['kind'] == 'compaction', aborted=outcome == 'aborted',
        watch_error=outcome == 'failed', completed_successfully=outcome == 'finished',
        execution_unverified=outcome == 'unverified', incoming_context_ccost_known=incoming is not None,
        extra_ccost_known=extra is not None)


def _detail(db, row, evidence, zone):
    binding = row['source'], row['session_id']
    if db.execute('SELECT 1 FROM archive_prompt_state WHERE source=? AND root_id=?', binding).fetchone() is None:
        return None
    prompts = []
    for raw in db.execute('''SELECT * FROM archive_prompt_history
                          WHERE source=? AND root_id=? ORDER BY start_ms DESC, event_id''', binding):
        try:
            prompts.append(_prompt(raw))
        except UNREADABLE:
            continue
    cost = historical_amount(evidence.get('ccost'))
    calls = sum(prompt.calls for prompt in prompts) if prompts and all(prompt.calls is not None for prompt in prompts) else None
    block = SessionPromptBlock(row['session_id'], row['title'], tuple(prompts), cost or Decimal(0), calls,
        duration_ms=historical_int(evidence.get('duration_ms')), comparison_cost_complete=cost is not None,
        rate_usage_complete=False, rate_provisional=True)
    report = ReportProjection(ReportKind.SESSIONS, 'Session detail', 'OpenCode', (), prompt_blocks=(block,))
    view = project(report, zone, prompt_details=True).to_json()
    block_json, = view['prompt_blocks']
    if cost is None:
        block_json['total_ccost'] = None
        for display in (block_json['display'], *block_json['display_units'].values()):
            display['total_ccost'] = 'N/A'
    for item in block_json['rows']:
        item['id'] = identity((row['session_id'], item['event_id'], item['is_compaction']))
        item['retained'] = True
    return dict(view=view, activity=None, value_authority=None)


def _usage(db, tables, row):
    binding = row['source'], row['session_id']
    if db.execute('SELECT 1 FROM archive_request_rosters WHERE source=? AND root_id=?', binding).fetchone() is None:
        return None
    rows = []
    for raw in db.execute('''SELECT r.* FROM archive_request_membership AS m
        JOIN archive_requests AS r USING (source, request_key)
        JOIN archive_countable_requests AS c USING (source, request_key)
        WHERE m.source=? AND m.root_id=? ORDER BY r.clock_ms, r.request_key''', binding):
        value = dict(raw)
        for name in ('request_key', 'fork_key', 'account_key'):
            value[name] = value[name].hex() if isinstance(value.get(name), bytes) else None
        rows.append(value)
    attribution = {}
    if 'archive_prompt_attribution' in tables:
        for request, prompt in db.execute('''SELECT request_key, prompt_id FROM archive_prompt_attribution
                WHERE source=? AND root_id=? ORDER BY request_key, prompt_id''', binding):
            if isinstance(request, bytes):
                attribution.setdefault(request.hex(), []).append(prompt)
    intervals = []
    if 'archive_stats_intervals' in tables:
        intervals = [list(item) for item in db.execute('''SELECT start_ms, duration_ms, provisional
                     FROM archive_stats_intervals WHERE source=? AND root_id=?''', binding)]
    parents = []
    if 'archive_stats_parents' in tables:
        parents = [list(item) for item in db.execute('''SELECT session_id, parent_id FROM archive_stats_parents
                   WHERE source=? AND root_id=?''', binding)]
    return dict(title=row['title'], legacy_requests=rows, legacy_attribution=attribution,
                legacy_intervals=intervals, legacy_parents=parents)
