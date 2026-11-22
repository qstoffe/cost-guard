"""Single source-qualified Sessions publication owner."""
from dataclasses import dataclass, replace
import re
from threading import Lock
import time

from src.cache.display_history import BATCH_LIMIT, SessionChange, SessionFact

from .session_archive_projection import SessionPublication

DETAIL_HINT_LIMIT = 16


@dataclass(frozen=True, slots=True)
class ArchiveAdmission:
    source: str
    epoch: str
    archive_epoch: int
    facts: tuple[SessionPublication, ...]


class SessionArchiveOwner:
    """Bind proven scope outside HTTP and serialize accepted SQLite publications.

    The acquisition caller supplies the actual accepted observation epoch and
    revisions. This owner never opens the source or accepts unbound work.
    """

    def __init__(self, history, publish):
        self.history = history
        self.publish = publish
        self._lock = Lock()
        self._signal = Lock()
        self._binding = ("", "")
        self._clear_fence = (0, 0, -1)

    @property
    def clear_fence(self):
        return self._clear_fence[0]

    def observation_fence(self, sequence):
        fence, _, cutoff = self._clear_fence
        return fence if sequence > cutoff else None

    def bind(self, source, epoch, *, announce=False):
        if bool(source) != bool(epoch):
            raise ValueError("incomplete_archive_binding")
        # Live revocation must not wait on a SQLite write. Admissions carry
        # an immutable incarnation; a detached partition is never exposed.
        with self._signal:
            self._binding = (source, epoch)
            if announce:
                self.publish("cache", {"view": "sessions", "binding": epoch or None})

    def admit(self, revisions, *, binding=None, clear_fence=None):
        if len(revisions) > BATCH_LIMIT or any(not session_id or not revision for session_id, revision in revisions.items()):
            raise ValueError("invalid_archive_admission")
        with self._lock:
            source, epoch = self._binding
            if (not source or binding is not None and (source, epoch) != binding
                    or clear_fence is not None and clear_fence != self.clear_fence):
                return None
            state = self.history.source_state(source)
            previous = self.history.session_checkpoints(source, tuple(revisions))
            return ArchiveAdmission(source, epoch, state.archive_epoch, tuple(
                SessionPublication(session_id, revision, epoch, previous.get(session_id))
                for session_id, revision in revisions.items()))

    def commit(self, admission, rows, current_revisions, *, missing=(), dependency=None, eligible=None, usage=None):
        """Publish compact facts and notify only after the SQLite commit succeeded."""
        with self._lock:
            if ((admission.source, admission.epoch) != self._binding
                    or eligible is not None and not eligible()):
                return None
            updates, absent = [], []
            for proof in admission.facts:
                session_id = proof.session_id
                if session_id in rows:
                    row = proof.project(rows[session_id], current_revision=current_revisions.get(session_id),
                                         current_epoch=admission.epoch, dependency=dependency,
                                         usage=usage if len(admission.facts) == 1 else None)
                    if row is not None:
                        updates.append(row)
                elif session_id in missing and session_id not in current_revisions and proof.checkpoint:
                    absent.append((session_id, proof.checkpoint))
            return self._commit(admission, tuple(updates), tuple(absent))

    def publish_catalog(self, admission, titles, current_revisions, *, activity=None):
        """Store only metadata for newly discovered roots; never reset known facts."""
        with self._lock:
            if (admission.source, admission.epoch) != self._binding:
                return None
            clocks = activity or {}
            updates = tuple(SessionChange(SessionFact(proof.session_id, proof.source_revision, titles[proof.session_id],
                                    catalog_activity_ms=clocks.get(proof.session_id)),
                                    None, frozenset({"catalog_activity_ms"})) for proof in admission.facts
                             if proof.checkpoint is None and proof.session_id in titles
                            and current_revisions.get(proof.session_id) == proof.source_revision)
            present = tuple((proof.session_id, proof.checkpoint) for proof in admission.facts
                             if proof.checkpoint and proof.checkpoint.revision == proof.source_revision
                            and current_revisions.get(proof.session_id) == proof.source_revision)
            return self._commit(admission, updates, present=present)

    def commit_summary(self, admission, row, revision, *, dependency, eligible, usage):
        binding = admission.source, admission.epoch

        def current():
            return (eligible is None or eligible()) and self._binding == binding

        with self._lock:
            if len(admission.facts) != 1 or not current():
                return False
            change = admission.facts[0].project(row, current_revision=revision, current_epoch=admission.epoch,
                                                dependency=dependency, usage=usage)
            if change is None:
                return False
            result = self.history.commit_summary(admission.source, change, archive_epoch=admission.archive_epoch,
                                                 eligible=current)
            self._announce(*binding, result.generation, detail_roots=result.detail_roots)
            return result.applied == 1

    def _commit(self, admission, updates, missing=(), present=()):
        result = self.history.commit_session_batch(admission.source, updates, missing=missing, present=present,
                                                   archive_epoch=admission.archive_epoch)
        self._announce(admission.source, admission.epoch, result.generation, detail_roots=result.detail_roots)
        return result.generation

    def commit_live(self, source, epoch, *, running=None, watch=None, clear_fence, eligible=lambda: True):
        def current():
            return (source, epoch) == self._binding and clear_fence == self.clear_fence and eligible()

        with self._lock:
            if not current():
                return False
            _, cleared_ms, _ = self._clear_fence
            archive_epoch = self.history.source_state(source).archive_epoch
            if cleared_ms:
                if running is not None:
                    running = tuple(item for item in running if item.observed_ms > cleared_ms)
                if watch is not None:
                    watch = _watch_after_clear(watch, cleared_ms)
            outcome = self.history.replace_live(source, epoch, running=running, watch=watch,
                                                archive_epoch=archive_epoch, eligible=current)
            if outcome is None:
                return False
            with self._signal:
                if not current():
                    return False
                self._announce_sessions(epoch, outcome.sessions_generation, detail_roots=())
                if outcome.watch_generation is not None:
                    self.publish("watch-cache", dict(binding=epoch, archive_epoch=archive_epoch,
                                                     generation=outcome.watch_generation))
            return True

    def commit_models(self, source, epoch, catalog, *, clear_fence, eligible):
        with self._lock:
            fence, cleared_ms, _ = self._clear_fence
            if ((source, epoch) != self._binding or clear_fence != fence
                    or catalog.observed_ms <= cleared_ms or not eligible()):
                return False
            archive_epoch = self.history.source_state(source).archive_epoch
            return self.history.publish_model_catalog(source, catalog, archive_epoch=archive_epoch,
                eligible=lambda: self._binding == (source, epoch) and eligible())

    def clear(self, source, epoch, expected, *, eligible, current_observation):
        """Serialize with both archive producers without holding the Live lock."""
        with self._lock:
            if (source, epoch) != self._binding or not eligible():
                return None
            state = self.history.clear_confirmed_sessions(source, expected)
            if state is not None:
                self._clear_fence = (self.clear_fence + 1, int(time.time() * 1000), current_observation())
                self._announce(source, epoch, state.generation)
            return state

    def publish_coverage(self, source, epoch, fence, proof, *, eligible, widen_only=False):
        with self._lock:
            if self._binding != (source, epoch) or self.clear_fence != fence or not eligible():
                return
            state = self.history.source_state(source)
            generation = self.history.publish_session_coverage(source, proof, archive_epoch=state.archive_epoch,
                                                               widen_only=widen_only)
            self._announce(source, epoch, generation, detail_roots=())

    def _announce(self, source, epoch, generation, *, detail_roots=None):
        if generation is not None:
            with self._signal:
                if (source, epoch) == self._binding:
                    self._announce_sessions(epoch, generation, detail_roots=detail_roots)

    def _announce_sessions(self, epoch, generation, *, detail_roots):
        if generation is None:
            return
        hint = {"view": "sessions", "binding": epoch, "generation": generation}
        if detail_roots is not None and len(detail_roots) <= DETAIL_HINT_LIMIT:
            # Only routable IDs; no titles, fields or unbounded payload.
            hint["detail_roots"] = sorted(root for root in detail_roots
                                          if re.fullmatch(r"[A-Za-z0-9_-]{1,200}", root))
        self.publish("cache", hint)


def _watch_after_clear(watch, cleared_ms):
    facts = watch.facts if watch.observed_ms > cleared_ms else None
    if facts is not None:
        facts = tuple(
            replace(fact, qualified_ms=None, outcome="unverified", prompt_duration_ms=None, context_delta_tokens=None)
            if fact.outcome == "running" and (fact.qualified_ms is None or fact.qualified_ms <= cleared_ms) else fact
            for fact in facts)
    daily = watch.daily
    if daily is not None and daily.observed_at_ms <= cleared_ms:
        daily = None
    quotas = watch.quotas
    if quotas is not None:
        quotas = replace(quotas, facts=tuple(fact for fact in quotas.facts if fact.observed_ms > cleared_ms))
    if facts is None and daily is None and quotas is None:
        return None
    return replace(watch, facts=facts, daily=daily, quotas=quotas)
