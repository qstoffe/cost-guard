from __future__ import annotations

import io
import re
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from development.tests.test_analysis_core import make_snapshot
from development.tests.test_v786_regressions import _threshold_catalog
from src.analysis.context import PriceWarningSeverity, next_context_warning_state
from src.analysis.core import analyze_snapshot
from src.config import load_configuration
from src.domain import TokenUsage
from src.presentation import ReportRenderer, WatchRenderer
from src.presentation.context_warnings import warning_explanation_lines
from src.presentation.terminal import AnsiStyler
from src.reports.models import PromptProjection, ReportKind, ReportProjection, SessionPromptBlock
from src.reports.prompts import build_prompt_block
from src.watch.coordinator import WatchCoordinator
from src.watch.models import WatchProjection, WatchRow


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def prompt(severity: PriceWarningSeverity, text: str = "Localized economic warning") -> PromptProjection:
    tokens = 80_000 if severity == PriceWarningSeverity.APPROACHING else 120_000
    return PromptProjection(
        at_ms=2_000, prompt_number=1, label="prompt", preview="Normal prompt", model_effort="Test (Default)",
        ccost=Decimal("12"), cost_estimated=False, unresolved_cost=False, calls=1,
        incoming_context_tokens=76_000, incoming_context_ccost=Decimal("1"), extra_ccost=Decimal("11"),
        token_mix_percent=(90, 0, 0, 10), delta_context_tokens=4_000, next_context_tokens=tokens,
        next_context_warning=text, next_context_warning_severity=severity,
        watch_delta_context_tokens=4_000, watch_next_context_tokens=tokens,
        watch_next_context_warning=text, watch_next_context_warning_severity=severity,
        watch_next_context_cached_ccost=Decimal("1"), watch_next_context_fresh_ccost=Decimal("12"),
    )


def watch_projection(item: PromptProjection, title: str = "Normal session") -> WatchProjection:
    return WatchProjection("Cost Guard Watch", "V2", (WatchRow("root", title, item),),
                           session_warnings={"root": item.watch_next_context_warning})


def report_projection(item: PromptProjection, kind: ReportKind = ReportKind.SESSION) -> ReportProjection:
    block = SessionPromptBlock(
        "root", "Normal session", (item,), item.ccost, item.calls,
        next_context_tokens=item.next_context_tokens, next_context_warning=item.next_context_warning,
        next_context_warning_severity=item.next_context_warning_severity,
    )
    return ReportProjection(kind, "Test report", "V2", prompt_blocks=(block,))


class ContextWarningPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_configuration(Path(__file__).resolve().parents[2]).values

    def styles(self, config=None):
        return AnsiStyler((config or self.config)["colors"], enabled=True)

    def watch(self, projection, *, colored=True, config=None):
        stream = io.StringIO()
        WatchRenderer(config or self.config, stream=stream, interactive=colored).render(projection)
        return stream.getvalue()

    def report(self, projection, *, colored=True, width=160, config=None):
        stream = io.StringIO()
        ReportRenderer(config or self.config, stream=stream, color_enabled=colored, terminal_width=width).render(projection)
        return stream.getvalue()

    def test_watch_both_states_color_only_marker_and_next_value_in_table(self):
        styler = self.styles()
        for severity in (PriceWarningSeverity.APPROACHING, PriceWarningSeverity.EXCEEDED):
            with self.subTest(severity=severity):
                item = prompt(severity)
                text = self.watch(watch_projection(item))
                header = next(line for line in text.splitlines() if "Normal session" in line)
                self.assertIn(styler.apply("*1", "nextIctxWarning"), header)
                row = next(line for line in text.splitlines() if "Normal prompt" in line)
                self.assertIn(styler.apply(f"{'~' + str(item.watch_next_context_tokens // 1000) + 'k':>8}", "nextIctxWarning"), row)
                self.assertEqual(1, row.count("\x1b[0m"), "only the Next Ictx segment should be styled")
                self.assertNotIn("\x1b[91m", row)
                self.assertIn("+4k →", ANSI.sub("", row))

    def test_watch_approaching_marker_only_exceeded_full_explanation(self):
        styler = self.styles()
        for severity in (PriceWarningSeverity.APPROACHING, PriceWarningSeverity.EXCEEDED):
            text = self.watch(watch_projection(prompt(severity)))
            line = next(line for line in text.splitlines() if "*1" in line and "Next Ictx:" in line)
            plain = ANSI.sub("", line)
            expected = (styler.apply(plain, "nextIctxWarning") if severity == PriceWarningSeverity.EXCEEDED
                        else styler.apply("*1", "nextIctxWarning") + plain[2:])
            self.assertEqual(expected, line)

    def test_report_both_states_color_marker_and_next_indicator(self):
        styler = self.styles()
        for kind in (ReportKind.SESSION, ReportKind.DATE):
            for severity in (PriceWarningSeverity.APPROACHING, PriceWarningSeverity.EXCEEDED):
                with self.subTest(kind=kind, severity=severity):
                    item = prompt(severity)
                    text = self.report(report_projection(item, kind))
                    header = next(line for line in text.splitlines() if "Normal session" in line)
                    self.assertIn(styler.apply("*1", "nextIctxWarning"), header)
                    self.assertEqual(1, header.count("\x1b[0m"))
                    row = next(line for line in text.splitlines() if "Normal prompt" in line)
                    self.assertIn(styler.apply(f"{item.next_context_tokens // 1000}k", "nextIctxWarning"), row)
                    self.assertEqual(1, row.count("\x1b[0m"))
                    indicator = next(line for line in text.splitlines() if "* Next Ictx:" in line)
                    self.assertEqual(styler.apply(ANSI.sub("", indicator), "nextIctxWarning"), indicator)

    def test_compact_normal_report_still_omits_context_details(self):
        text = self.report(report_projection(prompt(PriceWarningSeverity.EXCEEDED), ReportKind.NORMAL))
        self.assertNotIn("Next Ictx:", text)
        self.assertNotIn("Localized economic warning", text)

    def test_report_marker_only_vs_full_explanation_including_wrapping(self):
        styler = self.styles()
        for severity in (PriceWarningSeverity.APPROACHING, PriceWarningSeverity.EXCEEDED):
            message = "Localized economic warning " + "explanation " * 12
            text = self.report(report_projection(prompt(severity, message)), width=80)
            lines = text.splitlines()
            index = next(i for i, line in enumerate(lines) if "*1" in line and "Localized" in line)
            wrapped = warning_explanation_lines("*1", message, severity, styler, width=80)
            self.assertEqual(wrapped, lines[index:index + len(wrapped)])
            self.assertGreater(len(wrapped), 1)
            if severity == PriceWarningSeverity.APPROACHING:
                self.assertEqual(styler.apply("*1", "nextIctxWarning") + ANSI.sub("", wrapped[0])[2:], wrapped[0])
                self.assertTrue(all("\x1b" not in line for line in wrapped[1:]))
            else:
                self.assertTrue(all(line == styler.apply(ANSI.sub("", line), "nextIctxWarning") for line in wrapped))

    def test_prose_cannot_override_structured_severity(self):
        styler = self.styles()
        for severity, message in ((PriceWarningSeverity.APPROACHING, "exceeded is not machine evidence"),
                                  (PriceWarningSeverity.EXCEEDED, "Approaching is not machine evidence")):
            item = prompt(severity, message)
            watch = self.watch(watch_projection(item))
            report = self.report(report_projection(item))
            for text in (watch, report):
                line = next(line for line in text.splitlines() if "*1" in line and message in line)
                plain = ANSI.sub("", line)
                expected = (styler.apply(plain, "nextIctxWarning") if severity == PriceWarningSeverity.EXCEEDED
                            else styler.apply("*1", "nextIctxWarning") + plain[2:])
                self.assertEqual(expected, line)

    def test_no_warning_redirected_output_and_long_title_marker(self):
        item = replace(prompt(PriceWarningSeverity.NONE, ""), watch_next_context_warning="")
        projection = replace(watch_projection(item), session_warnings={})
        self.assertNotIn("\x1b[38;5;172m", self.watch(projection))
        self.assertNotIn("*1", self.report(report_projection(item)))
        item = prompt(PriceWarningSeverity.EXCEEDED)
        title = "Long session title " * 8
        self.assertIn(self.styles().apply("*1", "nextIctxWarning"), self.watch(watch_projection(item, title)))
        self.assertNotIn("\x1b", self.watch(watch_projection(item), colored=False))
        self.assertNotIn("\x1b", self.report(report_projection(item), colored=False))

    def test_watch_expiry_live_none_and_report_fallback_share_state_selection(self):
        item = prompt(PriceWarningSeverity.EXCEEDED)
        historical = WatchRow("root", "title", item, is_latest_session_event=False)
        self.assertEqual("", historical.next_context_warning)
        self.assertEqual(PriceWarningSeverity.NONE, historical.next_context_warning_severity)
        reduced = replace(item, watch_next_context_tokens=20_000, watch_next_context_warning="",
                          watch_next_context_warning_severity=PriceWarningSeverity.NONE)
        self.assertEqual(PriceWarningSeverity.NONE, WatchRow("root", "title", reduced).next_context_warning_severity)
        fallback = replace(item, watch_next_context_tokens=None, watch_next_context_warning="",
                           watch_next_context_warning_severity=PriceWarningSeverity.NONE)
        self.assertEqual(PriceWarningSeverity.EXCEEDED, WatchRow("root", "title", fallback).next_context_warning_severity)

    def test_structured_severity_change_requires_full_watch_repaint(self):
        original = watch_projection(prompt(PriceWarningSeverity.APPROACHING))
        changed = replace(original, rows=(replace(original.rows[0], prompt=replace(original.rows[0].prompt,
                          watch_next_context_warning_severity=PriceWarningSeverity.EXCEEDED)),))
        self.assertNotEqual(WatchCoordinator._visible_signature(original), WatchCoordinator._visible_signature(changed))

    def test_unrelated_failure_and_abort_row_styles_remain_critical(self):
        renderer = WatchRenderer(self.config, stream=io.StringIO(), interactive=True)
        item = prompt(PriceWarningSeverity.EXCEEDED)
        for failed in (replace(item, watch_error=True), replace(item, aborted=True)):
            row = WatchRow("root", "title", failed, marker="!")
            self.assertEqual("costQuotaCritical", renderer._row_style(row))
            output = self.watch(replace(watch_projection(failed), rows=(row,)))
            self.assertIn(self.styles().apply("X", "costQuotaCritical").split("X")[0], output)

    def test_both_palette_defaults_use_same_non_red_warning_role(self):
        for palette in self.config["colorSchemes"].values():
            self.assertEqual(palette["nextIctxWarning"], palette["nextIctxWarningReason"])
            self.assertNotIn(palette["nextIctxWarning"]["foreground"], ("Red", "DarkRed"))


