"""OpenCode V2 read-only Session Source over registered loopback HTTP.

Public API snapshots are authoritative; non-replayable events are hints.
No OpenCode CLI or V2 database access.
"""
from __future__ import annotations

import hashlib
import json
import time
import threading
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath, PureWindowsPath
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from src.domain import (
    BackgroundActivity,
    ActiveContext,
    ContextBoundary,
    IntegrationHealth,
    MessageRole,
    NormalizedMessage,
    NormalizedPart,
    NormalizedSession,
    Provenance,
    SessionCapabilities,
    SessionSnapshot,
)
from src.domain.acquisition import AcquisitionMetrics

from .base import SourceChange
from .discovery import (
    ServiceRegistration,
    ServiceRegistrationCandidate,
    ServiceRegistrationError,
    discover_v2_registration_candidate,
    read_v2_service_registration,
)
from .errors import (FailureCode, SourceConcurrentChangeError, SourceDataError, SourceError,
                     SourceSchemaError, SourceUnavailableError, compatibility_failure, transport_failure)
from .connectivity import SourceConnectivity, observed
from .model_availability import settled_v2_model_ids
from .opencode_v2_normalization import (
    normalize_message_bundle, normalize_request_invocations, optional_positive_int, safe_int,
)
from .opencode_v2_background import background_activities, running_jobs
from .opencode_v2_diagnostics import summarize_v2_diagnostics
from .opencode_v2_events import normalize_event
from .opencode_v2_interruptions import LiveInterruptionReasons
from .opencode_v2_catalog import V2CatalogIndex
from .opencode_v2_snapshot import load_snapshots
from .opencode_v2_tree import CardTreeBrackets
from .opencode_v2_model_identity import DesktopModelCatalog
from .opencode_v2_transport import V2Endpoint, V2HttpClient, normalize_local_service_url
from .opencode_v2_wire import (
    fetch_global_sessions,
    fetch_active_ids,
    fetch_active_context,
    fetch_messages,
    fetch_project_sessions,
    is_lifecycle_status_item,
    location_boundaries,
    normalize_message_items,
    normalize_terminal_lifecycle,
    selection_boundaries,
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


def _skill_path_origin(path: Any) -> str:
    if not isinstance(path, str) or not path:
        return ""
    normalized = path.replace(chr(92), "/").rstrip("/").casefold()
    if normalized == "/builtin" or normalized.startswith("/builtin/"):
        return "builtin"
    if PurePosixPath(path).is_absolute() or PureWindowsPath(path).is_absolute():
        return "custom"
    return ""


def _skill_origin_map(response: Any) -> dict[str, str]:
    values = response.get("data") if isinstance(response, Mapping) else None
    if not isinstance(values, list):
        return {}
    origins: dict[str, str] = {}
    ambiguous: set[str] = set()
    for value in values:
        if not isinstance(value, Mapping):
            continue
        skill_id = value.get("id")
        if not isinstance(skill_id, str) or not skill_id:
            continue
        origin = _skill_path_origin(value.get("path"))
        if skill_id in origins:
            if origins[skill_id] != origin:
                ambiguous.add(skill_id)
        elif origin:
            origins[skill_id] = origin
        else:
            ambiguous.add(skill_id)
    return {skill_id: origin for skill_id, origin in origins.items() if skill_id not in ambiguous}


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
        self._connectivity = SourceConnectivity("v2")
        self.read_recovery = None
        self._connection_lock = threading.RLock()
        self._reads_cancelled = threading.Event()
        self._timeout_seconds = timeout_seconds
        self._endpoint: V2Endpoint | None = None
        self._endpoint_marker: tuple[int, ...] | None = None
        self._catalog_cache: tuple[_NativeSession, ...] | None = None
        self._catalog_index: V2CatalogIndex | None = None
        self._message_lock = threading.Lock()
        self.metrics = AcquisitionMetrics(generation="v2")
        self._skill_origin_cache: dict[str, dict[str, str]] = {}
        self._catalog_listed_at = 0.0
        self._http: V2HttpClient | None = None
        self._instance_cache: tuple[str, str] | None = None
        self._interruptions = LiveInterruptionReasons()
        self._evidence_epoch = None
        self._card_trees: CardTreeBrackets | None = None
        self._model_identities = DesktopModelCatalog(self._client)
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
            self._connectivity.registration = exc.code.value
            self.refresh_connection()
            raise SourceUnavailableError(str(exc), code=exc.code, phase="registration",
                exception_type=type(exc.__cause__).__name__ if exc.__cause__ else "", generation="v2") from exc
        self._connectivity.registration = "valid"
        if registration.version and not registration.version.startswith("2."):
            raise SourceSchemaError("Registered OpenCode service is not a supported V2 service",
                                    code=FailureCode.VERSION, phase="probe", generation="v2")
        endpoint = V2Endpoint(
            url=normalize_local_service_url(registration.url),
            version=registration.version,
            pid=registration.pid,
            username=registration.username,
            password=registration.password,
            registration_path=registration.path,
        )
        if self._endpoint != endpoint:
            if self._http is not None:
                self._http.close()
            self._http = None
            self._catalog_cache = None
            self._catalog_index = None
            self._catalog_listed_at = 0.0
            self._skill_origin_cache.clear()
            self._model_identities = DesktopModelCatalog(self._client)
        else:
            endpoint = self._endpoint
        self._endpoint = endpoint
        return endpoint

    def _current_endpoint(self) -> V2Endpoint:
        """Reuse the registration until OpenCode rewrites it (a restarted service may move port/auth)."""
        try:
            stat = self._candidate.path.stat()
            marker = (stat.st_mtime_ns, stat.st_size, stat.st_ino, stat.st_ctime_ns)
        except OSError:
            marker = None
        if self._endpoint is None or marker != self._endpoint_marker:
            endpoint = self._read_endpoint()
            epoch = endpoint, marker
            if epoch != self._evidence_epoch:
                self._interruptions = LiveInterruptionReasons()
                self._catalog_cache = None
                self._catalog_index = None
                self._evidence_epoch = epoch
            self._endpoint_marker = marker
        return self._endpoint

    def new_card_reader(self) -> OpenCodeV2Source:
        """Construct without I/O; retain selection/timeout, not mutable callbacks."""
        return OpenCodeV2Source(candidate=self._candidate, timeout_seconds=self._timeout_seconds)

    def export_session(self, session_id, epoch, cancelled):
        from .opencode_v2_export import native_export
        return native_export(self, session_id, epoch, cancelled)

    def begin_card_read(self, origin: OpenCodeV2Source) -> None:
        """Fresh job state on an exclusively borrowed reader, before validation."""
        self.metrics = AcquisitionMetrics(generation='v2')
        self.metrics.add('card_reader_reuses', int(self._http is not None))
        self._skill_origin_cache.clear()
        if self._card_trees is None:
            self._card_trees = CardTreeBrackets(self, reuse_seconds=_CATALOG_REUSE_SECONDS)
        self._card_trees.reset_job()
        for key, value in self._diagnostics.items():
            if isinstance(value, dict):
                if key == 'transport':
                    # The existing HTTP client retains this exact numeric dict.
                    for counter in value:
                        value[counter] = 0
                else:
                    value.clear()
            elif isinstance(value, int):
                self._diagnostics[key] = 0
        self.inherit_live_evidence(origin, reuse_catalog=True)

    def inherit_live_evidence(self, origin: OpenCodeV2Source, *, reuse_catalog=False) -> bool:
        """Copy actor evidence only between isolated readers of one service epoch.

        The path-based source identity alone survives a restart. Compare both
        registrations' observed epochs as well; never share a mutable registry.
        """
        if not isinstance(origin, OpenCodeV2Source) or origin is self:
            return False
        with origin._connection_lock:
            origin._current_endpoint()
            epoch = origin.observation_epoch
            evidence = origin._interruptions.copy()
        with self._connection_lock:
            self._current_endpoint()
            same = epoch is not None and self.observation_epoch == epoch
            keep = reuse_catalog and same and self._interruptions.equivalent(evidence)
            self._interruptions = evidence if same else LiveInterruptionReasons()
            if not keep:
                self._catalog_cache = None
                self._catalog_index = None
                self._catalog_listed_at = 0.0
            return same

    def refresh_observation_epoch(self) -> None:
        """Refresh local registration only, not catalogs, health or transport."""
        with self._connection_lock:
            self._current_endpoint()

    @property
    def observation_epoch(self) -> str | None:
        """Nonsecret observed registration identity; never serialize endpoint/auth."""
        with self._connection_lock:
            if self._evidence_epoch is None or self._endpoint is None:
                return None
            endpoint, marker = self._evidence_epoch
            if marker is None or marker != self._endpoint_marker:
                return None
            values = (endpoint.url, endpoint.version, endpoint.pid, self.source_instance, marker)
            payload = json.dumps(values, separators=(',', ':')).encode('utf-8')
            return 'registration-v1:' + hashlib.sha256(payload).hexdigest()

    def _client(self) -> V2HttpClient:
        """One client (and keep-alive connection per thread) per registered endpoint."""
        with self._connection_lock:
            if self._reads_cancelled.is_set():
                raise transport_failure(ConnectionAbortedError(), phase="shutdown")
            endpoint = self._current_endpoint()
            client = self._http
            if client is None or client.endpoint is not endpoint:
                client = self._http = V2HttpClient(endpoint, timeout_seconds=self._timeout_seconds,
                                                    stats=self._diagnostics["transport"])
            if self._reads_cancelled.is_set():
                client.cancel()
                raise transport_failure(ConnectionAbortedError(), phase="shutdown")
            client.request_timeout = self.read_recovery.request_timeout if self.read_recovery is not None else None
            client.read_admission = getattr(self, 'read_admission', None)
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

    def refresh_connection(self, *, timeout_seconds: float | None = None) -> None:
        """Discard uncertain discovery/catalog/pool state without touching OpenCode."""
        with self._connection_lock:
            if self._http is not None:
                self._http.close()
            self._http = None
            self._endpoint = None
            self._endpoint_marker = None
            self._catalog_cache = None
            self._catalog_index = None
            self._catalog_listed_at = 0.0
            self._skill_origin_cache.clear()
            if timeout_seconds is not None:
                self._timeout_seconds = timeout_seconds

    def probe(self) -> IntegrationHealth:
        try:
            info = self._client().json("/api/info", phase="probe")
            if not isinstance(info, Mapping):
                raise SourceSchemaError("OpenCode V2 health response is unsupported", phase="probe", generation="v2")
            version = info.get("version")
            if not isinstance(version, str) or not version.startswith("2."):
                raise SourceSchemaError("OpenCode shared service is not a supported V2 version",
                                        code=FailureCode.VERSION, phase="probe", generation="v2")
        except SourceError as exc:
            self._connectivity.failed(exc, "probe")
            return IntegrationHealth(exc.code != FailureCode.REGISTRATION_MISSING, False,
                                     str(exc), exc.code.value, exc.phase, exc.exception_type, exc.http_status)
        self._connectivity.version = version[:24] if all(c.isdigit() or c == "." for c in version) else "2.x"
        self._connectivity.succeeded()
        return IntegrationHealth(True, True, f"OpenCode V2 service {self._connectivity.version} is reachable")

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
        return {**summarize_v2_diagnostics(self._diagnostics),
                "acquisition": self.metrics.snapshot(),
                "connectivity": self._connectivity.snapshot()}

    def available_model_ids(self) -> tuple[str, ...] | None:
        """Use the selected registered service's settled global model list."""
        client = self._client()
        return settled_v2_model_ids(lambda: client.json("/api/model"))

    def model_identities_current(self, models):
        self._current_endpoint()
        return self._model_identities.current(models)

    def skill_origins_for_session(self, session_id: str) -> Mapping[str, str]:
        """Resolve a session's registered location and read its skill origins."""
        if not isinstance(session_id, str) or not session_id:
            return {}
        if self._card_trees is not None and self._card_trees.supported:
            return self.skill_origins(self._card_trees.directory(session_id))
        try:
            sessions = self._list_native_sessions(refresh=False)
        except SourceError:
            return {}
        native = next((item for item in sessions if str(item.data.get("id")) == session_id), None)
        return self.skill_origins(native.directory) if native is not None else {}

    def skill_origins(self, directory: str) -> Mapping[str, str]:
        """Read verified skill source paths once per location and service generation."""
        if not isinstance(directory, str) or not directory:
            return {}
        with self._connection_lock:
            cached = self._skill_origin_cache.get(directory)
            if cached is not None:
                return dict(cached)
            try:
                response = self._client().json(
                    "/api/skill", query={"location[directory]": directory}, phase="skill_registry"
                )
            except SourceError:
                origins = {}
            else:
                origins = _skill_origin_map(response)
            self._skill_origin_cache[directory] = origins
            return dict(origins)

    def _list_native_sessions(
        self, since_ms: int | None = None, *, refresh: bool = True
    ) -> list[_NativeSession]:
        if since_ms is None and not refresh and self._catalog_cache is not None:
            return list(self._catalog_cache)
        started = time.perf_counter()
        self.metrics.add("full_catalog_fetches")
        client = self._client()
        raw_values: list[tuple[Mapping[str, Any], str]]
        contract: str
        pages: int
        try:
            raw_values, contract, pages = fetch_global_sessions(client)
        except (SourceUnavailableError, SourceDataError, SourceSchemaError) as exc:
            if not compatibility_failure(exc):
                raise
            raw_values, contract, pages = fetch_project_sessions(client, since_ms)
        else:
            # Older project-scoped services can accept /api/session globally but
            # return an empty array. Probe their project registry before treating
            # that as authoritative emptiness.
            if not raw_values:
                try:
                    legacy_values, legacy_contract, legacy_pages = fetch_project_sessions(client, since_ms)
                except (SourceUnavailableError, SourceDataError, SourceSchemaError) as exc:
                    if not compatibility_failure(exc):
                        raise
                else:
                    if legacy_values:
                        raw_values, contract, pages = legacy_values, legacy_contract, legacy_pages

        active_ids = fetch_active_ids(client)
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
        self.metrics.add("catalog_pages", pages)
        self.metrics.milliseconds["catalog"] = self.metrics.milliseconds.get("catalog", 0) + (time.perf_counter() - started) * 1000
        self._diagnostics["raw_sessions"] = len(result)
        if since_ms is None:
            self._catalog_cache = tuple(result)
            self._catalog_index = V2CatalogIndex(result)
            self.metrics.add("catalog_index_builds")
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

    @observed("catalog")
    def list_sessions(self, since_ms: int | None = None) -> Sequence[NormalizedSession]:
        self._diagnostics["last_snapshot_stage"] = "catalog"
        return tuple(self._normalize_session(value) for value in self._list_native_sessions(since_ms, refresh=True))

    @observed("catalog")
    def recent_session_catalog(self) -> Sequence[NormalizedSession]:
        """A just-completed selection/gap observation may serve the same report start."""
        fresh = self._catalog_cache is not None and time.monotonic() - self._catalog_listed_at <= _CATALOG_REUSE_SECONDS
        return tuple(self._normalize_session(value) for value in self._list_native_sessions(refresh=not fresh))

    @staticmethod
    def _tree(native: Sequence[_NativeSession], root_id: str) -> list[_NativeSession]:
        return V2CatalogIndex(native).tree(root_id)

    def _index(self) -> V2CatalogIndex:
        catalog = self._list_native_sessions(refresh=self._catalog_cache is None)
        return self._catalog_index or V2CatalogIndex(catalog)

    def watch_candidate_session_ids(self) -> frozenset[str]:
        """Native running state is independent of age; unsupported state fails open."""
        return frozenset(session_id for session_id, item in self._index().by_id.items() if item.active is not False)

    def _revision(self, tree: Sequence[_NativeSession]) -> str:
        started = time.perf_counter()
        self.metrics.add("revision_calculations")
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
                "revert": {
                    key: data["revert"].get(key)
                    for key in ("type", "messageID", "partID")
                } if isinstance(data.get("revert"), Mapping) else None,
                "fork": {
                    "sessionID": data["fork"].get("sessionID"),
                    "boundary": {
                        key: data["fork"]["boundary"].get(key)
                        for key in ("type", "messageID")
                    } if isinstance(data["fork"].get("boundary"), Mapping) else None,
                } if isinstance(data.get("fork"), Mapping) else None,
                "active": item.active,
            }
            live_reasons = self._interruptions.signature(str(data["id"]))
            if live_reasons:
                stable["live_interruptions"] = live_reasons
            digest.update(json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8"))
            digest.update(b"\n")
        self.metrics.milliseconds["revision"] = self.metrics.milliseconds.get("revision", 0) + (time.perf_counter() - started) * 1000
        return "v2-api:" + digest.hexdigest()

    def get_session_tree_revision(self, session_id: str) -> str:
        # Reuse the most recent complete catalog so a report can obtain many
        # root revisions without relisting every V2 project per root.  Snapshot
        # hydration refreshes independently and live events invalidate this hint.
        self.metrics.add("revision_checks")
        return self._index().revision(session_id, self._revision)

    def get_session_tree_revisions(self, session_ids: Sequence[str]) -> Mapping[str, str]:
        """Compute multiple V2 tree revisions from one complete session catalog."""
        unique = tuple(dict.fromkeys(str(value) for value in session_ids if str(value)))
        if not unique:
            return {}
        self._diagnostics["last_snapshot_stage"] = "catalog"
        self.metrics.add("revision_checks", len(unique))
        index = self._index()
        return {session_id: index.revision(session_id, self._revision) for session_id in unique}

    def _load_messages(self, native: _NativeSession) -> tuple[
        tuple[NormalizedMessage, ...], tuple[NormalizedPart, ...], tuple[ContextBoundary, ...],
        tuple[BackgroundActivity, ...], frozenset[str], ActiveContext | None,
    ]:
        session_id = str(native.data["id"])
        with self._message_lock:
            self.metrics.add("message_operations")
        active_context = fetch_active_context(self._client(), session_id=session_id)
        items, contract, pages, rejected_routes = fetch_messages(
            self._client(), session_id=session_id, directory=native.directory
        )
        with self._message_lock:
            return self._normalize_messages(native, items, contract, pages, rejected_routes, active_context)

    def _normalize_messages(self, native, items, contract, pages, rejected_routes, active_context):
        # Only network waits overlap. Canonical normalization and shared numeric
        # diagnostics remain serialized, outside the transport's own pool lock.
        session_id = str(native.data["id"])
        self.metrics.add("message_pages", pages)
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
            if message.role is MessageRole.ASSISTANT:
                message = replace(message, model=self._model_identities.resolve(message.model, native.directory))
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
        boundaries = (*location_boundaries(items, session_id=session_id),
                      *selection_boundaries(items, session_id=session_id))
        return (tuple(messages), tuple(parts), boundaries, background,
                notices, active_context)

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
            self.metrics.add('snapshot_catalog_reuses')
            return list(cached), True
        return self._list_native_sessions(refresh=True), False

    @observed("snapshot")
    def load_session_snapshot(self, session_id: str) -> SessionSnapshot:
        with self._connection_lock:
            self._client()
            epoch = self._evidence_epoch
        snapshot = load_snapshots(self, (session_id,),
            brackets=self._card_trees.bracket if self._card_trees is not None else None)[session_id]
        with self._connection_lock:
            self._current_endpoint()
            if epoch != self._evidence_epoch:
                raise SourceConcurrentChangeError('Service epoch changed during snapshot acquisition', phase='snapshot')
        return snapshot

    @observed("snapshot")
    def load_session_snapshots(self, session_ids: Sequence[str]) -> Mapping[str, SessionSnapshot]:
        return load_snapshots(self, session_ids)

    @observed('snapshot')
    def load_session_snapshots_for_sampling(self, session_ids: Sequence[str]) -> Mapping[str, SessionSnapshot]:
        """Strict single-reader lookahead; identify a failing member, return no partials."""
        if not 1 <= len(session_ids) <= 8:
            raise ValueError('invalid_sampling_window')
        return load_snapshots(self, session_ids, identify_members=True)

    @observed("snapshot")
    def load_session_snapshots_observed(self, session_ids: Sequence[str], progress) -> Mapping[str, SessionSnapshot]:
        """Explicit deep detail acquisition; ordinary Watch batches stay unchanged."""
        return load_snapshots(self, session_ids, workers=4, progress=progress)

    @observed("snapshot")
    def load_session_snapshots_available(self, session_ids: Sequence[str], progress) -> Mapping[str, SessionSnapshot]:
        """Partial-history opt-in: omit unstable trees, never return unverified data.

        Membership loss and transport/schema failures still fail the acquisition.
        Callers must expose missing coverage; ordinary snapshots remain strict.
        """
        return load_snapshots(self, session_ids, workers=4, progress=progress, available_only=True)

    @observed('snapshot')
    def load_card_snapshots(self, session_ids: Sequence[str], *, progress=None, on_root=None):
        """Watch-only small batches: typed member failures, no cross-epoch proof."""
        if not 1 <= len(session_ids) <= 3:
            raise ValueError('Card batches require one to three roots')
        with self._connection_lock:
            self._client()
            epoch = self._evidence_epoch
        failures = {}
        snapshots = load_snapshots(self, session_ids, workers=len(session_ids), progress=progress,
            available_only=True, failures=failures, on_root=on_root,
            brackets=self._card_trees.bracket if self._card_trees is not None else None)
        with self._connection_lock:
            self._current_endpoint()
            if epoch != self._evidence_epoch:
                raise SourceConcurrentChangeError('Service epoch changed during card acquisition', phase='snapshot')
        return snapshots, failures

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

    def close_changes(self) -> None:
        if self._http is not None:
            self._http.close_events()

    def cancel_reads(self) -> None:
        self._reads_cancelled.set()
        if self._http is not None:
            self._http.cancel()

    def close_reads(self) -> None:
        if self._http is not None:
            self._http.close()

    def iter_changes_until(self, stop_event: threading.Event) -> Iterator[SourceChange]:
        """Register cancellation before the first stream connection can start."""
        return self.iter_changes(stop_event=stop_event)

    def iter_changes(self, *, stop_event: threading.Event | None = None) -> Iterator[SourceChange]:
        """Yield live hints. Normal end/failure requires a full source resync."""

        if stop_event is not None and stop_event.is_set():
            return
        try:
            client = self._client()
            evidence = self._interruptions
            for value in client.sse("/api/event", stop_event=stop_event):
                self._catalog_cache = None
                self._catalog_index = None
                payload = value.get("payload") if isinstance(value.get("payload"), Mapping) else value
                evidence.observe(payload)
                event_type = str(payload.get("type", "unknown")) if isinstance(payload, Mapping) else "unknown"
                yield SourceChange(
                    source_id=self.source_id,
                    event_type=event_type,
                    session_id=self._event_session_id(value),
                    payload=deepcopy(dict(value)),
                )
        except SourceError as error:
            if stop_event is None or not stop_event.is_set():
                self._connectivity.failed(error, "event_stream")
                raise
