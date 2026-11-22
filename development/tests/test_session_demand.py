"""A visible page can drop priority without cancelling real source work."""
from collections import OrderedDict
from threading import Lock
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.application.session_archive_sweep import SessionArchiveSweep
from src.application.session_demand import LEASE_SECONDS, MAX_TAB_LEASES, SessionDemand


class SessionDemandTests(unittest.TestCase):
    def test_replacement_and_withdrawal_ignore_out_of_order_requests(self):
        jobs = SessionDemand()
        jobs.replace("binding", "tab", 1, ("old-page",), 0)
        jobs.replace("binding", "tab", 3, ("new-page",), 1)
        delayed = jobs.replace("binding", "tab", 2, (), 2)
        next_job = jobs.take("binding", 2)
        jobs.replace("binding", "tab", 4, (), 3)
        replay = jobs.replace("binding", "tab", 3, ("new-page",), 4)

        self.assertEqual((0, "new-page", 0), (delayed, next_job, replay))
        self.assertFalse(jobs.ready("binding", 4))

    def test_tabs_share_pending_roots_and_expiry_does_not_reacquire_on_heartbeat(self):
        jobs = SessionDemand()
        jobs.replace("binding", "left", 1, ("shared", "left-only"), 0)
        jobs.replace("binding", "right", 1, ("shared", "right-only"), 1)

        first = jobs.take("binding", 2)
        heartbeat = jobs.replace("binding", "left", 2, ("shared", "left-only"), 3)
        second = jobs.take("binding", 4)
        third = jobs.take("binding", 5)
        jobs.replace("binding", "closed", 1, ("gone",), 6)

        self.assertEqual(("shared", 1, "right-only", "left-only"), (first, heartbeat, second, third))
        self.assertIsNone(jobs.take("binding", 6 + LEASE_SECONDS))

    def test_namespace_and_lease_count_are_bounded(self):
        jobs = SessionDemand()
        for i in range(MAX_TAB_LEASES):
            jobs.replace("old", str(i), 1, ("old-key",), 0)

        rejected = jobs.replace("old", "additional", 1, ("not-admitted",), 1)
        new = jobs.replace("new", "tab", 1, ("new-key",), 2)
        stale_reader = jobs.take("old", 3)
        current = jobs.take("new", 4)

        self.assertEqual((0, 1, None, "new-key"), (rejected, new, stale_reader, current))

    def test_sweep_demotes_replaced_hints_without_erasing_independent_lifecycle_work(self):
        sweep = SessionArchiveSweep()
        catalog = SimpleNamespace(lock=Lock(), state="observed", archive_incarnation=0, clock=lambda: 1,
                                  membership_generation=1, archive_urgent=OrderedDict(lifecycle=(0, 1)))
        binding = "binding", 0
        eligible = lambda: True

        with patch.object(sweep, "_candidate", side_effect=lambda _, key: f"proof-{key}"):
            sweep.offer_visible(catalog, binding, "tab", 1, ("old-page",), eligible=eligible)
            sweep.offer_visible(catalog, binding, "tab", 2, ("new-page",), eligible=eligible)

            first = sweep._urgent(catalog, binding)
            second = sweep._urgent(catalog, binding)
            third = sweep._urgent(catalog, binding)

        self.assertEqual(("new-page", "proof-new-page", 0), first)
        self.assertEqual(("lifecycle", "proof-lifecycle", 1), second)
        self.assertIsNone(third)
