"""OpenCode source discovery helpers.

Discovery is intentionally process-free. Cost Guard must not start OpenCode
merely to decide whether local history/a registered background service is
available.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


@dataclass(frozen=True, slots=True)
class DatabaseCandidate:
    path: Path
    origin: str


@dataclass(frozen=True, slots=True)
class ServiceRegistrationCandidate:
    path: Path
    origin: str


@dataclass(frozen=True, slots=True)
class ServiceRegistration:
    path: Path
    url: str
    pid: int
    version: str | None = None
    password: str | None = None
    username: str = "opencode"


class ServiceRegistrationError(ValueError):
    pass


def _expanded_path(value: str, home: Path) -> Path:
    text = value.strip()
    if text.startswith("~/") or text == "~":
        text = str(home) + text[1:]
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve(strict=False)


def find_opencode_executable(
    *, environment: Mapping[str, str] | None = None, home: Path | None = None,
    which: Callable[[str], str | None] | None = None,
) -> str | None:
    """Locate an executable without starting OpenCode or exposing local paths."""
    env = os.environ if environment is None else environment
    user_home = Path.home() if home is None else home
    lookup = shutil.which if which is None else which
    found = lookup("opencode")
    if found:
        return found
    directories = [
        user_home / ".opencode" / "bin",
        user_home / ".local" / "bin",
        user_home / "bin",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
    ]
    for key in ("OPENCODE_INSTALL_DIR", "XDG_BIN_DIR"):
        configured = env.get(key, "").strip()
        if configured:
            try:
                directory = _expanded_path(configured, user_home)
                directories.extend((directory, directory / "bin"))
            except (OSError, ValueError, RuntimeError):
                continue
    for directory in directories:
        executable = directory / "opencode"
        try:
            if executable.is_file() and os.access(executable, os.X_OK):
                return str(executable)
        except (OSError, ValueError):
            continue
    return None


def default_opencode_data_dir(
    *, environment: Mapping[str, str] | None = None, home: Path | None = None
) -> Path:
    """Return OpenCode's XDG-style data directory without invoking OpenCode."""

    env = os.environ if environment is None else environment
    user_home = Path.home() if home is None else home
    configured = env.get("XDG_DATA_HOME", "").strip()
    if configured:
        base = _expanded_path(configured, user_home)
    else:
        base = user_home / ".local" / "share"
    return base / "opencode"


def default_opencode_state_dir(
    *, environment: Mapping[str, str] | None = None, home: Path | None = None
) -> Path:
    """Return OpenCode's shared-service state directory without starting it."""

    env = os.environ if environment is None else environment
    user_home = Path.home() if home is None else home
    configured = env.get("XDG_STATE_HOME", "").strip()
    if configured:
        base = _expanded_path(configured, user_home)
    else:
        base = user_home / ".local" / "state"
    return (base / "opencode").resolve(strict=False)


def discover_v1_database_candidate(
    *, environment: Mapping[str, str] | None = None, home: Path | None = None
) -> DatabaseCandidate:
    """Resolve the V1 SQLite candidate path."""

    env = os.environ if environment is None else environment
    user_home = Path.home() if home is None else home
    override = env.get("OPENCODE_DB", "").strip()
    if override:
        return DatabaseCandidate(_expanded_path(override, user_home), "OPENCODE_DB")
    return DatabaseCandidate(
        (default_opencode_data_dir(environment=env, home=user_home) / "opencode.db").resolve(strict=False),
        "default",
    )


def discover_v2_registration_candidate(
    *, environment: Mapping[str, str] | None = None, home: Path | None = None
) -> ServiceRegistrationCandidate:
    """Resolve the documented V2 shared-service registration file."""

    env = os.environ if environment is None else environment
    user_home = Path.home() if home is None else home
    return ServiceRegistrationCandidate(
        (default_opencode_state_dir(environment=env, home=user_home) / "service.json").resolve(strict=False),
        "default",
    )


def has_opencode_installation_evidence(
    *, environment: Mapping[str, str] | None = None, home: Path | None = None,
    platform: str | None = None,
) -> bool:
    """Conservative filesystem evidence when no usable source or PATH CLI exists.

    Offline registrations, legacy data and standard install/config directories
    count as evidence, not usable sources. Inaccessible evidence is unknown:
    retain the runtime/source error rather than claim OpenCode is not installed.
    """
    env = os.environ if environment is None else environment
    user_home = Path.home() if home is None else home
    config_home = _expanded_path(env["XDG_CONFIG_HOME"], user_home) if env.get("XDG_CONFIG_HOME", "").strip() else user_home / ".config"
    candidates = [
        discover_v1_database_candidate(environment=env, home=user_home).path,
        default_opencode_data_dir(environment=env, home=user_home),
        default_opencode_state_dir(environment=env, home=user_home),
        user_home / ".opencode", config_home / "opencode",
    ]
    if env.get("LOCALAPPDATA"):
        candidates.append(Path(env["LOCALAPPDATA"]) / "Programs" / "OpenCode")
    if env.get("APPDATA"):
        candidates.extend(Path(env["APPDATA"]) / "npm" / name for name in ("opencode", "opencode.cmd"))
    system = sys.platform if platform is None else platform
    if system == "darwin":
        candidates.extend((user_home / "Applications/OpenCode.app", Path("/Applications/OpenCode.app")))
    elif system.startswith("linux"):
        candidates.extend(Path(name) for name in ("/usr/bin/opencode", "/usr/local/bin/opencode", "/opt/opencode"))
    for path in candidates:
        try:
            path.stat()
            return True
        except (FileNotFoundError, NotADirectoryError):
            continue
        except OSError:
            return True
    return False


def read_v2_service_registration(candidate: ServiceRegistrationCandidate) -> ServiceRegistration:
    """Read the public service registration contract without modifying it.

    Current OpenCode V2 registers ``url``, ``pid`` and optionally ``version``
    and ``password``.  ``auth`` is accepted as a forward-compatible equivalent
    when present, but no secrets are ever surfaced in validation messages.
    """

    path = candidate.path
    if not path.is_file():
        raise ServiceRegistrationError("OpenCode V2 service registration is missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ServiceRegistrationError("OpenCode V2 service registration is unreadable") from exc
    if not isinstance(value, dict):
        raise ServiceRegistrationError("OpenCode V2 service registration is invalid")
    url = value.get("url")
    pid = value.get("pid")
    version = value.get("version")
    if not isinstance(url, str) or not url.strip():
        raise ServiceRegistrationError("OpenCode V2 service registration has no URL")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise ServiceRegistrationError("OpenCode V2 service registration has no valid PID")
    if version is not None and not isinstance(version, str):
        raise ServiceRegistrationError("OpenCode V2 service registration has an invalid version")

    password: str | None = None
    username = "opencode"
    raw_password = value.get("password")
    if isinstance(raw_password, str) and raw_password:
        password = raw_password
    auth = value.get("auth")
    if isinstance(auth, dict) and auth.get("type") == "basic":
        if isinstance(auth.get("username"), str) and auth["username"].strip():
            username = auth["username"].strip()
        if isinstance(auth.get("password"), str) and auth["password"]:
            password = auth["password"]

    return ServiceRegistration(
        path=path,
        url=url.strip(),
        pid=pid,
        version=version.strip() if isinstance(version, str) and version.strip() else None,
        password=password,
        username=username,
    )
