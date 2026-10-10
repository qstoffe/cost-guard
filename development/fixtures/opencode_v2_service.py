"""Fake loopback OpenCode V2 services for source/Watch tests.

Two synthetic services cover the transitional project-scoped array contract
(``FakeV2Service`` + the JSON fixture) and the current global cursor contract
(``CurrentV2Service``). Stopping a service drops its keep-alive connections the
way a real process exit does. No credentials, user data or network leave loopback.
"""
from __future__ import annotations

import base64
import copy
import json
import socket
import sys
import tempfile
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from src.sources.opencode_v2 import OpenCodeV2Source

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "development/fixtures/opencode_v2/service-fixture.json"


class LoopbackServer(ThreadingHTTPServer):
    """A stopped fake service drops keep-alive connections, like a real process exit."""

    def __init__(self, *args) -> None:
        super().__init__(*args)
        self._open: set[socket.socket] = set()
        self._open_lock = threading.Lock()

    def process_request(self, request, client_address) -> None:
        with self._open_lock:
            self._open.add(request)
        super().process_request(request, client_address)

    def server_close(self) -> None:
        super().server_close()
        with self._open_lock:
            connections, self._open = tuple(self._open), set()
        for connection in connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def handle_error(self, request, client_address) -> None:
        if isinstance(sys.exc_info()[1], OSError):
            return  # a client/test dropped the socket; not a fixture failure
        super().handle_error(request, client_address)

    def serve_in_background(self) -> threading.Thread:
        # A short poll keeps shutdown (once per test service) from costing ~0.5s.
        thread = threading.Thread(target=self.serve_forever, args=(0.05,), daemon=True)
        thread.start()
        return thread


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

        self.server = LoopbackServer(("127.0.0.1", 0), Handler)
        self.thread = self.server.serve_in_background()
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
        self.shells = None  # running-job registry; None answers 404 (unobservable)
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
                if parsed.path == "/api/shell" and owner.shells is not None:
                    here = query.get("location[directory]") == ["/private/repo"]  # location-scoped
                    self._json({"location": {"directory": "/private/repo"}, "data": owner.shells if here else []})
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

        self.server = LoopbackServer(("127.0.0.1", 0), Handler)
        self.thread = self.server.serve_in_background()
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
