"""Qualified direct reference costs; not native balances or estimated allocation."""
from bisect import bisect_right
from dataclasses import dataclass, field
from itertools import islice
from uuid import uuid4

from src.analysis.account_timeline import PERIODS, timeline_window
from src.analysis.cache import dependency_signature
from src.analysis.period_ccost import account_usage_routes, usage_provider
from src.cache.display_account_buckets import ACCOUNT_BATCH, ACCOUNT_LIMIT, ACCOUNT_MAX_BUCKETS, AccountBucket, AccountRun
from src.domain import CostDisposition

from .archive_exact_cost import ExactCost


def archived_account_roster(accounts):
    """Only exact account references qualify; labels and current logins assign nothing."""
    routes = {bytes.fromhex(dependency_signature(item.account.key)): frozenset(account_usage_routes(item.account, proven=True))
              for item in accounts}
    return routes if len(routes) <= ACCOUNT_LIMIT else None


def roster_signature(accounts):
    return dependency_signature(tuple((key.hex(), sorted(routes)) for key, routes in sorted(accounts.items())))


@dataclass(slots=True)
class _Subtotal:
    cost: ExactCost = field(default_factory=ExactCost)
    matched: int = 0
    priced: int = 0
    pricing: str | None = None
    conflicting: bool = False

    def add(self, observation):
        self.matched += 1
        if observation.known & 0b1111 != 0b1111 or not observation.pricing or len(observation.costs) != 4:
            return
        self.priced += 1
        if self.pricing is None:
            self.pricing = observation.pricing
        elif self.pricing != observation.pricing:
            self.conflicting = True
        for cost in observation.costs:
            self.cost.add(cost)


class _Window:
    def __init__(self, period, window):
        self.period = period
        self.edges = window.buckets[:len(window.buckets) - len(window.future)]
        self.left = tuple(left for left, _ in self.edges)
        self.costs = {}
        self.ambiguous = set()

    def locate(self, clock):
        slot = bisect_right(self.left, clock) - 1
        if slot >= 0 and clock < self.edges[slot][1]:
            return slot
        return None

    def add(self, observation):
        slot = self.locate(observation.clock_ms)
        if slot is not None:
            identifier = observation.account_key, slot
            if identifier not in self.costs:
                self.costs[identifier] = _Subtotal()
            self.costs[identifier].add(observation)

    def uncertain(self, clock):
        slot = self.locate(clock)
        if slot is not None:
            self.ambiguous.add(slot)

    def rows(self, account):
        for index, (left, right) in enumerate(self.edges):
            amount = self.costs.get((account, index))
            priced = amount and amount.priced and not amount.conflicting and index not in self.ambiguous
            yield AccountBucket(self.period, account, left, right, amount.cost.amount() if priced else None,
                                amount.matched if amount else 0, amount.priced if amount else 0,
                                amount.pricing if priced else None)


class ArchiveAccountHistory:
    """One 128-candidate catalog turn at a time, then a version-fenced publication."""

    def __init__(self, source, zone, now_ms, accounts):
        self.source, self.zone, self.now_ms = source, zone, now_ms
        if (len(accounts) > ACCOUNT_LIMIT or any(type(key) is not bytes or len(key) != 32 for key in accounts)):
            raise ValueError("invalid_accounts_roster")
        self.accounts = {key: frozenset(routes) for key, routes in accounts.items()}
        self.roster = roster_signature(self.accounts)
        self.windows = tuple(_Window(period, timeline_window(period, now_ms, zone)) for period in PERIODS)
        if any(len(window.edges) > ACCOUNT_MAX_BUCKETS for window in self.windows):
            raise ValueError("invalid_account_bucket_count")
        self.start = min(window.left[0] for window in self.windows)
        self.version = self.after = None
        self.done = False

    def advance(self, history):
        if self.done:
            raise RuntimeError("account_history_already_reduced")
        page = history.account_usage(self.source, self.start, self.now_ms, version=self.version, after=self.after)
        if page is None:
            return False
        self.version, self.after = page.version, page.after
        for observation in page.rows:
            routes = self.accounts.get(observation.account_key)
            provider = usage_provider(observation.provider)
            if (not routes or provider not in routes or
                    provider == "claude-agent" and observation.disposition == CostDisposition.BILLED.value):
                continue
            for window in self.windows:
                window.add(observation)
        for clock in page.ambiguous_clocks:
            for window in self.windows:
                window.uncertain(clock)
        self.done = self.after is None
        return True

    def rows(self):
        if not self.done:
            raise RuntimeError("account_history_population_incomplete")
        for window in self.windows:
            for account in sorted(self.accounts):
                yield from window.rows(account)


class AccountHistoryPublication:
    """Catalog executor owns one unpublished run; each write is explicitly bounded."""

    def __init__(self, build):
        self.build = build
        self.run = uuid4().hex
        self._rows = None
        self._count = 0
        self.published = False

    def step(self, history, *, eligible):
        if not eligible():
            return False
        build = self.build
        if not build.done:
            return build.advance(history)
        if self._rows is None:
            self._rows = iter(build.rows())
        batch = tuple(islice(self._rows, ACCOUNT_BATCH))
        if batch:
            if history.stage_account_buckets(build.source, build.version, self.run, batch, eligible=eligible):
                self._count += len(batch)
                return True
            return False
        stamp = AccountRun(self.run, build.version, build.zone, build.roster, build.now_ms, self._count)
        self.published = history.publish_account_buckets(build.source, stamp, eligible=eligible)
        return False
