"""Opaque continuation tokens for the last painted, committed Sessions page."""
from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as InvalidBase64
import hmac
import json
import re

from src.cache.display_session_seek import SessionSeek


_TOKEN = re.compile(r"[A-Za-z0-9_=-]{1,768}")
_ID = re.compile(r"[A-Za-z0-9_-]{1,200}")


def issue(seal, scope, result, row, target, *, forward):
    if not _ID.fullmatch(row.session_id):
        return None
    payload = json.dumps([scope["period"], scope["sort"], scope["direction"], scope["start_ms"],
                          scope["end_ms"], target, result.generation, result.total, row.session_id, forward],
                         separators=(",", ":")).encode("ascii")
    return urlsafe_b64encode(hmac.digest(seal, payload, "sha256") + payload).decode("ascii")


def read(seal, scope, token):
    if type(token) is not str or not _TOKEN.fullmatch(token):
        raise ValueError("invalid_sessions_cursor")
    try:
        signed = urlsafe_b64decode(token)
    except (InvalidBase64, ValueError):
        return None
    digest, payload = signed[:32], signed[32:]
    if not hmac.compare_digest(digest, hmac.digest(seal, payload, "sha256")):
        return None  # An old binding or expired page can still use its numbered offset.
    period, sort, direction, start, end, target, generation, total, anchor, forward = json.loads(payload)
    if (period, sort, direction, start, target) != tuple(scope[key] for key in
            ("period", "sort", "direction", "start_ms", "offset")):
        return None
    return SessionSeek(generation, total, end, anchor, forward)
