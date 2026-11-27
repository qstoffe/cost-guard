"""SessionCatalog prompt admission and same-prompt terminal handoff."""
from dataclasses import dataclass, replace

from src.domain.models import ONGOING_EVIDENCE_GRACE_MS, OngoingStatus

PROMPT_FRESHNESS_MS = ONGOING_EVIDENCE_GRACE_MS


@dataclass(frozen=True, slots=True)
class PromptEvidence:
    observed_ms: int
    prompt_id: str
    start_ms: int
    running: bool
    finish_ms: int | None
    ended: bool = False
    revision: str | None = None
    outcome: str | None = None
    ongoing: OngoingStatus | None = None
    watch_finish_ms: int | None = None

    @property
    def identity(self):
        return self.start_ms, self.prompt_id


@dataclass(frozen=True, slots=True)
class PromptHandoff:
    identity: tuple[int, str]
    observed_ms: int
    outcome: str | None
    watch_finish_ms: int | None = None

    @property
    def transition(self):
        return self.identity, self.observed_ms


def _record_handoff(catalog, key, evidence, previous, was_running):
    if evidence.running:
        catalog.terminal_handoffs.pop(key, None)
        catalog.finalize_roots.discard(key)
        if previous is None or previous.identity != evidence.identity:
            catalog.report_live_costs.pop(key, None)
    elif was_running and previous.identity == evidence.identity:
        catalog.terminal_handoffs[key] = PromptHandoff(
            evidence.identity, evidence.observed_ms, evidence.outcome, evidence.watch_finish_ms)
    elif (handoff := catalog.terminal_handoffs.get(key)) is not None:
        if handoff.identity == evidence.identity:
            catalog.terminal_handoffs[key] = replace(handoff, outcome=handoff.outcome or evidence.outcome,
                watch_finish_ms=evidence.watch_finish_ms or handoff.watch_finish_ms)


def observe_prompt_ends(catalog, observations):
    """Accept the end and Watch order clock for the same prompt and source."""
    with catalog.lock:
        if catalog.state != 'observed':
            return
        now = catalog.clock_ms()
        changed = set()
        for root, revision, at, ended, epoch in observations:
            key = root.session_id
            previous = catalog.prompt_activity.get(key)
            if (previous is None or previous.identity not in ended
                    or root.provenance != catalog.roots[key].provenance
                    or epoch != catalog.last_observation.source_epoch
                    or revision != catalog.revisions.get(key) or not 0 <= now - at <= PROMPT_FRESHNESS_MS):
                continue
            if key not in catalog.running_roots and key not in catalog.terminal_handoffs:
                continue
            terminal = ended[previous.identity]
            record_prompt(catalog, key, PromptEvidence(at, previous.prompt_id, previous.start_ms,
                False, None, ended=True, revision=revision, outcome=terminal.outcome,
                watch_finish_ms=terminal.watch_finish_ms), wake=True)
            changed.add(key)
        if catalog.archive is not None and changed:
            catalog._publish_report_runtime(changed)


def record_prompt(catalog, key, evidence, *, wake=False):
    now = catalog.clock_ms()
    if (catalog.roots[key].archived_at_ms is not None or not isinstance(evidence.prompt_id, str)
            or not catalog.lifecycle_cutoff_ms < evidence.observed_ms <= now
            or not evidence.prompt_id or type(evidence.start_ms) is not int
            or not 0 < evidence.start_ms <= now
            or evidence.finish_ms is not None and not evidence.start_ms <= evidence.finish_ms <= now):
        return
    previous = catalog.prompt_activity.get(key)
    was_running = catalog._running(key)
    if evidence.finish_ms is not None:
        evidence = replace(evidence, ended=True)
    if (evidence.watch_finish_ms is not None
            and not evidence.start_ms <= evidence.watch_finish_ms <= now):
        evidence = replace(evidence, watch_finish_ms=None)
    if not evidence.running and not evidence.ended:
        return
    if previous is None:
        if not evidence.running:
            return  # Ordinary history belongs to the scalar index.
    else:
        # An older prompt can still own active background work. Only a
        # newer qualified positive can move the focal identity backward.
        if (evidence.observed_ms < previous.observed_ms
                or evidence.identity < previous.identity
                and (not evidence.running or evidence.observed_ms == previous.observed_ms)):
            return
        if evidence.prompt_id == previous.prompt_id:
            if (evidence.start_ms != previous.start_ms or (evidence.running and previous.finish_ms is not None
                    and (evidence.revision == previous.revision or not wake))
                    or evidence.observed_ms == previous.observed_ms and evidence.running):
                return
            if evidence.ended and evidence.finish_ms is None and previous.finish_ms is not None:
                evidence = replace(evidence, finish_ms=previous.finish_ms, revision=previous.revision)
            if evidence.ended and evidence.watch_finish_ms is None:
                evidence = replace(evidence, watch_finish_ms=previous.watch_finish_ms)
    previous_finish = catalog.recent_finishes.get(key)
    if evidence.running or evidence.finish_ms is not None:
        catalog.recent_finishes.pop(key, None)
    elif was_running:
        # Sort/membership hint only, never a displayed or durable finish.
        catalog.recent_finishes[key] = evidence.observed_ms
    elif previous is not None and previous.identity != evidence.identity:
        catalog.recent_finishes.pop(key, None)
    catalog.prompt_activity[key] = evidence
    if catalog.archive is not None:
        _record_handoff(catalog, key, evidence, previous, was_running)
    if evidence.running:
        catalog.running_roots.add(key)
        if catalog.archive is not None:
            catalog.live_owned.add(key)
        catalog.history_queue.remove(key)
        if wake and (not was_running or previous is not None and previous.identity != evidence.identity):
            catalog.urgent_takeover.add(key)
    else:
        catalog.running_roots.discard(key)
        catalog.urgent_takeover.discard(key)
        if catalog.archive is not None and was_running and evidence.ended:
            catalog.finalize_roots.add(key)
            catalog.history_queue.remove(key)
            if wake:
                catalog.urgent_takeover.add(key)
    if catalog.archive is not None and (was_running != evidence.running
            or previous_finish != catalog.recent_finishes.get(key)):
        catalog.generation += 1
    if wake and (previous is None or was_running != evidence.running or previous.identity != evidence.identity
                 or previous.finish_ms != evidence.finish_ms):
        catalog.wake_revision += 1
