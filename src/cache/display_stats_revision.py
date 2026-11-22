"""A shared, correction-fenced cohort for bounded Stats reducers."""
from dataclasses import dataclass

from .display_usage_reader import UsageVersion, retained_usage_version


_TABLES = ("archive_stats_roots", "archive_stats_intervals", "archive_stats_parents",
           "archive_stats_first_inputs", "archive_response_timing")


@dataclass(frozen=True, slots=True)
class StatsVersion:
    usage: UsageVersion
    evidence: int


def stats_revision_schema():
    triggers = "\n".join(f"""
        CREATE TRIGGER IF NOT EXISTS {table}_revision AFTER UPDATE ON {table} BEGIN
            INSERT INTO archive_stats_revisions(source,revision,invalidated_through) VALUES(NEW.source,0,1)
            ON CONFLICT(source) DO UPDATE SET invalidated_through=revision+1;
        END;
    """ for table in (*_TABLES, "archive_stats_request_identity"))
    return triggers + """
        CREATE INDEX IF NOT EXISTS archive_stats_root_cohort
        ON archive_stats_roots(source,first_revision,root_id);
    """


def stats_revision(db, source):
    row = db.execute("SELECT revision FROM archive_stats_revisions WHERE source=?", (source,)).fetchone()
    return row[0] if row else 0


def retained_stats_version(db, source, expected=None):
    usage = retained_usage_version(db, source, expected.usage if expected else None)
    if usage is None:
        return None
    row = db.execute("SELECT revision,invalidated_through FROM archive_stats_revisions WHERE source=?",
                     (source,)).fetchone()
    revision, floor = row or (0, 0)
    if expected is None:
        return StatsVersion(usage, revision)
    return expected if floor <= expected.evidence <= revision else None
