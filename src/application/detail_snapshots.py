"""Committed projections for live and retained Session Detail reads."""
from dataclasses import dataclass
import logging
import sqlite3
from uuid import uuid4

from src.cache.web_archive import ArchiveFact

from .detail_archive import DOMAIN, readable_detail
from .session_values import INVALID_REASONS


LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DetailRead:
    fact: ArchiveFact | None
    frame: dict
    runtime: bool = False

    @property
    def acquisition(self):
        return self.frame.get('acquisition')


class DetailSnapshots:
    def __init__(self, archive, clock):
        self.archive = archive
        self.clock = clock
        self.run = uuid4().hex
        self.written = {}
        self.pending = {}

    def publish(self, key, status, *, projection=None):
        if projection is not None:
            self.pending[key] = projection
        projection = self.pending.get(key)
        if projection is not None and projection['revision'] != status['revision']:
            self.pending.pop(key)
            projection = None
        if projection is None and status == self.written.get(key):
            return
        try:
            self.archive.publish_detail_runtime(self.run, key, status, projection=projection)
        except (OSError, sqlite3.Error, ValueError):
            LOG.debug('detail_runtime_write_unavailable')
        else:
            self.written[key] = status
            self.pending.pop(key, None)

    def read(self, key, after, *, proof=None):
        try:
            (frame, projection), candidates = self.archive.detail_snapshot(DOMAIN, self.run, key)
            saved = readable_detail(key, candidates)
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
            return DetailRead(None, {})
        if frame is None:
            return DetailRead(saved, {})
        validated = frame.get('validated')
        authority = frame['acquisition'].get('reason')
        live = (projection is not None and frame['revision'] is not None
                and projection['revision'] == frame['revision'] and not frame['unavailable']
                and authority not in INVALID_REASONS and validated is not None
                and 0 <= self.clock() - validated <= 3600 and frame['generation'] > after)
        # Settled data from the historical lane can be newer than the detail
        # lane's capture. Never displace a current Running proof with old facts.
        running_proof = bool(frame['running'])
        if running_proof and proof and proof['scope'] == frame.get('execution_scope') and (
                proof['observed_at_ms'] > (frame['observed'] or 0)):
            running_proof = bool(set(frame.get('running_ids', ())).intersection(proof['running']))
        elif running_proof and live and self.clock() - validated > 300:
            running_proof = False
        newer_saved = (saved is not None and not running_proof
                       and saved.partition == frame['partition']
                       and saved.observed_ms > (frame['observed'] or 0))
        if live and not newer_saved:
            fact = ArchiveFact(frame['revision'], frame['observed'], projection['value'], frame['partition'])
            return DetailRead(fact, frame, runtime=True)
        return DetailRead(saved, frame)

    def discard(self, key=None):
        try:
            if self.archive.path.is_file():
                self.archive.clear_detail_runtime(self.run, key)
        except (OSError, sqlite3.Error):
            LOG.debug('detail_runtime_cleanup_unavailable')
        if key is None:
            self.written.clear()
            self.pending.clear()
        else:
            self.written.pop(key, None)
            self.pending.pop(key, None)
