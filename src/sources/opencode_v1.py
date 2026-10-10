"""Read-only OpenCode V1 SQLite Session Source.

The adapter owns all knowledge of the legacy ``session``/``message``/``part``
schema.  It never shells out to ``opencode db`` and never writes OpenCode
persistence.  Native rows are normalized into Cost Guard's canonical domain
before leaving this module.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from src.domain import (
    CostKind,
    CostObservation,
    EventKind,
    IntegrationHealth,
    MessageRole,
    ModelInvocation,
    ModelRef,
    NormalizedEvent,
    NormalizedMessage,
    NormalizedPart,
    NormalizedSession,
    Provenance,
    SessionCapabilities,
    SessionSnapshot,
    TokenUsage,
)

from .discovery import DatabaseCandidate, discover_v1_database_candidate
from .errors import SourceDataError, SourceError, SourceSchemaError, SourceUnavailableError
from .opencode_errors import normalize_error_name as _error_name
from .opencode_errors import normalize_abort_reason
from .opencode_tokens import token_usage
from .opencode_v1_revision import batch_revisions, revision_from_rows, revision_rows


REQUIRED_COLUMNS: dict[str, frozenset[str]] = {
    "session": frozenset({
        "id", "parent_id", "project_id", "directory", "title",
        "time_created", "time_updated", "time_archived",
    }),
    "message": frozenset({"id", "session_id", "time_created", "time_updated", "data"}),
    "part": frozenset({"id", "message_id", "session_id", "time_created", "time_updated", "data"}),
}

V1_CAPABILITIES = SessionCapabilities(
    exact_input_tokens=True,
    exact_output_tokens=True,
    exact_reasoning_tokens=True,
    exact_cache_read_tokens=True,
    exact_cache_write_tokens=True,
    native_cost=True,
    child_sessions=True,
    compaction_events=True,
    live_changes=False,
)

_SYNTHETIC_CONTINUATION = re.compile(
    r"^\s*Summarize the task tool output above and continue with your task\.?\s*$",
    flags=re.IGNORECASE,
)
_VISIBLE_USER_PARTS = frozenset({"text", "file", "subtask"})


@dataclass(frozen=True, slots=True)
class V1SchemaInfo:
    tables: tuple[str, ...]
    supported: bool
    detail: str = ""


def _safe_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _optional_positive_int(value: Any) -> int | None:
    parsed = _safe_int(value, 0)
    return parsed if parsed > 0 else None


def _decimal(value: Any, *, context: str) -> Decimal:
    try:
        result = Decimal(str(0 if value is None else value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise SourceDataError(f"OpenCode V1 {context} contains an invalid numeric value") from exc
    if not result.is_finite() or result < 0:
        raise SourceDataError(f"OpenCode V1 {context} contains an invalid numeric value")
    return result


def _token_usage(value: Any, *, context: str) -> TokenUsage | None:
    return token_usage(value, context=context, source="OpenCode V1")


def _model_ref(provider: Any, model: Any) -> ModelRef | None:
    provider_text = "" if provider is None else str(provider).strip()
    model_text = "" if model is None else str(model).strip()
    if not provider_text and not model_text:
        return None
    return ModelRef(provider=provider_text, model=model_text)


def _message_model(data: Mapping[str, Any]) -> tuple[ModelRef | None, str | None]:
    role = str(data.get("role", ""))
    variant: str | None = None
    if role == "user":
        nested = data.get("model")
        if isinstance(nested, Mapping):
            model = _model_ref(nested.get("providerID"), nested.get("modelID"))
            raw_variant = nested.get("variant")
            variant = str(raw_variant) if raw_variant not in (None, "") else None
            return model, variant
        return None, None
    model = _model_ref(data.get("providerID"), data.get("modelID"))
    raw_variant = data.get("variant")
    variant = str(raw_variant) if raw_variant not in (None, "") else None
    return model, variant


def _part_semantic_data(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a detached semantic payload without native row identity fields."""

    result = deepcopy(dict(data))
    for key in ("id", "messageID", "sessionID"):
        result.pop(key, None)
    return result


def _part_cost(data: Mapping[str, Any]) -> CostObservation | None:
    if "cost" not in data:
        return None
    return CostObservation(
        amount=_decimal(data.get("cost"), context="step cost"),
        currency="USD",
        kind=CostKind.PROVIDER_REPORTED,
        estimated=False,
    )


