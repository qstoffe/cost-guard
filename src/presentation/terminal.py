"""Terminal styling and table primitives driven entirely by resolved config."""
from __future__ import annotations

import os
import re
import shutil
import sys
import textwrap
from dataclasses import dataclass
from typing import Mapping, Sequence, TextIO

from .fade import faded_style

_CONSOLE_FG = {
    "Black": 30, "DarkRed": 31, "DarkGreen": 32, "DarkYellow": 33,
    "DarkBlue": 34, "DarkMagenta": 35, "DarkCyan": 36, "Gray": 37,
    "DarkGray": 90, "Red": 91, "Green": 92, "Yellow": 93,
    "Blue": 94, "Magenta": 95, "Cyan": 96, "White": 97,
}
_CONSOLE_BG = {name: code + 10 if code < 90 else code + 10 for name, code in _CONSOLE_FG.items()}
# Bright foreground 90..97 maps to bright background 100..107 rather than +10 from semantic ANSI range.
for _name, _fg in list(_CONSOLE_FG.items()):
    if 90 <= _fg <= 97:
        _CONSOLE_BG[_name] = _fg + 10


_ESCAPES = re.compile(r"(?:\x1b\[|\x9b)[0-?]*[ -/]*[@-~]|\x1b[\]P^_X][^\x07\x1b]*(?:\x07|\x1b\\)?|\x1b[@-Z\\-_]")


def single_line(value: object, fallback: str = "") -> str:
    """Keep external text (titles, prompt previews) in one cell, never arbitrary terminal lines.

    Remove CSI/OSC/DCS terminal escapes, fold line breaks and other control
    characters into single spaces and drop a leading Markdown heading marker.
    """
    without_escapes = _ESCAPES.sub("", str(value if value is not None else ""))
    one_line = " ".join("".join(char if char.isprintable() else " " for char in without_escapes).split())
    return re.sub(r"^#{1,6}(?:\s+|$)", "", one_line) or fallback


def visible_len(value: str) -> int:
    return len(value)


def fit(value: object, width: int, *, right: bool = False) -> str:
    text = str(value if value is not None else "")
    if width <= 0:
        return ""
    if len(text) > width:
        if width <= 3:
            text = text[:width]
        else:
            text = text[: width - 3] + "..."
    return text.rjust(width) if right else text.ljust(width)


def terminal_content_width(stream: TextIO | None = None, *, fallback: int = 120) -> int:
    """Return usable terminal width without making redirected output environment-dependent."""
    candidate = stream or sys.stdout
    try:
        if bool(getattr(candidate, "isatty", lambda: False)()):
            fileno = getattr(candidate, "fileno", None)
            if callable(fileno):
                return max(40, os.get_terminal_size(fileno()).columns - 1)
            return max(40, shutil.get_terminal_size((fallback, 24)).columns - 1)
    except (OSError, ValueError):
        pass
    return max(40, int(fallback))


def wrap_prose(
    text: str, width: int, *, initial_prefix: str = "", continuation_prefix: str = "",
) -> list[str]:
    """Wrap unstyled prose at spaces; an indivisible word may exceed the width."""
    return textwrap.wrap(
        " ".join(text.split()), width=max(1, int(width), len(initial_prefix) + 1, len(continuation_prefix) + 1),
        initial_indent=initial_prefix, subsequent_indent=continuation_prefix,
        break_long_words=False, break_on_hyphens=False,
    )


@dataclass(frozen=True, slots=True)
class Column:
    name: str
    right: bool = False
    min_width: int = 1
    max_width: int = 80
    flexible: bool = False
    fixed_width: int | None = None


@dataclass(frozen=True, slots=True)
class StyledText:
    """Cell text with independently styled visible segments."""
    parts: tuple[tuple[str, str | None], ...]

    def __str__(self) -> str:
        return "".join(text for text, _role in self.parts)


