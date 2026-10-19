"""V1/V2 history acquisition parity, shared catalog indexes and consistency brackets."""
from __future__ import annotations

from copy import deepcopy
from contextlib import closing
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from development.fixtures.opencode_v1_database import create_v1_database
from development.fixtures.opencode_v2_service import source_with_current_service, source_with_service
from development.fixtures.watch_runtime import make_service
from src.sources.opencode_v1 import OpenCodeV1Source
from src.sources.selection import SourceSelector


class V1HistoryDiscoveryTests(unittest.TestCase):
    def test_row_activity_not_stale_session_clock_selects_old_parent_with_current_child(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.db"
            create_v1_database(path)
            with closing(sqlite3.connect(path)) as connection, connection:
                connection.execute("UPDATE session SET time_updated=1000")
                connection.execute("UPDATE message SET time_updated=90000000 WHERE id='msg_child_assistant'")
            source = OpenCodeV1Source(path)
            sessions = source.list_sessions(since_ms=86400000)
            self.assertEqual(["ses_child"], [item.session_id for item in sessions])
            self.assertEqual(90000000, sessions[0].updated_at_ms)
            with patch.object(source, "_json_object", side_effect=AssertionError("revision parsed payload")):
                self.assertEqual(source.get_session_tree_revision("ses_root"), source.get_session_tree_revisions(("ses_root",))["ses_root"])

    def test_large_batch_revisions_cover_every_requested_root_without_parameter_or_cycle_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.db"
            create_v1_database(path)
            ids = [f"root-{index}" for index in range(1200)]
            with closing(sqlite3.connect(path)) as connection, connection:
                connection.executemany("INSERT INTO session(id,project_id,directory,title,time_created,time_updated) VALUES(?, 'p', '/', '', 1, 2)",
                                       ((root_id,) for root_id in ids))
                connection.execute("UPDATE session SET parent_id=id WHERE id=?", (ids[-1],))
            source = OpenCodeV1Source(path)
            actual = source.get_session_tree_revisions(ids)
            self.assertEqual(set(ids), set(actual))
            self.assertEqual(source.get_session_tree_revision(ids[-1]), actual[ids[-1]])

    def test_conservative_liveness_probe_finds_old_unfinished_work_without_hydrating(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.db"
            create_v1_database(path)
            source = OpenCodeV1Source(path)
            self.assertNotIn("ses_child", source.watch_candidate_session_ids())
            with closing(sqlite3.connect(path)) as connection, connection:
                raw = json.loads(connection.execute("SELECT data FROM message WHERE id='msg_child_assistant'").fetchone()[0])
                raw["time"].pop("completed")
                connection.execute("UPDATE message SET data=? WHERE id='msg_child_assistant'", (json.dumps(raw),))
            with patch.object(source, "load_session_snapshot", side_effect=AssertionError("liveness hydrated history")):
                self.assertIn("ses_child", source.watch_candidate_session_ids())

    def test_daily_reference_coverage_matches_transitional_v2_and_warm_source_revision_gates(self):
        with tempfile.TemporaryDirectory() as directory, source_with_service() as (v2, _, _):
            path = Path(directory) / "history.db"
            create_v1_database(path)
            v1 = OpenCodeV1Source(path)
            values = []
            for generation, source in (("v1", v1), ("v2", v2)):
                _, _, service, _ = make_service(str(Path(directory) / generation), source, now_ms=10000)
                first, entries = service.build_watch_quota_with_today_entries(query_account=False)
                self.assertEqual(4, len(entries))
                values.append(first.comparison_today)
                before = source.metrics.counts.get("hydrated_roots", 0)
                again = service.build_watch_quota(query_account=False)
                self.assertEqual(first.comparison_today, again.comparison_today)
                self.assertEqual(before, source.metrics.counts.get("hydrated_roots", 0))
            self.assertEqual(values[0], values[1])


class V2HistoryBatchTests(unittest.TestCase):
    def test_watch_selection_skips_unrendered_migration_gap_and_report_reuses_fresh_catalog(self):
        with source_with_current_service() as (source, service, _):
            def unavailable_legacy():
                raise AssertionError("Watch acquired unrelated legacy history")
            selected = SourceSelector(v2_factory=lambda: source, v1_factory=unavailable_legacy,
                                      inspect_migration_gap=False).select("v2")
            self.assertIsNone(selected.migration_gap)
            self.assertEqual(0, source.metrics.counts.get("full_catalog_fetches", 0))
            first = source.list_sessions()
            self.assertEqual(first, source.recent_session_catalog())
            self.assertEqual(1, source.metrics.counts["full_catalog_fetches"])
            source._catalog_listed_at = -1
            source.recent_session_catalog()
            self.assertEqual(2, source.metrics.counts["full_catalog_fetches"])

    def test_thousand_root_revisions_share_one_index_and_hydrations_share_authoritative_brackets(self):
        with source_with_current_service() as (source, service, _):
            template = service.sessions[0]
            service.sessions = [dict(deepcopy(template), id=f"root-{index:04d}") for index in range(1000)]
            service.session_page_size = 200
            service.messages = {}
            sessions = source.list_sessions()
            roots = tuple(item.session_id for item in sessions)
            first = source.get_session_tree_revisions(roots)
            second = source.get_session_tree_revisions(roots)
            self.assertEqual(first, second)
            self.assertEqual(1, source.metrics.counts["full_catalog_fetches"])
            self.assertEqual(1, source.metrics.counts["catalog_index_builds"])
            self.assertEqual(1000, source.metrics.counts["revision_calculations"])
            snapshots = source.load_session_snapshots(roots[:4])
            self.assertEqual(set(roots[:4]), set(snapshots))
            self.assertEqual(2, source.metrics.counts["full_catalog_fetches"])
            self.assertEqual(12, source.metrics.counts["catalog_pages"])
            self.assertEqual(4, source.metrics.counts["message_operations"])
            self.assertTrue(all(item.source_revision == source.get_session_tree_revision(key) for key, item in snapshots.items()))

    def test_batch_retries_only_changed_tree_and_keeps_stable_neighbors(self):
        with source_with_current_service() as (source, service, _):
            service.sessions[1].pop("parentID")
            source.list_sessions()
            original = source._load_messages
            reads = []
            def changing(native):
                reads.append(native.data["id"])
                result = original(native)
                if len(reads) == 1:
                    service.sessions[0]["time"]["updated"] += 1
                return result
            with patch.object(source, "_load_messages", side_effect=changing):
                snapshots = source.load_session_snapshots(("ses_current", "ses_current_child"))
            self.assertEqual(2, reads.count("ses_current"))
            self.assertEqual(1, reads.count("ses_current_child"))
            self.assertEqual(2, len(snapshots))
            self.assertEqual(4, source.metrics.counts["full_catalog_fetches"], "initial, shared-after and one fresh retry bracket pair")

    def test_legacy_batch_remains_compatible_with_project_scoped_lists(self):
        with source_with_service() as (source, _, _):
            source.list_sessions()
            snapshots = source.load_session_snapshots(("ses_root", "ses_other"))
            self.assertEqual({"ses_root", "ses_child"}, {item.session_id for item in snapshots["ses_root"].sessions})
            self.assertEqual(2, source.metrics.counts["full_catalog_fetches"])
            self.assertEqual(3, source.metrics.counts["message_operations"])


if __name__ == "__main__":
    unittest.main()
