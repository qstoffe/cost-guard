"""One-time transfer of the previous Web archive into the checkout's archive."""
from contextlib import closing
import sqlite3

from .web_archive import APPLICATION_ID, SCHEMA


PREVIOUS_ALGORITHM_SUFFIX = '/previous-appdata'


def snapshot_stamp(path):
    """Detect changed source bytes, including uncheckpointed WAL contents."""
    def stamp(item, *, empty_is_absent=False):
        try:
            result = item.stat()
        except FileNotFoundError:
            return None
        if not result.st_size and empty_is_absent:
            return None  # A read-only SQLite connection may create an empty WAL.
        return result.st_size, result.st_mtime_ns, result.st_dev, result.st_ino

    return stamp(path), stamp(path.with_name(path.name + '-wal'), empty_is_absent=True)


def retire(path, original):
    if path.is_symlink() or snapshot_stamp(path) != original:
        raise OSError('old cache changed during transfer')
    # Removing a stale sidecar before a failed main-file unlink could lose WAL
    # history. Leave any locked files to the caller's later upgrade attempt.
    path.unlink(missing_ok=True)
    for suffix in ('-wal', '-shm'):
        path.with_name(path.name + suffix).unlink(missing_ok=True)


def import_web_archive(destination, old_path):
    """Commit and publish old facts; the caller separately retires the source."""
    original = snapshot_stamp(old_path)
    if original[0] is None:
        return original
    if old_path.is_symlink() or old_path.samefile(destination.path):
        raise OSError('old cache aliases destination')
    old_uri = old_path.resolve().as_uri() + '?mode=ro'
    domains = ()
    with destination._connect(write=True) as db:
        db.execute('ATTACH DATABASE ? AS previous', (old_uri,))
        db.execute('PRAGMA main.synchronous=FULL')
        db.execute('BEGIN IMMEDIATE')
        identity = db.execute('PRAGMA previous.application_id').fetchone()[0]
        version = db.execute('PRAGMA previous.user_version').fetchone()[0]
        if identity == APPLICATION_ID and version in (1, SCHEMA):
            # A live publication can win an exact key while older fields are
            # still readable. Retain one alternative for the ordinary decoders.
            db.execute('''CREATE TEMP TABLE transfer AS
                SELECT old.partition, old.domain, old.item, old.algorithm AS original_algorithm,
                       CASE WHEN new.item IS NULL THEN old.algorithm ELSE old.algorithm || ? END AS algorithm,
                       old.observed_ms
                FROM previous.facts AS old LEFT JOIN main.facts AS new USING (partition, domain, algorithm, item)
                LEFT JOIN main.facts AS alternate ON alternate.partition=old.partition AND
                     alternate.domain=old.domain AND alternate.item=old.item AND
                     alternate.algorithm=old.algorithm || ?
                WHERE new.item IS NULL OR (old.domain != 'legacy-import/1'
                      AND new.value != old.value AND
                      (alternate.item IS NULL OR alternate.value != old.value
                       OR alternate.observed_ms < old.observed_ms))''',
                       (PREVIOUS_ALGORITHM_SUFFIX, PREVIOUS_ALGORITHM_SUFFIX))
            domains = tuple(row[0] for row in db.execute('SELECT DISTINCT domain FROM transfer'))
            db.execute('''INSERT INTO main.facts (partition, domain, item, algorithm, revision, observed_ms, value)
                SELECT t.partition, t.domain, t.item, t.algorithm, old.revision, t.observed_ms, old.value
                FROM transfer AS t JOIN previous.facts AS old USING (partition, domain, item)
                WHERE old.algorithm=t.original_algorithm
                ON CONFLICT(partition, domain, algorithm, item) DO UPDATE SET
                  revision=excluded.revision, observed_ms=excluded.observed_ms, value=excluded.value''')
            db.execute('''INSERT OR REPLACE INTO main.fact_cursors (partition, domain, algorithm, item)
                SELECT partition, domain, algorithm, item FROM transfer
                WHERE domain != 'legacy-import/1' ''')
            db.commit()
    # Use a separate read connection after commit. A readable previous key
    # must exist in the destination, either imported or superseded by newer data.
    with destination._connect() as db:
        db.execute('ATTACH DATABASE ? AS previous', (old_uri,))
        if identity == APPLICATION_ID and version in (1, SCHEMA):
            missing = db.execute('''SELECT 1 FROM previous.facts AS old
                LEFT JOIN main.facts AS new USING (partition, domain, algorithm, item)
                LEFT JOIN main.facts AS alternate ON alternate.partition=old.partition AND
                     alternate.domain=old.domain AND alternate.item=old.item AND
                     alternate.algorithm=old.algorithm || ?
                WHERE new.item IS NULL
                   OR (old.domain != 'legacy-import/1' AND new.value != old.value
                       AND (alternate.item IS NULL OR alternate.value != old.value)) LIMIT 1''',
                                 (PREVIOUS_ALGORITHM_SUFFIX,)).fetchone()
            if missing:
                raise sqlite3.DatabaseError('Web history transfer not readable')
        db.execute('SELECT 1 FROM main.facts LIMIT 1').fetchone()
    if domains:
        destination.note_publication(domains)
    return original


def retire_disposable(database, old_path):
    original = snapshot_stamp(old_path)
    if old_path.is_symlink() or (database.paths.database.is_file() and old_path.is_file()
                                and old_path.samefile(database.paths.database)):
        raise OSError('old cache aliases destination')
    if original[0] is None:
        retire(old_path, original)
        return
    old_uri = old_path.resolve().as_uri() + '?mode=ro'
    with closing(sqlite3.connect(old_uri, uri=True, timeout=0.2)) as older:
        tables = {row[0] for row in older.execute("SELECT name FROM sqlite_schema WHERE type='table'")}
        sightings = (older.execute('SELECT model_id, first_seen_at FROM model_first_sightings').fetchall()
                     if 'model_first_sightings' in tables else [])
        pricing = (older.execute('''SELECT namespace, cache_key, payload_json, source_revision, algorithm_version,
                     updated_at_utc FROM cache_entries WHERE namespace=?''', ('pricing.github-copilot',)).fetchall()
                   if 'cache_entries' in tables else [])
    database.initialize(busy_timeout_ms=100)
    with database.connect(busy_timeout_ms=100) as db:
        db.execute('PRAGMA synchronous=FULL')
        db.executemany('''INSERT INTO model_first_sightings VALUES (?,?)
            ON CONFLICT(model_id) DO UPDATE SET first_seen_at=min(first_seen_at, excluded.first_seen_at)''', sightings)
        db.executemany('''INSERT OR IGNORE INTO cache_entries
            (namespace,cache_key,payload_json,source_revision,algorithm_version,updated_at_utc)
            VALUES (?,?,?,?,?,?)''', pricing)
    with database.connect(busy_timeout_ms=100) as db:
        if any(not db.execute('SELECT 1 FROM model_first_sightings WHERE model_id=?', (key,)).fetchone()
               for key, _ in sightings) or any(not db.execute(
                   'SELECT 1 FROM cache_entries WHERE namespace=? AND cache_key=?', row[:2]).fetchone() for row in pricing):
            raise sqlite3.DatabaseError('disposable cache transfer not readable')
        db.execute('SELECT 1 FROM cache_metadata LIMIT 1').fetchone()
    retire(old_path, original)
