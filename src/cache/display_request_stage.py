"""Private normalized request input and preparation; no publication authority."""
from dataclasses import dataclass

from .display_requests import REQUEST_COLUMNS, DisplayRequest, request_table_schema, upsert_request_values
from .display_usage_reader import usage_version


STAGE_ROWS = 32
STAGE_BYTES = 128 * 1024
_COLUMNS = ",".join(REQUEST_COLUMNS)
_MARKS = ",".join("?" for _ in REQUEST_COLUMNS)


@dataclass(frozen=True, slots=True)
class RequestInputScope:
    source: str
    binding: str
    archive_epoch: int
    incarnation: int
    root_id: str
    revision: str
    progress: int
    pricing: str
    dependency: str


def request_stage_schema():
    # Not installed by DisplayHistory until there is an owner for recovery,
    # publication and bounded disposal. Repository tests install it in place.
    return """
        CREATE TABLE archive_request_inputs (
            run TEXT PRIMARY KEY,
            source TEXT NOT NULL, binding TEXT NOT NULL, archive_epoch INTEGER NOT NULL,
            incarnation INTEGER NOT NULL, root_id TEXT NOT NULL, revision TEXT NOT NULL,
            progress INTEGER NOT NULL, pricing TEXT NOT NULL, dependency TEXT NOT NULL,
            next_page INTEGER NOT NULL DEFAULT 0, sealed INTEGER NOT NULL DEFAULT 0,
            edges_started INTEGER NOT NULL DEFAULT 0
        ) WITHOUT ROWID;
        CREATE TABLE archive_request_preparations (
            attempt TEXT PRIMARY KEY, run TEXT NOT NULL REFERENCES archive_request_inputs(run),
            usage_revision INTEGER NOT NULL, after_key BLOB, sealed INTEGER NOT NULL DEFAULT 0,
            edits INTEGER NOT NULL DEFAULT 0
        ) WITHOUT ROWID;
        CREATE TABLE archive_prepare_forks (
            attempt TEXT NOT NULL REFERENCES archive_request_preparations(attempt),
            fork_key BLOB NOT NULL, dedup_tree TEXT NOT NULL, change INTEGER NOT NULL,
            after_ordinal INTEGER, after_session TEXT, after_key BLOB,
            multiplicity INTEGER, first_ordinal INTEGER, first_session TEXT, done INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(attempt,fork_key,dedup_tree)
        ) WITHOUT ROWID;
        CREATE INDEX archive_prepare_pending_forks ON archive_prepare_forks(attempt,fork_key,dedup_tree)
            WHERE NOT done;
    """ + request_table_schema(
        "archive_input_requests", "REFERENCES archive_request_inputs(run)",
        extra_columns="""
            timing_start INTEGER, timing_duration INTEGER, timing_excluded INTEGER,
            message_key BLOB, step_key BLOB, sample_hash BLOB, source_model_key BLOB, stats_effort TEXT,
        """,
    ) + """
        CREATE TABLE archive_input_attribution(
            run TEXT NOT NULL, request_key BLOB NOT NULL, prompt_id TEXT NOT NULL,
            PRIMARY KEY(run,request_key,prompt_id),
            FOREIGN KEY(run,request_key) REFERENCES archive_input_requests(source,request_key)
        ) WITHOUT ROWID;
    """ + request_table_schema(
        "archive_prepare_requests", "REFERENCES archive_request_preparations(attempt)",
        extra_columns="first_revision INTEGER,",
    ) + """
        CREATE INDEX archive_prepare_candidates ON archive_prepare_requests(
            source,fork_key,dedup_tree,request_ordinal,session_id,request_key);
        CREATE INDEX archive_prepare_clock ON archive_prepare_requests(source,clock_ms,request_key);
    """


