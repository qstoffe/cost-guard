"""Finite controlled provider calls; virtual latency never uses wall-clock sleeps."""
from dataclasses import replace
from decimal import Decimal
import threading
import time

from src.domain import AccountRef, AccountSnapshot, IntegrationHealth, QuotaComponent


def wait_for(predicate, *, timeout=2):
    deadline = time.monotonic() + timeout
    wake = threading.Event()
    while time.monotonic() < deadline:
        if predicate():
            return
        wake.wait(0.002)
    raise AssertionError("fixture completion deadline exceeded")


class Provider:
    def __init__(self, name, *, gate=None, failure=None, callback=None):
        self.provider_id = name
        self.gate, self.failure, self.callback = gate, failure, callback
        self.entered = threading.Event()
        self.returned = threading.Event()
        self.calls = 0

    def probe(self):
        return IntegrationHealth(True, True, "fixture")

    def get_account_snapshots(self):
        self.calls += 1
        self.entered.set()
        if self.callback:
            self.callback()
        if self.gate and not self.gate.wait(2):
            raise TimeoutError("fixture deadline")
        self.returned.set()
        if self.failure:
            raise self.failure
        return (AccountSnapshot(AccountRef("fixture", self.provider_id, "account"), self.calls,
                                self.provider_id, quotas=(QuotaComponent("quota", remaining_fraction=Decimal("0.5")),)),)


class ControlledQuota:
    """Capture native values at request start (the conservative freshness case)."""

    def __init__(self, clock, name="controlled"):
        self.clock, self.provider_id = clock, name
        self.value = Decimal(".75")
        self.starts = []
        self.gate = threading.Event()
        self.snapshot = None

    def probe(self):
        return IntegrationHealth(True, True, "fixture")

    def get_account_snapshots(self):
        self.gate.clear()
        captured = self.snapshot or AccountSnapshot(AccountRef("fixture", self.provider_id, "a"), 0, "Private account",
                                                   quotas=(QuotaComponent("window", remaining_fraction=self.value),))
        self.starts.append(self.clock[0])
        if not self.gate.wait(2):
            raise TimeoutError("fixture completion deadline")
        return (replace(captured, fetched_at_ms=int(100_000 + self.clock[0] * 1000)),)
