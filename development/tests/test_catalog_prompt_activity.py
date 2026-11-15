"""Source-confirmed Sessions clocks, never catalog/part modification clocks."""
from dataclasses import replace
import unittest

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests.fixtures.catalog_prompt_activity import at, finished_snapshot
from src.application.session_catalog import SessionCatalog
from src.domain import NormalizedPart, TerminalEvidence, TerminalOutcome
from src.reports.session_summary import session_summary
from src.watch.observers import observe_catalog
from src.analysis.session_activity import activity_fields
from src.analysis import analyze_snapshot
from src.reports.sampling import AnalyzedRoot
from src.domain import EventKind, NormalizedEvent
from src.sources.errors import SourceUnavailableError
from unittest.mock import patch


class CatalogPromptActivityTests(unittest.TestCase):
    def setUp(self):
        self.now = at("02:00:00")
        self.clock = 0
        self.source = SyntheticMonthSource(0, 1, month_start_ms=1)
        self.source.snapshots = {"root-0000": finished_snapshot()}
        self.service = report_service(self, self.source, now_ms=self.now)
        self.catalog = SessionCatalog(clock=lambda: self.clock, clock_ms=lambda: self.now)
        self.observe()

    def observe(self):
        self.catalog.observe(observe_catalog(self.source, include_archived_revisions=True))

    def acquire(self, **request):
        page = self.catalog.page(**request)
        self.catalog.tick(self.service)
        return self.catalog.page(token=page["token"], **request)

    def test_finished_0118_not_root_archive_or_child_metadata_0152(self):
        snapshot = self.source.snapshots["root-0000"]
        for variant in ("root", "archive", "child", "part"):
            with self.subTest(variant=variant):
                root = replace(snapshot.root, archived_at_ms=at("01:52:00") if variant == "archive" else None)
                sessions = (root,)
                messages = snapshot.messages
                if variant == "child":
                    sessions += (replace(root, session_id="child", parent_session_id=root.session_id),)
                if variant == "part":
                    assistant = messages[-1]
                    part = NormalizedPart("rewrite", assistant.message_id, root.session_id, "text",
                        at("01:17:00"), at("01:52:00"), assistant.provenance, {"text": "saved"})
                    messages = (*messages[:-1], replace(assistant, parts=(part,)))
                self.source.snapshots[root.session_id] = replace(snapshot, root=root, sessions=sessions,
                    messages=messages, source_revision=variant)
                self.clock += 6
                self.observe()

                page = self.acquire()

                self.assertEqual(page["view"]["session_usage"][0]["last_activity_ms"], at("01:18:00"))
                self.assertFalse(page["pending_sort"])

    def test_cold_page_never_displays_metadata_and_does_not_read_history(self):
        page = self.catalog.page()
        self.assertEqual(self.source.load_count, 0)
        self.assertIsNone(page["view"]["session_usage"][0]["last_activity_ms"])
        self.assertTrue(page["pending_sort"])

    def test_new_real_prompt_advances_but_metadata_revision_retains_then_replaces(self):
        first = self.acquire()
        original = self.source.snapshots["root-0000"]
        self.source.snapshots["root-0000"] = replace(original,
            root=replace(original.root, updated_at_ms=at("01:59:00")), source_revision="metadata")
        self.observe()
        pending = self.catalog.page(token=first["token"])
        self.assertEqual(pending["view"]["session_usage"][0]["last_activity_ms"], at("01:18:00"))
        self.assertEqual(pending["view"]["session_usage"][0]["activity_state"], "retained")
        self.clock += 6
        self.catalog.tick(self.service)
        self.source.snapshots["root-0000"] = replace(finished_snapshot(finished=at("01:52:00")),
            source_revision="real-prompt")
        self.observe()
        self.clock += 6
        self.catalog.tick(self.service)
        latest = self.catalog.page(token=first["token"])
        self.assertEqual(latest["view"]["session_usage"][0]["last_activity_ms"], at("01:52:00"))
        self.assertFalse(latest["pending_sort"])

    def test_running_unverified_and_explicit_failed_terminal(self):
        snapshot = self.source.snapshots["root-0000"]
        assistant = snapshot.messages[-1]
        for state in ("running", "unverified", "failed", "aborted"):
            with self.subTest(state=state):
                terminal = TerminalEvidence(at("01:52:00"),
                    TerminalOutcome.FAILURE if state == "failed" else TerminalOutcome.CANCELLATION)
                root = replace(snapshot.root, active=state == "running")
                message = replace(assistant, completed_at_ms=None, finish_reason=None,
                    termination=terminal if state in ("failed", "aborted") else None)
                self.source.snapshots[root.session_id] = replace(snapshot, root=root, sessions=(root,),
                    messages=(*snapshot.messages[:-1], message), invocations=(), source_revision=state)
                self.clock += 6
                self.observe()

                row, _ = session_summary(self.service, root, state, active=True)

                self.assertEqual(row.last_activity_ms,
                    at("01:52:00") if state in ("failed", "aborted") else
                    at("01:18:00") - 300 if state == "running" else None)
                self.assertEqual(row.running, state == "running")
                self.assertEqual(row.prompt_started_ms, at("01:18:00") - 300)

    def test_running_start_is_fixed_under_metadata_part_and_revision_churn_then_new_prompt_and_terminal(self):
        source = SyntheticMonthSource(1, 2, month_start_ms=at("01:00:00"), running_roots=1)
        snapshot = replace(source.snapshots["root-0000"], complete=True)
        self.source.snapshots = {"root-0000": snapshot}
        self.observe()
        first = self.acquire(period="all")
        start = at("01:00:01")
        for sequence in range(5):
            root = replace(snapshot.root, updated_at_ms=self.now - sequence)
            assistant = snapshot.messages[-1]
            part = NormalizedPart("stream", assistant.message_id, root.session_id, "text",
                start + 100, self.now - sequence, assistant.provenance, {"text": "streaming" * sequence})
            self.source.snapshots[root.session_id] = replace(snapshot, root=root, sessions=(root,),
                messages=(*snapshot.messages[:-1], replace(assistant, parts=(part,))),
                source_revision=f"stream-{sequence}")
            self.clock += 6
            self.observe()
            self.catalog.tick(self.service)
            row = self.catalog.page(token=first["token"], period="all")["view"]["session_usage"][0]
            self.assertEqual(row["last_activity_ms"], start)
            self.assertTrue(row["running"])
        newer = SyntheticMonthSource(1, 3, month_start_ms=at("01:00:00"), running_roots=1).snapshots["root-0000"]
        self.source.snapshots["root-0000"] = replace(newer, complete=True, source_revision="new-prompt")
        self.clock += 6
        self.observe()
        self.catalog.tick(self.service)
        latest = self.catalog.page(token=first["token"], period="all")["view"]["session_usage"][0]
        self.assertEqual(latest["last_activity_ms"], at("01:00:02"))
        self.assertTrue(latest["running"])
        for outcome in (TerminalOutcome.SUCCESS, TerminalOutcome.FAILURE, TerminalOutcome.CANCELLATION):
            terminal = TerminalEvidence(at("01:52:00"), outcome)
            root = replace(newer.root, active=False)
            self.source.snapshots[root.session_id] = replace(newer, root=root, sessions=(root,), complete=True,
                messages=(*newer.messages[:-1], replace(newer.messages[-1], termination=terminal)),
                source_revision=outcome.value)
            self.clock += 6
            self.observe()
            self.catalog.tick(self.service)
            ended = self.catalog.page(token=first["token"], period="all")["view"]["session_usage"][0]
            self.assertEqual(ended["last_activity_ms"], at("01:52:00"))
            self.assertFalse(ended["running"])

    def test_running_before_local_midnight_remains_in_today_but_finished_ancient_work_does_not(self):
        for zone in ("UTC", "Europe/Stockholm"):
            source = SyntheticMonthSource(2, 1, month_start_ms=at("00:00:00") - 4 * 3_600_000,
                                          running_roots=1)
            source.snapshots = {key: replace(value, complete=True) for key, value in source.snapshots.items()}
            service = report_service(self, source, now_ms=self.now, timezone_id=zone)
            catalog = SessionCatalog(clock=lambda: self.clock, clock_ms=lambda: self.now, timezone_id=zone)
            catalog.observe(observe_catalog(source, include_archived_revisions=True))
            first = catalog.page(period="all")
            catalog.tick(service)
            today = catalog.page(token=first["token"], navigation=1, period="today")
            self.assertFalse(today["pending_sort"])
            self.assertEqual([row["session_id"] for row in today["view"]["session_usage"]], ["root-0000"])
            self.assertLess(today["view"]["session_usage"][0]["last_activity_ms"], today["window"]["start_ms"])
            self.assertTrue(today["view"]["session_usage"][0]["running"])

    def test_metadata_today_candidate_is_excluded_after_yesterdays_prompt_is_verified(self):
        self.source.snapshots["root-0000"] = finished_snapshot(finished=at("00:00:00") - 1)
        self.observe()
        page = self.acquire()
        self.assertEqual(page["total"], 0)
        self.assertFalse(page["pending_sort"])
        self.assertEqual((page["progress"]["completed"], page["progress"]["total"]), (1, 1))

    def test_future_metadata_admits_today_but_old_metadata_discovery_is_explicit(self):
        snapshot = self.source.snapshots["root-0000"]
        for metadata in (self.now + 86_400_000, at("00:00:00") - 1000):
            with self.subTest(metadata=metadata):
                root = replace(snapshot.root, created_at_ms=metadata, updated_at_ms=metadata)
                self.source.snapshots[root.session_id] = replace(snapshot, root=root, sessions=(root,))
                self.catalog = SessionCatalog(clock=lambda: self.clock, clock_ms=lambda: self.now)
                self.observe()
                page = self.catalog.page()
                self.assertEqual(page["candidate_scope"], "source_catalog_metadata")
                self.assertEqual(page["total"], 1 if metadata > self.now else 0)
                self.assertEqual(self.source.load_count, 0)
        # All explicitly expands discovery; the qualified event then admits the
        # same source/root in Today even if native metadata was stale.
        all_time = self.acquire(period="all")
        today = self.catalog.page(token=all_time["token"])
        self.assertEqual(today["total"], 1)
        self.assertEqual(today["view"]["session_usage"][0]["last_activity_ms"], at("01:18:00"))

    def test_new_root_and_changed_revision_hints_survive_identical_catalog_polls(self):
        old = at("00:00:00") - 1000
        snapshot = finished_snapshot(metadata=old)
        root = replace(snapshot.root, created_at_ms=old)
        self.source.snapshots["root-0000"] = replace(snapshot, root=root, sessions=(root,))
        self.catalog = SessionCatalog(clock=lambda: self.clock, clock_ms=lambda: self.now)
        self.observe()
        self.assertEqual(self.catalog.page()["total"], 0)
        self.source.snapshots["root-0000"] = replace(self.source.snapshots["root-0000"], source_revision="new")
        second = finished_snapshot(1, metadata=old)
        second = replace(second, root=replace(second.root, created_at_ms=old))
        self.source.snapshots["root-0001"] = second
        self.observe()
        self.observe()
        self.assertEqual(self.catalog.page()["total"], 2)

    def test_partial_history_cannot_verify_latest_or_exclude_candidate(self):
        self.source.snapshots["root-0000"] = replace(finished_snapshot(
            finished=at("00:00:00") - 1), complete=False, source_revision="partial")
        self.observe()
        page = self.acquire()
        self.assertEqual(page["total"], 1)
        self.assertTrue(page["pending_sort"])
        self.assertEqual(page["view"]["session_usage"][0]["activity_state"], "partial")

    def test_same_id_new_source_drops_previous_clock_but_outage_retains_same_source(self):
        first = self.acquire()
        self.catalog.observe(None, unavailable=True)
        retained = self.catalog.page(token=first["token"])
        self.assertEqual(retained["view"]["session_usage"][0]["last_activity_ms"], at("01:18:00"))
        self.assertEqual(retained["view"]["session_usage"][0]["activity_state"], "retained")
        snapshot = self.source.snapshots["root-0000"]
        for field, value in (("source_instance", "other-host"), ("source_generation", "other-epoch")):
            root = replace(snapshot.root, provenance=replace(snapshot.root.provenance, **{field: value}))
            self.source.snapshots[root.session_id] = replace(snapshot, root=root, sessions=(root,))
            self.observe()
            page = self.catalog.page(token=first["token"])
            self.assertIsNone(page["view"]["session_usage"][0]["last_activity_ms"])
            self.assertTrue(page["pending_sort"])

    def test_registration_epoch_cannot_reuse_same_id_revision_or_scalar_cache(self):
        self.source.observation_epoch = "first-registration"
        self.observe()
        first = self.acquire()
        reads = self.source.load_count
        self.source.observation_epoch = "new-registration"
        self.observe()
        pending = self.catalog.page(token=first["token"])
        self.assertIsNone(pending["view"]["session_usage"][0]["last_activity_ms"])
        self.assertTrue(pending["pending_sort"])
        self.catalog.tick(self.service)
        self.assertEqual(self.source.load_count, reads + 1)
        root = self.source.snapshots["root-0000"].root
        original = self.service._analyze
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            self.source.observation_epoch = "changed-during-acquisition"
            return result
        with patch.object(self.service, "_analyze", side_effect=changed):
            with self.assertRaises(SourceUnavailableError):
                session_summary(self.service, root, "synthetic-rev-0", active=True)

    def test_recomputed_earlier_or_absent_event_replaces_retained_clock(self):
        first = self.acquire()
        for count, expected in ((1, at("01:00:00")), (0, None)):
            snapshot = finished_snapshot(finished=at("01:00:00"))
            self.source.snapshots["root-0000"] = replace(snapshot,
                messages=snapshot.messages if count else (), events=snapshot.events if count else (),
                invocations=snapshot.invocations if count else (), source_revision=f"corrected-{count}")
            self.observe()
            self.clock += 6
            self.catalog.page(token=first["token"], period="all")
            self.catalog.tick(self.service)
            row = self.catalog.page(token=first["token"], period="all")["view"]["session_usage"][0]
            self.assertEqual(row["last_activity_ms"], expected)
            self.assertEqual(row["activity_state"], "ready")

    def test_confirmed_event_sort_ignores_metadata_and_preserves_pinned_epoch(self):
        self.source.snapshots = {f"root-{index:04d}": finished_snapshot(index,
            finished=at("01:00:00") + index * 1000) for index in range(100)}
        self.observe()
        page = self.catalog.page()
        for _ in range(25):
            self.catalog.tick(self.service)
        ready = self.catalog.page(token=page["token"])
        self.assertFalse(ready["pending_sort"])
        self.assertEqual([row["session_id"] for row in ready["view"]["session_usage"]],
                         [f"root-{index:04d}" for index in range(99, 74, -1)])
        older = self.catalog.page(token=page["token"], offset=75, epoch=ready["epoch"])
        ascending = self.catalog.page(token=page["token"], direction=1)
        self.assertEqual(ascending["view"]["session_usage"][0]["session_id"], "root-0000")
        snapshot = self.source.snapshots["root-0000"]
        self.source.snapshots["root-0000"] = replace(snapshot,
            root=replace(snapshot.root, updated_at_ms=self.now), source_revision="metadata-only")
        self.observe()
        pending = self.catalog.page(token=page["token"])
        self.assertEqual(pending["view"]["session_usage"][0]["session_id"], "root-0099")
        pinned = self.catalog.page(token=page["token"], offset=75, epoch=ready["epoch"])
        self.assertEqual([row["session_id"] for row in pinned["view"]["session_usage"]],
                         [row["session_id"] for row in older["view"]["session_usage"]])
        self.assertEqual(pinned["order_state"], "verified")

    def test_attributed_child_completion_but_not_independent_later_child_turn(self):
        root_snapshot = finished_snapshot()
        child_snapshot = finished_snapshot(1, finished=at("01:52:00"))
        root, child = root_snapshot.root, replace(child_snapshot.root, parent_session_id=root_snapshot.root.session_id)
        assistant = root_snapshot.messages[-1]
        link = NormalizedPart("link", assistant.message_id, root.session_id, "tool",
            assistant.created_at_ms + 1, at("01:18:00"), assistant.provenance,
            {"tool": "subagent", "state": {"status": "completed", "metadata": {"sessionID": child.session_id},
             "time": {"start": assistant.created_at_ms + 1, "end": at("01:18:00")}}})
        child = replace(child, created_at_ms=assistant.created_at_ms + 2)
        # A child launched before the parent's return can finish afterward.
        child_events = tuple(replace(event, created_at_ms=assistant.created_at_ms + 3) for event in child_snapshot.events)
        child_messages = tuple(replace(message, created_at_ms=assistant.created_at_ms + 4)
            for message in child_snapshot.messages)
        snapshot = replace(root_snapshot, sessions=(root, child),
            messages=(*root_snapshot.messages[:-1], replace(assistant, parts=(link,)), *child_messages),
            events=(*root_snapshot.events, *child_events), parts=(link,),
            invocations=(*root_snapshot.invocations, *child_snapshot.invocations))
        item = AnalyzedRoot(root, analyze_snapshot(snapshot, now_ms=self.now), False, snapshot)
        self.assertEqual(activity_fields(item)["last_activity_ms"], at("01:52:00"))
        independent = replace(child_events[0], event_id="independent", created_at_ms=at("01:58:00"))
        reply = replace(child_messages[-1], message_id="independent-reply",
            parent_message_id="independent", created_at_ms=at("01:58:01"), completed_at_ms=at("01:59:00"))
        later_snapshot = replace(snapshot, events=(*snapshot.events, independent),
            messages=(*snapshot.messages, reply))
        item = AnalyzedRoot(root, analyze_snapshot(later_snapshot, now_ms=self.now), False, later_snapshot)
        self.assertEqual(activity_fields(item)["last_activity_ms"], at("01:52:00"))
        # A newer root turn owns the clock even when an older linked turn ends later.
        newer = finished_snapshot(finished=at("01:45:00"))
        new_event = replace(newer.events[0], event_id="new-root-turn")
        new_messages = tuple(replace(message, message_id="new-" + message.message_id,
            parent_message_id="new-root-turn" if message.parent_message_id else None)
            for message in newer.messages)
        new_messages = (replace(new_messages[0], message_id="new-root-turn"), *new_messages[1:])
        overlapping = replace(later_snapshot, events=(*later_snapshot.events, new_event),
            messages=(*later_snapshot.messages, *new_messages))
        item = AnalyzedRoot(root, analyze_snapshot(overlapping, now_ms=self.now), False, overlapping)
        fields = activity_fields(item)
        self.assertEqual(fields["last_activity_ms"], at("01:45:00"))
        self.assertEqual(fields["activity_latest_ms"], at("01:52:00"), "period evidence remains independent")
        # No valid task link: mere ancestry/metadata does not count as work.
        snapshot = replace(snapshot, messages=(*root_snapshot.messages, *child_snapshot.messages),
            events=(*root_snapshot.events, *child_snapshot.events))
        item = AnalyzedRoot(root, analyze_snapshot(snapshot, now_ms=self.now), False, snapshot)
        self.assertEqual(activity_fields(item)["last_activity_ms"], at("01:18:00"))

    def test_compaction_and_sparse_prompt_start_without_priced_requests(self):
        snapshot = self.source.snapshots["root-0000"]
        event = NormalizedEvent("compact", snapshot.root.session_id, EventKind.COMPACTION,
            at("01:50:00"), snapshot.root.provenance)
        assistant = replace(snapshot.messages[-1], message_id="summary", parent_message_id="compact",
            created_at_ms=at("01:50:01"), completed_at_ms=at("01:52:00"), summary=True)
        snapshot = replace(snapshot, events=(*snapshot.events, event),
            messages=(*snapshot.messages, assistant))
        item = AnalyzedRoot(snapshot.root, analyze_snapshot(snapshot, now_ms=self.now), False, snapshot)
        self.assertEqual(activity_fields(item)["last_activity_ms"], at("01:52:00"))
        event = replace(event, kind=EventKind.USER_PROMPT, created_at_ms=at("01:55:00"))
        snapshot = replace(snapshot, events=(event,), messages=(), invocations=())
        item = AnalyzedRoot(snapshot.root, analyze_snapshot(snapshot, now_ms=self.now), False, snapshot)
        fields = activity_fields(item)
        self.assertIsNone(fields["last_activity_ms"], "a bare start is not a supported finish")
        self.assertEqual(fields["prompt_started_ms"], at("01:55:00"))


if __name__ == "__main__":
    unittest.main()
