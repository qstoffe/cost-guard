"""Idle Watch can publish independently acquired quota without another source read."""
import tempfile
import unittest
from unittest.mock import Mock

from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from src.watch import WatchCoordinator
from src.accounts.acquisition import AccountUpdate


class IdleAccountPublicationTests(unittest.TestCase):
    def test_idle_projection_accepts_completed_account_without_new_acquisition(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = MutableSource(make_snapshot())
            config, selection, service, _ = make_service(tmp, source)
            snapshots = service.account_quota_snapshots()
            mailbox = []
            service.begin_account_refresh = Mock()
            service.poll_account_refresh = lambda: mailbox.pop() if mailbox else None
            watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                     clock_ms=lambda: 10_000_000)
            try:
                opening = watch.initialize().projection
                self.assertEqual(0, opening.active_count)
                self.assertFalse(opening.quota.accounts)
                starts, loads = service.begin_account_refresh.call_count, source.load_count
                mailbox.append(AccountUpdate(snapshots, tuple(item.key for item in snapshots)))

                status = watch.status_projection(seconds_until_check=5)

                self.assertEqual(list(snapshots), [item.account for item in status.quota.accounts])
                self.assertEqual((starts, loads), (service.begin_account_refresh.call_count, source.load_count))
            finally:
                watch.close()
