from __future__ import annotations

import io
import unittest
from dataclasses import replace
from pathlib import Path

from development.tests.fixtures.pricing_catalog import threshold_catalog
from development.tests.fixtures.session_snapshots import make_uncompacted_snapshot
from development.tests.fixtures.warning_projections import warning_prompt
from src.analysis.context import PriceWarningSeverity, next_context_warning_state
from src.analysis.core import analyze_snapshot
from src.config import load_configuration
from src.domain import TokenUsage
from src.presentation import ReportRenderer, WatchRenderer
from src.presentation.terminal import AnsiStyler
from src.reports.prompts import build_prompt_block
from src.watch.models import WatchProjection, WatchRow


class ContextWarningPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_configuration(Path(__file__).resolve().parents[2]).values

    def styles(self, config=None):
        return AnsiStyler((config or self.config)["colors"], enabled=True)

    def watch(self, projection, *, colored=True, config=None):
        stream = io.StringIO()
        WatchRenderer(config or self.config, stream=stream, interactive=colored).render(projection)
        return stream.getvalue().replace("\x1b[2K", "")

    def report(self, projection, *, colored=True, width=160, config=None):
        stream = io.StringIO()
        ReportRenderer(config or self.config, stream=stream, color_enabled=colored, terminal_width=width).render(projection)
        return stream.getvalue()

    def test_watch_expiry_live_none_and_report_fallback_share_state_selection(self):
        item = warning_prompt(PriceWarningSeverity.EXCEEDED)
        historical = WatchRow("root", "title", item, is_latest_session_event=False)
        self.assertEqual("", historical.next_context_warning)
        self.assertEqual(PriceWarningSeverity.NONE, historical.next_context_warning_severity)
        reduced = replace(item, watch_next_context_tokens=20_000, watch_next_context_warning="",
                          watch_next_context_warning_severity=PriceWarningSeverity.NONE)
        self.assertEqual(PriceWarningSeverity.NONE, WatchRow("root", "title", reduced).next_context_warning_severity)
        stale_mapping = self.watch(WatchProjection(
            "Watch", "V2", (WatchRow("root", "title", reduced),),
            session_warnings={"root": item.watch_next_context_warning},
        ))
        self.assertNotIn("*1", stale_mapping)
        self.assertNotIn("Context:", stale_mapping)
        fallback = replace(item, watch_next_context_tokens=None, watch_next_context_warning="",
                           watch_next_context_warning_severity=PriceWarningSeverity.NONE)
        self.assertEqual(PriceWarningSeverity.EXCEEDED, WatchRow("root", "title", fallback).next_context_warning_severity)


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
