"""Interactive startup progress bar with redirected-output-safe behavior."""
from __future__ import annotations

import shutil
import sys
import threading
import textwrap
from typing import Callable, TextIO

_FRAMES = ("|", "/", "-", "\\")


def _supports_blocks(stream: TextIO) -> bool:
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        "█░✓".encode(encoding)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def _format_progress_line(
    percent: int,
    frame: str,
    label: str,
    width: int,
    *,
    prefix: str = "",
    blocks: bool = True,
) -> str:
    width = max(1, int(width))
    percent = max(0, min(100, int(percent)))
    if width >= 40:
        bar_width = min(24, max(8, width - 38))
        filled = int(bar_width * percent / 100)
        full, empty = ("█", "░") if blocks else ("#", "-")
        line = f"{prefix}[{full * filled}{empty * (bar_width - filled)}] {percent:3d}%  {frame} "
    else:
        line = f"{prefix}{percent:3d}%  {frame} "
    room = max(0, width - len(line))
    if len(label) > room:
        label = label[: max(0, room - 3)] + ("..." if room >= 4 else "")
    return (line + label)[:width]


class StartupProgress:
    def __init__(
        self,
        stream: TextIO | None = None,
        *,
        mode: str = "normal",
        interactive: bool | None = None,
        animate: bool = True,
        line_sink: Callable[[str], None] | None = None,
        heading: str | None = None,
    ) -> None:
        self.stream = stream or sys.stderr
        # Interactive-only transient heading, removed again by stop().
        self.heading = heading
        self._heading_shown = False
        self._heading_rows = 0
        self._last_plain_label = ""
        if interactive is None:
            interactive = bool(getattr(self.stream, "isatty", lambda: False)())
        self.interactive = bool(interactive)
        self.mode = "watch" if mode == "watch" else "normal"
        self.animate = bool(animate)
        self.line_sink = line_sink
        self._blocks = _supports_blocks(self.stream)
        self._active = False
        self._closed = False
        self._percent = 0
        self._label = "Initializing"
        self._frame_index = 0
        self._analyzed_count = 0
        self._last_length = 0
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None

    def _target_for(self, label: str) -> int:
        if label.startswith("Analyzing "):
            self._analyzed_count += 1
            return min(76, 28 + self._analyzed_count * 8)
        stages = (
            ("Selecting OpenCode source", 5),
            ("Initializing cache", 10),
            ("Initializing Watch", 15),
            ("Loading GitHub Copilot pricing", 22),
            ("Calculating month/today billing", 78),
            ("Building prompt analytics", 84),
            ("Comparing model prices", 89),
            ("Checking GitHub Copilot quota", 94),
        )
        for name, target in stages:
            if label.startswith(name):
                return target
        return min(95, self._percent + 3)

    def _render_locked(self, *, frame: str | None = None) -> None:
        if not self.interactive or not self._active:
            return
        width = max(1, shutil.get_terminal_size((80, 24)).columns - 1)
        current_frame = frame or _FRAMES[self._frame_index % len(_FRAMES)]
        prefix = "Watch: " if self.mode == "watch" else ""
        line = _format_progress_line(
            self._percent,
            current_frame,
            self._label,
            width,
            prefix=prefix,
            blocks=self._blocks,
        )
        if self.line_sink is not None:
            self.line_sink(line)
            self._last_length = len(line)
            return
        if self.heading and not self._heading_shown:
            lines = textwrap.wrap(self.heading, width=width) or [""]
            self.stream.write("\n".join(lines) + "\n")
            self._heading_rows = len(lines)
            self._heading_shown = True
        padding = " " * max(0, self._last_length - len(line))
        self.stream.write("\r" + line + padding)
        self.stream.flush()
        self._last_length = len(line)

    def _animate(self) -> None:
        while not self._stop_event.wait(0.12):
            with self._lock:
                if not self._active or self._closed:
                    continue
                self._frame_index += 1
                self._render_locked()

    def _ensure_worker(self) -> None:
        if not self.interactive or not self.animate or self._worker is not None:
            return
        self._worker = threading.Thread(target=self._animate, name="cost-guard-startup-progress", daemon=True)
        self._worker.start()

    def update(self, label: str, percent: int | None = None) -> None:
        if self._closed:
            return
        text = str(label).strip() or "Initializing"
        if not self.interactive:
            # Percentage-only updates of the same stage are not redirected noise.
            if text != self._last_plain_label:
                self.stream.write(f"Cost Guard: {text}\n")
                self.stream.flush()
            self._last_plain_label = text
            return
        with self._lock:
            self._active = True
            self._label = text
            target = self._target_for(text) if percent is None else max(0, min(100, int(percent)))
            self._percent = max(self._percent, target)
            self._render_locked()
        self._ensure_worker()

    def stop(self) -> None:
        if self._closed:
            return
        self._closed = True
        if not self.interactive:
            return
        with self._lock:
            if self._active:
                self._percent = 100
                self._render_locked(frame="✓" if self._blocks else "*")
            self._active = False
        self._stop_event.set()
        worker = self._worker
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=0.25)
        if self._last_length and self.line_sink is None:
            self.stream.write("\r" + (" " * self._last_length) + "\r")
            if self._heading_shown:
                # Clear every heading row, including narrow-terminal wraps.
                self.stream.write("\x1b[1A\x1b[2K" * self._heading_rows)
            self.stream.flush()
        self._last_length = 0
