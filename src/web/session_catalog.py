"""Allowlisted catalog request validation; acquisition stays with shared Live."""
import re

from src.application.session_catalog import SORTS


def catalog_page(owner, value):
    if set(value) - {"token", "offset", "sort", "direction", "epoch"}:
        raise ValueError("invalid_request")
    offset = value.get("offset", 0)
    direction = value.get("direction", -1)
    if (type(offset) is not int or offset < 0 or offset > 1_000_000 or offset % 50
            or type(direction) is not int or direction not in (-1, 1)
            or value.get("sort", "activity") not in SORTS
            or any(value.get(key) is not None and (not isinstance(value[key], str)
                or not re.fullmatch(r"[a-f0-9]{32}", value[key])) for key in ("token", "epoch"))):
        raise ValueError("invalid_request")
    return owner.page(**value)
