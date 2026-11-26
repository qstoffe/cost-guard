"""Persist completed detail projections without native snapshots or raw tool data."""
import logging
import sqlite3

from src.cache.web_archive import ArchiveFact
from src.cache.prompt_range import DETAIL_DOMAIN as DOMAIN

from .projection import identity, project
from .session_activity import ActivityHistory, activity_summary
from .session_values import value_authority


LOG = logging.getLogger(__name__)


def detail_fact(key, revision, report, metadata, *, projection=None):
    if not isinstance(revision, str):
        return None
    block, = report.prompt_blocks
    if any(row.in_progress or row.execution_unverified for row in block.rows) or not (metadata['activity'] or {}).get('complete'):
        return None
    return ArchiveFact(revision, metadata['observed_at_ms'],
                       projection if projection is not None else detail_projection(key, report, metadata))


def detail_projection(key, report, metadata):
    view = project(report, metadata['timezone_id'], metadata['ccost_display_unit'], prompt_details=True).to_json()
    for row in view['prompt_blocks'][0]['rows']:
        row['id'] = identity((key, row['event_id'], row['is_compaction']))
        row['last_observed_at_ms'] = metadata['row_observations'].get(row['event_id'])
        row['retained'] = row['event_id'] in metadata['omitted_ids']
    return dict(view=view, activity=metadata['activity'], value_authority=metadata['value_authority'])


def save_detail(archive, partition, key, revision, report, metadata, *, projection=None):
    if not partition:
        return False
    fact = detail_fact(key, revision, report, metadata, projection=projection)
    if fact is None:
        return False
    try:
        return archive.publish(partition, DOMAIN, {key: fact})
    except (sqlite3.Error, OSError, ValueError):
        LOG.warning('detail_archive_write_unavailable')
        return False


def acquired_detail(service, item):
    """Reuse a qualified background capture rather than acquiring the tree twice."""
    root, snapshot = item.session, item.snapshot
    block = service._prompt_block(item, snapshot_running_metrics=True)
    history = ActivityHistory()
    history.snapshot = history.fresh_snapshot = snapshot
    history.report = service.session_detail_projection(root.session_id, root, block)
    metadata = dict(
        timezone_id=service.timezone_id, ccost_display_unit=service.config.get('ccostDisplayUnit', 'credits'),
        activity=history.activity_for(service.source, block.rows), value_authority=value_authority(history, service.source),
        row_observations={row.event_id: service.now_ms for row in block.rows},
        omitted_ids=frozenset(), observed_at_ms=service.now_ms,
    )
    return detail_fact(root.session_id, item.bundle.source_revision, history.report, metadata)


def refresh_detail(archive, key, previous=(0, None)):
    try:
        cursor, candidates = archive.history_item(DOMAIN, key, previous[0])
        value = readable_detail(key, (fact for _, fact in candidates))
        return (cursor, value) if value else previous
    except (sqlite3.Error, OSError, KeyError, IndexError, TypeError, ValueError):
        LOG.warning('detail_archive_read_unavailable')
    return previous


def load_detail(archive, key):
    return refresh_detail(archive, key)[1]


def readable_detail(key, candidates):
    readable = []
    for fact in candidates:
        try:
            block, = fact.value['view']['prompt_blocks']
            if block['session_id'] == key and isinstance(block['rows'], list):
                readable.append(fact)
        except (KeyError, TypeError, ValueError):
            continue
    return _reconcile(key, readable) if readable else None


