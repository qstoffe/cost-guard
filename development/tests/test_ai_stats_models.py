"""Independent model-ranking oracles; overall fun metrics remain unchanged."""
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
import unittest

from development.tests.test_ai_stats_tokens import entry, calculate
from development.tests.fixtures.active_hour import epoch
from src.analysis.ai_stats import StatsRoot, StatsObservation, period_stats, DAY_MS
from src.analysis.ai_stats_models import ModelActivity
from src.analysis.ai_stats_responses import ResponseCall, sample, model_key
from src.application.projection import project
from src.domain import ModelRef, TokenUsage
from src.domain.model_identity import ModelResolution
from src.pricing.catalog import PricingCatalog
from src.reports.ai_stats_responses import encode_responses, decode_activity
from src.reports.models import ReportKind, ReportProjection


class ModelStandingsTests(unittest.TestCase):
    NOW = epoch('2026-11-12T12:00:00+00:00')

    def request(self, sid, message, model, tokens, *, age=1000, variant=None, provider='route'):
        return replace(entry(sid, self.NOW - age, tokens, message=message),
                       model=ModelRef(provider, model), variant=variant)

    def test_mixed_root_child_clone_tokens_cost_averages_and_nonadditive_model_time(self):
        a = self.request('root', 'a', 'a', TokenUsage(input=10, cache_read=20, cache_write=30, output=40, reasoning=5))
        b = self.request('root', 'b', 'b', TokenUsage(output=50))
        child = self.request('child', 'child', 'a', TokenUsage(input=15), variant='high', age=500)
        second = self.request('second', 'second', 'a', TokenUsage(output=25), variant='low', age=300)
        clone = replace(a, session_id='z-clone')
        roots = (
            StatsRoot('root', 'Root', (a, b, child), ((self.NOW - 10000, 10000, False),),
                activity=(ModelActivity(a, self.NOW - 5000, 4000), ModelActivity(b, self.NOW - 4000, 3000),
                          ModelActivity(child, self.NOW - 3000, 2500))),
            StatsRoot('second', 'Second', (second,), ((self.NOW - 10000, 10000, False),),
                activity=(ModelActivity(second, self.NOW - 2000, 1700),)),
            StatsRoot('z-clone', 'Clone', (clone,), ((self.NOW - 10000, 10000, False),)))

        row = period_stats(roots, lambda _model, tokens: Decimal(tokens.total) / 100, period='all',
                           start=None, now=self.NOW, zone='UTC')
        metrics = {m.metric: m for m in row.metrics}
        amounts = lambda metric: [(r.model, r.value) for r in metrics[metric].podium]

        self.assertEqual(195, metrics['total-tokens'].value)
        self.assertEqual([('a', 145), ('b', 50)], amounts('total-tokens'))
        self.assertEqual(Decimal('1.95'), metrics['total-cost'].value)
        self.assertEqual([('a', Decimal('1.45')), ('b', Decimal('.50'))], amounts('total-cost'))
        self.assertEqual([('a', Decimal('.725')), ('b', Decimal('.50'))], amounts('average-cost'))
        self.assertEqual(10000, metrics['working-time'].value)
        self.assertEqual([('a', 4700), ('b', 3000)], amounts('working-time'))
        self.assertEqual((), metrics['token-rate'].podium, 'model time is independent of TPS sampling')

    def test_unknown_categories_pending_session_fallback_and_estimated_cost_are_not_model_guesses(self):
        partial = self.request('root', 'partial', 'unpriced', TokenUsage(
            input=4, output=999, reasoning=999, known_fields=('input',)))
        roots = (StatsRoot('root', 'Root', (partial,), ()),
                 StatsRoot('pending', 'Pending', (), ((self.NOW - 2000, 1000, False),), cost_pending=True))

        metrics, dto = calculate(roots, self.NOW)

        self.assertEqual(4, metrics['total-tokens'].value)
        self.assertEqual(4, metrics['total-tokens'].podium[0].value)
        attributed = metrics['total-cost'].podium[0].value
        self.assertEqual(attributed + Decimal('.003'), metrics['total-cost'].value)
        self.assertEqual(attributed, metrics['average-cost'].podium[0].value)
        self.assertEqual((), metrics['working-time'].podium)
        self.assertIn('4 observed tokens', dto['total-tokens']['podium'][0]['model_help'])
        cost = dto['total-cost']['podium'][0]
        self.assertIn('CCost', cost['display']['amount'])
        self.assertTrue(cost['display_units']['usd']['amount'].startswith('$'))

    def test_combined_effort_pool_single_cap_versions_and_weighted_rate(self):
        calls = tuple(ResponseCall(self.request('root', str(i), 'release-1',
            TokenUsage(output=100 + i, reasoning=10), variant=('low', 'medium', 'high')[i % 3],
            age=1000 + i), 1000 + i * 100) for i in range(96))
        version = ResponseCall(self.request('root', 'version', 'release-2', TokenUsage(output=200)), 2000)
        bounded = sample((*calls, version))
        root = StatsRoot('root', 'Root', tuple(c.entry for c in (*calls, version)), (), responses=bounded)

        metrics, dto = calculate((root,), self.NOW)
        rows = metrics['token-rate'].podium
        first = next(r for r in rows if r.model == 'release-1')
        retained = [c for c in bounded if c.entry.model.model == 'release-1']

        self.assertEqual(32, len(retained))
        self.assertEqual(2, len(rows))
        self.assertEqual(Decimal(sum(c.entry.tokens.output + 10 for c in retained)) * 1000 /
                         sum(c.duration_ms for c in retained), first.tokens_per_second)
        self.assertEqual({'release-1', 'release-2'}, {r['label'] for r in dto['token-rate']['podium']})
        self.assertIn('32 sampled calls', next(r for r in dto['token-rate']['podium'] if r['model'] == 'release-1')['model_help'])

    def test_unsampled_activity_roundtrip_keeps_all_calls_and_clips_period_without_copying_prompt_time(self):
        requests = tuple(self.request('root', str(i), 'a', TokenUsage(output=10), age=1000 + i * 2000)
                         for i in range(40))
        invocations = tuple(SimpleNamespace(session_id=e.session_id, message_id=e.message_id, step_part_id=None,
            created_at_ms=e.completed_at_ms - 1000, completed_at_ms=e.completed_at_ms) for e in requests)
        encoded = encode_responses(SimpleNamespace(trace_entries=requests),
            SimpleNamespace(messages=(), invocations=invocations), self.NOW)
        activity = decode_activity(encoded, [(e, None, None) for e in requests])
        root = StatsRoot('root', 'Root', requests, ((self.NOW - DAY_MS, DAY_MS, False),), activity=activity)

        row = period_stats((root,), lambda *_: Decimal(1), period='today', start=self.NOW - 2500,
                           now=self.NOW, zone='UTC')
        metrics = {m.metric: m for m in row.metrics}

        self.assertEqual(32, len(encoded['calls']))
        self.assertEqual(40, len(activity))
        self.assertEqual(2500, metrics['working-time'].value)
        self.assertEqual(1000, metrics['working-time'].podium[0].value)
        self.assertEqual(10, metrics['total-tokens'].podium[0].value)
        all_time = period_stats((root,), lambda *_: Decimal(1), period='all', start=None, now=self.NOW, zone='UTC')
        self.assertEqual(40000, next(m for m in all_time.metrics if m.metric == 'working-time').podium[0].value)

    def test_unique_catalog_label_fallback_collision_and_model_identity_not_effort(self):
        from development.tests.fixtures.report_runtime import FakePricingProvider
        base = FakePricingProvider().get_catalog().models[0]
        catalog = PricingCatalog((replace(base, model=ModelRef('github-copilot', 'release-1', 'Exact Display')),))
        one = self.request('root', 'one', 'release-1', TokenUsage(output=10), variant='low')
        two = self.request('root', 'two', 'unlisted-2026', TokenUsage(output=20), provider='other')
        duplicate = replace(one, message_id='three', model=ModelRef('other', 'release-1'))
        root = StatsRoot('root', 'Root', (one, two, duplicate), ())

        row = StatsObservation((root,), lambda *_: Decimal(1), now=self.NOW, zone='UTC',
            model_name=lambda model, provider: catalog.display_name(model, provider, exact=True)).period(period='all', start=None)
        dto = project(ReportProjection(ReportKind.AI_STATS, 'Stats', 'SYNTHETIC', ai_stats=(row,))).to_json()
        rows = next(m for m in dto['ai_stats'][0]['metrics'] if m['metric'] == 'total-tokens')['podium']

        self.assertEqual({'unlisted-2026', 'Exact Display · route', 'Exact Display · other'}, {r['label'] for r in rows})
        self.assertNotEqual(model_key(one), model_key(duplicate))
        self.assertEqual(model_key(one), model_key(replace(one, variant='high')))

    def test_source_qualified_aliases_remain_distinct_even_with_the_same_catalog_estimate(self):
        first = self.request('root', 'one', 'alias', TokenUsage(output=10))
        first = replace(first, model=ModelRef('claude-agent', 'claude-sonnet-5-5',
            resolution=ModelResolution('sonnet', 'synthetic-location-one', 'catalog-one')))
        second = replace(first, message_id='two', model=replace(first.model,
            resolution=ModelResolution('sonnet', 'synthetic-location-two', 'catalog-two')))
        root = StatsRoot('root', 'Root', (first, second), (),
                         responses=(ResponseCall(first, 1000), ResponseCall(second, 1000)))

        metrics, dto = calculate((root,), self.NOW)

        self.assertEqual(2, len(metrics['total-tokens'].podium))
        self.assertEqual(2, len(metrics['token-rate'].podium))
        rows = dto['token-rate']['podium']
        self.assertEqual(2, len({r['label'] for r in rows}))
        self.assertTrue(all('Catalog modelID: claude-sonnet-5-5' in r['model_help'] for r in rows))
        self.assertNotIn('synthetic-location', str(rows), 'source scope must stay private')


if __name__ == '__main__':
    unittest.main()
