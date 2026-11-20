"""Time, coverage, native roster and source-qualified account history regressions."""
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest

from development.tests.fixtures.account_periods import request, subscription
from development.tests.fixtures.opencode_v2_service import source_with_current_service
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.analysis.account_timeline import DAY_MS, timeline_buckets
from src.analysis.period_ccost import PeriodCCostIndex
from src.application.account_timeline import quota_roster, retain_compatible_quotas, timeline_view
from src.application.session_quota import source_scope
from src.domain import QuotaComponent
from src.reports.models import AccountProjection
from src.sources.errors import SourceConcurrentChangeError
from src.sources.opencode_v2 import OpenCodeV2Source
from src.watch.observers import observe_catalog
from src.watch.source_reads import SourceReads
from src.watch.account_timeline import AccountTimeline, TimelineHistory, ROOTS_PER_TURN
from src.web.dispatch import DataDispatcher


def stamp(value):
    return int(datetime.fromisoformat(value).timestamp() * 1000)


NOV_1 = stamp('2026-11-01T00:00:00+00:00')
NOV_5 = stamp('2026-11-05T05:00:00+00:00')


def projected(*accounts):
    return tuple(AccountProjection(item, f'Safe label {index + 1}')
                 for index, item in enumerate(accounts))


class TimelineBucketsTests(unittest.TestCase):
    def test_spring_gap_and_autumn_repeat_have_distinct_real_boundaries(self):
        for now, expected in (
            ('2026-03-29T04:30:00+02:00', ('00:00+01:00', '01:00+01:00', '03:00+02:00', '04:00+02:00')),
            ('2026-10-25T04:30:00+01:00', ('00:00+02:00', '01:00+02:00', '02:00+02:00',
                                          '02:00+01:00', '03:00+01:00', '04:00+01:00')),
        ):
            with self.subTest(now=now):
                start, buckets = timeline_buckets('today', stamp(now), 'Europe/Stockholm')
                left = [stamp(now[:11] + item) for item in expected]
                self.assertEqual(left[0], start)
                self.assertEqual(list(zip(left, [*left[1:], stamp(now)])), list(buckets))

    def test_rolling_cutoffs_are_absolute_and_keep_partial_calendar_edges(self):
        now = stamp('2026-11-01T11:25:00+01:00')
        for period, days in (('7-days', 7), ('30-days', 30)):
            start, buckets = timeline_buckets(period, now, 'Europe/Stockholm')
            self.assertEqual(now - days * DAY_MS, start)
            self.assertEqual(days + 1, len(buckets))
            self.assertEqual(stamp('2026-11-01T00:00:00+01:00'), buckets[-1][0])
            self.assertEqual(now, buckets[-1][1])
        _, buckets = timeline_buckets('7-days', now, 'Europe/Stockholm')
        self.assertEqual(stamp('2026-10-26T00:00:00+01:00'), buckets[0][1])

    def test_calendar_month_and_long_history_span_leap_day_and_year_rollover(self):
        start, days = timeline_buckets('month', stamp('2028-02-29T13:00:00+00:00'), 'UTC')
        self.assertEqual(stamp('2028-02-01T00:00:00+00:00'), start)
        self.assertEqual(29, len(days))
        first = stamp('2026-12-31T22:30:00+00:00')
        now = stamp('2028-02-29T13:00:00+00:00')
        _, months = timeline_buckets('all', now, 'UTC', earliest_ms=first)
        self.assertEqual((first, stamp('2027-01-01T00:00:00+00:00')), months[0])
        self.assertEqual((start, now), months[-1])
        self.assertEqual(15, len(months))


