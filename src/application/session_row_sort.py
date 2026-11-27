"""Shared Sessions sort values for stored rows and in-memory pages."""


def activity_time(row):
    return row.last_activity_ms if row.last_activity_ms is not None else row.prompt_started_ms


def effort_sort(key):
    if key is None:
        return None
    levels = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "default", "multiple")
    return (levels.index(key) if key in levels else len(levels), key)


def sort_values(row):
    return {"activity": activity_time(row),
        "name": row.title.casefold(),
        "model": (row.model if row.model != "N/A" else row.selected_display_model).casefold() or None,
        "effort": effort_sort(row.effort_key),
        "ccost": row.ccost if row.complete else None, "prompts": row.prompt_count,
        "duration": row.duration_ms, "ctx": row.context_tokens if row.context_qualified else None}


def sort_value(row, key):
    return sort_values(row)[key]
