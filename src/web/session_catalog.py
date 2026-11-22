"""Allowlisted catalog request validation; acquisition stays with shared Live."""
import re

from src.application.session_archive_sweep import VISIBLE_HINT_LIMIT
from src.application.session_catalog import SORTS
from src.application.session_catalog_scope import PAGE_SIZE, PERIODS


def catalog_page(owner, value):
    if value.get('action') == 'interest':
        if (set(value) != {'action', 'token', 'visible'} or type(value['visible']) is not bool
                or not isinstance(value['token'], str) or not re.fullmatch(r'[a-f0-9]{32}', value['token'])):
            raise ValueError('invalid_request')
        owner.interest(value['token'], value['visible'])
        return {'status': 'accepted'}
    if set(value) - {"token", "offset", "sort", "direction", "epoch", "period", "navigation", "applied", "cancelled", "passive"}:
        raise ValueError("invalid_request")
    offset = value.get("offset", 0)
    direction = value.get("direction", -1)
    if (type(offset) is not int or offset < 0 or offset > 1_000_000 or offset % PAGE_SIZE
            or type(value.get("passive", False)) is not bool
            or value.get("passive", False) and (offset != 0 or value.get("navigation") is not None)
            or type(direction) is not int or direction not in (-1, 1)
            or value.get("sort", "activity") not in SORTS
            or value.get("period", "today") not in PERIODS
            or any(value.get(key) is not None and (type(value[key]) is not int
                or not 1 <= value[key] <= 9_007_199_254_740_991) for key in ("navigation", "applied", "cancelled"))
            or any(value.get(key) is not None and (not isinstance(value[key], str)
                or not re.fullmatch(r"[a-f0-9]{32}", value[key])) for key in ("token", "epoch"))):
        raise ValueError("invalid_request")
    return owner.page(**value)


def cached_priority(handler, value, *, detail):
    field = "session_id" if detail else "session_ids"
    binding, raw = value.get("binding"), value.get(field)
    keys = [raw] if detail else raw
    if (set(value) != {"binding", field} or not isinstance(binding, str) or not re.fullmatch(r"[a-f0-9]{32}", binding)
            or type(keys) is not list or not 1 <= len(keys) <= VISIBLE_HINT_LIMIT
            or any(not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", key) for key in keys)
            or len(set(keys)) != len(keys)):
        handler.reply(400, {"error": "invalid_request"})
        return
    owner = handler.server.lifecycle
    archive = getattr(owner, "display_archive", None)
    catalog = getattr(getattr(owner, "live", None), "catalog", None)
    if archive is None or catalog is None or not getattr(owner, "cached_sessions_enabled", False):
        handler.reply(503, {"error": "cache_unavailable"})
        return
    prioritized = archive.prioritize_detail(catalog, binding, keys[0]) if detail else (
        archive.prioritize_visible(catalog, binding, keys))
    if prioritized is None:
        handler.reply(409, {"error": "cache_source_unbound"})
    else:
        handler.reply(202, {"prioritized": prioritized})
