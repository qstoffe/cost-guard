"""Measured time does not restart on unrelated price, response or root changes."""
from dataclasses import dataclass


MEASURED_GEOMETRY = "provisional=0 AND start_ms>0 AND duration_ms>0"


@dataclass(frozen=True, slots=True)
class StatsGeometryVersion:
    archive_epoch: int
    revision: int


def geometry_schema():
    birth = "COALESCE((SELECT revision+1 FROM archive_stats_revisions WHERE source=NEW.source),1)"
    old = "OLD.provisional=0 AND OLD.start_ms>0 AND OLD.duration_ms>0"
    new = "NEW.provisional=0 AND NEW.start_ms>0 AND NEW.duration_ms>0"
    return f"""
        CREATE TABLE IF NOT EXISTS archive_stats_geometry_revisions (
            source TEXT PRIMARY KEY REFERENCES sources(source),
            revision INTEGER NOT NULL, invalidated_through INTEGER NOT NULL
        ) WITHOUT ROWID;
        CREATE INDEX IF NOT EXISTS archive_stats_measured_cohort
        ON archive_stats_intervals(source,first_revision,root_id,session_id,event_id,kind)
        WHERE {MEASURED_GEOMETRY};
        CREATE TRIGGER IF NOT EXISTS archive_stats_geometry_birth AFTER INSERT ON archive_stats_intervals WHEN {new} BEGIN
            INSERT INTO archive_stats_geometry_revisions VALUES(NEW.source,NEW.first_revision,0)
            ON CONFLICT(source) DO UPDATE SET revision=max(revision,excluded.revision);
        END;
        CREATE TRIGGER IF NOT EXISTS archive_stats_geometry_correction AFTER UPDATE ON archive_stats_intervals
        WHEN (({old}) OR ({new})) AND
             (OLD.start_ms,OLD.duration_ms,OLD.provisional) IS NOT (NEW.start_ms,NEW.duration_ms,NEW.provisional)
        BEGIN
            INSERT INTO archive_stats_geometry_revisions VALUES(NEW.source,{birth},{birth})
            ON CONFLICT(source) DO UPDATE SET
                revision=max(revision,excluded.revision),
                invalidated_through=max(invalidated_through,excluded.invalidated_through);
        END;
    """


def retained_geometry_version(db, source, expected=None):
    row = db.execute("""
        SELECT sources.archive_epoch,revisions.revision,revisions.invalidated_through
        FROM sources LEFT JOIN archive_stats_geometry_revisions AS revisions USING(source)
        WHERE source=?
    """, (source,)).fetchone()
    epoch, revision, floor = row or (0, 0, 0)
    if expected is None:
        return StatsGeometryVersion(epoch, revision or 0)
    if expected.archive_epoch != epoch or not (floor or 0) <= expected.revision <= (revision or 0):
        return None
    return expected
