"""Finish the bounded fold once all sparse physical parents are materialized."""
from .display_request_install import current_slot_scope
from .display_request_materialize import _savepoint
from .display_request_stage import STAGE_ROWS


DRAIN_SCHEMA = """
    CREATE TABLE archive_slot_drain(
        attempt TEXT PRIMARY KEY REFERENCES archive_request_preparations(attempt),
        phase TEXT NOT NULL DEFAULT 'forks',
        after_key BLOB, after_prompt TEXT
    ) WITHOUT ROWID;
"""


def drain_slot_page(db, slot, witness, *, eligible):
    """True retires the fully folded slot; False has more work; None is stale.

    The caller coordinates the writer transaction. Contributions are positive
    only. Neither a staged roster nor a completed drain asserts readiness.
    """
    if not db.in_transaction:
        raise ValueError("request drain requires a writer transaction")
    scope = current_slot_scope(db, slot, witness) if eligible() else None
    if scope is None:
        return None
    if db.execute("SELECT 1 FROM archive_prepare_requests WHERE source=? LIMIT 1", (slot.attempt,)).fetchone():
        return False
    with _savepoint(db, "archive_drain_slot") as rollback:
        db.execute("INSERT OR IGNORE INTO archive_slot_drain(attempt) VALUES(?)", (slot.attempt,))
        phase, key, prompt = db.execute(
            "SELECT phase,after_key,after_prompt FROM archive_slot_drain WHERE attempt=?", (slot.attempt,)).fetchone()
        finished = False
        if phase == "forks":
            _fork_page(db, slot, witness.source)
        elif phase == "members":
            _member_page(db, slot, witness, scope, key)
        elif phase == "edges":
            _edge_page(db, slot, witness.source, scope, key, prompt)
        elif phase == "retire":
            db.execute("UPDATE archive_request_rosters SET revision=?,pricing=? WHERE source=? AND root_id=?",
                       (scope.revision, witness.pricing, witness.source, scope.root))
            db.execute("DELETE FROM archive_request_slots WHERE source=? AND attempt=?", (witness.source, slot.attempt))
            db.execute("DELETE FROM archive_slot_drain WHERE attempt=?", (slot.attempt,))
            finished = True
        else:
            raise ValueError("invalid_request_drain_phase")
        if not eligible():
            rollback()
            return None
        return finished


def _fork_page(db, slot, source):
    rows = db.execute("""
        SELECT fork_key,dedup_tree,multiplicity,first_ordinal,first_session
        FROM archive_prepare_forks WHERE attempt=? AND done ORDER BY fork_key,dedup_tree LIMIT ?
    """, (slot.attempt, STAGE_ROWS)).fetchall()
    for fork, tree, count, ordinal, session in rows:
        if count:
            db.execute("""
                INSERT INTO archive_fork_trees VALUES(?,?,?,?,?,?)
                ON CONFLICT(source,fork_key,dedup_tree) DO UPDATE SET
                    (multiplicity,first_ordinal,first_session)=
                    (excluded.multiplicity,excluded.first_ordinal,excluded.first_session)
            """, (source, fork, tree, count, ordinal, session))
        else:
            db.execute("DELETE FROM archive_fork_trees WHERE source=? AND fork_key=? AND dedup_tree=?",
                       (source, fork, tree))
        db.execute("DELETE FROM archive_prepare_forks WHERE attempt=? AND fork_key=? AND dedup_tree=?",
                   (slot.attempt, fork, tree))
    if len(rows) < STAGE_ROWS:
        _progress(db, slot, "members")


def _member_page(db, slot, witness, scope, key):
    # Some roots already have retained evidence. Do not replace that roster
    # or retract any prior members before this exact fold reaches EOF.
    db.execute("""
        INSERT INTO archive_request_rosters VALUES(?,?,?,?)
        ON CONFLICT(source,root_id) DO NOTHING
    """, (witness.source, scope.root, scope.revision, witness.pricing))
    seek = "AND request_key>?" if key is not None else ""
    rows = db.execute(f"""
        SELECT request_key FROM archive_input_requests WHERE source=? {seek} ORDER BY request_key LIMIT ?
    """, (scope.run, *((key,) if key is not None else ()), STAGE_ROWS)).fetchall()
    db.executemany("INSERT OR IGNORE INTO archive_request_membership VALUES(?,?,?)",
                   ((witness.source, scope.root, request) for request, in rows))
    if len(rows) < STAGE_ROWS:
        _progress(db, slot, "edges")
    else:
        _progress(db, slot, "members", rows[-1][0])


def _edge_page(db, slot, source, scope, key, prompt):
    query = """
        SELECT request_key,prompt_id FROM archive_input_attribution WHERE run=? {seek}
        ORDER BY request_key,prompt_id LIMIT ?
    """
    if key is None:
        rows = db.execute(query.format(seek=""), (scope.run, STAGE_ROWS)).fetchall()
    else:
        rows = db.execute(query.format(seek="AND request_key=? AND prompt_id>?"),
                          (scope.run, key, prompt, STAGE_ROWS)).fetchall()
        if len(rows) < STAGE_ROWS:
            rows.extend(db.execute(query.format(seek="AND request_key>?"),
                                   (scope.run, key, STAGE_ROWS - len(rows))).fetchall())
    db.executemany("INSERT OR IGNORE INTO archive_prompt_attribution VALUES(?,?,?,?)",
                   ((source, scope.root, request, prompt) for request, prompt in rows))
    if len(rows) < STAGE_ROWS:
        _progress(db, slot, "retire")
    else:
        _progress(db, slot, "edges", *rows[-1])


def _progress(db, slot, phase, key=None, prompt=None):
    db.execute("UPDATE archive_slot_drain SET phase=?,after_key=?,after_prompt=? WHERE attempt=?",
               (phase, key, prompt, slot.attempt))
