"""Committed display frames for the archived Accounts timeline."""
import sqlite3
from time import monotonic

from src.analysis.account_timeline import period_start
from src.application.account_timeline import restore_range_totals
from src.cache.web_archive import ArchiveFact


DOMAIN = 'account-timeline-view/2'


class AccountTimelineSnapshots:
    def __init__(self, archive, notify):
        self.archive = archive
        self.notify = notify
        self.published = {}
        self._committed = {}
        self._restore_window = None
        self._restored = {}
        self.observed = 0

    def publish(self, *, zone, day, marker, now, periods, results, roster, ready,
                active, active_until):
        changes = {}
        for period in periods:
            view = results.get(period)
            previous = self.published.get(period)
            if view is None and previous is None:
                # On startup keep the previous run's compatible committed
                # graph until this run can replace it, not an empty seed.
                continue
            # Store the precomputed graph, not its source facts. Each finite
            # graph and its roster/status are from the same owner turn.
            result = dict(zone=zone, day=day, scope=marker, view=view,
                          series=roster if view is None else (), ready=ready,
                          active_until=active_until if period in active else 0, range_totals=True)
            if result != previous:
                changes[period] = result
        if not changes or not self.archive.path.is_file():
            return
        observed = max(now, self.observed + 1)
        try:
            facts = {period: ArchiveFact(str(observed), observed, value) for period, value in changes.items()}
            committed = self.archive.publish_checkpoint(DOMAIN, facts)
            if committed:
                # Keep wire values detached from the writer's change detection
                # and publish view and observed revision in the same swap.
                self._committed = {**self._committed, **committed}
                self.published.update((period, changes[period]) for period in committed)
                self.observed = observed
                if self.notify is not None:
                    self.notify(('accounts',), tuple(committed))
        except (OSError, sqlite3.Error, ValueError):
            pass  # Keep serving the last committed frame and retry on the next turn.

    def lookup(self, period, revision, *, zone, now):
        empty = dict(scope=None, revision=0, unchanged=False, view=None,
                     series=(), ready=False, acquiring=False)
        day = period_start('today', now, zone)
        frame = self._committed.get(period)
        if frame is not None and frame.value['zone'] == zone and frame.value['day'] == day:
            return self._reply(frame, revision, now)
        try:
            frame = self._read(period, zone, day)
        except (OSError, sqlite3.Error):
            return empty
        return self._reply(frame, revision, now, restored=True) if frame is not None else empty

    def _read(self, period, zone, day):
        _, candidates = self.archive.history_item(DOMAIN, period, 0)
        start = period_start(period, day, zone)
        for _, fact in candidates:
            value = fact.value
            view = value.get('view')
            if (value.get('zone') == zone and value.get('day') == day
                    and (view is None or view.get('start_ms', start) == start)):
                return fact
        return None

    def restored_periods(self, periods, zone, day):
        """The owner checks for durable frames before admitting startup projections."""
        if self._restore_window != (zone, day):
            self._restore_window = (zone, day)
            self._restored = {}
        if not self.archive.path.is_file():
            return frozenset()
        for period in periods - self._restored.keys():
            try:
                frame = self._read(period, zone, day)
            except (OSError, sqlite3.Error):
                # A read error is not proof of a cold cache. Retry before publishing.
                continue
            view = frame.value.get('view') if frame is not None else None
            self._restored[period] = view is not None and any(
                point is not None for item in view['series'] for point in item.get('points', ()))
        return frozenset(period for period in periods if self._restored.get(period, True))

    @staticmethod
    def _reply(fact, revision, now, *, restored=False):
        value, current = fact.value, fact.observed_ms
        view = value.get('view')
        unchanged = view is not None and revision == current
        if restored and view is not None and not unchanged and not value.get('range_totals'):
            view = restore_range_totals(view)
        reply = dict(scope=value['scope'], revision=current, unchanged=unchanged,
                     view=None if unchanged else view, series=value['series'], ready=value['ready'],
                     acquiring=(not restored and value['ready']
                         and 0 <= now - current < 5_000 and monotonic() < value['active_until']))
        if restored and value.get('view') is not None:
            reply['restored'] = True
        return reply

    def close(self):
        self._committed = {}
