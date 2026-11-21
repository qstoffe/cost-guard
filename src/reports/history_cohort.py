"""Disposable finite-observation manifests; never a source ledger or snapshot store."""
import json
import sqlite3

from src.analysis.cache import dependency_signature
from src.domain.session_tree import root_by_session
from .history_work import HistoryCheckpointError

NAMESPACE = 'history-cohort-1'
TRANSIENT = 'token-mix-transient-1'
MAX_ROOTS = 100_000
MAX_BYTES = 16 * 1024 * 1024


def structure(sessions):
    ancestry = root_by_session(sessions)
    groups = {}
    for session in sessions:
        p = session.provenance
        groups.setdefault(ancestry[session.session_id], []).append((
            session.session_id, session.parent_session_id, session.created_at_ms,
            session.archived_at_ms, p.source_type, p.source_generation, p.source_instance))
    return {sid: dependency_signature(sorted(rows)) for sid, rows in groups.items()}


def identity(service):
    return (service.selection.selected, getattr(service.source, 'source_instance', None),
            getattr(service.source, 'source_id', None))


class HistoryCohort:
    def __init__(self, service, scan, sessions, roots, versions, reference, *, period=None):
        self.service = service
        self.identity = identity(service)
        self.key = dependency_signature((NAMESPACE, scan))
        self.binding = dependency_signature((identity(service), service.now_ms, service.timezone_id, period,
            service._dependencies(service._load_catalog()), reference.analysis_signature,
            service.config, service.selection.warnings, service.selection.migration_gap))
        members = structure(sessions)
        self.omitted = set()
        self.versions = versions
        if len(roots) > MAX_ROOTS:
            raise HistoryCheckpointError('history_resource_limit')
        try:
            saved = service.cache_repository.get(NAMESPACE, self.key, busy_timeout_ms=50)
            if saved is None:
                if getattr(service, 'history_resuming', False):
                    raise HistoryCheckpointError('history_checkpoint_unavailable')
                self.value = dict(binding=self.binding, identity=list(self.identity), roots={
                    root.session_id: [versions[root.session_id], members[root.session_id],
                        [root.provenance.source_type, root.provenance.source_generation, root.provenance.source_instance]]
                    for root in roots}, omitted=[])
                self.save()
            else:
                self.value = saved.payload
                if saved.algorithm_version != NAMESPACE:
                    raise HistoryCheckpointError('history_checkpoint_unavailable')
                self.validate()
                self.omitted = set(self.value['omitted'])
            self.roots = self.reconcile(sessions, roots, versions, members=members)
        except (OSError, sqlite3.Error) as error:
            self.failed(error)

    def validate(self):
        value = self.value
        if isinstance(value, dict) and 'identity' in value and value['identity'] != list(self.identity):
            raise HistoryCheckpointError('source_identity_changed')
        if (not isinstance(value, dict) or value.get('binding') != self.binding or value.get('identity') != list(self.identity)
                or not isinstance(value.get('roots'), dict) or len(value['roots']) > MAX_ROOTS
                or not isinstance(value.get('omitted'), list) or not all(isinstance(s, str) for s in value['omitted'])
                or not set(value['omitted']) <= value['roots'].keys()
                or any(not isinstance(sid, str) or not isinstance(row, list) or len(row) != 3
                    or not isinstance(row[1], str) or len(row[1]) != 64
                    or not isinstance(row[2], list) or len(row[2]) != 3 for sid, row in value['roots'].items())):
            raise HistoryCheckpointError('history_checkpoint_unavailable')

    @property
    def total(self):
        return len(self.value['roots'])

    @property
    def signature(self):
        return dependency_signature((self.binding, self.value['roots']))

    def reconcile(self, sessions, roots, versions, *, members=None):
        if identity(self.service) != self.identity:
            raise HistoryCheckpointError('source_identity_changed')
        if members is None:
            members = structure(sessions)
        current = {r.session_id: r for r in roots}
        omitted = set()
        for sid, (revision, membership, provenance) in self.value['roots'].items():
            root = current.get(sid)
            if root and [root.provenance.source_type, root.provenance.source_generation,
                         root.provenance.source_instance] != provenance:
                raise HistoryCheckpointError('source_identity_changed')
            if (root is None or not isinstance(revision, str) or not revision
                    or versions.get(sid) != revision or members.get(sid) != membership):
                omitted.add(sid)
        self.omit(omitted)
        return [current[sid] for sid in self.value['roots'] if sid not in self.omitted]

    def accepts(self, snapshot):
        row = self.value['roots'].get(snapshot.root.session_id)
        return (row is not None and snapshot.source_revision == row[0]
                and structure(snapshot.sessions).get(snapshot.root.session_id) == row[1])

    def omit(self, ids):
        changed = set(ids) - self.omitted
        if changed:
            self.omitted.update(changed)
            self.save()

    def save(self):
        self.value['omitted'] = sorted(self.omitted)
        if len(json.dumps(self.value).encode()) > MAX_BYTES:
            raise HistoryCheckpointError('history_resource_limit')
        try:
            self.service.cache_repository.put(NAMESPACE, self.key, self.value,
                algorithm_version=NAMESPACE, busy_timeout_ms=50)
            # Bounded orphan cleanup at acquisition, not a new maintenance worker.
            with self.service.cache_repository.database.connect(operation='write', busy_timeout_ms=50) as connection:
                connection.execute("""DELETE FROM cache_entries WHERE rowid IN (
                    SELECT rowid FROM cache_entries WHERE namespace IN (?,?,?)
                    AND updated_at_utc < datetime('now','-1 day') LIMIT 256)""", (NAMESPACE, TRANSIENT, 'ai-stats-transient'))
                connection.execute("""DELETE FROM cache_entries WHERE rowid IN (
                    SELECT rowid FROM cache_entries WHERE namespace=? ORDER BY updated_at_utc DESC, rowid DESC
                    LIMIT 32 OFFSET 32)""", (NAMESPACE,))
        except (OSError, sqlite3.Error) as error:
            self.failed(error)

    @staticmethod
    def failed(error):
        code = getattr(error, 'sqlite_errorcode', None)
        busy = type(code) is int and code & 255 in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
        raise HistoryCheckpointError('history_checkpoint_busy' if busy else 'history_checkpoint_unavailable') from error
