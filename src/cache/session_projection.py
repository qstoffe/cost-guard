"""Indexed ready Sessions metadata; display payloads are loaded only for the page."""
from contextlib import closing
import json
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
TERMINAL_HIGHLIGHT_MS = 30_000
HISTORICAL_QUALIFIERS = {
    'activity_qualified': True, 'context_qualified': True,
    'model_pending': False, 'effort_qualified': True, 'effort_pending': False,
}


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


def create_runtime_schema(db):
    db.execute('''CREATE TABLE session_runtime (
        run TEXT PRIMARY KEY,
        state TEXT NOT NULL,
        terminal INTEGER NOT NULL
    ) WITHOUT ROWID''')
    db.execute('''CREATE TABLE session_pending (
        run TEXT NOT NULL,
        item TEXT NOT NULL,
        activity_ms INTEGER,
        unavailable INTEGER NOT NULL,
        PRIMARY KEY(run, item)
    ) WITHOUT ROWID''')
    db.execute('''CREATE INDEX session_pending_window
        ON session_pending (run, unavailable, activity_ms)''')
    db.execute('''CREATE TABLE session_live (
        run TEXT NOT NULL,
        item TEXT NOT NULL,
        start_ms INTEGER,
        finish_ms INTEGER,
        last_activity_ms INTEGER,
        latest_activity_ms INTEGER,
        payload TEXT NOT NULL,
        finalizing INTEGER NOT NULL DEFAULT 0,
        activity_order_ms INTEGER,
        PRIMARY KEY(run, item)
    ) WITHOUT ROWID''')


def upgrade_runtime_schema(db):
    db.execute('ALTER TABLE session_live ADD COLUMN finalizing INTEGER NOT NULL DEFAULT 0')


def add_runtime_activity_order(db):
    db.execute('ALTER TABLE session_live ADD COLUMN activity_order_ms INTEGER')


def reconcile_ready_index(db):
    """Remove unsupported pointers, keeping every durable history fact."""
    # Require the committed revision and the evidence used by the writer's
    # admission gate. An old display flag never revives Running in this index.
    flags = ' AND '.join(f"json_type(f.value, '$.row.{name}') IS '{str(expected).lower()}'"
                         for name, expected in HISTORICAL_QUALIFIERS.items())
    db.execute(f'''DELETE FROM ready_sessions AS r WHERE NOT EXISTS (
        SELECT 1 FROM facts AS f
        WHERE f.partition=r.partition AND f.domain=? AND f.algorithm=r.algorithm
          AND f.item=r.item AND f.revision=r.revision AND f.observed_ms=r.observed_ms
          AND CASE WHEN json_valid(f.value) THEN
            json_extract(f.value, '$.row.session_id') = r.item
            AND json_type(f.value, '$.row.title') IS 'text' AND {flags} END
        )''', (SESSIONS_DOMAIN,))
    # A legacy projection with partial/absent valuation must sort with the
    # unknowns even if its stored subtotal was encoded as zero.
    db.execute('''UPDATE ready_sessions AS r SET cost_key=NULL WHERE cost_key IS NOT NULL
        AND EXISTS (SELECT 1 FROM facts AS f WHERE f.partition=r.partition
          AND f.domain=? AND f.algorithm=r.algorithm AND f.item=r.item
          AND (json_type(f.value, '$.row.complete') IS NOT 'true'
            OR json_extract(f.value, '$.row.ccost') IS NULL
            OR json_extract(f.value, '$.row.ccost') IN ('None', '', 'N/A')))''', (SESSIONS_DOMAIN,))
    for name in ('prompt_count', 'duration_ms', 'context_tokens'):
        db.execute(f'''UPDATE ready_sessions AS r SET {name}=NULL WHERE {name} IS NOT NULL
            AND EXISTS (SELECT 1 FROM facts AS f WHERE f.partition=r.partition
                AND f.domain=? AND f.algorithm=r.algorithm AND f.item=r.item
                AND (json_type(f.value, '$.row.{name}') IS NOT 'integer'
                     OR json_extract(f.value, '$.row.{name}') NOT BETWEEN 0 AND 9007199254740991))''',
            (SESSIONS_DOMAIN,))


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
    cursor = db.execute('''INSERT INTO ready_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(item) DO UPDATE SET
            partition=excluded.partition, algorithm=excluded.algorithm, revision=excluded.revision,
            observed_ms=excluded.observed_ms, activity_ms=excluded.activity_ms,
            last_activity_ms=excluded.last_activity_ms, latest_activity_ms=excluded.latest_activity_ms,
            title_key=excluded.title_key, model_key=excluded.model_key, effort_key=excluded.effort_key,
            cost_key=excluded.cost_key, prompt_count=excluded.prompt_count,
            duration_ms=excluded.duration_ms, context_tokens=excluded.context_tokens
        WHERE (excluded.observed_ms, excluded.partition, excluded.revision) >=
               (ready_sessions.observed_ms, ready_sessions.partition, ready_sessions.revision)''', values)
    return bool(cursor.rowcount)


