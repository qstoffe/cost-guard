"""One background Token Mix build; request paths only read its last commit."""
from contextlib import AbstractContextManager
from enum import Enum
import sqlite3

from .archive_token_mix import ArchiveMixRollup


class MixBuildState(str, Enum):
    MORE = "more"
    STALE = "stale"
    PUBLISHED = "published"


class ArchiveMixBuild(AbstractContextManager):
    """Consume one bounded input slice per call; close on stale or completed.

    Distinct executing prompt identities spill to a private temporary SQLite
    DB, not a whole-history Python set or a second persisted display archive.
    """

    def __init__(self, source, timezone_id, end_ms, *, pricing=None):
        self.source = source
        self.timezone_id = timezone_id
        self.reducer = ArchiveMixRollup(timezone_id, end_ms, pricing=pricing)
        self.publication = None
        self._version = self._cursor = None
        self._counts = dict.fromkeys(self.reducer.totals, 0)
        self._prompts = sqlite3.connect("")
        try:
            self._prompts.execute("PRAGMA cache_size=-512")
            self._prompts.execute("""
                CREATE TABLE prompts(period TEXT NOT NULL, session TEXT NOT NULL, id TEXT NOT NULL,
                    PRIMARY KEY(period, session, id)) WITHOUT ROWID
            """)
        except BaseException:
            self.close()
            raise

    def step(self, history, *, eligible=lambda: True):
        if self._prompts is None:
            raise RuntimeError("archive_mix_build_closed")
        try:
            state = self._advance(history, eligible)
        except BaseException:
            self.close()
            raise
        if state is not MixBuildState.MORE:
            self.close()
        return state

    def _advance(self, history, eligible):
        if not eligible():
            return MixBuildState.STALE
        batch = history.usage_inputs(self.source, expected=self._version, after=self._cursor)
        if batch is None:
            return MixBuildState.STALE
        self._version = batch.version
        self._cursor = batch.next_key
        keys = self.reducer.add_slice(batch)
        with self._prompts as db:
            for period in self._counts:
                self._counts[period] += db.executemany("INSERT OR IGNORE INTO prompts VALUES(?,?,?)",
                    (key for key in keys if key[0] == period)).rowcount
        if self._cursor is not None:
            return MixBuildState.MORE
        rows = tuple(total.row() for total in self.reducer.result(self._counts))
        if eligible():
            self.publication = history.replace_mix_totals(
                self.source, self._version, self.timezone_id, rows, eligible=eligible)
        if self.publication is not None:
            return MixBuildState.PUBLISHED
        return MixBuildState.STALE

    def close(self):
        if self._prompts is not None:
            self._prompts.close()
            self._prompts = None

    def __exit__(self, *exc):
        self.close()
