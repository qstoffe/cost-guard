from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from src.config import ConfigError, load_configuration, merge_config, read_jsonc, remove_json_comments

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "development/fixtures/config"


def make_package(tmp: str, fixture: str | None = None) -> Path:
    package = Path(tmp) / "package"
    package.mkdir()
    (package / "config").mkdir()
    shutil.copy2(ROOT / "config/default-config.jsonc", package / "config/default-config.jsonc")
    if fixture:
        shutil.copy2(FIXTURES / fixture, package / "config/user-config.jsonc")
    return package


class JsoncTests(unittest.TestCase):
    def test_comment_removal_preserves_markers_inside_strings(self) -> None:
        text = r'''{
          // comment
          "url": "https://example.test/a/*not-comment*/?x=//ok",
          "value": 3 /* block */
        }'''
        stripped = remove_json_comments(text)
        self.assertIn("https://example.test/a/*not-comment*/?x=//ok", stripped)
        self.assertNotIn("// comment", stripped)
        self.assertNotIn("/* block */", stripped)

    def test_merge_preserves_explicit_null_and_inherits_omitted_values(self) -> None:
        defaults = {"a": {"one": 1, "two": 2}, "b": 3}
        merged = merge_config(defaults, {"a": {"one": None}})
        self.assertEqual({"a": {"one": None, "two": 2}, "b": 3}, merged)


class ConfigurationCompatibilityTests(unittest.TestCase):
    def test_default_config_loads_without_creating_user_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = make_package(tmp)
            config = load_configuration(package)
            self.assertFalse(config.user_config_present)
            self.assertFalse((package / "config/user-config.jsonc").exists())
            self.assertEqual("auto", config.open_code_source)
            self.assertEqual("classic", config.values["colorScheme"])

    def test_partial_v77_style_override_merges_and_source_is_canonicalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = make_package(tmp, "partial-user.jsonc")
            config = load_configuration(package)
            self.assertTrue(config.user_config_present)
            self.assertEqual("v2", config.open_code_source)
            self.assertFalse(config.values["copilotQuota"]["enabled"])
            self.assertEqual(70, config.values["thresholds"]["promptCostP75"])
            style = config.values["colors"]["watchSummary"]
            self.assertEqual("Cyan", style["foreground"])
            self.assertIsNone(style["background"])

    def test_explicit_null_color_semantics_match_v77(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = make_package(tmp, "explicit-null-user.jsonc")
            config = load_configuration(package)
            self.assertIsNone(config.values["colors"]["watchSummary"])
            summary_cost = config.values["colors"]["watchSummaryCost"]
            self.assertEqual("Cyan", summary_cost["foreground"])
            self.assertIsNone(summary_cost["background"])

    def test_legacy_pricing_days_converts_to_hours(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = make_package(tmp, "legacy-pricing-user.jsonc")
            config = load_configuration(package)
            self.assertEqual(48.0, config.values["pricingMaxAgeHours"])

    def test_current_pricing_hours_wins_over_legacy_days(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = make_package(tmp)
            (package / "config/user-config.jsonc").write_text(
                '{"pricingMaxAgeDays": 9, "pricingMaxAgeHours": 5}', encoding="utf-8"
            )
            config = load_configuration(package)
            self.assertEqual(5, config.values["pricingMaxAgeHours"])

    def test_unknown_user_setting_fails_closed_without_echoing_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = make_package(tmp, "invalid-unknown-user.jsonc")
            with self.assertRaises(ConfigError) as caught:
                load_configuration(package)
            message = str(caught.exception)
            self.assertIn("Setting: notARealSetting", message)
            self.assertIn("(omitted for security)", message)

    def test_invalid_source_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = make_package(tmp)
            (package / "config/user-config.jsonc").write_text(
                '{"openCode": {"source": "mixed"}}', encoding="utf-8"
            )
            with self.assertRaises(ConfigError) as caught:
                load_configuration(package)
            self.assertIn("Setting: openCode.source", str(caught.exception))

    def test_malformed_jsonc_error_does_not_echo_parser_excerpt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config/user-config.jsonc"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"auth": "secret-value",', encoding="utf-8")
            with self.assertRaises(ConfigError) as caught:
                read_jsonc(path)
            self.assertNotIn("secret-value", str(caught.exception))
            self.assertIn("Invalid JSONC", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
