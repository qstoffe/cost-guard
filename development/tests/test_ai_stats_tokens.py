"""Token traffic and response podium. Standing policy: architecture/modules/reports.md
section 'AI Stats = best effort / never Unavailable'; every ready card is covered.
"""
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
from hashlib import sha256
import json
import unittest

from development.tests.fixtures.active_hour import epoch
from src.analysis.ai_stats import DAY_MS, StatsRoot, period_stats, windows
from src.analysis.active_hour import HOUR_MS
from src.analysis.models import TraceEntry
from src.application.projection import project
from src.domain import ModelRef, TokenUsage
from src.reports.models import ReportKind, ReportProjection
from src.analysis.ai_stats_responses import ResponseCall, sample, call_key
from src.reports.ai_stats_responses import encode_responses, decode_responses, response_duration
from src.sources.opencode_v2_normalization import normalize_message_bundle, normalize_invocations


def entry(sid, stamp, tokens, *, message='m', step=None):
    return TraceEntry(sid, 'prompt', message, step, stamp, 0,
                      ModelRef('synthetic', 'unpriced'), None, tokens)


def calculate(roots, now, period='all', *, complete=True, calendar='SE', zone='Europe/Stockholm'):
    row = period_stats(roots, lambda *_: None, period=period, start=dict(windows(zone, now))[period],
        now=now, zone=zone, workday_calendar=calendar, source_complete=complete)
    dto = project(ReportProjection(ReportKind.AI_STATS, 'AI Stats', 'SYNTHETIC', ai_stats=(row,))).to_json()
    return {m.metric: m for m in row.metrics}, {m['metric']: m for m in dto['ai_stats'][0]['metrics']}


