"""Independent model/publisher weights, canonical eligibility and revision reuse."""
from dataclasses import replace
from decimal import Decimal as D
import io
import unittest

from development.tests.fixtures.compact_reports import Availability, report_service, START, NOW
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests.fixtures.session_snapshots import make_snapshot
from src.analysis import analyze_snapshot
from src.analysis.comparisons import model_comparison_rows, threshold_cost_multiplier
from src.analysis.token_mix import PricedUsage
from src.analysis.workload_mix import PromptMix, WorkloadSamples, prompt_mix
from src.application.projection import project
from src.application.contracts import export
from src.domain import ModelPricing, ModelRef, PricingTier, TokenUsage
from src.pricing.catalog import PricingCatalog
from src.pricing.publishers import publisher_for
from src.presentation import ReportRenderer
from src.reports.service import ReportRequest
from src.reports.models import ReportKind


def prices():
    def model(name, publisher, rates):
        tier = PricingTier(per_million_input=D(rates[0]), per_million_cache_read=D(rates[1]),
                           per_million_cache_write=D(0), per_million_output=D(rates[2]), max_input_tokens=100)
        return ModelPricing(ModelRef("github-copilot", name, name), "USD", tiers=(tier,
            replace(tier, min_input_tokens=101, max_input_tokens=None, per_million_output=D(rates[2]) * 3)),
            metadata={"publisher": publisher} if publisher else {})
    return PricingCatalog((model("gpt-test", "OpenAI", ("1", ".1", "5")),
        model("gpt-other", "open ai", ("2", ".2", "2")),
        model("claude-test", "Anthropic", ("3", ".3", "1")), model("untried", "OpenAI", ("1", ".1", "4"))))


def add(samples, model, publisher, count, tokens, *, start=0):
    for i in range(start, start + count):
        samples.add(PromptMix(i, "root", f"{model}-{i}", ((model, publisher, tokens),)))


