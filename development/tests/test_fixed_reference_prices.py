"""Fixed Web reference prices never turn synthetic weights into observed history."""
from dataclasses import replace
from decimal import Decimal as D
import json
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import Availability, report_service, START, NOW
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.test_workload_mix import prices
from src.analysis.comparisons import model_comparison_rows
from src.analysis.token_mix import PricedUsage
from src.application.projection import project
from src.domain import ModelPricing, ModelRef, PricingTier
from src.pricing.catalog import PricingCatalog
from src.reports import ReportKind, ReportRequest
from src.reports.model_comparison import compact_boundary, web_model_catalog, web_model_promotion


class FixedReferenceTests(unittest.TestCase):
    def test_fixed_weights_and_full_denominator_ignore_history_and_selectable_scope(self):
        catalog = prices()
        # Independent 2/96/1/1 formula, with source-supported zero cache-write.
        units = {'gpt-test': D('.166'), 'gpt-other': D('.252'),
                 'claude-test': D('.358'), 'untried': D('.156')}
        expected = {name: value / D('.156') for name, value in units.items()}
        selected = replace(catalog, models=catalog.models[:1])
        initial = None
        for count in (0, 1, 100, 10000):
            usage = (PricedUsage(output_tokens=100),) * count
            frozen = web_model_catalog(usage, catalog, selected, now_ms=NOW, cache_repository=None)
            rows = {row.model: row for row in frozen.rows}
            self.assertEqual(expected, {name: row.relative_cost for name, row in rows.items()})
            self.assertEqual((('OpenAI', 'gpt-test'),), frozen.selectable)
            self.assertEqual(D('.266') / D('.156'), rows['gpt-test'].relative_levels[1].relative_cost)
            self.assertTrue(all(row.evidence.global_prompts == 0 for row in rows.values()))
            if initial is not None:
                self.assertEqual(initial, frozen)
            initial = frozen
        # Fixed projection must not even enumerate a passed history generator.
        def forbidden():
            raise AssertionError('fixed prices do not inspect history')
            yield
        self.assertTrue(model_comparison_rows(forbidden(), catalog, fixed_reference=True))

    def test_models_only_does_not_list_hydrate_analyze_or_sample_historical_roots(self):
        for count in (0, 1, 100, 5000):
            source = SyntheticMonthSource(1, count, month_start_ms=START)
            service = report_service(self, source, now_ms=NOW, availability=Availability(None))
            service.pricing_provider.catalog = prices()
            with patch.object(service, 'session_catalog', side_effect=AssertionError('no history catalog')), \
                    patch.object(service, '_analyze', side_effect=AssertionError('no root analysis')), \
                    patch('src.reports.service.recent_sample_roots', side_effect=AssertionError('no sampling')), \
                    patch('src.reports.service.latest_prompts', side_effect=AssertionError('no prompt extraction')):
                report = service.build_model_price_list(ReportRequest(ReportKind.NORMAL))
            self.assertEqual(0, source.load_count)
            self.assertIsNone(service._comparison_mix, 'Watch warning sample is not synthetic')
            self.assertIsNone(report.accounts_quotas)
            self.assertEqual(0, report.model_comparison_sample_size)
            self.assertIsNone(report.model_comparison_mix)
            dto = project(report).to_json()
            self.assertEqual('fixed-statistical-average', dto['model_catalog']['comparison_basis'])
            self.assertEqual(['0.02', '0.96', '0.01', '0.01'], dto['model_catalog']['reference_token_weights'])
            self.assertEqual('1', next(row['relative_cost'] for row in dto['model_catalog']['rows'] if row['model'] == 'untried'))

    def test_unknown_rates_stay_unknown_and_boundaries_are_exact(self):
        tier = PricingTier(per_million_input=D(1), per_million_cache_read=D(0),
                           per_million_output=D(2))
        known = ModelPricing(ModelRef('github-copilot', 'known'), 'USD', tiers=(tier,))
        unknown = replace(known, model=ModelRef('github-copilot', 'unknown'),
                          tiers=(replace(tier, per_million_cache_read=None),))
        rows = model_comparison_rows((), PricingCatalog((known, unknown)),
            include_uncomparable=True, fixed_reference=True)
        self.assertEqual('unknown', rows[-1].model_name)
        self.assertIsNone(rows[-1].relative_to_lowest)
        for number, text in ((272000, '272K'), (272001, '272.001K'), (1000000, '1M'), (1000001, '1.000001M'), (999, '999')):
            self.assertEqual(text, compact_boundary(number))


class PromotionReferenceTests(unittest.TestCase):
    def model(self, *, rates=('7', '0.7', '14', '21'), metadata=None):
        return ModelPricing(ModelRef('github-copilot', 'Offer', 'Offer'), 'USD',
            tiers=(PricingTier(**dict(zip(('per_million_input', 'per_million_cache_read',
                'per_million_cache_write', 'per_million_output'), map(D, rates)))),),
            metadata={'promotion_active': 'true', 'promotion_expires_ms': str(NOW + 86400000),
                      'promotion_discount_percent': '30', **(metadata or {})})

    def test_current_percent_is_of_original_not_discount_and_expired_is_absent(self):
        model = self.model()
        offer = web_model_promotion(model, NOW)
        self.assertEqual('70% of original price (30% off)', offer.price_comparison)
        self.assertIsNone(web_model_promotion(model, NOW + 86400000))
        for discount in ('', 'NaN', '-1', '100', '101', 'unpublished'):
            unknown = self.model(metadata={'promotion_discount_percent': discount})
            offer = web_model_promotion(unknown, NOW)
            self.assertEqual('', offer.price_comparison)
            self.assertTrue(offer.through)
        missing = replace(model, tiers=(replace(model.tiers[0], per_million_input=None),))
        self.assertEqual('', web_model_promotion(missing, NOW).price_comparison)

    def test_weighted_standard_tiers_and_different_tier_percentages_are_qualified(self):
        model = self.model(rates=('7', '0.7', '14', '21'))
        tier = model.tiers[0]
        model = replace(model, tiers=(replace(tier, max_input_tokens=272000),
            replace(tier, min_input_tokens=272001, input_threshold_operator='>')))
        standard = [
            dict(min=None, max=272000, threshold_operator=None, i='10', c='1', w='20', o='30'),
            dict(min=272001, max=None, threshold_operator='>', i='14', c='1.4', w='28', o='42')]
        model = replace(model, metadata={**model.metadata, 'promotion_standard_tiers': json.dumps(standard)})
        self.assertEqual('Base context tier: 70% of original price (30% off)\n'
            'Input context >272K tokens: 50% of original price (50% off)',
            web_model_promotion(model, NOW).price_comparison)
        standard[0]['c'] = '2'
        changed_weights = replace(model, metadata={**model.metadata, 'promotion_standard_tiers': json.dumps(standard)})
        self.assertIn('Base context tier: 44.35% of original price (55.65% off)',
                      web_model_promotion(changed_weights, NOW).price_comparison)
        standard[0]['c'] = None
        unknown = replace(model, metadata={**model.metadata, 'promotion_standard_tiers': json.dumps(standard)})
        self.assertEqual('Input context >272K tokens: 50% of original price (50% off)',
                         web_model_promotion(unknown, NOW).price_comparison)
        standard[1]['min'] = 300001
        mismatched = replace(model, metadata={**model.metadata, 'promotion_standard_tiers': json.dumps(standard)})
        self.assertEqual('', web_model_promotion(mismatched, NOW).price_comparison)
