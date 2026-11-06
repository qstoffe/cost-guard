"""Revision-bracketed finite history work and compact durable continuation proof."""
from src.analysis.cache import dependency_signature
from src.domain.progress import WorkProgress
from src.domain.session_tree import root_by_session
from .history import session_catalog_revision


class HistoryContinuation(Exception):
    """The caller may resume only after separately receiving durable progress."""


class HistoryCheckpointError(Exception):
    """A managed history cannot safely save the next bounded step."""


def revisions(service, roots):
    if getattr(service, 'history_checkpoint', None) and len(roots) > 100_000:
        raise HistoryCheckpointError('history_resource_limit')
    ids = tuple(root.session_id for root in roots)
    bulk = getattr(service.source, 'get_session_tree_revisions', None)
    return bulk(ids) if callable(bulk) else {sid: service.source.get_session_tree_revision(sid) for sid in ids}


def active_roots(sessions):
    ancestry = root_by_session(sessions)
    return {ancestry.get(session.session_id) for session in sessions if session.active is True}


class HistoryWork:
    def __init__(self, service, sessions, roots, versions, reference):
        if getattr(service, 'history_checkpoint', None) and len(roots) > 100_000:
            raise HistoryCheckpointError('history_resource_limit')
        self.service, self.sessions, self.roots, self.versions = service, sessions, roots, versions
        self.signature = dependency_signature((session_catalog_revision(service.selection.selected, sessions),
            sorted(versions.items()), service._dependencies(service._load_catalog()), reference.analysis_signature))
        self.saved = 0
        self.processed = 0

    def checkpoint(self, count, *, processed, remaining):
        """Count only successful stable writes, never analyzed/partial roots."""
        self.saved += count
        self.processed += processed
        callback = getattr(self.service, 'history_checkpoint', None)
        if callback and count:
            callback(dict(signature=self.signature, completed=self.saved, total=len(self.roots)))
        limit = getattr(self.service, 'history_slice_roots', None)
        if callback and limit and self.processed >= limit and remaining:
            if not count:
                raise HistoryCheckpointError('history_checkpoint_unavailable')
            raise HistoryContinuation()

    def verify(self, latest=None):
        if not getattr(self.service, 'shared_web_evidence', False):
            return set()
        from .service import SessionCatalogChangedError
        service = self.service
        service.progress(WorkProgress('Verifying complete history revisions', 'catalog', stage='history-verify'))
        latest = tuple(service.source.list_sessions()) if latest is None else latest
        if getattr(service, 'allow_partial_history', False):
            # Updates may be withheld; changed membership, ancestry, archive or
            # source identity must still invalidate the whole ordering/scope.
            def membership(values):
                return {(s.session_id, s.parent_session_id, s.created_at_ms, s.archived_at_ms,
                         s.provenance.source_type, s.provenance.source_generation,
                         s.provenance.source_instance) for s in values}
            if membership(latest) != membership(self.sessions):
                raise SessionCatalogChangedError('History membership changed during acquisition')
            current = revisions(service, self.roots)
            changed = {sid for sid, revision in self.versions.items() if current.get(sid) != revision}
            ancestry = root_by_session(self.sessions)
            prior = {s.session_id: s for s in self.sessions}
            changed.update(ancestry[s.session_id] for s in latest if s != prior[s.session_id])
            return changed
        if (session_catalog_revision(service.selection.selected, latest) !=
                session_catalog_revision(service.selection.selected, self.sessions)
                or revisions(service, self.roots) != self.versions):
            raise SessionCatalogChangedError('History changed during acquisition')
        return set()
