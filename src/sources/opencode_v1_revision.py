"""Cheap row-state revision proofs for the legacy OpenCode V1 schema."""
from __future__ import annotations

import hashlib
import sqlite3
from typing import Mapping, Sequence

from .errors import SourceDataError

_REVISION_FIELDS = (
    "id", "parent_id", "project_id", "time_updated", "time_archived",
    "message_count", "message_max_updated", "message_updated_total",
    "message_max_created", "message_max_id", "part_count", "part_max_updated",
    "part_updated_total", "part_max_created", "part_max_id",
)


def revision_from_rows(rows: Sequence[sqlite3.Row]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        values = ["" if row[field] is None else str(row[field]) for field in _REVISION_FIELDS]
        digest.update("\0".join(values).encode("utf-8", errors="surrogatepass"))
        digest.update(b"\n")
    return "v1-tree:" + digest.hexdigest()


def revision_rows(connection: sqlite3.Connection, session_id: str) -> list[sqlite3.Row]:
    rows = connection.execute(
        """
        WITH RECURSIVE tree(id) AS (
          SELECT id FROM session WHERE id = ?
          UNION
          SELECT s.id FROM session s JOIN tree ON s.parent_id = tree.id
        ),
        msg_state AS (
          SELECT m.session_id, COUNT(*) AS message_count,
                 COALESCE(MAX(m.time_updated), 0) AS message_max_updated,
                 COALESCE(SUM(m.time_updated), 0) AS message_updated_total,
                 COALESCE(MAX(m.time_created), 0) AS message_max_created,
                 COALESCE(MAX(m.id), '') AS message_max_id
          FROM message m JOIN tree t ON t.id = m.session_id GROUP BY m.session_id
        ),
        part_state AS (
          SELECT p.session_id, COUNT(*) AS part_count,
                 COALESCE(MAX(p.time_updated), 0) AS part_max_updated,
                 COALESCE(SUM(p.time_updated), 0) AS part_updated_total,
                 COALESCE(MAX(p.time_created), 0) AS part_max_created,
                 COALESCE(MAX(p.id), '') AS part_max_id
          FROM part p JOIN tree t ON t.id = p.session_id GROUP BY p.session_id
        )
        SELECT s.id, s.parent_id, s.project_id, s.time_updated, s.time_archived,
               COALESCE(ms.message_count, 0) AS message_count,
               COALESCE(ms.message_max_updated, 0) AS message_max_updated,
               COALESCE(ms.message_updated_total, 0) AS message_updated_total,
               COALESCE(ms.message_max_created, 0) AS message_max_created,
               COALESCE(ms.message_max_id, '') AS message_max_id,
               COALESCE(ps.part_count, 0) AS part_count,
               COALESCE(ps.part_max_updated, 0) AS part_max_updated,
               COALESCE(ps.part_updated_total, 0) AS part_updated_total,
               COALESCE(ps.part_max_created, 0) AS part_max_created,
               COALESCE(ps.part_max_id, '') AS part_max_id
        FROM tree t JOIN session s ON s.id = t.id
        LEFT JOIN msg_state ms ON ms.session_id = s.id
        LEFT JOIN part_state ps ON ps.session_id = s.id
        ORDER BY s.id
        """,
        (session_id,),
    ).fetchall()
    if not rows:
        raise SourceDataError("OpenCode V1 session does not exist")
    return list(rows)


def batch_revisions(connection: sqlite3.Connection, session_ids: Sequence[str]) -> Mapping[str, str]:
    unique = tuple(dict.fromkeys(str(value) for value in session_ids if str(value)))
    if not unique:
        return {}
    values_sql = ",".join("(?)" for _ in unique)
    rows = connection.execute(
        f"""
        WITH RECURSIVE requested(root_id) AS (VALUES {values_sql}),
        tree(root_id, id) AS (
          SELECT r.root_id, s.id FROM requested r JOIN session s ON s.id = r.root_id
          UNION ALL
          SELECT t.root_id, s.id FROM session s JOIN tree t ON s.parent_id = t.id
        ),
        msg_state AS (
          SELECT t.root_id, m.session_id, COUNT(*) AS message_count,
                 COALESCE(MAX(m.time_updated), 0) AS message_max_updated,
                 COALESCE(SUM(m.time_updated), 0) AS message_updated_total,
                 COALESCE(MAX(m.time_created), 0) AS message_max_created,
                 COALESCE(MAX(m.id), '') AS message_max_id
          FROM message m JOIN tree t ON t.id = m.session_id GROUP BY t.root_id, m.session_id
        ),
        part_state AS (
          SELECT t.root_id, p.session_id, COUNT(*) AS part_count,
                 COALESCE(MAX(p.time_updated), 0) AS part_max_updated,
                 COALESCE(SUM(p.time_updated), 0) AS part_updated_total,
                 COALESCE(MAX(p.time_created), 0) AS part_max_created,
                 COALESCE(MAX(p.id), '') AS part_max_id
          FROM part p JOIN tree t ON t.id = p.session_id GROUP BY t.root_id, p.session_id
        )
        SELECT t.root_id, s.id, s.parent_id, s.project_id, s.time_updated, s.time_archived,
               COALESCE(ms.message_count, 0) AS message_count,
               COALESCE(ms.message_max_updated, 0) AS message_max_updated,
               COALESCE(ms.message_updated_total, 0) AS message_updated_total,
               COALESCE(ms.message_max_created, 0) AS message_max_created,
               COALESCE(ms.message_max_id, '') AS message_max_id,
               COALESCE(ps.part_count, 0) AS part_count,
               COALESCE(ps.part_max_updated, 0) AS part_max_updated,
               COALESCE(ps.part_updated_total, 0) AS part_updated_total,
               COALESCE(ps.part_max_created, 0) AS part_max_created,
               COALESCE(ps.part_max_id, '') AS part_max_id
        FROM tree t JOIN session s ON s.id = t.id
        LEFT JOIN msg_state ms ON ms.root_id = t.root_id AND ms.session_id = s.id
        LEFT JOIN part_state ps ON ps.root_id = t.root_id AND ps.session_id = s.id
        ORDER BY t.root_id, s.id
        """,
        unique,
    ).fetchall()
    grouped: dict[str, list[sqlite3.Row]] = {session_id: [] for session_id in unique}
    for row in rows:
        grouped[str(row["root_id"])].append(row)
    missing = [session_id for session_id, values in grouped.items() if not values]
    if missing:
        raise SourceDataError(f"OpenCode V1 session does not exist: {missing[0]}")
    return {session_id: revision_from_rows(values) for session_id, values in grouped.items()}
