"""Single source-qualified Sessions publication owner."""
from dataclasses import dataclass
from threading import Lock

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

    def bind(self, source, epoch, *, announce=False):
        if bool(source) != bool(epoch):
            raise ValueError("incomplete_archive_binding")
        # Live revocation must not wait on a SQLite write. Admissions carry
        # an immutable incarnation; a detached partition is never exposed.
        with self._signal:
            self._binding = (source, epoch)
            if announce:
                self.publish("cache", {"view": "sessions", "binding": epoch or None})

    def admit(self, revisions, *, binding=None):
        if len(revisions) > BATCH_LIMIT or any(not session_id or not revision for session_id, revision in revisions.items()):
            raise ValueError("invalid_archive_admission")
        with self._lock:
            source, epoch = self._binding
            if not source or binding is not None and (source, epoch) != binding:
                return None
            state = self.history.source_state(source)
            previous = self.history.session_checkpoints(source, tuple(revisions))
            return ArchiveAdmission(source, epoch, state.archive_epoch, tuple(
                SessionPublication(session_id, revision, epoch, previous.get(session_id))
                for session_id, revision in revisions.items()))

    def commit(self, admission, rows, current_revisions, *, missing=(), dependency=None):
        """Publish compact facts and notify only after the SQLite commit succeeded."""
        with self._lock:
            if (admission.source, admission.epoch) != self._binding:
                return None
            updates, absent = [], []
            for proof in admission.facts:
                session_id = proof.session_id
                if session_id in rows:
                    row = proof.project(rows[session_id], current_revision=current_revisions.get(session_id),
                                         current_epoch=admission.epoch, dependency=dependency)
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
        if generation is not None:
            with self._signal:
                if (admission.source, admission.epoch) == self._binding:
                    self.publish("cache", {"view": "sessions", "binding": admission.epoch, "generation": generation})
        return generation
