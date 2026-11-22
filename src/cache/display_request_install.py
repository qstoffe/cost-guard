"""Private atomic usage-slot install; not registered by the runtime schema."""
from dataclasses import dataclass

from .display_request_overlay import RequestSlot
from .display_usage_reader import advance_usage_revision


INSTALL_SCHEMA = """
    CREATE TABLE archive_request_slots(
        source TEXT PRIMARY KEY REFERENCES sources(source),
        attempt TEXT NOT NULL REFERENCES archive_request_preparations(attempt),
        birth INTEGER NOT NULL, layout INTEGER NOT NULL DEFAULT 0
    ) WITHOUT ROWID;
"""


@dataclass(frozen=True, slots=True)
class RequestInstallWitness:
    source: str
    binding: str
    incarnation: int
    pricing: str
    dependency: str
    evidence: int
    geometry: int


@dataclass(frozen=True, slots=True)
class InstalledRequestScope:
    run: str
    root: str
    revision: str


def current_slot_scope(db, slot, witness):
    """Exact persisted root and independent evidence fences for one writer turn."""
    row = db.execute("""
        SELECT x.run,x.root_id,x.revision
        FROM archive_request_slots AS s
        JOIN archive_request_preparations AS a USING(attempt)
        JOIN archive_request_inputs AS x USING(run)
        JOIN sources AS b ON b.source=s.source
        JOIN sessions AS root ON root.source=s.source AND root.session_id=x.root_id
        LEFT JOIN session_progress AS r ON root.source=r.source AND root.session_id=r.session_id
        LEFT JOIN archive_usage_revisions AS u ON u.source=s.source
        LEFT JOIN archive_stats_revisions AS e ON e.source=s.source
        LEFT JOIN archive_stats_geometry_revisions AS g ON g.source=s.source
        WHERE s.source=? AND (s.attempt,s.birth,s.layout)=(?,?,?)
          AND x.source=s.source AND x.archive_epoch=b.archive_epoch
          AND (x.binding,x.incarnation,x.pricing,x.dependency)=(?,?,?,?)
          AND root.source_present AND root.revision=x.revision AND coalesce(r.progress,0)=x.progress
          AND coalesce(u.revision,0)=s.birth
          AND coalesce(e.revision,0)=? AND coalesce(g.revision,0)=?
    """, (witness.source, slot.attempt, slot.birth, slot.layout, witness.binding, witness.incarnation,
          witness.pricing, witness.dependency, witness.evidence, witness.geometry)).fetchone()
    return InstalledRequestScope(*row) if row else None


def install_usage_slot(db, attempt, witness, *, eligible):
    """Install request and fork evidence only in the caller's writer transaction.

    The caller owns current catalog/writer coordination and must roll back
    this transaction if eligibility changes before commit. Nothing here
    installs Stats evidence, Detail, membership, coverage or notifications.
    """
    if not db.in_transaction:
        raise ValueError("request slot install requires a writer transaction")
    if not eligible():
        return None
    row = db.execute("""
        SELECT p.usage_revision,p.edits,p.corrections,p.winner_changes
        FROM archive_request_preparations AS p
        JOIN archive_request_inputs AS i USING(run)
        JOIN sources AS s USING(source)
        JOIN sessions AS root ON root.source=i.source AND root.session_id=i.root_id
        LEFT JOIN session_progress AS r ON r.source=i.source AND r.session_id=i.root_id
        LEFT JOIN archive_usage_revisions AS u ON u.source=i.source
        LEFT JOIN archive_stats_revisions AS e ON e.source=i.source
        LEFT JOIN archive_stats_geometry_revisions AS g ON g.source=i.source
        WHERE p.attempt=? AND p.sealed AND i.sealed AND i.source=?
          AND (i.binding,i.incarnation,i.pricing,i.dependency)=(?,?,?,?)
          AND s.archive_epoch=i.archive_epoch AND coalesce(u.revision,0)=p.usage_revision
          AND root.source_present AND root.revision=i.revision AND coalesce(r.progress,0)=i.progress
          AND coalesce(e.revision,0)=? AND coalesce(g.revision,0)=?
          AND NOT EXISTS(SELECT 1 FROM archive_prepare_forks f INDEXED BY archive_prepare_pending_forks
                         WHERE f.attempt=p.attempt AND NOT f.done)
          AND NOT EXISTS(SELECT 1 FROM archive_prepare_winners w INDEXED BY archive_prepare_pending_winners
                         WHERE w.attempt=p.attempt AND NOT w.done)
    """, (attempt, witness.source, witness.binding, witness.incarnation, witness.pricing, witness.dependency,
          witness.evidence, witness.geometry)).fetchone()
    if row is None:
        return None
    revision, edits, corrections, winner_changes = row
    birth = revision + bool(edits)
    if not db.execute("""
        INSERT INTO archive_request_slots(source,attempt,birth) VALUES(?,?,?)
        ON CONFLICT(source) DO NOTHING
    """, (witness.source, attempt, birth)).rowcount:
        return None
    if edits:
        # Either change invalidates reductions over the prior visible usage.
        advance_usage_revision(db, witness.source, changed_winner=bool(corrections or winner_changes))
    return RequestSlot(attempt, birth)
