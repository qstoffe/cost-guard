"""Durable, source-qualified history inputs for the established report projections."""
from dataclasses import replace

from src.analysis.cache import encode_trace_entry
from src.analysis.causal import trace_entries
from src.analysis.daily_usage import prompt_attributions, request_identity
from src.cache.web_archive import ArchiveFact

from . import ai_stats_evidence


# Persisted wire schema, independent of the reconstructible analysis cache.
DOMAIN = 'usage/1'


def acquired_usage(service, item):
    snapshot, bundle = item.snapshot, item.bundle
    root = item.session
    provenance = root.provenance
    revision = bundle.source_revision
    if (provenance.source_instance != service.source.source_instance
            or not isinstance(revision, str) or not snapshot.complete
            or any(session.active is True for session in snapshot.sessions)
            or any(prompt.in_progress for prompt in bundle.prompts)
            or any(compaction.in_progress for compaction in bundle.compactions)):
        return None
    reference = service._load_comparison_catalog()
    stats = ai_stats_evidence.payload(bundle, reference, snapshot, service.config, now=service.now_ms)
    # Keep native account attribution, not display labels, private updates or
    # raw errors. Physical request identity remains the canonical join key.
    usage = [encode_trace_entry(replace(entry, error_name='error' if entry.error_name else None,
        account_ref=replace(entry.account_ref, account_label=None) if entry.account_ref else None))
        for entry in trace_entries(snapshot)]
    attribution = prompt_attributions(bundle)
    causal = {entry.invocation_id: attribution[request_identity(entry)] for entry in bundle.trace_entries
              if entry.invocation_id and request_identity(entry) in attribution}
    return ArchiveFact(revision, service.now_ms,
                       dict(title=root.title, stats=stats, account_usage=usage, causal_prompts=causal))
