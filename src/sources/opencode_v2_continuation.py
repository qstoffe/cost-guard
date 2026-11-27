"""Current V2 automations; export only qualified ownership and trigger data."""
import time
from collections.abc import Mapping

from src.domain.models import ONGOING_EVIDENCE_GRACE_MS, ScheduledContinuation
from .errors import SourceError


def _stamp(value):
    return value if type(value) is int and 0 < value < 253402300800000 else None


def scheduled_continuations(client):
    try:
        response = client.json('/api/experimental/automation', phase='continuation')
    except SourceError:
        return None
    data = response.get('data') if isinstance(response, Mapping) else None
    if not isinstance(data, list):
        return None
    records = [item for item in data if isinstance(item, Mapping)
               and isinstance(item.get('id'), str) and item['id']]
    if len(records) != len(data) or len({item['id'] for item in records}) != len(records):
        return None
    now_ms = time.time_ns() // 1_000_000
    pending = []
    for item in records:
        status, runs = item.get('status'), item.get('runCount')
        if status not in ('active', 'paused', 'done') or type(runs) is not int or runs < 0:
            return None
        session = item.get('sessionID')
        action = item.get('action')
        target = action.get('to') if isinstance(action, Mapping) and action.get('type') == 'prompt' else None
        if not isinstance(session, str) or not session or target != {'session': session}:
            continue
        timing = item.get('time')
        created = _stamp(timing.get('created')) if isinstance(timing, Mapping) else None
        trigger = item.get('trigger')
        kind = trigger.get('type') if isinstance(trigger, Mapping) else None
        if created is None or kind not in ('at', 'every', 'cron', 'event'):
            return None
        expires = _stamp(item.get('expires'))
        if runs == 0 and status == 'active' and (expires is None or now_ms < expires):
            due = _stamp(item.get('nextDueAt')) if kind != 'event' else None
            pending.append(ScheduledContinuation(session, created, due,
                'An automatic event' if kind == 'event' else 'A scheduled continuation'))
        elif runs == 1 and status != 'paused':
            fired = _stamp(item.get('lastRunAt'))
            if (fired is not None and 0 <= now_ms - fired < ONGOING_EVIDENCE_GRACE_MS
                    and item.get('lastOutcome') not in ('skipped', 'failed', 'disabled', 'expired')):
                # The service can record delivery before the prompt appears in
                # history. Allow a bounded handoff, without naming an inbox item.
                pending.append(ScheduledContinuation(session, created, None,
                    'Delivery of the automatic continuation', dispatched_ms=fired))
    return tuple(pending)
