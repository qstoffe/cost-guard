"""Restrained category emphasis shared by report and Watch pricing notices."""
from __future__ import annotations

from .terminal import AnsiStyler, wrap_prose


def pricing_notice_lines(text: str, width: int, styler: AnsiStyler, role: str) -> list[str]:
    label, colon, _body = text.partition(":")
    emphasized = len(label + colon) if colon else 0
    indent = len(text.partition(" ")[0]) + 1 if text.startswith(("*", "✦")) else 0
    lines = wrap_prose(text, width, continuation_prefix=" " * indent)
    result = []
    offset = 0
    for index, line in enumerate(lines):
        prefix = " " * indent if index else ""
        content = line[len(prefix):]
        count = min(len(content), max(0, emphasized - offset))
        result.append(prefix + styler.apply(content[:count], role) + content[count:])
        offset += len(content) + 1
    return result
