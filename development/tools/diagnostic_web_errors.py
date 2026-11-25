"""Read bounded, explicitly recognized fields from the managed Web error reporter."""
from collections import deque
import os
import re
import stat

_ERROR_FILE = r"cost-guard-errors-\d{4}-\d{2}-\d{2}\.log"
_CRASH_FILE = r"cost-guard-crash-\d{8}-\d{6}-\d{1,12}(?:-\d{1,3})?\.txt"
_IDENTIFIER = r"[A-Za-z_][A-Za-z_0-9]{0,79}"
_LOCATION = (r"(?:(?:src|development)(?:/[a-zA-Z0-9_.-]{1,64}){1,8}|<external>/[a-zA-Z0-9_.-]{1,80})"
             r":\d{1,8} in [a-zA-Z_0-9<>.-]{1,80}")
_SAFE_LINES = re.compile("|".join((
    r"Timestamp: \d{4}-\d\d-\d\dT[\d:.+-]{8,30}", r"Cost Guard: (?:v?\d{1,4}\.\d{1,4}|unknown)",
    r"Mode: Web", r"Phase: [a-zA-Z0-9_.-]{1,64}", r"Component: [a-zA-Z0-9_.-]{1,64}",
    r"Severity: (?:recoverable|fatal)", rf"Exception: {_IDENTIFIER}", rf"Location: (?:{_LOCATION}|<no frame>)",
    r"Fingerprint: [a-f0-9]{16}", r"Occurrence: \d{1,8}", r"Cache phase: (?:connect|pragma|read|write|commit)",
    r"SQLite(?: primary)? code: (?:\d{1,5}|unavailable)", r"(?:OS errno|Windows error): \d{1,10}",
    r"Repeated \d{1,10} additional times over \d{1,12}\.\d+s\.",
    r"Component (?:still degraded|later recovered)\.", r"Failure changed\.", r"Process execution ended\.",
    r"Chained exception:", r"Traceback \(most recent call last\):", rf"  {_LOCATION}",
    rf"{_IDENTIFIER}: \[message omitted for privacy\]",
)))


def _safe_stat(path):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("unsafe_path")
    return info


def read_bounded(path, limit, *, tail=False):
    for parent in path.parents:
        _safe_stat(parent)
    info = _safe_stat(path)
    if not stat.S_ISREG(info.st_mode) or (not tail and info.st_size > limit):
        raise ValueError("invalid_file")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError("changed_file")
        truncated = tail and opened.st_size > limit
        if truncated:
            stream.seek(opened.st_size - limit)
        data = stream.read(limit if tail else limit + 1)
    if truncated:
        _, _, data = data.partition(b"\n")
    if len(data) > limit:
        raise ValueError("oversize")
    return data


def _reports(path, pattern):
    for parent in (path, *path.parents):
        if not stat.S_ISDIR(_safe_stat(parent).st_mode):
            raise ValueError("invalid_directory")
    names = []
    partial = False
    with os.scandir(path) as entries:
        for index, entry in enumerate(entries):
            if index >= 512:
                partial = True
                break
            if re.fullmatch(pattern, entry.name):
                names.append(entry.name)
    reports = deque(maxlen=12)
    for name in sorted(names)[-3:]:
        try:
            text = read_bounded(path / name, 32 * 1024, tail=True).decode("utf-8", errors="replace")
            for episode in text.replace("\r\n", "\n").split("\n\n"):
                lines = [line for line in episode.splitlines() if len(line) <= 768 and _SAFE_LINES.fullmatch(line)]
                if lines and lines[0].startswith("Timestamp: "):
                    reports.append(lines[:80])
        except (OSError, ValueError):
            partial = True
    return {"status": "partial" if partial else "recorded" if reports else "not_observed",
            "reports": list(reports)}


def runtime_evidence(directory):
    result = {}
    for kind, pattern in (("errors", _ERROR_FILE), ("crashes", _CRASH_FILE)):
        try:
            result[kind] = _reports(directory / "logs" / kind, pattern)
        except FileNotFoundError:
            result[kind] = {"status": "not_observed"}
        except (OSError, ValueError) as exc:
            result[kind] = {"status": "unavailable", "exception_type": type(exc).__name__}
    return result
