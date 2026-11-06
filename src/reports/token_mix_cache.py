"""Web-only, revision-keyed minimal history evidence; never durable user history.

Unchanged roots reuse compact request facts and their canonical category valuation,
not hydrated snapshots or verbose derived prompt records. Global clone deduplication
and grouping still belong to token_mix_history. Deleted roots are never read back.
"""
from decimal import Decimal, InvalidOperation
import sqlite3

from src.analysis.cache import dependency_signature
from src.analysis.models import TraceEntry
from src.cache.repository import CacheEntry
from src.domain import ModelRef, TokenUsage
from src.domain.progress import WorkProgress
from .token_mix_history import history_projection

ALGORITHM = 'web-token-mix-evidence-1'
NAMESPACE = 'web-token-mix-evidence'
BATCH_SIZE = 64


def cache_key(service, root, reference):
    provenance = root.provenance
    return dependency_signature((ALGORITHM, provenance.source_type, provenance.source_generation,
        provenance.source_instance, root.session_id, service._dependencies(service._load_catalog()),
        reference.analysis_signature))


def encode(bundle, reference):
    prompts = {}
    for prompt in bundle.prompts:
        for entry in prompt.entries:
            prompts.setdefault(entry, (prompt.session_id, prompt.prompt_id))
    facts = []
    for entry in bundle.trace_entries:
        tokens = entry.tokens
        costs = reference.reference_category_valuation(entry.model, tokens) if tokens.total else (Decimal(0),) * 4
        facts.append(dict(session=entry.session_id, parent=entry.parent_event_id, message=entry.message_id,
            part=entry.step_part_id, completed=entry.completed_at_ms, order=entry.sort_order,
            model=[entry.model.provider, entry.model.model, entry.model.display_name], variant=entry.variant,
            tokens=[tokens.input, tokens.cache_read, tokens.cache_write, tokens.output, tokens.reasoning],
            known=list(tokens.known_fields), reported=str(entry.reported_cost), instance=entry.source_instance,
            prompt=prompts.get(entry), costs=None if costs is None else [str(value) for value in costs]))
    return facts


def decode(facts):
    result = []
    if not isinstance(facts, list):
        raise ValueError('invalid_evidence')
    for fact in facts:
        counts = fact['tokens']
        if len(counts) != 5 or any(type(value) is not int or value < 0 for value in counts):
            raise ValueError('invalid_tokens')
        tokens = TokenUsage(input=counts[0], cache_read=counts[1], cache_write=counts[2],
            output=counts[3], reasoning=counts[4], known_fields=tuple(fact['known']))
        entry = TraceEntry(fact['session'], fact['parent'], fact['message'], fact['part'],
            fact['completed'], fact['order'], ModelRef(*fact['model']), fact['variant'], tokens,
            reported_cost=Decimal(fact['reported']), source_instance=fact['instance'])
        costs = None if fact['costs'] is None else tuple(Decimal(value) for value in fact['costs'])
        if costs is not None and (len(costs) != 4 or any(not value.is_finite() or value < 0 for value in costs)):
            raise ValueError('invalid_costs')
        prompt = None if fact['prompt'] is None else tuple(fact['prompt'])
        result.append((entry, prompt, costs))
    return result


def load(cached, revision):
    try:
        if cached is not None and cached.source_revision == revision and cached.algorithm_version == ALGORITHM:
            return decode(cached.payload)
    except (OSError, sqlite3.Error, KeyError, TypeError, ValueError, InvalidOperation):
        pass
    return None


def build_cached_token_mix(service, progress):
    progress(WorkProgress('Loading pricing catalog', 'pricing'), None)
    reference = service._load_comparison_catalog()
    progress(WorkProgress('Checking history revisions', 'catalog'), None)
    roots = [root for root in service.source.list_sessions() if root.parent_session_id is None]
    keys = {root.session_id: cache_key(service, root, reference) for root in roots}
    try:
        cached = service.cache_repository.get_many(NAMESPACE, keys.values(), busy_timeout_ms=50)
    except (OSError, sqlite3.Error):
        cached = {}
    entries, prompts, costs = [], {}, {}
    pending = []

    def include(facts):
        for entry, prompt, parts in facts:
            entries.append(entry)
            if prompt is not None:
                prompts.setdefault(entry, prompt)
            costs[entry.model, entry.tokens] = parts

    for index, root in enumerate(roots):
        revision = service.source.get_session_tree_revision(root.session_id)
        key = keys[root.session_id]
        facts = load(cached.pop(key, None), revision)
        service.metrics.add('token_mix_cache_hits' if facts is not None else 'token_mix_cache_misses')
        if facts is not None:
            service._acquisition.revisions[root.session_id] = revision
            include(facts)
        else:
            pending.append((root, key))
        progress(WorkProgress('Checking history cache', 'history', index + 1, len(roots)), None)
    for start in range(0, len(pending), BATCH_SIZE):
        chunk = pending[start:start + BATCH_SIZE]
        writes = []
        service.prepare_roots([root for root, _key in chunk], progress_scope='date')
        for root, key in chunk:
            item = service._analyze(root)
            payload = encode(item.bundle, reference)
            service.metrics.add('token_mix_valued_requests', len(payload))
            include(decode(payload))
            if (item.bundle.cacheable and service.source.get_session_tree_revision(root.session_id)
                    == item.bundle.source_revision):
                writes.append(CacheEntry(NAMESPACE, key, payload, item.bundle.source_revision, ALGORITHM))
            service._analyzed.pop(root.session_id, None)
        try:
            service.cache_repository.put_many(writes, busy_timeout_ms=50)
        except (OSError, sqlite3.Error):
            pass
        progress(WorkProgress('Updating changed history', 'history', start + len(chunk), len(pending)), None)
    return history_projection(service, reference, entries, prompts, progress,
        valuation=lambda model, tokens: costs[model, tokens])
