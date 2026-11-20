"""Time, coverage, native roster and source-qualified account history regressions."""
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from development.tests.fixtures.account_periods import request, subscription
from development.tests.fixtures.opencode_v2_service import source_with_current_service
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from src.analysis.account_timeline import DAY_MS, timeline_window
from src.analysis.period_ccost import PeriodCCostIndex
from src.application.account_timeline import quota_roster, retain_compatible_quotas, retain_refresh, timeline_view
from src.application.session_quota import source_scope
from src.domain import QuotaComponent
from src.reports.models import AccountProjection
from src.sources.errors import SourceConcurrentChangeError
from src.sources.opencode_v2 import OpenCodeV2Source
from src.watch.observers import observe_catalog
from src.watch.source_reads import SourceReads
from src.watch.account_timeline import AccountTimeline, TimelineHistory, FOREGROUND_SLICE_MS, ROOTS_PER_TURN
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
                window = timeline_window('today', stamp(now), 'Europe/Stockholm')
                left = [stamp(now[:11] + item) for item in expected]
                self.assertEqual(left[0], window.start)
                self.assertEqual(tuple(zip(left, [*left[1:], stamp(now)])), window.buckets)
                self.assertEqual((len(left) - 1,), window.partial)

    def test_seven_days_is_still_rolling_with_partial_calendar_edges(self):
        now = stamp('2026-11-01T11:25:00+01:00')
        window = timeline_window('7-days', now, 'Europe/Stockholm')
        self.assertEqual(now - 7 * DAY_MS, window.start)
        self.assertEqual(8, len(window.buckets))
        self.assertEqual((stamp('2026-11-01T00:00:00+01:00'), now), window.buckets[-1])
        self.assertEqual((0, 7), window.partial)
        self.assertEqual(stamp('2026-10-26T00:00:00+01:00'), window.buckets[0][1])
        midnight = stamp('2027-01-01T00:00:00+00:00')
        window = timeline_window('7-days', midnight, 'UTC')
        self.assertEqual((stamp('2026-12-31T00:00:00+00:00'), midnight), window.buckets[-1])
        self.assertEqual((), window.partial)

    def test_thirty_days_includes_today_and_exactly_29_prior_dates(self):
        now = stamp('2026-11-20T00:45:00+01:00')
        window = timeline_window('30-days', now, 'Europe/Stockholm')
        self.assertEqual(stamp('2026-10-22T00:00:00+02:00'), window.start)
        self.assertEqual(tuple([f'2026-10-{day}' for day in range(22, 32)] +
                               [f'2026-11-{day:02}' for day in range(1, 21)]), window.dates)
        self.assertEqual((stamp('2026-11-20T00:00:00+01:00'), now), window.buckets[-1])
        self.assertEqual((29,), window.partial)
        self.assertEqual((), window.future)

    def test_month_axis_reserves_each_local_date_at_first_paint_and_midnight_rollover(self):
        for day, count, current in (('2026-11-01', 30, 0), ('2026-11-02', 30, 1), ('2026-11-20', 30, 19),
                                     ('2027-01-02', 31, 1), ('2027-02-02', 28, 1), ('2028-02-02', 29, 1),
                                     ('2028-02-29', 29, 28), ('2028-03-01', 31, 0)):
            with self.subTest(day=day):
                now = stamp(f'{day}T00:00:00+01:00')
                window = timeline_window('month', now, 'Europe/Stockholm')
                self.assertEqual(tuple(f'{day[:7]}-{number:02}' for number in range(1, count + 1)), window.dates)
                self.assertEqual(count, len(window.buckets))
                self.assertEqual((now, now), window.buckets[current])
                self.assertEqual((current,), window.partial)
                self.assertEqual(tuple(range(current + 1, count)), window.future)

    def test_today_keeps_an_empty_current_hour_on_an_exact_clock_boundary(self):
        now = stamp('2026-10-25T02:00:00+01:00')
        window = timeline_window('today', now, 'Europe/Stockholm')
        self.assertEqual(4, len(window.buckets))
        self.assertEqual((stamp('2026-10-25T02:00:00+02:00'), now), window.buckets[-2])
        self.assertEqual((now, now), window.buckets[-1])
        self.assertEqual((3,), window.partial)

    def test_calendar_and_rolling_buckets_cover_both_dst_day_lengths(self):
        for now, date, hours in (('2026-03-30T12:00:00+02:00', '2026-03-29', 23),
                                 ('2026-10-26T12:00:00+01:00', '2026-10-25', 25)):
            with self.subTest(date=date):
                for period in ('7-days', '30-days', 'month'):
                    window = timeline_window(period, stamp(now), 'Europe/Stockholm')
                    index = window.dates.index(date) if window.dates else -2
                    left, right = window.buckets[index]
                    self.assertEqual(hours * 3_600_000, right - left)


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
        expected = ['50000', '0', '12000', None, None] + [None] * 25
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
        self.assertEqual(['500', None, '0', '0', '0'], [p['amount'] if p else None for p in rows[0]['points'][:5]])
        self.assertEqual(['0', None, None, '0', '0'], [p['amount'] if p else None for p in rows[2]['points'][:5]])
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
        self.assertEqual(['0', '0', '0'], [row['points'][4]['amount'] for row in series])

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

    def test_pending_overlap_allows_only_provisional_positive_and_preserves_nonpending_gaps(self):
        native = subscription()
        index = PeriodCCostIndex((request('one', NOV_1 + DAY_MS + 5, amount=100, ref=native.ref),),
                                 lambda _, tokens: Decimal(tokens.input), verified_models=True)
        pending = ((NOV_1 + DAY_MS, NOV_1 + DAY_MS + 100), (NOV_1 + 3 * DAY_MS, NOV_1 + 4 * DAY_MS))
        permanent = ((NOV_1 + 2 * DAY_MS, NOV_1 + 3 * DAY_MS),)
        result = timeline_view('month', NOV_5, 'UTC', quota_roster(projected(native)), index,
                               first_covered_ms=NOV_1, gaps=permanent, pending=pending).to_json()
        self.assertEqual([1, 3], result['pending_buckets'])
        self.assertEqual(['$0.00', '~$1.00', None, None, '$0.00'],
                         [point['display']['usd'] if point else None for point in result['series'][0]['points'][:5]])

    def test_missing_valuation_can_settle_without_zero_or_loading(self):
        result = timeline_view('month', NOV_5, 'UTC', quota_roster(projected(subscription())), None,
                               first_covered_ms=NOV_1, gaps=()).to_json()
        self.assertEqual([], result['pending_buckets'])
        self.assertEqual([None] * 30, result['series'][0]['points'])

    def test_refresh_retains_a_usable_value_but_never_across_price_or_gap(self):
        native = subscription()
        roster = quota_roster(projected(native))
        index = PeriodCCostIndex((request('old', NOV_1 + 5, amount=100, ref=native.ref),),
                                 lambda _, tokens: Decimal(tokens.input), verified_models=True)
        prior = timeline_view('month', NOV_5, 'UTC', roster, index, first_covered_ms=NOV_1,
                              gaps=(), price_revision='rates').to_json()
        day = ((NOV_1, NOV_1 + DAY_MS),)
        options = dict(first_covered_ms=NOV_1, gaps=(), pending=day, initial_pending=(), price_revision='rates')

        def view(**changes):
            return timeline_view('month', NOV_5 + 1000, 'UTC', roster, None, **(options | changes)).to_json()

        held = retain_refresh(prior, view())
        self.assertEqual('$1.00', held['series'][0]['points'][0]['display']['usd'])
        self.assertEqual([0], held['pending_buckets'])
        self.assertEqual([], held['initial_pending_buckets'])
        self.assertIsNone(retain_refresh(prior, view(gaps=day))['series'][0]['points'][0])
        self.assertIsNone(retain_refresh(prior, view(initial_pending=day))['series'][0]['points'][0])
        self.assertIsNone(retain_refresh(prior, view(price_revision='new rates'))['series'][0]['points'][0])

    def test_future_slots_never_query_the_index_or_acquire_history(self):
        native = subscription()
        first = NOV_1 + DAY_MS
        now = first + 100
        calls = []
        index = PeriodCCostIndex((), lambda *_: Decimal(1), verified_models=True)
        cost = index.cost

        def observed_cost(route, account, left, right, model=None):
            calls.append((left, right))
            return cost(route, account, left, right, model)

        index.cost = observed_cost
        view = timeline_view('month', now, 'UTC', quota_roster(projected(native)), index,
                             first_covered_ms=NOV_1, gaps=(), pending=((now, now + DAY_MS),)).to_json()
        self.assertEqual({(NOV_1, first), (first, now)}, set(calls))
        self.assertEqual(now, view['end_ms'])
        self.assertEqual(list(range(2, 30)), view['future_buckets'])
        self.assertEqual([], view['pending_buckets'])
        self.assertEqual([None] * 28, view['series'][0]['points'][2:])

    def test_thirty_day_cost_boundaries_are_half_open_including_local_midnight(self):
        first = stamp('2026-10-22T00:00:00+02:00')
        second = stamp('2026-10-23T00:00:00+02:00')
        now = stamp('2026-11-20T00:01:00+01:00')
        account = subscription()
        facts = tuple(request(str(at), at, amount=amount, ref=account.ref)
                      for at, amount in ((first - 1, 700), (first, 1), (second, 2), (now - 1, 3), (now, 900)))
        index = PeriodCCostIndex(facts, lambda _, tokens: Decimal(tokens.input), verified_models=True)
        view = timeline_view('30-days', now, 'Europe/Stockholm', quota_roster(projected(account)), index,
                             first_covered_ms=first - DAY_MS, gaps=()).to_json()
        self.assertEqual(['1', '2'] + ['0'] * 27 + ['3'], [point['amount'] for point in view['series'][0]['points']])


class TimelineDOMTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is optional VM tooling')
    def test_stale_bucket_frames_and_compatible_selection(self):
        result = subprocess.run(['node', 'development/tests/integration/account_timeline_dom.cjs'],
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


class TimelineDemandTests(unittest.TestCase):
    def test_silent_failure_preserves_last_good_then_a_new_revision_replaces_it(self):
        source = SyntheticMonthSource(1, 1, month_start_ms=NOV_1)
        key, snapshot = next(iter(source.snapshots.items()))
        source.snapshots[key] = replace(snapshot, complete=True)
        service = SimpleNamespace(source=source, close_accounts=lambda: None, progress=lambda *_: None)
        lane = AccountTimeline(lambda _: service, SourceReads())
        self.addCleanup(lane.close)
        args = dict(source=source_scope(source), observation=observe_catalog(source), periods={'month'},
            accounts=projected(subscription('github-copilot')), zone='UTC',
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
            values, more, _, interrupted = history.step(source_scope(origin), observation, ('today',),
                quota_roster(projected(subscription('openai'))), 'UTC',
                FakePricingProvider().catalog, lambda: None, None, DAY_MS // 2)

            self.assertEqual({'today'}, values.keys())
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
        self.assertEqual({'month'}, dispatch.account_timeline_demand())
        now = 18
        dispatch.interest('one', 'accounts', True, account_period='month')
        self.assertEqual({'month'}, dispatch.account_timeline_demand())
        now = 25
        dispatch.interest('one', 'accounts', True, account_period='30-days')
        self.assertEqual({'month', '30-days'}, dispatch.account_timeline_demand())
        dispatch.interest('one', 'accounts', False, account_period='30-days')
        self.assertEqual({'month'}, dispatch.account_timeline_demand())
        dispatch.interest('two', 'watch', True)
        self.assertEqual(set(), dispatch.account_timeline_demand())
        dispatch.interest('two', 'accounts', True, account_period='month')
        now = 100
        self.assertEqual({'month'}, dispatch.account_timeline_demand())
        now = 116
        self.assertEqual(set(), dispatch.account_timeline_demand())

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

        values, more, _, _ = turn(('30-days', 'today'))
        self.assertTrue(more)
        self.assertEqual({'30-days', 'today'}, values.keys())
        for index in range(1, 20):
            values, more, _, _ = turn(('30-days', 'month'), NOV_5 + 1000 * index)
            if not more:
                break
        self.assertFalse(more)
        self.assertEqual(217, source.load_count)
        self.assertGreater(Decimal(values['30-days'].to_json()['series'][0]['peak']), 0)
        turn(('30-days',), NOV_5 + 25_000)
        self.assertEqual(217, source.load_count)
        removed, _ = source.snapshots.popitem()
        newest = next(iter(source.snapshots))
        source.snapshots[newest] = replace(source.snapshots[newest], source_revision='corrected')
        observation = observe_catalog(source, include_archived_revisions=True)
        _, _, invalidated, _ = turn(('month',), NOV_5 + 27_000)
        self.assertTrue(invalidated)
        self.assertNotIn(removed, history.roots)
        self.assertEqual('corrected', history.roots[newest].revision)
        self.assertEqual(218, source.load_count)

    def test_cold_progress_marks_disjoint_dates_and_clears_failed_reads_without_false_zero(self):
        source = SyntheticMonthSource(0, 0, month_start_ms=NOV_1)
        for index, day in enumerate((0, *(2 for _ in range(13)), *(4 for _ in range(11)))):
            snapshot = make_root_snapshot(index, 1, month_start_ms=NOV_1 + day * DAY_MS)
            source.snapshots[snapshot.root.session_id] = replace(snapshot, complete=True)
        load = source.load_session_snapshot

        def failing_oldest(key):
            if key == 'root-0000':
                raise SourceConcurrentChangeError('old tree unavailable')
            return load(key)

        source.load_session_snapshot = failing_oldest
        service = SimpleNamespace(source=source, close_accounts=lambda: None, progress=lambda *_: None)
        lane = AccountTimeline(lambda _: service, SourceReads())
        self.addCleanup(lane.close)
        args = dict(source=source_scope(source), observation=observe_catalog(source), periods={'month'},
            accounts=projected(subscription('github-copilot')), zone='UTC',
            catalog=FakePricingProvider().catalog, prices=lambda: None, migration_gap=None)

        def publish(now):
            lane.tick(**args, now_ms=now)
            lane.job.result(2)
            lane.tick(**args, now_ms=now + 1)
            return lane.lookup('month')

        first = publish(NOV_5)
        self.assertEqual(12, source.load_count)
        self.assertEqual([0, 2], first['view']['pending_buckets'])
        self.assertEqual([0, 2], first['view']['initial_pending_buckets'])
        points = first['view']['series'][0]['points']
        self.assertIsNone(points[0])
        self.assertEqual('0', points[1]['amount'])
        self.assertEqual('~<$0.01', points[2]['display']['usd'])
        self.assertEqual(first, publish(NOV_5 + FOREGROUND_SLICE_MS), 'intermediate repricing is coalesced')
        final = publish(NOV_5 + 2 * FOREGROUND_SLICE_MS)
        self.assertEqual(24, source.load_count)
        self.assertGreater(final['revision'], first['revision'])
        self.assertEqual(first['scope'], final['scope'])
        self.assertEqual([], final['view']['pending_buckets'])
        self.assertIsNone(final['view']['series'][0]['points'][0])
        self.assertGreater(Decimal(final['view']['series'][0]['points'][2]['amount']), Decimal(points[2]['amount']))

    def test_visible_cold_slices_keep_priority_past_fifteen_seconds_and_withdraw(self):
        source = SyntheticMonthSource(49, 1, month_start_ms=NOV_1)
        source.snapshots = {key: replace(snapshot, complete=True) for key, snapshot in source.snapshots.items()}
        lane = AccountTimeline(lambda _: SimpleNamespace(source=source, close_accounts=lambda: None,
            progress=lambda *_: None), SourceReads())
        self.addCleanup(lane.close)
        args = dict(source=source_scope(source), observation=observe_catalog(source),
            accounts=projected(subscription('github-copilot')), zone='UTC', catalog=FakePricingProvider().catalog,
            prices=lambda: None, migration_gap=None)
        dispatch = DataDispatcher(None, clock=lambda: elapsed)
        elapsed = 1
        dispatch.interest('tab', 'accounts', True, account_period='month')

        def tick(now):
            lane.tick(**args, periods=dispatch.account_timeline_demand(), now_ms=now)

        tick(NOV_5)
        lane.job.result(2)
        self.assertEqual(12, source.load_count)
        tick(NOV_5 + 1)
        # Even after 15 seconds the same visible request gets sub-second turns.
        elapsed = 17
        tick(NOV_5 + 16_000)
        lane.job.result(2)
        tick(NOV_5 + 16_001)
        tick(NOV_5 + 16_000 + FOREGROUND_SLICE_MS)
        lane.job.result(2)
        self.assertEqual(36, source.load_count)
        dispatch.interest('tab', 'watch', True)
        tick(NOV_5 + 17_000)
        self.assertFalse(lane.fast)
        self.assertFalse(lane.lookup('month')['acquiring'])
        self.assertIsNone(lane.job)
        self.assertEqual(36, source.load_count)
        dispatch.interest('tab', 'accounts', True, account_period='month')
        tick(NOV_5 + 18_000)
        lane.job.result(2)
        tick(NOV_5 + 18_000 + FOREGROUND_SLICE_MS)
        lane.job.result(2)
        tick(NOV_5 + 18_001 + FOREGROUND_SLICE_MS)
        self.assertEqual(49, source.load_count)
        self.assertFalse(lane.fast)
        self.assertFalse(lane.lookup('month')['acquiring'])

    def test_live_revision_is_quiet_pending_and_historical_roots_are_not_reacquired(self):
        source = SyntheticMonthSource(25, 2, month_start_ms=NOV_1, today_roots=1, now_ms=NOV_5)
        source.snapshots = {key: replace(snapshot, complete=True) for key, snapshot in source.snapshots.items()}
        live = next(reversed(source.snapshots))
        original = source.snapshots[live]
        active_root = replace(original.root, active=True)
        source.snapshots[live] = replace(original, root=active_root, sessions=(active_root,))
        history = TimelineHistory(lambda _: SimpleNamespace(source=source, close_accounts=lambda: None,
            progress=lambda *_: None), SourceReads())

        def turn(now):
            return history.step(source_scope(source), observe_catalog(source), ('month',),
                quota_roster(projected(subscription('github-copilot'))), 'UTC', FakePricingProvider().catalog,
                lambda: None, None, now, foreground=True)

        first, _, _, _ = turn(NOV_5)
        self.assertGreater(Decimal(first['month'].to_json()['series'][0]['points'][4]['amount']), 0)
        invocation = original.invocations[1]
        source.snapshots[live] = replace(source.snapshots[live], complete=False, source_revision='in-flight',
            invocations=(original.invocations[0], replace(invocation, completed_at_ms=None)))
        turn(NOV_5 + FOREGROUND_SLICE_MS)
        self.assertEqual(24, source.load_count)
        self.assertNotIn(live, history.roots, 'need not chase a revised live root before untouched older roots')
        values, more, _, _ = turn(NOV_5 + 2 * FOREGROUND_SLICE_MS)
        partial = values['month'].to_json()
        self.assertFalse(more)
        self.assertEqual(26, source.load_count)
        self.assertEqual([4], partial['pending_buckets'])
        self.assertEqual([], partial['initial_pending_buckets'])

    def test_stalled_slice_expires_only_the_activity_hint(self):
        source = SyntheticMonthSource(25, 1, month_start_ms=NOV_1)
        source.snapshots = {key: replace(snapshot, complete=True) for key, snapshot in source.snapshots.items()}
        lane = AccountTimeline(lambda _: SimpleNamespace(source=source, close_accounts=lambda: None,
            progress=lambda *_: None), SourceReads())
        self.addCleanup(lane.close)
        args = dict(source=source_scope(source), observation=observe_catalog(source), periods={'month'},
            accounts=projected(subscription('github-copilot')), zone='UTC', catalog=FakePricingProvider().catalog,
            prices=lambda: None, migration_gap=None)
        with patch('src.watch.account_timeline.monotonic', return_value=100) as clock:
            lane.tick(**args, now_ms=NOV_5)
            lane.job.result(2)
            lane.tick(**args, now_ms=NOV_5 + FOREGROUND_SLICE_MS)
            partial = lane.lookup('month')
            self.assertTrue(partial['acquiring'])
            clock.return_value = 105
            stalled = lane.lookup('month', partial['revision'])
            self.assertTrue(stalled['unchanged'])
            self.assertFalse(stalled['acquiring'])
