"""The sole writable Web preference: bounded, preserving user JSONC theme edits.

No settings cache: reads use canonical configuration validation. Local writes are
serialized and compare file identity/bytes immediately before atomic replacement.
This detects ordinary editor conflicts, not hostile same-user filesystem races.
"""
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from threading import Lock

from src.config import ConfigError, read_jsonc, validated_values
from .instance_state import _private
from .process_identity import InstanceConflict

MAX_CONFIG_BYTES = 1024 * 1024
THEMES = ("classic", "web")
JSONC_TOKENS = re.compile(r'"(?:[^"\\]|\\.)*"|//[^\r\n]*|/\*[\s\S]*?\*/')


class ThemeError(ValueError):
    """Allowlisted public error code only; never includes parser text or paths."""


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ThemeError("settings_invalid_config")
        result[key] = value
    return result


def jsonc_document(raw):
    text = raw.decode("utf-8")
    # Keep offsets, CRLFs and every non-comment character intact for minimal edits.
    masked = JSONC_TOKENS.sub(lambda m: m[0] if m[0].startswith('"') else
                             re.sub(r"[^\r\n]", " ", m[0]), text)
    value = json.loads(masked, object_pairs_hook=unique_pairs)
    if not isinstance(value, dict):
        raise ThemeError("settings_invalid_config")
    return text, masked, value


def replace_theme(raw, theme):
    """Locate only a top-level value; preserve all other original bytes exactly."""
    text, masked, values = jsonc_document(raw)
    decoder = json.JSONDecoder()
    opening = masked.index("{")
    cursor = opening + 1
    while masked[cursor:].lstrip()[:1] != "}":
        cursor += len(masked[cursor:]) - len(masked[cursor:].lstrip())
        key, cursor = decoder.raw_decode(masked, cursor)
        cursor = masked.index(":", cursor) + 1
        cursor += len(masked[cursor:]) - len(masked[cursor:].lstrip())
        start = cursor
        _, cursor = decoder.raw_decode(masked, cursor)
        if key == "webTheme":
            return (text[:start] + json.dumps(theme) + text[cursor:]).encode("utf-8")
        cursor += len(masked[cursor:]) - len(masked[cursor:].lstrip())
        if masked[cursor] == ",":
            cursor += 1
    newline = "\r\n" if "\r\n" in text else "\n"
    insertion = newline + '  "webTheme": ' + json.dumps(theme) + ("," if values else "")
    return (text[:opening + 1] + insertion + text[opening + 1:]).encode("utf-8")


def safe_info(path, *, owned=False):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ThemeError("settings_unsafe_path")
    if owned and os.name != "nt" and info.st_uid != os.getuid():
        raise ThemeError("settings_unsafe_path")
    return info


def signature(info):
    # Windows CRT fstat ctime differs from Path.lstat (change vs birth time).
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


class ThemeSettings:
    def __init__(self, root):
        self.root = Path(root).absolute()
        self.directory = self.root / "config"
        self.path = self.directory / "user-config.jsonc"
        self.lock = Lock()

    def _paths(self):
        for path in (self.directory, *self.directory.parents):
            info = safe_info(path, owned=path in (self.directory, self.root))
            if not stat.S_ISDIR(info.st_mode):
                raise ThemeError("settings_unsafe_path")
        default = self.directory / "default-config.jsonc"
        info = safe_info(default)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_CONFIG_BYTES:
            raise ThemeError("settings_unsafe_path")

    def _snapshot(self):
        self._paths()
        try:
            info = safe_info(self.path, owned=True)
        except FileNotFoundError:
            return None, None
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ThemeError("settings_unsafe_path")
        if info.st_size > MAX_CONFIG_BYTES:
            raise ThemeError("settings_config_too_large")
        with self.path.open("rb") as stream:
            if signature(os.fstat(stream.fileno())) != signature(info):
                raise ThemeError("settings_conflict")
            raw = stream.read(MAX_CONFIG_BYTES + 1)
        if len(raw) > MAX_CONFIG_BYTES:
            raise ThemeError("settings_config_too_large")
        return raw, signature(info)

    def _values(self, raw):
        defaults = read_jsonc(self.directory / "default-config.jsonc")
        overrides = jsonc_document(raw)[2] if raw is not None else {}
        return validated_values(defaults, overrides)

    def read(self):
        return self._perform(None)

    def write(self, theme, *, allowed=lambda: True):
        if not isinstance(theme, str) or theme not in THEMES:
            raise ThemeError("invalid_request")
        return self._perform(theme, allowed=allowed)

    def _perform(self, theme, *, allowed=lambda: True):
        try:
            with self.lock:
                raw, identity = self._snapshot()
                effective = self._values(raw)
                if theme is None:
                    return effective["webTheme"]
                updated = replace_theme(raw if raw is not None else b"{\n}\n", theme)
                self._values(updated)
                if not allowed():
                    raise ThemeError("instance_stopping")
                self._commit(raw, identity, updated, allowed)
                return theme
        except ThemeError:
            raise
        except (ConfigError, ValueError, UnicodeError, RecursionError, OverflowError):
            raise ThemeError("settings_invalid_config") from None
        except (OSError, InstanceConflict):
            raise ThemeError("settings_not_writable" if theme is not None else "settings_unavailable") from None

    def _commit(self, raw, identity, updated, allowed):
        if raw is not None and not safe_info(self.path).st_mode & stat.S_IWUSR:
            raise ThemeError("settings_not_writable")
        descriptor, name = tempfile.mkstemp(prefix=".web-theme-", suffix=".tmp", dir=self.directory)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                _private(temporary)
                stream.write(updated)
                stream.flush()
                os.fsync(stream.fileno())
            current, current_identity = self._snapshot()
            if current_identity != identity or current != raw:
                raise ThemeError("settings_conflict")
            if not allowed():
                raise ThemeError("instance_stopping")
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
