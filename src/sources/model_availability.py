"""OpenCode model availability used to scope comparison rows to selectable models."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import unicodedata
from typing import Any, Callable, Mapping, Protocol
from src.sources.errors import SourceError


class ModelAvailabilitySource(Protocol):
    """Return the effective global list of selectable OpenCode model IDs.

    ``None`` means availability could not be established safely and callers
    should keep their existing unfiltered catalog rather than hide models.
    """

    def available_model_ids(self) -> tuple[str, ...] | None: ...


CommandRunner = Callable[[], tuple[int, str]]


def _valid_identity(value: str) -> bool:
    # Selectable IDs are opaque, not our own model-name grammar. Reject terminal
    # controls/bidi/whitespace and bound input without excluding new variants.
    return bool(value) and len(value) <= 1024 and not any(
        char.isspace() or unicodedata.category(char).startswith("C") for char in value
    )


def model_ids_from_v2_snapshot(value: Any) -> tuple[str, ...] | None:
    """Read selectable IDs from the current V2 model.list snapshot.

    ``id`` is the selectable identity; ``modelID`` is the upstream request name
    and may differ for configured variants/aliases. Unknown or partial shapes
    are not proof of availability. A valid empty/disabled-only list is proof.
    """
    models = value.get("data") if isinstance(value, Mapping) else value
    if not isinstance(models, list):
        return None
    result: dict[str, str] = {}
    for model in models:
        if not isinstance(model, Mapping) or not isinstance(model.get("enabled"), bool):
            return None
        if not model["enabled"]:
            continue
        provider, identity = model.get("providerID"), model.get("id")
        if not isinstance(provider, str) or not isinstance(identity, str):
            return None
        if "/" in provider or not _valid_identity(provider) or not _valid_identity(identity):
            return None
        full_id = f"{provider}/{identity}"
        result.setdefault(full_id.lower(), full_id)
    return tuple(result.values())


def settled_v2_model_ids(
    fetch: Callable[[], Any],
    *,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    interval: float = 0.3,
    quiet: float = 1.0,
    timeout: float = 6.0,
) -> tuple[str, ...] | None:
    """Return a V2 model list only after it stops changing.

    A freshly (re)started service boots each location lazily: model.list first
    answers a well-formed empty list, then provider-by-provider partial lists
    while plugins load. Those snapshots are valid in shape but not proof.
    Warm services settle after one confirming poll; after any observed change
    the list must stay unchanged for ``quiet`` seconds. Empty is proof only if
    it persists until ``timeout``; a still-changing list is not established.
    """
    deadline = clock() + timeout
    previous = model_ids_from_v2_snapshot(fetch())
    if previous is None:
        return None
    stable_since, window = clock(), interval
    while True:
        sleep(interval)
        current = model_ids_from_v2_snapshot(fetch())
        if current is None:
            return None
        now = clock()
        if {value.lower() for value in current} != {value.lower() for value in previous}:
            previous, stable_since, window = current, now, quiet
        elif previous and now - stable_since >= window:
            return previous
        if now >= deadline:
            return previous if not previous else None


class FallbackModelAvailabilitySource:
    """Prefer live selected-source truth, retaining CLI compatibility on failure."""

    def __init__(self, *sources: ModelAvailabilitySource) -> None:
        self.sources = sources

    def available_model_ids(self) -> tuple[str, ...] | None:
        for source in self.sources:
            try:
                result = source.available_model_ids()
            except (SourceError, OSError):
                # Advisory lookup errors must not leak private payloads/messages.
                continue
            if result is not None:
                return result
        return None


def _default_runner() -> tuple[int, str]:
    # OpenCode is commonly installed on Windows through an npm-style .cmd shim.
    # Resolve through PATHEXT first, then explicitly use cmd.exe for batch shims;
    # CreateProcess cannot portably execute a .cmd/.bat file as an executable.
    executable = shutil.which("opencode") or "opencode"
    command = [executable, "models"]
    if executable.lower().endswith((".cmd", ".bat")):
        comspec = os.environ.get("COMSPEC") or "cmd.exe"
        command = [comspec, "/d", "/s", "/c", subprocess.list2cmdline(command)]
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""
    return int(proc.returncode), proc.stdout or ""


class OpenCodeModelAvailabilitySource:
    """Read the effective global model list independently from quota accounts.

    This intentionally asks OpenCode itself rather than inferring entitlement
    from the pricing catalog.  For GitHub Copilot that preserves organization
    policy filtering (models disabled by the organization are omitted).
    """

    def __init__(self, *, runner: CommandRunner = _default_runner) -> None:
        self.runner = runner

    def available_model_ids(self) -> tuple[str, ...] | None:
        code, output = self.runner()
        if code != 0:
            return None
        result: list[str] = []
        seen: set[str] = set()
        output = re.sub(r"\x1b\[[0-9;]*m", "", output)
        for line in output.split("\n"):
            model_id = line.removesuffix("\r").strip(" \t")
            if "/" not in model_id:
                continue
            provider, identity = model_id.split("/", 1)
            if not _valid_identity(provider) or not _valid_identity(identity):
                return None
            key = model_id.lower()
            if key not in seen:
                seen.add(key)
                result.append(model_id)
        return tuple(result) if result or not output.strip() else None
