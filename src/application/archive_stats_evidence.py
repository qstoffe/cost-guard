"""Extract Stats-specific source evidence within the existing root capture."""
from src.cache.display_stats_evidence import ResponseTiming, StatsCapture, StatsInterval, StatsMatch
from src.reports.ai_stats_responses import response_interval
from src.reports.matched_runs import matched_execution_status, matched_input


def _request_identity(item):
    return item.session_id, item.message_id, item.step_part_id


class StatsResponses:
    def __init__(self, snapshot):
        self.messages = {(m.session_id, m.message_id): m for m in snapshot.messages}
        self.invocations = {_request_identity(invocation): invocation for invocation in snapshot.invocations}

    def observation(self, entry):
        if entry.completed_at_ms <= 0:
            return None
        if entry.error_name or entry.finish_reason in ("error", "aborted"):
            return ResponseTiming(excluded=True)
        invocation = self.invocations.get(_request_identity(entry))
        if invocation is None:
            return None
        interval = response_interval(invocation, self.messages.get((entry.session_id, entry.message_id)))
        if interval is None or sum(interval) > entry.completed_at_ms:
            return None
        return ResponseTiming(*interval)


def _match(snapshot, bundle):
    observed = matched_input(snapshot, bundle)
    if observed is None:
        return None
    fingerprint, prompt = observed
    if prompt.prompt_time_ms <= 0:
        return None
    status = matched_execution_status(prompt)
    return StatsMatch(prompt.prompt_id, bytes.fromhex(fingerprint), prompt.prompt_time_ms,
                      prompt.execution_duration_ms if status != "running" else None,
                      "unverified" if status == "running" else status)


def stats_capture(snapshot, bundle):
    intervals = tuple(
        StatsInterval(prompt.session_id, prompt.prompt_id, "prompt", prompt.prompt_time_ms or None,
                      prompt.execution_duration_ms, prompt.in_progress)
        for prompt in bundle.prompts)
    intervals += tuple(
        StatsInterval(compaction.session_id, compaction.user_message_id, "compaction", compaction.created_at_ms or None,
                      compaction.duration_ms, compaction.in_progress)
        for compaction in bundle.compactions)
    return StatsCapture(intervals, any(p.in_progress and not p.entries for p in bundle.prompts),
                        _match(snapshot, bundle), tuple((s.session_id, s.parent_session_id) for s in snapshot.sessions))
