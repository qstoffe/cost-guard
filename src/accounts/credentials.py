"""Bounded, read-only account inventory for the selected OpenCode installation.

No federation, credential refresh or credential persistence. Opaque source IDs
are derived from locators, never from secret/token bytes.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Mapping, Sequence

from src.domain import AccountRef


@dataclass(frozen=True, slots=True)
class CredentialRecord:
    ref: AccountRef
    value: Mapping[str, object] = field(repr=False)
    active: bool = True


def source_identity(path: Path) -> str:
    return "opencode:" + hashlib.sha256(os.path.normcase(str(path.resolve(strict=False))).encode()).hexdigest()[:24]


def resolve_auth_path(override: str | None, *, home: Path | None = None) -> Path:
    if override is not None and override.strip():
        return Path(os.path.expandvars(os.path.expanduser(override.strip())))
    return (home or Path.home()) / ".local" / "share" / "opencode" / "auth.json"


def _record(provider: str, path: Path, locator: str, value: object, active: bool = True) -> CredentialRecord | None:
    if not isinstance(value, Mapping) or value.get("type") not in {"oauth", "api"}:
        return None
    metadata = value.get("metadata") if isinstance(value.get("metadata"), Mapping) else {}
    account_id = value.get("accountId") or value.get("account_id") or metadata.get("accountID")
    label = metadata.get("accountLabel") or metadata.get("label")
    return CredentialRecord(AccountRef(
        source_identity(path), provider, str(account_id) if account_id else None,
        locator, str(label) if isinstance(label, str) and label.strip() else None,
    ), value, active)


def configured_credentials(
    auth_path: Path, db_path: Path | None, providers: Sequence[str],
) -> tuple[CredentialRecord, ...]:
    """V2 rows take precedence per integration; no silent identity switching.

    Inactive configured accounts are quota-visible, not selected for inference.
    Unknown V2 schema/read errors fail closed rather than falling back identities.
    """
    records = []
    present: set[str] = set()
    if db_path is not None and db_path.is_file():
        try:
            with closing(sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)) as conn:
                conn.execute("PRAGMA query_only=ON")
                if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='credential'").fetchone():
                    columns = {row[1] for row in conn.execute("PRAGMA table_info(credential)")}
                    if not {"integration_id", "value"} <= columns:
                        return ()
                    identity = "id" if "id" in columns else "rowid"
                    active = "active" if "active" in columns else "1"
                    placeholders = ",".join("?" for _ in providers)
                    rows = conn.execute(
                        f"SELECT {identity}, integration_id, value, {active} FROM credential "
                        f"WHERE integration_id IN ({placeholders}) ORDER BY {identity}", tuple(providers),
                    ).fetchall()
                    for row_id, provider, raw, is_active in rows:
                        present.add(provider)
                        try:
                            value = json.loads(raw)
                        except (ValueError, TypeError):
                            continue
                        record = _record(provider, db_path, f"credential:{row_id}", value, bool(is_active))
                        if record:
                            records.append(record)
        except (sqlite3.Error, OSError):
            return ()
    try:
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        auth = {}
    if isinstance(auth, Mapping):
        for provider in providers:
            if provider not in present:
                record = _record(provider, auth_path, f"auth:{provider}", auth.get(provider))
                if record:
                    records.append(record)
    unique = {}
    for record in records:
        prior = unique.get(record.ref.key)
        if prior is None or record.active:
            unique[record.ref.key] = record
    return tuple(unique.values())
