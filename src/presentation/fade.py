"""Theme-aware ANSI256 attenuation of arbitrary semantic foreground colors."""
from __future__ import annotations

from typing import Mapping

_BASIC = ((0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0),
          (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192),
          (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0),
          (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255))
_NAMES = ("Black", "DarkRed", "DarkGreen", "DarkYellow", "DarkBlue", "DarkMagenta",
          "DarkCyan", "Gray", "DarkGray", "Red", "Green", "Yellow", "Blue", "Magenta", "Cyan", "White")


def _rgb(index: int) -> tuple[int, int, int]:
    if index < 16:
        return _BASIC[index]
    if index >= 232:
        return (8 + 10 * (index - 232),) * 3
    n = index - 16
    levels = (0, 95, 135, 175, 215, 255)
    return levels[n // 36], levels[(n // 6) % 6], levels[n % 6]


def faded_style(style: object, *, light: bool) -> dict[str, object]:
    source = dict(style) if isinstance(style, Mapping) else {}
    ansi, name, background = source.get("ansi256"), source.get("foreground"), source.get("background")
    if isinstance(ansi, int) and 0 <= ansi <= 255 and background is None:
        foreground = _rgb(ansi)
    elif name in _NAMES:
        foreground = _BASIC[_NAMES.index(name)]
    else:
        foreground = (0, 0, 0) if light else (220, 220, 220)
    target = _BASIC[_NAMES.index(background)] if background in _NAMES else ((255, 255, 255) if light else (0, 0, 0))
    blended = tuple(round(a * 0.65 + b * 0.35) for a, b in zip(foreground, target))
    # Preserve hue, using the portable 256-color cube rather than truecolor.
    index = min(range(16, 256), key=lambda i: sum((a - b) ** 2 for a, b in zip(_rgb(i), blended)))
    return {**source, "foreground": None, "ansi256": index}
