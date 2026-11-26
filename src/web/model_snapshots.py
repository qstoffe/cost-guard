"""Committed Models display frames and detached requests for the report writer."""
from collections import deque
import sqlite3
from uuid import uuid4

from src.cache.web_archive import ArchiveFact, REPORT_CHECKPOINTS


DOMAIN = 'models-display/1'
ITEM = 'reference'
REFERENCE_FIELDS = ('publisher', 'model', 'release_date', 'selectable', 'superseded',
                    'superseded_selectable', 'reviewed_key', 'reviewed_successor_key')


class ModelSnapshots:
    def __init__(self, archive, *, notify=None):
        self.archive = archive
        self.run = uuid4().hex
        self.committed = None
        self.observed = 0
        self.notify = notify
        # One known request; coalesce bursts without making cache readers
        # acquire a dispatcher or worker lock.
        self.demand = deque(maxlen=1)
        self.retries = deque(maxlen=1)

    def publish(self, frame, now):
        prior = self.committed or {}
        same_source = prior.get('frame', {}).get('source_identity') == frame['source_identity']
        references = prior.get('benchmark') if same_source else None
        view = (frame.get('result') or {}).get('view') or {}
        rows = (view.get('model_catalog') or {}).get('rows')
        if isinstance(rows, (list, tuple)):
            references = dict(rows=[{key: row[key] for key in REFERENCE_FIELDS if key in row}
                                    for row in rows if isinstance(row, dict) and 'publisher' in row and 'model' in row],
                              timezone_id=view.get('timezone_id', 'UTC'))
        value = dict(run=self.run, frame=frame, benchmark=references)
        if value == self.committed:
            return
        try:
            previous = self.observed
            if not previous:
                _, facts = self.archive.history_item(DOMAIN, ITEM, 0)
                previous = max((fact.observed_ms for _, fact in facts), default=0)
            observed = max(now, previous + 1)
            fact = ArchiveFact(str(observed), observed, value)
            saved = self.archive.publish(REPORT_CHECKPOINTS, DOMAIN, {ITEM: fact})
        except (OSError, sqlite3.Error, ValueError):
            return  # Retry from the writer; do not expose an uncommitted replacement.
        if saved:
            self.committed, self.observed = value, observed
            if self.notify and any(prior.get('frame', {}).get(key) != frame.get(key)
                                   for key in ('result_id', 'source_identity', 'terminal', 'stale')):
                self.notify(('models',), ('all',))

    def _read(self):
        try:
            _, facts = self.archive.history_item(DOMAIN, ITEM, 0)
        except (OSError, sqlite3.Error):
            return {}
        for _, fact in facts:
            value = fact.value
            if value.get('run') == self.run:
                return value
        return {}

    def read(self):
        return self._read().get('frame')

    def read_benchmark(self):
        return self._read().get('benchmark') or {}

    def request(self, *, retry=False):
        (self.retries if retry else self.demand).append(True)

    def take_demand(self):
        retry, pending = bool(self.retries), bool(self.demand)
        if retry:
            self.retries.popleft()
        if pending:
            self.demand.popleft()
        return retry if retry or pending else None
