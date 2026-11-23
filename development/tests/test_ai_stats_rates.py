"""Independent request-cost/union-time oracles for the standard hourly-rate card."""
from dataclasses import replace
from decimal import Decimal
import unittest

from development.tests.fixtures.active_hour import epoch
from development.tests.test_ai_stats_tokens import entry
from src.analysis.active_hour import HOUR_MS
from src.analysis.ai_stats import StatsRoot, period_stats, windows
from src.analysis.ai_stats_models import ModelActivity
from src.application.projection import project
from src.domain import ModelRef, TokenUsage
from src.reports.models import ReportKind, ReportProjection

NOW = epoch('2026-11-16T12:00:00+00:00')


def request(name, start, duration, cost, effort=None, provider='route', sid='root'):
    fact = replace(entry(sid, start + duration, TokenUsage(input=cost), message=name),
                   model=ModelRef(provider, name.split(':')[0]), variant=effort)
    return fact, ModelActivity(fact, start, duration)


def root(calls, **kwargs):
    return StatsRoot('root', 'Synthetic', tuple(e for e, _ in calls),
                     ((NOW - HOUR_MS, HOUR_MS, False),),
                     activity=tuple(a for _, a in calls if a is not None), **kwargs)


def calculate(roots, now=NOW, period='all', zone='UTC', valuation=None):
    row = period_stats(roots, valuation or (lambda _m, t: Decimal(t.input)),
        period=period, start=dict(windows(zone, now))[period], now=now, zone=zone)
    card = row.metrics[0]
    dto = project(ReportProjection(ReportKind.AI_STATS, 'Stats', 'SYNTHETIC', ai_stats=(row,))).to_json()
    return card, dto['ai_stats'][0]['metrics'][0]


