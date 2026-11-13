"""Bounded Web-only invocation disclosure from already-owned canonical evidence.

No output, metadata, environment, content-bearing arguments or unknown fields
cross this boundary. Normal commands retain their source text; recognized secrets
are redacted or withheld with cause-specific qualifications.
"""
import hashlib
import json
import math
from collections.abc import Mapping
from decimal import Decimal
from dataclasses import replace

from .models import ToolFailure, ToolInvocation
from .invocation_redaction import redact
from .tool_contracts import tool_input

MAX_INPUT_TEXT = 4096  # ASCII-escaped formatted text; wire escaping is bounded.
MAX_INVOCATIONS = 5
MAX_FAILED_INVOCATIONS = 10  # One shared card budget, not ten per tool group.
_FIELDS = (
    "command", "code", "workdir", "cwd", "shell", "description", "background", "timeout",
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


def _format(inputs, shell, budget):
    """One privacy/size boundary for native parts and registry fallback alike."""
    lines, reasons = [], []
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
        if len(json.dumps('\n\n'.join([*lines, line]), ensure_ascii=True)) > budget:
            reasons.append('Oversized field omitted (display budget).')
            continue
        lines.append(line)
    text = '\n\n'.join(lines)
    qualification = ' '.join(dict.fromkeys(reasons))
    if reasons and inputs:
        qualification += ' Not the complete invocation.'
    return text, qualification


def invocation(part, *, budget=MAX_INPUT_TEXT) -> ToolInvocation:
    """Copy only small, supported scalar input fields; never inspect huge values."""
    kind = str(part.data.get('tool') or part.data.get('name') or '').lower()
    text, qualification = _format(tool_input(part.data), kind in _SHELL, budget)
    origin = part.provenance
    call_id = part.data.get("callID")
    has_call = isinstance(call_id, str) and bool(call_id)
    physical = ("call", call_id) if has_call else ("part", part.part_id)
    identity = _digest((origin.source_type, origin.source_generation, origin.source_instance,
                        part.session_id, physical))
    revision = _digest((part.updated_at_ms, text, qualification))
    return ToolInvocation(identity, revision, text, qualification, kind, part.created_at_ms)


def failed_invocations(parts, origin, *, budget=MAX_INPUT_TEXT):
    """Reuse the invocation filter, exporting only bounded, source-owned failures."""
    selected = parts[:MAX_FAILED_INVOCATIONS]
    details = []
    for name, part in selected:
        source = part.provenance
        if (source.source_type, source.source_generation, source.source_instance) != (
                origin.source_type, origin.source_generation, origin.source_instance):
            continue
        details.append(ToolFailure(name, invocation(part, budget=budget), _failure_reason(part)))
    return tuple(details)


def _failure_reason(part):
    # Never copy arbitrary error/output/stack text. Exact recognized codes or
    # whole fixed messages can qualify a short category; everything else is unknown.
    state = part.data.get("state")
    error = state.get("error") if isinstance(state, Mapping) else None
    values = [error] if isinstance(error, str) else (
        [error.get(key) for key in ("name", "type", "code")] if isinstance(error, Mapping) else [])
    reasons = set()
    for value in values:
        if not isinstance(value, str) or len(value) > 80:
            continue
        value = value.strip().lower()
        if value in {"enoent", "filenotfounderror", "file not found", "no such file or directory"}:
            reasons.add("File not found")
        elif value in {"eacces", "eperm", "permissionerror", "permission denied", "access denied"}:
            reasons.add("Permission denied")
    return next(iter(reasons)) if len(reasons) == 1 else "Failure reason unavailable"


def background_invocations(snapshot, messages, parts, *, other_count=0):
    """Separate live jobs using prompt-qualified origins, never kind/time guesses."""
    owners = {(message.session_id, message.message_id) for message in messages}
    jobs = {}
    for job in snapshot.background:
        if job.running and (job.session_id, job.owner_message_id) in owners:
            key = (job.session_id, job.activity_id)
            if key not in jobs:
                jobs[key] = job
            elif jobs[key] != job:
                jobs[key] = replace(job, tool_call_id='', tool_part_id='', invocation_input=(),
                                    invocation_reason='Conflicting job origins; command withheld.')
    ordered = sorted(jobs.values(), key=lambda job: (job.started_at_ms, job.session_id, job.activity_id))
    budget = MAX_INPUT_TEXT // max(1, min(len(ordered), MAX_INVOCATIONS) + other_count)
    details = []
    origin = snapshot.root.provenance
    for job in ordered[:MAX_INVOCATIONS]:
        matched = [part for part in parts if part.session_id == job.session_id
                   and part.message_id == job.owner_message_id
                   and (part.data.get('callID') == job.tool_call_id if job.tool_call_id
                        else job.tool_part_id and part.part_id == job.tool_part_id)]
        inputs = tool_input(matched[0].data) if len(matched) == 1 else {}
        fallback = dict(job.invocation_input)
        reason = job.invocation_reason
        native_command, registry_command = inputs.get('command'), fallback.get('command')
        if len(matched) == 1:
            part = matched[0]
            source = part.provenance
            if ((job.tool_part_id and part.part_id != job.tool_part_id)
                    or (source.source_type, source.source_generation, source.source_instance) !=
                       (origin.source_type, origin.source_generation, origin.source_instance)):
                reason = 'Conflicting source identity; command withheld.'
        command_mismatch = native_command and registry_command and native_command != registry_command
        if reason:
            text, qualification = '', reason
        elif command_mismatch:
            # Original input and the executed registry representation can differ
            # (e.g. runtime wrappers). Never guess equivalence or mix their fields.
            text, qualification = _format(inputs, job.kind in _SHELL, budget)
            qualification = ' '.join(filter(None, (qualification,
                'Original tool input shown; registry command differs. Registry details withheld; executed form not verified.')))
        elif len(matched) == 1 or fallback:
            # Registry fields are supplemental only after the adapter proves the
            # exact job + session + assistant-message join. Native input wins.
            combined = {**fallback, **inputs}
            if not inputs.get('command') and registry_command:
                combined['command'] = registry_command
            text, qualification = _format(combined, job.kind in _SHELL, budget)
        else:
            text, qualification = '', 'Original call link missing; only background activity is observable.'
        identity = _digest((origin.source_type, origin.source_generation, origin.source_instance,
                            job.session_id, 'background', job.activity_id))
        revision = _digest((job.owner_message_id, job.tool_part_id, job.tool_call_id,
                            text, qualification, job.started_at_ms))
        details.append(ToolInvocation(identity, revision, text, qualification, job.kind,
                                      job.started_at_ms, 'background'))
    return tuple(details), len(ordered)
