from __future__ import annotations

import ast
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from src.domain import EventKind
from src.sources.discovery import (
    default_opencode_state_dir,
    discover_v2_registration_candidate,
    read_v2_service_registration,
)
from src.sources.errors import SourceDataError, SourceResyncRequiredError
from src.sources.opencode_v1 import OpenCodeV1Source
from src.sources.opencode_v2 import OpenCodeV2Source
from src.sources.opencode_v2_transport import V2Endpoint, V2HttpClient
from development.fixtures.opencode_v1_database import create_v1_database
from development.fixtures.opencode_v2_service import (
    LoopbackServer, fixture, source_with_current_service, source_with_service,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILE = ROOT / "src/sources/opencode_v2.py"


class V2DiscoveryTests(unittest.TestCase):
    def test_default_registration_path_matches_documented_xdg_state_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "synthetic-home"
            expected_state = (home / ".local/state/opencode").resolve(strict=False)
            self.assertEqual(expected_state, default_opencode_state_dir(environment={}, home=home))
            candidate = discover_v2_registration_candidate(environment={}, home=home)
            self.assertEqual(expected_state / "service.json", candidate.path)

    def test_xdg_state_override_and_registration_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            candidate = discover_v2_registration_candidate(
                environment={"XDG_STATE_HOME": str(home / "state")}, home=home
            )
            candidate.path.parent.mkdir(parents=True)
            candidate.path.write_text(json.dumps({
                "url": "http://127.0.0.1:4096", "pid": 42, "version": "2.0.18", "password": "hidden"
            }), encoding="utf-8")
            value = read_v2_service_registration(candidate)
            self.assertEqual("2.0.18", value.version)
            self.assertEqual("opencode", value.username)
            self.assertEqual("hidden", value.password)


class OpenCodeV2SourceTests(unittest.TestCase):
    def test_probe_uses_registered_service_basic_auth_without_cli(self) -> None:
        with source_with_service() as (source, service, _):
            health = source.probe()
            self.assertTrue(health.available)
            self.assertTrue(health.healthy)
            self.assertIn("2.0.18", health.detail)
            request = next(item for item in service.requests if item[0] == "/api/info")
            self.assertTrue(request[1].startswith("Basic "))

    def test_missing_registration_and_non_v2_service_fail_health(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = OpenCodeV2Source(Path(temp) / "missing.json")
            health = source.probe()
            self.assertFalse(health.available)
            self.assertFalse(health.healthy)
        payload = fixture()
        payload["info"]["version"] = "1.18.32"
        with source_with_service(payload) as (source, _service, registration):
            registration.write_text(json.dumps({
                "url": source._read_endpoint().url, "pid": 4242, "version": "2.0.18", "password": "secret"
            }), encoding="utf-8")
            health = source.probe()
            self.assertTrue(health.available)
            self.assertFalse(health.healthy)
            self.assertIn("not a supported V2", health.detail)

    def test_remote_registered_service_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            registration = Path(temp) / "service.json"
            registration.write_text(json.dumps({
                "url": "http://example.com:4096", "pid": 42, "version": "2.0.18", "password": "secret"
            }), encoding="utf-8")
            source = OpenCodeV2Source(registration)
            health = source.probe()
            self.assertFalse(health.healthy)
            self.assertIn("not a local HTTP", health.detail)

    def test_list_sessions_routes_each_project_and_supports_since_filter(self) -> None:
        with source_with_service() as (source, service, _):
            sessions = source.list_sessions()
            self.assertEqual(["ses_root", "ses_child", "ses_other"], [item.session_id for item in sessions])
            child = next(item for item in sessions if item.session_id == "ses_child")
            self.assertEqual("ses_root", child.parent_session_id)
            self.assertEqual("v2", child.provenance.source_generation)
            recent = source.list_sessions(5000)
            self.assertEqual(["ses_root", "ses_child"], [item.session_id for item in recent])
            session_requests = [path for path, _auth in service.requests if path.startswith("/api/session?")]
            self.assertTrue(any("directory=%2Frepo" in value and "scope=project" in value for value in session_requests))
            self.assertTrue(any("directory=%2Fother" in value and "scope=project" in value for value in session_requests))

    def test_snapshot_normalizes_same_semantics_as_v1_contract(self) -> None:
        with source_with_service() as (source, _service, _):
            snapshot = source.load_session_snapshot("ses_root")
            self.assertEqual(["ses_root", "ses_child"], [item.session_id for item in snapshot.sessions])
            self.assertEqual(7, len(snapshot.messages))
            self.assertEqual(8, len(snapshot.parts))
            events = {item.event_id: item for item in snapshot.events}
            self.assertIs(events["msg_user"].kind, EventKind.USER_PROMPT)
            self.assertEqual("Hello Cost Guard", events["msg_user"].text)
            self.assertIs(events["msg_compact"].kind, EventKind.COMPACTION)
            self.assertIs(events["msg_synthetic"].kind, EventKind.SYNTHETIC_CONTINUATION)
            self.assertIs(events["msg_child_user"].kind, EventKind.SUBTASK)
            steps = [item for item in snapshot.invocations if item.message_id == "msg_assistant"]
            self.assertEqual([100, 40], [item.tokens.input for item in steps])
            self.assertEqual(["0.1", "0.2"], [str(item.cost.amount) for item in steps])
            self.assertTrue(snapshot.source_revision.startswith("v2-api:"))

    def test_equivalent_v1_and_v2_fixtures_share_canonical_analysis_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / "v1.db"
            create_v1_database(db_path)
            v1_snapshot = OpenCodeV1Source(db_path).load_session_snapshot("ses_root")
            with source_with_service() as (v2_source, _service, _registration):
                v2_snapshot = v2_source.load_session_snapshot("ses_root")

        def sessions(snapshot):
            return [
                (s.session_id, s.parent_session_id, s.title, s.created_at_ms, s.updated_at_ms, s.archived_at_ms)
                for s in snapshot.sessions
            ]

        def messages(snapshot):
            return [
                (
                    m.message_id, m.session_id, m.role.value, m.created_at_ms, m.completed_at_ms,
                    m.parent_message_id, None if m.model is None else (m.model.provider, m.model.model),
                    m.variant, m.agent, m.summary, m.finish_reason, m.error_name, m.tokens,
                    None if m.cost is None else (m.cost.amount, m.cost.currency, m.cost.kind.value),
                    tuple(part.kind for part in m.parts),
                )
                for m in snapshot.messages
            ]

        def events(snapshot):
            return [
                (e.event_id, e.session_id, e.kind.value, e.created_at_ms, e.text, dict(e.metadata))
                for e in snapshot.events
            ]

        def invocations(snapshot):
            return [
                (
                    i.invocation_id, i.session_id, i.model.provider, i.model.model, i.tokens,
                    None if i.cost is None else (i.cost.amount, i.cost.currency, i.cost.kind.value),
                    i.initiating_event_id, i.message_id, i.step_part_id, i.variant, i.summary,
                    i.finish_reason, i.error_name,
                )
                for i in snapshot.invocations
            ]

        self.assertEqual(sessions(v1_snapshot), sessions(v2_snapshot))
        self.assertEqual(messages(v1_snapshot), messages(v2_snapshot))
        self.assertEqual(events(v1_snapshot), events(v2_snapshot))
        self.assertEqual(invocations(v1_snapshot), invocations(v2_snapshot))

    def test_session_catalog_avoids_relisting_all_projects_for_each_tree_revision(self) -> None:
        with source_with_service() as (source, service, _):
            source.list_sessions()
            before = len([path for path, _ in service.requests if path.startswith("/api/project") or path.startswith("/api/session?")])
            source.get_session_tree_revision("ses_root")
            source.get_session_tree_revision("ses_child")
            after = len([path for path, _ in service.requests if path.startswith("/api/project") or path.startswith("/api/session?")])
            self.assertEqual(before, after, "tree revisions should reuse the already-loaded complete V2 catalog")

    def test_revision_changes_with_descendant_aggregate_state(self) -> None:
        payload = fixture()
        with source_with_service(payload) as (source, _service, _):
            before = source.get_session_tree_revision("ses_root")
            payload["sessions"]["/repo"][1]["tokens"]["input"] += 1
            # Fake server deep-copied its fixture, so mutate its live copy.
            # The source remains on the same service/registration.
            _service.fixture["sessions"]["/repo"][1]["tokens"]["input"] += 1
            source.list_sessions()  # discovery/resync refreshes the in-memory catalog
            after = source.get_session_tree_revision("ses_root")
            self.assertNotEqual(before, after)

    def test_event_stream_yields_hint_then_requires_full_resync_on_end(self) -> None:
        with source_with_service() as (source, _service, _):
            iterator = source.iter_changes()
            change = next(iterator)
            self.assertEqual("session.updated", change.event_type)
            self.assertEqual("ses_root", change.session_id)
            with self.assertRaises(SourceResyncRequiredError):
                next(iterator)

    def test_current_paginated_v2_contract_normalizes_openai_usage(self) -> None:
        with source_with_current_service() as (source, service, _):
            sessions = source.list_sessions()
            self.assertEqual(["ses_current", "ses_current_child"], [item.session_id for item in sessions])
            snapshot = source.load_session_snapshot("ses_current")

            self.assertEqual(2, len(snapshot.messages))
            self.assertEqual(1, len(snapshot.invocations))
            invocation = snapshot.invocations[0]
            self.assertEqual("openai", invocation.model.provider)
            self.assertEqual("gpt-5.6", invocation.model.model)
            self.assertEqual(6_100_000, invocation.tokens.input)
            self.assertEqual(5_000_000, invocation.tokens.cache_read)
            self.assertEqual("1.25", str(invocation.cost.amount))
            self.assertEqual("msg_current_user", invocation.initiating_event_id)

            metadata = source.diagnostic_metadata()
            self.assertEqual("global-paged-data", metadata["session_contract"])
            self.assertGreaterEqual(metadata["session_pages"], 3)
            self.assertEqual({"session-message-paged-data": 2}, metadata["message_contract_counts"])
            self.assertEqual({"current-v2-union": 1, "empty": 1}, metadata["message_shape_counts"])
            self.assertEqual({"user": 1, "assistant": 1}, metadata["message_type_counts"])
            self.assertGreaterEqual(metadata["message_pages_sampled"], 4)

            session_continuations = [
                urlsplit(path) for path, _ in service.requests
                if path.startswith("/api/session?") and "cursor=" in path
            ]
            self.assertTrue(session_continuations)
            for parsed in session_continuations:
                query = parse_qs(parsed.query)
                self.assertEqual({"cursor"}, set(query))

    def test_current_v2_normalizes_active_session_tool_name_time_and_compaction_tokens(self) -> None:
        with source_with_current_service() as (source, service, _):
            service.active = {"ses_current": {"type": "running"}}
            assistant = service.messages["ses_current"][1]
            assistant["content"].append({
                "type": "tool", "id": "tool_current", "name": "todowrite",
                "state": {"status": "running", "input": {"todos": [
                    {"status": "in_progress", "content": "current V2 todo"},
                ]}, "metadata": {}},
                "time": {"created": 3900, "ran": 3950},
            })
            service.messages["ses_current"].append({
                "id": "msg_current_compact", "type": "compaction", "status": "completed",
                "reason": "auto", "summary": "summary", "recent": "x" * 37_600,
                "model": {"providerID": "openai", "id": "gpt-5.6"},
                "tokens": {"input": 200_000, "output": 1_800, "reasoning": 0, "cache": {"read": 38_200, "write": 0}},
                "cost": 0, "time": {"created": 5000},
            })
            snapshot = source.load_session_snapshot("ses_current")
            self.assertTrue(snapshot.root.active)
            tool = next(part for part in snapshot.parts if part.part_id == "tool_current")
            self.assertEqual("todowrite", tool.data["tool"])
            self.assertEqual(3950, tool.created_at_ms)
            self.assertEqual(3950, tool.data["state"]["time"]["start"])
            compact = next(part for part in snapshot.parts if part.kind == "compaction")
            self.assertEqual(200_000, compact.data["tokens"]["input"])
            self.assertEqual("completed", compact.data["status"])

            message_continuations = [
                urlsplit(path) for path, _ in service.requests
                if path.startswith("/api/session/") and "/message?" in path and "cursor=" in path
            ]
            self.assertTrue(message_continuations)
            for parsed in message_continuations:
                query = parse_qs(parsed.query)
                self.assertEqual({"cursor"}, set(query))

    def test_location_switch_is_metadata_not_a_prompt_or_context_message(self) -> None:
        with source_with_current_service() as (source, service, _):
            service.messages["ses_current"].insert(1, {
                "id": "msg_location", "type": "location-switched",
                "location": {"directory": "/private/location"},
                "previous": {"directory": "/old/location"},
                "projectID": "project", "subpath": "worktree",
                "time": {"created": 3500},
            })
            snapshot = source.load_session_snapshot("ses_current")
            self.assertEqual(2, len(snapshot.messages))
            self.assertEqual(1, len(snapshot.invocations))
            self.assertEqual(["msg_current_user"], [event.event_id for event in snapshot.events])
            self.assertFalse(any("/private/location" in str(part.data) for part in snapshot.parts))
            self.assertEqual(
                {"current-v2-union+location-ignored": 1, "empty": 1},
                source.diagnostic_metadata()["message_shape_counts"],
            )

    def test_unknown_current_message_type_still_fails_closed(self) -> None:
        with source_with_current_service() as (source, service, _):
            service.messages["ses_current"].append({
                "id": "msg_unknown", "type": "future-provider-request", "time": {"created": 5000},
            })
            with self.assertRaisesRegex(SourceDataError, "unsupported: future-provider-request"):
                source.load_session_snapshot("ses_current")

    def test_location_switch_with_usage_cannot_be_silently_dropped(self) -> None:
        with source_with_current_service() as (source, service, _):
            service.messages["ses_current"].append({
                "id": "msg_location", "type": "location-switched", "time": {"created": 5000},
                "tokens": {"input": 100},
            })
            with self.assertRaisesRegex(SourceDataError, "location switch contains unsupported usage"):
                source.load_session_snapshot("ses_current")


    def test_status_only_current_route_falls_back_to_compatibility_message_route(self) -> None:
        with source_with_current_service(message_path="idle-then-message") as (source, service, _):
            snapshot = source.load_session_snapshot("ses_current")
            self.assertEqual(1, len(snapshot.invocations))
            self.assertEqual(6_100_000, snapshot.invocations[0].tokens.input)

            metadata = source.diagnostic_metadata()
            self.assertEqual({"message-paged-data": 2}, metadata["message_contract_counts"])
            self.assertEqual(
                {"session-message-paged-data:lifecycle-only": 2},
                metadata["message_route_rejection_counts"],
            )
            self.assertTrue(any(path.startswith("/api/message?") for path, _ in service.requests))

    def test_lifecycle_status_rows_mixed_with_messages_are_ignored(self) -> None:
        with source_with_current_service(message_path="session-message-with-idle") as (source, _service, _):
            snapshot = source.load_session_snapshot("ses_current")
            self.assertEqual(2, len(snapshot.messages))
            self.assertEqual(1, len(snapshot.invocations))

            metadata = source.diagnostic_metadata()
            self.assertEqual(1, metadata["message_type_counts"]["idle"])
            self.assertEqual(1, metadata["message_lifecycle_items_ignored"])
            self.assertEqual(
                {"current-v2-union+lifecycle-ignored": 1, "empty": 1},
                metadata["message_shape_counts"],
            )

    def test_current_v2_union_also_paginate_through_experimental_message_route(self) -> None:
        with source_with_current_service(message_path="/api/message") as (source, _service, _):
            snapshot = source.load_session_snapshot("ses_current")
            self.assertEqual(1, len(snapshot.invocations))
            self.assertEqual(6_100_000, snapshot.invocations[0].tokens.input)
            metadata = source.diagnostic_metadata()
            self.assertEqual({"message-paged-data": 2}, metadata["message_contract_counts"])
            self.assertEqual({"current-v2-union": 1, "empty": 1}, metadata["message_shape_counts"])

    def test_v2_adapter_has_no_subprocess_or_sqlite_dependency(self) -> None:
        tree = ast.parse(SOURCE_FILE.read_text(encoding="utf-8"))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        self.assertNotIn("subprocess", imports)
        self.assertNotIn("sqlite3", imports)


class V2TransportTests(unittest.TestCase):
    """Pooled keep-alive JSON transport: reuse, stale-socket retry and bounded idle sockets."""

    def _service(self, *, drop_after_first: bool = False):
        accepted: list[int] = []

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):
                return

            def setup(self):
                super().setup()
                accepted.append(1)

            def do_GET(self):
                raw = b'{"ok":true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                # Model a service closing an idle keep-alive socket without notice.
                self.close_connection = drop_after_first

        server = LoopbackServer(("127.0.0.1", 0), Handler)
        server.serve_in_background()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        host, port = server.server_address
        endpoint = V2Endpoint(f"http://{host}:{port}", "2.1.0", 1, "opencode", None, Path("service.json"))
        return V2HttpClient(endpoint, timeout_seconds=2.0), accepted, server

    def test_sequential_requests_reuse_one_connection(self) -> None:
        client, accepted, _server = self._service()
        for _ in range(25):
            self.assertEqual({"ok": True}, client.json("/api/info"))
        self.assertEqual(1, len(accepted))

    def test_service_closed_idle_socket_is_retried_on_a_fresh_connection(self) -> None:
        client, accepted, _server = self._service(drop_after_first=True)
        for _ in range(5):
            self.assertEqual({"ok": True}, client.json("/api/info"))
        self.assertEqual(5, len(accepted))

    def test_concurrent_workers_keep_a_bounded_idle_pool(self) -> None:
        client, _accepted, _server = self._service()
        barrier = threading.Barrier(8)

        def work() -> None:
            barrier.wait(timeout=5)
            for _ in range(5):
                client.json("/api/info")

        threads = [threading.Thread(target=work) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertLessEqual(len(client._idle), 4)
        client.close()
        self.assertEqual([], client._idle)


if __name__ == "__main__":
    unittest.main()
