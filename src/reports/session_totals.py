"""Whole-session diagnostics from unique physical requests, not rendered rows."""
from decimal import Decimal

from src.analysis.token_mix import MIX_FIELDS
from src.analysis.valuation import physical_usage_key, unique_usage


def token_mix(values):
    total = sum(values)
    if not total:
        return None
    percentages = [value * 100 // total for value in values]
    # Allocate rounding remainders, never subtract them from an empty Output.
    order = sorted(range(4), key=lambda index: -(values[index] * 100 % total))
    for index in order[:100 - sum(percentages)]:
        percentages[index] += 1
    return tuple(percentages)


def session_totals(bundle, catalog):
    entries = unique_usage(bundle.trace_entries)
    def key(entry):
        return physical_usage_key(entry) or ("legacy", entry.sort_order)
    # The first root request of each causal prompt/compaction owns incoming
    # context. Later requests, linked agents and unattributed calls are Extra.
    first = {key(record.entries[0]) for record in (*bundle.prompts, *bundle.compactions)
             if record.entries and record.entries[0].session_id == record.session_id}
    amounts = [Decimal(0), Decimal(0)]
    observed = [False, False]
    complete = [bundle.usage_coverage_complete] * 2
    tokens = [0, 0, 0, 0]
    mix_complete = bundle.usage_coverage_complete
    for entry in entries:
        known = set(entry.tokens.known_fields)
        mix_complete &= set(MIX_FIELDS) <= known
        for index, name in enumerate(MIX_FIELDS):
            tokens[index] += getattr(entry.tokens, name) + (entry.tokens.reasoning if name == "output" else 0)
        parts = catalog.reference_category_valuation(entry.model, entry.tokens)
        for index, name in enumerate(MIX_FIELDS):
            component = 0 if key(entry) in first and index < 3 else 1
            supported = name in known and (parts is not None or
                set(MIX_FIELDS[:3]) <= known and entry.tokens.total == 0)
            complete[component] &= supported
            if supported:
                amounts[component] += parts[index] if parts is not None else Decimal(0)
                observed[component] = True
    return dict(
        total_incoming_context_ccost=amounts[0] if observed[0] or complete[0] else None,
        total_extra_ccost=amounts[1] if observed[1] or complete[1] else None,
        total_incoming_context_ccost_complete=complete[0],
        total_extra_ccost_complete=complete[1],
        total_token_mix_percent=token_mix(tokens) if mix_complete else None,
    )
