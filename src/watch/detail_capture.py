"""One supervised detail child; bulk history IPC never runs on the Live turn."""
import multiprocessing
from pathlib import Path
import pickle
import tempfile
from threading import Event
import time


PHASES = ('queued', 'reading', 'verifying', 'analyzing', 'publishing')
MAX_DETAIL_BYTES = 256 * 1024 * 1024


class DetailWorkerStopError(RuntimeError):
    """Keep the exact child handle and stop admission if exit is unconfirmed."""


class WorkMeter:
    def __init__(self, shared):
        self.shared = shared
        self.units = 0
        self.last_sent = 0

    def observe(self, phase, units=0):
        self.units += max(0, units)
        now = time.monotonic()
        if now - self.last_sent >= .05 or units == 0:
            with self.shared.get_lock():
                self.shared[:] = (PHASES.index(phase), self.units)
            self.last_sent = now


class DetailWriter:
    """Bound file IPC size without truncating a successfully published history."""
    def __init__(self, stream, progress=lambda *_: None):
        self.stream, self.progress, self.bytes = stream, progress, 0

    def write(self, data):
        self.bytes += len(data)
        if self.bytes > MAX_DETAIL_BYTES:
            raise ValueError('detail_too_large')
        for offset in range(0, len(data), 65536):
            self.stream.write(data[offset:offset + 65536])
            self.progress('publishing', 1)


def write_payload(path, value, progress=lambda *_: None):
    with Path(path).open('wb') as stream:
        pickle.dump(value, DetailWriter(stream, progress), protocol=pickle.HIGHEST_PROTOCOL)


def read_payload(path):
    if Path(path).stat().st_size > MAX_DETAIL_BYTES:
        raise ValueError('detail_too_large')
    with Path(path).open('rb') as stream:
        return pickle.load(stream)  # Only this owned child/parent writes these private files.


class DetailCapture:
    def __init__(self, target, *, no_progress_seconds=120, context=None):
        self.target = target
        self.context = context or multiprocessing.get_context('spawn')
        self.no_progress_seconds = no_progress_seconds
        self.stopping = Event()
        self.process = None
        self.directory = None
        self.exit_unconfirmed = False
        self.last_metrics = {}
        self.started_count = 0
        self.retired_count = 0

    def cancel(self):
        self.stopping.set()

    def _stop(self, process):
        process.terminate()
        process.join(1)
        if process.is_alive():
            process.kill()
            process.join(1)
        if process.is_alive():
            self.exit_unconfirmed = True
            raise DetailWorkerStopError('detail_worker_exit_unconfirmed')
        self.retired_count += 1

    def capture(self, details, source, config, now_ms, *, unavailable=False):
        claimed = details.claim()
        if claimed is None:
            return
        key, attempt, history = claimed
        outcome = dict(error='detail_internal_error', terminal=True)
        started = time.monotonic()
        try:
            if self.exit_unconfirmed:
                raise DetailWorkerStopError('detail_worker_exit_unconfirmed')
            if unavailable or self.stopping.is_set():
                outcome = dict(error='source_unavailable')
                return
            export = getattr(source, 'detail_evidence', None)
            evidence = export() if callable(export) else None
            identity = source.source_id, source.source_instance, getattr(source, 'observation_epoch', None)
            directory = tempfile.TemporaryDirectory(prefix='cost-guard-detail-')
            self.directory = directory
            try:
                input_path, output_path = Path(directory.name) / 'input', Path(directory.name) / 'output'
                write_payload(input_path, dict(history=history, key=key, config=config,
                    now_ms=now_ms, identity=identity, evidence=evidence))
                shared = self.context.Array('d', (PHASES.index('reading'), 0))
                process = self.context.Process(target=self.target, args=(shared, (str(input_path), str(output_path))))
                self.process = process
                last_units, changed_at = 0, time.monotonic()
                try:
                    process.start()
                    self.started_count += 1
                    while process.is_alive():
                        # A crashed/blocked child can own this lock too. Reading
                        # progress must never disable cancellation or the watchdog.
                        lock = shared.get_lock()
                        if lock.acquire(timeout=.05):
                            try:
                                phase, units = shared[:]
                            finally:
                                lock.release()
                            if units > last_units:
                                last_units, changed_at = units, time.monotonic()
                            details.progress(key, attempt, PHASES[int(phase)], int(units))
                        if self.stopping.is_set() or not details.current(key, attempt):
                            outcome = dict(error='detail_cancelled', terminal=True)
                            self._stop(process)
                            break
                        if time.monotonic() - changed_at >= self.no_progress_seconds:
                            outcome = dict(error='detail_no_progress')
                            self._stop(process)
                            break
                        process.join(.05)
                    else:
                        process.join()
                        if process.exitcode == 0 and output_path.is_file():
                            outcome = read_payload(output_path)
                        else:
                            outcome = dict(error='detail_worker_failed', terminal=True)
                    # The original service epoch must still own this publication.
                    refresh = getattr(source, 'refresh_observation_epoch', None)
                    if callable(refresh):
                        refresh()
                    current = source.source_id, source.source_instance, getattr(source, 'observation_epoch', None)
                    if identity != current:
                        outcome = dict(error='source_identity_changed', terminal=True)
                    self.last_metrics = dict(seconds=round(time.monotonic() - started, 3),
                        input_bytes=input_path.stat().st_size,
                        output_bytes=output_path.stat().st_size if output_path.is_file() else 0,
                        completed=int(last_units), work=outcome.get('work', {}))
                finally:
                    if process.pid is not None and process.is_alive() and not self.exit_unconfirmed:
                        self._stop(process)
                    if not self.exit_unconfirmed:
                        process.close()
                        self.process = None
            finally:
                # A child with unconfirmed exit still owns its exact IPC files.
                if not self.exit_unconfirmed:
                    directory.cleanup()
                    self.directory = None
        except DetailWorkerStopError:
            raise
        except Exception:
            outcome = dict(error='detail_worker_failed', terminal=True)
        finally:
            details.finish(key, attempt, outcome)
            if not outcome.get('error'):
                self.last_metrics['published_at_ms'] = int(time.time() * 1000)
