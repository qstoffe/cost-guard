"""Small positive historical identity facts, independent of price freshness."""
from dataclasses import dataclass

from .display_usage_reader import USAGE_SLICE


@dataclass(frozen=True, slots=True)
class MixIdentity:
    label: str
    publisher: str | None


@dataclass(frozen=True, slots=True)
class MixReferenceStamp:
    observed_at: int
    signature: str


def mix_identity_schema():
    return """
        CREATE TABLE IF NOT EXISTS archive_mix_identities (
            source TEXT NOT NULL REFERENCES sources(source), model TEXT NOT NULL,
            label TEXT NOT NULL, label_at INTEGER NOT NULL,
            publisher TEXT, publisher_at INTEGER,
            PRIMARY KEY(source,model)
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS archive_mix_reference (
            source TEXT PRIMARY KEY REFERENCES archive_mix_state(source) ON DELETE CASCADE,
            observed_at INTEGER NOT NULL, signature TEXT NOT NULL
        ) WITHOUT ROWID;
    """


def read_mix_reference(db, source):
    row = db.execute("SELECT observed_at,signature FROM archive_mix_reference WHERE source=?", (source,)).fetchone()
    return MixReferenceStamp(*row) if row else None


def save_mix_reference(db, source, stamp):
    db.execute("""
        INSERT INTO archive_mix_reference VALUES(?,?,?)
        ON CONFLICT(source) DO UPDATE SET (observed_at,signature)=(excluded.observed_at,excluded.signature)
        WHERE excluded.observed_at >= archive_mix_reference.observed_at
    """, (source, stamp.observed_at, stamp.signature))


def read_mix_identities(db, source, keys):
    if not keys:
        return {}
    if len(keys) > USAGE_SLICE:
        raise ValueError("invalid_mix_identity_batch")
    marks = ",".join("?" for _ in keys)
    return {model: MixIdentity(label, publisher) for model, label, publisher in db.execute(f"""
        SELECT model,label,publisher FROM archive_mix_identities WHERE source=? AND model IN ({marks})
    """, (source, *keys))}


def save_mix_identities(db, source, candidates, observed_at):
    if not candidates or len(candidates) > USAGE_SLICE or observed_at <= 0:
        raise ValueError("invalid_mix_identity_batch")
    db.executemany("""
        INSERT INTO archive_mix_identities VALUES(?,?,?,?,?,?)
        ON CONFLICT(source,model) DO UPDATE SET
            label=CASE WHEN excluded.label_at >= label_at THEN excluded.label ELSE label END,
            label_at=max(label_at,excluded.label_at),
            publisher=CASE WHEN excluded.publisher_at >= coalesce(publisher_at,0)
                           THEN excluded.publisher ELSE publisher END,
            publisher_at=max(coalesce(publisher_at,0),coalesce(excluded.publisher_at,0))
        WHERE excluded.label_at > label_at OR excluded.label_at = label_at AND excluded.label <> label
           OR excluded.publisher_at > coalesce(publisher_at,0)
           OR excluded.publisher_at = publisher_at AND excluded.publisher IS NOT publisher
    """, ((source, model, value.label, observed_at, value.publisher, observed_at if value.publisher else None)
          for model, value in candidates.items()))