def open_request_input(db, run, scope):
    """Caller owns the writer transaction and qualified acquisition scope."""
    if not (run and scope.source and scope.binding and scope.root_id and scope.revision
            and scope.pricing and scope.dependency):
        raise ValueError("invalid_request_input_scope")
    if usage_version(db, scope.source).archive_epoch != scope.archive_epoch:
        return False
    db.execute("""
        INSERT INTO archive_request_inputs(run,source,binding,archive_epoch,incarnation,root_id,
                                           revision,progress,pricing,dependency)
        VALUES(?,?,?,?,?,?,?,?,?,?)
    """, (run, scope.source, scope.binding, scope.archive_epoch, scope.incarnation, scope.root_id,
          scope.revision, scope.progress, scope.pricing, scope.dependency))
    return True


def _input_row(request, pricing, root):
    if (not isinstance(request, DisplayRequest) or not isinstance(request.key, bytes) or not request.key
            or request.dedup_tree not in (None, root)):
        raise ValueError("invalid_staged_request")
    timing, identity = request.response, request.stats_identity
    return (*request.values(pricing), *((timing.start_ms, timing.duration_ms, timing.excluded)
                                       if timing is not None else (None,) * 3),
            *((identity.message_key, identity.step_key, identity.sample_hash,
               identity.source_model_key, identity.effort) if identity is not None else (None,) * 5))


def _open_input(db, run, page):
    row = db.execute("""
        SELECT i.root_id,i.pricing,i.edges_started FROM archive_request_inputs AS i
        JOIN sources AS s USING(source)
        WHERE run=? AND NOT sealed AND next_page=? AND s.archive_epoch=i.archive_epoch
    """, (run, page)).fetchone()
    return row


def append_request_input(db, run, page, requests):
    """Accept one ordered typed page; never fill a gap or overwrite an identity."""
    if not isinstance(requests, tuple) or not 1 <= len(requests) <= STAGE_ROWS:
        raise ValueError("invalid_request_input_page")
    state = _open_input(db, run, page)
    if state is None or state[2]:
        return False
    root, pricing, _ = state
    rows = tuple(_input_row(request, pricing, root) for request in requests)
    size = sum(len(value.encode("utf-8")) if isinstance(value, str) else len(value) if isinstance(value, bytes) else 8
               for row in rows for value in row)
    if size > STAGE_BYTES:
        raise ValueError("request_input_page_exceeds_size")
    db.executemany(f"""
        INSERT INTO archive_input_requests(
            source,{_COLUMNS},timing_start,timing_duration,timing_excluded,
            message_key,step_key,sample_hash,source_model_key,stats_effort)
        VALUES(?,{_MARKS},?,?,?,?,?,?,?,?)
    """, ((run, *row) for row in rows))
    _advance_input(db, run)
    return True


def append_request_attribution(db, run, page, edges):
    """Stage bounded positive causal edges to already captured physical rows."""
    if not isinstance(edges, tuple) or not 1 <= len(edges) <= STAGE_ROWS:
        raise ValueError("invalid_request_attribution_page")
    if _open_input(db, run, page) is None:
        return False
    size = 0
    for key, prompt in edges:
        if not isinstance(key, bytes) or not key or not isinstance(prompt, str) or not prompt:
            raise ValueError("invalid_request_attribution")
        size += len(key) + len(prompt.encode("utf-8"))
        if size > STAGE_BYTES:
            raise ValueError("request_attribution_page_exceeds_size")
        if not db.execute("SELECT 1 FROM archive_input_requests WHERE source=? AND request_key=?",
                          (run, key)).fetchone():
            raise ValueError("request_attribution_without_request")
    db.executemany("INSERT INTO archive_input_attribution VALUES(?,?,?)",
                   ((run, key, prompt) for key, prompt in edges))
    _advance_input(db, run, edges_started=True)
    return True


def _advance_input(db, run, *, edges_started=False):
    db.execute("UPDATE archive_request_inputs SET next_page=next_page+1,edges_started=? WHERE run=?",
               (edges_started, run))


def seal_request_input(db, run, page):
    """Call only after qualified EOF; this is not display or coverage readiness."""
    if _open_input(db, run, page) is None:
        return False
    db.execute("UPDATE archive_request_inputs SET sealed=1 WHERE run=?", (run,))
    return True


