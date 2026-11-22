"""Source-fenced AI Stats cache adapter; no finite report or source fallback."""
from dataclasses import asdict
from threading import Lock

from src.analysis.ai_stats import windows
from src.application.archive_stats_refresh import ArchiveStatsRefresh


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
        usage = stamp.version.usage
        with self._signal:
            if not eligible():
                return
            self._marks.update(dict.fromkeys(published.changed_periods, (usage.revision, stamp.version.evidence,
                                                                          stamp.as_of)))
            self._publish("ai-stats-cache", dict(binding=views.binding, archive_epoch=usage.archive_epoch,
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
        value, epoch = archive.history.stats_time_view(views.source, views.timezone_id, period, start, now_ms)
        if archive.views is not views or self._binding(views) != binding:
            return None
        # This is not the canonical estimated working-time card. Even a current
        # subtotal has no authority over unseen, provisional or unmeasured work.
        calendar = value.row.calendar if value else None
        roots = value.row.roots if value else None
        return dict(binding=views.binding, archive_epoch=epoch, period=period, start_ms=start,
                    as_of_ms=value.stamp.as_of if value else None,
                    measured_working_ms=value.row.working_ms if value else None,
                    measured_calendar=asdict(calendar) if calendar else None,
                    measured_root_time=asdict(roots) if roots else None, coverage="unknown")

    def close(self):
        self._refresh.withdraw()
