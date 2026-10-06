"""Small stdlib HTTP/SSE transport for the registered local OpenCode V2 service."""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import ProxyHandler, Request, build_opener

from .errors import SourceDataError, SourceResyncRequiredError, SourceUnavailableError

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "::"}


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


class V2HttpClient:
    def __init__(self, endpoint: V2Endpoint, *, timeout_seconds: float = 10.0):
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        # A registered local service must never be sent through ambient proxies.
        self._opener = build_opener(ProxyHandler({}))

    def _headers(self, *, accept: str = "application/json") -> dict[str, str]:
        headers = {"Accept": accept, "User-Agent": "cost-guard/78.9"}
        if self.endpoint.password:
            raw = f"{self.endpoint.username}:{self.endpoint.password}".encode("utf-8")
            headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
        return headers

    def _url(self, path: str, query: Mapping[str, Any] | None = None) -> str:
        suffix = path if path.startswith("/") else "/" + path
        url = self.endpoint.url + suffix
        if query:
            clean = {key: value for key, value in query.items() if value is not None}
            if clean:
                url += "?" + urlencode(clean)
        return url

    def json(self, path: str, *, query: Mapping[str, Any] | None = None) -> Any:
        request = Request(self._url(path, query), headers=self._headers(), method="GET")
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                body = response.read()
        except HTTPError as exc:
            code = exc.code
            exc.close()
            raise SourceUnavailableError(f"OpenCode V2 API returned HTTP {code}") from exc
        except (URLError, OSError, TimeoutError) as exc:
            raise SourceUnavailableError("OpenCode V2 service could not be reached") from exc
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise SourceDataError("OpenCode V2 API returned malformed JSON") from exc

    def sse(self, path: str) -> Iterator[Mapping[str, Any]]:
        request = Request(self._url(path), headers=self._headers(accept="text/event-stream"), method="GET")
        try:
            response = self._opener.open(request, timeout=max(self.timeout_seconds, 120.0))
        except HTTPError as exc:
            code = exc.code
            exc.close()
            raise SourceUnavailableError(f"OpenCode V2 event API returned HTTP {code}") from exc
        except (URLError, OSError, TimeoutError) as exc:
            raise SourceUnavailableError("OpenCode V2 event stream could not be reached") from exc
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
        except (UnicodeError, OSError, TimeoutError) as exc:
            raise SourceResyncRequiredError(
                "OpenCode V2 event stream failed; a fresh snapshot is required"
            ) from exc
        finally:
            response.close()
        raise SourceResyncRequiredError(
            "OpenCode V2 event stream ended; a fresh snapshot is required"
        )
