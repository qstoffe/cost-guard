"""Token subtotals on the existing catalog executor; no source or pricing work."""
from src.cache.display_stats_tokens import StatsTokenRow, StatsTokenStamp

from .archive_exact_cost import ExactCost
from .archive_stats_population import ArchiveStatsPopulation, PopulationState


class _ReferenceSubtotal:
    def __init__(self):
        self.total = ExactCost()
        self.priced = 0
        self.price = None
        self.mixed_prices = False

    def add(self, observation):
        if observation.ccost is not None:
            self.total.add(observation.ccost)
            self.priced += 1
        if observation.pricing is not None:
            if self.price is None:
                self.price = observation.pricing
            self.mixed_prices |= self.price != observation.pricing

    def amount(self, population_gap):
        return self.total.amount() if self.priced and not (population_gap or self.mixed_prices) else None


class ArchiveStatsTokens:
    def __init__(self, source, zone, now_ms):
        self.source, self.zone, self.now_ms = source, zone, now_ms
        self._population = ArchiveStatsPopulation(source, zone, now_ms)
        self.scopes = self._population.scopes
        self._periods = iter(self.scopes)
        self._period = self._cursor = None
        self._rows = []
        self.publication = None

    def step(self, history, *, eligible):
        if not eligible():
            return False
        if self._period is None:
            state = self._population.step(history, eligible=eligible)
            if state is PopulationState.READY:
                self._next_period()
            return state is not PopulationState.STALE

        page = self._population.page(self._period, after=self._cursor)
        self._requests += len(page.keys)
        for observation in page.observations:
            self._usage_gaps |= observation.usage_gap
            if observation.tokens is not None:
                self._subtotal = (self._subtotal or 0) + observation.tokens
            self._cost.add(observation)
            # The producer only supplies a tree ID for an observed path from
            # its top-level root. Candidate reconciliation has already run.
            if observation.subagent:
                self._subagent_cost.add(observation)
        self._cursor = page.next_cursor
        if self._cursor is not None:
            return True

        population_gap = self._period in self._population.gaps
        self._rows.append(StatsTokenRow(self._period, self.scopes[self._period],
                                       None if population_gap else self._subtotal, self._requests,
                                       self._usage_gaps, population_gap,
                                        self._cost.amount(population_gap), self._cost.priced, self._cost.mixed_prices,
                                        self._subagent_cost.amount(population_gap)))
        self._next_period()
        if self._period is not None:
            return True

        stamp = StatsTokenStamp(self._population.version, self.zone, self.now_ms, self._population.next_completion)
        self.publication = history.publish_stats_tokens(self.source, stamp, tuple(self._rows), eligible=eligible)
        return False

    def _next_period(self):
        self._period = next(self._periods, None)
        self._subtotal, self._requests, self._usage_gaps = None, 0, False
        self._cost, self._subagent_cost = _ReferenceSubtotal(), _ReferenceSubtotal()

    def close(self):
        self._population.close()
