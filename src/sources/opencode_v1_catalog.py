"""V1 metadata activity and conservative liveness candidates, separate from revisions."""
from __future__ import annotations

import sqlite3


def catalog_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    """Payload-free activity includes child message/part changes missed by session clocks."""
    return connection.execute("""
        WITH messages AS (
          SELECT session_id, MAX(MAX(time_created, time_updated)) AS activity FROM message GROUP BY session_id
        ), parts AS (
          SELECT session_id, MAX(MAX(time_created, time_updated)) AS activity FROM part GROUP BY session_id
        )
        SELECT s.*, MAX(s.time_updated, s.time_created, COALESCE(m.activity, 0), COALESCE(p.activity, 0)) AS activity
        FROM session s LEFT JOIN messages m ON m.session_id = s.id LEFT JOIN parts p ON p.session_id = s.id
        ORDER BY activity DESC, s.id DESC
    """).fetchall()


def watch_candidates(connection: sqlite3.Connection) -> frozenset[str]:
    """Only a terminal latest message can exclude a session from liveness discovery.

    This explicit liveness probe reads last-message status and live tool flags,
    never tokens or text. V1 has no native active registry: old running tools
    cannot be age-filtered. This stays separate from payload-free revisions and
    never declares a prompt running: canonical analysis remains authoritative.
    """
    rows = connection.execute("""
        WITH latest AS (
          SELECT id, session_id, data, time_created,
                 ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY time_created DESC, id DESC) AS ordinal
          FROM message
        ), live_parts AS (
          SELECT DISTINCT p.session_id FROM part p
          WHERE CASE WHEN json_valid(p.data) THEN
            json_extract(p.data, '$.type') = 'tool'
            AND json_extract(p.data, '$.state.status') IN ('pending', 'streaming', 'running') ELSE 1 END
        )
        SELECT m.session_id FROM latest m WHERE m.ordinal = 1 AND (
          CASE WHEN json_valid(m.data) THEN
            COALESCE(json_extract(m.data, '$.role'), '') != 'assistant'
            OR json_extract(m.data, '$.finish') = 'tool-calls'
            OR (COALESCE(json_extract(m.data, '$.time.completed'), 0) <= 0
                AND json_extract(m.data, '$.error') IS NULL)
          ELSE 1 END
          OR m.session_id IN (SELECT session_id FROM live_parts)
        )
    """).fetchall()
    return frozenset(str(row[0]) for row in rows)
