"""Private per-key slot materialization and dependent timing writes."""
from contextlib import contextmanager

from .display_requests import REQUEST_COLUMNS
from .display_request_slot_stats import IDENTITY_SHAPE, slot_stats_recipe


_COLUMNS = ",".join(REQUEST_COLUMNS)
_STAGED_COLUMNS = ",".join(f"p.{column}" for column in REQUEST_COLUMNS)
_FOLD_COLUMNS = (*REQUEST_COLUMNS, "first_revision")


def fixture_usage_fold_schema():
    """Prepare a fixture database; do not install this in the live schema."""
    before = " AND ".join(f"OLD.{name} IS b.{name}" for name in _FOLD_COLUMNS)
    after = " AND ".join(f"NEW.{name} IS p.{name}" for name in _FOLD_COLUMNS)
    return f"""
    CREATE TABLE archive_usage_fold_guard(
        source TEXT PRIMARY KEY, attempt TEXT NOT NULL, request_key BLOB NOT NULL
    ) WITHOUT ROWID;
    DROP TRIGGER archive_usage_correction;
    CREATE TRIGGER archive_usage_correction AFTER UPDATE ON archive_requests
    WHEN NOT EXISTS(
        SELECT 1 FROM archive_usage_fold_guard g
        JOIN archive_prepare_before b ON b.source=g.attempt AND b.request_key=g.request_key
        JOIN archive_prepare_requests p ON p.source=g.attempt AND p.request_key=g.request_key
        WHERE OLD.source=g.source AND NEW.source=g.source AND {before} AND {after}
    ) BEGIN
        INSERT INTO archive_usage_revisions(source,revision,invalidated_through) VALUES(NEW.source,0,1)
        ON CONFLICT(source) DO UPDATE SET invalidated_through=revision+1;
    END;
    """


def fold_slot_correction(db, slot, witness, key, *, eligible):
    """Try one persisted replacement. The caller owns the shared writer lock.

    This fixture path exempts only the usage trigger. The old Stats identity
    must stay unavailable until a separately qualified write replaces it.
    """
    if not db.in_transaction:
        raise ValueError("request materialization requires a writer transaction")
    if not eligible():
        return False
    image = db.execute(f"""
        SELECT {_STAGED_COLUMNS},p.first_revision
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
        WHERE s.source=? AND (s.attempt,s.birth,s.layout)=(?,?,?)
          AND x.source=s.source AND x.archive_epoch=b.archive_epoch
          AND (x.binding,x.incarnation,x.pricing,x.dependency)=(?,?,?,?)
          AND root.source_present AND root.revision=x.revision AND coalesce(r.progress,0)=x.progress
          AND coalesce(u.revision,0)=s.birth
          AND coalesce(e.revision,0)=? AND coalesce(g.revision,0)=?
          AND p.first_revision IS NOT NULL
    """, _scope_args(slot, witness, key)).fetchone()
    if image is None:
        return False
    invalidation = _identity_invalidation(db, slot, witness.source, key)
    if invalidation is None:
        return False
    cols = ",".join(_FOLD_COLUMNS)
    same = " AND ".join(f"r.{name} IS b.{name}" for name in _FOLD_COLUMNS)
    marks = ",".join("?" for _ in image)
    with _savepoint(db, "archive_fold_correction") as rollback:
        db.execute("INSERT INTO archive_usage_fold_guard VALUES(?,?,?)", (witness.source, slot.attempt, key))
        applied = db.execute(f"""
            UPDATE archive_requests AS r SET ({cols})=({marks})
            WHERE r.source=? AND r.request_key=? AND EXISTS(
                SELECT 1 FROM archive_prepare_before b WHERE b.source=? AND b.request_key=? AND {same}
            )
        """, (*image, witness.source, key, slot.attempt, key)).rowcount
        db.execute("DELETE FROM archive_usage_fold_guard WHERE source=?", (witness.source,))
        if not applied or not eligible():
            rollback()
            return False
        if invalidation:
            _discard_incompatible_identity(db, witness.source, key, invalidation)
        db.execute("DELETE FROM archive_prepare_before WHERE source=? AND request_key=?", (slot.attempt, key))
        _retire(db, slot, witness.source, key)
        return True


