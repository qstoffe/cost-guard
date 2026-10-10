"""Small stdlib HTTP/SSE transport for the registered local OpenCode V2 service.

JSON GETs reuse pooled keep-alive loopback connections: reports and Watch
issue hundreds of small requests, and opening a connection per request used to
dominate hydration time. A reused connection that the service has already
closed is retried once on a fresh connection; every request is an idempotent
GET. The event stream always owns its own connection.
"""
from __future__ import annotations

import base64
import http.client
import json
import threading
import time
import weakref
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterator, Mapping
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

from .errors import SourceDataError, SourceResyncRequiredError, SourceUnavailableError

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "::"}
# Errors that mean "the idle keep-alive connection was already closed".
_STALE_CONNECTION_ERRORS = (
    http.client.RemoteDisconnected, ConnectionResetError, ConnectionAbortedError, BrokenPipeError,
)
_MAX_IDLE_CONNECTIONS = 4


@dataclass(frozen=True, slots=True)
class V2Endpoint:
    url: str
    version: str | None
    pid: int
    username: str
    password: str | None
    registration_path: Path


def normalize_local_service_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise SourceUnavailableError("OpenCode V2 service URL is invalid") from exc
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "http" or host not in _LOCAL_HOSTS or parsed.username or parsed.password:
        raise SourceUnavailableError("OpenCode V2 registered service is not a local HTTP endpoint")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise SourceUnavailableError("OpenCode V2 registered service URL has an unsupported path")
    normalized_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    netloc = f"[{normalized_host}]" if ":" in normalized_host else normalized_host
    if parsed.port is not None:
        netloc += f":{parsed.port}"
    return urlunsplit(("http", netloc, "", "", "")).rstrip("/")


def _close_idle(idle: list[http.client.HTTPConnection], lock: threading.Lock) -> None:
    with lock:
        values = tuple(idle)
        idle.clear()
    for connection in values:
        connection.close()


class V2HttpClient:
    """Plain loopback HTTP; never routed through ambient proxies (http.client has none)."""

    def __init__(self, endpoint: V2Endpoint, *, timeout_seconds: float = 10.0,
                 stats: dict[str, float] | None = None):
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        parsed = urlsplit(endpoint.url)
        self._host = parsed.hostname or "127.0.0.1"
        self._port = parsed.port
        # A request checks out an idle connection (any thread) and returns it
        # afterwards, so short-lived workers never accumulate sockets. Idle
        # sockets close when the client is replaced/collected or at exit.
        self._idle: list[http.client.HTTPConnection] = []
        self._lock = threading.Lock()
        weakref.finalize(self, _close_idle, self._idle, self._lock)
        # Privacy-safe counters only (no paths, queries or payloads).
        self.stats = stats if stats is not None else {}
        for key in ("requests", "connections_opened", "stale_retries", "request_ms"):
            self.stats.setdefault(key, 0)

    def _count(self, key: str, amount: float = 1) -> None:
        with self._lock:
            self.stats[key] += amount

    def _headers(self, *, accept: str = "application/json") -> dict[str, str]:
        headers = {"Accept": accept, "User-Agent": "cost-guard"}
        if self.endpoint.password:
            raw = f"{self.endpoint.username}:{self.endpoint.password}".encode("utf-8")
            headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
        return headers

    @staticmethod
    def _target(path: str, query: Mapping[str, Any] | None = None) -> str:
        target = path if path.startswith("/") else "/" + path
        if query:
            clean = {key: value for key, value in query.items() if value is not None}
            if clean:
                target += "?" + urlencode(clean)
        return target

    def _new_connection(self, timeout: float) -> http.client.HTTPConnection:
        return http.client.HTTPConnection(self._host, self._port, timeout=timeout)

    def close(self) -> None:
        """Close idle keep-alive connections; later requests reconnect."""
        _close_idle(self._idle, self._lock)

    def _get(self, target: str, *, allow_reuse: bool = True) -> tuple[int, bytes]:
        with self._lock:
            connection = self._idle.pop() if allow_reuse and self._idle else None
        reused = connection is not None
        if connection is None:
            connection = self._new_connection(self.timeout_seconds)
            self._count("connections_opened")
        started = time.perf_counter()
        try:
            connection.request("GET", target, headers=self._headers())
            response = connection.getresponse()
            result = response.status, response.read()
        except _STALE_CONNECTION_ERRORS:
            connection.close()
            if not reused:
                raise
            self._count("stale_retries")
            return self._get(target, allow_reuse=False)  # the service closed an idle socket
        except BaseException:
            connection.close()
            raise
        with self._lock:
            self.stats["requests"] += 1
            self.stats["request_ms"] += round((time.perf_counter() - started) * 1000, 3)
            if len(self._idle) < _MAX_IDLE_CONNECTIONS:
                self._idle.append(connection)
                return result
        connection.close()
        return result

    def json(self, path: str, *, query: Mapping[str, Any] | None = None) -> Any:
        try:
            status, body = self._get(self._target(path, query))
        except (OSError, http.client.HTTPException) as exc:
            raise SourceUnavailableError("OpenCode V2 service could not be reached") from exc
        if status >= 300:
            raise SourceUnavailableError(f"OpenCode V2 API returned HTTP {status}")
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise SourceDataError("OpenCode V2 API returned malformed JSON") from exc

    def sse(self, path: str) -> Iterator[Mapping[str, Any]]:
        connection = self._new_connection(max(self.timeout_seconds, 120.0))
        try:
            connection.request("GET", self._target(path), headers=self._headers(accept="text/event-stream"))
            response = connection.getresponse()
        except (OSError, http.client.HTTPException) as exc:
            connection.close()
            raise SourceUnavailableError("OpenCode V2 event stream could not be reached") from exc
        if response.status >= 300:
            connection.close()
            raise SourceUnavailableError(f"OpenCode V2 event API returned HTTP {response.status}")
        data_lines: list[str] = []
        try:
            for raw in response:
                line = raw.decode("utf-8").rstrip("\r\n")
                if not line:
                    if data_lines:
                        text = "\n".join(data_lines)
                        data_lines.clear()
                        try:
                            value = json.loads(text)
                        except json.JSONDecodeError as exc:
                            raise SourceDataError("OpenCode V2 event stream returned malformed JSON") from exc
                        if isinstance(value, Mapping):
                            yield value
                    continue
                if line.startswith(":"):
                    continue
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
            if data_lines:
                try:
                    value = json.loads("\n".join(data_lines))
                except json.JSONDecodeError as exc:
                    raise SourceDataError("OpenCode V2 event stream returned malformed JSON") from exc
                if isinstance(value, Mapping):
                    yield value
        except (UnicodeError, OSError, http.client.HTTPException) as exc:
            raise SourceResyncRequiredError(
                "OpenCode V2 event stream failed; a fresh snapshot is required"
            ) from exc
        finally:
            connection.close()
        raise SourceResyncRequiredError(
            "OpenCode V2 event stream ended; a fresh snapshot is required"
        )
