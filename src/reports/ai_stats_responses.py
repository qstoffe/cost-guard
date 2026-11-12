"""Extract approximate response intervals from already acquired canonical snapshots."""
from collections.abc import Mapping

from src.analysis.ai_stats_responses import ResponseCall, call_key, sample
from src.analysis.active_hour import deduplicated_requests


def _explicit_tool_start(part):
    if part.kind != 'tool':
        return None
    if 'execution_started_at_ms' in part.data:
        return part.data['execution_started_at_ms']
    state = part.data.get('state')
    time = state.get('time') if isinstance(state, Mapping) else None
    # State execution start is native ran/start, not inherited part/message time.
    return time.get('start') if isinstance(time, Mapping) else None


def response_bounds(invocation, message):
    """Observed step pairs outrank message fallback; no prompt timing enters here."""
    left, right = invocation.created_at_ms, invocation.completed_at_ms
    if message is not None:
        steps = [p for p in message.parts if p.kind == 'step-finish' and isinstance(p.data.get('tokens'), Mapping)]
        part = next((p for p in steps if p.part_id == invocation.step_part_id), None)
        timing = part.data.get('observed_time', part.data.get('time')) if part else None
        if isinstance(timing, Mapping):
            start, end = timing.get('start', timing.get('created')), timing.get('end', timing.get('completed'))
            if type(start) is int and type(end) is int and 0 < start < end:
                return start, end, True
        if len(steps) > 1:
            return None
    if type(left) is not int or type(right) is not int or not 0 < left < right:
        return None
    return left, right, False


def response_duration(invocation, message):
    """Never multiply an inherited message interval by steps or include tool waits."""
    bounds = response_bounds(invocation, message)
    if bounds is None:
        return None
    left, right, independent = bounds
    if message is not None and not independent:
        # V2 Step.Streamed follows provider-stream drain, before awaiting tools.
        # Preserve actual stream/tool overlap; completion still owns period scope.
        streamed = message.metadata.get('streamed_at_ms')
        if type(streamed) is int and left < streamed <= right:
            return streamed - left
        # A response that requested tools can finish its message after the tools.
        # Legacy fallback: clip only explicit execution, never tool creation.
        ends = [at for p in message.parts if type(at := _explicit_tool_start(p)) is int
                and type(left) is int and left < at and (right is None or at <= right)]
        if ends and right is not None:
            right = min(right, min(ends))
    return right - left


def encode_responses(bundle, snapshot, now):
    messages = {(m.session_id, m.message_id): m for m in snapshot.messages}
    invocations = {(r.session_id, r.message_id, r.step_part_id): r for r in snapshot.invocations}
    entries = deduplicated_requests(bundle.trace_entries)
    future = min((e.completed_at_ms for e in entries if e.completed_at_ms > now), default=None)

    def candidates():
        for entry in entries:
            if entry.completed_at_ms > now:
                continue
            request = invocations.get((entry.session_id, entry.message_id, entry.step_part_id))
            if request is None:
                continue
            duration = response_duration(request, messages.get((entry.session_id, entry.message_id)))
            if duration is not None:
                yield ResponseCall(entry, duration)

    indices = {call_key(e): i for i, e in enumerate(bundle.trace_entries)}
    return dict(as_of=now, next_completion=future,
                calls=[(indices[call_key(c.entry)], c.duration_ms) for c in sample(candidates())])


def decode_responses(value, facts, now=None):
    as_of, following = value['as_of'], value['next_completion']
    if (type(as_of) is not int or following is not None and (type(following) is not int or following <= as_of)
            or now is not None and (now < as_of or following is not None and now >= following)):
        raise ValueError('response_sample_time_changed')
    calls, seen = [], set()
    for index, duration in value['calls']:
        if (type(index) is not int or not 0 <= index < len(facts) or index in seen
                or type(duration) is not int or duration <= 0 or facts[index][0].completed_at_ms > as_of):
            raise ValueError('invalid_response_sample')
        seen.add(index)
        calls.append(ResponseCall(facts[index][0], duration))
    bounded = sample(calls)
    if len(bounded) != len(calls):
        raise ValueError('invalid_response_sample')
    return bounded
