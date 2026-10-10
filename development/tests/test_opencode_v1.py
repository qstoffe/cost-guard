from __future__ import annotations

import ast
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from src.domain import EventKind, MessageRole
from src.sources.discovery import default_opencode_data_dir, discover_v1_database_candidate
from src.sources.errors import SourceDataError
from src.sources.opencode_v1 import OpenCodeV1Source
from src.analysis.causal import build_prompt_records

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "development/fixtures/opencode_v1/schema.sql"
SOURCE_FILE = ROOT / "src/sources/opencode_v1.py"


from development.fixtures.opencode_v1_database import create_v1_database


def _json(value: dict) -> str:
    return json.dumps(value, separators=(",", ":"))


class V1DiscoveryTests(unittest.TestCase):
    def test_default_path_matches_opencode_xdg_shape(self) -> None:
        home = Path("/synthetic/home")
        path = default_opencode_data_dir(environment={}, home=home)
        self.assertEqual(home / ".local/share/opencode", path)
        candidate = discover_v1_database_candidate(environment={}, home=home)
        self.assertEqual((home / ".local/share/opencode/opencode.db").resolve(strict=False), candidate.path)
        self.assertEqual("default", candidate.origin)

    def test_xdg_data_home_and_opencode_db_overrides_are_respected(self) -> None:
        home = Path("/synthetic/home")
        xdg = discover_v1_database_candidate(
            environment={"XDG_DATA_HOME": "/profile/data"}, home=home
        )
        self.assertEqual(Path("/profile/data/opencode/opencode.db").resolve(strict=False), xdg.path)
        override = discover_v1_database_candidate(
            environment={"XDG_DATA_HOME": "/ignored", "OPENCODE_DB": "~/custom.db"}, home=home
        )
        self.assertEqual((home / "custom.db").resolve(strict=False), override.path)
        self.assertEqual("OPENCODE_DB", override.origin)


