"""Shared read-only OpenCode inventory; source-specific identities stay adapters'."""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from .credentials import CredentialRecord, CredentialView, read_credentials


@dataclass(frozen=True, slots=True)
class AccountCandidate:
    slot: int
    provider: object = field(repr=False)
    revision: object
    records: tuple[CredentialRecord, ...] | None = field(default=None, repr=False)


def _stamp(path: Path | None) -> tuple[object, ...]:
    if path is None:
        return ()
    try:
        stat = path.stat()
        return (stat.st_mtime_ns, stat.st_size, stat.st_ino)
    except OSError:
        return (None,)


class AccountDiscovery:
    """Read each shared auth/SQLite source once per revision, including WAL changes.

    No secret hashing, persistence or model-list inference. Other integrations keep
    their own probe contract on the isolated worker (e.g. Claude CLI metadata).
    """
    def __init__(self, providers: Sequence[object]):
        self.providers = tuple(providers)
        self._views: dict[tuple[Path, Path | None], tuple[object, CredentialView]] = {}
        self.failed_slots: set[int] = set()
        self._identities: dict[int, tuple[tuple[CredentialRecord, ...], int]] = {}

    def discover(self) -> tuple[AccountCandidate, ...]:
        result = []
        self.failed_slots.clear()
        for slot, provider in enumerate(self.providers):
            if not getattr(provider, "enabled", True):
                continue
            ids = getattr(provider, "integration_ids", None)
            if not isinstance(ids, (tuple, list)) or not all(isinstance(value, str) for value in ids) or not hasattr(provider, "auth_json_path"):
                result.append(AccountCandidate(slot, provider, None))
                continue
            auth, db = provider.auth_json_path, provider.credential_db_path
            key = (auth.resolve(strict=False), db.resolve(strict=False) if db else None)
            stamp = (_stamp(auth), _stamp(db), _stamp(Path(str(db) + "-wal")) if db else ())
            view = self._views.get(key)
            if view is None or view[0] != stamp:
                view = (stamp, read_credentials(auth, db, None))
                self._views[key] = view
            if not view[1].healthy:
                self.failed_slots.add(slot)
            records = tuple(record for record in view[1].records if record.ref.provider_id in ids)
            previous, generation = self._identities.get(slot, ((), 0))
            if previous != records:
                generation += 1
                self._identities[slot] = (records, generation)
            if records:
                pinned = copy(provider)
                pinned.credential_records = records
                result.append(AccountCandidate(slot, pinned, (key, generation), records))
        return tuple(result)

    def close(self) -> None:
        self._views.clear()
        self._identities.clear()
