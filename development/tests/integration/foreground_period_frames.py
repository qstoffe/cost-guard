"""Publish selected-period fixtures without scheduling a competing historian."""
from copy import copy
from decimal import Decimal
from types import SimpleNamespace

from development.tests.fixtures.account_periods import request, subscription
from development.tests.fixtures.ai_stats_views import stats_result
from development.tests.fixtures.token_mix_views import TokenMixJobs
from src.analysis.period_ccost import PeriodCCostIndex
from src.analysis.timezones import calendar_periods
from src.application.account_timeline import account_roster, timeline_view
from src.cache.web_archive import ArchiveFact
from src.reports import ReportKind, ReportRequest
from src.reports.models import AccountProjection
from src.watch.account_timeline_snapshots import AccountTimelineSnapshots
from src.web.history_reports import HistoryReports, VIEWS, checkpoint_stamp, settings_signature


class PeriodFrames:
    period = '7-days'

    def __init__(self, host, archive, now):
        self.archive, self.now = archive, now
        self.config = {'timezone': 'UTC'}
        self.windows = dict(calendar_periods('UTC', now))
        self.reports = HistoryReports(SimpleNamespace(archive=archive), lambda: None)
        self.charts = AccountTimelineSnapshots(archive, None)
        # Give the real HTTP routes committed projection readers. Keep the
        # background fixture host separate: no owner tick may create new data.
        reader = copy(host)
        reader.live.source_failure = None
        reader.history_reports = self.reports
        reader.history_config = self.config
        reader.history_accounts = SimpleNamespace(lookup=self.chart)
        reader.history_zone = 'UTC'
        host.server.lifecycle = reader

    def chart(self, period, revision, *, zone):
        return self.charts.lookup(period, revision, zone=zone, now=self.now)

    def publish_chart(self, generation):
        native = subscription()
        entry = request('call', self.now - 5000, amount=10 * generation, ref=native.ref)
        index = PeriodCCostIndex((entry,), lambda _, tokens: Decimal(tokens.input), account_only=True)
        roster = account_roster((AccountProjection(native, 'Fixture account'),))
        view = timeline_view(self.period, self.now, 'UTC', roster, index,
            first_covered_ms=self.windows[self.period], gaps=()).to_json()
        self.charts.publish(zone='UTC', day=self.windows['today'], marker='fixture', now=self.now + generation,
            periods=(self.period,), results={self.period: view}, roster=(), ready=True, active=(), active_until=0)
        assert self.chart(self.period, None, zone='UTC')['view']['series'][0]['total']['amount'] == str(10 * generation)

    def publish_report(self, kind, generation):
        if kind is ReportKind.AI_STATS:
            result = stats_result(ReportRequest(kind, stats_scope=self.period))
            for period in result['view']['ai_stats']:
                for metric in period['metrics']:
                    if metric.get('session_title'):
                        metric['session_title'] = f'Session {generation} in {period["period"]}'
        else:
            jobs = TokenMixJobs()
            key = jobs.submit(ReportRequest(kind, token_mix_scope=self.period))
            result = jobs.jobs[key]['result']
            for i, row in enumerate(result['view']['model_token_mix']):
                row['model'] = f'Model {i}, revision {generation}'
        result.update(sequence=generation, observed_at_ms=self.now + generation)
        stamp = checkpoint_stamp(self.config, 'UTC', self.windows[self.period], settings_signature(self.config))
        fact = ArchiveFact(str(generation), self.now + generation,
            dict(stamp=stamp, run=self.reports.run, views={kind.value: result}))
        assert self.period in self.archive.publish_checkpoint(VIEWS, {self.period: fact})

    def close(self):
        self.reports.close()
        self.charts.close()