class WorkloadMixTests(unittest.TestCase):
    def test_model_counts_zero_one_ten_99_100_and_more_are_prompt_slots(self):
        for count in (0, 1, 10, 99, 100, 121):
            with self.subTest(count=count):
                samples = WorkloadSamples()
                add(samples, "m", "OpenAI", count, (1, 0, 0, 0))
                add(samples, "p", "OpenAI", 110, (0, 0, 0, 10000), start=1000)
                mix, evidence = samples.effective("m", "OpenAI")
                own = min(count, 100)
                self.assertEqual((D(own) / 100, D(0), D(0), D(100 - own) / 100), mix[:4])
                self.assertEqual((own, 100 - own, 0),
                    (evidence.model_prompts, evidence.publisher_prompts, evidence.generic_prior_weight))
                self.assertEqual(D(1), sum(mix[:4]))

    def test_ten_forty_fifty_uses_pooled_shares_not_concatenated_tokens(self):
        samples = WorkloadSamples()
        add(samples, "m", "OpenAI", 10, (1, 0, 0, 0))
        add(samples, "p", "OpenAI", 40, (0, 100, 0, 0), start=100)
        add(samples, "other", "Anthropic", 100, (0, 0, 0, 7), start=200)
        mix, evidence = samples.effective("m", "OpenAI")
        self.assertEqual((D('.1'), D('.4'), D(0), D('.5')), mix[:4])
        self.assertEqual((10, 40, 50, 100, 50), (evidence.model_prompts, evidence.publisher_prompts,
            evidence.generic_prior_weight, evidence.global_prompts, evidence.observed_prompts))

    def test_short_history_prior_is_not_fabricated_observations(self):
        samples = WorkloadSamples()
        add(samples, "m", "OpenAI", 1, (3, 1, 0, 0))
        for publisher in (None, "Anthropic"):
            mix, evidence = samples.effective("untried", publisher)
            self.assertEqual((D('.75'), D('.25'), D(0), D(0), 1), mix)
            self.assertEqual((0, 0, 100, 1), (evidence.model_prompts, evidence.publisher_prompts,
                evidence.generic_prior_weight, evidence.global_prompts))
        empty, evidence = WorkloadSamples().effective("m", "OpenAI")
        self.assertEqual((D(0),) * 4 + (0,), empty)
        self.assertEqual(0, evidence.global_prompts)

    def test_mixed_prompt_exclusion_and_same_publisher_other_models_only(self):
        samples = WorkloadSamples()
        samples.add(PromptMix(1, "s", "mixed", (("m", "OpenAI", (1, 0, 0, 0)),
            ("p", "OpenAI", (0, 1000, 0, 0)), ("x", "Anthropic", (0, 0, 0, 1000)))))
        add(samples, "p", "OpenAI", 100, (0, 10, 0, 0), start=2)
        mix, evidence = samples.effective("m", "OpenAI")
        self.assertEqual((D('.01'), D('.99'), D(0), D(0)), mix[:4])
        self.assertEqual(99, evidence.publisher_prompts)
        # Deduplicating a compact sample never duplicates evidence.
        for item in samples.compact():
            samples.add(item)
        self.assertEqual(evidence, samples.effective("m", "OpenAI")[1])

    def test_publisher_zero_forty_ninety_100_and_200_exclusion_bound(self):
        for count in (0, 40, 90, 100):
            samples = WorkloadSamples()
            add(samples, "p", "OpenAI", count, (0, 1, 0, 0))
            add(samples, "x", "Anthropic", 100, (0, 0, 0, 1), start=1000)
            mix, evidence = samples.effective("untried", "OpenAI")
            self.assertEqual((D(0), D(count) / 100, D(0), D(100 - count) / 100), mix[:4])
            self.assertEqual(count, evidence.publisher_prompts)

    def test_canonical_eligibility_dedup_reasoning_and_manufacturer_identity(self):
        catalog = prices()
        bundle = analyze_snapshot(make_snapshot(), now_ms=4000)
        record = bundle.prompts[0]
        base = record.entries[0]
        entry = replace(base, model=ModelRef("claude-code", "gpt-test"), tokens=TokenUsage(input=2, output=3, reasoning=5))
        invalid = replace(entry, message_id="bad", step_part_id="bad", tokens=TokenUsage(input=999, known_fields=("input",)))
        unknown = replace(entry, message_id="unknown", step_part_id="unknown", model=ModelRef("github-copilot", "unknown"))
        clone = replace(entry, session_id='fork')
        prompt = replace(record, in_progress=False, aborted=False, entries=(entry,) * 100 + (clone, invalid, unknown))
        compact = prompt_mix(prompt, catalog)
        self.assertEqual((("gpt-test", "OpenAI", (2, 0, 0, 8)),), compact.groups)
        for change in ({"in_progress": True}, {"aborted": True}):
            self.assertIsNone(prompt_mix(replace(prompt, **change), catalog))
        self.assertEqual("OpenAI", publisher_for(catalog, "github-copilot/gpt-other"))
        for metadata in ({}, {"publisher": "GitHub Copilot"}, {"publisher": "OpenAI", "manufacturer": "Anthropic"}):
            altered = PricingCatalog((replace(catalog.models[0], metadata=metadata),))
            self.assertIsNone(publisher_for(altered, "gpt-test"))

    def test_global_mix_prices_every_model_and_warning_tier_ratio(self):
        catalog = prices()
        usage = (PricedUsage(cache_read_tokens=90), PricedUsage(output_tokens=10))
        rows = {r.model_name: r for r in model_comparison_rows(usage, catalog)}
        # Shared 90% cache / 10% output: .59, .38, .37, .49 USD/M.
        self.assertEqual(D('.59') / D('.37'), rows['gpt-test'].relative_to_lowest)
        self.assertEqual(D(1), rows['claude-test'].relative_to_lowest)
        self.assertEqual(D('.38') / D('.37'), rows['gpt-other'].relative_to_lowest)
        self.assertEqual(D('.49') / D('.37'), rows['untried'].relative_to_lowest)
        self.assertTrue(all(row.evidence.global_prompts == 2 for row in rows.values()))
        mix = (D(0), D('.9'), D(0), D('.1'), 2)
        multiplier = threshold_cost_multiplier(catalog, 'gpt-test', 100, mix)
        self.assertEqual(D('1.59') / D('.59'), multiplier)
        levels = rows['gpt-test'].relative_levels
        self.assertAlmostEqual(multiplier, levels[1].relative_cost / levels[0].relative_cost, places=25)

    def test_identical_prices_compare_equally_including_untried_models(self):
        catalog = prices()
        catalog = PricingCatalog((catalog.models[0], replace(catalog.models[0],
            model=ModelRef('route', 'untried', 'untried'), metadata={})))
        rows = model_comparison_rows((PricedUsage(input_tokens=3, output_tokens=7),), catalog)
        self.assertEqual(2, len(rows))
        self.assertEqual(rows[0].estimated_ccost, rows[1].estimated_ccost)
        self.assertEqual(rows[0].relative_levels, rows[1].relative_levels)
        self.assertEqual(D(1), rows[0].relative_to_lowest)


