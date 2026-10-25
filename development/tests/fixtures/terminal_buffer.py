"""Small in-memory VT viewport/scrollback model for Watch repaint regressions."""
from __future__ import annotations

import re


class TerminalBuffer:
    """Replay Watch's cursor/erase sequences without opening a real terminal."""

    def __init__(self, columns: int, rows: int) -> None:
        self.columns = columns
        self.rows = rows
        self.viewport = [""] * rows
        self.history: list[str] = []
        self.row = 0
        self.column = 0

    @property
    def contents(self) -> list[str]:
        return self.history + self.viewport

    def feed(self, output: str) -> None:
        for token in re.findall(r"\x1b\[[0-9;?]*[A-Za-z]|[^\x1b]", output):
            if token.startswith("\x1b["):
                self._control(token[2:-1], token[-1])
            elif token == "\r":
                self.column = 0
            elif token == "\n":
                self.column = 0
                self._down()
            else:
                if self.column == self.columns:
                    self.column = 0
                    self._down()
                line = self.viewport[self.row].ljust(self.column)
                self.viewport[self.row] = line[:self.column] + token + line[self.column + 1:]
                self.column += 1

    def _down(self) -> None:
        if self.row == self.rows - 1:
            self.history.append(self.viewport.pop(0))
            self.viewport.append("")
        else:
            self.row += 1

    def _control(self, parameters: str, command: str) -> None:
        if command == "H":
            coordinates = [int(value or 1) for value in (parameters or "1;1").split(";")]
            self.row = min(self.rows - 1, coordinates[0] - 1)
            self.column = min(self.columns - 1, coordinates[1] - 1)
        elif command == "K" and parameters == "2":
            self.viewport[self.row] = ""
        elif command == "J":
            if parameters == "3":
                self.history.clear()
            elif parameters == "2":
                self.viewport = [""] * self.rows
            elif parameters in {"", "0"}:
                self.viewport[self.row] = self.viewport[self.row][:self.column]
                self.viewport[self.row + 1:] = [""] * (self.rows - self.row - 1)
