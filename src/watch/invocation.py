"""Bounded Web-only invocation disclosure from already-owned canonical evidence.

No output, metadata, environment, content-bearing arguments or unknown fields
cross this boundary. Normal commands retain their source text; recognized secrets
are redacted or withheld with cause-specific qualifications.
"""
import hashlib
import json
import math
from decimal import Decimal

from .models import ToolInvocation
from .invocation_redaction import redact
from .tool_contracts import tool_input

MAX_INPUT_TEXT = 4096  # ASCII-escaped formatted text; wire escaping is bounded.
_FIELDS = (
    "command", "code", "workdir", "cwd", "description", "background", "timeout",
    "pattern", "path", "include", "glob", "filePath", "offset", "limit",
    "literal", "caseSensitive", "hidden", "recursive", "maxResults",
)
_SHELL = frozenset({'shell', 'bash', 'functions.shell', 'functions.bash'})
_SECRET_FIELDS = frozenset({'env', 'environment', 'headers', 'authorization', 'cookie',
                            'password', 'secret', 'token', 'api_key', 'apiKey', 'credentials'})


def _timeout(value, shell):
    if (not shell or isinstance(value, bool) or not isinstance(value, (int, float))
            or value <= 0):
        return str(value) if isinstance(value, str) else json.dumps(value)
    duration = Decimal(str(value))
    divisor, unit = (3600000, 'h') if duration >= 3600000 else (60000, 'min') if duration >= 60000 else (1000, 's')
    friendly = format(duration / divisor, '.6f').rstrip('0').rstrip('.')
    return f'{value} ms' + (f' ({friendly} {unit})' if Decimal(friendly) > 0 else '')


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=True).encode()).hexdigest()


def invocation(part) -> ToolInvocation:
    """Copy only small, supported scalar input fields; never inspect huge values."""
    inputs = tool_input(part.data)
    lines, reasons = [], []
    shell = str(part.data.get('tool') or part.data.get('name') or '').lower() in _SHELL
    if any(key in _SECRET_FIELDS for key in inputs):
        reasons.append('Environment/credential fields omitted.')
    if any(key not in _FIELDS and key not in _SECRET_FIELDS for key in inputs):
        reasons.append('Unsupported fields omitted.')
    if not inputs:
        reasons.append('No source input available.')
    elif shell and (not isinstance(inputs.get('command'), str) or not inputs['command']):
        reasons.append('No source command available.')
    for key in _FIELDS:
        if key not in inputs:
            continue
        value = inputs[key]
        supported = value is None or isinstance(value, (str, bool, int, float))
        if key == 'command' and (not isinstance(value, str) or not value):
            reasons.append('No source command available.')
            continue
        if key == 'code':
            reasons.append('Content/script body omitted.')
            continue
        if not supported:
            reasons.append('Structured input omitted.')
            continue
        if (isinstance(value, int) and value.bit_length() > 64 or
                isinstance(value, float) and not math.isfinite(value)):
            reasons.append('Unsupported numeric input omitted.')
            continue
        if isinstance(value, str):
            if len(value) > MAX_INPUT_TEXT:
                reasons.append('Oversized field omitted.')
                continue
            value, reason = redact(value)
            if reason:
                reasons.append(reason)
            if value is None:
                continue
        rendered = (_timeout(value, shell) if key == 'timeout' else
                    value if isinstance(value, str) else json.dumps(value))
        line = f'{key}:\n{rendered}'
        if len(json.dumps('\n\n'.join([*lines, line]), ensure_ascii=True)) > MAX_INPUT_TEXT:
            reasons.append('Oversized field omitted (display budget).')
            continue
        lines.append(line)
    text = '\n\n'.join(lines)
    qualification = ' '.join(dict.fromkeys(reasons))
    if reasons and inputs:
        qualification += ' Not the complete invocation.'
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