class TimelineProjectionTests(unittest.TestCase):
    def view(self, accounts, entries, *, gaps=(), start=NOV_1, value=None, now=NOV_5):
        index = PeriodCCostIndex(entries, value or (lambda _, tokens: Decimal(tokens.input)), verified_models=True)
        return timeline_view('month', now, 'UTC', quota_roster(accounts), index,
                             first_covered_ms=start, gaps=gaps).to_json()['series']

    def test_per_bucket_not_cumulative_and_never_joins_missing_history(self):
        native = subscription(identity='private-account-key')
        calls = (request('one', NOV_1 + 5, amount=50_000, ref=native.ref),
                 request('two', NOV_1 + 2 * DAY_MS, amount=12_000, ref=native.ref))
        series = self.view(projected(native), calls, gaps=((NOV_1 + 3 * DAY_MS, NOV_5),))
        expected = ['50000', '0', '12000', None, None]
        self.assertEqual(expected, [p['amount'] if p else None for p in series[0]['points']])
        self.assertEqual(series[0]['points'], series[1]['points'])
        self.assertEqual([True, False], [row['primary'] for row in series])
        self.assertNotIn('private-account-key', str(series))

    def test_covered_zero_differs_from_partial_pricing_attribution_and_source_gaps(self):
        a, b = subscription(identity='first'), subscription(identity='second')
        calls = (request('a', NOV_1 + 1, amount=500, ref=a.ref),
                 request('ambiguous', NOV_1 + DAY_MS, amount=300),
                 request('unpriced', NOV_1 + 2 * DAY_MS, amount=700, ref=b.ref, model='missing'))
        rows = self.view(projected(a, b), calls, value=lambda model, tokens:
            None if model.model == 'missing' else Decimal(tokens.input))
        self.assertEqual(['500', None, '0', '0', '0'], [p['amount'] if p else None for p in rows[0]['points']])
        self.assertEqual(['0', None, None, '0', '0'], [p['amount'] if p else None for p in rows[2]['points']])
        unknown = self.view(projected(a), (), start=None)
        self.assertTrue(all(p is None for p in unknown[0]['points']))

    def test_model_quota_includes_deduplicated_child_usage_and_only_matching_models(self):
        native = subscription()
        model = QuotaComponent('Model weekly', scope='model', model_id='GPT-Test')
        native = replace(native, primary_quota_label='weekly', quotas=(*native.quotas, model))
        child = replace(request('physical', NOV_1 + 55, amount=9, ref=native.ref),
                        session_id='child', root_session_id='root', parent_session_id='root')
        other = request('other model', NOV_1 + 58, amount=13, model='other')
        future = request('exact end', NOV_5, amount=500, ref=native.ref)
        series = self.view(projected(native), (child, child, other, future))
        self.assertEqual(['weekly', '5-hour', 'Model weekly'], [row['quota'] for row in series])
        self.assertEqual(['22', '22', '9'], [row['points'][0]['amount'] for row in series])
        self.assertEqual(['~$0.22', '~$0.22', '$0.09'], [row['points'][0]['display']['usd'] for row in series])
        self.assertEqual(['0', '0', '0'], [row['points'][-1]['amount'] for row in series])

    def test_partial_observation_retains_compatible_quota_but_real_change_retires_it(self):
        native = subscription()
        previous = {native.key: native}
        partial = replace(native, availability='partial', quotas=native.quotas[:1])
        retained = retain_compatible_quotas(projected(partial), previous)
        self.assertEqual(native.quotas, retained[0].account.quotas)
        observed = retain_compatible_quotas(projected(replace(partial, availability='available')), previous)
        self.assertEqual(native.quotas[:1], observed[0].account.quotas)
        changed = replace(partial, ref=replace(native.ref, account_id='new'))
        self.assertEqual(1, len(quota_roster(retain_compatible_quotas(projected(changed), previous))))

    def test_small_positive_uses_product_format_and_nonzero_numeric_headroom(self):
        native = subscription()
        rows = self.view(projected(native), (request('tiny', NOV_1 + 1, ref=native.ref),),
                         value=lambda *_: Decimal('.00001'))
        self.assertEqual({'credits': '<0.1', 'usd': '<$0.01'}, rows[0]['points'][0]['display'])
        self.assertEqual(Decimal(0), Decimal(rows[0]['ticks'][0]['amount']))
        self.assertGreater(Decimal(rows[0]['ticks'][-1]['amount']), Decimal('.00001'))