def open_request_preparation(db, run, attempt):
    row = db.execute("SELECT source,archive_epoch FROM archive_request_inputs WHERE run=? AND sealed",
                     (run,)).fetchone()
    if row is None:
        return False
    source, epoch = row
    version = usage_version(db, source)
    if version.archive_epoch != epoch:
        return False
    db.execute("INSERT INTO archive_request_preparations(attempt,run,usage_revision) VALUES(?,?,?)",
               (attempt, run, version.revision))
    return True


def prepare_request_page(db, attempt):
    """Return True at EOF, False for more, None for stale; no visible writes."""
    state = db.execute("""
        SELECT i.run,i.source,i.archive_epoch,p.usage_revision,p.after_key
        FROM archive_request_preparations AS p JOIN archive_request_inputs AS i USING(run)
        WHERE p.attempt=? AND NOT p.sealed
    """, (attempt,)).fetchone()
    if state is None:
        return None
    run, source, epoch, revision, after = state
    version = usage_version(db, source)
    if (version.archive_epoch, version.revision) != (epoch, revision):
        return None
    resume = "AND request_key>?" if after is not None else ""
    rows = db.execute(f"""
        SELECT {_COLUMNS} FROM archive_input_requests
        WHERE source=? {resume} ORDER BY request_key LIMIT ?
    """, (run, *((after,) if after is not None else ()), STAGE_ROWS)).fetchall()
    keys = tuple(row[0] for row in rows)
    edits = 0
    if keys:
        params = ",".join("?" for _ in keys)
        db.execute(f"""
            INSERT INTO archive_prepare_requests(source,first_revision,{_COLUMNS})
            SELECT ?,first_revision,{_COLUMNS} FROM archive_requests
            WHERE source=? AND request_key IN ({params})
        """, (attempt, source, *keys))
        edits = upsert_request_values(db, attempt, None, rows, private=True)
        _discard_identical(db, source, attempt, keys, params)
        _mark_fork_changes(db, source, attempt, keys, params)
    eof = len(rows) < STAGE_ROWS
    db.execute("UPDATE archive_request_preparations SET after_key=?,sealed=?,edits=edits+? WHERE attempt=?",
               (keys[-1] if keys else after, eof, edits, attempt))
    return eof


def _discard_identical(db, source, attempt, keys, params):
    base = ",".join(f"b.{col}" for col in REQUEST_COLUMNS[1:])
    staged = ",".join(f"p.{col}" for col in REQUEST_COLUMNS[1:])
    db.execute(f"""
        DELETE FROM archive_prepare_requests AS p WHERE p.source=? AND p.request_key IN ({params})
          AND EXISTS(SELECT 1 FROM archive_requests AS b
              WHERE b.source=? AND b.request_key=p.request_key AND ({base}) IS ({staged}))
    """, (attempt, *keys, source))


def _mark_fork_changes(db, source, attempt, keys, params):
    rows = db.execute(f"""
        SELECT b.fork_key,b.dedup_tree,p.fork_key,p.dedup_tree
        FROM archive_prepare_requests AS p LEFT JOIN archive_requests AS b
        ON b.source=? AND b.request_key=p.request_key
        WHERE p.source=? AND p.request_key IN ({params})
          AND (b.fork_key,b.dedup_tree,b.request_ordinal,b.session_id)
              IS NOT (p.fork_key,p.dedup_tree,p.request_ordinal,p.session_id)
    """, (source, attempt, *keys)).fetchall()
    db.executemany("""
        INSERT INTO archive_prepare_forks(attempt,fork_key,dedup_tree,change) VALUES(?,?,?,?)
        ON CONFLICT(attempt,fork_key,dedup_tree) DO UPDATE SET change=change+excluded.change
    """, ((attempt, fork, tree, delta)
           for old_fork, old_tree, new_fork, new_tree in rows
           for fork, tree, delta in ((old_fork, old_tree, -1), (new_fork, new_tree, 1))
           if fork is not None and tree is not None))


def _pending_fork(db, attempt):
    return db.execute("""
        SELECT fork_key,dedup_tree,change,after_ordinal,after_session,after_key
        FROM archive_prepare_forks INDEXED BY archive_prepare_pending_forks WHERE attempt=? AND NOT done
        ORDER BY fork_key,dedup_tree LIMIT 1
    """, (attempt,)).fetchone()


