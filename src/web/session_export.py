"""Explicit POST-only native transfer; no durable content or download leases."""
import select
import socket
from threading import BoundedSemaphore

from src.sources.errors import SessionExportError


class SessionExports:
    def __init__(self):
        self.slot = BoundedSemaphore(1)

    def handle(self, handler, value):
        owner = handler.server.lifecycle
        if (set(value) != {'token'} or not isinstance(value['token'], str) or
                len(value['token']) != 32):
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
            payload, filename = owner.live.details.export(value['token'],
                driver.coordinator.report_service.source, cancelled)
            if cancelled():
                raise SessionExportError('export_cancelled')
            handler.reply(200, payload, disposition=f'attachment; filename="{filename}"')
        except KeyError:
            handler.reply(410, {'error': 'detail_expired'})
        except SessionExportError as error:
            handler.reply(409, {'error': str(error)})
        finally:
            self.slot.release()
