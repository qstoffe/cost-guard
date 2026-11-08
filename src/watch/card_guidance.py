"""One Watch-owned guidance observation; acquisition uses an existing card permit."""
from dataclasses import dataclass, replace
import sqlite3
from threading import Event
import time

from src.pricing.base import PricingUnavailableError
from src.reports.context_guidance import (GUIDANCE_TTL_MS, GuidanceObservation,
    complete_guidance, requalify_guidance)
from src.reports.context_sample import collect_context_sample
from src.sources.errors import SourceError
from .source_reads import SourceReads


class _ObsoleteGuidance(Exception):
    """Cancellation/dependency change, not a card source failure."""


@dataclass(slots=True)
class _Attempt:
    generation: int
    scope: object
    started_at_ms: int
    started_monotonic: float
    cancelled: Event
    reads: SourceReads
    future: object = None

    def cancel(self):
        self.cancelled.set()
        self.reads.cancel()  # This attempt only, never the other card sources.


class CardGuidance:
    def __init__(self, workers, service, *, binding, monotonic=time.monotonic):
        self.workers, self.service, self.binding = workers, service, binding
        self.monotonic = monotonic
        self.workers.defer_guidance = True
        self.key = object()  # Private accounting slot, not a source/session identity.
        self.current = None
        self.observation = None
        self.attempt = None
        self.generation = 0
        self.next_check = 0
        self.retry_at = 0
        self.failed = False
        self.stopping = False
        self.demand = False
        self.active_demand = False
        self.admission_order = 0
        self.last_wall_ms = None

    def _read_binding(self, service):
        try:
            return self.binding(service)
        except (SourceError, PricingUnavailableError, OSError, sqlite3.Error):
            return None

    def _invalidate(self):
        self.generation += 1
        self.observation = None
        if self.attempt is not None:
            self.attempt.cancel()

    def _valid_age(self, wall, monotonic, now_ms):
        return (0 <= now_ms - wall < GUIDANCE_TTL_MS and
            0 <= self.monotonic() - monotonic < GUIDANCE_TTL_MS / 1000)

    def _refresh(self):
        current = self._read_binding(self.service)
        old_scope = self.current.scope if self.current else None
        new_scope = current.scope if current else None
        if old_scope != new_scope:
            self._invalidate()
            self.retry_at = 0
            self.failed = current is None
        self.current = current
        self.next_check = self.monotonic() + 1

    def tick(self, cards, now_ms):
        if self.stopping:
            return
        if self.last_wall_ms is not None and now_ms < self.last_wall_ms:
            self._invalidate()  # Never resurrect an observation after clock rollback.
            self.retry_at = 0
        self.last_wall_ms = now_ms
        done = self.attempt is not None and self.attempt.future.done()
        if self.monotonic() >= self.next_check or done:
            self._refresh()
        if self.observation is not None and (now_ms < self.observation.started_at_ms or
                self.monotonic() < self.observation.started_monotonic):
            self._invalidate()
        if self.attempt is not None:
            attempt = self.attempt
            if now_ms < attempt.started_at_ms or self.monotonic() < attempt.started_monotonic:
                attempt.cancel()
            if done:
                value = attempt.future.result()  # Software defects retain the fatal boundary.
                if (not attempt.cancelled.is_set() and attempt.generation == self.generation and
                        self.current is not None and attempt.scope == self.current.scope):
                    if isinstance(value, GuidanceObservation):
                        self.observation, self.failed = value, False
                    else:
                        self.failed = True
                        self.retry_at = self.monotonic() + 5
                self.attempt = None
        self.demand = self.active_demand = False
        visible = set(cards._ranked_ids(now_ms))
        for key, entry in cards.sessions.items():
            active = bool(cards._focals(entry, now_ms)) or key in cards.active_candidates
            if not active and key not in visible:
                continue
            capture = entry.capture
            if capture is None or capture.context is None or entry.verified_generation != entry.generation:
                continue
            context = capture.context
            if (self.current is not None and context.source_epoch and
                    context.source_epoch != self.current.scope.source[2]):
                entry.capture = replace(capture, context=replace(context, multiplier=None,
                    cached_ccost=None, fresh_ccost=None, guidance_state='unavailable'))
                continue  # Old-epoch anchors cannot qualify a new service observation.
            if self.current is not None:
                context = requalify_guidance(context, self.current, self.service.config)
            if context.price_threshold:
                if self.current is not None and self.observation is not None:
                    context = complete_guidance(context, self.observation.mix,
                        self.current.reference_catalog, self.current.scope.semantics)
                    context = replace(context, guidance_sample_at_ms=self.observation.started_at_ms,
                        guidance_state='ready' if self._valid_age(self.observation.started_at_ms,
                            self.observation.started_monotonic, now_ms) else 'refreshing')
                else:
                    context = replace(context, multiplier=None,
                        guidance_state='unavailable' if self.failed or self.current is None else 'pending')
                self.demand = True
                self.active_demand |= active
            if context != capture.context:
                entry.capture = replace(capture, context=context)

    @property
    def pending(self):
        return (not self.stopping and self.demand and self.current is not None and
            (self.observation is None or not self._valid_age(self.observation.started_at_ms,
                self.observation.started_monotonic, self.last_wall_ms)) and
            self.attempt is None and self.monotonic() >= self.retry_at)

    def admit(self, now_ms):
        if not self.pending:
            return False
        # Always requalify immediately before admission, not just on the one-second cadence.
        self._refresh()
        if self.current is None:
            return False
        attempt = _Attempt(self.generation, self.current.scope, now_ms,
            self.monotonic(), Event(), SourceReads())
        future = self.workers.submit_guidance(self.key, lambda: self._produce(attempt))
        if future is None:
            return False
        attempt.future = future
        self.attempt = attempt
        return True

    def _produce(self, attempt):
        service = None
        def check():
            if attempt.cancelled.is_set() or self.workers.stopping.is_set():
                raise _ObsoleteGuidance()
            if service is not None:
                current = self._read_binding(service)
                if current is None or current.scope != attempt.scope:
                    raise _ObsoleteGuidance()
        try:
            check()
            service = self.workers.factory(attempt.started_at_ms)
            with attempt.reads.using(service.source):
                check()
                current = self._read_binding(service)
                if current is None or current.scope != attempt.scope:
                    raise _ObsoleteGuidance()
                # Pin exactly the local cache observation included in the binding.
                service.catalog = current.catalog
                service.comparison_pricing_catalog = current.reference_catalog
                roots, activity = service._ordered_roots(service.session_catalog())
                check()
                sample = collect_context_sample(service, roots, activity, check=check)
                check()
                return GuidanceObservation(attempt.scope, sample.mix,
                    attempt.started_at_ms, attempt.started_monotonic)
        except _ObsoleteGuidance:
            return None
        except (SourceError, PricingUnavailableError, OSError, sqlite3.Error):
            return None
        finally:
            if service is not None:
                service.close_accounts()

    def cancel(self):
        self.stopping = True
        self._invalidate()