def _ready_window(start_ms, end_ms):
    if start_ms is None:
        # Preserve recorded sessions with unknown activity; known future-only ones are not yet eligible.
        return '''(last_activity_ms < ? OR latest_activity_ms < ? OR
                   (last_activity_ms IS NULL AND latest_activity_ms IS NULL))''', (end_ms, end_ms)
    return ('''((last_activity_ms >= ? AND last_activity_ms < ?) OR
                (latest_activity_ms >= ? AND latest_activity_ms < ?))''',
             (max(1, start_ms), end_ms) * 2)


def next_ready_activity(db, now):
    stamps = (db.execute(f'SELECT min({column}) FROM ready_sessions WHERE {column}>?', (now,)).fetchone()[0]
              for column in ('last_activity_ms', 'latest_activity_ms'))
    return min((stamp for stamp in stamps if stamp is not None), default=None)


def read_ready(db, *, offset, size, sort, direction, start_ms, end_ms):
    column = SORT_COLUMNS[sort]
    order = 'DESC' if direction == -1 else 'ASC'
    predicate, bounds = _ready_window(start_ms, end_ms)
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


def _page_rows(encoded):
    # Explicit ordinals keep the result independent of aggregate input order.
    return [tuple(row[1:]) for row in sorted(json.loads(encoded))]