def _identity_invalidation(db, slot, source, key):
    same = " AND ".join(f"b.{name} IS p.{name}" for name in IDENTITY_SHAPE)
    reusable = db.execute(f"""
        SELECT {same}, b.dedup_tree, p.dedup_tree, b.clock_ms IS p.clock_ms
        FROM archive_prepare_before b JOIN archive_prepare_requests p USING(source,request_key)
        WHERE b.source=? AND b.request_key=?
    """, (slot.attempt, key)).fetchone()
    if reusable is None:
        raise ValueError("missing_correction_before_image")
    keep_shape, prior_tree, current_tree, same_clock = reusable
    if same_clock and prior_tree != current_tree and db.execute(
            "SELECT 1 FROM archive_response_timing WHERE source=? AND request_key=?", (source, key)).fetchone():
        return None  # Keep timing evidence unavailable under the sparse conflicting tree.
    prior = db.execute("""
        SELECT message_key,step_key,sample_hash,source_model_key,effort,first_revision
        FROM archive_stats_request_identity WHERE source=? AND request_key=?
    """, (source, key)).fetchone()
    if prior is None:
        return ()
    observed = slot_stats_recipe(db, slot, key)
    if observed is None or observed[0] is None:
        return None  # No positive proof: keep old identity and the unresolved sparse image.
    return () if keep_shape and prior[:-1] == observed else (prior[-1], prior_tree, current_tree)


def _discard_incompatible_identity(db, source, key, invalidation):
    revision, prior_tree, current_tree = invalidation
    db.execute("""
        DELETE FROM archive_stats_request_identity WHERE source=? AND request_key=? AND first_revision=?
    """, (source, key, revision))
    db.execute("DELETE FROM archive_stats_request_ready WHERE source=? AND root_id IN (?,?)",
               (source, prior_tree, current_tree))


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
    """, _scope_args(slot, witness, key)).fetchone()
    if row is None:
        return False

    with _savepoint(db, "archive_materialize_timing") as rollback:
        if not _materialize(db, slot, witness, key, row) or not eligible():
            rollback()
            return False
        return True


def _scope_args(slot, witness, key):
    return (key, witness.source, slot.attempt, slot.birth, slot.layout, witness.binding, witness.incarnation,
            witness.pricing, witness.dependency, witness.evidence, witness.geometry)


@contextmanager
def _savepoint(db, name):
    def rollback():
        db.execute(f"ROLLBACK TO {name}")

    db.execute(f"SAVEPOINT {name}")
    try:
        yield rollback
    except BaseException:
        rollback()
        raise
    finally:
        db.execute(f"RELEASE {name}")


def _retire(db, slot, source, key):
    db.execute("DELETE FROM archive_prepare_requests WHERE source=? AND request_key=?", (slot.attempt, key))
    db.execute("UPDATE archive_request_slots SET layout=layout+1 WHERE source=?", (source,))


def _materialize(db, slot, witness, key, row):
    request, timing = row[:-3], row[-3:]
    marks = ",".join("?" for _ in request)
    if not db.execute(f"""
        INSERT INTO archive_requests(source,{_COLUMNS},first_revision) VALUES(?,{marks},?)
        ON CONFLICT(source,request_key) DO NOTHING
    """, (witness.source, *request, slot.birth)).rowcount:
        return False
    _retire(db, slot, witness.source, key)
    new_evidence = witness.evidence + 1
    db.execute("""
        INSERT INTO archive_response_timing VALUES(?,?,?,?,?,?,?)
    """, (witness.source, key, request[1], *timing, new_evidence))
    db.execute("""
        INSERT INTO archive_stats_revisions(source,revision) VALUES(?,?)
        ON CONFLICT(source) DO UPDATE SET revision=excluded.revision
    """, (witness.source, new_evidence))
    return True
