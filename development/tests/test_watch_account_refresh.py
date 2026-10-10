"""Account-refresh state can be tested without source hydration or a dashboard."""
from collections import deque
from dataclasses import replace
from decimal import Decimal
import unittest

from src.accounts.acquisition import AccountUpdate
from src.domain import AccountRef, AccountSnapshot, QuotaComponent
from src.watch.account_refresh import WatchAccountRefresh


class AccountWork:
    def __init__(self):
        self.results = deque()
        self.starts = []
        self.accounts_pending = False
        self.closed = False

    def set_now_ms(self, now): self.now = now
    def begin_account_refresh(self): self.starts.append(self.now)
    def poll_account_refresh(self): return self.results.popleft() if self.results else None
    def close_accounts(self): self.closed = True


class WatchAccountRefreshTests(unittest.TestCase):
    def setUp(self):
        self.clock = [100_000, 0.0]
        self.work = AccountWork()
        self.refresh = WatchAccountRefresh(self.work, clock_ms=lambda: self.clock[0], monotonic=lambda: self.clock[1])
        self.good = AccountSnapshot(AccountRef("fixture", "provider", "a"), 100_000, "Provider",
                                    quotas=(QuotaComponent("window", remaining_fraction=Decimal(".75")),))
        self.error = replace(self.good, quotas=(), availability="error", observations={"parser_reason": "network_failure"})

    def advance(self, seconds):
        self.clock[0] += seconds * 1000
        self.clock[1] += seconds

    def publish(self, *snapshots):
        self.work.results.append(AccountUpdate(tuple(snapshots), tuple(item.key for item in snapshots)))
        return self.refresh.refresh(now_ms=self.clock[0])

    def test_source_like_wakes_cannot_amplify_provider_starts(self):
        self.publish(self.good)
        for _ in range(59):
            self.advance(1)
            self.refresh.refresh(now_ms=self.clock[0])
        self.assertEqual([100_000], self.work.starts)
        self.advance(1)
        self.refresh.refresh(now_ms=self.clock[0])
        self.assertEqual([100_000, 160_000], self.work.starts)

    def test_first_error_retries_once_per_identity_without_inventing_capacity(self):
        self.publish(self.error)
        self.assertEqual((self.good.key,), self.refresh.recovering_keys)
        self.assertEqual(5, self.refresh.retry_at)
        self.assertEqual((), self.refresh.snapshots[0].quotas)
        self.assertEqual({}, self.refresh.seen_ms)
        for delay in (5, 10, 20, 25):
            self.advance(delay)
            self.publish(self.error)
        self.assertIsNone(self.refresh.recovery_until)
        self.assertEqual(4, len(self.work.starts))
        self.advance(60)
        self.publish(self.error)
        self.assertIsNone(self.refresh.recovery_until)

    def test_recovery_expiry_without_new_update_is_not_an_observation(self):
        self.publish(self.good)
        self.advance(600)
        self.refresh.resume()
        self.publish(self.error)
        self.assertTrue(self.refresh.stale)
        self.advance(60)

        changed = self.refresh.refresh(now_ms=self.clock[0])

        self.assertTrue(changed)
        self.assertEqual({self.good.key: 100_000}, self.refresh.seen_ms)
        self.assertEqual((), self.refresh.snapshots[0].quotas)
        self.assertFalse(self.refresh.recovering_keys)

    def test_durable_auth_rejection_never_enters_retry_or_retains_capacity(self):
        self.publish(self.good)
        self.advance(600)
        self.refresh.resume()

        self.publish(replace(self.error, observations={"http_status": 401}))

        self.assertFalse(self.refresh.recovering_keys)
        self.assertIsNone(self.refresh.retry_at)
        self.assertEqual((), self.refresh.snapshots[0].quotas)

    def test_successful_publication_during_recovery_clears_retry_state(self):
        self.publish(self.error)
        self.advance(5)

        self.publish(self.good)

        self.assertIsNone(self.refresh.retry_at)
        self.assertIsNone(self.refresh.recovery_until)
        self.assertFalse(self.refresh.recovering_keys)
        self.assertEqual(105_000, self.refresh.seen_ms[self.good.key])

    def test_close_prevents_all_future_acquisition_and_publication(self):
        self.refresh.close()
        self.work.results.append(AccountUpdate((self.good,), (self.good.key,)))

        changed = self.refresh.refresh(now_ms=self.clock[0], force=True)

        self.assertFalse(changed)
        self.assertTrue(self.work.closed)
        self.assertEqual([], self.work.starts)
        self.assertEqual((), self.refresh.snapshots)
