"""Single source-qualified Sessions publication owner."""
from dataclasses import dataclass, replace
from threading import Lock
import time

from src.cache.display_history import BATCH_LIMIT, SessionChange, SessionFact

from .session_archive_projection import SessionPublication


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

    def _commit(self, admission, updates, missing=(), present=()):
        generation = self.history.commit_sessions(admission.source, updates, missing=missing, present=present,
                                                    archive_epoch=admission.archive_epoch)
        self._announce(admission.source, admission.epoch, generation)
        return generation

    def commit_running(self, source, epoch, running, *, clear_fence):
        with self._lock:
            fence, cleared_ms, _ = self._clear_fence
            if (source, epoch) != self._binding or clear_fence != fence:
                return
            archive_epoch = self.history.source_state(source).archive_epoch
            fresh = tuple(item for item in running if item.observed_ms > cleared_ms)
            generation = self.history.replace_running(source, epoch, fresh, archive_epoch=archive_epoch)
            self._announce(source, epoch, generation)

    def commit_watch(self, source, epoch, observation, *, clear_fence):
        with self._lock:
            fence, cleared_ms, _ = self._clear_fence
            if (source, epoch) != self._binding or clear_fence != fence or observation.observed_ms <= cleared_ms:
                return
            if observation.daily is not None and observation.daily.observed_at_ms <= cleared_ms:
                observation = replace(observation, daily=None)
            archive_epoch = self.history.source_state(source).archive_epoch
            generation = self.history.replace_watch(source, epoch, observation, archive_epoch=archive_epoch)
            if generation is not None:
                with self._signal:
                    if (source, epoch) == self._binding:
                        self.publish("watch-cache", dict(binding=epoch, archive_epoch=archive_epoch,
                                                        generation=generation))

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
            self._announce(source, epoch, generation)

    def _announce(self, source, epoch, generation):
        if generation is not None:
            with self._signal:
                if (source, epoch) == self._binding:
                    self.publish("cache", {"view": "sessions", "binding": epoch, "generation": generation})