class TokenTrafficTests(unittest.TestCase):
    def test_all_five_periods_count_physical_categories_and_reasoning_once_without_prices(self):
        now = epoch('2026-11-12T12:00:00+00:00')
        ages = (HOUR_MS, 2 * DAY_MS, 10 * DAY_MS, 20 * DAY_MS, 40 * DAY_MS)
        roots = tuple(StatsRoot(str(i), 'Root',
            (entry(str(i), now - age, TokenUsage(input=11, cache_read=1000, cache_write=17, output=23, reasoning=29)),),
            ((now - age - HOUR_MS, HOUR_MS, False),)) for i, age in enumerate(ages))

        for period, requests in (('today', 1), ('7-days', 2), ('30-days', 4), ('month', 3), ('all', 5)):
            with self.subTest(period=period):
                metrics, dto = calculate(roots, now, period)

                self.assertEqual(requests * 1080, metrics['total-tokens'].value)
                self.assertEqual('complete', metrics['total-tokens'].status)
                self.assertEqual(str(requests * 1080), dto['total-tokens']['exact_value'])
                self.assertNotIn('display_units', dto['total-tokens'])
                self.assertNotIn('display_units', dto['token-rate'])

    def test_step_precedence_child_usage_and_clone_dedup_use_the_same_integer_numerator(self):
        now = epoch('2026-11-12T12:00:00+00:00')
        at = now - HOUR_MS
        fallback = entry('root', at, TokenUsage(input=999))
        step = replace(fallback, step_part_id='step', tokens=TokenUsage(input=2, cache_read=3, output=5, reasoning=7))
        clone = replace(step, session_id='clone')
        child = entry('child', at + 1, TokenUsage(cache_read=3, cache_write=11), message='child-message')
        roots = (StatsRoot('root', 'Root', (fallback, step, step, child), ((at, HOUR_MS, False),)),
                 StatsRoot('clone', 'Clone', (clone,), ((at, HOUR_MS, False),)))

        metrics, _ = calculate(roots, now)

        self.assertEqual(31, metrics['total-tokens'].value)
        self.assertIsNone(metrics['token-rate'].rates)

    def test_missing_categories_pending_gaps_and_unknown_completion_are_not_evidenced_zero(self):
        now = epoch('2026-11-12T12:00:00+00:00')
        at = now - HOUR_MS
        root = StatsRoot('root', 'Root', (entry('root', at, TokenUsage(input=4)),), ((at, HOUR_MS, False),))
        missing = replace(root, entries=(entry('root', at,
            TokenUsage(input=4, output=999, reasoning=999, known_fields=('input',))),))
        cases = ((missing, True, 4, 'missing-token-usage'), (replace(root, cost_pending=True), True, 4, 'pending-usage'),
            (root, False, 4, 'source-incomplete'),
            (replace(root, entries=(replace(root.entries[0], completed_at_ms=0),)), True, 0, 'unknown-request-time'))

        for evidence, complete, expected, reason in cases:
            metrics, dto = calculate((evidence,), now, complete=complete)

            self.assertEqual(expected, metrics['total-tokens'].value)
            self.assertIn(reason, metrics['total-tokens'].reasons)
            self.assertEqual(str(expected), dto['total-tokens']['display']['value'])
            for card in dto.values():
                self.assertNotRegex(str(card['display']), r'Unavailable|N/A')

    def test_workflow_time_cannot_become_a_response_denominator(self):
        now = epoch('2026-11-12T12:00:00+00:00')
        at = now - HOUR_MS
        root = StatsRoot('root', 'Root', (entry('root', at, TokenUsage(input=24)),), ())

        for intervals in ((), ((at, None, False),), ((at, HOUR_MS, True),), ((at, 0, False),)):
            metrics, dto = calculate((replace(root, intervals=intervals),), now, 'today')

            self.assertEqual(24, metrics['total-tokens'].value)
            self.assertEqual((), metrics['token-rate'].podium)
            self.assertIn('stopwatch', dto['token-rate']['display']['value'])
            self.assertNotIn('rates', dto['token-rate'])

    def test_podium_does_not_repurpose_calendar_denominators_even_across_dst(self):
        for stamp in ('2026-03-29T20:00:00+00:00', '2026-10-25T20:00:00+00:00',
                      '2026-12-27T20:00:00+00:00', '2027-01-01T00:30:00+00:00'):
            now = epoch(stamp)
            root = StatsRoot('root', 'Root', (entry('root', now - HOUR_MS, TokenUsage(input=840)),),
                             ((now - HOUR_MS, HOUR_MS, False),))
            for calendar in ('SE', ''):
                for period in ('today', '7-days', '30-days', 'month', 'all'):
                    metrics, _ = calculate((root,), now, period, calendar=calendar)
                    self.assertEqual(Decimal('.002520'), metrics['hourly-rate'].rates.active_rate)
                    self.assertIsNone(metrics['token-rate'].rates)

        metrics, dto = calculate((), epoch('2026-11-07T12:00:00+00:00'), 'today')
        self.assertEqual((0, 'complete'), (metrics['total-tokens'].value, metrics['total-tokens'].status))
        self.assertIn('No races yet', dto['token-rate']['display']['value'])
        self.assertEqual([], dto['token-rate']['podium'])

    def test_large_integer_survives_projection_and_precise_help_without_money_cap(self):
        now = epoch('2026-11-12T12:00:00+00:00')
        amount = 2**60 + 123
        root = StatsRoot('root', 'Root', (entry('root', now - HOUR_MS, TokenUsage(cache_read=amount)),),
                         ((now - HOUR_MS, HOUR_MS, False),))

        metrics, dto = calculate((root,), now)

        self.assertEqual(amount, metrics['total-tokens'].value)
        self.assertEqual(str(amount), dto['total-tokens']['exact_value'])
        self.assertIn(str(amount), dto['total-tokens']['display']['token_help'])
        self.assertEqual((), metrics['token-rate'].podium)


