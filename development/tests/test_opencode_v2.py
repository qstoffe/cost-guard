from __future__ import annotations

import ast
import base64
import copy
import json
import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from src.domain import EventKind
from src.sources.discovery import (
    default_opencode_state_dir,
    discover_v2_registration_candidate,
    read_v2_service_registration,
)
from src.sources.errors import SourceDataError, SourceResyncRequiredError, SourceUnavailableError
from src.sources.opencode_v1 import OpenCodeV1Source
from src.sources.opencode_v2 import OpenCodeV2Source
from development.tests.test_opencode_v1 import create_v1_database

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "development/fixtures/opencode_v2/service-fixture.json"
SOURCE_FILE = ROOT / "src/sources/opencode_v2.py"


class FakeV2Service:
    def __init__(self, fixture: dict, *, password: str = "secret"):
        self.fixture = copy.deepcopy(fixture)
        self.password = password
        self.requests: list[tuple[str, str | None]] = []
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def __enter__(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):
                return

            def _json(self, value, status=200):
                raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                auth = self.headers.get("Authorization")
                owner.requests.append((self.path, auth))
                expected = "Basic " + base64.b64encode(f"opencode:{owner.password}".encode()).decode()
                if auth != expected:
                    self._json({"error": "unauthorized"}, 401)
                    return
                parsed = urlsplit(self.path)
                query = parse_qs(parsed.query)
                if parsed.path == "/api/info":
                    self._json(owner.fixture["info"])
                    return
                if parsed.path == "/api/project":
                    self._json(owner.fixture["projects"])
                    return
                if parsed.path == "/api/model" and "models" in owner.fixture:
                    self._json(owner.fixture["models"])
                    return
                if parsed.path == "/api/session":
                    directory = query.get("directory", [""])[0]
                    values = list(owner.fixture["sessions"].get(directory, []))
                    if "start" in query:
                        start = int(query["start"][0])
                        values = [
                            item for item in values
                            if int(item.get("time", {}).get("updated", 0)) >= start
                        ]
                    self._json(values)
                    return
                if parsed.path.startswith("/api/session/") and parsed.path.endswith("/message"):
                    session_id = parsed.path.split("/")[3]
                    self._json(owner.fixture["messages"].get(session_id, []))
                    return
                if parsed.path == "/api/event":
                    payload = "".join(
                        f"data: {json.dumps(item, separators=(',', ':'))}\n\n"
                        for item in owner.fixture.get("events", [])
                    ).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                self._json({"error": "not found"}, 404)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_args):
        assert self.server is not None
        self.server.shutdown()
        self.server.server_close()
        assert self.thread is not None
        self.thread.join(timeout=5)

    @property
    def url(self) -> str:
        assert self.server is not None
        host, port = self.server.server_address
        return f"http://{host}:{port}"


def fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@contextmanager
def source_with_service(payload: dict | None = None):
    data = fixture() if payload is None else payload
    with tempfile.TemporaryDirectory() as temp, FakeV2Service(data) as service:
        registration = Path(temp) / "service.json"
        registration.write_text(json.dumps({
            "url": service.url,
            "pid": 4242,
            "version": "2.0.18",
            "password": service.password,
        }), encoding="utf-8")
        yield OpenCodeV2Source(registration, timeout_seconds=2.0), service, registration


