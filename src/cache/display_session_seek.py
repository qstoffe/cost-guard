"""Adjacent Sessions pages seek existing nullable sort indexes."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionSeek:
    generation: int
    total: int
    end_ms: int | None
    anchor_id: str
    forward: bool


def seek_keys(db, source, *, column, index, direction, where, params, limit, seek, nullable):
    """Three bounded ordered ranges; no OR predicate that scans earlier rows."""
    anchor = db.execute(f"SELECT {column} FROM sessions WHERE source=? AND session_id=?",
                        (source, seek.anchor_id)).fetchone()
    if anchor is None:
        return None
    value = anchor[0]
    comparison = ">" if seek.forward else "<"
    key_comparison = ">" if seek.forward == (direction == 1) else "<"
    id_order = "ASC" if seek.forward else "DESC"
    key_order = "ASC" if key_comparison == ">" else "DESC"
    key_missing = f"({column} IS NULL)"
    known_order = f"{column} {key_order}, session_id {id_order}"
    known = f"{key_missing}=0 AND " if nullable else ""
    segments = []
    if value is None:
        segments.append((f"{key_missing}=1 AND {column} IS NULL AND session_id{comparison}?",
                         f"session_id {id_order}", (seek.anchor_id,)))
        if not seek.forward:
            segments.append((f"{key_missing}=0", known_order, ()))
    else:
        segments.append((f"{known}{column}=? AND session_id{comparison}?",
                         f"session_id {id_order}", (value, seek.anchor_id)))
        segments.append((f"{known}{column}{key_comparison}?", known_order, (value,)))
        if seek.forward and nullable:
            segments.append((f"{key_missing}=1 AND {column} IS NULL", f"session_id {id_order}", ()))
    selected = []
    for condition, order, args in segments:
        if len(selected) == limit:
            break
        selected.extend(key for key, in db.execute(f"""
            SELECT session_id FROM sessions INDEXED BY {index}
            WHERE {where} AND {condition} ORDER BY {order} LIMIT ?
        """, (*params, *args, limit - len(selected))))
    if not seek.forward:
        selected.reverse()
    return selected
