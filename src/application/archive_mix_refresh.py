"""Cooperative Token Mix work for the existing serialized catalog lane."""
import sqlite3
import time

from src.analysis.ai_stats import windows

from .archive_mix_build import ArchiveMixBuild, MixBuildState
from .archive_mix_identity import qualified_mix_reference


class ArchiveMixRefresh:
    def __init__(self, *, clock=time.monotonic, grouped=False):
        self._clock = clock
        self._probe_at = 0
        self._binding = None
        self._build = None
        self._grouped = grouped

    def due(self, binding):
        """In-memory admission hint only; safe on the Live observer."""
        return binding != self._binding or binding is not None and self._clock() >= self._probe_at

    def advance(self, history, source, timezone_id, binding, now_ms, *, eligible, reference=lambda: None):
        """Run one slice or one cheap due-check, never acquire source or prices."""
        try:
            return self._advance(history, source, timezone_id, binding, now_ms, eligible, reference)
        except (OSError, sqlite3.Error):
            self.close()
            self._probe_at = self._clock() + 5
            return None

    def _advance(self, history, source, timezone_id, binding, now_ms, eligible, reference):
        if self._binding != binding:
            self.close()
            self._binding = binding
            self._probe_at = 0
        if not eligible():
            self.close()
            return None
        scopes = windows(timezone_id, now_ms)
        if self._build is not None and (self._build.reducer.scopes != scopes
                                       or self._build.reducer.end_ms > now_ms):
            self.close()
        if self._build is None:
            stamp = history.mix_refresh(source, timezone_id, now_ms)
            # An optional unavailable local catalog must not stall the archive.
            try:
                catalog = qualified_mix_reference(reference(), now_ms) if self._grouped else None
            except (OSError, sqlite3.Error):
                catalog = None
            previous = stamp.reference if stamp else None
            if catalog and previous and catalog.stamp.observed_at < previous.observed_at:
                catalog = None  # A cache fallback may not replace a newer proof.
            reference_changed = catalog and (previous is None or catalog.stamp.signature != previous.signature)
            if stamp is not None and (stamp.end_ms > now_ms or
                     not stamp.changed and not reference_changed and (stamp.grouped or not self._grouped) and
                    windows(timezone_id, stamp.end_ms) == scopes):
                if self._grouped:
                    history.reclaim_mix_groups(source)
                self._probe_at = self._clock() + 5
                return None
            if self._grouped:
                history.reclaim_mix_groups(source)
            self._build = ArchiveMixBuild(source, timezone_id, now_ms, grouped=self._grouped, reference=catalog)
        state = self._build.step(history, eligible=eligible)
        if state == MixBuildState.MORE:
            return None
        publication = self._build.publication
        self.close()
        self._probe_at = self._clock() + (2 if state == MixBuildState.STALE else 5)
        return publication

    def close(self):
        # Must be called in the catalog executor, even on shutdown or rebind.
        if self._build is not None:
            self._build.close()
            self._build = None

    def withdraw(self):
        self.close()
        self._binding = None
        self._probe_at = 0