class CurrentV2Service:
    """Synthetic current OpenCode 2 global/cursor API."""

    def __init__(self, *, password: str = "secret", message_path: str = "session-message"):
        self.password = password
        self.message_path = message_path
        self.requests: list[tuple[str, str | None]] = []
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.sessions = [
            {
                "id": "ses_current", "projectID": "prj_current", "title": "private current",
                "agent": "build", "model": {"providerID": "openai", "id": "gpt-5.6", "variant": "medium"},
                "cost": 1.25,
                "tokens": {"input": 6100000, "output": 10000, "reasoning": 5000, "cache": {"read": 5000000, "write": 0}},
                "time": {"created": 1000, "updated": 9000},
                "location": {"directory": "/private/repo"},
            },
            {
                "id": "ses_current_child", "parentID": "ses_current", "projectID": "prj_current",
                "title": "child", "agent": "build", "cost": 0.25,
                "tokens": {"input": 100, "output": 20, "reasoning": 10, "cache": {"read": 50, "write": 0}},
                "time": {"created": 2000, "updated": 8000},
                "location": {"directory": "/private/repo"},
            },
        ]
        self.active = {}
        self.messages = {
            "ses_current": [
                {
                    "id": "msg_current_user", "type": "user",
                    "text": "private prompt omitted from diagnostics",
                    "files": [], "agents": [], "time": {"created": 3000},
                },
                {
                    "id": "msg_current_assistant", "type": "assistant",
                    "agent": "build",
                    "model": {"providerID": "openai", "id": "gpt-5.6", "variant": "medium"},
                    "content": [
                        {"type": "reasoning", "id": "reason_1", "text": "private reasoning",
                         "time": {"created": 3050, "completed": 3090}},
                        {"type": "text", "id": "text_1", "text": "private answer"},
                    ],
                    "finish": "stop", "cost": 1.25,
                    "tokens": {
                        "input": 6100000, "output": 10000, "reasoning": 5000,
                        "cache": {"read": 5000000, "write": 0},
                    },
                    "time": {"created": 3100, "completed": 4000},
                },
            ],
            "ses_current_child": [],
        }

    def __enter__(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):
                return

            def _json(self, value, status=200):
                raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                auth = self.headers.get("Authorization")
                owner.requests.append((self.path, auth))
                expected = "Basic " + base64.b64encode(f"opencode:{owner.password}".encode()).decode()
                if auth != expected:
                    self._json({"error": "unauthorized"}, 401)
                    return
                parsed = urlsplit(self.path)
                query = parse_qs(parsed.query)
                if parsed.path == "/api/info":
                    self._json({"version": "2.1.0"})
                    return
                if parsed.path == "/api/session/active":
                    self._json({"data": owner.active})
                    return
                if parsed.path == "/api/session":
                    cursor = query.get("cursor", [None])[0]
                    if cursor is None:
                        self._json({"data": [owner.sessions[0]], "cursor": {"next": "sessions:2"}})
                    elif cursor == "sessions:2":
                        self._json({"data": [owner.sessions[1]], "cursor": {"next": "sessions:end"}})
                    elif cursor == "sessions:end":
                        self._json({"data": [], "cursor": {}})
                    else:
                        self._json({"error": "bad cursor"}, 400)
                    return
                if parsed.path == "/api/message" and owner.message_path in {"/api/message", "idle-then-message"}:
                    cursor = query.get("cursor", [None])[0]
                    session_id = query.get("sessionID", [None])[0]
                    if cursor is not None:
                        # The real cursor carries the original query; continuation
                        # requests deliberately omit session/order/limit.
                        session_id, marker = cursor.rsplit(":", 1)
                    else:
                        marker = "1"
                    values = owner.messages.get(session_id or "", [])
                    index = int(marker) - 1 if marker.isdigit() else len(values)
                    if index < len(values):
                        next_marker = str(index + 2) if index + 1 < len(values) else "end"
                        self._json({"data": [values[index]], "cursor": {"next": f"{session_id}:{next_marker}"}})
                    else:
                        self._json({"data": [], "cursor": {}})
                    return
                if (parsed.path.startswith("/api/session/") and parsed.path.endswith("/message")
                        and owner.message_path in {"session-message", "idle-then-message", "session-message-with-idle"}):
                    path_session_id = parsed.path.split("/")[3]
                    if owner.message_path == "idle-then-message":
                        self._json({"data": [{"type": "idle"}], "cursor": {}})
                        return
                    cursor = query.get("cursor", [None])[0]
                    if cursor is not None:
                        session_id, marker = cursor.rsplit(":", 1)
                    else:
                        session_id, marker = path_session_id, "1"
                    values = owner.messages.get(session_id, [])
                    index = int(marker) - 1 if marker.isdigit() else len(values)
                    if index < len(values):
                        page = [values[index]]
                        if owner.message_path == "session-message-with-idle" and index == 0:
                            page.insert(0, {"type": "idle"})
                        next_marker = str(index + 2) if index + 1 < len(values) else "end"
                        self._json({"data": page, "cursor": {"next": f"{session_id}:{next_marker}"}})
                    else:
                        self._json({"data": [], "cursor": {}})
                    return
                self._json({"error": "not found"}, 404)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_args):
        assert self.server is not None
        self.server.shutdown()
        self.server.server_close()
        assert self.thread is not None
        self.thread.join(timeout=5)

    @property
    def url(self) -> str:
        assert self.server is not None
        host, port = self.server.server_address
        return f"http://{host}:{port}"


@contextmanager
def source_with_current_service(*, message_path: str = "session-message"):
    with tempfile.TemporaryDirectory() as temp, CurrentV2Service(message_path=message_path) as service:
        registration = Path(temp) / "service.json"
        registration.write_text(json.dumps({
            "url": service.url, "pid": 5252, "version": "2.1.0", "password": service.password,
        }), encoding="utf-8")
        yield OpenCodeV2Source(registration, timeout_seconds=2.0), service, registration


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


if __name__ == "__main__":
    unittest.main()
