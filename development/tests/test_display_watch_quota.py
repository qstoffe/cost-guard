"""Native quota proof, expiry, and revocation on the shared Watch read."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from development.tests.fixtures.display_watch import native_account, running_frame
from src.accounts.acquisition import AccountUpdate
from src.application.live import LiveRuntime
from src.application.watch_native_quota import native_quotas
from src.sources.opencode_v1 import OpenCodeV1Source
from src.watch.account_refresh import WatchAccountRefresh
from src.web.display_archive import DisplayArchive


class DisplayWatchQuotaTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        source = root / "fixture.db"
        source.touch()
        self.driver = SimpleNamespace(terminal=False, error=None, coordinator=SimpleNamespace(
            report_service=SimpleNamespace(timezone_id="UTC", selection=SimpleNamespace(
                selected="v1", source=OpenCodeV1Source(source))), catalog_observation=None))
        self.events = []
        self.archive = DisplayArchive(root, lambda kind, event: self.events.append((kind, event)), watch_enabled=True)
        self.addCleanup(self.archive.close)
        self.assertTrue(self.archive.initialize())
        self.clock = self.enterContext(patch("src.web.display_archive.time.time", return_value=99))
        self.archive.observe(self.driver, before_tick=True)

    def publish(self, now, refresh, frame=None):
        self.clock.return_value = now / 1000
        hint = self.archive.publish_watch(frame, frame.now_ms if frame else None, account_refresh=refresh)
        self.archive._watch_write.result(timeout=5)
        return hint

    def read(self, *, healthy=False):
        return self.archive.watch_snapshot(live_eligible=lambda: healthy, presentation=True)

    def test_provider_proof_is_independent_of_the_card_clock_and_not_exported_across_binding(self):
        account = native_account(100_000)
        refresh = SimpleNamespace(snapshots=(account,), seen_ms={account.key: 101_000})
        hint = self.publish(101_000, refresh)

        first = self.read()
        self.clock.return_value = 120
        reset = self.read()
        self.clock.return_value = 400.001
        expired = self.read()
        self.archive.unbind()
        self.archive.observe(self.driver, before_tick=True)
        rebound = self.read()

        self.assertEqual(("empty", 1, hint["revision"]), (first["freshness"], first["generation"], first["quota_revision"]))
        item, = first["view"]["accounts"]["accounts"]
        self.assertEqual(("Fixture Pro", 100_000, "25%", False), (item["observation"]["label"],
            item["observation"]["observed_at_ms"], item["primary"]["used_percent"], item["stale"]))
        last, = reset["view"]["accounts"]["accounts"]
        self.assertTrue(last["stale"])
        self.assertEqual([], expired["view"]["accounts"]["accounts"])
        self.assertIsNone(rebound["view"]["accounts"])
        self.assertEqual("watch-cache", self.events[-3][0])
        for excluded in ("private-provider-instance", "private-account-id", "private-provider-payload", "98765"):
            self.assertNotIn(excluded, str(first))
            for file in self.archive.history.path.parent.glob(self.archive.history.path.name + "*"):
                self.assertNotIn(excluded.encode(), file.read_bytes())

    def test_known_provider_revocation_masks_an_older_sqlite_generation_under_write_pressure(self):
        account = native_account(100_000)
        refresh = SimpleNamespace(snapshots=(account,), seen_ms={account.key: 100_000})
        initial = self.publish(100_000, refresh, running_frame(100_000))
        rejected = replace(account, availability="error", observations={"parser_reason": "auth_failure"})
        refresh.snapshots = (rejected,)
        self.clock.return_value = 101

        with self.archive.history._write_lock:
            hint = self.archive.publish_watch(None, None, account_refresh=refresh)
            held = self.read(healthy=True)
        self.archive._watch_write.result(timeout=5)
        committed = self.read(healthy=True)

        self.assertGreater(hint["revision"], initial["revision"])
        self.assertIsNone(held["view"]["accounts"])
        self.assertEqual((1, 100_000, "running"), (held["generation"], held["observed_ms"], held["cards"][0]["outcome"]))
        self.assertEqual((2, 100_000), (committed["generation"], committed["observed_ms"]))
        self.assertEqual([], committed["view"]["accounts"]["accounts"])

    def test_seen_time_and_binding_are_required_even_if_native_capacity_exists(self):
        account = native_account(100_000)
        refresh = SimpleNamespace(snapshots=(account,), seen_ms={})

        no_proof = native_quotas(refresh, bound_ms=99_000, now_ms=101_000)
        refresh.seen_ms = {account.key: 98_000}
        old_identity = native_quotas(refresh, bound_ms=99_000, now_ms=101_000)
        refresh.seen_ms = {account.key: 102_000}
        future = native_quotas(refresh, bound_ms=99_000, now_ms=101_000)
        refresh.seen_ms = {account.key: 101_000}
        completed_late = native_quotas(refresh, bound_ms=100_500, now_ms=101_000)

        self.assertEqual(((), (), (), ()), (no_proof, old_identity, future, completed_late))

    def test_live_publishes_quota_completion_before_any_verified_card_frame(self):
        self.clock.return_value = 101
        native = native_account(100_000)
        provider_work = Mock()
        provider_work.poll_account_refresh.return_value = AccountUpdate(
            (native,), (native.key,), ((native.key, 101_000),))
        refresh = WatchAccountRefresh(provider_work, clock_ms=lambda: 101_000, monotonic=lambda: 1)
        self.driver.coordinator.accounts = refresh
        self.driver.observed_at_ms = None
        self.driver.source_state = "starting"
        publications = []
        live = LiveRuntime(None, lambda _, item: publications.append(item.to_json()), display_archive=self.archive)

        refresh.refresh(now_ms=101_000)
        live._publish_frame(self.driver, None)
        self.archive._watch_write.result(timeout=5)
        stored = self.read()

        live_read, = publications
        self.assertIsNone(live_read["view"])
        self.assertEqual(dict(binding=stored["binding"], revision=stored["quota_revision"]), live_read["watch_quota_hint"])
        self.assertEqual("25%", stored["view"]["accounts"]["accounts"][0]["primary"]["used_percent"])
