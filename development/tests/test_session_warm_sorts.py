"""Real scalar-source warm navigation, independent lifecycle and provisional clocks."""
from dataclasses import replace
import json
import time
import unittest
from unittest.mock import patch

from development.tests.fixtures.catalog_warm_sorts import NOW, WarmSortSource
from development.tests.fixtures.compact_reports import report_service
from src.application.session_catalog import SessionCatalog, SORTS, ordered
from src.reports.watch_capture import capture_rows
from src.sources.errors import SourceUnavailableError
from src.watch.observers import observe_catalog


class WarmSortTests(unittest.TestCase):
    def setUp(self):
        self.clock = 0
        self.sequence = 1
        self.source = WarmSortSource()
        self.service = report_service(self, self.source, now_ms=NOW)
        self.catalog = SessionCatalog(clock=lambda: self.clock, clock_ms=lambda: NOW)
        self.observe()
        self.page = self.catalog.page(navigation=1)
        for _ in range(24):
            self.clock += 6
            self.catalog.tick(self.service)
            self.page = self.catalog.page(token=self.page["token"], navigation=1)
            if not self.page["pending_sort"]:
                break
        self.assertFalse(self.page["pending_sort"])
        self.assertEqual((self.page["available"], self.page["total"]), (48, 46))
        self.catalog.page(token=self.page["token"], applied=1)

    def observe(self):
        self.catalog.observe(observe_catalog(self.source, include_archived_revisions=True))

    def watch(self):
        snapshot = self.source.snapshots["root-0000"]
        capture, _ = capture_rows(self.service, snapshot.root, fresh=snapshot)
        running = next((row for row in capture.rows if row.in_progress and not row.execution_unverified), None)
        self.catalog.observe_prompts(((snapshot.root, running is not None, 0,
            running.event_id if running else "", running.at_ms if running else None),))

    def navigate(self, sort, direction):
        self.sequence += 1
        return self.catalog.page(token=self.page["token"], sort=sort, direction=direction,
            navigation=self.sequence, applied=self.sequence - 1)

    def test_48_candidates_repeated_all_seven_sorts_reuse_facts_during_running_revision_churn(self):
        timings = []
        before = dict(self.catalog.metrics)
        reads = self.source.load_count
        previous_cost = self.catalog.rows["root-0000"].ccost
        stable = {key: value for key, value in self.catalog.valid.items() if key != "root-0000"}
        for turn in range(3):
            self.clock += 6
            self.observe()  # Fresh unchanged publication is not scalar invalidation.
            snapshot = self.source.snapshots["root-0002"]
            root = replace(snapshot.root, title=f"Renamed {turn}", updated_at_ms=NOW + turn)
            self.source.snapshots[root.session_id] = replace(snapshot, root=root, sessions=(root,))
            self.observe()
            self.source.stream(turn)
            self.observe()
            self.watch()  # Real canonical prompt proof, independent of scalar revision.
            for sort in ("ccost", "ccost", "duration", *SORTS):
                for direction in (-1, 1):
                    started = time.perf_counter()
                    page = self.navigate(sort, direction)
                    timings.append(dict(sort=sort, direction=direction,
                        ms=round((time.perf_counter() - started) * 1000, 3),
                        pending=page["pending_sort"], completed=page["progress"]["completed"],
                        total=page["progress"]["total"], epoch=page["epoch"]))
                    self.assertFalse(page["pending_sort"], (turn, sort, direction, page["progress"]))
                    self.assertEqual((page["progress"]["completed"], page["progress"]["total"]), (48, 48))
                    epoch = self.catalog.leases[page["token"]]["epochs"][page["epoch"]]
                    expected = ordered(self.catalog._rows(tuple(self.catalog.roots)), sort, direction)
                    expected = [row.session_id for row in expected if row.session_id not in ("root-0046", "root-0047")]
                    self.assertEqual([row.session_id for row in epoch.rows], expected)
                    self.assertEqual(epoch.rows[0].session_id, "root-0000")
                    running = page["view"]["session_usage"][0]
                    self.assertIsNone(running["snapshot_revision"])
                    self.assertEqual(running["metric_states"]["ccost"], "retained")
            self.assertEqual(self.source.load_count, reads + turn)
            self.catalog.page(token=self.page["token"], sort="ctx", direction=1, applied=self.sequence)
            self.catalog.tick(self.service)
            self.assertGreater(self.catalog.rows["root-0000"].ccost, previous_cost)
            previous_cost = self.catalog.rows["root-0000"].ccost
            self.assertEqual(self.source.reads["root-0002"], 1, "unchanged finished facts never reacquire")
            self.assertEqual({key: value[0] for key, value in self.catalog.valid.items() if key != "root-0000"},
                {key: value[0] for key, value in stable.items()})
        print(json.dumps(dict(warm_navigations=timings, history_reads=self.source.load_count - reads,
            scalar_admissions=self.catalog.metrics["attempts"] - before["attempts"],
            cache_hits=self.catalog.metrics["cache_hits"] - before["cache_hits"],
            cache_misses=self.catalog.metrics["cache_misses"] - before["cache_misses"])))

    def test_start_only_stays_on_page_two_in_provisional_activity_order(self):
        old = self.catalog.rows["root-0001"]
        self.assertIsNone(old.last_activity_ms)
        self.assertEqual(old.prompt_started_ms, NOW - (14 * 60 + 25) * 60_000)
        self.assertFalse(old.running)
        for turn in range(4):
            self.navigate("duration", 1 if turn % 2 else -1)
            activity = self.navigate("activity", -1)
            self.catalog.page(token=activity["token"], applied=self.sequence)
            snapshot = self.source.snapshots["root-0042"]
            self.source.snapshots["root-0042"] = replace(snapshot, source_revision=f"changed-{turn}")
            self.observe()
            self.watch()
            provisional = self.catalog.page(token=activity["token"], passive=True)
            self.assertTrue(provisional["pending_sort"])
            self.assertEqual(provisional["order_state"], "provisional")
            epoch = self.catalog.leases[activity["token"]]["epochs"][provisional["epoch"]]
            ids = [row.session_id for row in epoch.rows]
            self.assertEqual(ids.index("root-0001"), 45, "qualified start is not an unknown discovery hint")
            self.assertNotIn("root-0001", [row["session_id"] for row in provisional["view"]["session_usage"]])
            self.clock += 6
            self.catalog.tick(self.service)

    def test_finish_requires_only_changed_root_and_retires_running_priority(self):
        reads = self.source.load_count
        self.source.finish()
        self.observe()
        self.watch()
        page = self.navigate("duration", -1)
        self.assertTrue(page["pending_sort"])
        self.assertEqual(page["progress"]["completed"], 47)
        self.clock += 6
        self.catalog.tick(self.service)
        ready = self.catalog.page(token=page["token"], sort="duration", navigation=self.sequence)
        self.assertFalse(ready["pending_sort"])
        self.assertEqual(self.source.load_count - reads, 1)
        self.assertFalse(self.catalog.rows["root-0000"].running)
        self.assertEqual(self.catalog.rows["root-0000"].last_activity_ms, NOW - 100)

    def test_absent_metric_lifecycle_expiry_and_transient_failure_do_not_gain_false_proof(self):
        self.catalog.rows["root-0002"] = replace(self.catalog.rows["root-0002"], context_qualified=False)
        missing = self.navigate("ctx", 1)
        self.assertTrue(missing["pending_sort"])
        self.assertEqual(missing["progress"]["completed"], 47)
        self.catalog.page(token=missing["token"], cancelled=self.sequence)
        self.source.stream(1)
        self.observe()
        self.clock += 16  # No current Watch signal; old running proof is expired.
        pending = self.navigate("ccost", 1)
        self.assertTrue(pending["pending_sort"])
        with patch("src.application.session_catalog.session_summary", side_effect=SourceUnavailableError("synthetic")):
            self.catalog.tick(self.service)
        failed = self.catalog.page(token=pending["token"], sort="ccost", direction=1, navigation=self.sequence)
        self.assertTrue(failed["pending_sort"])
        self.assertEqual(failed["progress"]["status"], "pending")
        self.clock += 121
        self.catalog.tick(self.service)
        self.assertFalse(self.catalog.page(token=pending["token"], sort="ccost", direction=1,
            navigation=self.sequence)["pending_sort"])

    def test_source_epoch_and_provenance_changes_invalidate_warm_navigation(self):
        for change in ("epoch", "provenance"):
            with self.subTest(change=change):
                page = self.navigate("ccost", 1)
                if change == "epoch":
                    self.source.observation_epoch = "new-source"
                else:
                    snapshot = self.source.snapshots["root-0002"]
                    root = replace(snapshot.root, provenance=replace(snapshot.root.provenance, source_instance="other"))
                    self.source.snapshots[root.session_id] = replace(snapshot, root=root, sessions=(root,))
                self.observe()
                with self.assertRaisesRegex(KeyError, "catalog_expired"):
                    self.catalog.page(token=page["token"], sort="ccost", direction=1, navigation=self.sequence)

    def test_start_only_later_verified_finish_and_absent_start_are_not_invented_clocks(self):
        from src.domain import TerminalEvidence, TerminalOutcome
        snapshot = self.source.snapshots["root-0001"]
        terminal = replace(snapshot.messages[-1],
            termination=TerminalEvidence(NOW - 100, TerminalOutcome.SUCCESS))
        self.source.snapshots["root-0001"] = replace(snapshot,
            messages=(*snapshot.messages[:-1], terminal), source_revision="verified-finish")
        self.observe()
        self.watch()
        page = self.navigate("activity", -1)
        self.assertTrue(page["pending_sort"])
        self.clock += 6
        self.catalog.tick(self.service)
        ready = self.catalog.page(token=page["token"], navigation=self.sequence)
        self.assertFalse(ready["pending_sort"])
        self.assertEqual(ready["view"]["session_usage"][1]["session_id"], "root-0001")
        self.assertEqual(ready["view"]["session_usage"][1]["last_activity_ms"], NOW - 100)
        self.source.snapshots["root-0001"] = replace(snapshot, messages=(), parts=(), events=(),
            invocations=(), source_revision="no-prompt")
        self.observe()
        self.clock += 6
        self.catalog.tick(self.service)
        row = self.catalog.rows["root-0001"]
        self.assertIsNone(row.last_activity_ms)
        self.assertIsNone(row.prompt_started_ms)
        self.assertIsNone(row.activity_latest_ms)
        all_time = self.catalog.page(token=page["token"], period="all", applied=self.sequence)
        epoch = self.catalog.leases[page["token"]]["epochs"][all_time["epoch"]]
        self.assertEqual(epoch.rows[-1].session_id, "root-0001")


if __name__ == "__main__":
    unittest.main()
