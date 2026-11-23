"""Bounded native transfers from one registered V2 source and catalog tree."""
import re
import time
from types import SimpleNamespace

from .errors import SourceDataError, SourceError, SessionExportError
from .opencode_v2_catalog import V2CatalogIndex
from .opencode_v2_transport import V2HttpClient
from .opencode_v2_wire import fetch_global_sessions

MAX_EXPORT_BYTES = 32 * 1024 * 1024  # Per native transfer.
EXPORT_SECONDS = 90
REQUEST_SECONDS = 15
SESSION_ID = re.compile(r'ses_[A-Za-z0-9_-]{1,160}\Z')
EXPORT_ROUTE = '/api/experimental/session/{sessionID}/export'


class ExportReads:
    def __init__(self, client, cancelled):
        self.client = client
        self.cancelled = cancelled
        self.deadline = time.monotonic() + EXPORT_SECONDS

    def check(self):
        if self.cancelled():
            raise SessionExportError('export_cancelled')
        if time.monotonic() >= self.deadline:
            raise SessionExportError('export_timed_out')

    def json(self, path, *, query=None, max_bytes=8 * 1024 * 1024):
        self.check()
        deadline = min(self.deadline, time.monotonic() + REQUEST_SECONDS)
        try:
            return self.client.bounded_json(path, query=query, max_bytes=max_bytes,
                                            deadline=deadline, cancelled=self.cancelled)
        except (SessionExportError, SourceError):
            self.check()
            if time.monotonic() >= deadline:
                raise SessionExportError('export_timed_out') from None
            raise


class CatalogReads:
    """Keep only topology from the same paged wire contract used by Live."""
    def __init__(self, reads):
        self.reads = reads

    def json(self, path, *, query=None):
        page = self.reads.json(path, query=query)
        items, cursor = page.get('data'), page.get('cursor')
        if (not isinstance(items, list) or (cursor is not None and not isinstance(cursor, dict))
                or (cursor and cursor.get('next') and (not items or not isinstance(cursor['next'], str)))):
            raise SessionExportError('export_invalid_response')
        return {**page, 'data': [dict(id=item.get('id'), parentID=item.get('parentID')) for item in items]}


def _check_capability(specification):
    operation = specification.get('paths', {}).get(EXPORT_ROUTE, {}).get('get', {})
    transfer = specification.get('components', {}).get('schemas', {}).get('SessionTransfer.Data', {})
    supports_native = any(
        isinstance(parameter, dict) and parameter.get('name') == 'sanitize'
        and parameter.get('in') == 'query' and 'false' in parameter.get('schema', {}).get('enum', [])
        for parameter in operation.get('parameters', [])
    )
    if not supports_native or not (
        transfer.get('type') == 'object' and {'info', 'messages'} <= set(transfer.get('required', []))
        and transfer.get('properties', {}).get('messages', {}).get('type') == 'array'
    ):
        raise SessionExportError('export_unavailable')


def _session_data(response, session_id, parent_id):
    data = response.get('data')
    if set(response) != {'data'} or not isinstance(data, dict):
        raise SessionExportError('export_invalid_response')
    info, messages = data.get('info'), data.get('messages')
    if (not isinstance(info, dict) or info.get('id') != session_id
            or (info.get('parentID') or None) != (parent_id or None)
            or not isinstance(messages, list)
            or any(not isinstance(message, dict) or not isinstance(message.get('id'), str)
                   or not isinstance(message.get('type'), str)
                   or message.get('sessionID', session_id) != session_id for message in messages)
            or len({message['id'] for message in messages}) != len(messages)):
        raise SessionExportError('export_invalid_response')
    return data


def native_export_tree(source, session_id, epoch, cancelled):
    """Yield one native session at a time. Exhaustion verifies the pinned epoch."""
    if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
        raise SessionExportError('export_unavailable')
    reader = source.new_card_reader()
    client = None
    member_id = session_id
    try:
        reader.refresh_observation_epoch()
        if not epoch or reader.observation_epoch != epoch:
            raise SessionExportError('export_source_changed')
        # No Live sockets, cached topology, redirects or endpoint reselection.
        client = V2HttpClient(reader._current_endpoint())
        if reader.observation_epoch != epoch:
            raise SessionExportError('export_source_changed')
        reads = ExportReads(client, cancelled)
        _check_capability(reads.json('/openapi.json'))
        sessions, _, _ = fetch_global_sessions(CatalogReads(reads))
        topology = V2CatalogIndex([SimpleNamespace(data=row) for row, _ in sessions])
        if session_id not in topology.by_id:
            raise SessionExportError('export_unavailable')
        for member in topology.tree(session_id):
            reads.check()
            member_id = member.data['id']
            if not SESSION_ID.fullmatch(member_id):
                raise SessionExportError('export_invalid_response')
            response = reads.json(EXPORT_ROUTE.replace('{sessionID}', member_id),
                                  query={'sanitize': 'false'}, max_bytes=MAX_EXPORT_BYTES)
            yield _session_data(response, member_id, member.data.get('parentID'))
            del response
        reader.refresh_observation_epoch()
        if reader.observation_epoch != epoch:
            raise SessionExportError('export_source_changed')
        reads.check()
    except SourceDataError:
        raise SessionExportError('export_invalid_response') from None
    except SourceError as error:
        if error.http_status in (404, 405, 501):
            code = 'export_unavailable' if member_id == session_id else 'export_descendant_unavailable'
        elif error.http_status in (401, 403):
            code = 'export_source_denied'
        else:
            code = 'export_source_unavailable'
        raise SessionExportError(code) from None
    except (AttributeError, TypeError, ValueError, RecursionError, UnicodeError):
        raise SessionExportError('export_invalid_response') from None
    finally:
        if client is not None:
            client.cancel()
        reader.close_reads()
