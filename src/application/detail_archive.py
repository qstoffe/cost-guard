"""Persist completed detail projections without native snapshots or raw tool data."""
import logging
import sqlite3

from src.cache.web_archive import ArchiveFact

from .projection import identity, project
from .session_activity import activity_summary


LOG = logging.getLogger(__name__)
DOMAIN = 'detail/1'


def save_detail(archive, partition, key, revision, report, metadata):
    if not partition or not isinstance(revision, str):
        return False
    block, = report.prompt_blocks
    if any(row.in_progress for row in block.rows) or not (metadata['activity'] or {}).get('complete'):
        return False
    view = project(report, metadata['timezone_id'], metadata['ccost_display_unit'], prompt_details=True).to_json()
    for row in view['prompt_blocks'][0]['rows']:
        row['id'] = identity((key, row['event_id'], row['is_compaction']))
        row['last_observed_at_ms'] = metadata['row_observations'].get(row['event_id'])
        row['retained'] = row['event_id'] in metadata['omitted_ids']
    observed = metadata['observed_at_ms']
    try:
        archive.publish(partition, DOMAIN, {key: ArchiveFact(revision, observed, dict(
            view=view, activity=metadata['activity'], value_authority=metadata['value_authority']))})
    except (sqlite3.Error, OSError, ValueError):
        LOG.warning('detail_archive_write_unavailable')
        return False
    return True


def load_detail(archive, partition, key):
    try:
        fact = archive.read(partition, DOMAIN, item=key).get(key)
        if fact and fact.value['view']['prompt_blocks'][0]['session_id'] == key:
            return fact
    except (sqlite3.Error, OSError, KeyError, IndexError, TypeError):
        LOG.warning('detail_archive_read_unavailable')
    return None


def archived_page(fact, revision, offset, anchor, *, mode, begin, chunk, acquisition):
    payload = fact.value
    view = payload['view']
    block, = view['prompt_blocks']
    rows = block['rows']
    cache_revision = identity(('durable-history', fact.revision, fact.observed_ms))
    stale = revision is not None and revision != cache_revision
    if chunk and stale:
        raise KeyError('detail_expired')
    if stale and anchor:
        offset = next((i for i, row in enumerate(rows) if row['id'] == anchor), offset)
    offset = (max(0, len(rows) - 50) if offset >= 2**52 else
              max(0, min(offset, max(0, len(rows) - 1))))
    shown = rows[offset:offset + (25 if begin or chunk else 50)]
    view = {**view, 'prompt_blocks': [{**block, 'rows': shown}]}
    authority = payload['value_authority']
    if authority is not None:
        authority = {**authority, 'rows': {row['event_id']: authority['rows'].get(row['event_id']) for row in shown}}
    return dict(state='observed', pending=False, revision=cache_revision, stale_cursor=stale, offset=offset,
                total=len(rows), mode=mode, value_authority=authority, values_invalidated=False,
                export_available=False, acquisition=acquisition,
                **(dict(activity=activity_summary(payload['activity']), quota_usage=None) if not chunk else {}),
                **(dict(activity_refresh=None, activity_revision=cache_revision) if begin else {}),
                result=dict(observed_at_ms=fact.observed_ms, view=view,
                            source=dict(status='acquired', atomicity='per_root_snapshot')))
