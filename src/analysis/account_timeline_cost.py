"""Conservative reference valuation for the Accounts chart only."""
from collections import defaultdict
from decimal import Decimal
from functools import lru_cache

from src.domain.ccost import reference_usd_to_ccost
from src.pricing.catalog import canonical_model_name
from src.pricing.identities import unverified_alias
from .period_ccost import usage_provider
from .token_mix import MIX_FIELDS
from .valuation import ComparisonCost

_RATE_FIELDS = ('per_million_input', 'per_million_cache_read', 'per_million_cache_write', 'per_million_output')
_MILLION = Decimal(1_000_000)
_NO_RATES = (None,) * len(_RATE_FIELDS)


def _counts(tokens):
    return (tokens.input, tokens.cache_read, tokens.cache_write, tokens.output + tokens.reasoning)


def _rates(tier):
    if tier is None:
        return _NO_RATES
    rates = tuple(getattr(tier, name) for name in _RATE_FIELDS)
    return (*rates[:2], rates[0] if rates[2] is None else rates[2], rates[3])


def _typical_rates(tiers):
    # Use the lower quartile of positive published rates, per category. Free
    # models are real zeroes for their own requests, not proxies for paid usage.
    def quartile(values):
        known = sorted(value for value in values if value is not None and value > 0)
        return known[(len(known) - 1) // 4] if known else None

    return tuple(quartile(values) for values in zip(*map(_rates, tiers))) if tiers else _NO_RATES


def _sample_keys(entry):
    scope = (entry.source_instance, usage_provider(entry.model.provider),
             entry.account_ref.key if entry.account_ref else None)
    model = canonical_model_name(entry.model.model)
    return ((*scope, model, entry.session_id), (*scope, model), scope) if model else (scope,)


class TimelineValuation:
    def __init__(self, catalog, previous=None):
        self.catalog = catalog
        self.previous = previous
        self.reference = lru_cache(maxsize=8192)(catalog.reference_valuation)
        by_provider = defaultdict(list)
        for model in catalog.ccost_models:
            by_provider[usage_provider(model.model.provider)].append(model.selected_tier(0))
        self.default_rates = _typical_rates([tier for tiers in by_provider.values() for tier in tiers])
        self.provider_rates = {provider: _typical_rates(tiers) for provider, tiers in by_provider.items()}

    def __call__(self, entries):
        samples = {}
        for entry in entries:
            tokens = entry.tokens
            if tokens.total and all(name in tokens.known_fields for name in MIX_FIELDS):
                counts = _counts(tokens)
                for key in _sample_keys(entry):
                    if len(key) == 3 and self.reference(entry.model, tokens) is None:
                        continue  # Only priced requests calibrate another model's missing categories.
                    previous = samples.get(key)
                    samples[key] = tuple(map(min, zip(previous, counts))) if previous is not None else counts
        return (self._value(entry, samples) for entry in entries)

    def _value(self, entry, samples):
        tokens = entry.tokens
        complete = all(name in tokens.known_fields for name in MIX_FIELDS)
        observed_usd = (entry.reported_cost if entry.reported_cost_currency == 'USD' else Decimal(0))
        if complete and not tokens.total:
            if observed_usd > 0:
                return ComparisonCost(reference_usd_to_ccost(observed_usd), 1, 1, source_complete=False)
            return ComparisonCost(priced_requests=1, observed_requests=1)
        exact = self.reference(entry.model, tokens)
        if exact is not None and complete:
            return ComparisonCost(exact, 1, 1, source_complete=not self.catalog.reference_stale)

        typical = next((samples[key] for key in _sample_keys(entry) if key in samples), (0, 0, 0, 0))
        inferred = (*typical[:3], max(typical[3], tokens.reasoning))
        estimated_counts = tuple(count if name in tokens.known_fields else estimate
                                 for name, count, estimate in zip(MIX_FIELDS, _counts(tokens), inferred))
        direct = cached = _NO_RATES
        if not unverified_alias(entry.model.model, entry.model.provider):
            input_tokens = sum(estimated_counts[:3])
            model = self.catalog.reference_prices(entry.model.model)
            direct = _rates(model.selected_tier(input_tokens) if model else None)
            if self.previous is not None and None in direct:
                model = self.previous.reference_prices(entry.model.model)
                cached = _rates(model.selected_tier(input_tokens) if model else None)
        provider = self.provider_rates.get(usage_provider(entry.model.provider), _NO_RATES)
        if observed_usd > 0 and not any(count and (current is not None or saved is not None)
                                       for count, current, saved in zip(estimated_counts, direct, cached)):
            return ComparisonCost(reference_usd_to_ccost(observed_usd), 1, 1, source_complete=False)
        rates = [next((rate for rate in options if rate is not None), None)
                 for options in zip(direct, cached, provider, self.default_rates)]
        valued = sum((count * rate for count, rate in zip(estimated_counts, rates) if count and rate is not None),
                     Decimal(0)) / _MILLION
        amount = max(exact or Decimal(0), valued)
        return ComparisonCost(amount, 1, int(amount > 0), source_complete=False)
