"""Native sanitized transfer, isolated from analytical hydration and caches."""
import json
import re
import time

from .errors import SourceError, SessionExportError
from .opencode_v2_transport import V2HttpClient

MAX_EXPORT_BYTES = 16 * 1024 * 1024
EXPORT_SECONDS = 4
SESSION_ID = re.compile(r'ses_[A-Za-z0-9_-]{1,160}\Z')
EXPORT_ROUTE = '/api/experimental/session/{sessionID}/export'


def native_export(source, session_id, epoch, cancelled):
    if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
        raise SessionExportError('export_unavailable')
    deadline = time.monotonic() + EXPORT_SECONDS
    reader = source.new_card_reader()
    client = None
    try:
        reader.refresh_observation_epoch()
        if not epoch or reader.observation_epoch != epoch:
            raise SessionExportError('export_source_changed')
        # A private transport pins the selected registration/auth; never reselect,
        # follow redirects, borrow Live's sockets or persist transcript content.
        client = V2HttpClient(reader._current_endpoint())
        specification = client.bounded_json('/openapi.json', max_bytes=8 * 1024 * 1024,
            deadline=deadline, cancelled=cancelled)
        operation = specification.get('paths', {}).get(EXPORT_ROUTE, {}).get('get', {})
        parameters = operation.get('parameters', [])
        transfer = specification.get('components', {}).get('schemas', {}).get('SessionTransfer.Data', {})
        if not any(isinstance(p, dict) and p.get('name') == 'sanitize' and p.get('in') == 'query'
                   and set(p.get('schema', {}).get('enum', [])) == {'true', 'false'} for p in parameters) or not (
                transfer.get('type') == 'object' and set(transfer.get('required', [])) == {'info', 'messages'}
                and transfer.get('properties', {}).get('messages', {}).get('type') == 'array'):
            raise SessionExportError('export_unavailable')
        response = client.bounded_json(EXPORT_ROUTE.replace('{sessionID}', session_id),
            query={'sanitize': 'true'}, max_bytes=MAX_EXPORT_BYTES, deadline=deadline, cancelled=cancelled)
        data = response.get('data')
        if (set(response) != {'data'} or not isinstance(data, dict) or
                not isinstance(data.get('info'), dict) or data['info'].get('id') != session_id or
                not isinstance(data.get('messages'), list) or
                any(not isinstance(message, dict) or not isinstance(message.get('id'), str) or
                    not isinstance(message.get('type'), str) or
                    message.get('sessionID', session_id) != session_id
                    for message in data['messages'])):
            raise SessionExportError('export_invalid_response')
        if len({message['id'] for message in data['messages']}) != len(data['messages']):
            raise SessionExportError('export_invalid_response')
        # The CLI emits the native data, not the HTTP {data: ...} envelope.
        payload = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
        if len(payload) > MAX_EXPORT_BYTES:
            raise SessionExportError('export_too_large')
        reader.refresh_observation_epoch()
        if reader.observation_epoch != epoch:
            raise SessionExportError('export_source_changed')
        if cancelled() or time.monotonic() >= deadline:
            raise SessionExportError('export_cancelled')
        return payload
    except SourceError as error:
        if error.http_status in (404, 405, 501):
            code = 'export_unavailable'
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
