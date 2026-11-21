"""Current-host prompt evidence shared by the catalog and its archive lane."""
from dataclasses import dataclass, replace
from heapq import nsmallest

from src.cache.display_history import BATCH_LIMIT, RUNNING_FRESH_MS, RunningSession


@dataclass(frozen=True, slots=True)
class PromptEvidence:
    observed_ms: int
    prompt_id: str
    start_ms: int
    running: bool
    finish_ms: int | None
    ended: bool = False
    revision: str | None = None

    @property
    def identity(self):
        return self.start_ms, self.prompt_id


def observe_prompts(catalog, evidence):
    """Accept only current canonical Watch captures; omission is not a lifecycle event."""
    with catalog.lock:
        if catalog.state != "observed":
            return
        now = catalog.clock_ms()
        for root, revision, captured_at, prompt_id, start, running, finish, ended in evidence:
            key = root.session_id
            if (key not in catalog.roots or root.provenance != catalog.roots[key].provenance
                    or revision != catalog.revisions.get(key) or not 0 <= now - captured_at <= RUNNING_FRESH_MS):
                continue
            before = terminal_prompt(catalog, key)
            was_running = is_running(catalog, key)
            record_prompt(catalog, key, PromptEvidence(captured_at, prompt_id, start, running, finish, ended, revision),
                          wake=True)
            after = terminal_prompt(catalog, key)
            if catalog.display_archive is not None:
                if after is not None and before != after:
                    catalog._archive_priority(key)
                if before != after or was_running != is_running(catalog, key):
                    catalog._archive_prompt_changed(key, now)


def terminal_prompt(catalog, key):
    """Read the accepted stop hint under the catalog lock, not a verified finish."""
    prompt = catalog.prompt_activity.get(key)
    if (prompt is not None and prompt.ended and not prompt.running
            and prompt.revision == catalog.revisions.get(key) and prompt.observed_ms > catalog.lifecycle_cutoff_ms):
        return prompt.identity
    return None


def running_snapshot(catalog, evidence):
    """Only currently proven, same-revision starts from the shared observer."""
    with catalog.lock:
        if catalog.state != "observed" or catalog.interrupted:
            return ()
        recent = {}
        now = catalog.clock_ms()
        for root, revision, captured_at, prompt_id, start, running, _, _ in evidence:
            key = root.session_id
            if (not running or not revision or key not in catalog.roots or not is_running(catalog, key)
                    or root.provenance != catalog.roots[key].provenance
                    or (start, prompt_id) != catalog.prompt_activity[key].identity
                    or not 0 <= now - captured_at < RUNNING_FRESH_MS or not 0 < start <= captured_at
                    or revision != catalog.revisions.get(key)):
                continue
            recent[key] = RunningSession(key, root.title or "Untitled session", start, captured_at)
        return tuple(nsmallest(BATCH_LIMIT, recent.values(), key=lambda item: (-item.started_ms, item.session_id)))


def record_prompt(catalog, key, evidence, *, wake=False):
    """Reduce one ordered observation while the caller holds the catalog lock."""
    now = catalog.clock_ms()
    if (catalog.roots[key].archived_at_ms is not None or not isinstance(evidence.prompt_id, str)
            or not catalog.lifecycle_cutoff_ms < evidence.observed_ms <= now
            or not evidence.prompt_id or type(evidence.start_ms) is not int or not 0 < evidence.start_ms <= now
            or evidence.finish_ms is not None and not evidence.start_ms <= evidence.finish_ms <= now):
        return
    previous = catalog.prompt_activity.get(key)
    if evidence.finish_ms is not None:
        evidence = replace(evidence, ended=True)
    if previous is None:
        if not evidence.running:
            return  # Ordinary history belongs to the scalar index.
    else:
        if evidence.identity < previous.identity or evidence.observed_ms < previous.observed_ms:
            return
        if evidence.prompt_id == previous.prompt_id:
            if (evidence.start_ms != previous.start_ms or evidence.running and previous.ended
                    or not evidence.running and not evidence.ended
                    or evidence.observed_ms == previous.observed_ms and evidence.running):
                return
            if (evidence.ended and evidence.finish_ms is None and previous.finish_ms is not None
                    and evidence.revision == previous.revision and previous.observed_ms > catalog.lifecycle_cutoff_ms):
                evidence = replace(evidence, finish_ms=previous.finish_ms)
    catalog.prompt_activity[key] = evidence
    if evidence.running:
        catalog.running_roots.add(key)
    else:
        catalog.running_roots.discard(key)
    if wake and (previous is None or (previous.identity, previous.running, previous.finish_ms) !=
            (evidence.identity, evidence.running, evidence.finish_ms)):
        catalog.wake_revision += 1


def is_running(catalog, key):
    return (not catalog.interrupted and key in catalog.running_roots
            and catalog.prompt_activity[key].observed_ms > catalog.lifecycle_cutoff_ms)
