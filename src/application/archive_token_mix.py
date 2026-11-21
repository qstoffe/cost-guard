"""Reduce stable archive slices, without source or counterfactual valuation."""
from dataclasses import dataclass, field, replace
from decimal import Decimal

from src.analysis.ai_stats import windows
from src.analysis.token_mix import MIX_FIELDS, TokenMix, summarize_token_mix
from src.cache.display_mix_totals import MixTotalRow


@dataclass(slots=True)
class _ExactCost:
    """Use integer coefficients, independent of Decimal's ambient context."""
    coefficient: int = 0
    exponent: int = 0

    def add(self, value):
        if not value.is_finite() or value < 0:
            raise ValueError("invalid_archive_category_cost")
        _, digits, exponent = value.as_tuple()
        if not any(digits):
            return
        contribution = int("".join(map(str, digits)))
        if not self.coefficient:
            self.coefficient, self.exponent = contribution, exponent
        else:
            common = min(self.exponent, exponent)
            self.coefficient = (self.coefficient * 10 ** (self.exponent - common) +
                                contribution * 10 ** (exponent - common))
            self.exponent = common

    def amount(self):
        return Decimal((0, tuple(map(int, str(self.coefficient))), self.exponent))


@dataclass(slots=True)
class _Totals:
    counts: list[int] = field(default_factory=lambda: [0] * 4)
    observed: list[int] = field(default_factory=lambda: [0] * 4)
    costs: tuple[_ExactCost, ...] = field(default_factory=lambda: tuple(_ExactCost() for _ in range(4)))
    known: int = 0b1111
    requests: int = 0
    priced: int = 0
    observed_any: bool = False
    uncertain_forks: int = 0
    stale_prices: int = 0

    def add(self, item, pricing):
        self.requests += 1
        self.known &= item.known
        self.observed_any |= bool(item.known & 0b1111 or item.tokens[4])
        for index, volume in enumerate(item.tokens[:4]):
            self.counts[index] += volume
            if item.known & (1 << index):
                self.observed[index] += volume
        self.counts[3] += item.tokens[4]  # Canonical I / C / W / O includes reasoning once.
        self.observed[3] += item.tokens[4]
        if item.category_costs is not None:
            self.priced += 1
            self.stale_prices += pricing is not None and pricing != item.pricing
            for accumulator, cost in zip(self.costs, item.category_costs):
                accumulator.add(cost)

    def mix(self, prompt_count):
        known = tuple(name for index, name in enumerate(MIX_FIELDS) if self.known & (1 << index))
        mix = summarize_token_mix(self.counts, known, self.requests,
                                 sum(self.observed) if self.observed_any else None, sample_size=prompt_count)
        # No valuation is not a zero-valued cost. Explicitly priced zero is.
        return replace(mix, costs=tuple(cost.amount() for cost in self.costs) if self.priced else None,
                       priced_requests=self.priced)


@dataclass(frozen=True, slots=True)
class ArchiveMixTotal:
    period: str
    start_ms: int | None
    end_ms: int
    mix: TokenMix
    observed: tuple[int, int, int, int]
    unqualified_forks: int
    undated_calls: int
    stale_prices: int

    def row(self):
        mix = self.mix
        return MixTotalRow(self.period, self.start_ms, self.end_ms, mix.totals, self.observed, mix.costs,
                           mix.known_total_tokens, mix.sample_size, mix.request_count, mix.priced_requests,
                           self.unqualified_forks, self.undated_calls, self.stale_prices)


class ArchiveMixRollup:
    """Five fixed scopes, truncated by one clock, with a bounded prompt-key sink.

    The caller stores/deduplicates prompt keys out of process memory. This
    reducer neither owns coverage proof nor declares any source history complete.
    """

    def __init__(self, timezone_id, end_ms, *, pricing=None):
        self.end_ms = end_ms
        self.pricing = pricing
        self.scopes = windows(timezone_id, end_ms)
        self.totals = {period: _Totals() for period, _ in self.scopes}
        self.undated_calls = 0

    def _periods(self, clock):
        if clock is None:
            return ("all",)
        if clock > self.end_ms:
            return ()
        return tuple(period for period, start in self.scopes if start is None or start <= clock)

    def add_slice(self, usage):
        prompt_keys = set()
        for clock in usage.unqualified_clocks:
            for period in self._periods(clock):
                self.totals[period].uncertain_forks += 1
        for item in usage.entries:
            self.undated_calls += item.clock_ms is None
            for period in self._periods(item.clock_ms):
                self.totals[period].add(item, self.pricing)
                if item.logical_prompt_id:
                    prompt_keys.add((period, item.session_id, item.logical_prompt_id))
        return prompt_keys

    def result(self, prompt_counts):
        return tuple(ArchiveMixTotal(period, start, self.end_ms, total.mix(prompt_counts.get(period, 0)),
                    tuple(total.observed), total.uncertain_forks, self.undated_calls, total.stale_prices)
                     for period, start in self.scopes for total in (self.totals[period],))
