"""Full Watch timing over one existing canonical capture; no reads or retained history."""
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import islice
import re
from statistics import median

from src.domain import TerminalOutcome
from .invocation_redaction import redact
from .models import ShellTiming
from .tool_contracts import tool_input

SHELL_TOOLS = frozenset({'shell', 'bash', 'functions.shell', 'functions.bash'})
MAX_HISTORY_PARTS = 256
MAX_HISTORY_MESSAGES = 128
MAX_HISTORY_JOBS = 256
MIN_SAMPLES = 2
_MAX_DATE_MS = 253402300799999  # Last millisecond in the supported local calendar.
_WORKLOAD_FIELDS = frozenset({'command', 'workdir', 'cwd', 'shell', 'description', 'background', 'timeout'})
_LAUNCHER_ONLY = re.compile(
    r"""(?ix)(?:^|[/\\])(?:py|python[\d.]*|pwsh|powershell|bash|sh|node|cmd)(?:\.exe)?["']?"""
    r"""(?:\s+[-/]\S+)*$""")


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _positive_ms(value):
    return value if type(value) in (int, float) and 0 < value <= _MAX_DATE_MS else None


def native_timeout(inputs):
    return _positive_ms(inputs.get('timeout'))


def _stamp(value):
    return int(_positive_ms(value) or 0)


def source_scope(origin):
    return origin.source_type, origin.source_generation, origin.source_instance


def shell_kind(part):
    return str(part.data.get('tool') or part.data.get('name') or '').lower()


def physical_key(part):
    if part.provenance.source_session_id not in (None, part.session_id):
        return None
    call = part.data.get('callID')
    if isinstance(call, str) and call:
        return (part.session_id, 'call', call)
    if part.part_id:
        return (part.session_id, 'part', part.part_id)
    return None


def _boundary(part, key):
    # Current V2 records the unmodified boundary before populating convenient
    # fallback times. Legacy/experimental state.time is itself source input.
    field = {'start': 'execution_started_at_ms', 'end': 'execution_ended_at_ms'}[key]
    if field in part.data:
        return _stamp(part.data[field])
    return _stamp(_mapping(_mapping(part.data.get('state')).get('time')).get(key))


def foreground_start(part):
    if start := _boundary(part, 'start'):
        return start, 'execution'
    if created := _stamp(_mapping(part.data.get('observed_time')).get('created')):
        return created, 'call_created'
    return 0, ''


def _workload(part, inputs, *, mode):
    kind = shell_kind(part)
    command = inputs.get('command')
    if (kind not in SHELL_TOOLS or not isinstance(command, str) or len(command) > 4096
            or len(command.split(None, 1)) < 2 or _LAUNCHER_ONLY.search(command.strip())
            or inputs.keys() - _WORKLOAD_FIELDS or redact(command)[1]):
        return None
    directories = [inputs[key] for key in ('workdir', 'cwd') if key in inputs]
    shell = inputs.get('shell', '')
    if (any(not isinstance(path, str) or len(path) > 1024 for path in directories)
            or len(directories) == 2 and directories[0] != directories[1]
            or not isinstance(shell, str) or len(shell) > 128):
        return None
    # Match verbatim invocation (including ordered arguments, quoting and
    # compound work), same session/workdir and same source/tool/mode. Never
    # normalize away a model, fixture, arm, wrapper or unknown execution field.
    return (part.session_id, kind, mode, command, directories[0] if directories else '', shell)


def _successful_foreground(part):
    state = _mapping(part.data.get('state'))
    metadata = _mapping(state.get('metadata'))
    return (state.get('status') == 'completed' and type(metadata.get('exit')) in (int, float)
            and metadata['exit'] == 0 and metadata.get('interrupted') is not True
            and str(metadata.get('status', '')).lower() not in
                {'error', 'timeout', 'timed_out', 'failed', 'cancelled', 'canceled', 'aborted', 'interrupted', 'killed'}
            and not state.get('error'))


def _part_job_key(job):
    if job.tool_call_id:
        return job.session_id, 'call', job.tool_call_id
    if job.tool_part_id:
        return job.session_id, 'part', job.tool_part_id
    return None


@dataclass(frozen=True, slots=True)
class _Sample:
    end: int
    duration: int


class ShellHistory:
    """Transient per-capture bounded samples, built only for a comparable live call."""

    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.samples = None

    def _collect(self):
        samples = defaultdict(list)
        snapshot = self.snapshot
        scope = source_scope(snapshot.root.provenance)
        if not snapshot.complete or not all(scope):
            return samples
        # Native snapshots already place messages in source-time order.
        recent = (part for message in islice(reversed(snapshot.messages), MAX_HISTORY_MESSAGES)
                  for part in reversed(message.parts))
        parts = [part for part in islice(recent, MAX_HISTORY_PARTS)
                 if part.kind == 'tool' and shell_kind(part) in SHELL_TOOLS]
        counts = Counter(physical_key(part) for part in parts)
        jobs = list(islice(reversed(snapshot.background), MAX_HISTORY_JOBS))
        job_counts = Counter(_part_job_key(job) for job in jobs)
        jobs = {_part_job_key(job): job for job in jobs}
        for part in parts:
            key = physical_key(part)
            if key is None or counts[key] != 1 or source_scope(part.provenance) != scope:
                continue
            inputs = tool_input(part.data)
            detached = inputs.get('background') is True or part.data.get('detached_job') is True
            if detached:
                job = jobs.get(key)
                if (job is None or job_counts[key] != 1 or job.running or not job.invocation_end_observed
                        or job.invocation_start_kind != 'execution' or job.outcome is not TerminalOutcome.SUCCESS
                        or job.owner_message_id != part.message_id or job.kind != shell_kind(part)
                        or job.tool_part_id and job.tool_part_id != part.part_id):
                    continue
                # Paired native shell completion event, not the return of the
                # launching tool. The notice may include delivery latency.
                start, end, mode = job.started_at_ms, job.ended_at_ms, 'background'
            else:
                if not _successful_foreground(part):
                    continue
                start, end, mode = _boundary(part, 'start'), _boundary(part, 'end'), 'foreground'
            timeout = native_timeout(inputs)
            if not start or not end or start >= end or timeout and end - start >= timeout:
                continue
            if workload := _workload(part, inputs, mode=mode):
                samples[workload].append(_Sample(end, end - start))
        return samples

    def timing(self, part, inputs, *, start, anchor, mode, comparable=True):
        timeout = native_timeout(inputs)
        if (part is None or not comparable or anchor != 'execution' or not physical_key(part)
                or not all(source_scope(part.provenance))
                or not (workload := _workload(part, inputs, mode=mode))):
            return ShellTiming(anchor, timeout)
        if self.samples is None:
            self.samples = self._collect()
        durations = [sample.duration for sample in self.samples.get(workload, ()) if sample.end <= start]
        count = len(durations)
        if count < MIN_SAMPLES:
            return ShellTiming(anchor, timeout, sample_count=count)
        # Round to a stable 30-second duration; never use the timeout as ETA.
        typical = max(30_000, int((median(durations) + 15_000) // 30_000) * 30_000)
        return ShellTiming(anchor, timeout, typical, count)
