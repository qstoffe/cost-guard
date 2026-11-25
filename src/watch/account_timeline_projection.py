"""One owned process keeps archived Accounts CPU work off the Web interpreter."""
from dataclasses import dataclass
from multiprocessing import get_context
from pathlib import Path
import pickle
from threading import Event
from time import monotonic, thread_time
from types import SimpleNamespace

from src.cache.web_archive import WebArchive
from src.pricing.catalog import PricingCatalog
from src.process_ownership import run_owned
from src.reports.archived_usage import ArchivedUsage
from .account_timeline_archive import ArchivedAccountTimeline


MAX_REQUEST_BYTES = 16 * 1024 * 1024
MAX_RESULT_BYTES = 8 * 1024 * 1024
PROJECTION_DEADLINE_SECONDS = 30


class _ReadOnlyArchive(WebArchive):
    # The parent supplies its process-local invalidation token, not data or a
    # write capability. SQLite remains the authority for committed facts.
    revision = None

    def generation(self, domain):
        return self.revision

    def _open(self, *, write, check_same_thread=True):
        if write:
            raise RuntimeError('account_projection_read_only')
        return super()._open(write=False, check_same_thread=check_same_thread)


def _write(channel, value, limit):
    payload = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
    if len(payload) > limit:
        raise ValueError('account_projection_message_too_large')
    channel.send_bytes(payload)


def _read(channel, limit):
    # Only our spawned process and its exact owning parent hold the pipe ends.
    return pickle.loads(channel.recv_bytes(limit))


@dataclass(frozen=True, slots=True)
class _Request:
    sequence: int
    revision: int
    observation: object
    periods: tuple
    roster: tuple
    zone: str
    pricing: tuple
    migration_gap: object
    now: int
    progress: dict


@dataclass(frozen=True, slots=True)
class _Result:
    sequence: int
    revision: int
    cursor: int
    values: dict
    more: bool
    removed: bool
    initial: set
    pending: set
    cpu: float


def _pricing_input(catalog):
    if catalog is None:
        return None, None
    return catalog.diagnostic_signature, (
        catalog.models, catalog.retrieved_at_ms, catalog.source_revision,
        catalog.refresh_not_after_ms, catalog.reference_stale,
    )


def _observation_input(observation):
    if observation is None:
        return None
    # The archive projection needs only causal membership and activity bounds.
    sessions = tuple(SimpleNamespace(session_id=row.session_id, created_at_ms=row.created_at_ms,
                                     updated_at_ms=row.updated_at_ms, archived_at_ms=row.archived_at_ms)
                     for row in observation.sessions)
    return SimpleNamespace(sessions=sessions, root_by_session=dict(observation.root_by_session))


def _migration_gap_input(gap):
    if gap is None or not gap.has_gap:
        return None
    sessions = tuple(SimpleNamespace(first_ms=item.first_ms, last_ms=item.last_ms) for item in gap.sessions)
    return SimpleNamespace(has_gap=True, sessions=sessions)


def _project(channel, directory):
    archive = _ReadOnlyArchive(Path(directory))
    usage = ArchivedUsage(archive)
    projection = ArchivedAccountTimeline(usage)
    catalog, active_price = None, None
    with channel:
        while True:
            try:
                request = _read(channel, MAX_REQUEST_BYTES)
            except (EOFError, OSError):
                return
            archive.revision = request.revision
            try:
                started = thread_time()
                signature, rates = request.pricing
                if signature != active_price:
                    # Do not pickle the PricingCatalog's process-local lookup caches.
                    catalog = PricingCatalog(*rates) if rates is not None else None
                    if catalog is not None and catalog.diagnostic_signature != signature:
                        raise ValueError('account_projection_price_scope')
                    active_price = signature
                values, more, removed = projection.step(None, request.observation, request.periods, request.roster,
                    request.zone, catalog, lambda: catalog, request.migration_gap, request.now, **request.progress)
                result = _Result(request.sequence, request.revision, usage.cursor, values, more, removed,
                                 projection.initial_periods, projection.pending_periods, thread_time() - started)
                _write(channel, result, MAX_RESULT_BYTES)
            except (EOFError, OSError):
                return
            except Exception:
                # No source text, paths or exception payloads cross the pipe.
                _write(channel, None, MAX_RESULT_BYTES)
                return


class ArchivedAccountProjection:
    """Existing executor thread owns admission; Live still owns publication and shutdown."""
    def __init__(self, archive, *, context=None):
        self.directory = archive.path.parent
        self.context = context or get_context('spawn')
        self.stopping = Event()
        self.process = self.channel = None
        self.exit_unconfirmed = False
        self.sequence = 0
        self.revision, self.cursor = -1, -1
        self.initial_periods, self.pending_periods = set(), set()
        self.child_cpu = 0

    def _start(self):
        if self.exit_unconfirmed or self.stopping.is_set():
            raise RuntimeError('account_projection_not_available')
        parent, child = self.context.Pipe()
        process = self.context.Process(target=run_owned, args=(_project, child, str(self.directory)))
        try:
            process.start()
        except BaseException:
            parent.close()
            raise
        finally:
            child.close()
        self.process, self.channel = process, parent

    def step(self, scope, observation, periods, roster, zone, catalog, prices, migration_gap, now,
             *, archive_revision, **progress):
        if self.stopping.is_set() or self.exit_unconfirmed:
            raise RuntimeError('account_projection_stopping')
        if self.process is None:
            self._start()
        self.sequence += 1
        pricing = _pricing_input(prices() or catalog)
        request = _Request(self.sequence, archive_revision, _observation_input(observation),
                           tuple(periods), roster, zone, pricing, _migration_gap_input(migration_gap), now,
                           {key: progress[key] for key in ('unavailable_history', 'live_roots', 'pending_history',
                            'source_available', 'progress_roots') if key in progress})
        self.child_cpu = 0
        try:
            _write(self.channel, request, MAX_REQUEST_BYTES)
            deadline = monotonic() + PROJECTION_DEADLINE_SECONDS
            while not self.stopping.is_set() and monotonic() < deadline:
                if self.channel.poll(.1):
                    break
            else:
                raise RuntimeError('account_projection_interrupted')
            result = _read(self.channel, MAX_RESULT_BYTES)
            if (not isinstance(result, _Result) or self.stopping.is_set() or result.sequence != request.sequence
                    or result.revision != archive_revision or result.revision < self.revision):
                raise RuntimeError('account_projection_result_not_qualified')
        except Exception:
            self.close()
            raise
        # A coherent earlier generation may finish while newer facts are
        # committed. Its coverage describes its own snapshot, never the new one.
        self.child_cpu = result.cpu
        if result.cursor < self.cursor:
            # A restarted worker may need several bounded reads to catch up.
            self.initial_periods = self.pending_periods = set(periods)
            return {}, True, False
        self.revision, self.cursor = result.revision, result.cursor
        self.initial_periods, self.pending_periods = result.initial, result.pending
        return result.values, result.more, result.removed

    def stop(self):
        self.stopping.set()

    def close(self):
        if self.process is None:
            return
        self.channel.close()  # EOF requests ordinary exit without another send.
        process = self.process
        process.join(1)
        if process.is_alive():
            process.terminate()
            process.join(1)
        if process.is_alive():
            process.kill()
            process.join(1)
        if process.is_alive():
            self.exit_unconfirmed = True
            raise RuntimeError('account_projection_exit_unconfirmed')
        process.close()
        self.process = self.channel = None
