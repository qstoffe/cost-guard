"""Web-only, revision-keyed minimal history evidence; never durable user history.

Unchanged roots reuse compact request facts and their canonical category valuation,
not hydrated snapshots or verbose derived prompt records. Global clone deduplication
and grouping still belong to token_mix_history. Deleted roots are never read back.
"""
from decimal import Decimal, InvalidOperation
from dataclasses import replace
import sqlite3

from src.analysis.cache import dependency_signature
from src.analysis.models import TraceEntry
from src.analysis.model_identity import encode_model, decode_model, current
from src.cache.repository import CacheEntry
from src.cache.session_scope import snapshot_scope
from src.domain import ModelRef, TokenUsage
from src.domain.progress import WorkProgress
from src.pricing.identities import MODEL_IDENTITY_SEMANTICS, identity_cache_current
from .token_mix_history import history_projection
from .history_work import HistoryWork, HistoryCheckpointError, active_roots, revisions
from .history_snapshots import load as load_snapshots, warnings as history_warnings

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
        if entry.model.resolution is not None:
            facts[-1]['resolved_identity'] = encode_model(entry.model)
        if not identity_cache_current(None, ((entry.model.provider, entry.model.model),)):
            facts[-1]['model_identity_semantics'] = MODEL_IDENTITY_SEMANTICS
    return facts


def decode(facts):
    result = []
    if not isinstance(facts, list):
        raise ValueError('invalid_evidence')
    for fact in facts:
        provider, model, _display = fact['model']
        if not identity_cache_current(fact.get('model_identity_semantics'), ((provider, model),)):
            raise ValueError('outdated_model_identity')
        counts = fact['tokens']
        if len(counts) != 5 or any(type(value) is not int or value < 0 for value in counts):
            raise ValueError('invalid_tokens')
        tokens = TokenUsage(input=counts[0], cache_read=counts[1], cache_write=counts[2],
            output=counts[3], reasoning=counts[4], known_fields=tuple(fact['known']))
        entry = TraceEntry(fact['session'], fact['parent'], fact['message'], fact['part'],
            fact['completed'], fact['order'], decode_model(fact['resolved_identity']) if 'resolved_identity' in fact
            else ModelRef(*fact['model']), fact['variant'], tokens,
            reported_cost=Decimal(fact['reported']), source_instance=fact['instance'])
        costs = None if fact['costs'] is None else tuple(Decimal(value) for value in fact['costs'])
        if costs is not None and (len(costs) != 4 or any(not value.is_finite() or value < 0 for value in costs)):
            raise ValueError('invalid_costs')
        prompt = None if fact['prompt'] is None else tuple(fact['prompt'])
        result.append((entry, prompt, costs))
    return result


def load(cached, revision, source=None):
    try:
        if cached is not None and cached.source_revision == revision and cached.algorithm_version == ALGORITHM:
            facts = decode(cached.payload)
            return facts if current(source, (entry.model for entry, _prompt, _cost in facts)) else None
    except (OSError, sqlite3.Error, KeyError, TypeError, ValueError, InvalidOperation):
        pass
    return None


def observe(service, roots, versions):
    """Optional bounded derived-cache windows; a failed read leaves scalar per-root reuse intact."""
    try:
        return service._acquisition.observe(roots, versions)
    except (OSError, sqlite3.Error):
        return {}


def build_cached_token_mix(service, progress):
    progress(WorkProgress('Loading pricing catalog', 'pricing'), None)
    reference = service._load_comparison_catalog()
    progress(WorkProgress('Checking history revisions', 'catalog'), None)
    sessions = tuple(service.source.list_sessions())
    roots = [root for root in sessions if root.parent_session_id is None]
    versions = revisions(service, roots)
    work = HistoryWork(service, sessions, roots, versions, reference)
    active = active_roots(sessions)
    keys = {root.session_id: cache_key(service, root, reference) for root in roots}
    try:
        cached = service.cache_repository.get_many(NAMESPACE, keys.values(), busy_timeout_ms=50)
    except (OSError, sqlite3.Error):
        cached = {}
    facts_by_root = {}
    fact_count = 0
    unavailable = set()
    pending = []

    def include(root, facts):
        nonlocal fact_count
        fact_count += len(facts)
        if getattr(service, 'history_checkpoint', None) and fact_count > 250_000:
            raise HistoryCheckpointError('history_resource_limit')
        facts_by_root[root.session_id] = facts

    for index, root in enumerate(roots):
        revision = versions[root.session_id]
        key = keys[root.session_id]
        facts = load(cached.pop(key, None), revision, service.source) if root.session_id not in active else None
        service.metrics.add('token_mix_cache_hits' if facts is not None else 'token_mix_cache_misses')
        if facts is not None:
            service._acquisition.revisions[root.session_id] = revision
            include(root, facts)
            work.saved += 1
        else:
            pending.append((root, key))
        progress(WorkProgress('Checking history cache', 'history', index + 1, len(roots), stage='history-cache'), None)
    progress(WorkProgress('Updating changed history', 'history', 0, len(pending), stage='history-load'), None)
    batch_size = getattr(service, 'history_batch_size', BATCH_SIZE)
    for start in range(0, len(pending), batch_size):
        chunk = pending[start:start + batch_size]
        writes = []
        partial = getattr(service, 'allow_partial_history', False)
        observations = observe(service, [root for root, _key in chunk], versions) if partial else {}
        snapshots = load_snapshots(service, [root for root, _key in chunk]) if partial else None
        if not partial:
            service.prepare_roots([root for root, _key in chunk], progress_scope='date')
        for root, key in chunk:
            if partial and root.session_id not in snapshots:
                unavailable.add(root.session_id)
                continue
            item = (service._analyze(root, snapshot=snapshots[root.session_id],
                observation=observations.get(root.session_id)) if partial else service._analyze(root))
            payload = encode(item.bundle, reference)
            service.metrics.add('token_mix_valued_requests', len(payload))
            include(root, decode(payload))
            if (item.bundle.cacheable and root.session_id not in active
                    and item.bundle.source_revision == versions[root.session_id]
                    and service.source.get_session_tree_revision(root.session_id)
                    == item.bundle.source_revision):
                writes.append(CacheEntry(NAMESPACE, key, payload, item.bundle.source_revision, ALGORITHM,
                    snapshot_scope(item.snapshot) if item.snapshot is not None else None))
            service._analyzed.pop(root.session_id, None)
        write_error = None
        try:
            service.cache_repository.put_many(writes, busy_timeout_ms=50)
        except (OSError, sqlite3.Error) as error:
            write_error = error
            writes = []
        progress(WorkProgress('Updating changed history', 'history', start + len(chunk), len(pending), stage='history-load'), None)
        work.checkpoint(len(writes), processed=len(chunk), remaining=start + len(chunk) < len(pending), error=write_error)
    unavailable.update(work.verify())
    if unavailable and len(unavailable) == len(roots):
        raise HistoryCheckpointError('history_revision_churn')
    entries, prompts, costs = [], {}, {}
    for sid, facts in facts_by_root.items():
        if sid in unavailable:
            service._acquisition.revisions.pop(sid, None)
            continue
        for entry, prompt, parts in facts:
            entries.append(entry)
            if prompt is not None:
                prompts.setdefault(entry, prompt)
            costs[entry.model, entry.tokens] = parts
    report = history_projection(service, reference, entries, prompts, progress,
        valuation=lambda model, tokens: costs[model, tokens])
    return replace(report, source_warnings=(*report.source_warnings, *history_warnings(unavailable)),
                   history_omitted_roots=len(unavailable))
