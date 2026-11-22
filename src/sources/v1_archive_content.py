"""A conservative fingerprint of one complete ordered V1 archive capture."""
import hashlib


SESSION_FIELDS = ("id", "parent_id", "project_id", "directory", "title", "time_created", "time_updated", "time_archived")
MESSAGE_FIELDS = ("id", "session_id", "time_created", "time_updated")
PART_FIELDS = ("id", "message_id", "session_id", "time_created", "time_updated")
_RECORDS = ((b"S", SESSION_FIELDS), (b"M", MESSAGE_FIELDS), (b"P", PART_FIELDS))


class CaptureFingerprint:
    """No payload copy or whole-root sort; a changed seek order can miss reuse."""
    def __init__(self, binding, encoding):
        self._hash = hashlib.sha256(b"opencode-v1-archive-capture-v1\0")
        self._field(binding)
        self._field(encoding)

    def record(self, phase, row, payload=None):
        kind, columns = _RECORDS[phase]
        self._hash.update(kind)
        for key in columns:
            self._field(row[key])
        if phase:
            self._frame(b"J", payload)

    def finish(self):
        return "v1-capture:" + self._hash.hexdigest()

    def _frame(self, label, value):
        self._hash.update(label)
        self._hash.update(len(value).to_bytes(8, "big"))
        self._hash.update(value)

    def _field(self, value):
        if value is None:
            self._hash.update(b"N")
        elif isinstance(value, int):
            self._frame(b"I", value.to_bytes(8, "big", signed=True))
        elif isinstance(value, float):
            self._frame(b"R", value.hex().encode("ascii"))
        elif isinstance(value, str):
            self._frame(b"T", value.encode("utf-8", errors="surrogatepass"))
        else:
            self._frame(b"B", value)  # SQLite BLOB.
