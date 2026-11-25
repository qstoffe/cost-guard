"""Indexed display provenance for All time; never a report query bound."""

DETAIL_DOMAIN = 'detail/1'
BACKFILL_BATCH = 16


def create_schema(db, *, upgrade=False):
    db.execute('''CREATE TABLE prompt_range (
        partition TEXT NOT NULL, item TEXT NOT NULL, first_ms INTEGER NOT NULL,
        PRIMARY KEY(partition, item)
    ) WITHOUT ROWID''')
    db.execute('CREATE INDEX prompt_range_first ON prompt_range (first_ms)')
    db.execute('''CREATE TABLE prompt_range_backfill (
        slot INTEGER PRIMARY KEY CHECK (slot=1), cursor INTEGER NOT NULL
    )''')
    if upgrade:
        db.execute('INSERT INTO prompt_range_backfill VALUES (1, 0)')


def first_prompt(value):
    try:
        block, = value['view']['prompt_blocks']
        rows = block['rows']
    except (KeyError, TypeError, ValueError):
        return None
    if not isinstance(rows, list):
        return None
    return min((at for row in rows if isinstance(row, dict) and row.get('is_compaction') is False
                and type(at := row.get('at_ms')) is int and 0 < at < 2**53), default=None)


def save(db, partition, item, first):
    if first is not None:
        db.execute('''INSERT INTO prompt_range VALUES (?, ?, ?)
            ON CONFLICT(partition, item) DO UPDATE SET first_ms=excluded.first_ms
            WHERE excluded.first_ms < prompt_range.first_ms''',
            (partition, item, first))


def backfill_cursor(db):
    row = db.execute('SELECT cursor FROM prompt_range_backfill WHERE slot=1').fetchone()
    return row[0] if row is not None else None


def read(db, run, now):
    stored = db.execute('SELECT min(first_ms) FROM prompt_range WHERE first_ms<=?', (now,)).fetchone()[0]
    runtime = db.execute('''SELECT state='observed' AND NOT terminal AND NOT EXISTS (
        SELECT 1 FROM session_pending WHERE run=?
    ) FROM session_runtime WHERE run=?''', (run, run)).fetchone()
    return stored, bool(runtime and runtime[0]) and backfill_cursor(db) is None
