"""Stable JSON identity for persisted cache dependencies."""
from hashlib import sha256
import json
from typing import Any


def dependency_signature(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str)
    return sha256(payload.encode("utf-8")).hexdigest()
