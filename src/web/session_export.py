"""One authenticated, in-memory analysis export, independent of detail refresh."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import logging
import re
from threading import Event, Lock
import time

from src.sources.errors import SessionExportError, SourceError
from src.application.projection import identity as fingerprint


CHUNK_BYTES = 1024 * 1024
CLIENT_IDLE_SECONDS = 300
KEY = re.compile(r'[0-9a-f]{32}\Z')
LOG = logging.getLogger(__name__)


@dataclass
class Export:
    key: str
    browser: str
    owner: object
    driver: object
    source: object
    identity: tuple
    touched: float
    cancelled: Event
    state: str = 'preparing'
    archive: bytes | None = None
    filename: str | None = None
    error: str | None = None

    def retired(self, session):
        return (self.cancelled.is_set() or self.owner.stopping.is_set()
                or self.owner.live.driver is not self.driver
                or not session.authorized_browser(self.browser))


def binding(source):
    if not callable(getattr(source, 'export_session_tree', None)):
        return None
    epoch = getattr(source, 'observation_epoch', None)
    return (source.source_id, source.source_instance, epoch) if epoch else None


def selection(handler, token):
    owner = handler.server.lifecycle
    live = getattr(owner, 'live', None)
    driver = getattr(live, 'driver', None)
    if driver is None:
        return ('unavailable' if getattr(live, 'source_failure', None) else 'pending'), None
    if getattr(driver, 'terminal', False):
        return 'unavailable', None
    source = driver.coordinator.report_service.source
    if not callable(getattr(source, 'export_session_tree', None)):
        return 'unavailable', None
    source_binding = binding(source)
    if source_binding is None:
        return 'pending', None
    identity = live.details.export_selection(token, source_binding)
    return 'ready', (driver, source, identity)


def export_status(handler, token):
    state, request = selection(handler, token)
    return {'export_state': state, **({'export_scope': fingerprint(request[2])} if request else {})}


class SessionExports:
    def __init__(self):
        self.lock = Lock()
        self.current = None
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='cost-guard-export')

    def expire(self):
        with self.lock:
            job = self.current
            if job and time.monotonic() - job.touched >= CLIENT_IDLE_SECONDS:
                self._release(job)

    def _release(self, job):
        job.cancelled.set()
        job.archive = None
        if job.state != 'preparing':
            self.current = None

    def close(self):
        with self.lock:
            if self.current:
                self._release(self.current)
        self.pool.shutdown(wait=True)

    def _build(self, job, session):
        try:
            archive, filename = job.owner.live.details.export_admitted(
                job.identity, job.source, lambda: job.retired(session))
            error = None
        except SessionExportError as failure:
            archive = filename = None
            error = str(failure)
        except Exception:
            LOG.error('Session analysis archive generation failed')
            archive = filename = None
            error = 'export_failed'
        with self.lock:
            if job.retired(session):
                self.current = None
                return
            job.archive, job.filename, job.error = archive, filename, error
            job.state = 'ready' if error is None else 'failed'

    def _start(self, handler, key, browser, token, scope):
        self.expire()
        _, request = selection(handler, token)
        if request is None:
            raise SessionExportError('export_unavailable')
        driver, source, identity = request
        if fingerprint(identity) != scope:
            raise SessionExportError('export_source_changed')
        with self.lock:
            if self.current is not None:
                if self.current.browser == browser and self.current.cancelled.is_set():
                    raise SessionExportError('export_retiring')
                raise SessionExportError('export_busy')
            job = Export(key, browser, handler.server.lifecycle, driver, source, identity,
                         time.monotonic(), Event())
            self.current = job
            self.pool.submit(self._build, job, handler.server.session)
        handler.reply(202, {'state': 'preparing'})

    def _read(self, handler, job, action, offset):
        if job.retired(handler.server.session):
            raise SessionExportError('export_cancelled')
        if action == 'status' and job.state == 'preparing':
            handler.reply(200, {'state': 'preparing'})
            return
        if job.error:
            raise SessionExportError(job.error)
        try:
            job.source.refresh_observation_epoch()
        except SourceError:
            raise SessionExportError('export_source_changed') from None
        if binding(job.source) != job.identity[:3]:
            raise SessionExportError('export_source_changed')
        with self.lock:
            archive, filename = job.archive, job.filename
        if archive is None or job.retired(handler.server.session):
            raise SessionExportError('export_cancelled')
        if action == 'status':
            handler.reply(200, {'state': 'ready', 'size': len(archive)})
        elif offset >= len(archive):
            handler.reply(400, {'error': 'invalid_request'})
        else:
            # Only the small, fully admitted response leaves the ingress timer.
            if handler.deadline is not None:
                handler.deadline.cancel()
                handler.deadline.join()
            handler.connection.settimeout(15)
            handler.reply(200, archive[offset:offset + CHUNK_BYTES], content_type='application/zip',
                          disposition=f'attachment; filename="{filename}"')

    def handle(self, handler, value):
        owner = handler.server.lifecycle
        if not owner or handler.headers.get('X-CG-Instance') != owner.nonce:
            handler.reply(409, {'error': 'host_identity_changed'})
            return
        action, key, token, offset, scope = (value.get(field) for field in ('action', 'id', 'token', 'offset', 'scope'))
        fields = {'start': {'token', 'scope'}, 'status': set(), 'cancel': set(), 'chunk': {'offset'}}
        if (not isinstance(action, str) or action not in fields or
                set(value) != {'action', 'id'} | fields[action] or
                not isinstance(key, str) or not KEY.fullmatch(key) or
                action == 'start' and (not isinstance(token, str) or not KEY.fullmatch(token) or
                                       not isinstance(scope, str) or len(scope) != 64) or
                action == 'chunk' and (type(offset) is not int or not 0 <= offset < 2**26
                                       or offset % CHUNK_BYTES)):
            handler.reply(400, {'error': 'invalid_request'})
            return
        browser = handler.server.session.browser_key(handler.headers.get('Cookie'))
        try:
            if action == 'start':
                self._start(handler, key, browser, token, scope)
                return
            with self.lock:
                job = self.current
                if job is None or job.key != key or job.browser != browser:
                    raise SessionExportError('export_cancelled')
                job.touched = time.monotonic()
                if action == 'cancel':
                    self._release(job)
            if action == 'cancel':
                handler.reply(200, {'state': 'released'})
            else:
                self._read(handler, job, action, offset)
        except KeyError:
            handler.reply(410, {'error': 'detail_expired'})
        except SessionExportError as error:
            code = str(error)
            handler.reply(429 if code in ('export_busy', 'export_retiring') else 409, {'error': code})
