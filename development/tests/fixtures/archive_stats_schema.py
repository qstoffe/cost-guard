"""Synthetic reconstruction of prior AI Stats schema revisions for migration tests."""


def remove_measured_cohort(db):
    db.execute("DROP TRIGGER archive_stats_geometry_birth")
    db.execute("DROP TRIGGER archive_stats_geometry_correction")
    db.execute("DROP INDEX archive_stats_measured_cohort")
    db.execute("DROP TABLE archive_stats_geometry_revisions")


def restore_v20_stamp(db):
    db.execute("ALTER TABLE archive_stats_time_state RENAME COLUMN geometry_revision TO evidence_revision")
    db.execute("ALTER TABLE archive_stats_time_state ADD COLUMN usage_revision INTEGER NOT NULL DEFAULT 0")


def restore_v20_cohort(db):
    db.execute("""
        CREATE INDEX archive_stats_geometry_cohort
        ON archive_stats_intervals(source,first_revision,root_id,session_id,event_id,kind)
    """)