class AIStatsRateTests(unittest.TestCase):
    def test_threshold_matrix_in_every_period_and_final_medals_are_rate_ordered(self):
        for primary in range(5):
            for short in range(5):
                calls = [request('p' + str(i), NOW - 120000, 60000, i + 1) for i in range(primary)]
                calls += [request('s' + str(i), NOW - 10000, 10000, i + 10) for i in range(short)]
                # Every short is faster than every primary; fillers can win gold.
                primaries = ['p' + str(i) for i in reversed(range(primary))]
                shorts = ['s' + str(i) for i in reversed(range(short))]
                expected = primaries[:3] if primary >= 3 else shorts[:3 - primary] + primaries
                for period in ('today', '7-days', '30-days', 'month', 'all'):
                    with self.subTest(primary=primary, short=short, period=period):
                        card, dto = calculate((root(calls),), period=period)
                        self.assertEqual(expected, [r.model for r in card.podium])
                        self.assertEqual(expected, [r['label'] for r in dto['podium']])

    def test_exact_minute_boundaries_and_zero_cost_are_eligible(self):
        calls = [request(name, NOW - 120000, duration, cost)
                 for name, duration, cost in (('short', 59999, 1000), ('exact', 60000, 1),
                                             ('over', 60001, 1), ('free', 60000, 0))]

        card, dto = calculate((root(calls),))

        self.assertEqual(['exact', 'over', 'free'], [r.model for r in card.podium])
        self.assertEqual(Decimal(60), card.podium[0].value)
        self.assertEqual(Decimal(3600000) / 60001, card.podium[1].value)
        self.assertEqual(0, card.podium[2].value)
        self.assertEqual('0 CCost/h', dto['podium'][2]['display']['amount'])
        self.assertEqual('$0.00/h', dto['podium'][2]['display_units']['usd']['amount'])

    def test_many_short_intervals_union_qualifies_but_overlapping_calls_do_not(self):
        calls = [request('many:' + str(i), NOW - 100000 + i * 10000, 10000, 1) for i in range(6)]
        calls += [request('overlap:' + str(i), NOW - 100000, 40000, 100) for i in range(3)]
        calls += [request(name, NOW - 100000, 60000, 1) for name in ('other-a', 'other-b')]

        card, _dto = calculate((root(calls),))

        self.assertEqual(['many', 'other-a', 'other-b'], [r.model for r in card.podium])
        self.assertEqual(360, card.podium[0].value, 'six calls, one minute, six CCost')

    def test_global_headline_model_and_effort_unions_are_independent_with_shared_prices(self):
        calls = [request('a:high', NOW - 120000, 60000, 2, 'high'),
                 request('a:max', NOW - 90000, 60000, 3, 'max', 'second-route', 'child'),
                 request('a:default', NOW - 61000, 1000, 1, 'default'),
                 request('b', NOW - 120000, 60000, 1)]
        calls[1] = (replace(calls[1][0], parent_session_id='root', root_session_id='root'), calls[1][1])
        valuations = []
        def price(model, tokens):
            valuations.append((model.provider, tokens.input))
            return Decimal(tokens.input)
        roots = (root(calls),)

        card, dto = calculate(roots, valuation=price)

        self.assertEqual(4, len(valuations), 'one canonical valuation per request')
        self.assertEqual(280, card.value, 'seven CCost / 90 seconds of measured execution')
        self.assertEqual(280, card.rates.active_rate)
        self.assertEqual(['a', 'b'], [r.model for r in card.podium])
        self.assertEqual(240, card.podium[0].value, 'six CCost / 90 unioned seconds')
        self.assertEqual(60, card.podium[1].value)
        self.assertEqual((('Default', Decimal(3600)), ('Max', Decimal(180)), ('High', Decimal(120))),
                         card.podium[0].by_effort)
        self.assertEqual('route + second-route', card.podium[0].provider)
        medal = dto['podium'][0]
        self.assertEqual('route + second-route/a\n\nBy Effort:\n• Default — 3600 CCost/h'
                         '\n• Max — 180 CCost/h\n• High — 120 CCost/h', medal['model_help'])
        self.assertEqual('$2.40/h', medal['display_units']['usd']['amount'])
        self.assertIn('• Default — $36.00/h', medal['display_units']['usd']['model_help'])
        self.assertEqual('280 CCost/h', dto['display']['value'])
        self.assertIn('measured execution', dto['display']['rate_help'])
        self.assertIn('higher or lower', dto['display']['rate_help'])
        self.assertNotRegex(str(dto['display']), r'Calendar|Workday|Active AI average')

    def test_older_untimed_peer_never_erases_recent_model_in_larger_rolling_period(self):
        timed = request('partial:timed', NOW - 2000, 1000, 1)
        untimed, _activity = request('partial:untimed', NOW - 48 * HOUR_MS, 1000, 1000, 'max')
        good = request('good', NOW - 2000, 1000, 1)
        roots = (root((timed, (untimed, None), good), source_complete=False, cost_pending=True),)

        for period, total in [('today', 2), ('7-days', 1002), ('30-days', 1002)]:
            with self.subTest(period=period):
                row = period_stats(roots, lambda _m, t: Decimal(t.input), period=period,
                                   start=dict(windows('UTC', NOW))[period], now=NOW, zone='UTC')
                card, cost = row.metrics[:2]
                self.assertEqual(['good', 'partial'], [r.model for r in card.podium])
                self.assertEqual(7200, card.value, 'two paired CCost / one measured second')
                self.assertEqual(total, cost.value)
                self.assertEqual(period != 'today', 'unpaired-request-timing' in card.reasons)
                self.assertIn('source-incomplete', card.reasons)

    def test_simultaneous_models_keep_global_union_headline_even_with_untimed_cost(self):
        first = request('a', NOW - 120000, 120000, 2)
        second = request('b', NOW - 60000, 60000, 3, sid='parallel')
        untimed, _ = request('untimed', NOW - 1000, 1000, 5)
        roots = (replace(root((first, (untimed, None))), intervals=((NOW - 120000, 120000, False),)),
                 StatsRoot('parallel', 'Parallel', (second[0],), ((NOW - 60000, 60000, False),),
                           activity=(second[1],)))

        card, _dto = calculate(roots)

        self.assertEqual(150, card.value, 'five paired CCost / two global unioned minutes')
        self.assertEqual(['b', 'a'], [r.model for r in card.podium])
        self.assertEqual([Decimal(180), Decimal(60)], [r.value for r in card.podium])
        self.assertEqual(150, card.rates.active_rate)

    def test_invalid_failed_cancelled_future_and_foreign_timing_cannot_supply_rates(self):
        good, activity = request('model', NOW - 2000, 1000, 1)
        variants = [(good, None), (good, replace(activity, duration_ms=0)),
                    (good, replace(activity, duration_ms=-1)),
                    (good, replace(activity, start_ms=0)),
                    (good, replace(activity, duration_ms=2001)),
                    (replace(good, error_name='failed'), activity),
                    (replace(good, finish_reason='aborted'), activity),
                    (replace(good, completed_at_ms=0), activity),
                    (replace(good, completed_at_ms=NOW + 1), activity),
                    (replace(good, source_instance='foreign'), activity)]
        for fact, timing in variants:
            with self.subTest(fact=fact, timing=timing):
                card, _dto = calculate((root(((fact, timing),)),))
                self.assertEqual((), card.podium)

    def test_clone_survivor_borrows_only_same_source_physical_interval(self):
        fact, activity = request('model', NOW - 10000, 10000, 2)
        clone = replace(fact, session_id='z-clone')
        roots = (root(((fact, None),)), StatsRoot('z-clone', 'Clone', (clone,), (),
                 activity=(replace(activity, entry=clone),)))

        card, _dto = calculate(roots)
        foreign, _dto = calculate((roots[0], replace(roots[1], activity=(
            replace(activity, entry=replace(clone, source_instance='foreign')),))))

        self.assertEqual(720, card.value)
        self.assertEqual(720, card.podium[0].value)
        self.assertEqual((), foreign.podium)

    def test_completion_owns_cost_and_clipped_execution_owns_time_at_local_and_dst_boundaries(self):
        for stamp in ('2026-03-29T20:00:00+00:00', '2026-10-25T20:00:00+00:00',
                      '2027-01-01T00:30:00+00:00'):
            now = epoch(stamp)
            for period, cutoff in windows('Europe/Stockholm', now):
                if cutoff is None:
                    continue
                crossing = request('crossing', cutoff - 30000, 60000, 2)
                excluded = request('old', cutoff - 60001, 60000, 999)
                at_edge = request('edge', cutoff - 60000, 60000, 3)
                roots = (root((crossing, excluded, at_edge)),)
                with self.subTest(stamp=stamp, period=period):
                    card, _dto = calculate(roots, now, period, 'Europe/Stockholm')
                    self.assertEqual(2, card.rates.total, 'only crossing has positive measured time in this period')
                    self.assertEqual(['crossing'], [r.model for r in card.podium])
                    self.assertEqual(240, card.podium[0].value, 'full two CCost / clipped 30 seconds')

    def test_unrounded_sorting_effort_ties_and_raw_headline_have_no_internal_cap(self):
        calls = [request('z:high', NOW - 1000, 1000, 1, 'high'),
                 request('z:default', NOW - 1000, 1000, 1, 'default'),
                 request('a', NOW - 1000, 1000, 1)]
        prices = iter((Decimal('.01000000000001'), Decimal(0), Decimal('.01000000000000')))

        card, _dto = calculate((root(calls),), valuation=lambda *_: next(prices))

        self.assertEqual(['z', 'a'], [r.model for r in card.podium])
        self.assertEqual((('High', Decimal('36.000000000036')), ('Default', Decimal(0))),
                         card.podium[0].by_effort)
        tied, _dto = calculate((root(calls),), valuation=lambda *_: Decimal(0))
        self.assertEqual(['a', 'z'], [r.model for r in tied.podium])
        self.assertEqual((('Default', Decimal(0)), ('High', Decimal(0))), tied.podium[1].by_effort)
        tiny = replace(root((request('expensive', NOW - 1, 1, 1000000),)),
                       intervals=((NOW - 1, 1, False),))
        huge, dto = calculate((tiny,))
        self.assertEqual(Decimal('3600000000000'), huge.value)
        self.assertEqual(huge.value, huge.rates.active_rate)
        self.assertEqual('3600000000000 CCost/h', dto['display']['value'])
        self.assertEqual('$36000000000.00/h', dto['display_units']['usd']['value'])

    def test_estimated_cost_is_not_a_measured_rate_even_with_timing(self):
        fact, activity = request('unknown', NOW - 10000, 10000, 100)
        fact = replace(fact, tokens=TokenUsage(input=100, known_fields=('input',)))
        observed = root(((fact, replace(activity, entry=fact)),))

        card, _dto = calculate((observed,), valuation=lambda *_: None)

        self.assertIsNone(card.value)
        self.assertEqual((), card.podium)
        self.assertIn('unpriced-requests', card.reasons)

    def test_empty_and_no_duration_preserve_safe_headline_and_no_podium(self):
        untimed = root((request('untimed', NOW - 1000, 1000, 24),))
        for roots, expected, display in [((), 0, '0 CCost/h'),
                ((replace(untimed, activity=()),), None, 'N/A')]:
            card, dto = calculate(roots)
            self.assertEqual(expected, card.value)
            self.assertEqual((), card.podium)
            self.assertEqual(display, dto['display']['value'])
            self.assertNotRegex(str(dto['display']), r'Calendar|Workday|Unavailable')

    def test_legacy_calendar_shift_scalars_remain_compatible_but_not_presented(self):
        at = epoch('2026-11-02T06:00:00+00:00')
        observed = root((request('model', at, 28 * HOUR_MS, 840),))

        card, dto = calculate((observed,), epoch('2026-11-08T20:00:00+00:00'), '7-days',
                              'Europe/Stockholm')

        self.assertEqual((7, 5, 168, 40, 28), (card.rates.calendar_days, card.rates.workdays,
            card.rates.calendar_hours, card.rates.workday_hours, card.rates.active_hours))
        self.assertEqual((Decimal(5), Decimal(21), Decimal(30)),
                         (card.rates.calendar_rate, card.rates.workday_rate, card.rates.active_rate))
        self.assertEqual({'value', 'trait', 'rate_help'}, set(dto['display']))


if __name__ == '__main__':
    unittest.main()
