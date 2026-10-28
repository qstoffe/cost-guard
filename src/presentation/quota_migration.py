"""Temporary CLI Watch announcement; no acquisition, config or usage history.

TODO(FR000525, 2026-12-27T21:35:22Z): after this verified 60-day sunset,
remove this module, WatchRenderer wiring, its tests and the cleanup note.
The permanent Used quota presentation must remain.
"""
from datetime import datetime
from contextlib import closing
import math
import os
from pathlib import Path
import sqlite3
import sys
import time

# PR #98 merged as ebd3dce5212e8d7aaca1929335a191957678c0e7.
# GitHub merged_at verified 2026-10-28; immutable sunset 2026-12-27T21:35:22Z.
MERGED_AT_UTC: str | None = "2026-10-28T21:35:22Z"
NOTICE = "⚠ Quota bars now show Used instead of Remaining"
PERSONAL_SECONDS = 72 * 3600
GLOBAL_SECONDS = 60 * 86400


def state_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return base / "CostGuard" / "quota-used-notice.sqlite3"


class QuotaMigrationNotice:
    """Read-only eligibility; persist only after a successful visible publication.

    A single SQLite row retains the earliest successful display across processes.
    Corruption/rollback/write errors suppress further notices in this process.
    Deleting local state can rearm only within the immutable global window.
    """
    def __init__(self, *, path=None, clock=time.time, merged_at=None):
        self.path = path
        self.clock = clock
        anchor = MERGED_AT_UTC if merged_at is None else merged_at
        self.merged_at = (None if anchor is None else
                          datetime.fromisoformat(anchor.replace("Z", "+00:00")).timestamp())
        self.deadline = None if self.merged_at is None else self.merged_at + GLOBAL_SECONDS
        self.disabled = False
        self.last_now = 0.0
        self.first_shown = None

    def eligible(self) -> bool:
        now = self.clock()
        if self.disabled or not math.isfinite(now) or self.deadline is None or now < self.merged_at or now >= self.deadline:
            return False  # No path lookup, creation or first-seen initialization after sunset.
        if now < self.last_now:
            self.disabled = True
            return False
        self.last_now = now
        try:
            if self.path is None:
                self.path = state_path()
            if self.path.exists():
                with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=0.1)) as db:
                    row = db.execute("SELECT first_shown, expired FROM notice WHERE id=1").fetchone()
                if row is None or not isinstance(row[0], (float, int)) or not 0 < row[0] <= now:
                    self.disabled = True
                    return False
                self.first_shown = row[0]
                if row[1] != 0:
                    return False
                if now >= self.first_shown + PERSONAL_SECONDS:
                    with closing(sqlite3.connect(self.path, timeout=0.2)) as db, db:
                        db.execute("UPDATE notice SET expired=1 WHERE id=1")
                    return False
            return True
        except (OSError, sqlite3.Error, ValueError):
            self.disabled = True
            return False

    def displayed(self, shown_at: float) -> None:
        """Called after stream flush/screen publication, never for hidden rendering."""
        if self.first_shown is not None:
            return
        if (self.deadline is None or not math.isfinite(shown_at) or
                shown_at < self.last_now or shown_at >= self.deadline):
            self.disabled = True
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=0.2)) as db, db:
                db.execute("CREATE TABLE IF NOT EXISTS notice (id INTEGER PRIMARY KEY CHECK(id=1), "
                           "first_shown REAL NOT NULL, expired INTEGER NOT NULL DEFAULT 0)")
                db.execute("INSERT INTO notice (id, first_shown) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET "
                           "first_shown=min(first_shown, excluded.first_shown)", (shown_at,))
            self.first_shown = shown_at if self.first_shown is None else min(self.first_shown, shown_at)
        except (OSError, sqlite3.Error):
            self.disabled = True
