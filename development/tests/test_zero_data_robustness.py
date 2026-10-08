"""Fresh price lists and conservative report-only installation errors."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal as D
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

from development.fixtures.synthetic_month import SyntheticMonthSource
from development.tests import test_compact_reports as compact
from src import bootstrap
from src.analysis.comparisons import model_comparison_rows
from src.domain import ModelPricing, ModelRef, PricingTier
from src.pricing.catalog import PricingCatalog, token_mix_unit_price
from src.reports import ReportRequest, ReportKind
from src.sources.discovery import has_opencode_installation_evidence
from src.sources.errors import SourceUnavailableError
from src.sources.selection import SourceSelector


def catalog():
    def model(name, i, c, w, o):
        return ModelPricing(ModelRef("fixture", name, name), "USD", D(i), D(c),
                            None if w is None else D(w), D(o))
    return PricingCatalog((model("Input heavy", 10, ".1", None, 10),
                           model("Cache heavy", 1, 1, 1, 1)))


def sample(i=0, c=0, w=0, o=0):
    return SimpleNamespace(input_tokens=i, cache_read_tokens=c, cache_write_tokens=w, output_tokens=o)


class SyntheticSortingTests(unittest.TestCase):
    def test_default_is_weighted_and_not_exposed_as_observed_data(self):
        for records in ((), (sample(),)):
            rows = model_comparison_rows(records, catalog())
            self.assertEqual(["Cache heavy", "Input heavy"], [row.model_name for row in rows])
            self.assertTrue(all(row.relative_to_lowest is None and row.estimated_ccost is None for row in rows))

    def test_real_usage_replaces_default_automatically(self):
        prices = catalog()
        default = model_comparison_rows((), prices)
        actual = model_comparison_rows((sample(i=100),), prices)
        self.assertEqual(["Input heavy", "Cache heavy"], [row.model_name for row in actual])
        self.assertNotEqual(default, actual)
        self.assertEqual((D(10), D(1)), tuple(row.relative_to_lowest for row in actual))

    def test_same_normal_pricing_path_preserves_tiers_and_missing_write_fallback(self):
        prices = catalog()
        base = PricingTier(max_input_tokens=100, per_million_input=D(10),
                           per_million_cache_read=D(".1"), per_million_output=D(10))
        long = replace(base, min_input_tokens=101, max_input_tokens=None, per_million_cache_read=D(1000))
        prices = PricingCatalog((replace(prices.models[0], tiers=(base, long)), prices.models[1],
                                 ModelPricing(ModelRef("fixture", "Unpriced", "Unpriced"), "USD")))
        fallback = model_comparison_rows((), prices)
        actual = model_comparison_rows((sample(2, 96, 1, 1),), prices)
        self.assertEqual(["Cache heavy", "Input heavy", "Unpriced"], [r.model_name for r in fallback])
        self.assertEqual([r.model_name for r in fallback[:2]], [r.model_name for r in actual])
        mix = (D(".02"), D(".96"), D(".01"), D(".01"), 1)
        self.assertEqual(D("49.6"), token_mix_unit_price(mix, prices.ccost_models[0]))
        self.assertTrue(all(r.estimated_ccost is None for r in fallback))

    def test_fresh_report_and_all_models_show_catalog_but_no_synthetic_usage(self):
        for kind in (ReportKind.NORMAL, ReportKind.ALL_MODELS):
            service = compact.CompactReportTests.service(self, SyntheticMonthSource(0, 0, month_start_ms=0),
                                                         availability=compact.Availability(None))
            service.pricing_provider.catalog = catalog()
            report = service.build(ReportRequest(kind))
            self.assertEqual(["Cache heavy", "Input heavy"], [row.model for row in report.model_comparison])
            self.assertTrue(all(row.relative_cost is None for row in report.model_comparison))
            self.assertEqual(0, report.model_comparison_sample_size)
            self.assertEqual(0, report.token_mix.request_count)
            text = compact.rendered(report)
            self.assertIn("Cache heavy", text)
            self.assertIn("Relative CCost stays blank", text)
            self.assertNotIn("Input: 2%", text)


class InstallationEvidenceTests(unittest.TestCase):
    def test_absent_environment_has_no_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(has_opencode_installation_evidence(environment={}, home=Path(directory), platform="test"))

    def test_offline_data_registration_config_and_standard_installs_are_evidence(self):
        for relative in (".local/share/opencode", ".local/state/opencode", ".opencode/bin",
                         ".config/opencode", "local/Programs/OpenCode"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                home = Path(directory)
                (home / relative).mkdir(parents=True)
                self.assertTrue(has_opencode_installation_evidence(
                    environment={"LOCALAPPDATA": str(home / "local")}, home=home, platform="test"))

    def test_explicit_database_and_xdg_locations_are_evidence(self):
        for key, relative in (("OPENCODE_DB", "custom.db"), ("XDG_DATA_HOME", "data/opencode"),
                              ("XDG_STATE_HOME", "state/opencode"), ("XDG_CONFIG_HOME", "config/opencode"),
                              ("APPDATA", "roaming/npm/opencode.cmd")):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                home = Path(directory)
                path = home / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
                location = path if key == "OPENCODE_DB" else home / relative.split("/")[0]
                self.assertTrue(has_opencode_installation_evidence(environment={key: str(location)}, home=home, platform="test"))

    def test_inaccessible_evidence_is_not_claimed_as_absence(self):
        with patch.object(Path, "stat", side_effect=PermissionError):
            self.assertTrue(has_opencode_installation_evidence(environment={}, home=Path("fixture")))

    def test_system_install_locations_are_evidence_without_path_executable(self):
        for platform, installed in (("darwin", "/Applications/OpenCode.app"), ("linux", "/usr/bin/opencode")):
            def stat(path):
                if path == Path(installed):
                    return object()
                raise FileNotFoundError
            with self.subTest(platform=platform), patch.object(Path, "stat", stat):
                self.assertTrue(has_opencode_installation_evidence(environment={}, home=Path("fixture"), platform=platform))


class ReportStartupTests(unittest.TestCase):
    def report_failure(self, executable=None, evidence=False, args=()):
        stream = io.StringIO()
        with patch.object(bootstrap, "load_configuration", return_value=Mock(values={"openCode": {"source": "auto"}})), \
             patch.object(bootstrap, "_select_source", side_effect=SourceUnavailableError("source offline")), \
             patch.object(bootstrap, "StartupProgress"), \
             patch.object(bootstrap.shutil, "which", return_value=executable), \
             patch.object(bootstrap, "has_opencode_installation_evidence", return_value=evidence), \
             patch.object(bootstrap.sys, "stdout", stream):
            code = bootstrap.main(args)
        return code, stream.getvalue()

    def test_report_not_found_only_after_failed_selection_and_no_installation_evidence(self):
        code, text = self.report_failure()
        self.assertEqual(1, code)
        self.assertIn("Cost Guard - OpenCode not found", text)
        self.assertIn("Install OpenCode and start it once", text)

    def test_installed_but_offline_keeps_runtime_error(self):
        for executable, evidence in (("opencode", False), (None, True)):
            code, text = self.report_failure(executable, evidence)
            self.assertEqual(1, code)
            self.assertIn("Runtime error", text)
            self.assertIn("source offline", text)
            self.assertNotIn("not installed", text)
            self.assertNotIn("OpenCode not found", text)

    def test_usable_v1_or_v2_wins_without_a_discoverable_executable(self):
        for generation in ("v1", "v2"):
            healthy = Mock()
            healthy.probe.return_value = SimpleNamespace(healthy=True, available=True)
            healthy.list_sessions.return_value = ()
            missing = Mock()
            missing.probe.return_value = SimpleNamespace(healthy=False, available=False, detail="absent")
            selector = SourceSelector(v1_factory=lambda: healthy if generation == "v1" else missing,
                                      v2_factory=lambda: healthy if generation == "v2" else missing)
            with patch.object(bootstrap, "SourceSelector", return_value=selector), \
                 patch.object(bootstrap.shutil, "which", return_value=None) as which, \
                 patch.object(bootstrap.subprocess, "run") as run:
                self.assertIs(healthy, bootstrap._select_source("auto").source)
                which.assert_not_called()
                run.assert_not_called()

    def test_watch_still_waits_without_installation_check(self):
        with patch.object(bootstrap, "load_configuration", return_value=Mock(values={"openCode": {"source": "auto"}})), \
             patch.object(bootstrap, "_select_source", side_effect=SourceUnavailableError("absent")), \
             patch.object(bootstrap, "_wait_for_watch_source", side_effect=KeyboardInterrupt) as wait, \
             patch.object(bootstrap, "StartupProgress"), patch.object(bootstrap, "WatchRenderer"), \
             patch.object(bootstrap, "has_opencode_installation_evidence") as evidence:
            self.assertEqual(0, bootstrap.main(["--watch"]))
            wait.assert_called_once()
            evidence.assert_not_called()


if __name__ == "__main__":
    unittest.main()