def prepare_fork_page(db, attempt):
    """Resolve one affected tree or one seek page through shadowed candidates."""
    state = db.execute("""
        SELECT i.source,i.archive_epoch,p.usage_revision
        FROM archive_request_preparations AS p JOIN archive_request_inputs AS i USING(run)
        WHERE p.attempt=? AND p.sealed
    """, (attempt,)).fetchone()
    if state is None:
        return None
    source, epoch, revision = state
    version = usage_version(db, source)
    if (version.archive_epoch, version.revision) != (epoch, revision):
        return None
    pending = _pending_fork(db, attempt)
    if pending is None:
        return True
    fork, tree, change, ordinal, session, key = pending
    previous = db.execute("""
        SELECT multiplicity FROM archive_fork_trees WHERE source=? AND fork_key=? AND dedup_tree=?
    """, (source, fork, tree)).fetchone()
    count = (previous[0] if previous else 0) + change
    if count < 0:
        raise ValueError("invalid_prepared_fork_multiplicity")
    first = None
    if count:
        base, after = _first_unshadowed(db, source, fork, tree, attempt, (ordinal, session, key))
        if after is not None:
            db.execute("""
                UPDATE archive_prepare_forks SET (after_ordinal,after_session,after_key)=(?,?,?)
                WHERE attempt=? AND fork_key=? AND dedup_tree=?
            """, (*after, attempt, fork, tree))
            return False
        overlay = db.execute("""
            SELECT request_ordinal,session_id,request_key
            FROM archive_prepare_requests INDEXED BY archive_prepare_candidates
            WHERE source=? AND fork_key=? AND dedup_tree=?
            ORDER BY request_ordinal,session_id,request_key LIMIT 1
        """, (attempt, fork, tree)).fetchone()
        first = min((row for row in (base, overlay) if row is not None), default=None)
        if first is None:
            raise ValueError("missing_prepared_fork_candidate")
    db.execute("""
        UPDATE archive_prepare_forks SET (multiplicity,first_ordinal,first_session,done)=(?,?,?,1)
        WHERE attempt=? AND fork_key=? AND dedup_tree=?
    """, (count, *(first[:2] if first is not None else (None, None)), attempt, fork, tree))
    return False


def _first_unshadowed(db, source, fork, tree, attempt, after):
    # Slice the base stream before checking shadows. Filtering shadows first
    # could walk every old candidate in one ostensibly bounded LIMIT query.
    if after[2] is None:
        rows = _base_fork_candidates(db, source, fork, tree, attempt, "", (), STAGE_ROWS)
    else:
        # Row-value comparison can rescan the whole equal-clock prefix in
        # SQLite. Seek each disjoint range with an explicit scalar bound.
        rows = []
        ranges = (("AND request_ordinal=? AND session_id=? AND request_key>?", after),
                  ("AND request_ordinal=? AND session_id>?", after[:2]),
                  ("AND request_ordinal>?", after[:1]))
        for lower, args in ranges:
            if len(rows) == STAGE_ROWS:
                break
            rows.extend(_base_fork_candidates(db, source, fork, tree, attempt, lower, args, STAGE_ROWS - len(rows)))
    first = next((row[:3] for row in rows if not row[3]), None)
    return first, rows[-1][:3] if first is None and len(rows) == STAGE_ROWS else None


def _base_fork_candidates(db, source, fork, tree, attempt, lower, args, limit):
    return db.execute(f"""
        SELECT b.*,EXISTS(SELECT 1 FROM archive_prepare_requests AS p WHERE p.source=? AND p.request_key=b.request_key)
        FROM (
            SELECT request_ordinal,session_id,request_key
            FROM archive_requests INDEXED BY archive_fork_candidates
            WHERE source=? AND fork_key=? AND dedup_tree=?
              AND fork_key IS NOT NULL AND dedup_tree IS NOT NULL {lower}
            ORDER BY request_ordinal,session_id,request_key LIMIT ?
        ) AS b
    """, (attempt, source, fork, tree, *args, limit)).fetchall()
