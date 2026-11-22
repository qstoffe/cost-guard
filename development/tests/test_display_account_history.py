"""Typed Accounts archive uses qualified shared facts, not provider or report jobs."""
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from src.analysis.cache import dependency_signature
from src.application.account_timeline import archived_timeline_view
from src.application.archive_account_history import AccountHistoryPublication, ArchiveAccountHistory, archived_account_roster
from src.cache.display_history import DisplayHistory, SessionChange, SessionFact
from src.cache.display_account_buckets import AccountBucket
from src.cache.display_requests import DisplayRequest, RequestRoster
from src.cache.display_usage_reader import USAGE_SLICE
from src.domain import AccountRef, AccountSnapshot, CostDisposition
from src.web.display_archive import DisplayArchive
from src.web.display_binding import DisplayBinding


NOW = int(datetime(2026, 10, 25, 12, tzinfo=timezone.utc).timestamp() * 1000)
HOUR = 3_600_000
REF = AccountRef("source-account", "openai", account_id="selected")
ACCOUNT = bytes.fromhex(dependency_signature(REF.key))
OTHER = bytes.fromhex(dependency_signature(("source-account", "openai", "id:foreign")))


def observation(key, clock, *, digest=ACCOUNT, provider="openai-codex", costs=("1", "0", "0", "0"),
                known=0b1111, fork=None, root="selected", disposition=CostDisposition.UNKNOWN.value):
    return DisplayRequest(key.to_bytes(8, "big"), clock, fork, "executing", "prompt",
        provider, "model", "recorded", digest, (1, 0, 0, 0, 0), known, Decimal("100"), "USD", disposition,
        tuple(map(Decimal, costs)) if costs else None, None, False, root)


class DisplayAccountHistoryTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.history = DisplayHistory(self.root)
        self.history.initialize()

    def save(self, rows, *, root="selected", revision="r1", pricing="reference-1", source="trusted"):
        previous = self.history.session_checkpoints(source, (root,)).get(root)
        self.history.commit_sessions(source, (SessionChange(SessionFact(root, revision, root),
            previous.revision if previous else None, previous_progress=previous.progress if previous else 0,
            request_roster=RequestRoster(pricing, rows, ())),))

    def reducer(self, now=NOW, zone="UTC", roster=None):
        return ArchiveAccountHistory("trusted", zone, now, {ACCOUNT: {"openai"}} if roster is None else roster)

    def finish(self, publisher):
        for _ in range(50):
            if not publisher.step(self.history, eligible=lambda: True):
                return publisher.published
        self.fail("bounded fixture did not finish")

    def test_only_exact_account_evidence_counts_and_absence_does_not_retract(self):
        self.save((
            observation(0, NOW - HOUR, costs=("1.1111111111111111111111111111", "0", "0", "0")),
            observation(1, NOW - HOUR, costs=("0.0000000000000000000000000002", "0", "0", "0")),
            observation(2, NOW - HOUR, digest=OTHER),
            observation(3, NOW - HOUR, digest=None),
            observation(4, NOW - HOUR, provider="unrelated"),
            observation(5, NOW - HOUR, costs=None),
            observation(6, NOW, costs=("999", "0", "0", "0")),
            observation(7, NOW - 2 * HOUR, costs=("0", "0", "0", "0")),
        ))
        self.save((observation(20, NOW - HOUR),), source="foreign")
        build = self.reducer()
        publisher = AccountHistoryPublication(build)
        self.assertTrue(self.finish(publisher))
        checkpoint = self.history.session_checkpoints("trusted", ("selected",))["selected"]
        self.history.commit_sessions("trusted", missing=(("selected", checkpoint),))
        self.history = DisplayHistory(self.root)
        self.history.initialize()
        second = self.reducer(NOW + 1)
        self.assertTrue(self.finish(AccountHistoryPublication(second)))

        _, as_of, rows = self.history.read_account_buckets("trusted", "UTC", build.roster,
                                                          "today", ACCOUNT, NOW - 12 * HOUR, NOW + 1)
        by_clock = {row.start: row for row in rows}
        combined = by_clock[NOW - HOUR]
        self.assertEqual(NOW + 1, as_of)
        self.assertEqual(Decimal("1.1111111111111111111111111113"), combined.subtotal)
        self.assertEqual((3, 2), (combined.matched, combined.priced))
        self.assertEqual(Decimal(0), by_clock[NOW - 2 * HOUR].subtotal)
        self.assertIsNone(by_clock[NOW - 3 * HOUR].subtotal)
        self.assertEqual(Decimal("999"), by_clock[NOW].subtotal)

    def test_two_stockholm_fold_buckets_are_distinct_and_floor_is_half_open(self):
        first = int(datetime(2026, 10, 25, 0, tzinfo=timezone.utc).timestamp() * 1000)
        self.save((observation(1, first, costs=("2", "0", "0", "0")),
                   observation(2, first + HOUR, costs=("3", "0", "0", "0"))))
        build = self.reducer(zone="Europe/Stockholm")

        self.assertTrue(self.finish(AccountHistoryPublication(build)))
        _, _, rows = self.history.read_account_buckets("trusted", build.zone, build.roster,
                                                      "today", ACCOUNT, first, NOW)
        self.assertEqual([(first, first + HOUR, Decimal(2)),
                          (first + HOUR, first + 2 * HOUR, Decimal(3))],
                         [(row.start, row.end, row.subtotal) for row in rows if row.subtotal is not None])

    def test_precommitted_rows_are_invisible_and_corrections_invalidate_partial_build(self):
        self.save(tuple(observation(index, NOW - HOUR) for index in range(USAGE_SLICE + 2)))
        build = self.reducer()
        publisher = AccountHistoryPublication(build)
        self.assertTrue(publisher.step(self.history, eligible=lambda: True))
        self.assertFalse(build.done)
        self.save((observation(0, NOW - HOUR, costs=("10", "0", "0", "0")),), revision="r2")
        self.assertFalse(publisher.step(self.history, eligible=lambda: True))
        self.assertFalse(publisher.published)
        self.assertIsNone(self.history.read_account_buckets("trusted", "UTC", build.roster,
                                                           "today", ACCOUNT, 0, NOW))

        updated = AccountHistoryPublication(self.reducer())
        self.assertTrue(updated.step(self.history, eligible=lambda: True))
        self.assertTrue(updated.step(self.history, eligible=lambda: True))
        self.assertTrue(updated.step(self.history, eligible=lambda: True))  # First bounded staging write.
        self.assertIsNone(self.history.read_account_buckets("trusted", "UTC", build.roster,
                                                           "today", ACCOUNT, 0, NOW))
        cleared = self.history.clear_confirmed_sessions("trusted", self.history.source_state("trusted"))
        self.assertEqual(1, cleared.archive_epoch)
        self.assertFalse(updated.step(self.history, eligible=lambda: True))
        self.assertFalse(updated.published)

    def test_unqualified_clone_or_mixed_price_signature_withholds_only_affected_buckets(self):
        self.save((observation(1, NOW - 2 * HOUR), observation(2, NOW - 3 * HOUR)))
        self.save((observation(3, NOW - 2 * HOUR, root="extra"),), root="extra", pricing="different")
        self.save((observation(4, NOW - HOUR, root="extra"), observation(5, NOW - HOUR, root=None, fork=b"unknown")),
                  root="extra", revision="r2")
        build = self.reducer()
        self.assertTrue(self.finish(AccountHistoryPublication(build)))

        _, _, rows = self.history.read_account_buckets("trusted", "UTC", build.roster,
                                                      "today", ACCOUNT, NOW - 3 * HOUR, NOW)

        self.assertEqual([Decimal(1), None, None, None], [row.subtotal for row in rows])
        self.assertEqual([1, 2, 1, 0], [row.priced for row in rows])

    def test_account_offer_joins_the_catalog_lane_without_native_quota_storage(self):
        account = AccountSnapshot(REF, NOW, "OpenAI")
        roster = archived_account_roster((SimpleNamespace(account=account),))
        self.assertEqual({ACCOUNT: frozenset({"openai"})}, roster)
        self.save((observation(1, NOW - HOUR),))
        archive = DisplayArchive(self.root, lambda *_: None, accounts_enabled=True)
        self.addCleanup(archive.close)
        archive._set_binding(DisplayBinding("trusted", "registered"))
        series = (SimpleNamespace(account=account, label="Verified account"),)
        archive.accounts.offer(series, verified=False)
        self.assertIsNone(archive.next_projection(lambda: None))
        archive.accounts.offer(series, verified=True)
        for _ in range(20):
            turn = archive.next_projection(lambda: None)
            if turn is None:
                break
            turn(NOW, active=lambda: True)
        else:
            self.fail("archive did not finish its cached Accounts turns")

        build = self.reducer()
        _, _, rows = self.history.read_account_buckets("trusted", "UTC", build.roster,
                                                      "today", ACCOUNT, NOW - HOUR, NOW)
        self.assertEqual([Decimal(1), None], [row.subtotal for row in rows])
        snapshot = archive.accounts.snapshot("today", NOW)
        self.assertEqual("unknown", snapshot["view"]["coverage"])
        self.assertEqual("Verified account", snapshot["view"]["series"][0]["account"])
        self.assertEqual("1", snapshot["view"]["series"][0]["points"][-2]["amount"])
        self.assertIsNone(snapshot["view"]["series"][0]["points"][-1])
        self.assertEqual(1792972800000, snapshot["expires_ms"])  # Next UTC midnight.

    def test_rolling_window_never_keeps_an_old_subtotal_across_its_start(self):
        day = 24 * HOUR
        start = NOW - 7 * day
        midnight = start + 12 * HOUR
        rows = (
            AccountBucket("7-days", ACCOUNT, start, midnight, Decimal(2), 1, 1, "same"),
            AccountBucket("7-days", ACCOUNT, midnight, midnight + day, Decimal(3), 1, 1, "same"),
        )
        roster = ((ACCOUNT, "Known account"),)

        exact = archived_timeline_view("7-days", NOW, NOW, "UTC", roster, rows).to_json()
        shifted = archived_timeline_view("7-days", NOW, NOW + 1, "UTC", roster, rows).to_json()
        boundary = archived_timeline_view("7-days", NOW, NOW + 12 * HOUR, "UTC", roster, rows).to_json()

        self.assertEqual("5", exact["series"][0]["total"]["amount"])
        self.assertIsNone(shifted["series"][0]["points"][0])
        self.assertEqual("3", shifted["series"][0]["total"]["amount"])
        self.assertEqual([midnight, midnight + day], list(boundary["buckets"][0]))
        self.assertEqual("3", boundary["series"][0]["total"]["amount"])