class OpenCodeV1SourceTests(unittest.TestCase):
    def test_structured_errors_hydrate_consistently_with_v2(self) -> None:
        errors = [
            ({"name": "MessageAbortedError"}, True),
            ({"name": "UnknownError", "data": {"message": "Aborted"}}, True),
            ({"type": "aborted", "message": "<redacted>"}, True),
            ({"name": "UnknownError", "data": {"code": "ERR_CANCELED"}}, True),
            ({"name": "ProviderError", "message": "provider timeout"}, False),
        ]
        for error, aborted in errors:
            with self.subTest(error=error), closing(sqlite3.connect(self.db_path)) as connection:
                data = json.loads(connection.execute("SELECT data FROM message WHERE id='msg_assistant'").fetchone()[0])
                data.update(error=error, finish="error")
                connection.execute("UPDATE message SET data=? WHERE id='msg_assistant'", (_json(data),))
                connection.commit()
                snapshot = self.source.load_session_snapshot("ses_root")
                record = next(p for p in build_prompt_records(snapshot, now_ms=10000) if p.prompt_id == "msg_user")
                self.assertEqual(aborted, record.aborted)
                self.assertEqual(not aborted, record.watch_error)
                self.assertEqual("AbortedError" if aborted else "ProviderError",
                                 next(m.error_name for m in snapshot.messages if m.message_id == "msg_assistant"))
                self.assertEqual(record.entries[0].error_name, record.entries[1].error_name)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "opencode.db"
        create_v1_database(self.db_path)
        self.source = OpenCodeV1Source(self.db_path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_probe_and_schema_detection_are_explicit(self) -> None:
        health = self.source.probe()
        self.assertTrue(health.available)
        self.assertTrue(health.healthy)
        schema = self.source.inspect_schema()
        self.assertTrue(schema.supported)
        self.assertTrue({"session", "message", "part"}.issubset(schema.tables))

    def test_missing_and_unsupported_database_fail_health_probe(self) -> None:
        missing = OpenCodeV1Source(Path(self.temp.name) / "missing.db").probe()
        self.assertFalse(missing.available)
        self.assertFalse(missing.healthy)
        unsupported_path = Path(self.temp.name) / "unsupported.db"
        with closing(sqlite3.connect(unsupported_path)) as connection:
            connection.execute("CREATE TABLE session(id TEXT PRIMARY KEY)")
        unsupported = OpenCodeV1Source(unsupported_path).probe()
        self.assertTrue(unsupported.available)
        self.assertFalse(unsupported.healthy)
        self.assertIn("missing legacy tables", unsupported.detail)

    def test_list_sessions_and_since_filter_normalize_relationships(self) -> None:
        sessions = self.source.list_sessions()
        self.assertEqual(["ses_root", "ses_child", "ses_other"], [s.session_id for s in sessions])
        child = next(s for s in sessions if s.session_id == "ses_child")
        self.assertEqual("ses_root", child.parent_session_id)
        self.assertEqual("v1", child.provenance.source_generation)
        self.assertTrue(child.capabilities.compaction_events)
        recent = self.source.list_sessions(since_ms=5000)
        self.assertEqual(["ses_root", "ses_child"], [s.session_id for s in recent])

    def test_snapshot_preserves_tree_messages_parts_events_and_step_billing(self) -> None:
        snapshot = self.source.load_session_snapshot("ses_root")
        self.assertEqual("ses_root", snapshot.root.session_id)
        self.assertEqual(["ses_root", "ses_child"], [s.session_id for s in snapshot.sessions])
        self.assertEqual(7, len(snapshot.messages))
        self.assertEqual(8, len(snapshot.parts))

        messages = {m.message_id: m for m in snapshot.messages}
        self.assertIs(messages["msg_user"].role, MessageRole.USER)
        self.assertEqual("gpt-test", messages["msg_user"].model.model)
        self.assertEqual("msg_user", messages["msg_assistant"].parent_message_id)
        self.assertTrue(messages["msg_summary"].summary)

        events = {event.event_id: event for event in snapshot.events}
        self.assertIs(events["msg_user"].kind, EventKind.USER_PROMPT)
        self.assertEqual("Hello Cost Guard", events["msg_user"].text)
        self.assertIs(events["msg_compact"].kind, EventKind.COMPACTION)
        self.assertEqual("true", events["msg_compact"].metadata["auto"])
        self.assertIs(events["msg_synthetic"].kind, EventKind.SYNTHETIC_CONTINUATION)
        self.assertIs(events["msg_child_user"].kind, EventKind.SUBTASK)
        self.assertEqual("claude-test", events["msg_child_user"].metadata["model_id"])

        assistant_steps = [i for i in snapshot.invocations if i.message_id == "msg_assistant"]
        self.assertEqual(2, len(assistant_steps), "step-finish parts must beat cumulative message totals")
        self.assertEqual([100, 40], [i.tokens.input for i in assistant_steps])
        self.assertEqual(["0.1", "0.2"], [str(i.cost.amount) for i in assistant_steps])
        self.assertTrue(all(i.initiating_event_id == "msg_user" for i in assistant_steps))

        child_invocation = next(i for i in snapshot.invocations if i.message_id == "msg_child_assistant")
        self.assertEqual(20, child_invocation.tokens.input)
        self.assertEqual("0.2", str(child_invocation.cost.amount))
        self.assertEqual("msg_child_user", child_invocation.initiating_event_id)

    def test_revision_detects_part_change_even_when_session_timestamp_is_unchanged(self) -> None:
        before = self.source.get_session_tree_revision("ses_root")
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("UPDATE part SET time_updated=time_updated+1 WHERE id='prt_user_text'")
            connection.commit()
        after = self.source.get_session_tree_revision("ses_root")
        self.assertNotEqual(before, after)
        with closing(sqlite3.connect(self.db_path)) as verify:
            self.assertEqual(9000, verify.execute("SELECT time_updated FROM session WHERE id='ses_root'").fetchone()[0])

    def test_revision_detects_child_tree_membership_change_without_root_timestamp_change(self) -> None:
        before = self.source.get_session_tree_revision("ses_root")
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute(
                "INSERT INTO session(id,parent_id,project_id,directory,title,time_created,time_updated,time_archived) "
                "VALUES(?,?,?,?,?,?,?,?)",
                ("ses_new_child", "ses_root", "project-a", "/repo", "New child", 5000, 5000, None),
            )
            connection.commit()
        after = self.source.get_session_tree_revision("ses_root")
        self.assertNotEqual(before, after)
        with closing(sqlite3.connect(self.db_path)) as verify:
            self.assertEqual(9000, verify.execute("SELECT time_updated FROM session WHERE id='ses_root'").fetchone()[0])

    def test_batch_revisions_match_individual_revisions_and_track_child_part_changes(self) -> None:
        individual = {
            session_id: self.source.get_session_tree_revision(session_id)
            for session_id in ("ses_root", "ses_other")
        }
        batch = self.source.get_session_tree_revisions(("ses_root", "ses_other"))
        self.assertEqual(individual, batch)

        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("UPDATE part SET time_updated=time_updated+7 WHERE id='prt_child_text'")
            connection.commit()
        changed = self.source.get_session_tree_revisions(("ses_root", "ses_other"))
        self.assertNotEqual(batch["ses_root"], changed["ses_root"])
        self.assertEqual(batch["ses_other"], changed["ses_other"])

    def test_batch_revision_missing_root_fails_closed(self) -> None:
        with self.assertRaises(SourceDataError):
            self.source.get_session_tree_revisions(("ses_root", "missing"))

    def test_snapshot_revision_matches_standalone_revision_for_stable_tree(self) -> None:
        snapshot = self.source.load_session_snapshot("ses_root")
        self.assertEqual(self.source.get_session_tree_revision("ses_root"), snapshot.source_revision)

    def test_adapter_connection_is_query_only_and_does_not_create_sidecars(self) -> None:
        with self.source._connection() as connection:  # focused contract test of the transport boundary
            self.assertEqual(1, connection.execute("PRAGMA query_only").fetchone()[0])
            with self.assertRaises(SourceDataError):
                # The context manager converts SQLite write rejection to a source-safe failure.
                with self.source._connection() as second:
                    second.execute("UPDATE session SET title='mutated' WHERE id='ses_root'")
        with closing(sqlite3.connect(self.db_path)) as verify:
            self.assertEqual("Root", verify.execute("SELECT title FROM session WHERE id='ses_root'").fetchone()[0])
        self.assertFalse(Path(str(self.db_path) + "-wal").exists())
        self.assertFalse(Path(str(self.db_path) + "-shm").exists())

    def test_revision_probe_does_not_hydrate_json_payloads(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("UPDATE message SET data='not-json' WHERE id='msg_user'")
            connection.commit()
        revision = self.source.get_session_tree_revision("ses_root")
        self.assertTrue(revision.startswith("v1-tree:"))

    def test_malformed_json_fails_closed(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("UPDATE message SET data='not-json' WHERE id='msg_user'")
            connection.commit()
        with self.assertRaises(SourceDataError):
            self.source.load_session_snapshot("ses_root")

    def test_v1_adapter_has_no_subprocess_dependency(self) -> None:
        tree = ast.parse(SOURCE_FILE.read_text(encoding="utf-8"))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        self.assertNotIn("subprocess", imports)
        self.assertFalse(any(name.startswith("subprocess.") for name in imports))


if __name__ == "__main__":
    unittest.main()