class AnsiStyler:
    def __init__(self, colors: Mapping[str, object], *, enabled: bool | None = None, light_theme: bool = False) -> None:
        self.colors = colors
        self.light_theme = light_theme
        if enabled is None:
            enabled = bool(getattr(sys.stdout, "isatty", lambda: False)()) and not os.environ.get("NO_COLOR")
        self.enabled = bool(enabled)

    @staticmethod
    def _sequence(style: object, *, faded: bool = False) -> str:
        if not isinstance(style, Mapping):
            return ""
        fg = style.get("foreground")
        bg = style.get("background")
        ansi = style.get("ansi256")
        codes: list[str] = []
        if isinstance(ansi, int) and (bg is None or faded):
            codes.append(f"38;5;{ansi}")
        elif isinstance(fg, str) and fg in _CONSOLE_FG:
            codes.append(str(_CONSOLE_FG[fg]))
        if isinstance(bg, str) and bg in _CONSOLE_BG:
            codes.append(str(_CONSOLE_BG[bg]))
        return f"\x1b[{';'.join(codes)}m" if codes else ""

    def apply(self, text: str, role: str | None = None, *, faded: bool = False) -> str:
        if not self.enabled or (not role and not faded):
            return text
        style = self.colors.get(role) if role else None
        sequence = self._sequence(faded_style(style, light=self.light_theme) if faded else style, faded=faded)
        return f"{sequence}{text}\x1b[0m" if sequence else text


def _rendered_width(widths: Sequence[int]) -> int:
    return 1 + sum(width + 3 for width in widths)


def _resolve_widths(
    columns: Sequence[Column],
    rows: Sequence[Sequence[object]],
    *,
    target_width: int | None,
) -> list[int]:
    widths: list[int] = []
    for index, column in enumerate(columns):
        if column.fixed_width is not None:
            widths.append(max(len(column.name), int(column.fixed_width)))
            continue
        width = max(len(column.name), column.min_width)
        for row in rows:
            if index < len(row):
                width = max(width, len(str(row[index] if row[index] is not None else "")))
        widths.append(min(column.max_width, width))

    if target_width is None:
        return widths
    target = max(1, int(target_width))
    while _rendered_width(widths) > target:
        best_index = -1
        best_reducible = 0
        for index, column in enumerate(columns):
            if column.fixed_width is not None or not column.flexible:
                continue
            minimum = max(len(column.name), column.min_width)
            reducible = widths[index] - minimum
            if reducible > best_reducible:
                best_index = index
                best_reducible = reducible
        if best_index < 0 or best_reducible <= 0:
            break
        over = _rendered_width(widths) - target
        widths[best_index] -= min(best_reducible, max(1, over))
    return widths


def _render_cell(
    raw: object,
    width: int,
    *,
    right: bool,
    role: str | None,
    styler: AnsiStyler | None,
    faded: bool = False,
) -> str:
    plain = str(raw if raw is not None else "")
    fitted = fit(plain, width, right=right)
    if styler is None:
        return fitted

    # If fitting truncated the value, segment boundaries no longer map to the
    # visible text. Style the visible value as one unit in that rare case.
    visible_value = plain if len(plain) <= width else (plain[:width] if width <= 3 else plain[: width - 3] + "...")
    left_pad = width - len(visible_value) if right else 0
    right_pad = width - len(visible_value) if not right else 0
    prefix = " " * left_pad
    suffix = " " * right_pad
    if isinstance(raw, StyledText) and len(plain) <= width:
        body = "".join(styler.apply(text, segment_role or role, faded=faded) for text, segment_role in raw.parts)
    else:
        body = styler.apply(visible_value, role, faded=faded)
    return prefix + body + suffix


def resolve_table_widths(
    columns: Sequence[Column],
    rows: Sequence[Sequence[object]],
    *,
    target_width: int | None = None,
) -> tuple[int, ...]:
    """Resolve the visible content width of each table column."""
    return tuple(_resolve_widths(columns, rows, target_width=target_width))


def render_table(
    columns: Sequence[Column],
    rows: Sequence[Sequence[object]],
    *,
    styles: Sequence[Sequence[str | None]] | None = None,
    styler: AnsiStyler | None = None,
    target_width: int | None = None,
    separator_before_rows: Sequence[int] = (),
    faded_rows: Sequence[int] = (),
) -> list[str]:
    widths = list(resolve_table_widths(columns, rows, target_width=target_width))
    separator = "|" + "|".join("-" * (width + 2) for width in widths) + "|"
    result = [separator]
    header = "| " + " | ".join(fit(column.name, widths[index], right=column.right) for index, column in enumerate(columns)) + " |"
    result.extend((header, separator))
    separators = set(separator_before_rows)
    faded = set(faded_rows)
    for row_index, row in enumerate(rows):
        if row_index in separators:
            result.append(separator)
        cells: list[str] = []
        for index, column in enumerate(columns):
            raw = row[index] if index < len(row) else ""
            role = None
            if styles and row_index < len(styles) and index < len(styles[row_index]):
                role = styles[row_index][index]
            cells.append(_render_cell(raw, widths[index], right=column.right, role=role, styler=styler,
                                      faded=row_index in faded))
        result.append("| " + " | ".join(cells) + " |")
    result.append(separator)
    return result