class ResponsePodiumTests(unittest.TestCase):
    NOW = epoch('2026-11-12T12:00:00+00:00')

    def call(self, name, output, duration, *, age=1000, model='a', variant=None, sid='root'):
        e = replace(entry(sid, self.NOW - age, TokenUsage(input=99999, cache_read=99999,
            output=output, reasoning=20), message=name), model=ModelRef('route', model), variant=variant)
        return ResponseCall(e, duration)

    def root(self, calls):
        return StatsRoot('root', 'Root', tuple(c.entry for c in calls),
                         ((self.NOW - HOUR_MS, HOUR_MS, False),), responses=tuple(calls))

    def test_weighted_output_oracle_parallel_models_efforts_ties_and_invalid_calls(self):
        calls = (self.call('a1', 80, 1000), self.call('a2', 880, 9000),
                 self.call('b', 180, 1000, model='b'), self.call('effort', 180, 1000, variant='high'),
                 self.call('zero', 1000000, 0), self.call('negative', 1000000, -1),
                 self.call('future', 1000000, 1, age=-1000),
                 replace(self.call('failed', 1000000, 1), entry=replace(self.call('failed', 1000000, 1).entry, error_name='Error')))
        metrics, dto = calculate((self.root(calls),), self.NOW, complete=False)
        podium = metrics['token-rate'].podium

        self.assertEqual([('a', 'high', Decimal(200), 1), ('b', '', Decimal(200), 1),
                          ('a', '', Decimal(100), 2)],
                         [(r.model, r.variant, r.tokens_per_second, r.sampled_calls) for r in podium])
        self.assertEqual((1000, 10000), (podium[2].output_tokens, podium[2].duration_ms))
        self.assertEqual('1 sampled call', dto['token-rate']['podium'][0]['sample'])
        self.assertNotIn('calendar_rate', dto['token-rate']['display'])
        for card in dto.values():
            self.assertNotRegex(str(card['display']), r'Unavailable|N/A')

    def test_one_two_32_and_many_samples_are_bounded_stable_and_per_model(self):
        for count in (1, 2, 32, 100):
            calls = tuple(self.call(str(i), 80, 1000, age=1000 + i) for i in range(count))
            other = self.call('other', 30, 1000, model='b')
            first = sample((*calls, other))
            second = sample((other, *reversed(calls)))
            self.assertEqual({call_key(c.entry) for c in first}, {call_key(c.entry) for c in second})
            metrics, _ = calculate((self.root((*calls, other)),), self.NOW)
            self.assertEqual([min(count, 32), 1], [r.sampled_calls for r in metrics['token-rate'].podium])
            self.assertEqual(Decimal(100), metrics['token-rate'].podium[0].tokens_per_second)
            if count == 100:
                # Independent full-sort oracle; production retains only 32 items.
                spread = sorted(range(8, 100), key=lambda i: sha256(json.dumps(
                    ('', 'root', str(i), '', 'prompt', 0), separators=(',', ':')).encode()).digest())[:24]
                self.assertEqual({str(i) for i in (*range(8), *spread)},
                                 {c.entry.message_id for c in first if c.entry.model.model == 'a'})

    def test_very_slow_positive_response_never_rounds_to_a_false_zero(self):
        call = self.call('slow', 1, HOUR_MS)
        _, dto = calculate((self.root((call,)),), self.NOW)
        self.assertEqual('<0.1 tok/s', dto['token-rate']['podium'][0]['speed'])

    def test_completion_periods_clone_and_step_precedence_do_not_leak(self):
        old, recent = self.call('old', 80, 1000, age=40 * DAY_MS), self.call('recent', 180, 1000)
        stepped = replace(recent, entry=replace(recent.entry, step_part_id='step'))
        clone = replace(stepped, entry=replace(stepped.entry, session_id='clone'))
        root = self.root((old, recent, stepped, stepped, clone))
        for period in ('today', '7-days', '30-days', 'month', 'all'):
            metrics, _ = calculate((root,), self.NOW, period)
            expected = 2 if period == 'all' else 1
            self.assertEqual(expected, metrics['token-rate'].podium[0].sampled_calls)

    def test_clone_with_missing_timing_cannot_erase_usable_physical_response(self):
        original = self.call('response', 80, 1000, sid='z-root')
        clone = replace(original.entry, session_id='a-clone', message_id='cloned-message')
        roots = (self.root((original,)), StatsRoot('a-clone', 'Clone', (clone,), ()))
        metrics, _ = calculate(roots, self.NOW)
        self.assertEqual((Decimal(100), 1), (metrics['token-rate'].podium[0].tokens_per_second,
                                           metrics['token-rate'].podium[0].sampled_calls))

    def test_root_summary_time_bounds_revision_rebuild_and_future_eviction(self):
        recent = self.call('recent', 80, 1000)
        old = tuple(self.call('old' + str(i), 80, 1000, age=40 * DAY_MS + i) for i in range(80))
        future = tuple(self.call('future' + str(i), 80, 1000, age=-1000 - i) for i in range(40))
        calls = (*old, recent, *future)
        bundle = SimpleNamespace(trace_entries=tuple(c.entry for c in calls))
        invocations = tuple(SimpleNamespace(session_id=c.entry.session_id, message_id=c.entry.message_id,
            step_part_id=None, created_at_ms=c.entry.completed_at_ms - c.duration_ms,
            completed_at_ms=c.entry.completed_at_ms) for c in calls)
        snapshot = SimpleNamespace(messages=(), invocations=invocations)

        value = encode_responses(bundle, snapshot, self.NOW)
        facts = [(e, None, None) for e in bundle.trace_entries]
        restored = decode_responses(value, facts, self.NOW + 500)

        self.assertEqual(32, len(restored))
        self.assertIn('recent', [c.entry.message_id for c in restored])
        self.assertTrue(all(c.entry.completed_at_ms <= self.NOW for c in restored))
        with self.assertRaisesRegex(ValueError, 'time_changed'):
            decode_responses(value, facts, self.NOW + 1000)
        with self.assertRaisesRegex(ValueError, 'time_changed'):
            decode_responses(value, facts, self.NOW - 1)
        revised = encode_responses(bundle, snapshot, self.NOW + 2000)
        self.assertTrue(any(c.entry.message_id.startswith('future') for c in decode_responses(revised, facts)))

    def test_request_proxy_excludes_tool_execution_and_inherited_multistep_intervals(self):
        raw = dict(info=dict(id='m', sessionID='s', role='assistant', providerID='route', modelID='a',
            time=dict(created=1000, completed=101000), tokens=dict(output=100)), parts=[
                dict(id='tool', type='tool', state=dict(time=dict(start=3000, end=101000)))])
        message, _ = normalize_message_bundle(raw, lambda *_: None)
        request = normalize_invocations(message, lambda *_: None)[0]
        self.assertEqual(2000, response_duration(request, message))
        raw['parts'] = [dict(id='one', type='step-finish', tokens=dict(output=100)),
                        dict(id='two', type='step-finish', tokens=dict(output=200))]
        message, _ = normalize_message_bundle(raw, lambda *_: None)
        requests = normalize_invocations(message, lambda *_: None)
        self.assertEqual([None, None], [response_duration(r, message) for r in requests])
        raw['parts'][0]['time'] = dict(start=1000, end=3000)
        raw['parts'][1]['time'] = dict(start=100000, end=101000)
        message, _ = normalize_message_bundle(raw, lambda *_: None)
        self.assertEqual([2000, 1000], [response_duration(r, message)
                                      for r in normalize_invocations(message, lambda *_: None)])
        raw['parts'][0]['time'] = dict(created=1000, completed=3000)
        raw['parts'][1]['time'] = dict(created=100000, completed=101000)
        # Wire adapter preserves original current-key timestamps in observed_time.
        for part in raw['parts']:
            part['observed_time'] = part.pop('time')
        message, _ = normalize_message_bundle(raw, lambda *_: None)
        self.assertEqual([2000, 1000], [response_duration(r, message)
                                      for r in normalize_invocations(message, lambda *_: None)])

    def test_stream_end_keeps_tool_overlap_but_excludes_post_stream_wait(self):
        raw = dict(info=dict(id='m', sessionID='s', role='assistant', providerID='route', modelID='a',
            time=dict(created=1000, streamed=7000, completed=101000), tokens=dict(output=120)), parts=[
                dict(id='tool', type='tool', state=dict(time=dict(start=3000, end=5000)))])
        message, _ = normalize_message_bundle(raw, lambda *_: None)
        request = normalize_invocations(message, lambda *_: None)[0]

        self.assertEqual(6000, response_duration(request, message))
        self.assertEqual(101000, request.completed_at_ms)
        for marker in (None, 0, 1000, 101001, True):
            with self.subTest(streamed=marker):
                fallback = replace(message, metadata={**message.metadata, 'streamed_at_ms': marker})
                self.assertEqual(2000, response_duration(request, fallback))
        no_tool = replace(message, parts=())
        self.assertEqual(100000, response_duration(request, replace(no_tool, metadata={})))

        raw['parts'].append(dict(id='step', type='step-finish', tokens=dict(output=120),
                                 time=dict(start=2000, end=4000)))
        message, _ = normalize_message_bundle(raw, lambda *_: None)
        independent = normalize_invocations(message, lambda *_: None)[0]
        self.assertEqual(2000, response_duration(independent, message))


if __name__ == '__main__':
    unittest.main()
