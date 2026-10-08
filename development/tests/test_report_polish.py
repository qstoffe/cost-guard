"""Composed one-shot layout, independent model styles and word-aware prose."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import io
import re
import unittest

from development.tests.test_quota_presentation import quotas, rolling
from src.presentation import ReportRenderer
from src.reports.models import (
    ModelComparisonProjection, PromptProjection,
    ReportKind, ReportProjection, SessionPromptBlock,
)
from src.reports.semantics import model_is_recent

NOW = int(datetime(2026, 9, 30, tzinfo=timezone.utc).timestamp() * 1000)
CONFIG = {"timezone": "UTC", "colors": {"modelComparisonPromotion": {"ansi256": 214}, "modelComparisonNew": {"ansi256": 118}}}
NOTE = "CCost is reference valuation, not billing; account CCost is shown only when usage attribution is proven."


def sample_report():
    prompt = PromptProjection(1, 1, "Prompt", "Example", "Test", Decimal("1"), False,
                              False, 1, 1000, Decimal("0.01"), None, (100, 0, 0, 0))
    block = SessionPromptBlock("ses_test", "Example", (prompt,), Decimal("1"), 1)
    return ReportProjection(
        ReportKind.NORMAL, "Report", "V2", source_warnings=("Synthetic warning",),
        model_comparison=(ModelComparisonProjection("OpenAI", "Test", Decimal("1"), "1/1/1/1", "2026-09-29"),),
        prompt_blocks=(block, replace(block, session_id="ses_second")),
        accounts_quotas=quotas(rolling()), notes=("Synthetic footer note",),
    )


def render(report, *, width=80, color=False, header=True):
    stream = io.StringIO()
    ReportRenderer(CONFIG, stream=stream, terminal_width=width, color_enabled=color).render(
        report, include_header=header)
    return stream.getvalue()


class SectionLayoutTests(unittest.TestCase):
    def assert_boundaries(self, text, headings, width):
        lines = text.splitlines()
        actual = [line for line in lines if line.startswith("## ")]
        self.assertEqual(headings, actual)
        for heading in headings:
            index = lines.index(heading)
            self.assertEqual(["", ""], lines[index - 2:index], heading)
            if index > 2:
                self.assertNotEqual("", lines[index - 3], heading)
            self.assertEqual("-" * width, lines[index + 1], heading)
            self.assertEqual("", lines[index + 2], heading)
            self.assertNotEqual("", lines[index + 3], heading)

    def test_complete_normal_report_including_empty_sections(self):
        populated = sample_report()
        empty = replace(populated, model_comparison=(), prompt_blocks=(), accounts_quotas=quotas())
        headings = []
        for report in (populated, empty):
            for width in (80, 120):
                for header in (False, True):
                    with self.subTest(populated=bool(report.prompt_blocks), width=width, header=header):
                        self.assert_boundaries(render(report, width=width, header=header), headings, width)

    def test_session_and_date_modes_use_same_major_section_contract(self):
        for kind in (ReportKind.SESSION, ReportKind.DATE):
            for blocks in (sample_report().prompt_blocks, ()):
                with self.subTest(kind=kind, empty=not blocks):
                    report = replace(sample_report(), kind=kind, prompt_blocks=blocks)
                    self.assert_boundaries(render(report), ["## User prompts"], 80)

    def test_omitted_account_section_and_reused_renderer_keep_boundaries(self):
        report = replace(sample_report(), accounts_quotas=None)
        stream = io.StringIO()
        renderer = ReportRenderer(CONFIG, stream=stream, terminal_width=80, color_enabled=False)
        renderer.render(report)
        renderer.render(sample_report())
        chunks = stream.getvalue().split("# Cost Guard ")[1:]
        self.assertEqual(2, len(chunks))
        for chunk in chunks:
            headings = [line for line in chunk.splitlines() if line.startswith("## ")]
            self.assert_boundaries(chunk, headings, 80)


class RecentModelTests(unittest.TestCase):
    def test_recent_name_date_and_independent_promotion_styles(self):
        rows = []
        cases = (("Recent", "2026-09-29", False), ("Recent promo", "2026-09-29", True),
                 ("Old", "2026-09-23", False), ("Old promo", "2026-09-23", True),
                 ("Future", "2026-10-01", False), ("Unknown", None, False))
        for name, released, promo in cases:
            rows.append(ModelComparisonProjection("OpenAI", name, Decimal("2"), "1/1/1/1", released,
                                                  promotional=promo, recent=model_is_recent(released, now_ms=NOW)))
        notice = "✦ New Models: Recent (2026-09-29), Recent promo (2026-09-29)"
        text = render(replace(sample_report(), model_comparison=tuple(rows), recent_model_notice=notice),
                      color=True, width=160)
        for item in rows:
            line = next(line for line in text.splitlines() if line.startswith("|") and item.model in line
                        and re.sub(r"\x1b\[[0-9;]*m", "", line.split("|")[2]).strip() == item.model)
            cells = line.split("|")[1:-1]
            self.assertEqual(item.recent, "\x1b[38;5;118m" in cells[1], item.model)
            self.assertEqual(item.recent, "\x1b[38;5;118m" in cells[4], item.model)
            for index in (2, 3):
                self.assertEqual(item.promotional, "\x1b[38;5;214m" in cells[index], item.model)
        self.assertIn(notice, re.sub(r"\x1b\[[0-9;]*m", "", text))
        self.assertIn("\x1b[38;5;118m✦ New Models:\x1b[0m Recent", text)


class NoteWrappingTests(unittest.TestCase):
    def test_word_boundaries_hanging_indent_and_wide_single_line(self):
        from src.presentation.terminal import wrap_prose

        lines = wrap_prose(NOTE, 72, initial_prefix="* ", continuation_prefix="  ")
        self.assertGreater(len(lines), 1)
        self.assertTrue(lines[0].startswith("* "))
        self.assertTrue(all(line.startswith("  ") and not line.lstrip().startswith("*") for line in lines[1:]))
        self.assertTrue(all(len(line) <= 72 for line in lines))
        self.assertEqual(NOTE, " ".join(line[2:] for line in lines))
        self.assertEqual(["* " + NOTE], wrap_prose(NOTE, 200, initial_prefix="* ", continuation_prefix="  "))

    def test_narrow_widths_and_unbreakable_tokens_never_split_words(self):
        from src.presentation.terminal import wrap_prose

        text = "Keep YYYY-MM-DD:YYYY-MM-DD and attribution intact."
        for width in (1, 2, 3, 12, 24):
            with self.subTest(width=width):
                lines = wrap_prose(text, width, initial_prefix="* ", continuation_prefix="  ")
                self.assertEqual(text, " ".join(line[2:] for line in lines))

    def test_complete_report_wraps_account_note_and_other_long_prose(self):
        report = replace(sample_report(), notes=(NOTE,),
                         model_comparison_promotion_notes=("*1 Promo: " + NOTE,))
        text = render(report, width=72)
        lines = text.splitlines()
        note_start = lines.index("* CCost is reference valuation, not billing; account CCost is shown only")
        self.assertEqual("  when usage attribution is proven.", lines[note_start + 1])
        self.assertNotIn("quota visibility alone", text)
        for line in lines:
            if line and not line.startswith(("|", "#", "  5h", "  Week")):
                self.assertLessEqual(len(line), 72, line)
        # Colored promotion text is wrapped before ANSI styling, with numbered hanging indentation.
        colored = render(report, width=72, color=True)
        plain = re.sub(r"\x1b\[[0-9;]*m", "", colored)
        self.assertEqual(text, plain)
        promo_index = lines.index("*1 Promo: CCost is reference valuation, not billing; account CCost is")
        self.assertTrue(lines[promo_index + 1].startswith("   "))


if __name__ == "__main__":
    unittest.main()
