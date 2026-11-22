"""Current-host prompt evidence shared by the catalog and its archive lane."""
from dataclasses import dataclass, replace
from heapq import nsmallest

from src.cache.display_history import (
    BATCH_LIMIT, FINISH_FIELDS, RUNNING_FRESH_MS, FinishedSession, RunningSession, SessionFact,
)


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
            recent[key] = RunningSession(key, root.title or "Untitled session", start, captured_at, prompt_id)
        return tuple(nsmallest(BATCH_LIMIT, recent.values(), key=lambda item: (-item.started_ms, item.session_id)))


def archive_finish_snapshot(catalog, entries):
    """Freeze a bounded set of causal finishes and a catalog-revision commit guard."""
    with catalog.lock:
        if catalog.state != "observed" or catalog.interrupted:
            return (), lambda: False
        now, incarnation = catalog.clock_ms(), catalog.archive_incarnation
        candidates = {}
        for entry in entries:
            capture, snapshot = entry.capture, entry.snapshot
            if (capture is None or capture.catalog_finish is None or capture.retained
                    or not capture.authoritative or entry.verified_generation != entry.generation
                    or snapshot is None or not snapshot.complete or snapshot.source_revision != entry.revision
                    or entry.source_status.failed_at is not None):
                continue
            root, revision, observed = entry.root, entry.revision, capture.observed_at_ms
            key = root.session_id
            _, start, _, _ = capture.catalog_prompt
            finish, latest = capture.catalog_finish
            if (root.archived_at_ms is not None or not revision or revision != catalog.revisions.get(key)
                    or root != catalog.roots.get(key) or is_running(catalog, key)
                    or not (catalog.lifecycle_cutoff_ms < observed <= now
                            and now - observed < RUNNING_FRESH_MS and latest <= now)):
                continue
            fields = FINISH_FIELDS
            cost, context = entry.cost.value, capture.context
            ccost = None
            if (entry.cost.status == "observed" and cost is not None
                    and cost.source_complete and cost.total.complete):
                ccost = cost.total.known_ccost
                fields = fields | {"ccost"}
            tokens = None
            if context is not None and context.context_state in {"ready-current", "invalidated"}:
                tokens = context.tokens if context.context_state == "ready-current" else None
                fields = fields | {"context_tokens", "context_detail"}
            detail = "Estimated next incoming session context." if tokens is not None else None
            fact = SessionFact(key, revision, root.title or "Untitled session", activity_ms=finish,
                ccost=ccost, context_tokens=tokens, latest_activity_ms=latest, prompt_started_ms=start,
                activity_origin="finish", context_detail=detail)
            candidates[key] = FinishedSession(fact, observed, fields)
        finishes = tuple(nsmallest(BATCH_LIMIT, candidates.values(),
            key=lambda item: (-item.fact.activity_ms, item.fact.session_id)))
        roots = {item.fact.session_id: catalog.roots[item.fact.session_id] for item in finishes}

    def current():
        with catalog.lock:
            return (catalog.state == "observed" and not catalog.interrupted and
                    catalog.archive_incarnation == incarnation and all(
                        item.observed_ms > catalog.lifecycle_cutoff_ms
                        and item.fact.revision == catalog.revisions.get(item.fact.session_id)
                        and catalog.roots.get(item.fact.session_id) == roots[item.fact.session_id]
                        and not is_running(catalog, item.fact.session_id) for item in finishes))

    return finishes, current


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