def _reconcile(key, candidates):
    winner, *retained = candidates
    if not retained:
        return winner
    value = winner.value
    view = value['view']
    block, = view['prompt_blocks']
    rows = {}
    for fact in candidates:
        original, = fact.value['view']['prompt_blocks']
        for row in original['rows']:
            if not isinstance(row, dict) or not isinstance(row.get('event_id'), str) or not row['event_id']:
                continue
            event = row['event_id'], row.get('is_compaction') is True
            if event not in rows:
                # Neither a retained Running flag nor an unverified old start is
                # allowed to acquire current execution authority.
                rows[event] = {**row, 'id': identity((key, *event)), 'in_progress': False,
                               'retained': fact is not winner or row.get('retained', False)}
            else:
                rows[event] = _fill_display(rows[event], row, (
                    'at_ms', 'completed_at_ms', 'duration_ms', 'ccost', 'calls', 'incoming_context_tokens',
                    'incoming_context_ccost', 'extra_ccost', 'token_mix_percent', 'watch_model', 'watch_effort'))
        if fact is not winner:
            block = _fill_display(block, original, ('total_ccost', 'total_calls', 'duration_ms',
                                  'total_incoming_context_ccost', 'total_extra_ccost', 'total_token_mix_percent'))
    ordered = sorted(rows.values(), key=lambda row: (-(row.get('at_ms') or 0), row['event_id']))
    reconciled = {**value, 'view': {**view, 'prompt_blocks': [{**block, 'rows': ordered}]}}
    authority = value.get('value_authority') or {}
    reconciled['value_authority'] = {
        'scope': identity(('shared-history', key)),
        'rows': {row['event_id']: 'known' if row.get('token_mix_percent') is not None else
                 'unavailable' for row in ordered},
        'totals': {**authority.get('totals', {}), **{name: 'known' for name in (
            'total_ccost', 'total_calls', 'duration_ms', 'total_incoming_context_ccost',
            'total_extra_ccost', 'total_token_mix_percent') if block.get(name) is not None}},
    }
    revision = identity(tuple((item.partition, item.revision, item.observed_ms) for item in candidates))
    return ArchiveFact(revision, winner.observed_ms, reconciled, winner.partition)


def _fill_display(current, old, names):
    fields = {name: old[name] for name in names
              if current.get(name) in (None, '', 'N/A') and old.get(name) not in (None, '', 'N/A')}
    if not fields:
        return current
    def merge(values, former):
        return {**values, **{name: former[name] for name in fields if name in former}}
    old_units = old.get('display_units') or {}
    return {**current, **fields, 'display': merge(current.get('display') or {}, old.get('display') or {}),
            'display_units': {unit: merge(values, old_units.get(unit, {}))
                              for unit, values in (current.get('display_units') or {}).items()}}


def archived_page(fact, revision, offset, anchor, *, mode, begin, chunk, acquisition, runtime=None, size=None):
    payload = fact.value
    view = payload['view']
    block, = view['prompt_blocks']
    rows = block['rows']
    cache_revision = detail_revision(fact, runtime)
    stale = revision is not None and revision != cache_revision
    if chunk and stale:
        raise KeyError('detail_read_stale')
    if stale and anchor:
        offset = next((i for i, row in enumerate(rows) if row['id'] == anchor), offset)
    offset = (max(0, len(rows) - 50) if offset >= 2**52 else
              max(0, min(offset, max(0, len(rows) - 1))))
    shown = rows[offset:offset + (size or (25 if begin or chunk else 50))]
    view = {**view, 'prompt_blocks': [{**block, 'rows': shown}]}
    authority = payload.get('value_authority')
    if authority is not None:
        authority = {**authority, 'rows': {row['event_id']: authority['rows'].get(row['event_id']) for row in shown}}
    active = runtime is not None
    refresh = runtime.get('activity_refresh') if active and mode == 'live' else None
    export = bool(active and runtime['export_available'] and not chunk)
    return dict(cache_first=True, state=runtime['state'] if active else 'observed',
                 pending=False, revision=cache_revision, stale_cursor=stale, offset=offset,
                 total=len(rows), mode=mode, value_authority=authority, values_invalidated=False,
                 export_available=export, acquisition=acquisition,
                 **(dict(activity=activity_summary(payload.get('activity')),
                         quota_usage=runtime['quota_usage'] if active else None) if not chunk else {}),
                 **(dict(activity_refresh=refresh,
                         activity_revision=runtime.get('activity_revision') or cache_revision if active
                             else cache_revision) if begin else {}),
                 result=dict(observed_at_ms=fact.observed_ms, view=view,
                              source=dict(status='acquired' if active and runtime['state'] == 'observed' else 'partial',
                                          identity='shared-history', atomicity='cached_projection')))


def detail_revision(fact, runtime):
    return runtime['revision'] if runtime is not None else identity(('durable-history', fact.revision, fact.observed_ms))
