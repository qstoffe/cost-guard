"""One background Token Mix build; request paths only read its last commit."""
from contextlib import AbstractContextManager
from enum import Enum
from hashlib import sha256
import json
import sqlite3
from uuid import uuid4

from src.cache.display_mix_groups import GROUP_BATCH

from .archive_mix_groups import MixGroupStage
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

    def __init__(self, source, timezone_id, end_ms, *, pricing=None, grouped=False, reference=None):
        self.source = source
        self.timezone_id = timezone_id
        self.reducer = ArchiveMixRollup(timezone_id, end_ms, pricing=pricing)
        self.publication = None
        self._version = self._cursor = None
        self._group_cursor = None
        self._group_run = uuid4().hex if grouped else None
        self._group_hashes = {period: sha256() for period, _ in self.reducer.scopes} if grouped else {}
        self._counts = dict.fromkeys(self.reducer.totals, 0)
        self._prompts = sqlite3.connect("")
        try:
            self._prompts.execute("PRAGMA cache_size=-512")
            self._prompts.execute("""
                CREATE TABLE prompts(period TEXT NOT NULL, session TEXT NOT NULL, id TEXT NOT NULL,
                    PRIMARY KEY(period, session, id)) WITHOUT ROWID
            """)
            self._groups = MixGroupStage(self._prompts, self.reducer.periods_for, reference=reference) if grouped else None
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
        if self._group_cursor is not None:
            return self._export_groups(history, eligible)
        batch = history.usage_inputs(self.source, expected=self._version, after=self._cursor)
        if batch is None:
            return MixBuildState.STALE
        self._version = batch.version
        self._cursor = batch.next_cursor
        keys = self.reducer.add_slice(batch)
        with self._prompts as db:
            for period in self._counts:
                self._counts[period] += db.executemany("INSERT OR IGNORE INTO prompts VALUES(?,?,?)",
                    (key for key in keys if key[0] == period)).rowcount
            if self._groups is not None:
                self._groups.add(batch.entries)
        if self._cursor is not None:
            return MixBuildState.MORE
        if self._groups is not None:
            self._group_cursor = ("", "", "")
            return MixBuildState.MORE
        return self._publish(history, eligible)

    def _export_groups(self, history, eligible):
        page = tuple(self._groups.page(self._group_cursor, GROUP_BATCH))
        if not page:
            return self._publish(history, eligible)
        rows = tuple(group.row(key, prompts) for key, group, prompts in page)
        if not history.stage_mix_groups(self.source, self._version, self._group_run, rows, eligible=eligible):
            return MixBuildState.STALE
        for row in rows:
            self._group_hashes[row.period].update(json.dumps(row.values(), ensure_ascii=True).encode("ascii") + b"\n")
        self._group_cursor = page[-1][0]
        return MixBuildState.MORE

    def _publish(self, history, eligible):
        rows = tuple(total.row() for total in self.reducer.result(self._counts))
        if eligible():
            self.publication = history.replace_mix_totals(
                self.source, self._version, self.timezone_id, rows, eligible=eligible, group_run=self._group_run,
                group_marks={period: digest.hexdigest() for period, digest in self._group_hashes.items()})
        if self.publication is not None:
            return MixBuildState.PUBLISHED
        return MixBuildState.STALE

    def close(self):
        if self._prompts is not None:
            self._prompts.close()
            self._prompts = None

    def __exit__(self, *exc):
        self.close()
