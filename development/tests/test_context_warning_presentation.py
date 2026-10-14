from __future__ import annotations

import io
import re
import unittest
from dataclasses import replace
from pathlib import Path

from development.fixtures.pricing_catalog import threshold_catalog
from development.fixtures.session_snapshots import make_uncompacted_snapshot
from development.fixtures.warning_projections import warning_prompt, warning_report_projection, warning_watch_projection
from src.analysis.context import PriceWarningSeverity, next_context_warning_state
from src.analysis.core import analyze_snapshot
from src.config import load_configuration
from src.domain import TokenUsage
from src.presentation import ReportRenderer, WatchRenderer
from src.presentation.watch import _fit_model_effort
from src.presentation.context_warnings import warning_explanation_lines
from src.presentation.terminal import AnsiStyler
from src.reports.models import ReportKind
from src.reports.prompts import build_prompt_block
from src.watch.coordinator import WatchCoordinator
from src.watch.models import WatchProjection, WatchRow


ANSI = re.compile(r"\x1b\[[0-9;]*m")


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
                item = warning_prompt(severity)
                text = self.watch(warning_watch_projection(item))
                header = next(line for line in text.splitlines() if "Normal session" in line)
                self.assertNotIn("*1", header)
                row = next(line for line in text.splitlines() if "Normal prompt" in line)
                self.assertIn(styler.apply("Test (Default)", "nextIctxWarning"), row)
                self.assertIn(styler.apply("*1", "nextIctxWarning"), row)
                self.assertIn(styler.apply(f"{'~' + str(item.watch_next_context_tokens // 1000) + 'k':>8}", "nextIctxWarning"), row)
                self.assertEqual(3, row.count("\x1b[0m"), "Model, marker and Next Ictx are styled independently")
                self.assertNotIn("\x1b[91m", row)
                self.assertIn("+4k →", ANSI.sub("", row))

    def test_watch_approaching_marker_only_exceeded_full_explanation(self):
        styler = self.styles()
        for severity in (PriceWarningSeverity.APPROACHING, PriceWarningSeverity.EXCEEDED):
            text = self.watch(warning_watch_projection(warning_prompt(severity)))
            line = next(line for line in text.splitlines() if "*1" in line and "Context:" in line)
            plain = ANSI.sub("", line)
            expected = (styler.apply(plain, "nextIctxWarning") if severity == PriceWarningSeverity.EXCEEDED
                        else styler.apply("*1", "nextIctxWarning") + plain[2:])
            self.assertEqual(expected, line)

    def test_report_both_states_color_marker_and_next_indicator(self):
        styler = self.styles()
        for kind in (ReportKind.SESSION, ReportKind.DATE):
            for severity in (PriceWarningSeverity.APPROACHING, PriceWarningSeverity.EXCEEDED):
                with self.subTest(kind=kind, severity=severity):
                    item = warning_prompt(severity)
                    text = self.report(warning_report_projection(item, kind))
                    header = next(line for line in text.splitlines() if "Normal session" in line)
                    self.assertIn(styler.apply("*1", "nextIctxWarning"), header)
                    self.assertEqual(1, header.count("\x1b[0m"))
                    row = next(line for line in text.splitlines() if "Normal prompt" in line)
                    self.assertIn(styler.apply(f"{item.next_context_tokens // 1000}k", "nextIctxWarning"), row)
                    self.assertEqual(1, row.count("\x1b[0m"))
                    indicator = next(line for line in text.splitlines() if "* Next Ictx:" in line)
                    self.assertEqual(styler.apply(ANSI.sub("", indicator), "nextIctxWarning"), indicator)

    def test_compact_normal_report_still_omits_context_details(self):
        text = self.report(warning_report_projection(warning_prompt(PriceWarningSeverity.EXCEEDED), ReportKind.NORMAL))
        self.assertNotIn("Next Ictx:", text)
        self.assertNotIn("Localized economic warning", text)

    def test_price_warning_uses_context_label_but_next_input_indicator_is_unchanged(self):
        item = warning_prompt(PriceWarningSeverity.EXCEEDED, "[Price threshold >200.0K exceeded]")

        watch = self.watch(warning_watch_projection(item), colored=False)
        report = self.report(warning_report_projection(item), colored=False)

        self.assertIn("Context: Price threshold >200.0K exceeded", watch)
        self.assertIn("Context: Price threshold >200.0K exceeded", report)
        self.assertNotIn("Next Ictx: Price threshold", watch + report)
        self.assertIn("Next Ictx: ~", report)

    def test_report_marker_only_vs_full_explanation_including_wrapping(self):
        styler = self.styles()
        for severity in (PriceWarningSeverity.APPROACHING, PriceWarningSeverity.EXCEEDED):
            message = "Localized economic warning " + "explanation " * 12
            text = self.report(warning_report_projection(warning_prompt(severity, message)), width=80)
            lines = text.splitlines()
            index = next(i for i, line in enumerate(lines) if "*1" in line and "Localized" in line)
            wrapped = warning_explanation_lines("*1", f"Context: {message}", severity, styler, width=80)
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
            item = warning_prompt(severity, message)
            watch = self.watch(warning_watch_projection(item))
            report = self.report(warning_report_projection(item))
            for text in (watch, report):
                line = next(line for line in text.splitlines() if "*1" in line and message in line)
                plain = ANSI.sub("", line)
                expected = (styler.apply(plain, "nextIctxWarning") if severity == PriceWarningSeverity.EXCEEDED
                            else styler.apply("*1", "nextIctxWarning") + plain[2:])
                self.assertEqual(expected, line)

    def test_no_warning_redirected_output_and_long_title_marker(self):
        item = replace(warning_prompt(PriceWarningSeverity.NONE, ""), watch_next_context_warning="")
        projection = replace(warning_watch_projection(item), session_warnings={})
        self.assertNotIn("\x1b[38;5;172m", self.watch(projection))
        self.assertNotIn("*1", self.watch(projection))
        self.assertNotIn("*1", self.report(warning_report_projection(item)))
        item = warning_prompt(PriceWarningSeverity.EXCEEDED)
        title = "Long session title " * 8
        output = self.watch(warning_watch_projection(item, title))
        self.assertNotIn("*1", next(line for line in output.splitlines() if title[:18] in line))
        self.assertIn(self.styles().apply("Test (Default)", "nextIctxWarning"), output)
        self.assertIn(self.styles().apply("*1", "nextIctxWarning"), output)
        self.assertNotIn("\x1b", self.watch(warning_watch_projection(item), colored=False))
        self.assertNotIn("\x1b", self.report(warning_report_projection(item), colored=False))

    def test_warning_stays_on_its_prompt_and_fits_independently_truncated_model_effort(self):
        base = warning_prompt(PriceWarningSeverity.APPROACHING)
        long_label = "Claude Sonnet 5.5 (Extra High)"
        for width in range(9):
            self.assertLessEqual(len(_fit_model_effort(long_label, width)), width)
        rows = tuple(
            WatchRow(f"S{number}", f"Session {number}", replace(
                base, preview=f"test prompt {number}", model_effort=long_label, watch_model_effort=long_label,
            ))
            for number in range(1, 13)
        )
        warnings = {row.session_id: base.watch_next_context_warning for row in rows}
        text = self.watch(WatchProjection("Watch", "V2", rows, session_warnings=warnings))
        line = next(line for line in text.splitlines() if "#1 test prompt 12" in line)
        model_cell = ANSI.sub("", line).split("|")[2].strip()
        self.assertEqual(25, len(model_cell))
        self.assertTrue(model_cell.endswith("*12"))
        fitted = model_cell[:-3]
        model, effort = fitted.rsplit(" ", 1)
        self.assertTrue(model.endswith("..."))
        self.assertTrue(effort.startswith("(") and effort.endswith(")"))
        self.assertIn("...", effort)
        styler = self.styles()
        self.assertIn(styler.apply(fitted, "nextIctxWarning"), line)
        self.assertIn(styler.apply("*12", "nextIctxWarning"), line)

        no_warning = replace(base, preview="plain prompt", model_effort=long_label, watch_model_effort=long_label,
                             watch_next_context_warning="", watch_next_context_warning_severity=PriceWarningSeverity.NONE)
        plain_projection = WatchProjection("Watch", "V2", (WatchRow("plain", "Plain", no_warning),),
                                           session_warnings={})
        plain_line = next(line for line in self.watch(plain_projection).splitlines() if "plain prompt" in line)
        plain_cell = ANSI.sub("", plain_line).split("|")[2].strip()
        self.assertEqual(25, len(plain_cell))
        self.assertFalse(plain_cell.endswith("*"))
        plain_model, plain_effort = plain_cell.rsplit(" ", 1)
        self.assertTrue(plain_model.endswith("..."))
        self.assertTrue(plain_effort.startswith("(") and plain_effort.endswith(")"))
        self.assertIn("...", plain_effort)

        unrelated = WatchRow("root", "Session root", replace(base, preview="older prompt",
                              model_effort="Unrelated model", watch_model_effort="Unrelated model"),
                             is_latest_session_event=False)
        current = WatchRow("root", "Session root", replace(base, preview="current prompt",
                           model_effort="Current model", watch_model_effort="Current model"))
        scoped = self.watch(WatchProjection("Watch", "V2", (unrelated, current),
                                            session_warnings={"root": base.watch_next_context_warning}))
        old_line = next(line for line in scoped.splitlines() if "older prompt" in line)
        current_line = next(line for line in scoped.splitlines() if "current prompt" in line)
        self.assertIn("Unrelated model", old_line)
        self.assertNotIn("*1", old_line)
        self.assertIn(styler.apply("Current model", "nextIctxWarning"), current_line)
        self.assertIn(styler.apply("*1", "nextIctxWarning"), current_line)

    def test_compaction_warning_marker_follows_its_model_effort(self):
        item = replace(warning_prompt(PriceWarningSeverity.EXCEEDED), is_compaction=True,
                       model_effort="Claude (High)", watch_model_effort="Claude (High)")
        output = self.watch(warning_watch_projection(item))
        compaction_line = next(line for line in output.splitlines() if "/compact" in line)
        plain = ANSI.sub("", compaction_line)
        self.assertIn("Claude (High)*1", plain)
        self.assertNotIn("*1", next(line for line in output.splitlines() if "Normal session" in line))

    def test_watch_expiry_live_none_and_report_fallback_share_state_selection(self):
        item = warning_prompt(PriceWarningSeverity.EXCEEDED)
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
        original = warning_watch_projection(warning_prompt(PriceWarningSeverity.APPROACHING))
        changed = replace(original, rows=(replace(original.rows[0], prompt=replace(original.rows[0].prompt,
                          watch_next_context_warning_severity=PriceWarningSeverity.EXCEEDED)),))
        self.assertNotEqual(WatchCoordinator._visible_signature(original), WatchCoordinator._visible_signature(changed))

    def test_unrelated_failure_and_abort_row_styles_remain_critical(self):
        renderer = WatchRenderer(self.config, stream=io.StringIO(), interactive=True)
        item = warning_prompt(PriceWarningSeverity.EXCEEDED)
        for failed in (replace(item, watch_error=True), replace(item, aborted=True)):
            row = WatchRow("root", "title", failed, marker="!")
            self.assertEqual("costQuotaCritical", renderer._row_style(row))
            output = self.watch(replace(warning_watch_projection(failed), rows=(row,)))
            self.assertIn(self.styles().apply("X", "costQuotaCritical").split("X")[0], output)

    def test_both_palette_defaults_use_same_non_red_warning_role(self):
        for palette in self.config["colorSchemes"].values():
            self.assertEqual(palette["nextIctxWarning"], palette["nextIctxWarningReason"])
            self.assertNotIn(palette["nextIctxWarning"]["foreground"], ("Red", "DarkRed"))


class StructuredPriceWarningTests(unittest.TestCase):
    def test_threshold_boundary_and_custom_trigger_are_unchanged(self):
        catalog = threshold_catalog()
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
                snapshot = make_uncompacted_snapshot()
                snapshot = replace(snapshot, invocations=tuple(
                    replace(item, tokens=TokenUsage(input=tokens, output=4)) if item.invocation_id == "i_next" else item
                    for item in snapshot.invocations))
                block = build_prompt_block(session_id="root", title="Test", bundle=analyze_snapshot(snapshot, now_ms=4000),
                                           snapshot=snapshot, catalog=threshold_catalog(), config={})
                item = next(row for row in block.rows if row.event_id == "u_next")
                self.assertEqual(severity, item.next_context_warning_severity)
                self.assertEqual(severity, item.watch_next_context_warning_severity)
                self.assertEqual(severity, block.next_context_warning_severity)
                self.assertEqual(severity, WatchRow("root", "Test", item).next_context_warning_severity)


if __name__ == "__main__":
    unittest.main()
