"""Coherent activity-day cost, initiating-prompt count and full-population mix."""
from dataclasses import dataclass

from .token_mix import TokenMix, priced_token_mix
from .valuation import ComparisonCost, comparison_cost, unique_usage


def request_identity(entry):
    message = entry.message_id or (entry.parent_event_id, entry.sort_order)
    return entry.source_instance, entry.session_id, message, entry.step_part_id


def prompt_attributions(bundle):
    """Causal parent assignment wins; known compaction usage adds no prompt."""
    result = {request_identity(entry): None for record in bundle.compactions for entry in record.entries}
    for prompt in bundle.prompts:
        if prompt.prompt_kind == "subtask":
            continue
        for entry in prompt.entries:
            result[request_identity(entry)] = (entry.source_instance, prompt.session_id, prompt.prompt_id)
    return result


@dataclass(frozen=True, slots=True)
class DailyUsage:
    day_start_ms: int
    observed_at_ms: int
    total: ComparisonCost
    mix: TokenMix
    prompt_count: int
    prompt_count_complete: bool


def daily_usage(entries, prompt_of, *, day_start_ms, now_ms, valuation, category_valuation):
    records = unique_usage(entry for entry in entries if day_start_ms <= entry.completed_at_ms <= now_ms)
    prompts = {prompt_of[request_identity(entry)] for entry in records
               if prompt_of.get(request_identity(entry)) is not None}
    return DailyUsage(day_start_ms, now_ms, comparison_cost(records, valuation),
        priced_token_mix(((entry.model, entry.tokens) for entry in records), category_valuation,
            sample_size=len(prompts)), len(prompts),
        all(request_identity(entry) in prompt_of for entry in records))