class ComparisonHistoryTests(unittest.TestCase):
    def test_warning_first_uses_global_sample_not_targets_older_own_prompts(self):
        source = SyntheticMonthSource(2, 100, month_start_ms=START)
        for index in range(2):
            # Separate the roots by a day: 100 one-second prompts otherwise overlap.
            root = make_root_snapshot(index, 100, month_start_ms=START + index * 86_400_000)
            source.snapshots[root.root.session_id] = replace(root, invocations=tuple(
                replace(item, model=ModelRef('route', 'gpt-test' if index == 0 else 'claude-test'),
                    tokens=TokenUsage(output=100) if index == 0 else TokenUsage(cache_read=90, output=10))
                for item in root.invocations))
        service = report_service(self, source, now_ms=NOW)
        service.pricing_provider.catalog = prices()
        expected = D('1.59') / D('.59')
        self.assertEqual(expected, service._threshold_multiplier('gpt-test', 100))
        self.assertEqual(1, source.load_count, 'older target history is not acquired')
        report = service.build(ReportRequest(ReportKind.ALL_MODELS))
        levels = next(row for row in report.model_comparison if row.model == 'gpt-test').relative_levels
        self.assertAlmostEqual(expected, levels[1].relative_cost / levels[0].relative_cost, places=25)

    def test_actual_global_sample_sizes_and_warning_cache_use_same_pooled_mix(self):
        for count in (0, 1, 99, 100, 121):
            with self.subTest(count=count):
                source = SyntheticMonthSource(1, count, month_start_ms=START)
                root = source.snapshots['root-0000']
                # Deliberately dissimilar model/publisher jobs, not equal prompt weights.
                source.snapshots['root-0000'] = replace(root, invocations=tuple(
                    replace(item, model=ModelRef('route', 'gpt-test' if i % 2 else 'claude-test'),
                        tokens=TokenUsage(cache_read=90) if i % 2 else TokenUsage(output=10))
                    for i, item in enumerate(root.invocations)))
                service = report_service(self, source, now_ms=NOW)
                service.pricing_provider.catalog = prices()
                report = service.build(ReportRequest(ReportKind.ALL_MODELS))
                self.assertEqual(min(count, 100), report.model_comparison_sample_size)
                rows = {row.model: row for row in report.model_comparison}
                if not count:
                    self.assertTrue(all(row.relative_cost is None for row in rows.values()))
                    continue
                cached = min(count // 2, 50) * 90
                output = min((count + 1) // 2, 50) * 10
                total = D(cached + output)
                # Independent category-price formula; every row uses these same volumes.
                raw = {name: (D(cached) * cache + D(output) * out) / total
                    for name, cache, out in (('gpt-test', D('.1'), D(5)),
                        ('gpt-other', D('.2'), D(2)), ('claude-test', D('.3'), D(1)),
                        ('untried', D('.1'), D(4)))}
                for name, cost in raw.items():
                    self.assertAlmostEqual(cost / min(raw.values()), rows[name].relative_cost, places=25)
                expected = (D(cached) * D('.1') + D(output) * 15) / (D(cached) * D('.1') + D(output) * 5)
                self.assertAlmostEqual(expected, service._threshold_multiplier('gpt-test', 100), places=25)
                dto = export(project(report))
                self.assertEqual(min(count, 100), dto['model_comparison_sample_size'])
                for row in dto['model_comparison']:
                    self.assertIn(f"latest {min(count, 100)} completed priceable prompts globally", row['display']['evidence'])

    def test_older_model_history_never_changes_global_comparison_or_loads_deep_roots(self):
        source = SyntheticMonthSource(12, 20, month_start_ms=START)
        for index in range(5):
            root = source.snapshots[f"root-{index:04d}"]
            source.snapshots[root.root.session_id] = replace(root, invocations=tuple(replace(i,
                model=ModelRef('route', 'claude-test'), tokens=TokenUsage(output=100)) for i in root.invocations))
        service = report_service(self, source, now_ms=NOW)
        service.pricing_provider.catalog = prices()
        first = service.build(ReportRequest(ReportKind.ALL_MODELS))
        older = next(r for r in first.model_comparison if r.model == 'claude-test')
        self.assertEqual((0, 0, 100), (older.evidence.model_prompts,
            older.evidence.publisher_prompts, older.evidence.global_prompts))
        self.assertEqual(100, first.token_mix.sample_size)
        self.assertLess(source.load_count, 12)
        loaded = source.load_count
        self.assertLess(len(service._analyzed), 12, 'deep snapshots released')
        warm = report_service(self, source, now_ms=NOW)
        # New service with the SAME cache repository proves cross-process-style reuse.
        warm.cache_repository = service.cache_repository
        warm._derived.repository = service.cache_repository
        warm.pricing_provider.catalog = prices()
        again = warm.build(ReportRequest(ReportKind.ALL_MODELS))
        self.assertEqual(first.model_comparison, again.model_comparison)
        self.assertEqual(loaded, source.load_count)
        source.snapshots.pop('root-0000')
        revised = warm.build(ReportRequest(ReportKind.ALL_MODELS))
        self.assertEqual(first.model_comparison, revised.model_comparison)
        root = source.snapshots['root-0001']
        source.snapshots[root.root.session_id] = replace(root, source_revision='changed', invocations=tuple(
            replace(i, model=ModelRef('route', 'gpt-test')) for i in root.invocations))
        changed = warm.build(ReportRequest(ReportKind.ALL_MODELS))
        self.assertEqual(first.model_comparison, changed.model_comparison)
        self.assertEqual(loaded, source.load_count)

    def test_publisher_history_reconciles_same_requests_and_shared_cli_web_projection(self):
        source = SyntheticMonthSource(1, 2, month_start_ms=START)
        root = source.snapshots['root-0000']
        first = root.invocations[0]
        extra = replace(first, invocation_id='extra', provider_request_id='extra', message_id='extra',
                        model=ModelRef('route', 'gpt-other'), tokens=TokenUsage(output=300))
        unknown = replace(extra, invocation_id='unknown', provider_request_id='unknown', message_id='unknown',
                          model=ModelRef('route', 'missing'))
        source.snapshots['root-0000'] = replace(root, invocations=(*root.invocations, extra, unknown))
        service = report_service(self, source, now_ms=NOW, availability=Availability(None))
        service.pricing_provider.catalog = prices()
        report = service.build_token_mix_history()
        family = next(p for p in report.publisher_token_mix if p.publisher == 'OpenAI')
        self.assertEqual((2, 3), (family.prompts, family.calls))
        self.assertEqual(report.token_mix.request_count, sum(p.calls for p in report.publisher_token_mix))
        self.assertEqual(sum(report.token_mix.costs), sum(sum(p.mix.costs) for p in report.publisher_token_mix))
        self.assertEqual(report.token_mix.total_tokens, sum(p.mix.total_tokens for p in report.publisher_token_mix))
        self.assertEqual(report.token_mix.total_tokens, sum(m.mix.total_tokens for m in report.model_token_mix))
        dto = export(project(report))
        self.assertEqual('OpenAI', dto['publisher_token_mix'][0]['publisher'])
        self.assertEqual('3', str(dto['publisher_token_mix'][0]['calls']))
        stream = io.StringIO()
        ReportRenderer({'timezone': 'UTC'}, stream=stream, color_enabled=False, terminal_width=120).render(report)
        self.assertIn('Token Mix % by publisher', stream.getvalue())
        self.assertIn('Unknown / unverified', stream.getvalue())
        service.model_availability_source = Availability(('gpt-test',))
        filtered = service.build_token_mix_history()
        self.assertEqual(['gpt-test'], [row.model for row in filtered.model_token_mix])
        self.assertEqual(['OpenAI'], [row.publisher for row in filtered.publisher_token_mix])
        self.assertEqual((2, 2), (filtered.publisher_token_mix[0].prompts, filtered.publisher_token_mix[0].calls))
        self.assertEqual(filtered.token_mix, filtered.publisher_token_mix[0].mix)


if __name__ == '__main__':
    unittest.main()
