"""Explicit POST-only native transfer; no durable content or download leases."""
import re
import select
import socket
import sqlite3
from threading import BoundedSemaphore

from src.sources.errors import SessionExportError


class SessionExports:
    def __init__(self):
        self.slot = BoundedSemaphore(1)

    def handle(self, handler, value, *, cached=False):
        owner = handler.server.lifecycle
        valid = (set(value) == {'binding', 'session_id'} and isinstance(value['binding'], str)
                 and re.fullmatch(r'[a-f0-9]{32}', value['binding']) and isinstance(value['session_id'], str)
                 and re.fullmatch(r'ses_[A-Za-z0-9_-]{1,160}', value['session_id'])) if cached else (
                     set(value) == {'token'} and isinstance(value['token'], str) and len(value['token']) == 32)
        if not valid:
            handler.reply(400, {'error': 'invalid_request'})
            return
        if not owner or handler.headers.get('X-CG-Instance') != owner.nonce:
            handler.reply(409, {'error': 'host_identity_changed'})
            return
        driver = getattr(getattr(owner, 'live', None), 'driver', None)
        if driver is None:
            handler.reply(409, {'error': 'export_unavailable'})
            return
        if not self.slot.acquire(blocking=False):
            handler.reply(429, {'error': 'export_busy'})
            return
        try:
            def cancelled():
                if (owner.stopping.is_set() or owner.live.driver is not driver or
                        not handler.server.session.authenticated(handler.headers.get('Cookie'))):
                    return True
                try:
                    return bool(select.select([handler.connection], [], [], 0)[0] and
                                not handler.connection.recv(1, socket.MSG_PEEK))
                except OSError:
                    return True
            if cached:
                payload, filename = self._cached(owner, driver, value, cancelled)
            else:
                payload, filename = owner.live.details.export(value['token'],
                    driver.coordinator.report_service.source, cancelled)
            if cancelled():
                raise SessionExportError('export_cancelled')
            handler.reply(200, payload, disposition=f'attachment; filename="{filename}"')
        except KeyError:
            handler.reply(410, {'error': 'detail_expired'})
        except SessionExportError as error:
            handler.reply(409, {'error': str(error)})
        except (OSError, sqlite3.Error):
            handler.reply(503, {'error': 'cache_unavailable'})
        finally:
            self.slot.release()

    @staticmethod
    def _cached(owner, driver, value, cancelled):
        archive = getattr(owner, 'display_archive', None)
        views = getattr(archive, 'views', None)
        if not getattr(owner, 'cached_sessions_enabled', False) or views is None or driver.terminal:
            raise SessionExportError('export_unavailable')
        if views.binding != value['binding']:
            raise SessionExportError('export_source_changed')
        service = driver.coordinator.report_service
        epoch = archive.export_epoch(service, views)
        if not epoch:
            raise SessionExportError('export_unavailable')
        key = value['session_id']
        if not views.history.has_present_session(views.source, key):
            raise SessionExportError('export_unavailable')

        def retired():
            return cancelled() or driver.terminal or archive.export_epoch(service, views) != epoch

        if retired():
            raise SessionExportError('export_source_changed')
        payload = service.source.export_session(key, epoch, retired)
        if not views.history.has_present_session(views.source, key) or retired():
            raise SessionExportError('export_cancelled')
        return payload, f'opencode-{key}-sanitized.json'
