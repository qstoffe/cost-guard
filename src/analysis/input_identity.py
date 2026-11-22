"""Versioned exact first-input identity from normalized, ordered semantic parts.

No filesystem/URL acquisition. Unverifiable attachment references and unknown
part kinds fail closed. Only the digest may enter a disposable match index.
"""
import base64
import binascii
from hashlib import sha256
import json
from urllib.parse import unquote_to_bytes

from src.domain import EventKind, MessageRole

IDENTITY_VERSION = 'first-input-1'


def first_input(snapshot):
    """Do not promote the second input when the first is unsupported/a subtask."""
    if snapshot.root.parent_session_id is not None or not snapshot.complete:
        return None
    events = sorted((event for event in snapshot.events
        if event.session_id == snapshot.root.session_id and event.kind in {
            EventKind.USER_PROMPT, EventKind.SUBTASK}), key=lambda event: (event.created_at_ms, event.event_id))
    if not events or events[0].kind is not EventKind.USER_PROMPT:
        return None
    return next((message for message in snapshot.messages
        if message.session_id == snapshot.root.session_id and message.message_id == events[0].event_id
        and message.role is MessageRole.USER and not message.summary), None)


def _file(data):
    # A recorded inline data URI supplies content, unlike a filename/path/HTTP URL.
    url = data.get('url')
    if not isinstance(url, str) or not url.startswith('data:') or ',' not in url:
        return None
    header, body = url[5:].split(',', 1)
    try:
        content = base64.b64decode(body, validate=True) if header.endswith(';base64') else unquote_to_bytes(body)
    except (ValueError, binascii.Error):
        return None
    return ['file', data.get('mime') or header.split(';')[0], data.get('filename') or '',
            len(content), sha256(content).hexdigest()]


def fingerprint(message):
    if message is None:
        return None
    parts = []
    for part in message.parts:
        if part.data.get('synthetic') or part.data.get('ignored'):
            continue
        if part.kind == 'text' and isinstance(part.data.get('text'), str):
            parts.append(['text', part.data['text']])
        elif part.kind == 'file':
            value = _file(part.data)
            if value is None:
                return None
            parts.append(value)
        else:
            return None
    if not parts or not any(part[0] == 'file' or part[1].strip() for part in parts):
        return None
    encoded = json.dumps([IDENTITY_VERSION, parts], ensure_ascii=True, separators=(',', ':')).encode('ascii')
    return sha256(encoded).hexdigest()


def preview(message):
    """Ephemeral bounded display only, never a match key or persisted payload."""
    if message is None:
        return 'Input preview unavailable'
    text = ' '.join(part.data.get('text', '') for part in message.parts
        if part.kind == 'text' and not part.data.get('synthetic') and not part.data.get('ignored'))
    # Avoid displaying likely credentials/private key material even in a short preview.
    if any(word in text.lower() for word in ('private key', 'bearer ', 'password', 'api_key', 'access_token')):
        return 'Input preview withheld (potentially private)'
    compact = ' '.join(text.split())
    return compact[:120] + ('…' if len(compact) > 120 else '') if compact else 'Attachment input'
