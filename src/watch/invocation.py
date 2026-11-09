"""Bounded Web-only invocation disclosure from already-owned canonical evidence.

No output, metadata, environment, content-bearing arguments or unknown fields
cross this boundary. Freeform allowlisted strings are screened, not guaranteed
secret-free; the UI explicitly describes omissions and this qualification.
"""
from collections.abc import Mapping
import hashlib
import json
import math
import re

from .models import ToolInvocation
from .tool_contracts import tool_input

MAX_INPUT_TEXT = 4096  # ASCII JSON characters; wire escaping is bounded to 2x.
_FIELDS = (
    "command", "code", "workdir", "cwd", "description", "background", "timeout",
    "pattern", "path", "include", "glob", "filePath", "offset", "limit",
    "literal", "caseSensitive", "hidden", "recursive", "maxResults",
)
# Do not forward arbitrary script bodies as `code`; only an observed shell command
# is displayable. Structured/nested parameters remain unavailable, not stringified.
_SENSITIVE = re.compile(
    r"password|passwd|secret|token|api[_-]?key|authorization|cookie|credential|"
    r"private[ _-]?key|-----BEGIN|\bbearer\s|\bredacted\b|\bmasked\b|"
    r"\b(?:sk-|gh[pousr]_|github_pat_|AKIA|ASIA|gsk_)[\w-]+|"
    r"\beyJ[\w-]+\.[\w-]+\.[\w-]+|(?:^|\s)(?:-u|--user)\s|"
    r"\b[A-Za-z_][\w:]*\s*=|https?://[^\s/]+:[^\s/]+@|"
    r"(?:--?env\b|\$env:|\bsetenv\b|\bexport\b)", re.I,
)
_UNAVAILABLE = "Invocation details unavailable from the current source."


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=True).encode()).hexdigest()


def invocation(part) -> ToolInvocation:
    """Copy only small, supported scalar input fields; never inspect huge values."""
    inputs = tool_input(part.data)
    safe = {}
    omitted = len(inputs) > len(_FIELDS) or any(key not in _FIELDS for key in inputs)
    for key in _FIELDS:
        if key not in inputs:
            continue
        value = inputs[key]
        supported = value is None or isinstance(value, (str, bool, int, float))
        if (key == "code" or not supported or
                isinstance(value, str) and (len(value) > MAX_INPUT_TEXT or _SENSITIVE.search(value)) or
                isinstance(value, int) and value.bit_length() > 64 or
                isinstance(value, float) and not math.isfinite(value)):
            omitted = True
            continue
        candidate = {**safe, key: value}
        if len(json.dumps(candidate, indent=2, ensure_ascii=True)) > MAX_INPUT_TEXT:
            omitted = True
            continue
        safe = candidate
    text = "\n\n".join(f"{key}:\n{value if isinstance(value, str) else json.dumps(value)}"
                         for key, value in safe.items())
    qualification = (_UNAVAILABLE if not inputs else
        "Limited source input: sensitive, unsupported or oversized fields omitted. Not the complete invocation."
        if omitted else "Observed source input (key/value formatting only).")
    if inputs and not safe:
        qualification = _UNAVAILABLE + " Sensitive, unsupported or oversized input withheld."
    origin = part.provenance
    call_id = part.data.get("callID")
    has_call = isinstance(call_id, str) and bool(call_id)
    physical = ("call", call_id) if has_call else ("part", part.part_id)
    identity = _digest((origin.source_type, origin.source_generation, origin.source_instance,
                        part.session_id, physical))
    revision = _digest((part.updated_at_ms, text, qualification))
    return ToolInvocation(identity, revision, text, qualification)


def background_invocation(snapshot, messages, parts):
    """One running job, one original physical call; never match by tool kind."""
    owners = {(message.session_id, message.message_id) for message in messages}
    jobs = [job for job in snapshot.background
            if job.running and (job.session_id, job.owner_message_id) in owners]
    if len(jobs) != 1:
        return None
    job = jobs[0]
    matched = [part for part in parts
               if part.session_id == job.session_id and part.message_id == job.owner_message_id
               and (part.data.get("callID") == job.tool_call_id if job.tool_call_id
                    else job.tool_part_id and part.part_id == job.tool_part_id)]
    return invocation(matched[0]) if len(matched) == 1 else None
