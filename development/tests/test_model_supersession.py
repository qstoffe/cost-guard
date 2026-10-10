"""Table-local classification and semantic-color attenuation, without pricing changes."""
from __future__ import annotations

from decimal import Decimal
import io
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from src.analysis.comparisons import RelativePriceLevel
from src.config import load_configuration
from src.presentation.model_supersession import model_version, superseded_rows
from src.presentation.fade import faded_style
from src.presentation.report import ReportRenderer
from src.presentation.terminal import AnsiStyler, Column, StyledText, render_table
from src.reports.models import ModelComparisonProjection, ReportKind, ReportProjection

ROOT = Path(__file__).resolve().parents[2]
ANSI = re.compile(r"\x1b\[[0-9;]*m")


class SupersessionTests(unittest.TestCase):
    def test_numeric_versions_and_equal_trailing_zeros(self):
        groups = (("OpenAI", ("GPT-5.6 Sol", "GPT-6 Sol", "GPT-6.1 Sol")),
                  ("Anthropic", ("Claude Opus 4.8", "Claude Opus 5", "Claude Opus 5.5")),
                  ("Google", ("Gemini 3.7 Flash", "Gemini 3.8 Flash")),
                  ("Google", ("Gemini 3.9 Pro", "Gemini 3.10 Pro")),
                  ("xAI", ("Grok 4.5", "Grok 4.6", "Grok 4.7")),
                  ("xAI", ("Grok 4.9", "Grok 4.10")))
        for publisher, names in groups:
            with self.subTest(publisher=publisher):
                self.assertEqual(tuple(range(len(names) - 1)), superseded_rows([(publisher, n) for n in names]))
        self.assertEqual((), superseded_rows([("OpenAI", "GPT-6"), ("OpenAI", "GPT-6.0")]))
        self.assertEqual((0, 1), superseded_rows([("OpenAI", n) for n in ("GPT-6", "GPT-6.0", "GPT-6.0.1")]))

    def test_grok_matching_is_numeric_table_local_and_conservative(self):
        old, new = ("xAI", "Grok 4.6"), ("xAI", "Grok 4.7")
        self.assertEqual((), superseded_rows([old]))
        self.assertEqual((1,), superseded_rows([new, old]))
        self.assertEqual((), superseded_rows([("xAI", "Grok 4"), ("xAI", "Grok 4.0")]))
        self.assertEqual(model_version("xAI", "Grok 4.7"), model_version(" XAI ", " GROK 4.7 "))
        for publisher, name in (
            ("Other", "Grok 5"), ("OpenAI", "Grok 5"), ("xAI", "GPT-5"),
            ("xAI", "Grok 5 Preview"), ("xAI", "Grok 5 Experimental"),
            ("xAI", "Grok 5 Fast"), ("xAI", "Grok 5 Mini"),
            ("xAI", "Grok 5 (fast mode)"), ("xAI", "Grok 5-2026-10-01"),
        ):
            with self.subTest(publisher=publisher, name=name):
                self.assertIsNone(model_version(publisher, name))
                self.assertEqual((), superseded_rows([old, (publisher, name)]))

    def test_grok_screenshot_rows_fade_two_older_versions_not_latest(self):
        items = tuple(ModelComparisonProjection("xAI", name, Decimal("37.5"), "3/0.3/0/15", date,
                                                relative_levels=(RelativePriceLevel(Decimal("37.5")),
                                                                 RelativePriceLevel(Decimal("75.0"), 200000, ">")))
                      for name, date in (("Grok 4.5", "2026-07-08"), ("Grok 4.6", "2026-08-12"),
                                         ("Grok 4.7", "2026-09-21")))
        original = tuple(items)
        config = load_configuration(ROOT).values
        for kind in (ReportKind.NORMAL, ReportKind.ALL_MODELS):
            for scheme in ("classic", "modus-operandi-tinted"):
                values = {**config, "colorScheme": scheme, "colors": config["colorSchemes"][scheme]}
                for width in (80, 120, 200):
                    with self.subTest(kind=kind, scheme=scheme, width=width):
                        report = ReportProjection(kind, "Report", "V2", model_comparison=items)
                        plain, colored = io.StringIO(), io.StringIO()
                        ReportRenderer(values, stream=plain, color_enabled=False, terminal_width=width)._render_model_comparison(report)
                        renderer = ReportRenderer(values, stream=colored, color_enabled=True, terminal_width=width)
                        renderer._render_model_comparison(report)
                        output = colored.getvalue()
                        self.assertEqual(plain.getvalue(), ANSI.sub("", output))
                        for index, item in enumerate(items):
                            line = next(line for line in output.splitlines() if item.model in line)
                            self.assertIn(renderer.styler.apply(item.model, faded=index < 2), line)
                            self.assertIn(renderer.styler.apply(item.publisher, faded=index < 2), line)
                            self.assertIn(renderer.styler.apply(item.release_date, faded=index < 2), line)
                            self.assertIn(renderer.styler.apply("37.5x → 75.0x (>200K)", faded=index < 2), line)
                            if kind is ReportKind.ALL_MODELS:
                                self.assertIn(renderer.styler.apply(item.price_summary, faded=index < 2), line)
                            if index == 2:
                                self.assertNotIn(renderer.styler.apply(item.model, faded=True), line)
                        self.assertLess(output.index("Grok 4.5"), output.index("Grok 4.6"))
                        self.assertLess(output.index("Grok 4.6"), output.index("Grok 4.7"))
        self.assertEqual(original, items)

    def test_named_tiers_and_new_families_are_recognized_generically(self):
        self.assertEqual((0,), superseded_rows([("OpenAI", "GPT-5.6 Luna"), ("OpenAI", "GPT-6 Luna")]))
        self.assertEqual((0,), superseded_rows([("Anthropic", "Claude Fable 5"), ("Anthropic", "Claude Fable 5.1")]))
        self.assertEqual((1,), superseded_rows([("OpenAI", "GPT-6 Codex"), ("OpenAI", "GPT-5.3-Codex")]))
        self.assertEqual((0,), superseded_rows([("Anthropic", "Claude 3.5 Sonnet"), ("Anthropic", "Claude Sonnet 4")]))
        self.assertEqual(model_version("OpenAI", "GPT-6 Luna"), model_version("Open AI", "gpt‑6  \tLUNA"))
        self.assertEqual(model_version("Google", "Gemini 3 Flash Lite"), model_version("Google", "Gemini 3 Flash-Lite"))
        for publisher, name in (("OpenAI", "GPT-6 Luna Preview"), ("OpenAI", "GPT-6 Fast"),
                                ("Anthropic", "Claude Opus 4.8 (fast mode) (preview)"),
                                ("Anthropic", "Claude Fable 5 Experimental"), ("Google", "Gemini 4 Flash Preview"),
                                ("Google", "Gemini 4 Exp"), ("OpenAI", "GPT-6 Luna-2026-10-01"), ("OpenAI", "GPT-4o")):
            with self.subTest(name=name):
                self.assertIsNone(model_version(publisher, name))

    def test_live_catalog_names_fade_every_older_same_variant_row(self):
        rows = [("OpenAI", n) for n in ("GPT-6 Astra", "GPT-5.5", "GPT-5.6 Sol", "GPT-5.4", "GPT-5.6 Terra",
                                        "GPT-6 Sol", "GPT-5.3-Codex", "GPT-6.1 Sol", "GPT-5.4 mini", "GPT-5 mini",
                                        "GPT-5.6 Luna", "GPT-5.4 nano", "GPT-6 Luna")]
        rows += [("Anthropic", n) for n in ("Claude Fable 5", "Claude Opus 4.8 (fast mode) (preview)", "Claude Fable 5.1",
                                            "Claude Opus 4.8", "Claude Opus 5", "Claude Sonnet 4", "Claude Sonnet 4.6",
                                            "Claude Opus 5.5", "Claude Sonnet 5", "Claude Sonnet 5.5",
                                            "Claude Haiku 4.5", "Claude Haiku 5.5")]
        faded = {rows[index][1] for index in superseded_rows(rows)}
        self.assertEqual({"GPT-5.4", "GPT-5.6 Sol", "GPT-6 Sol", "GPT-5 mini", "GPT-5.6 Luna",
                          "Claude Fable 5", "Claude Opus 4.8", "Claude Opus 5", "Claude Sonnet 4",
                          "Claude Sonnet 4.6", "Claude Sonnet 5", "Claude Haiku 4.5"}, faded)

    def test_families_variants_channels_and_publishers_remain_separate(self):
        rows = [("Anthropic", "Claude Opus 4"), ("Anthropic", "Claude Sonnet 5"),
                ("Google", "Gemini 3 Flash"), ("Google", "Gemini 4 Pro"),
                ("OpenAI", "GPT-5 Sol"), ("OpenAI", "GPT-6 Mini"),
                ("OpenAI", "GPT-7 Sol (fast mode)"), ("OpenAI", "GPT-8 Sol Preview"),
                ("OpenAI", "GPT-9 Sol Experimental"), ("Other", "GPT-10 Sol"),
                ("OpenAI", "GPT-11 Mystery"), ("OpenAI", "GPT-13 Luna"), ("Other", "Version 3.10"),
                ("Anthropic", "GPT-12 Sol"), ("Google", "Gemini 3 Flash Lite")]
        self.assertEqual((), superseded_rows(rows))
        self.assertIsNone(model_version("Other", "Version 3.9"))

    def test_only_displayed_models_count_even_after_availability_filtering(self):
        old, newer = ("OpenAI", "GPT-6 Sol"), ("OpenAI", "GPT-6.1 Sol")
        self.assertEqual((), superseded_rows([old]))
        self.assertEqual((0,), superseded_rows([old, newer]))

    def test_row_modifier_keeps_segments_and_separators_independent(self):
        colors = {"promotion": {"ansi256": 214}, "new": {"ansi256": 118}}
        styler = AnsiStyler(colors, enabled=True)
        rows = [("Google", StyledText((("*2 ", "promotion"), ("2.5x", None))), "2026-10-01")]
        columns = (Column("Publisher"), Column("Relative"), Column("Released"))
        faded = render_table(columns, rows, styles=[(None, None, "new")], styler=styler, faded_rows=(0,))
        plain = render_table(columns, rows)
        self.assertEqual(plain, [ANSI.sub("", line) for line in faded])
        self.assertEqual(plain[:3], faded[:3])
        self.assertEqual(plain[-1], faded[-1])
        self.assertIn(styler.apply("*2 ", "promotion", faded=True), faded[3])
        self.assertIn(styler.apply("2.5x", faded=True), faded[3])
        self.assertIn(styler.apply("2026-10-01", "new", faded=True), faded[3])
        self.assertNotIn("\x1b[0m|", faded[3])

    def test_dark_light_custom_colors_and_backgrounds_are_derived(self):
        for scheme in ("classic", "modus-operandi-tinted"):
            config = load_configuration(ROOT).values
            colors = config["colorSchemes"][scheme]
            styler = AnsiStyler(colors, enabled=True, light_theme=scheme != "classic")
            sequences = [styler.apply("cell", role, faded=True) for role in (None, "modelComparisonPromotion", "modelComparisonNew")]
            self.assertEqual(3, len(set(sequences)))
            for role in ("modelComparisonPromotion", "modelComparisonNew"):
                self.assertNotEqual(styler.apply("cell", role), styler.apply("cell", role, faded=True))
        style = {"foreground": "Cyan", "background": "Black", "ansi256": None}
        faded = faded_style(style, light=False)
        self.assertEqual("Black", faded["background"])
        self.assertIsNotNone(faded["ansi256"])
        self.assertNotEqual(faded_style({"ansi256": 214}, light=False), faded_style({"ansi256": 45}, light=False))
        self.assertEqual("cell", AnsiStyler({}, enabled=False).apply("cell", faded=True))

    def test_full_rows_promotions_and_geometry_with_no_semantic_mutation(self):
        items = tuple(ModelComparisonProjection("Google", name, Decimal(cost), "0.1/0.01/0/0.3", "2026-10-01",
                                                promotional=True, recent=True, promotion_marker=index + 1)
                      for index, (name, cost) in enumerate((("Gemini 3.8 Flash", "2.0"), ("Gemini 3.7 Flash", "2.5"))))
        original = tuple(items)
        config = load_configuration(ROOT).values
        for kind in (ReportKind.NORMAL, ReportKind.ALL_MODELS):
            for width in (80, 120, 200):
                report = ReportProjection(kind, "Report", "V2", model_comparison=items)
                outputs = []
                for enabled in (False, True):
                    stream = io.StringIO()
                    renderer = ReportRenderer(config, stream=stream, color_enabled=enabled, terminal_width=width)
                    renderer._render_model_comparison(report)
                    outputs.append(stream.getvalue())
                self.assertEqual(outputs[0], ANSI.sub("", outputs[1]))
                styler = renderer.styler
                old = next(line for line in outputs[1].splitlines() if "*2" in line)
                new = next(line for line in outputs[1].splitlines() if "*1" in line)
                self.assertIn(styler._sequence(faded_style(config["colors"]["modelComparisonPromotion"], light=False)), old)
                self.assertIn(styler._sequence(config["colors"]["modelComparisonPromotion"]), new)
                self.assertEqual(4 if kind is ReportKind.NORMAL else 5, old.count("\x1b[0m"))
                # Turning classification off leaves identical plain information/order.
                stream = io.StringIO()
                with patch("src.presentation.report.superseded_rows", return_value=()):
                    ReportRenderer(config, stream=stream, color_enabled=False, terminal_width=width)._render_model_comparison(report)
                self.assertEqual(outputs[0], stream.getvalue())
        self.assertEqual(original, items)

    def test_redirected_output_and_no_color_are_unchanged(self):
        with patch("sys.stdout", io.StringIO()):
            self.assertFalse(AnsiStyler({}).enabled)
        with patch.dict("os.environ", {"NO_COLOR": "1"}), patch("sys.stdout.isatty", return_value=True):
            self.assertFalse(AnsiStyler({}).enabled)


if __name__ == "__main__":
    unittest.main()
