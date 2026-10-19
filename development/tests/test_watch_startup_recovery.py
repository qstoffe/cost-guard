"""Unfinished Watch startup must wait without provider/accounting side effects."""
from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from development.fixtures.watch_runtime import CountingAccountProvider, FakeLiveSource, make_service
from src.sources.errors import FailureCode, SourceDataError, SourceSchemaError, SourceUnavailableError
from src.watch import WatchCoordinator
from src.watch.coordinator import SOURCE_UNREADABLE_RETRIES


class FlakySource(FakeLiveSource):
    def __init__(self, *, phase="catalog", error=None):
        super().__init__()
        self.phase = phase
        self.failure = error
        self.failures = 0

    def _check(self, phase):
        if phase == self.phase and self.failure is not None:
            self.failures += 1
            raise self.failure

    def list_sessions(self, since_ms=None):
        self._check("catalog")
        return super().list_sessions(since_ms)

    def load_session_snapshot(self, session_id):
        self._check("snapshot")
        return super().load_session_snapshot(session_id)


class Renderer:
    def __init__(self):
        self.statuses = []

    def render_startup_status(self, status, *, active):
        self.statuses.append((status, active))


class WatchStartupRecoveryTests(unittest.TestCase):
    def test_initial_catalog_and_snapshot_failures_recover_without_quota_refresh(self):
        for phase in ("catalog", "snapshot"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as td:
                source = FlakySource(phase=phase, error=SourceUnavailableError("offline", code=FailureCode.REFUSED))
                account = CountingAccountProvider()
                config, selection, service, _ = make_service(td, source, account_provider=account)
                clock = [2200]
                waits, provider_calls = [], []
                def sleep(seconds):
                    waits.append(seconds)
                    provider_calls.append(account.calls)
                    clock[0] += int(seconds * 1000)
                    if len(waits) == 2:
                        source.failure = None
                watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                         clock_ms=lambda: clock[0], sleep=sleep)
                with patch.object(watch, "_start_event_pump") as pump:
                    cycle = watch.initialize_with_recovery(Renderer())
                self.assertEqual([5, 5], waits)
                self.assertEqual([0, 0], provider_calls)
                self.assertEqual(1, account.calls)
                self.assertTrue(cycle.recovered)
                self.assertTrue(watch.observation)
                self.assertTrue(cycle.projection.rows)
                pump.assert_called_once()
                watch.close()

    def test_partial_initialization_is_discarded_before_retry(self):
        with tempfile.TemporaryDirectory() as td:
            source = FlakySource()
            account = CountingAccountProvider()
            config, selection, service, _ = make_service(td, source, account_provider=account)
            watches = []
            def sleep(_seconds):
                watch = watches[0]
                self.assertIsNone(watch.observation)
                self.assertEqual({}, watch.blocks)
                self.assertEqual({}, watch.snapshots)
                self.assertEqual({}, watch.token_mix._messages)
                self.assertEqual(0, account.calls)
            watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                     clock_ms=lambda: 2200, sleep=sleep)
            watches.append(watch)
            hydrate = watch._hydrate_startup
            failure = [True]
            def first_quota(*args, **kwargs):
                result = hydrate(*args, **kwargs)
                if failure:
                    failure.pop()
                    raise SourceUnavailableError("offline", code=FailureCode.RESET)
                return result
            with patch.object(watch, "_hydrate_startup", side_effect=first_quota), \
                 patch.object(watch, "_start_event_pump"):
                cycle = watch.initialize_with_recovery(Renderer())
            self.assertTrue(cycle.recovered)
            self.assertEqual(1, account.calls)
            watch.close()

    def test_initial_incompatibility_is_terminal_without_wait_or_accounts(self):
        for error in (SourceSchemaError("unsupported"), SourceUnavailableError("auth", code=FailureCode.AUTH),
                      SourceUnavailableError("bad registration", code=FailureCode.REGISTRATION_INVALID)):
            with self.subTest(error=error.code), tempfile.TemporaryDirectory() as td:
                account = CountingAccountProvider()
                source = FlakySource(error=error)
                config, selection, service, _ = make_service(td, source, account_provider=account)
                waits = []
                watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                         clock_ms=lambda: 2200, sleep=waits.append)
                with self.assertRaises(type(error)):
                    watch.initialize_with_recovery(Renderer())
                self.assertEqual([], waits)
                self.assertEqual(0, account.calls)
                watch.close()

    def test_initial_malformed_data_has_existing_bounded_retry_limit(self):
        with tempfile.TemporaryDirectory() as td:
            source = FlakySource(error=SourceDataError("invalid data"))
            config, selection, service, _ = make_service(td, source)
            waits = []
            watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                     clock_ms=lambda: 2200, sleep=waits.append)
            with self.assertRaises(SourceDataError):
                watch.initialize_with_recovery(Renderer())
            self.assertEqual(SOURCE_UNREADABLE_RETRIES, len(waits))
            watch.close()

    def test_ctrl_c_during_initial_recovery_propagates_cleanly(self):
        with tempfile.TemporaryDirectory() as td:
            source = FlakySource(error=SourceUnavailableError("offline", code=FailureCode.TIMEOUT))
            config, selection, service, _ = make_service(td, source)
            def cancel(_seconds):
                raise KeyboardInterrupt
            watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                     clock_ms=lambda: 2200, sleep=cancel)
            with self.assertRaises(KeyboardInterrupt):
                watch.initialize_with_recovery(Renderer())
            self.assertIsNone(watch.observation)
            watch.close()


if __name__ == "__main__":
    unittest.main()