def _message_cost(data: Mapping[str, Any]) -> CostObservation | None:
    if "cost" not in data:
        return None
    return CostObservation(
        amount=_decimal(data.get("cost"), context="message cost"),
        currency="USD",
        kind=CostKind.PROVIDER_REPORTED,
        estimated=False,
    )


def _event_text(parts: Sequence[NormalizedPart]) -> str:
    values: list[str] = []
    for part in parts:
        data = part.data
        synthetic = bool(data.get("synthetic", False))
        if part.kind not in _VISIBLE_USER_PARTS or synthetic:
            continue
        if part.kind == "text":
            text = str(data.get("text", "")).strip()
            if text:
                values.append(text)
        elif part.kind == "file":
            filename = str(data.get("filename", "")).strip()
            if filename:
                values.append(f"[file: {filename}]")
        elif part.kind == "subtask":
            command = str(data.get("command", "")).strip()
            description = str(data.get("description", "")).strip()
            prompt = str(data.get("prompt", "")).strip()
            prefix = f"/{command}" if command else "[subtask]"
            if description:
                values.append(f"{prefix} - {description}")
            elif prompt:
                preview = " ".join(prompt.split())
                if len(preview) > 240:
                    preview = preview[:240]
                values.append(f"{prefix} - {preview}")
            else:
                values.append(prefix)
    return " ".join(" ".join(values).replace("\t", " ").split())


def _event_kind(parts: Sequence[NormalizedPart]) -> EventKind:
    if any(part.kind == "compaction" for part in parts):
        return EventKind.COMPACTION
    visible = [
        part for part in parts
        if part.kind in _VISIBLE_USER_PARTS and not bool(part.data.get("synthetic", False))
    ]
    if any(part.kind == "subtask" for part in visible):
        return EventKind.SUBTASK
    if visible:
        return EventKind.USER_PROMPT
    for part in parts:
        if part.kind != "text" or not bool(part.data.get("synthetic", False)):
            continue
        if _SYNTHETIC_CONTINUATION.match(str(part.data.get("text", ""))):
            return EventKind.SYNTHETIC_CONTINUATION
    return EventKind.OTHER


def _event_metadata(message: NormalizedMessage) -> dict[str, str]:
    metadata: dict[str, str] = {}
    if message.model:
        metadata["provider_id"] = message.model.provider
        metadata["model_id"] = message.model.model
    if message.variant:
        metadata["variant"] = message.variant
    if message.agent:
        metadata["agent"] = message.agent
    for part in message.parts:
        if part.kind == "subtask":
            model = part.data.get("model")
            if isinstance(model, Mapping):
                provider = str(model.get("providerID", "")).strip()
                model_id = str(model.get("modelID", "")).strip()
                variant = str(model.get("variant", "")).strip()
                if provider:
                    metadata["provider_id"] = provider
                if model_id:
                    metadata["model_id"] = model_id
                if variant:
                    metadata["variant"] = variant
        elif part.kind == "compaction":
            metadata["auto"] = "true" if bool(part.data.get("auto", False)) else "false"
            tail = part.data.get("tail_start_id", part.data.get("tailStartId"))
            if tail:
                metadata["tail_start_id"] = str(tail)
    return metadata


