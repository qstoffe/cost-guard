"""Process-local request observations, independent of visible rows and quotas."""
from __future__ import annotations

from dataclasses import replace

from src.analysis.models import RootAnalysisBundle
from src.analysis.token_mix import (
    MIX_FIELDS, CategoryValuation, TokenMix, priceable_request, priced_token_mix, token_mix,
)
from src.domain import ModelRef, SessionSnapshot, TokenUsage


class WatchTokenMix:
    def __init__(self, started_at_ms: int) -> None:
        self.started_at_ms = started_at_ms
        # Message fallback and step-finish usage are alternate representations,
        # never additive. Keep observed steps when a later snapshot loses them.
        self._messages: dict[tuple[str | None, str, str], dict[str, tuple[TokenUsage, ModelRef]]] = {}
        self._stepped: set[tuple[str | None, str, str]] = set()
        # Initiating user prompt per observed request, for the prompt count.
        self._prompts: dict[tuple[tuple[str | None, str, str], str], tuple[str, str]] = {}
        self._projection = self._total = TokenMix()
        self._valuation: CategoryValuation | None = None
        self._dirty = False

    def observe(self, snapshot: SessionSnapshot, bundle: RootAnalysisBundle) -> None:
        active = {(entry.session_id, entry.message_id, entry.step_part_id)
                  for record in (*bundle.prompts, *bundle.compactions) if record.in_progress
                  for entry in record.entries}
        prompt_of = {(entry.session_id, entry.message_id, entry.step_part_id): (record.session_id, record.prompt_id)
                     for record in bundle.prompts for entry in record.entries}
        messages = {(m.session_id, m.message_id): m for m in snapshot.messages}
        for invocation in snapshot.invocations:
            key = (invocation.provenance.source_instance, invocation.session_id,
                   invocation.message_id or invocation.invocation_id)
            request = invocation.step_part_id or ""
            previous_item = self._messages.get(key, {}).get(request)
            previous = previous_item[0] if previous_item else None
            message = messages.get((invocation.session_id, invocation.message_id))
            termination = message.termination if message else None
            ended = invocation.completed_at_ms or (termination.completed_at_ms if termination else None)
            running = (ended is None and (invocation.session_id, invocation.message_id,
                                         invocation.step_part_id) in active)
            if (previous is None and invocation.created_at_ms < self.started_at_ms
                    and (ended is None or ended < self.started_at_ms) and not running):
                continue
            if not request and key in self._stepped:
                continue
            observed = self._messages.setdefault(key, {})
            if request and key not in self._stepped:
                observed.pop("", None)
                self._prompts.pop((key, ""), None)
                self._stepped.add(key)
            usage = invocation.tokens
            if previous is not None:
                # An incomplete refresh must not erase already-observed fields.
                usage = replace(usage, **{name: getattr(previous, name) for name in MIX_FIELDS
                                         if name not in usage.known_fields and name in previous.known_fields},
                                reasoning=previous.reasoning if "output" not in usage.known_fields else usage.reasoning,
                                known_fields=tuple(name for name in MIX_FIELDS
                                                   if name in usage.known_fields or name in previous.known_fields))
            item = (usage, invocation.model)
            if observed.get(request) != item:
                observed[request] = item
                self._dirty = True
            prompt = prompt_of.get((invocation.session_id, invocation.message_id, invocation.step_part_id))
            if prompt is not None and self._prompts.get((key, request)) != prompt:
                self._prompts[(key, request)] = prompt
                self._dirty = True

    def project(self, valuation: CategoryValuation | None = None) -> TokenMix:
        """Displayed Token Mix %: only this run's reference-priceable requests."""
        self._refresh(valuation)
        return self._projection

    def project_total(self, valuation: CategoryValuation | None = None) -> TokenMix:
        """Every observed run request, so Watch total CCost keeps its completeness."""
        self._refresh(valuation)
        return self._total

    def _refresh(self, valuation: CategoryValuation | None) -> None:
        # Countdown rendering must not rescan an ever-growing run's history.
        if not (self._dirty or valuation != self._valuation):
            return

        observed = tuple((key, request, usage, model) for key, requests in self._messages.items()
                         for request, (usage, model) in requests.items())
        prompts = len({self._prompts[(key, request)] for key, request, _usage, _model in observed
                       if (key, request) in self._prompts})
        if valuation is None:
            self._total = self._projection = token_mix((usage for *_ids, usage, _model in observed), sample_size=prompts)
        else:
            priced = tuple(item for item in observed if priceable_request(item[3], item[2], valuation))
            priced_prompts = len({self._prompts[(key, request)] for key, request, _usage, _model in priced
                                  if (key, request) in self._prompts})
            self._total = priced_token_mix(((model, usage) for *_ids, usage, model in observed),
                                           valuation, sample_size=prompts)
            self._projection = priced_token_mix(((model, usage) for *_ids, usage, model in priced),
                                                valuation, sample_size=priced_prompts)
        self._valuation = valuation
        self._dirty = False
