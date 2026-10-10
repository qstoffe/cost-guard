"""OpenCode V2 read-only Session Source over registered loopback HTTP.

Public API snapshots are authoritative; non-replayable events are hints.
No OpenCode CLI or V2 database access.
"""
from __future__ import annotations

import hashlib
import json
import time
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from src.domain import (
    BackgroundActivity,
    ContextBoundary,
    IntegrationHealth,
    MessageRole,
    ModelInvocation,
    NormalizedMessage,
    NormalizedPart,
    NormalizedSession,
    Provenance,
    SessionCapabilities,
    SessionSnapshot,
)

from .base import SourceChange
from .discovery import (
    ServiceRegistration,
    ServiceRegistrationCandidate,
    ServiceRegistrationError,
    discover_v2_registration_candidate,
    read_v2_service_registration,
)
from .errors import SourceDataError, SourceUnavailableError
from .model_availability import settled_v2_model_ids
from .opencode_v2_normalization import (
    normalize_invocations, normalize_message_bundle, optional_positive_int, safe_int,
)
from .opencode_v2_background import background_activities, running_jobs
from .opencode_v2_diagnostics import summarize_v2_diagnostics
from .opencode_v2_events import normalize_event
from .opencode_v2_interruptions import LiveInterruptionReasons
from .opencode_v2_transport import V2Endpoint, V2HttpClient, normalize_local_service_url
from .opencode_v2_wire import (
    fetch_global_sessions,
    fetch_messages,
    fetch_project_sessions,
    is_lifecycle_status_item,
    location_boundaries,
    normalize_message_items,
    normalize_terminal_lifecycle,
    session_directory,
)


V2_CAPABILITIES = SessionCapabilities(
    exact_input_tokens=True,
    exact_output_tokens=True,
    exact_reasoning_tokens=True,
    exact_cache_read_tokens=True,
    exact_cache_write_tokens=True,
    native_cost=True,
    child_sessions=True,
    compaction_events=True,
    live_changes=True,
)
# A complete catalog this recent may serve as a snapshot's "before" bracket.
_CATALOG_REUSE_SECONDS = 2.0




@dataclass(frozen=True, slots=True)
class _NativeSession:
    data: Mapping[str, Any]
    directory: str
    active: bool | None = None