class OpenCodeV1Source:
    """OpenCode V1 history reader backed by legacy SQLite projection tables."""

    source_id = "opencode-v1"
    capabilities = V1_CAPABILITIES

    def __init__(self, db_path: Path | str | None = None, *, candidate: DatabaseCandidate | None = None):
        if candidate is not None and db_path is not None:
            raise ValueError("Specify db_path or candidate, not both")
        if candidate is None:
            if db_path is None:
                candidate = discover_v1_database_candidate()
            else:
                candidate = DatabaseCandidate(Path(db_path).expanduser().resolve(strict=False), "explicit")
        self._candidate = candidate
        self._path = candidate.path
        path_key = str(self._path).encode("utf-8", errors="surrogatepass")
        self._instance_id = "sqlite:" + hashlib.sha256(path_key).hexdigest()[:16]

    @property
    def database_path(self) -> Path:
        return self._path

    @property
    def source_instance(self) -> str:
        return self._instance_id

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        if not self._path.is_file():
            raise SourceUnavailableError("OpenCode V1 database is not available")
        # as_uri() safely encodes spaces/non-ASCII.  mode=ro prevents creation and
        # writes while still allowing SQLite to observe an active WAL file.
        uri = self._path.resolve().as_uri() + "?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True, timeout=5.0)
        except sqlite3.Error as exc:
            raise SourceUnavailableError("OpenCode V1 database could not be opened read-only") from exc
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            yield connection
        except sqlite3.Error as exc:
            # Includes OperationalError, InterfaceError and DatabaseError.
            # Never leak SQLite's raw text (which may contain local paths).
            raise SourceDataError(
                f"OpenCode V1 SQLite {type(exc).__name__} during database read"
            ) from exc
        finally:
            connection.close()

    def inspect_schema(self) -> V1SchemaInfo:
        if not self._path.is_file():
            return V1SchemaInfo((), False, "database missing")
        try:
            with self._connection() as connection:
                table_rows = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
                tables = tuple(str(row["name"]) for row in table_rows)
                missing_tables = [table for table in REQUIRED_COLUMNS if table not in tables]
                if missing_tables:
                    return V1SchemaInfo(tables, False, "missing legacy tables: " + ", ".join(missing_tables))
                for table, required in REQUIRED_COLUMNS.items():
                    columns = {
                        str(row["name"])
                        for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
                    }
                    missing = sorted(required - columns)
                    if missing:
                        return V1SchemaInfo(tables, False, f"unsupported {table} schema; missing: {', '.join(missing)}")
                return V1SchemaInfo(tables, True, "legacy V1 schema available")
        except SourceError:
            raise

    def probe(self) -> IntegrationHealth:
        if not self._path.is_file():
            detail = (
                "OPENCODE_DB does not point to an existing database"
                if self._candidate.origin == "OPENCODE_DB"
                else "OpenCode V1 database was not found at the standard data location"
            )
            return IntegrationHealth(available=False, healthy=False, detail=detail)
        try:
            schema = self.inspect_schema()
        except SourceError as exc:
            return IntegrationHealth(available=True, healthy=False, detail=str(exc))
        if not schema.supported:
            return IntegrationHealth(available=True, healthy=False, detail=schema.detail)
        return IntegrationHealth(available=True, healthy=True, detail="OpenCode V1 SQLite history is readable")

    def _require_schema(self, connection: sqlite3.Connection) -> None:
        tables = {
            str(row["name"])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        missing_tables = [table for table in REQUIRED_COLUMNS if table not in tables]
        if missing_tables:
            raise SourceSchemaError("OpenCode V1 database is missing required legacy history tables")
        for table, required in REQUIRED_COLUMNS.items():
            columns = {
                str(row["name"])
                for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
            }
            if not required.issubset(columns):
                raise SourceSchemaError(f"OpenCode V1 {table} schema is not supported")

    def _session_provenance(self, session_id: str) -> Provenance:
        return Provenance(
            source_type="opencode",
            source_generation="v1",
            source_instance=self._instance_id,
            source_session_id=session_id,
        )

    def _event_provenance(self, session_id: str, event_id: str) -> Provenance:
        return Provenance(
            source_type="opencode",
            source_generation="v1",
            source_instance=self._instance_id,
            source_session_id=session_id,
            source_event_id=event_id,
        )

    def _normalize_session(self, row: sqlite3.Row) -> NormalizedSession:
        session_id = str(row["id"])
        return NormalizedSession(
            session_id=session_id,
            title=str(row["title"] or session_id),
            created_at_ms=_safe_int(row["time_created"]),
            updated_at_ms=_safe_int(row["time_updated"]),
            archived_at_ms=_optional_positive_int(row["time_archived"]),
            parent_session_id=str(row["parent_id"]) if row["parent_id"] not in (None, "") else None,
            provenance=self._session_provenance(session_id),
            capabilities=self.capabilities,
        )

    def list_sessions(self, since_ms: int | None = None) -> Sequence[NormalizedSession]:
        with self._connection() as connection:
            self._require_schema(connection)
            sql = (
                "SELECT id, parent_id, project_id, directory, title, "
                "time_created, time_updated, time_archived FROM session"
            )
            params: tuple[Any, ...] = ()
            if since_ms is not None:
                sql += " WHERE time_updated >= ?"
                params = (int(since_ms),)
            sql += " ORDER BY time_updated DESC, id DESC"
            rows = connection.execute(sql, params).fetchall()
            return tuple(self._normalize_session(row) for row in rows)

    def _tree_rows(self, connection: sqlite3.Connection, session_id: str) -> list[sqlite3.Row]:
        rows = connection.execute(
            """
            WITH RECURSIVE tree(id, depth) AS (
              SELECT id, 0 FROM session WHERE id = ?
              UNION
              SELECT s.id, tree.depth + 1
              FROM session s JOIN tree ON s.parent_id = tree.id
            )
            SELECT s.id, s.parent_id, s.project_id, s.directory, s.title,
                   s.time_created, s.time_updated, s.time_archived, tree.depth
            FROM tree JOIN session s ON s.id = tree.id
            ORDER BY tree.depth, s.time_created, s.id
            """,
            (session_id,),
        ).fetchall()
        if not rows:
            raise SourceDataError("OpenCode V1 session does not exist")
        return list(rows)

    def get_session_tree_revision(self, session_id: str) -> str:
        with self._connection() as connection:
            self._require_schema(connection)
            return revision_from_rows(revision_rows(connection, session_id))

    def get_session_tree_revisions(self, session_ids: Sequence[str]) -> Mapping[str, str]:
        """Return multiple conservative tree revisions with one SQLite statement."""
        with self._connection() as connection:
            self._require_schema(connection)
            return batch_revisions(connection, session_ids)

    @staticmethod
    def _json_object(raw: Any, *, context: str) -> dict[str, Any]:
        if not isinstance(raw, str):
            raise SourceDataError(f"OpenCode V1 {context} is not JSON text")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SourceDataError(f"OpenCode V1 {context} contains malformed JSON") from exc
        if not isinstance(value, dict):
            raise SourceDataError(f"OpenCode V1 {context} JSON is not an object")
        return value

    def _normalize_part(self, row: sqlite3.Row) -> NormalizedPart:
        data = self._json_object(row["data"], context="part")
        session_id = str(row["session_id"])
        part_id = str(row["id"])
        kind = str(data.get("type", "other") or "other")
        return NormalizedPart(
            part_id=part_id,
            message_id=str(row["message_id"]),
            session_id=session_id,
            kind=kind,
            created_at_ms=_safe_int(row["time_created"]),
            updated_at_ms=_safe_int(row["time_updated"]),
            provenance=self._event_provenance(session_id, part_id),
            data=_part_semantic_data(data),
        )

    def _normalize_message(
        self, row: sqlite3.Row, parts: tuple[NormalizedPart, ...]
    ) -> NormalizedMessage:
        data = self._json_object(row["data"], context="message")
        session_id = str(row["session_id"])
        message_id = str(row["id"])
        role_text = str(data.get("role", "")).lower()
        role = {
            "user": MessageRole.USER,
            "assistant": MessageRole.ASSISTANT,
        }.get(role_text, MessageRole.OTHER)
        time_data = data.get("time") if isinstance(data.get("time"), Mapping) else {}
        created = _safe_int(time_data.get("created"), _safe_int(row["time_created"]))
        completed = _optional_positive_int(time_data.get("completed"))
        model, variant = _message_model(data)
        metadata: dict[str, Any] = {}
        for key in ("mode", "system", "structured"):
            if key in data:
                metadata[key] = deepcopy(data[key])
        return NormalizedMessage(
            message_id=message_id,
            session_id=session_id,
            role=role,
            created_at_ms=created,
            completed_at_ms=completed,
            parent_message_id=str(data.get("parentID")) if data.get("parentID") not in (None, "") else None,
            model=model,
            variant=variant,
            agent=str(data.get("agent")) if data.get("agent") not in (None, "") else None,
            summary=bool(data.get("summary", False)),
            finish_reason=str(data.get("finish")) if data.get("finish") not in (None, "") else None,
            error_name=_error_name(data.get("error")),
            abort_reason=normalize_abort_reason(data.get("error")),
            tokens=_token_usage(data.get("tokens"), context="message tokens"),
            cost=_message_cost(data),
            parts=parts,
            provenance=self._event_provenance(session_id, message_id),
            metadata=metadata,
        )

    def _normalize_event(self, message: NormalizedMessage) -> NormalizedEvent | None:
        if message.role is not MessageRole.USER:
            return None
        kind = _event_kind(message.parts)
        text = _event_text(message.parts)
        return NormalizedEvent(
            event_id=message.message_id,
            session_id=message.session_id,
            kind=kind,
            created_at_ms=message.created_at_ms,
            provenance=message.provenance,
            text=text or None,
            metadata=_event_metadata(message),
        )

    def _normalize_invocations(self, message: NormalizedMessage) -> list[ModelInvocation]:
        if message.role is not MessageRole.ASSISTANT or message.model is None:
            return []
        steps = [part for part in message.parts if part.kind == "step-finish" and isinstance(part.data.get("tokens"), Mapping)]
        result: list[ModelInvocation] = []
        if steps:
            for index, part in enumerate(steps):
                tokens = _token_usage(part.data.get("tokens"), context="step tokens")
                if tokens is None:
                    continue
                result.append(ModelInvocation(
                    invocation_id=f"{message.message_id}:{part.part_id}",
                    session_id=message.session_id,
                    created_at_ms=message.created_at_ms,
                    completed_at_ms=message.completed_at_ms,
                    model=message.model,
                    tokens=tokens,
                    cost=_part_cost(part.data),
                    provenance=self._event_provenance(message.session_id, part.part_id),
                    initiating_event_id=message.parent_message_id,
                    message_id=message.message_id,
                    step_part_id=part.part_id,
                    variant=message.variant,
                    summary=message.summary,
                    finish_reason=message.finish_reason,
                    error_name=message.error_name,
                ))
            return result
        if message.tokens is None:
            return []
        result.append(ModelInvocation(
            invocation_id=message.message_id,
            session_id=message.session_id,
            created_at_ms=message.created_at_ms,
            completed_at_ms=message.completed_at_ms,
            model=message.model,
            tokens=message.tokens,
            cost=message.cost,
            provenance=message.provenance,
            initiating_event_id=message.parent_message_id,
            message_id=message.message_id,
            variant=message.variant,
            summary=message.summary,
            finish_reason=message.finish_reason,
            error_name=message.error_name,
        ))
        return result

    def load_session_snapshot(self, session_id: str) -> SessionSnapshot:
        with self._connection() as connection:
            self._require_schema(connection)
            # Pin one SQLite read snapshot so session/tree metadata, revision
            # evidence, messages and parts cannot come from different writer
            # generations while OpenCode is active in WAL mode.
            connection.execute("BEGIN")
            tree_rows = self._tree_rows(connection, session_id)
            revision_state = revision_rows(connection, session_id)
            session_ids = tuple(str(row["id"]) for row in tree_rows)
            placeholders = ",".join("?" for _ in session_ids)
            message_rows = connection.execute(
                f"""
                SELECT id, session_id, time_created, time_updated, data
                FROM message WHERE session_id IN ({placeholders})
                ORDER BY time_created, id
                """,
                session_ids,
            ).fetchall()
            part_rows = connection.execute(
                f"""
                SELECT id, message_id, session_id, time_created, time_updated, data
                FROM part WHERE session_id IN ({placeholders})
                ORDER BY message_id, time_created, id
                """,
                session_ids,
            ).fetchall()
            connection.commit()

        sessions = tuple(self._normalize_session(row) for row in tree_rows)
        part_values = tuple(self._normalize_part(row) for row in part_rows)
        parts_by_message: dict[str, list[NormalizedPart]] = {}
        for part in part_values:
            parts_by_message.setdefault(part.message_id, []).append(part)
        messages = tuple(
            self._normalize_message(row, tuple(parts_by_message.get(str(row["id"]), ())))
            for row in message_rows
        )
        events = tuple(
            event
            for message in messages
            if (event := self._normalize_event(message)) is not None
        )
        invocations_list: list[ModelInvocation] = []
        for message in messages:
            invocations_list.extend(self._normalize_invocations(message))
        invocations = tuple(sorted(
            invocations_list,
            key=lambda value: (
                value.completed_at_ms if value.completed_at_ms is not None else value.created_at_ms,
                value.invocation_id,
            ),
        ))
        root = next(session for session in sessions if session.session_id == session_id)
        return SessionSnapshot(
            root=root,
            sessions=sessions,
            messages=messages,
            parts=part_values,
            events=events,
            invocations=invocations,
            source_revision=revision_from_rows(revision_state),
        )
