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
        self._source = ""
        self._epoch = ""

    def bind(self, source, epoch):
        if bool(source) != bool(epoch):
            raise ValueError("incomplete_archive_binding")
        with self._lock:
            self._source, self._epoch = source, epoch

    def admit(self, revisions):
        if len(revisions) > BATCH_LIMIT or any(not session_id or not revision for session_id, revision in revisions.items()):
            raise ValueError("invalid_archive_admission")
        with self._lock:
            if not self._source:
                return None
            state = self.history.source_state(self._source)
            previous = self.history.session_revisions(self._source, tuple(revisions))
            return ArchiveAdmission(self._source, self._epoch, state.archive_epoch, tuple(
                SessionPublication(session_id, revision, self._epoch, previous.get(session_id))
                for session_id, revision in revisions.items()))

    def commit(self, admission, rows, current_revisions, *, missing=()):
        """Publish compact facts and notify only after the SQLite commit succeeded."""
        with self._lock:
            if (admission.source, admission.epoch) != (self._source, self._epoch):
                return None
            updates, absent = [], []
            for proof in admission.facts:
                session_id = proof.session_id
                if session_id in rows:
                    row = proof.project(rows[session_id], current_revision=current_revisions.get(session_id),
                                        current_epoch=self._epoch)
                    if row is not None:
                        updates.append(row)
                elif session_id in missing and session_id not in current_revisions and proof.archived_revision:
                    absent.append((session_id, proof.archived_revision))
            return self._commit(admission, tuple(updates), tuple(absent))

    def publish_catalog(self, admission, titles, current_revisions):
        """Store only metadata for newly discovered roots; never reset known facts."""
        with self._lock:
            if (admission.source, admission.epoch) != (self._source, self._epoch):
                return None
            updates = tuple(SessionChange(SessionFact(proof.session_id, proof.source_revision, titles[proof.session_id]),
                                   None, frozenset()) for proof in admission.facts
                            if proof.archived_revision is None and proof.session_id in titles
                            and current_revisions.get(proof.session_id) == proof.source_revision)
            return self._commit(admission, updates)

    def _commit(self, admission, updates, missing=()):
        generation = self.history.commit_sessions(admission.source, updates, missing=missing,
                                                  archive_epoch=admission.archive_epoch)
        if generation is not None:
            self.publish("cache", {"view": "sessions", "binding": admission.epoch, "generation": generation})
        return generation
