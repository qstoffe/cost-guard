"""Independent model-ranking oracles; overall fun metrics remain unchanged."""
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
import unittest

from development.tests.test_ai_stats_tokens import entry, calculate
from development.tests.fixtures.active_hour import epoch
from development.tests.fixtures.session_snapshots import DAY as DAY_MS
from src.analysis.ai_stats import StatsRoot, StatsObservation, period_stats
from src.analysis.ai_stats_models import ModelActivity
from src.analysis.ai_stats_responses import ResponseCall, sample, model_key
from src.analysis.ai_stats_buckets import friendly_model
from src.application.projection import project
from src.domain import ModelRef, TokenUsage
from src.domain.model_identity import ModelResolution
from src.pricing.catalog import PricingCatalog
from src.reports.ai_stats_responses import encode_responses, decode_activity, decode_responses
from src.reports.models import ReportKind, ReportProjection


class ModelStandingsTests(unittest.TestCase):
    NOW = epoch('2026-11-12T12:00:00+00:00')

    def test_subagent_cost_uses_own_model_effort_and_shared_unrounded_valuation_once(self):
        main = replace(self.request('root', 'main', 'gpt-6.1-sol', TokenUsage(output=10), variant='high'),
                       root_session_id='root', model=ModelRef('route', 'gpt-6.1-sol', 'GPT-6 Sol'))
        child = replace(self.request('child', 'child', 'gpt-6.1-sol', TokenUsage(output=90), variant='max'),
                        root_session_id='root', parent_session_id='root', model=main.model)
        root = StatsRoot('root', 'Root', (main, child), ())
        valuations = []
        def price(model, tokens):
            valuations.append((model, tokens))
            return Decimal(tokens.output)

        row = period_stats((root,), price, period='all', start=None, now=self.NOW, zone='UTC')
        metrics = {m.metric: m for m in row.metrics}
        dto = project(ReportProjection(ReportKind.AI_STATS, 'Stats', 'SYNTHETIC', ai_stats=(row,))).to_json()
        card = next(m for m in dto['ai_stats'][0]['metrics'] if m['metric'] == 'subagent-cost')

        self.assertEqual(2, len(valuations), 'one existing valuation per physical request, no second pipeline')
        self.assertEqual(Decimal(100), metrics['total-cost'].value)
        self.assertEqual(Decimal(90), metrics['subagent-cost'].value)
        self.assertEqual((('Max', Decimal(90)),), metrics['subagent-cost'].podium[0].by_effort)
        self.assertEqual('route/GPT-6 Sol\n\nBy Effort:\n• Max — 90 CCost', card['podium'][0]['model_help'])
        self.assertEqual('$0.90', card['display_units']['usd']['value'])
        self.assertEqual('route/GPT-6 Sol\n\nBy Effort:\n• Max — $0.90',
                         card['podium'][0]['display_units']['usd']['model_help'])

    def test_child_medals_include_fourth_place_in_total_and_merge_only_child_routes_and_efforts(self):
        main = self.request('root', 'main', 'claude-sonnet-5-5', TokenUsage(output=99), variant='high')
        calls = tuple(replace(self.request('child-' + str(i), str(i), model, TokenUsage(output=amount),
                            provider=provider, variant=effort),
                            root_session_id='root', parent_session_id='root' if i != 2 else 'child-0')
                      for i, (model, amount, provider, effort) in enumerate((
                          ('claude-sonnet-5-5', 10, 'claude-agent', 'default'),
                          ('claude-sonnet-5-5', 20, 'claude-code', 'high'),
                          ('claude-sonnet-5-5', 30, 'github-copilot', 'default'),
                          ('b', 40, 'route', 'low'), ('c', 40, 'route', 'max'), ('d', 5, 'route', None))))
        root = StatsRoot('root', 'Root', (main, *calls), ())

        row = period_stats((root,), lambda _m, t: Decimal(t.output) / 100, period='all',
                           start=None, now=self.NOW, zone='UTC')
        metrics = {m.metric: m for m in row.metrics}
        child = metrics['subagent-cost']

        self.assertEqual(Decimal('1.45'), child.value)
        self.assertEqual(Decimal('2.44'), metrics['total-cost'].value)
        self.assertEqual(['Claude Sonnet 5.5', 'b', 'c'], [r.model for r in child.podium])
        self.assertEqual('claude-agent + claude-code + github-copilot', child.podium[0].provider)
        self.assertEqual((('Default', Decimal('.4')), ('High', Decimal('.2'))), child.podium[0].by_effort)

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
        self.assertEqual('route/unpriced\n\nBy Effort:\n• Default — 4 tokens',
                         dto['total-tokens']['podium'][0]['model_help'])
        cost = dto['total-cost']['podium'][0]
        self.assertIn('CCost', cost['display']['amount'])
        self.assertEqual('<$0.01', cost['display_units']['usd']['amount'])

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
        self.assertIn('By Effort:\n• ', next(r for r in dto['token-rate']['podium'] if r['model'] == 'release-1')['model_help'])

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
        self.assertEqual(3600, metrics['hourly-rate'].podium[0].value)
        all_time = period_stats((root,), lambda *_: Decimal(1), period='all', start=None, now=self.NOW, zone='UTC')
        self.assertEqual(40000, next(m for m in all_time.metrics if m.metric == 'working-time').podium[0].value)
        self.assertEqual(3600, all_time.metrics[0].podium[0].value, 'all forty request costs / all forty seconds')

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

        self.assertEqual({'unlisted-2026', 'Exact Display'}, {r['label'] for r in rows})
        self.assertEqual(model_key(one), model_key(duplicate))
        self.assertEqual(model_key(one), model_key(replace(one, variant='high')))

    def test_source_qualified_aliases_share_the_same_friendly_catalog_bucket(self):
        first = self.request('root', 'one', 'alias', TokenUsage(output=10))
        first = replace(first, model=ModelRef('claude-agent', 'claude-sonnet-5-5',
            resolution=ModelResolution('sonnet', 'synthetic-location-one', 'catalog-one')))
        second = replace(first, message_id='two', model=replace(first.model,
            resolution=ModelResolution('sonnet', 'synthetic-location-two', 'catalog-two')))
        root = StatsRoot('root', 'Root', (first, second), (),
                         responses=(ResponseCall(first, 1000), ResponseCall(second, 1000)))

        metrics, dto = calculate((root,), self.NOW)

        self.assertEqual(1, len(metrics['total-tokens'].podium))
        self.assertEqual(1, len(metrics['token-rate'].podium))
        rows = dto['token-rate']['podium']
        self.assertEqual(['Claude Sonnet 5.5'], [r['label'] for r in rows])
        self.assertEqual('claude-agent/Claude Sonnet 5.5\n\nBy Effort:\n• Default — 10 tok/s',
                         rows[0]['model_help'])
        self.assertNotIn('synthetic-location', str(rows), 'source scope must stay private')

    def test_five_cards_share_alias_bucket_and_independent_effort_numeric_oracles_in_every_period(self):
        a = replace(self.request('root', 'a', 'alias', TokenUsage(
            input=10, cache_read=20, cache_write=30, output=100, reasoning=10), variant='medium'),
            selected_effort='default', model=ModelRef('claude-agent', 'claude-sonnet-5-5',
                resolution=ModelResolution('sonnet', 'one', 'signature-one')))
        b = replace(a, message_id='b', tokens=TokenUsage(output=300), variant='high',
                    model=replace(a.model, resolution=ModelResolution('claude-sonnet', 'two', 'signature-two')))
        c = replace(a, message_id='c', tokens=TokenUsage(input=20, output=200), selected_effort='high')
        d = replace(b, session_id='second', message_id='d', tokens=TokenUsage(output=400), selected_effort='high')
        e = replace(d, message_id='e', tokens=TokenUsage(output=50), selected_effort='low')
        clone = replace(a, session_id='z-clone')
        roots = (
            StatsRoot('root', 'Root', (a, b, c), (), responses=(
                ResponseCall(a, 1000), ResponseCall(b, 3000), ResponseCall(c, 2000)),
                activity=(ModelActivity(a, self.NOW - 8000, 4000), ModelActivity(b, self.NOW - 6000, 4000),
                          ModelActivity(c, self.NOW - 5000, 3000))),
            StatsRoot('second', 'Second', (d, e), (), responses=(ResponseCall(d, 8000), ResponseCall(e, 1000)),
                activity=(ModelActivity(d, self.NOW - 3000, 2000), ModelActivity(e, self.NOW - 2000, 1000))),
            StatsRoot('z-clone', 'Clone', (clone,), (), responses=(ResponseCall(clone, 1000),)))
        prices = {170: Decimal('.0012'), 300: Decimal('.0023'), 220: Decimal('.0045'),
                  400: Decimal('.0089'), 50: Decimal('.0001')}
        observation = StatsObservation(roots, lambda _model, tokens: prices[tokens.total], now=self.NOW, zone='UTC')
        expected = {
            'hourly-rate': (Decimal('.0170') * 3600000 / 7000,
                (('High', Decimal('12.06')), ('Default', Decimal('2.1')), ('Low', Decimal('.36')))),
            'total-cost': (Decimal('.0170'), (('High', Decimal('.0134')), ('Default', Decimal('.0035')), ('Low', Decimal('.0001')))),
            'total-tokens': (1140, (('High', 620), ('Default', 470), ('Low', 50))),
            'working-time': (7000, (('Default', 6000), ('High', 4000), ('Low', 1000))),
            'average-cost': (Decimal('.0085'), (('High', Decimal('.0067')), ('Default', Decimal('.0035')), ('Low', Decimal('.0001')))),
            'token-rate': (Decimal(1060) / 15, (('Default', Decimal('102.5')), ('High', Decimal(60)), ('Low', Decimal(50)))),
        }
        for period, start in (('today', self.NOW - 3600000), ('7-days', self.NOW - 7 * DAY_MS),
                              ('30-days', self.NOW - 30 * DAY_MS), ('month', self.NOW - 10 * DAY_MS), ('all', None)):
            result = observation.period(period=period, start=start)
            metrics = {m.metric: m for m in result.metrics}
            for metric, (amount, efforts) in expected.items():
                with self.subTest(period=period, metric=metric):
                    self.assertEqual(1, len(metrics[metric].podium))
                    row = metrics[metric].podium[0]
                    self.assertEqual('Claude Sonnet 5.5', row.display_name)
                    self.assertEqual(amount, row.tokens_per_second if metric == 'token-rate' else row.value)
                    self.assertEqual(efforts, row.by_effort)
            dto = project(ReportProjection(ReportKind.AI_STATS, 'Stats', 'SYNTHETIC', ai_stats=(result,))).to_json()
            for card in dto['ai_stats'][0]['metrics']:
                if card['metric'] not in expected:
                    continue
                row = card['podium'][0]
                self.assertRegex(row['model_help'], r'^claude-agent/Claude Sonnet 5\.5\n\nBy Effort:\n• ')
                self.assertEqual(1, row['model_help'].count('• Default'))
                self.assertNotRegex(row['model_help'], r'unverified|signature|catalog|observed|sampled|\(medium\)')
                if card['metric'] in ('hourly-rate', 'total-cost', 'average-cost'):
                    self.assertIn('$', row['display_units']['usd']['model_help'])
                    self.assertIn('CCost', row['display']['model_help'])
                else:
                    self.assertNotIn('display_units', row)

    def test_catalog_family_best_effort_is_local_and_explicit_old_releases_stay_old(self):
        from development.tests.fixtures.report_runtime import FakePricingProvider
        base = FakePricingProvider().get_catalog().models[0]
        catalog = PricingCatalog(tuple(replace(base, model=ModelRef('github-copilot', identity, label))
            for identity, label in (('claude-sonnet-4-6', 'Claude Sonnet 4.6'),
                                    ('claude-sonnet-5-5', 'Claude Sonnet 5.5'))))
        alias = ModelRef('claude-agent', 'sonnet')
        old = ModelRef('claude-agent', 'claude-sonnet-4-6')

        self.assertEqual('Claude Sonnet 5.5', friendly_model(alias, catalog))
        self.assertEqual('Claude Sonnet 4.6', friendly_model(old, catalog))
        self.assertEqual('Claude Sonnet', friendly_model(alias, PricingCatalog(())))
        self.assertEqual('Claude Sonnet (version unverified)', catalog.display_name('sonnet', 'claude-agent', exact=True))
        self.assertIsNone(catalog.reference_valuation(alias, TokenUsage(output=100)))
        self.assertEqual('sonnet', alias.recorded_model)
        conflicting_hint = ModelRef('claude-agent', 'claude-sonnet-5-5', 'Claude Sonnet 5.5',
            resolution=ModelResolution('claude-sonnet-4-6', 'source', 'signature'))
        self.assertEqual('Claude Sonnet 4.6', friendly_model(conflicting_hint, PricingCatalog(())))

    def test_alias_sampling_is_one_32_call_cohort_before_effort_and_headline_math(self):
        calls = tuple(ResponseCall(replace(self.request('root', str(i), 'alias', TokenUsage(output=100 + i),
                variant=('default', 'high')[i % 2], age=1000 + i),
                model=ModelRef('claude-agent', 'claude-sonnet-5-5',
                    resolution=ModelResolution('sonnet', str(i % 2), 'signature' + str(i % 2)))), 1000 + i * 100)
            for i in range(96))
        root = StatsRoot('root', 'Root', tuple(c.entry for c in calls), (), responses=calls)

        metrics, _dto = calculate((root,), self.NOW)

        row = metrics['token-rate'].podium[0]
        self.assertEqual(32, row.sampled_calls)
        selected = sample(calls)
        self.assertEqual(Decimal(sum(c.entry.tokens.output for c in selected)) * 1000 /
                         sum(c.duration_ms for c in selected), metrics['token-rate'].value)
        self.assertEqual(row.tokens_per_second, metrics['token-rate'].value)
        for effort, speed in row.by_effort:
            subset = [c for c in selected if (c.entry.variant == 'high') == (effort == 'High')]
            self.assertEqual(Decimal(sum(c.entry.tokens.output for c in subset)) * 1000 /
                             sum(c.duration_ms for c in subset), speed)

    def test_existing_source_qualified_compact_samples_reproject_without_history_rehydration(self):
        requests = tuple(replace(self.request('root', str(i), 'alias', TokenUsage(output=100 + i), age=1000 + i),
            model=ModelRef('claude-agent', 'claude-sonnet-5-5',
                resolution=ModelResolution('sonnet', str(i % 2), 'signature' + str(i % 2)))) for i in range(96))
        snapshot = SimpleNamespace(messages=(), invocations=tuple(SimpleNamespace(
            session_id=e.session_id, message_id=e.message_id, step_part_id=None,
            created_at_ms=e.completed_at_ms - 1000, completed_at_ms=e.completed_at_ms) for e in requests))
        encoded = encode_responses(SimpleNamespace(trace_entries=requests), snapshot, self.NOW)
        restored = decode_responses(encoded, [(e, None, None) for e in requests])
        root = StatsRoot('root', 'Root', requests, (), responses=restored)

        metrics, _dto = calculate((root,), self.NOW)

        self.assertEqual(64, len(restored), 'existing source-qualified evidence remains decodable')
        self.assertEqual(1, len(metrics['token-rate'].podium))
        self.assertEqual(32, metrics['token-rate'].podium[0].sampled_calls, 'one final friendly cohort, not 64 calls')

if __name__ == '__main__':
    unittest.main()