class TimelineDemandTests(unittest.TestCase):
    def test_silent_failure_preserves_last_good_then_a_new_revision_replaces_it(self):
        source = SyntheticMonthSource(1, 1, month_start_ms=NOV_1)
        key, snapshot = next(iter(source.snapshots.items()))
        source.snapshots[key] = replace(snapshot, complete=True)
        service = SimpleNamespace(source=source, close_accounts=lambda: None, progress=lambda *_: None)
        lane = AccountTimeline(lambda _: service, SourceReads())
        self.addCleanup(lane.close)
        args = dict(source=source_scope(source), observation=observe_catalog(source), periods={'month'},
            boosted=False, accounts=projected(subscription('github-copilot')), zone='UTC',
            catalog=FakePricingProvider().catalog, prices=lambda: None, migration_gap=None)

        def publish(now):
            lane.tick(**args, now_ms=now)
            lane.job.result(2)
            lane.tick(**args, now_ms=now + 1)
            return lane.lookup('month')

        initial = publish(NOV_5)
        invocation = snapshot.invocations[0]
        source.snapshots[key] = replace(snapshot, complete=True, source_revision='new',
            invocations=(replace(invocation, tokens=replace(invocation.tokens, input=1000)),))
        args['observation'] = observe_catalog(source)
        load = source.load_session_snapshot

        def fail(_):
            raise SourceConcurrentChangeError('synthetic tree changed')

        source.load_session_snapshot = fail
        self.assertEqual(initial, publish(NOV_5 + 15_000))
        source.load_session_snapshot = load
        corrected = publish(NOV_5 + 46_000)
        self.assertGreater(Decimal(corrected['view']['series'][0]['peak']),
                           Decimal(initial['view']['series'][0]['peak']))
        self.assertEqual(initial['scope'], corrected['scope'])
        lane.tick(**dict(args, source=('new source', None, None)), now_ms=NOV_5 + 47_000, available=False)
        self.assertNotEqual(initial['scope'], lane.lookup('month')['scope'])
        self.assertIsNone(lane.lookup('month')['view'])

    def test_v2_catalog_revisions_qualify_isolated_history_including_children(self):
        with source_with_current_service() as (origin, server, registration):
            self.addCleanup(origin.close_reads)
            user, reply = server.messages['ses_current']
            server.messages['ses_current_child'] = [dict(user, id='child-prompt'),
                dict(reply, id='child-reply', time={'created': 4200, 'completed': 4700})]
            observation = observe_catalog(origin, include_archived_revisions=True)

            def worker(_):
                reader = OpenCodeV2Source(registration, timeout_seconds=2)
                reader.inherit_live_evidence(origin)
                return SimpleNamespace(source=reader, close_accounts=lambda: None, progress=lambda *_: None)

            history = TimelineHistory(worker, SourceReads())
            values, more, _, interrupted = history.step(source_scope(origin), observation, ('all',),
                quota_roster(projected(subscription('openai'))), 'UTC',
                FakePricingProvider().catalog, lambda: None, None, NOV_5)

            self.assertEqual({'all'}, values.keys())
            self.assertFalse(more or interrupted)
            evidence = history.roots['ses_current']
            self.assertTrue(evidence.acquired)
            self.assertIn('ses_current_child', {entry.session_id for entry in evidence.entries})
            self.assertEqual(observation.revisions['ses_current'], evidence.revision)

    def test_one_chart_lane_coalesces_periods_and_expires_hidden_demand(self):
        now = 1
        dispatch = DataDispatcher(None, clock=lambda: now)
        dispatch.interest('one', 'accounts', True, account_period='month')
        dispatch.interest('two', 'accounts', True, account_period='month')
        self.assertEqual(({'month'}, True), dispatch.account_timeline_demand())
        now = 18
        dispatch.interest('one', 'accounts', True, account_period='month')
        self.assertEqual(({'month'}, False), dispatch.account_timeline_demand())
        now = 25
        dispatch.interest('one', 'accounts', True, account_period='all')
        self.assertEqual(({'month', 'all'}, True), dispatch.account_timeline_demand())
        dispatch.interest('one', 'accounts', False, account_period='all')
        self.assertEqual(({'month'}, False), dispatch.account_timeline_demand())
        now = 100
        self.assertEqual((set(), False), dispatch.account_timeline_demand())

    def test_bounded_slices_reuse_unchanged_root_facts_across_periods_and_retire_removed_roots(self):
        source = SyntheticMonthSource(217, 5, month_start_ms=NOV_1)
        source.snapshots = {key: replace(snapshot, complete=True) for key, snapshot in source.snapshots.items()}
        service = SimpleNamespace(source=source, close_accounts=lambda: None, progress=lambda *_: None)
        catalog = FakePricingProvider().catalog
        history = TimelineHistory(lambda _: service, SourceReads())
        roster = quota_roster(projected(subscription('github-copilot'), subscription('openai'), subscription()))
        observation = observe_catalog(source, include_archived_revisions=True)

        def turn(periods, now=NOV_5):
            before = source.load_count
            result = history.step(source_scope(source), observation, periods, roster, 'UTC',
                                  catalog, lambda: None, None, now)
            self.assertLessEqual(source.load_count - before, ROOTS_PER_TURN)
            return result

        values, more, _, _ = turn(('all', 'today'))
        self.assertTrue(more)
        self.assertEqual({'all', 'today'}, values.keys())
        for index in range(1, 20):
            values, more, _, _ = turn(('all', 'month'), NOV_5 + 1000 * index)
            if not more:
                break
        self.assertFalse(more)
        self.assertEqual(217, source.load_count)
        self.assertGreater(Decimal(values['all'].to_json()['series'][0]['peak']), 0)
        turn(('30-days',), NOV_5 + 25_000)
        self.assertEqual(217, source.load_count)
        removed, _ = source.snapshots.popitem()
        newest = next(iter(source.snapshots))
        source.snapshots[newest] = replace(source.snapshots[newest], source_revision='corrected')
        observation = observe_catalog(source, include_archived_revisions=True)
        _, _, invalidated, _ = turn(('all',), NOV_5 + 27_000)
        self.assertTrue(invalidated)
        self.assertNotIn(removed, history.roots)
        self.assertEqual('corrected', history.roots[newest].revision)
        self.assertEqual(218, source.load_count)
