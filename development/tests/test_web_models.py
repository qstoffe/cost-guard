"""Models CLI membership/order, canonical tiers, fallback and rendered exact sorting."""
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from development.tests.fixtures.compact_reports import Availability, rendered, report_service
from development.tests.fixtures.model_views import model_report
from src.application.projection import project
from src.domain import ModelPricing, ModelRef, PricingTier
from src.pricing.catalog import PricingCatalog
from src.reports.model_comparison import web_model_catalog
from src.reports import ReportRequest

ROOT = Path(__file__).resolve().parents[2]


class ModelsTests(unittest.TestCase):
    def test_supersession_uses_selected_candidates_not_newer_unselectable_rows(self):
        report = model_report(include_model_catalog=True)
        catalog = report.model_catalog
        selected = tuple(pair for pair in catalog.selectable if pair[1] != 'GPT-5.2')
        dto = project(replace(report, model_catalog=replace(catalog, selectable=selected))).to_json()
        rows = {row['model']: row for row in dto['model_catalog']['rows']}
        self.assertTrue(rows['GPT-5.1']['superseded'])
        self.assertFalse(rows['GPT-5.1']['superseded_selectable'])
        self.assertTrue(rows['GPT-5.1']['selectable'])
        self.assertFalse(rows['GPT-5.2']['selectable'])

    def test_full_catalog_keeps_canonical_recent_and_promotion_semantics(self):
        now = 1793491200000
        model = ModelPricing(ModelRef('github-copilot', 'New model', 'New model'), 'USD',
            tiers=(PricingTier(per_million_input=Decimal('1')),), metadata={
                'publisher': 'Test', 'release_date': '2026-11-01', 'promotion_active': 'true',
                'promotion_expires_ms': str(now + 86400000), 'promotion_discount_percent': '50'})
        catalog = PricingCatalog((model,))
        frozen = web_model_catalog((), catalog, catalog, now_ms=now, cache_repository=None)
        self.assertTrue(frozen.rows[0].recent)
        self.assertTrue(frozen.rows[0].promotional)
        self.assertEqual(1, frozen.rows[0].promotion_marker)
        self.assertIn('Price Promotion: New model', frozen.promotion_notes[0])
        self.assertIn('50% off', frozen.promotion_notes[0])
        self.assertEqual('New model', frozen.recent_notices[0][0])
        self.assertIn('released 2026-11-01', frozen.recent_notices[0][1])

    def test_full_frozen_catalog_keeps_unknown_prices_and_selectable_supersession(self):
        dto = project(model_report(include_model_catalog=True)).to_json()
        rows = {row['model']: row for row in dto['model_catalog']['rows']}
        self.assertEqual(8, len(rows))
        self.assertIsNone(rows['Unknown']['relative_cost'])
        self.assertFalse(rows['Unselectable']['selectable'])
        self.assertTrue(rows['GPT-5.1']['superseded_selectable'])
        self.assertFalse(rows['GPT-5.2']['superseded_selectable'])
        self.assertEqual('8', rows['GPT-5.1']['relative_cost'])

    def test_web_snapshot_reuses_normal_acquisition_and_preserves_cli_scope(self):
        availability = Availability()
        service = report_service(self, availability=availability)
        report = service.build(ReportRequest(), include_model_catalog=True)
        self.assertEqual(1, availability.calls)
        self.assertIsNotNone(report.accounts_quotas)
        self.assertIsNotNone(report.model_catalog)
        self.assertGreaterEqual(len(report.model_catalog.rows), len(report.model_comparison))
        dto = project(report).to_json()
        selected = [row for row in dto['model_catalog']['rows'] if row['selectable']]
        self.assertEqual([(row.publisher, row.model) for row in report.model_comparison],
                         [(row['publisher'], row['model']) for row in selected])

    def test_selectable_and_all_catalogs_match_cli_even_without_priced_sample(self):
        for all_models in (False, True):
            for fallback in (False, True):
                with self.subTest(all_models=all_models, fallback=fallback):
                    report = model_report(all_models=all_models, fallback=fallback)
                    cli = rendered(report, width=2000)
                    dto = project(report).to_json()
                    names = [line.split("|")[2].strip() for line in cli.splitlines() if line.startswith("| OpenAI")]
                    full_names = [row["model"] for row in dto["model_comparison"]]
                    self.assertEqual([name if len(name) <= 80 else name[:77] + "..." for name in full_names], names)
                    self.assertEqual(all_models, "Unselectable" in names)
                    self.assertLess(names.index("Z"), names.index("A"))
                    old = next(row for row in dto["model_comparison"] if row["model"] == "GPT-5.1")
                    self.assertTrue(old["superseded"])
                    self.assertEqual("N/A → N/A (>200K) → N/A (≥1M)" if fallback else
                        "8.0x → 16.0x (>200K) → 32.0x (≥1M)", old["display"]["relative_cost"])
                    if all_models:
                        self.assertIn("2.1234567890123456789", cli)
                    if shutil.which("node"):
                        result = subprocess.run(["node", "development/tests/integration/web_models.cjs"],
                            input=json.dumps(dict(view=dto, order=full_names, fallback=fallback)),
                            cwd=ROOT, capture_output=True, text=True, timeout=10)
                        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_availability_fallback_and_verified_empty_are_distinct(self):
        for availability in ("unverified", "empty"):
            report = model_report(availability=availability)
            dto = project(report).to_json()
            self.assertEqual(availability == "unverified", dto["model_availability_unverified"])
            self.assertEqual(availability == "empty", dto["model_availability_empty"])
            self.assertEqual(7 if availability == "unverified" else 0, len(dto["model_comparison"]))
            self.assertTrue(report.source_warnings)


if __name__ == "__main__":
    unittest.main()
