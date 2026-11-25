"""Retire only the known pre-report-cache files, without importing their data."""
from contextlib import closing
import sqlite3
import stat


def _file_stamp(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
            getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
        raise OSError('obsolete cache path is not a private regular file')
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def retire_cache(path, *, application_id=None, versions=(), generation=None):
    path = path.absolute()
    if path.resolve() != path:
        raise OSError('obsolete cache path has an alias')
    sidecars = tuple(path.with_name(path.name + suffix) for suffix in ('-wal', '-shm', '-journal'))
    stamp = _file_stamp(path)
    for sidecar in sidecars:
        _file_stamp(sidecar)
    if stamp is not None:
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=0.1)) as db:
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
            if generation is not None:
                valid = db.execute("SELECT value FROM cache_metadata WHERE key='schema_generation'").fetchone()
                owned = valid == (str(generation),)
            else:
                owned = (db.execute('PRAGMA application_id').fetchone()[0] == application_id and
                         db.execute('PRAGMA user_version').fetchone()[0] in versions)
        if not owned or _file_stamp(path) != stamp:
            raise OSError('obsolete cache identity changed or is unrecognized')
        path.unlink()
    # A failed main-file removal must never be followed by sidecar removal.
    for sidecar in sidecars:
        if _file_stamp(sidecar) is not None:
            sidecar.unlink()