class StructuredPriceWarningTests(unittest.TestCase):
    def test_threshold_boundary_and_custom_trigger_are_unchanged(self):
        catalog = _threshold_catalog()
        for tokens, severity in ((0, PriceWarningSeverity.NONE), (75_000, PriceWarningSeverity.NONE),
                                 (75_001, PriceWarningSeverity.APPROACHING), (100_000, PriceWarningSeverity.APPROACHING),
                                 (100_001, PriceWarningSeverity.EXCEEDED)):
            state = next_context_warning_state(tokens=tokens, model_id="gpt-test", catalog=catalog)
            self.assertEqual(severity, state.price_severity)
            self.assertEqual(severity == PriceWarningSeverity.EXCEEDED, state.hard_warning)
        self.assertEqual(PriceWarningSeverity.NONE, next_context_warning_state(
            tokens=80_000, model_id="gpt-test", catalog=catalog, price_approach_percent=90).price_severity)
        self.assertEqual(PriceWarningSeverity.EXCEEDED, next_context_warning_state(
            tokens=100_001, model_id="gpt-test", catalog=catalog, price_approach_percent=0).price_severity)

    def test_analysis_severity_survives_report_and_watch_projection(self):
        for tokens, severity in ((20_000, PriceWarningSeverity.NONE), (80_000, PriceWarningSeverity.APPROACHING),
                                 (120_000, PriceWarningSeverity.EXCEEDED)):
            with self.subTest(tokens=tokens):
                snapshot = make_snapshot()
                messages = tuple(item for item in snapshot.messages if item.message_id not in {"u_comp", "a_comp"})
                invocations = tuple(replace(item, tokens=TokenUsage(input=tokens, output=4))
                                    if item.invocation_id == "i_next" else item
                                    for item in snapshot.invocations if item.invocation_id != "i_comp")
                snapshot = replace(snapshot, messages=messages, parts=tuple(p for m in messages for p in m.parts),
                                   events=tuple(e for e in snapshot.events if e.event_id != "u_comp"), invocations=invocations)
                block = build_prompt_block(session_id="root", title="Test", bundle=analyze_snapshot(snapshot, now_ms=4000),
                                           snapshot=snapshot, catalog=_threshold_catalog(), config={})
                item = next(row for row in block.rows if row.event_id == "u_next")
                self.assertEqual(severity, item.next_context_warning_severity)
                self.assertEqual(severity, item.watch_next_context_warning_severity)
                self.assertEqual(severity, block.next_context_warning_severity)
                self.assertEqual(severity, WatchRow("root", "Test", item).next_context_warning_severity)


if __name__ == "__main__":
    unittest.main()
