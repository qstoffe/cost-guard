"""Buffered Watch frames: overwrite changed rows without blanking the dashboard."""
from __future__ import annotations

import re
import shutil
import unicodedata
from typing import TextIO

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


class WatchScreen:
    def __init__(self, stream: TextIO) -> None:
        self.stream = stream
        self.lines: tuple[str, ...] = ()
        self.size = (0, 0)

    def publish(self, text: str) -> None:
        lines = tuple(text.split("\n"))
        size = shutil.get_terminal_size((80, 24))
        geometry = (size.columns, size.lines)
        if lines == self.lines and geometry == self.size:
            return
        # Absolute row patches are safe only while both frames fit the viewport.
        # Fixed-width tables can wrap in narrow terminals: overwrite the whole
        # frame there, in one write, and erase the stale tail AFTER the new text.
        fits = geometry == self.size and self._fits(self.lines, *geometry) and self._fits(lines, *geometry)
        if fits:
            output = self._patch(lines)
        else:
            output = "\x1b[H" + "\n".join("\x1b[2K" + line for line in lines) + "\x1b[0J"
        self.stream.write(output)
        self.stream.flush()
        self.lines, self.size = lines, geometry

    @staticmethod
    def _fits(lines: tuple[str, ...], columns: int, rows: int) -> bool:
        return bool(lines) and len(lines) <= rows and all(_cell_width(line) < columns for line in lines)

    def resized(self) -> bool:
        size = shutil.get_terminal_size((80, 24))
        return bool(self.lines) and (size.columns, size.lines) != self.size

    def _patch(self, lines: tuple[str, ...]) -> str:
        changes = [f"\x1b[{index + 1};1H\x1b[2K{line}" for index, line in enumerate(lines)
                   if index >= len(self.lines) or line != self.lines[index]]
        if len(lines) < len(self.lines):
            changes.append(f"\x1b[{len(lines) + 1};1H\x1b[0J")
        # Leave the cursor on the status row for the existing one-line updates.
        changes.append(f"\x1b[{len(lines)};1H")
        return "".join(changes)

    def status(self, text: str) -> None:
        if self.lines:
            if self.lines[-1] == text:
                return
            self.lines = (*self.lines[:-1], text)
        self.stream.write("\r\x1b[2K" + text)
        self.stream.flush()


def _cell_width(line: str) -> int:
    return sum(0 if unicodedata.combining(char) else 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
               for char in _ANSI.sub("", line))
