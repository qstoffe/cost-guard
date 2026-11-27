"""Compose a complete masked analysis ZIP without creating transcript files."""
from contextlib import closing
import io
import json
import re
from zipfile import ZIP_DEFLATED, ZipFile

from src.sources.errors import SessionExportError
from .session_export_mask import mask_session, mask_text

# Keep the browser's response cap in app.js in sync.
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_JSON_BYTES = 192 * 1024 * 1024  # Total pretty UTF-8 across all entries.
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f-\x9f\u00ad\u061c\u200b\u200e\u200f'
                     r'\u2028-\u202e\u2060-\u206f\ufeff\ud800-\udfff]')
_DEVICE = re.compile(r'^(con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³]|conin\$|conout\$)(?: *\.|$)', re.I)
_SESSION_ID = re.compile(r'ses_[A-Za-z0-9_-]{1,160}\Z')


def _safe_stem(title, session_id):
    clean = _UNSAFE.sub('', title) if isinstance(title, str) else ''
    # Leave room for a collision suffix and extension while preserving Unicode.
    stem = clean.encode('utf-8')[:200].decode('utf-8', errors='ignore').rstrip('. ')
    if stem.strip() and not _DEVICE.match(stem):
        return stem
    return f'session-{session_id}' if _SESSION_ID.fullmatch(session_id) else 'session'


def analysis_filename(title, session_id):
    return _safe_stem(mask_text(title) if isinstance(title, str) else '', session_id) + '.zip'


def _entry_name(stem, used, suffixes):
    key = stem.casefold()
    number = suffixes.get(key, 0)
    candidate = stem
    if key in used:
        while True:
            number += 1
            candidate = f'{stem} ({number})'
            if candidate.casefold() not in used:
                break
    suffixes[key] = number
    used.add(candidate.casefold())
    return candidate + '.json'


def _write_pretty(entry, data, remaining, check):
    buffer = bytearray()
    encoder = json.JSONEncoder(ensure_ascii=False, indent=2, allow_nan=False)
    for chunk in encoder.iterencode(data):
        buffer.extend(chunk.encode('utf-8'))
        if len(buffer) >= 65536:
            check()
            if len(buffer) >= remaining:
                raise SessionExportError('export_too_large')
            entry.write(buffer)
            remaining -= len(buffer)
            buffer.clear()
    buffer.extend(b'\n')
    check()
    if len(buffer) > remaining:
        raise SessionExportError('export_too_large')
    entry.write(buffer)
    return remaining - len(buffer)


def build_analysis_zip(acquire, cancelled):
    def check():
        if cancelled():
            raise SessionExportError('export_cancelled')

    def expired():
        check()
        return False

    used, suffixes = set(), {}
    remaining = MAX_JSON_BYTES
    try:
        with io.BytesIO() as buffer:
            with closing(acquire(expired)) as sessions, ZipFile(buffer, 'w', ZIP_DEFLATED) as archive:
                for data in sessions:
                    masked = mask_session(data, check)
                    info = masked['info']
                    stem = _safe_stem(info.get('title'), info['id'])
                    with archive.open(_entry_name(stem, used, suffixes), 'w') as entry:
                        remaining = _write_pretty(entry, masked, remaining, check)
                    del masked, data
                    if buffer.tell() > MAX_ARCHIVE_BYTES:
                        raise SessionExportError('export_too_large')
            check()
            if not used:
                raise SessionExportError('export_invalid_response')
            if buffer.tell() > MAX_ARCHIVE_BYTES:
                raise SessionExportError('export_too_large')
            return buffer.getvalue()
    except (TypeError, ValueError, RecursionError, UnicodeError):
        raise SessionExportError('export_invalid_response') from None
