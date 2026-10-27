"""Models CLI membership/order, canonical tiers, fallback and rendered exact sorting."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from development.tests.fixtures.compact_reports import rendered
from development.tests.fixtures.model_views import model_report
from src.application.projection import project

ROOT = Path(__file__).resolve().parents[2]


class ModelsTests(unittest.TestCase):
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