class OpenCodeV2Source:
    source_id = "opencode-v2"
    capabilities = V2_CAPABILITIES

    def __init__(
        self,
        registration_path: Path | str | None = None,
        *,
        candidate: ServiceRegistrationCandidate | None = None,
        timeout_seconds: float = 10.0,
    ):
        if registration_path is not None and candidate is not None:
            raise ValueError("Specify registration_path or candidate, not both")
        if candidate is None:
            if registration_path is None:
                candidate = discover_v2_registration_candidate()
            else:
                candidate = ServiceRegistrationCandidate(
                    Path(registration_path).expanduser().resolve(strict=False), "explicit"
                )
        self._candidate = candidate
        self._timeout_seconds = timeout_seconds
        self._endpoint: V2Endpoint | None = None
        self._endpoint_marker: tuple[int, int] | None = None
        self._catalog_cache: tuple[_NativeSession, ...] | None = None
        self._catalog_listed_at = 0.0
        self._http: V2HttpClient | None = None
        self._instance_cache: tuple[str, str] | None = None
        self._interruptions = LiveInterruptionReasons()
        self._diagnostics: dict[str, Any] = {
            "session_contract": None, "session_pages": 0, "raw_sessions": 0,
            "message_contracts": {}, "message_shapes": {}, "message_items": {}, "message_pages": {},
            "message_types": {}, "message_route_rejections": {}, "message_lifecycle_ignored": {},
            "last_snapshot_stage": "unknown", "snapshot_revision_rechecks": 0,
            "snapshot_catalog_reuses": 0, "snapshot_catalog_reuse_misses": 0, "transport": {},
        }

    @property
    def registration_path(self) -> Path:
        return self._candidate.path

    def _read_endpoint(self) -> V2Endpoint:
        try:
            registration: ServiceRegistration = read_v2_service_registration(self._candidate)
        except ServiceRegistrationError as exc:
            raise SourceUnavailableError(str(exc)) from exc
        if registration.version and not registration.version.startswith("2."):
            raise SourceUnavailableError("Registered OpenCode service is not a supported V2 service")
        endpoint = V2Endpoint(
            url=normalize_local_service_url(registration.url),
            version=registration.version,
            pid=registration.pid,
            username=registration.username,
            password=registration.password,
            registration_path=registration.path,
        )
        self._endpoint = endpoint
        return endpoint

    def _current_endpoint(self) -> V2Endpoint:
        """Reuse the registration until OpenCode rewrites it (a restarted service may move port/auth)."""
        try:
            stat = self._candidate.path.stat()
            marker: tuple[int, int] | None = (stat.st_mtime_ns, stat.st_size)
        except OSError:
            marker = None
        if self._endpoint is None or marker != self._endpoint_marker:
            endpoint = self._read_endpoint()
            self._endpoint_marker = marker
            return endpoint
        return self._endpoint

    def _client(self) -> V2HttpClient:
        """One client (and keep-alive connection per thread) per registered endpoint."""
        endpoint = self._current_endpoint()
        client = self._http
        if client is None or client.endpoint is not endpoint:
            client = self._http = V2HttpClient(endpoint, timeout_seconds=self._timeout_seconds,
                                               stats=self._diagnostics["transport"])
        return client

    @property
    def source_instance(self) -> str | None:
        try:
            endpoint = self._endpoint or self._read_endpoint()
        except SourceUnavailableError:
            return None
        path = str(endpoint.registration_path)
        if self._instance_cache is None or self._instance_cache[0] != path:
            digest = hashlib.sha256(path.encode("utf-8", errors="surrogatepass")).hexdigest()[:16]
            self._instance_cache = (path, f"service:{digest}")
        return self._instance_cache[1]

    def probe(self) -> IntegrationHealth:
        if not self._candidate.path.is_file():
            return IntegrationHealth(False, False, "OpenCode V2 shared-service registration was not found")
        try:
            endpoint = self._read_endpoint()
            info = V2HttpClient(endpoint, timeout_seconds=self._timeout_seconds).json("/api/info")
        except (SourceUnavailableError, SourceDataError) as exc:
            return IntegrationHealth(True, False, str(exc))
        if not isinstance(info, Mapping):
            return IntegrationHealth(True, False, "OpenCode V2 /api/info returned an invalid response")
        version = info.get("version")
        if not isinstance(version, str) or not version.startswith("2."):
            return IntegrationHealth(True, False, "OpenCode shared service is not a supported V2 version")
        return IntegrationHealth(True, True, f"OpenCode V2 service {version} is reachable")

    def _provenance(self, session_id: str, event_id: str | None = None) -> Provenance:
        return Provenance(
            source_type="opencode",
            source_generation="v2",
            source_instance=self.source_instance,
            source_session_id=session_id,
            source_event_id=event_id,
        )

    def diagnostic_metadata(self) -> Mapping[str, Any]:
        """Return non-secret observation metadata for the diagnostics bundle."""
        return summarize_v2_diagnostics(self._diagnostics)

    def available_model_ids(self) -> tuple[str, ...] | None:
        """Use the selected registered service's settled global model list."""
        client = self._client()
        return settled_v2_model_ids(lambda: client.json("/api/model"))

    def _list_native_sessions(
        self, since_ms: int | None = None, *, refresh: bool = True
    ) -> list[_NativeSession]:
        if since_ms is None and not refresh and self._catalog_cache is not None:
            return list(self._catalog_cache)
        client = self._client()
        raw_values: list[tuple[Mapping[str, Any], str]]
        contract: str
        pages: int
        try:
            raw_values, contract, pages = fetch_global_sessions(client)
        except (SourceUnavailableError, SourceDataError):
            raw_values, contract, pages = fetch_project_sessions(client, since_ms)
        else:
            # Older project-scoped services can accept /api/session globally but
            # return an empty array. Probe their project registry before treating
            # that as authoritative emptiness.
            if not raw_values:
                try:
                    legacy_values, legacy_contract, legacy_pages = fetch_project_sessions(client, since_ms)
                except (SourceUnavailableError, SourceDataError):
                    pass
                else:
                    if legacy_values:
                        raw_values, contract, pages = legacy_values, legacy_contract, legacy_pages

        active_ids: set[str] | None = None
        try:
            active_raw = client.json("/api/session/active")
            active_data = active_raw.get("data") if isinstance(active_raw, Mapping) else None
            if isinstance(active_data, Mapping):
                active_ids = {
                    str(session_id) for session_id, status in active_data.items()
                    if isinstance(status, Mapping) and str(status.get("type", "")).lower() == "running"
                }
        except (SourceUnavailableError, SourceDataError):
            active_ids = None
        values = [
            _NativeSession(
                data, directory,
                None if active_ids is None else str(data.get("id")) in active_ids,
            )
            for data, directory in raw_values
        ]
        if since_ms is not None:
            values = [
                item for item in values
                if safe_int((item.data.get("time") or {}).get("updated") if isinstance(item.data.get("time"), Mapping) else 0) >= int(since_ms)
            ]
        result = sorted(
            values,
            key=lambda item: (-safe_int((item.data.get("time") or {}).get("updated") if isinstance(item.data.get("time"), Mapping) else 0), str(item.data["id"])),
        )
        self._diagnostics["session_contract"] = contract
        self._diagnostics["session_pages"] = pages
        self._diagnostics["raw_sessions"] = len(result)
        if since_ms is None:
            self._catalog_cache = tuple(result)
            self._catalog_listed_at = time.monotonic()
        return result

    def _normalize_session(self, native: _NativeSession) -> NormalizedSession:
        data = native.data
        session_id = str(data["id"])
        time_value = data.get("time")
        time_map = time_value if isinstance(time_value, Mapping) else {}
        parent = data.get("parentID")
        return NormalizedSession(
            session_id=session_id,
            title=str(data.get("title") or session_id),
            created_at_ms=safe_int(time_map.get("created")),
            updated_at_ms=safe_int(time_map.get("updated")),
            archived_at_ms=optional_positive_int(time_map.get("archived")),
            parent_session_id=str(parent) if parent not in (None, "") else None,
            active=native.active,
            provenance=self._provenance(session_id),
            capabilities=self.capabilities,
        )

    def list_sessions(self, since_ms: int | None = None) -> Sequence[NormalizedSession]:
        self._diagnostics["last_snapshot_stage"] = "catalog"
        return tuple(self._normalize_session(value) for value in self._list_native_sessions(since_ms, refresh=True))

    @staticmethod
    def _tree(native: Sequence[_NativeSession], root_id: str) -> list[_NativeSession]:
        by_id = {str(item.data["id"]): item for item in native}
        if root_id not in by_id:
            raise SourceDataError("OpenCode V2 session does not exist")
        children: dict[str, list[str]] = {}
        for item in native:
            parent = item.data.get("parentID")
            if parent not in (None, ""):
                children.setdefault(str(parent), []).append(str(item.data["id"]))
        result: list[_NativeSession] = []
        queue = [root_id]
        seen: set[str] = set()
        while queue:
            current = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)
            result.append(by_id[current])
            queue.extend(sorted(children.get(current, ())))
        return result

    def _revision(self, tree: Sequence[_NativeSession]) -> str:
        digest = hashlib.sha256()
        for item in sorted(tree, key=lambda value: str(value.data["id"])):
            data = item.data
            time_value = data.get("time") if isinstance(data.get("time"), Mapping) else {}
            stable = {
                "id": data.get("id"),
                "parentID": data.get("parentID"),
                "projectID": data.get("projectID"),
                "directory": session_directory(data, item.directory),
                "time": {key: time_value.get(key) for key in ("created", "updated", "archived", "compacting")},
                "cost": data.get("cost"),
                "tokens": data.get("tokens"),
                "active": item.active,
            }
            live_reasons = self._interruptions.signature(str(data["id"]))
            if live_reasons:
                stable["live_interruptions"] = live_reasons
            digest.update(json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8"))
            digest.update(b"\n")
        return "v2-api:" + digest.hexdigest()

    def get_session_tree_revision(self, session_id: str) -> str:
        # Reuse the most recent complete catalog so a report can obtain many
        # root revisions without relisting every V2 project per root.  Snapshot
        # hydration refreshes independently and live events invalidate this hint.
        catalog = self._list_native_sessions(refresh=self._catalog_cache is None)
        return self._revision(self._tree(catalog, session_id))

    def get_session_tree_revisions(self, session_ids: Sequence[str]) -> Mapping[str, str]:
        """Compute multiple V2 tree revisions from one complete session catalog."""
        unique = tuple(dict.fromkeys(str(value) for value in session_ids if str(value)))
        if not unique:
            return {}
        self._diagnostics["last_snapshot_stage"] = "catalog"
        catalog = self._list_native_sessions(refresh=self._catalog_cache is None)
        return {session_id: self._revision(self._tree(catalog, session_id)) for session_id in unique}

    def _load_messages(self, native: _NativeSession) -> tuple[
        tuple[NormalizedMessage, ...], tuple[NormalizedPart, ...], tuple[ContextBoundary, ...],
        tuple[BackgroundActivity, ...], frozenset[str],
    ]:
        session_id = str(native.data["id"])
        items, contract, pages, rejected_routes = fetch_messages(
            self._client(), session_id=session_id, directory=native.directory
        )
        background, notices = background_activities(
            items, session_id=session_id, running_jobs=lambda: running_jobs(self._client(), native.directory))
        bundles, shape = normalize_message_items(items, session=native.data)
        if rejected_routes:
            self._diagnostics["message_route_rejections"][session_id] = "+".join(rejected_routes)
        type_counts = self._diagnostics.setdefault("message_types", {})
        if isinstance(type_counts, dict):
            for item in items:
                if isinstance(item.get("type"), str):
                    label = str(item["type"])
                elif isinstance(item.get("role"), str):
                    label = "experimental-role:" + str(item["role"])
                elif isinstance(item.get("info"), Mapping):
                    label = "legacy-role:" + str(item["info"].get("role", "other"))
                else:
                    label = "unknown"
                type_counts[label] = int(type_counts.get(label, 0)) + 1
        messages: list[NormalizedMessage] = []
        parts: list[NormalizedPart] = []
        for bundle in bundles:
            message, message_parts = normalize_message_bundle(bundle, self._provenance)
            messages.append(message)
            parts.extend(message_parts)
        messages.sort(key=lambda value: (value.created_at_ms, value.message_id))

        latest_user: str | None = None
        relinked: list[NormalizedMessage] = []
        for message in messages:
            if message.role is MessageRole.USER:
                latest_user = message.message_id
                relinked.append(message)
            elif message.role is MessageRole.ASSISTANT and message.parent_message_id is None and latest_user is not None:
                relinked.append(replace(message, parent_message_id=latest_user))
            else:
                relinked.append(message)
        messages = normalize_terminal_lifecycle(items, relinked, session_id=session_id,
                                               interruptions=self._interruptions)
        terminal_count = sum(message.termination is not None for message in messages)
        self._diagnostics.setdefault("message_terminal_evidence", {})[session_id] = terminal_count
        self._diagnostics["message_lifecycle_ignored"][session_id] = sum(
            is_lifecycle_status_item(item) for item in items
        ) - terminal_count
        parts.sort(key=lambda value: (value.message_id, value.created_at_ms, value.part_id))
        self._diagnostics["message_contracts"][session_id] = contract
        self._diagnostics["message_shapes"][session_id] = shape
        self._diagnostics["message_items"][session_id] = len(items)
        self._diagnostics.setdefault("message_pages", {})[session_id] = pages
        return tuple(messages), tuple(parts), location_boundaries(items, session_id=session_id), background, notices

    def _catalog_before_messages(self, session_id: str, *, allow_reuse: bool) -> tuple[list[_NativeSession], bool]:
        """Catalog that brackets a snapshot's message reads from before.

        Consistency needs equal tree revisions in a catalog read before and one
        read after the messages. A complete listing from the last couple of
        seconds still precedes the reads, so batches of snapshots reuse the
        previous after-catalog; a mismatch then retries with fresh catalogs.
        """
        cached, listed_at = self._catalog_cache, self._catalog_listed_at
        if (allow_reuse and cached is not None and time.monotonic() - listed_at <= _CATALOG_REUSE_SECONDS
                and any(str(item.data["id"]) == session_id for item in cached)):
            self._diagnostics["snapshot_catalog_reuses"] += 1
            return list(cached), True
        return self._list_native_sessions(refresh=True), False

    def load_session_snapshot(self, session_id: str) -> SessionSnapshot:
        reuse = True
        attempt = 0
        while attempt < 2:
            self._diagnostics["last_snapshot_stage"] = "catalog_before"
            before_all, reused = self._catalog_before_messages(session_id, allow_reuse=reuse)
            before_tree = self._tree(before_all, session_id)
            before_revision = self._revision(before_tree)
            messages: list[NormalizedMessage] = []
            parts: list[NormalizedPart] = []
            boundaries: list[ContextBoundary] = []
            background: list[BackgroundActivity] = []
            notices: set[str] = set()
            self._diagnostics["last_snapshot_stage"] = "messages"
            for native in before_tree:
                native_messages, native_parts, native_boundaries, native_background, native_notices = self._load_messages(native)
                messages.extend(native_messages)
                parts.extend(native_parts)
                boundaries.extend(native_boundaries)
                background.extend(native_background)
                notices.update(native_notices)
            self._diagnostics["last_snapshot_stage"] = "catalog_after"
            after_all = self._list_native_sessions(refresh=True)
            after_tree = self._tree(after_all, session_id)
            after_revision = self._revision(after_tree)
            if before_revision == after_revision:
                self._diagnostics["last_snapshot_stage"] = "normalize"
                sessions = tuple(self._normalize_session(item) for item in before_tree)
                events = tuple(
                    event for message in messages
                    if (event := normalize_event(message, frozenset(notices))) is not None
                )
                invocations: list[ModelInvocation] = []
                for message in messages:
                    invocations.extend(normalize_invocations(message, self._provenance))
                invocations.sort(key=lambda value: (
                    value.completed_at_ms if value.completed_at_ms is not None else value.created_at_ms,
                    value.invocation_id,
                ))
                root = next(value for value in sessions if value.session_id == session_id)
                self._diagnostics["last_snapshot_stage"] = "complete"
                return SessionSnapshot(
                    root=root,
                    sessions=sessions,
                    messages=tuple(sorted(messages, key=lambda value: (value.created_at_ms, value.message_id))),
                    parts=tuple(sorted(parts, key=lambda value: (value.message_id, value.created_at_ms, value.part_id))),
                    events=events,
                    invocations=tuple(invocations),
                    source_revision=after_revision,
                    context_boundaries=tuple(boundaries),
                    background=tuple(background),
                )
            if reused:
                reuse = False  # the reused catalog was stale; not a fresh attempt
                self._diagnostics["snapshot_catalog_reuse_misses"] += 1
                continue
            self._diagnostics["snapshot_revision_rechecks"] += 1
            attempt += 1
        self._diagnostics["last_snapshot_stage"] = "revision_changed"
        raise SourceDataError("OpenCode V2 session changed repeatedly while it was being read")

    @staticmethod
    def _event_session_id(value: Mapping[str, Any]) -> str | None:
        payload = value.get("payload") if isinstance(value.get("payload"), Mapping) else value
        properties = payload.get("properties") if isinstance(payload, Mapping) and isinstance(payload.get("properties"), Mapping) else {}
        if isinstance(payload.get("data"), Mapping):
            properties = payload["data"]
        for key in ("sessionID", "sessionId"):
            raw = properties.get(key)
            if isinstance(raw, str) and raw:
                return raw
        info = properties.get("info")
        if isinstance(info, Mapping):
            raw = info.get("sessionID", info.get("id"))
            if isinstance(raw, str) and raw:
                return raw
        return None

    def iter_changes(self) -> Iterator[SourceChange]:
        """Yield live hints. Normal end/failure requires a full source resync."""

        for value in self._client().sse("/api/event"):
            self._catalog_cache = None
            payload = value.get("payload") if isinstance(value.get("payload"), Mapping) else value
            self._interruptions.observe(payload)
            event_type = str(payload.get("type", "unknown")) if isinstance(payload, Mapping) else "unknown"
            yield SourceChange(
                source_id=self.source_id,
                event_type=event_type,
                session_id=self._event_session_id(value),
                payload=deepcopy(dict(value)),
            )
