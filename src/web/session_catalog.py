"""Allowlisted catalog request validation; acquisition stays with shared Live."""
import re

from src.application.session_catalog import SORTS
from src.application.session_catalog_scope import PAGE_SIZE, PERIODS


def catalog_page(owner, value):
    if value.get('action') == 'interest':
        if (set(value) != {'action', 'token', 'visible'} or type(value['visible']) is not bool
                or not isinstance(value['token'], str) or not re.fullmatch(r'[a-f0-9]{32}', value['token'])):
            raise ValueError('invalid_request')
        owner.interest(value['token'], value['visible'])
        return {'status': 'accepted'}
    if set(value) - {"token", "offset", "sort", "direction", "epoch", "period"}:
        raise ValueError("invalid_request")
    offset = value.get("offset", 0)
    direction = value.get("direction", -1)
    if (type(offset) is not int or offset < 0 or offset > 1_000_000 or offset % PAGE_SIZE
            or type(direction) is not int or direction not in (-1, 1)
            or value.get("sort", "activity") not in SORTS
            or value.get("period", "today") not in PERIODS
            or any(value.get(key) is not None and (not isinstance(value[key], str)
                or not re.fullmatch(r"[a-f0-9]{32}", value[key])) for key in ("token", "epoch"))):
        raise ValueError("invalid_request")
    return owner.page(**value)