def read_runtime_page(db, *, offset, size, sort, direction, start_ms, end_ms, run, finish_cutoff, query=''):
    """Read coverage, counts and the visible slice in one SQLite result row."""
    column = SORT_COLUMNS[sort]
    order = 'DESC' if direction == -1 else 'ASC'
    ready_window, ready_bounds = _ready_window(start_ms, end_ms)
    # The same eligible live set shadows history for both count and page.
    history = f'{ready_window} AND item NOT IN (SELECT item FROM live)'
    live_title, live_filter, live_bounds = '', '1', ()
    if query:
        db.create_function('casefold', 1, lambda title: (title or '').casefold(), deterministic=True)
        live_title = ", casefold(json_extract(payload, '$.title')) AS title_key"
        live_filter = '(instr(title_key, ?) OR instr(lower(item), ?))'
        live_bounds = (query, query)
        history += ' AND (instr(title_key, ?) OR instr(lower(item), ?))'
        ready_bounds += live_bounds
    pending_window, pending_bounds = '1', ()
    if start_ms is not None:
        pending_window = '(activity_ms IS NULL OR (activity_ms>=? AND activity_ms<?))'
        pending_bounds = (max(1, start_ms), end_ms)

    # Keep payloads out of the counts, sort and offset work. JSON transports
    # only the visible slice; payloads remain unmodified strings.
    with closing(db.execute(f'''WITH
        args(run, requested, size) AS (VALUES (?, ?, ?)),
        live AS (
            SELECT item, start_ms, finish_ms, coalesce(start_ms, activity_order_ms) AS order_ms, EXISTS (
                SELECT 1 FROM ready_sessions WHERE ready_sessions.item=session_live.item
            ) AS saved {live_title}
            FROM session_live WHERE run=(SELECT run FROM args)
              -- Like Running, unfinished handoffs span local calendar boundaries.
              AND (start_ms < ? OR (finish_ms < ? AND (finalizing OR finish_ms >= ?)))
        ),
        matching_live AS (SELECT * FROM live WHERE {live_filter}),
        counts AS (
            SELECT count(*) AS live_count, coalesce(sum(saved), 0) AS saved_count,
                   (SELECT count(*) FROM ready_sessions WHERE {history}) AS history_count
            FROM matching_live
        ),
        position AS (
            SELECT counts.*, size, min(requested, (max(0, live_count + history_count - 1) / size) * size) AS offset
            FROM counts CROSS JOIN args
        ),
        history_slice AS (
            SELECT item, partition, algorithm, {column} AS sort_key
            FROM ready_sessions WHERE {history}
            ORDER BY {column} IS NULL, {column} {order}, item
            LIMIT (SELECT size - max(0, min(size, live_count - offset)) FROM position)
            OFFSET (SELECT max(0, offset - live_count) FROM position)
        ),
        history_page AS (
            SELECT *, row_number() OVER (ORDER BY sort_key IS NULL, sort_key {order}, item) AS ordinal
            FROM history_slice
        ),
        live_page AS (
            SELECT *, row_number() OVER (ORDER BY order_ms DESC, item DESC) AS ordinal
            FROM matching_live
        )
        SELECT live_count + history_count, offset, saved_count + history_count,
            runtime.state, runtime.terminal,
            NOT EXISTS (SELECT 1 FROM session_pending AS p
                        WHERE p.run=args.run AND unavailable=0 AND {pending_window}),
            (SELECT count(*) FROM session_pending AS p
             WHERE p.run=args.run AND unavailable=1 AND {pending_window}),
            (SELECT json_group_array(json_array(page.ordinal, f.item, f.revision, f.observed_ms, f.value, f.partition))
             FROM history_page AS page JOIN facts AS f
             ON f.partition=page.partition AND f.domain=? AND f.algorithm=page.algorithm AND f.item=page.item),
            (SELECT json_group_array(json_array(page.ordinal, page.item, s.payload, page.start_ms,
                                               page.finish_ms, page.saved))
             FROM live_page AS page JOIN session_live AS s ON s.run=args.run AND s.item=page.item
             WHERE page.ordinal > position.offset AND page.ordinal <= position.offset + position.size)
        FROM position CROSS JOIN args
        LEFT JOIN session_runtime AS runtime ON runtime.run=args.run''',
         (run, offset, size, end_ms, end_ms, finish_cutoff, *live_bounds, *ready_bounds, *ready_bounds,
          *pending_bounds, *pending_bounds, SESSIONS_DOMAIN))) as cursor:
        row = cursor.fetchone()
    total, offset, cached, state, terminal, complete, unavailable, historical, live = row
    runtime = None if state is None else (state, terminal)
    return total, offset, _page_rows(historical), _page_rows(live), cached, runtime, (bool(complete), unavailable)


def update_runtime(db, run, *, state, terminal, reset_pending, pending, live):
    db.execute('''INSERT INTO session_runtime VALUES (?, ?, ?)
        ON CONFLICT(run) DO UPDATE SET state=excluded.state, terminal=excluded.terminal''',
        (run, state, terminal))
    if reset_pending:
        db.execute('DELETE FROM session_pending WHERE run=?', (run,))
    for key, value in pending.items():
        if value is None:
            db.execute('DELETE FROM session_pending WHERE run=? AND item=?', (run, key))
        else:
            db.execute('''INSERT INTO session_pending VALUES (?, ?, ?, ?)
                ON CONFLICT(run, item) DO UPDATE SET activity_ms=excluded.activity_ms,
                    unavailable=excluded.unavailable''', (run, key, *value))
    for key, value in live.items():
        if value is None:
            db.execute('DELETE FROM session_live WHERE run=? AND item=?', (run, key))
        else:
            db.execute('''INSERT INTO session_live (run, item, start_ms, finish_ms, last_activity_ms,
                             latest_activity_ms, payload, finalizing, activity_order_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run, item) DO UPDATE SET start_ms=excluded.start_ms, finish_ms=excluded.finish_ms,
                    last_activity_ms=excluded.last_activity_ms, latest_activity_ms=excluded.latest_activity_ms,
                    payload=excluded.payload, finalizing=excluded.finalizing,
                    activity_order_ms=excluded.activity_order_ms''', (run, key, *value))


def close_runtime(db, run):
    db.execute('DELETE FROM session_live WHERE run=?', (run,))
    db.execute('DELETE FROM session_pending WHERE run=?', (run,))
    db.execute('DELETE FROM session_runtime WHERE run=?', (run,))
