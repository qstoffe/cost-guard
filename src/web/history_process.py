"""Isolate the decoded report archive from the Live and HTTP interpreter."""
from multiprocessing import get_context
from pathlib import Path
import pickle
from threading import Event, Lock
from time import monotonic, thread_time
from types import SimpleNamespace

from src.cache.web_archive import WebArchive
from src.pricing.catalog import PricingCatalog
from src.process_ownership import run_owned
from src.reports.archived_usage import ArchivedUsage

from .history_projection import HistoryProjection
from .watch_history import watch_daily_usage


MAX_REQUEST_BYTES = 16 * 1024 * 1024
MAX_RESULT_BYTES = 32 * 1024 * 1024
PROJECTION_DEADLINE_SECONDS = 30


class _ProjectionArchive(WebArchive):
    revision = None

    def generation(self, domain):
        return self.revision

    def _open(self, *, write, check_same_thread=True, snapshot=True):
        if write:
            raise RuntimeError('history_projection_read_only')
        return super()._open(write=False, check_same_thread=check_same_thread, snapshot=snapshot)


def _message(value, limit):
    data = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
    return data if len(data) <= limit else None


def _receive(channel, limit):
    # The exact owning parent and spawned child are the only pipe endpoints.
    return pickle.loads(channel.recv_bytes(limit))


def _work(channel, directory):
    archive = _ProjectionArchive(Path(directory))
    usage = ArchivedUsage(archive, retain_account_entries=False)
    projection = HistoryProjection(usage)
    with channel:
        while True:
            try:
                sequence, kind, revision, signature, pricing, inputs = _receive(channel, MAX_REQUEST_BYTES)
            except (EOFError, OSError):
                return
            archive.revision = revision
            try:
                started = thread_time()
                reference = PricingCatalog(*pricing)
                if reference.diagnostic_signature != signature:
                    raise ValueError('history_projection_price_scope')
                snapshot = usage.snapshot()
                if kind == 'reports':
                    views, more = projection.render(reference=reference, snapshot=snapshot, **inputs)
                    result = views, more, snapshot[0], projection.next_clock_change(inputs['now'])
                else:
                    result = watch_daily_usage(snapshot[1], reference, **inputs), snapshot[2]
                payload = _message((sequence, revision, result, thread_time() - started), MAX_RESULT_BYTES)
            except Exception:
                payload = None
            try:
                channel.send_bytes(payload or _message((sequence, revision, None, 0), MAX_RESULT_BYTES))
            except (EOFError, OSError):
                return


def _selection_input(selection):
    gap = selection.migration_gap
    if gap and gap.has_gap:
        gap = SimpleNamespace(has_gap=True, sessions=tuple(
            SimpleNamespace(first_ms=item.first_ms, last_ms=item.last_ms) for item in gap.sessions))
    else:
        gap = None
    return SimpleNamespace(selected=selection.selected, warnings=tuple(selection.warnings), migration_gap=gap)


class ArchivedHistoryProcess:
    """Only the existing background owners enter this lane, one request each."""
    def __init__(self, archive):
        self.archive = archive
        self.context = get_context('spawn')
        self.lock = Lock()
        self.stopping = Event()
        self.process = self.channel = None
        self.exit_unconfirmed = False
        self.sequence = 0
        self.retry_after = 0

    def reports(self, inputs, reference, revision, *, previous):
        request = dict(inputs, selection=_selection_input(inputs['selection']), defer_while_loading=bool(previous))
        return self._request('reports', revision, reference, request)

    def watch(self, day, now, reference, revision):
        return self._request('watch', revision, reference, dict(day=day, now=now))

    def _start(self):
        local, remote = self.context.Pipe()
        process = self.context.Process(target=run_owned, args=(_work, remote, str(self.archive.path.parent)),
                                       name='cost-guard-archive-projection')
        try:
            process.start()
        except BaseException:
            local.close()
            raise
        finally:
            remote.close()
        self.process, self.channel = process, local

    def _request(self, kind, revision, reference, inputs):
        with self.lock:
            if self.stopping.is_set() or self.exit_unconfirmed or monotonic() < self.retry_after:
                raise RuntimeError('history_projection_not_available')
            self.sequence += 1
            pricing = (reference.models, reference.retrieved_at_ms, reference.source_revision,
                       reference.refresh_not_after_ms, reference.reference_stale)
            payload = _message((self.sequence, kind, revision, reference.diagnostic_signature, pricing, inputs),
                               MAX_REQUEST_BYTES)
            if payload is None:
                raise ValueError('history_projection_request_too_large')
            try:
                if self.process is None:
                    self._start()
                self.channel.send_bytes(payload)
                deadline = monotonic() + PROJECTION_DEADLINE_SECONDS
                while not self.stopping.is_set() and monotonic() < deadline:
                    if self.channel.poll(0.1):
                        break
                else:
                    raise RuntimeError('history_projection_interrupted')
                sequence, generation, result, cpu = _receive(self.channel, MAX_RESULT_BYTES)
                if sequence != self.sequence or generation != revision or self.stopping.is_set():
                    raise ValueError('history_projection_result_not_qualified')
            except Exception:
                self.retry_after = monotonic() + 2
                self._close()
                raise
            if result is None:
                raise RuntimeError('history_projection_result_unavailable')
            return result, cpu

    def stop(self):
        self.stopping.set()

    def close(self):
        self.stop()
        with self.lock:
            self._close()

    def _close(self):
        if self.process is None:
            return
        self.channel.close()
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
            raise RuntimeError('history_projection_exit_unconfirmed')
        process.close()
        self.process = self.channel = None
