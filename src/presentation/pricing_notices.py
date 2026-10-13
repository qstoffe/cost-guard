"""Restrained category emphasis shared by report and Watch pricing notices."""
from __future__ import annotations

from .terminal import AnsiStyler, wrap_prose


def _styled_notice_content(
    content: str,
    source_start: int,
    emphasized_end: int,
    highlight_spans: tuple[tuple[int, int], ...],
    styler: AnsiStyler,
    role: str,
) -> str:
    cuts = {0, len(content)}
    heading_cut = emphasized_end - source_start
    if 0 < heading_cut < len(content):
        cuts.add(heading_cut)
    source_end = source_start + len(content)
    for start, end in highlight_spans:
        if source_start < start < source_end:
            cuts.add(start - source_start)
        if source_start < end < source_end:
            cuts.add(end - source_start)
    points = sorted(cuts)
    parts: list[str] = []
    for left, right in zip(points, points[1:]):
        absolute = source_start + left
        bold = any(start <= absolute < end for start, end in highlight_spans)
        parts.append(styler.apply(content[left:right], role if absolute < emphasized_end or bold else None, bold=bold))
    return "".join(parts)


def pricing_notice_lines(
    text: str,
    width: int,
    styler: AnsiStyler,
    role: str,
    *,
    highlight_spans: tuple[tuple[int, int], ...] = (),
) -> list[str]:
    label, colon, _body = text.partition(":")
    emphasized = len(label + colon) if colon else 0
    indent = len(text.partition(" ")[0]) + 1 if text.startswith(("*", "\u2726")) else 0
    lines = wrap_prose(text, width, continuation_prefix=" " * indent)
    result = []
    offset = 0
    for index, line in enumerate(lines):
        prefix = " " * indent if index else ""
        content = line[len(prefix):]
        result.append(prefix + _styled_notice_content(content, offset, emphasized, highlight_spans, styler, role))
        offset += len(content) + 1
    return result
