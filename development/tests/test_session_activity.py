"""Whole-session activity, safe terminal details and pinned historical paging."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from development.tests.fixtures.report_runtime import FakePricingProvider, FakeSource
from development.tests.fixtures.session_activity import activity_snapshot
from development.tests.fixtures.session_snapshots import message, part, prov, MODEL
from src.application.session_activity import build_activity, activity_page
from src.application.session_detail import SessionDetails
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.domain import EventKind, MessageRole
from src.reports import ReportService
from src.sources.selection import SourceSelection

ROOT = Path(__file__).resolve().parents[2]
ORIGINS = SimpleNamespace(skill_origins_for_session=lambda _: {"auto-github-api": "custom"})


class SessionActivityTests(unittest.TestCase):
    def test_all_prompts_compaction_physical_duplicates_and_safe_distinct_outcomes(self):
        snapshot = activity_snapshot()

        result = build_activity(snapshot, ORIGINS)

        self.assertEqual({"read": 4, "shell": 1, "grep": 1, "custom skill": 2, "task": 1}, dict(result["counts"]))
        self.assertEqual((4, 5, 5), (result["failed_count"], result["failed_or_cancelled_count"], len(result["failures"])))
        self.assertEqual(5, len({call["identity"] for call in result["failures"]}))
        self.assertEqual([{"skill_id": "auto-github-api", "failed_count": 0}], list(result["skills"]))
        reads = [call for call in result["failures"] if call["tool_name"] == "read"]
        self.assertEqual(4, len(reads))
        self.assertEqual(1, sum(call["reason"] == "Failure reason unavailable" for call in reads))
        self.assertTrue(all(call["prompt_id"] for call in reads))
        wire = json.dumps(result)
        for secret in ("synthetic-secret", "private arbitrary error", "private file contents"):
            self.assertNotIn(secret, wire)
        cancelled = next(call for call in result["failures"] if call["outcome"] == "cancelled")
        self.assertIn("--token [redacted] --check", cancelled["text"])
        self.assertEqual("error", cancelled["recorded_status"])

    def test_recursive_windows_exclude_unrelated_and_late_child_calls(self):
        snapshot = activity_snapshot()
        child = next(session for session in snapshot.sessions if session.session_id == "child")
        nested = replace(child, session_id="nested", parent_session_id="child",
                         created_at_ms=1260, provenance=prov("nested"))
        link = part("nested-link", "ca", "child", "tool", {"tool": "subagent", "state": {
            "status": "completed", "time": {"start": 1250, "end": 1390},
            "metadata": {"sessionID": "nested"}}}, 1250)
        failure = part("nested-read", "na", "nested", "tool", {"tool": "read", "state": {
            "status": "error", "input": {"path": "src/nested.py"}, "error": "EACCES"}}, 1290)
        messages = tuple(replace(m, parts=(*m.parts, link)) if m.message_id == "ca" else m
                         for m in snapshot.messages)
        messages += (message("nu", "nested", MessageRole.USER, 1270),
            message("na", "nested", MessageRole.ASSISTANT, 1280, parent="nu",
                    parts=(failure,), completed=1350, model=MODEL),
            message("unrelated", "other", MessageRole.ASSISTANT, 1280, parent="elsewhere",
                    parts=(replace(failure, session_id="other"),), completed=1350),
            message("late", "child", MessageRole.ASSISTANT, 5000, parent="late-user",
                    parts=(replace(failure, session_id="child", message_id="late", created_at_ms=5010),), completed=5100))
        event = replace(snapshot.events[0], event_id="nu", session_id="nested",
                        kind=EventKind.USER_PROMPT, created_at_ms=1270, provenance=prov("nested"))
        snapshot = replace(snapshot, messages=messages, sessions=(*snapshot.sessions, nested),
                           events=(*snapshot.events, event), parts=tuple(p for m in messages for p in m.parts))

        result = build_activity(snapshot, ORIGINS)

        self.assertEqual(5, dict(result["counts"])["read"])
        self.assertEqual(1, dict(result["counts"])["subagent"])
        nested_detail = next(call for call in result["failures"] if "nested.py" in call["text"])
        self.assertEqual("Linked agent", nested_detail["owner"])
        self.assertEqual("Permission denied", nested_detail["reason"])

    def test_complete_counts_unbounded_reachability_and_truthful_partial_origins(self):
        result = build_activity(replace(activity_snapshot(300), complete=False), SimpleNamespace())

        pages = [activity_page(result, offset) for offset in range(0, 301, 25)]

        self.assertEqual(300, result["failed_count"])
        self.assertFalse(result["complete"])
        self.assertTrue(result["skills_partial"])
        self.assertEqual((), result["skills"])
        calls = [call for page in pages for call in page["failures"]]
        self.assertEqual(301, len({call["identity"] for call in calls}))
        self.assertTrue(all(len(page["failures"]) <= 25 for page in pages))
        self.assertTrue(all(len(json.dumps(page)) < 150_000 for page in pages))

    def test_source_epoch_changes_ui_scope_without_inventing_activity(self):
        snapshot = activity_snapshot()
        first = build_activity(snapshot, SimpleNamespace(observation_epoch="first"))

        changed = build_activity(snapshot, SimpleNamespace(observation_epoch="restarted"))

        self.assertNotEqual(first["scope"], changed["scope"])
        self.assertEqual(first["counts"], changed["counts"])
        self.assertEqual(first["failures"], changed["failures"])

    def test_wrong_source_details_are_omitted_without_losing_counts(self):
        snapshot = activity_snapshot()
        messages = tuple(replace(m, parts=tuple(replace(p, provenance=replace(p.provenance, source_generation="foreign"))
            if p.data.get("callID") == "physical-0000" else p for p in m.parts)) for m in snapshot.messages)

        result = build_activity(replace(snapshot, messages=messages), ORIGINS)

        self.assertEqual((4, 1, 4), (result["failed_count"], result["unavailable"], len(result["failures"])))

    def test_missing_timing_keeps_recorded_historical_call_and_latest_terminal_copy_wins(self):
        snapshot = activity_snapshot()
        messages = []
        for item in snapshot.messages:
            parts = tuple(replace(p, created_at_ms=0) if p.data.get("callID") == "physical-0001" else p
                          for p in item.parts)
            if item.message_id == "a_comp":
                first = next(p for p in parts if p.data.get("callID") == "physical-0002")
                parts += (replace(first, part_id="latest-copy", updated_at_ms=4000,
                                  data={**first.data, "state": {"status": "completed"}}),)
            messages.append(replace(item, parts=parts))

        result = build_activity(replace(snapshot, messages=tuple(reversed(messages))), ORIGINS)

        self.assertEqual((4, 3, 4), (dict(result["counts"])["read"], result["failed_count"], len(result["failures"])))
        self.assertEqual(0, result["failures"][0]["started_at_ms"])

    def test_detail_revision_freeze_cache_and_security_invalidation(self):
        with tempfile.TemporaryDirectory() as directory:
            database = CacheDatabase(Path(directory)); database.initialize()
            source = FakeSource(activity_snapshot(60))
            service = ReportService(selection=SourceSelection(source, "v1", (), source.probe()),
                pricing_provider=FakePricingProvider(), account_provider=None, cache_repository=CacheRepository(database),
                config=dict(load_configuration(ROOT).values, timezone="UTC"), now_ms=100_000)
            clock = [0]
            details = SessionDetails(clock=lambda: clock[0])
            token = details.open("root", "live")
            details.tick(service)
            first = details.page(token, 0, begin=True)
            self.assertEqual((60, 25), (first["activity"]["failed_count"], len(first["activity"]["failures"])))
            with patch("src.application.session_activity.build_activity", side_effect=AssertionError("repeated activity scan")):
                clock[0] += 6
                details.tick(service)
            source.snapshot = replace(activity_snapshot(61), source_revision="next")
            clock[0] += 6
            details.tick(service)
            second_page = details.activity_page(token, first["revision"], 25)
            self.assertEqual(61, second_page["total"], "old pinned revision has 60 failures + cancellation")
            latest = details.page(token, 0, begin=True)
            self.assertEqual(61, latest["activity"]["failed_count"])
            with self.assertRaises(KeyError):
                details.activity_page(token, first["revision"], 25)
            details.freeze(token)
            self.assertEqual(latest["revision"], details.page(token, 0)["revision"])
            clock[0] += 6
            # Frozen consumers do not acquire. A second live consumer drives invalidation.
            other = details.open("root", "live")
            key, attempt, _ = details.claim()
            details.finish(key, attempt, dict(error="source_identity_changed", terminal=True))
            self.assertIsNone(details.page(token, 0)["activity"])
            with self.assertRaises(KeyError):
                details.activity_page(token, latest["revision"], 0)
            details.close(other)


if __name__ == "__main__":
    unittest.main()
