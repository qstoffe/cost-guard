"""Indexed ready Sessions metadata; display payloads are loaded only for the page."""
from decimal import Decimal


SORT_COLUMNS = {
    'activity': 'activity_ms',
    'name': 'title_key',
    'model': 'model_key',
    'effort': 'effort_key',
    'ccost': 'cost_key',
    'prompts': 'prompt_count',
    'duration': 'duration_ms',
    'ctx': 'context_tokens',
}
SESSIONS_DOMAIN = 'sessions/1'


def create_schema(db):
    db.execute('''CREATE TABLE ready_sessions (
        item TEXT PRIMARY KEY,
        partition TEXT NOT NULL,
        algorithm TEXT NOT NULL,
        revision TEXT NOT NULL,
        observed_ms INTEGER NOT NULL,
        activity_ms INTEGER,
        last_activity_ms INTEGER,
        latest_activity_ms INTEGER,
        title_key TEXT NOT NULL,
        model_key TEXT,
        effort_key TEXT,
        cost_key BLOB,
        prompt_count INTEGER,
        duration_ms INTEGER,
        context_tokens INTEGER
    ) WITHOUT ROWID''')
    for column in SORT_COLUMNS.values():
        for suffix, direction in (('asc', 'ASC'), ('desc', 'DESC')):
            db.execute(f'''CREATE INDEX ready_sessions_{column}_{suffix}
                ON ready_sessions ({column} IS NULL, {column} {direction}, item)''')
    db.execute('CREATE INDEX ready_sessions_last_activity ON ready_sessions (last_activity_ms)')
    db.execute('CREATE INDEX ready_sessions_latest_activity ON ready_sessions (latest_activity_ms)')


def _decimal_key(amount):
    """An order-preserving SQLite BLOB without float rounding or Decimal context."""
    if amount is None:
        return None
    value = Decimal(amount)
    if not value:
        return b'\x01'
    exponent = (value.adjusted() + 2**63).to_bytes(8, 'big')
    digits = bytes(48 + digit for digit in value.as_tuple().digits).rstrip(b'0')
    magnitude = exponent + digits + b'\x00'
    if value.is_signed():
        return b'\x00' + bytes(255 - byte for byte in magnitude)
    return b'\x02' + magnitude


def save_ready(db, item, partition, algorithm, revision, observed_ms, keys, last_at, latest_at):
    effort = keys['effort']
    values = (item, partition, algorithm, revision, observed_ms, keys['activity'], last_at, latest_at,
              keys['name'], keys['model'], f'{effort[0]:02d}:{effort[1]}' if effort is not None else None,
              _decimal_key(keys['ccost']), keys['prompts'], keys['duration'], keys['ctx'])
    db.execute('''INSERT INTO ready_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(item) DO UPDATE SET
            partition=excluded.partition, algorithm=excluded.algorithm, revision=excluded.revision,
            observed_ms=excluded.observed_ms, activity_ms=excluded.activity_ms,
            last_activity_ms=excluded.last_activity_ms, latest_activity_ms=excluded.latest_activity_ms,
            title_key=excluded.title_key, model_key=excluded.model_key, effort_key=excluded.effort_key,
            cost_key=excluded.cost_key, prompt_count=excluded.prompt_count,
            duration_ms=excluded.duration_ms, context_tokens=excluded.context_tokens
        WHERE (excluded.observed_ms, excluded.partition, excluded.revision) >=
              (ready_sessions.observed_ms, ready_sessions.partition, ready_sessions.revision)''', values)


def read_ready(db, *, offset, size, sort, direction, start_ms, end_ms):
    column = SORT_COLUMNS[sort]
    order = 'DESC' if direction == -1 else 'ASC'
    if start_ms is None:
        predicate, bounds = '1', ()
    else:
        predicate = '(last_activity_ms >= ? AND last_activity_ms < ?) OR (latest_activity_ms >= ? AND latest_activity_ms < ?)'
        bounds = (max(1, start_ms), end_ms) * 2
    total = db.execute(f'SELECT count(*) FROM ready_sessions WHERE {predicate}', bounds).fetchone()[0]
    offset = min(offset, max(0, (total - 1) // size) * size)
    rows = db.execute(f'''SELECT f.item, f.revision, f.observed_ms, f.value, f.partition
        FROM (
            SELECT item, partition, algorithm, {column} AS sort_key
            FROM ready_sessions WHERE {predicate}
            ORDER BY {column} IS NULL, {column} {order}, item
            LIMIT ? OFFSET ?
        ) AS page JOIN facts AS f ON f.partition=page.partition AND f.domain=? AND
                                   f.algorithm=page.algorithm AND f.item=page.item
        ORDER BY page.sort_key IS NULL, page.sort_key {order}, page.item''',
        (*bounds, size, offset, SESSIONS_DOMAIN)).fetchall()
    return total, offset, rows
