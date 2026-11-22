"""Source-fenced AI Stats cache adapter; no finite report or source fallback."""
from dataclasses import asdict
from threading import Lock

from src.analysis.ai_stats import scope_rollover, windows
from src.application.archive_stats_refresh import ArchiveStatsRefresh
from src.cache.display_stats_tokens import StatsTokenPublication
from src.presentation.cached_stats import cached_stats


class DisplayStats:
    def __init__(self, archive, publish):
        self._archive = archive
        self._publish = publish
        self._refresh = ArchiveStatsRefresh()
        self._signal = Lock()
        self._marks = {}

    def _binding(self, views):
        return (views.binding, self._archive.sessions.clear_fence) if views is not None else None

    def pending(self):
        return self._refresh.due(self._binding(self._archive.views))

    def advance(self, now_ms, *, active):
        archive = self._archive
        views = archive.views
        if views is None or not active():
            self.close()
            return
        binding = self._binding(views)

        def eligible():
            return archive.views is views and self._binding(views) == binding and active()

        published = self._refresh.advance(archive.history, views.source, views.timezone_id, binding, now_ms,
                                          eligible=eligible)
        if published is None or not published.changed_periods:
            return
        stamp = published.stamp
        with self._signal:
            if not eligible():
                return
            if isinstance(published, StatsTokenPublication):
                epoch = stamp.version.usage.archive_epoch
                token = (stamp.version.usage.revision, stamp.version.evidence, stamp.as_of)
                for period in published.changed_periods:
                    self._marks[period] = (*self._marks.get(period, (None, None))[:2], *token)
            else:
                epoch = stamp.version.archive_epoch
                for period in published.changed_periods:
                    self._marks[period] = (stamp.version.revision, stamp.as_of, *self._marks.get(period, ())[2:])
            self._publish("ai-stats-cache", dict(binding=views.binding, archive_epoch=epoch,
                periods=published.changed_periods, marks=self._marks.copy()))

    def reset(self, views, *, archive_epoch=None):
        with self._signal:
            if self._archive.views is views:
                self._marks.clear()
                self._publish("ai-stats-cache", dict(binding=views.binding if views else None,
                    marks={}, archive_epoch=archive_epoch, cleared=archive_epoch is not None))

    def snapshot(self, period, now_ms):
        archive = self._archive
        views = archive.views
        if views is None:
            return None
        binding = self._binding(views)
        start = dict(windows(views.timezone_id, now_ms))[period]
        value, token, epoch = archive.history.stats_view(views.source, views.timezone_id, period, start, now_ms)
        if archive.views is not views or self._binding(views) != binding:
            return None
        # This is not the canonical estimated working-time card. Even a current
        # subtotal has no authority over unseen, provisional or unmeasured work.
        calendar = value.row.calendar if value else None
        roots = value.row.roots if value else None
        token_row, token_as_of = token or (None, None)
        return dict(binding=views.binding, archive_epoch=epoch, period=period, start_ms=start,
                    valid_until_ms=scope_rollover(period, views.timezone_id, now_ms),
                    as_of_ms=value.stamp.as_of if value else None,
                    measured_working_ms=value.row.working_ms if value else None,
                     measured_calendar=asdict(calendar) if calendar else None,
                     measured_root_time=asdict(roots) if roots else None,
                     observed_tokens=str(token_row.observed) if token_row and token_row.observed is not None else None,
                     tokens_as_of_ms=token_as_of,
                     display=cached_stats(value.row if value else None, token_row), coverage="unknown")

    def close(self):
        self._refresh.withdraw()
