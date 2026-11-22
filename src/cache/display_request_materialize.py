"""Private per-key timing write for a newly inserted slot request."""
from .display_requests import REQUEST_COLUMNS


_COLUMNS = ",".join(REQUEST_COLUMNS)
_STAGED_COLUMNS = ",".join(f"p.{column}" for column in REQUEST_COLUMNS)


def materialize_slot_timing(db, slot, witness, key, *, eligible):
    """Materialize one unavailable FK parent and its timing atomically.

    This handles insertions only, not replacements or unrelated row writers.
    The caller must own the shared writer transaction and current binding.
    """
    if not db.in_transaction:
        raise ValueError("request materialization requires a writer transaction")
    if not eligible():
        return False
    row = db.execute(f"""
        SELECT {_STAGED_COLUMNS},i.timing_start,i.timing_duration,i.timing_excluded
        FROM archive_request_slots AS s
        JOIN archive_request_preparations AS a USING(attempt)
        JOIN archive_request_inputs AS x USING(run)
        JOIN sources AS b ON b.source=s.source
        JOIN sessions AS root ON root.source=s.source AND root.session_id=x.root_id
        LEFT JOIN session_progress AS r ON root.source=r.source AND root.session_id=r.session_id
        LEFT JOIN archive_usage_revisions AS u ON u.source=s.source
        LEFT JOIN archive_stats_revisions AS e ON e.source=s.source
        LEFT JOIN archive_stats_geometry_revisions AS g ON g.source=s.source
        JOIN archive_prepare_requests AS p ON p.source=s.attempt AND p.request_key=?
        JOIN archive_input_requests AS i ON i.source=x.run AND i.request_key=p.request_key
        WHERE s.source=? AND (s.attempt,s.birth,s.layout)=(?,?,?)
          AND x.source=s.source AND x.archive_epoch=b.archive_epoch
          AND (x.binding,x.incarnation,x.pricing,x.dependency)=(?,?,?,?)
          AND root.source_present AND root.revision=x.revision AND coalesce(r.progress,0)=x.progress
          AND coalesce(u.revision,0)=s.birth
          AND coalesce(e.revision,0)=? AND coalesce(g.revision,0)=?
          AND p.first_revision IS NULL AND i.timing_excluded IS NOT NULL AND p.clock_ms IS i.clock_ms
    """, (key, witness.source, slot.attempt, slot.birth, slot.layout, witness.binding, witness.incarnation,
          witness.pricing, witness.dependency, witness.evidence, witness.geometry)).fetchone()
    if row is None:
        return False

    db.execute("SAVEPOINT archive_materialize_timing")
    try:
        if not _materialize(db, slot, witness, key, row) or not eligible():
            db.execute("ROLLBACK TO archive_materialize_timing")
            return False
        return True
    except BaseException:
        db.execute("ROLLBACK TO archive_materialize_timing")
        raise
    finally:
        db.execute("RELEASE archive_materialize_timing")


def _materialize(db, slot, witness, key, row):
    request, timing = row[:-3], row[-3:]
    marks = ",".join("?" for _ in request)
    if not db.execute(f"""
        INSERT INTO archive_requests(source,{_COLUMNS},first_revision) VALUES(?,{marks},?)
        ON CONFLICT(source,request_key) DO NOTHING
    """, (witness.source, *request, slot.birth)).rowcount:
        return False
    db.execute("DELETE FROM archive_prepare_requests WHERE source=? AND request_key=?", (slot.attempt, key))
    db.execute("UPDATE archive_request_slots SET layout=layout+1 WHERE source=?", (witness.source,))
    new_evidence = witness.evidence + 1
    db.execute("""
        INSERT INTO archive_response_timing VALUES(?,?,?,?,?,?,?)
    """, (witness.source, key, request[1], *timing, new_evidence))
    db.execute("""
        INSERT INTO archive_stats_revisions(source,revision) VALUES(?,?)
        ON CONFLICT(source) DO UPDATE SET revision=excluded.revision
    """, (witness.source, new_evidence))
    return True
