"""Bounded ephemeral compact facts, shared only across owned Web report jobs.

The host keeps one payload for at most a minute. Reuse never skips live catalog,
root revision or model identity verification, and never contains transcripts.
"""
import json
import time

from src.analysis.cache import dependency_signature
from src.analysis.timezones import format_local_timestamp

MAX_BYTES = 16 * 1024 * 1024
MAX_FACTS = 250_000
MAX_ROOTS = 100_000
MAX_AGE = 60


def signature(service, reference):
    return dependency_signature((service.selection.selected,
        service._dependencies(service._load_catalog()), reference.analysis_signature,
        service.timezone_id, format_local_timestamp(service.now_ms, service.timezone_id, "%Y-%m-%d")))


def qualified(value, key):
    return (isinstance(value, dict) and value.get('signature') == key
            and 0 <= time.monotonic() - value.get('created', 0) < MAX_AGE)


def publish(service, key, roots):
    if len(roots) > MAX_ROOTS or sum(len(item['payload']) for item in roots.values()) > MAX_FACTS:
        service.token_mix_reuse = None
        return
    value = dict(signature=key, created=time.monotonic(), roots=roots)
    payload = json.dumps(value, separators=(',', ':'), ensure_ascii=True).encode('ascii')
    if len(payload) > MAX_BYTES:
        service.token_mix_reuse = None
        return
    service.token_mix_reuse = value
    callback = getattr(service, 'publish_token_mix_reuse', None)
    if callback:
        callback(payload)
