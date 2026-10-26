"""Read only this checkout's bounded Web facts, without importing/starting Web."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

STATES = {"starting", "ready", "menu", "launcher", "source_changed", "runtime_fault", "gui_unavailable"}
SOURCE_STATES = {"loading", "running", "recovering", "source_unavailable", "failed",
                 "internal_error", "result_too_large", "unknown"}
CODES = {"starting", "ready", "stopped", "source_changed", "source_check_unavailable",
         "runtime_fault", "gui_unavailable", "tray_unavailable", "instance_start_timeout",
         "browser_open_failed", "configuration_unavailable", "instance_conflict",
         "gui_or_server_start_failed", "app_preparation_failed"}


def _read(path, limit):
    for item in (path, *path.parents):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("unsafe_path")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise ValueError("invalid_file")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("oversize")
    return data


def _snapshot(value):
    numeric = ("observed_at", "source_transitions", "uptime_ms")
    if (not isinstance(value, dict) or value.get("schema_version") != 1
            or value.get("instance_schema") != 1
            or not isinstance(value.get("product_version"), str)
            or not re.fullmatch(r"[0-9]{1,4}\.[0-9]{1,4}", value["product_version"])
            or value.get("state") not in STATES or value.get("source_status") not in SOURCE_STATES
            or any(type(value.get(k)) is not int or not 0 <= value[k] < 2**53 for k in numeric)):
        raise ValueError("invalid_snapshot")
    failures = value.get("api_failures")
    keys = ("denied", "invalid", "busy", "unavailable")
    if (not isinstance(failures, dict) or any(type(failures.get(k)) is not int or
            not 0 <= failures[k] <= 1_000_000 for k in keys)):
        raise ValueError("invalid_counters")
    return {k: value[k] for k in ("schema_version", "instance_schema", "product_version", "state",
                                 "source_status", *numeric)} | {"api_failures": {k: failures[k] for k in keys}}


def web_evidence(root, *, data_home=None):
    """Missing/stale facts are evidence limitations, never a running-host assertion."""
    if data_home is None:
        data_home = (os.environ.get("LOCALAPPDATA") if os.name == "nt" else
                     Path.home() / "Library/Application Support" if sys.platform == "darwin" else
                     os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    if not data_home or not Path(data_home).is_absolute():
        return {"status": "unavailable"}
    key = hashlib.sha256(os.fsencode(os.path.normcase(str(Path(root).resolve(strict=True))))).hexdigest()
    directory = Path(data_home) / "CostGuard/Web" / key
    result = {"status": "not_observed", "lifecycle_codes": {}, "snapshot": None}
    try:
        value = _snapshot(json.loads(_read(directory / "diagnostics.json", 4096)))
        result.update(status="recorded", snapshot=value,
                      age_seconds=max(0, int(time.time()) - value["observed_at"]))
    except FileNotFoundError:
        pass
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        result["status"] = "unavailable"
    try:
        counts = Counter()
        for line in _read(directory / "lifecycle.log", 65536).decode("ascii").splitlines():
            fields = line.split()
            if len(fields) == 2 and fields[0].isdigit() and fields[1] in CODES:
                counts[fields[1]] = min(1_000_000, counts[fields[1]] + 1)
        result["lifecycle_codes"] = dict(counts)
    except FileNotFoundError:
        pass
    except (OSError, ValueError, UnicodeError):
        result["lifecycle_status"] = "unavailable"
    result["action"] = "Use Beta launcher to restart; CLI remains independent. Recorded facts do not prove current readiness."
    return result
