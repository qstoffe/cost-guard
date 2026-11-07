"""Immutable prompt detail from canonically owned requests, never aggregate allocation."""
from dataclasses import dataclass
from decimal import Decimal

from src.analysis.comparisons import effort_model_parts
from src.analysis.effort import interpret_effort
from src.analysis.models import PromptRecord
from src.analysis.token_mix import MIX_FIELDS
from src.analysis.valuation import comparison_cost
from src.pricing.catalog import PricingCatalog


@dataclass(frozen=True, slots=True)
class PromptCostPart:
    session_id: str
    agent: int
    provider_id: str
    model_id: str
    variant: str | None
    model: str
    effort: str
    calls: int
    known_ccost: Decimal
    priced_requests: int
    complete: bool
    categories: tuple[Decimal | None, ...]
    price_tier: str = ""
    prompt_ids: tuple[tuple[str | None, str, str], ...] = ()
    prompts_complete: bool = False


def _price_tier(entry, catalog):
    pricing = catalog.reference_prices(entry.model.model)
    if pricing is None or len(pricing.tiers) < 2:
        return ""
    if not all(name in entry.tokens.known_fields for name in MIX_FIELDS[:3]):
        return "Unrecorded price tier"
    tier = pricing.selected_tier(entry.tokens.input + entry.tokens.cache_read + entry.tokens.cache_write)
    lower = tier.min_input_tokens or 0
    upper = str(tier.max_input_tokens) if tier.max_input_tokens is not None else "∞"
    return f"{tier.name} ({lower}–{upper} input tokens)"


def prompt_cost_parts(record: PromptRecord, catalog: PricingCatalog) -> tuple[PromptCostPart, ...]:
    """Preserve session/model/effort identity and each physical request's price tier.

    Root-entry slicing is the analysis attribution boundary, not a time/provider
    heuristic. Unknown telemetry cannot manufacture zero category contributions.
    """
    if not record.breakdown_known:
        return ()
    groups = {}
    agents = {record.session_id: 0}
    for index, entry in enumerate(record.entries):
        session = record.session_id if index < record.root_entry_count else entry.session_id
        if session not in agents:
            agents[session] = len(agents)
        key = (session, entry.model.provider, entry.model.model, entry.variant, _price_tier(entry, catalog))
        groups.setdefault(key, []).append(entry)
    result = []
    for (session, provider, model_id, variant, tier), entries in groups.items():
        total = comparison_cost(entries, catalog.reference_valuation)
        amounts = [Decimal(0)] * 4
        known = [True] * 4
        for entry in entries:
            parts = catalog.reference_category_valuation(entry.model, entry.tokens)
            tier_known = all(name in entry.tokens.known_fields for name in MIX_FIELDS[:3])
            for index, name in enumerate(MIX_FIELDS):
                supported = parts is not None and tier_known and name in entry.tokens.known_fields
                known[index] &= supported
                if supported:
                    amounts[index] += parts[index]
        model, effort = effort_model_parts(catalog, model_id,
            interpret_effort(variant, attributable=bool(variant)))
        result.append(PromptCostPart(session, agents[session], provider, model_id, variant,
            model, effort, len(entries), total.known_ccost, total.priced_requests, total.complete,
            tuple(value if supported else None for value, supported in zip(amounts, known)), tier,
            tuple(dict.fromkeys((entry.source_instance, entry.session_id, entry.logical_prompt_id)
                for entry in entries if entry.logical_prompt_id)),
            all(entry.logical_prompt_id is not None for entry in entries)))
    return tuple(result)
