from __future__ import annotations

import io
import tempfile
import unittest
from dataclasses import replace

from development.fixtures.session_snapshots import make_uncompacted_snapshot
from development.fixtures.pricing_catalog import catalog as sample_catalog, threshold_catalog
from development.fixtures.watch_runtime import MutableSource, make_service
from src.analysis import analyze_snapshot
from src.analysis.context import watch_context_state
from src.domain import ModelInvocation, TokenUsage
from src.presentation import WatchRenderer
from src.reports.prompts import build_prompt_block
from src.watch.models import WatchProjection, WatchRow


class V786RegressionTests(unittest.TestCase):
    def test_running_watch_ignores_newer_zero_usage_root_as_context_anchor(self) -> None:
        snapshot = make_uncompacted_snapshot(running=True)
        zero = ModelInvocation(
            "i_next_zero", "root", 2190, next(item.model for item in snapshot.invocations if item.invocation_id == "i_next"),
            TokenUsage(), next(item.provenance for item in snapshot.invocations if item.invocation_id == "i_next"),
            completed_at_ms=None, initiating_event_id="u_next", message_id="a_next",
        )
        snapshot = replace(snapshot, invocations=snapshot.invocations + (zero,))
        bundle = analyze_snapshot(snapshot, now_ms=2200)
        record = next(item for item in bundle.prompts if item.prompt_id == "u_next")
        self.assertEqual(0, record.last_root_entry.request_input_approx, "fixture must reproduce the v78.5 zero-tail failure")

        state = watch_context_state(snapshot, bundle, record, sample_catalog())
        self.assertEqual(34, state.next_tokens)
        self.assertEqual(21, state.delta_tokens)
        self.assertEqual("gpt-test", state.model_id)

    def test_running_watch_restores_live_threshold_marker_footnote_and_context_color_role(self) -> None:
        snapshot = make_uncompacted_snapshot(running=True)
        invocations = tuple(
            replace(item, tokens=TokenUsage(input=80_000, output=5)) if item.invocation_id == "i_next" else item
            for item in snapshot.invocations
        )
        snapshot = replace(snapshot, invocations=invocations)
        bundle = analyze_snapshot(snapshot, now_ms=2200)
        block = build_prompt_block(
            session_id="root", title="DFP-10524 – Review", bundle=bundle, snapshot=snapshot,
            catalog=threshold_catalog(), config={"thresholds": {"nextIctxPriceThresholdWarningPercent": 75}},
        )
        prompt = next(item for item in block.rows if item.event_id == "u_next")
        self.assertIsNotNone(prompt.watch_next_context_tokens)
        self.assertIn("Approaching price threshold", prompt.watch_next_context_warning)
        self.assertIsNotNone(prompt.watch_next_context_cached_ccost)
        self.assertIsNotNone(prompt.watch_next_context_fresh_ccost)

        projection = WatchProjection(
            title="Cost Guard Watch", source_label="V1",
            rows=(WatchRow("root", block.title, prompt, marker=">"),),
            active_count=1, status="1 prompt running · Next refresh: 00:05", now_ms=2200,
            session_warnings={"root": prompt.watch_next_context_warning},
        )
        stream = io.StringIO()
        WatchRenderer({"timezone": "UTC", "colors": {}, "thresholds": {}}, stream=stream, interactive=False).render(projection)
        text = stream.getvalue()
        self.assertIn("*1 DFP-10524", text)
        self.assertIn("*1 Context: Approaching price threshold", text)
        self.assertNotIn("$", text)
        self.assertIn("Context:", text)
        prompt_line = next(line for line in text.splitlines() if "#2 " in line)
        self.assertNotIn("N/A", prompt_line)

    def test_coordinator_projects_watch_specific_live_warning(self) -> None:
        snapshot = make_uncompacted_snapshot(running=True)
        invocations = tuple(
            replace(item, tokens=TokenUsage(input=80_000, output=5)) if item.invocation_id == "i_next" else item
            for item in snapshot.invocations
        )
        source = MutableSource(replace(snapshot, invocations=invocations))
        with tempfile.TemporaryDirectory() as td:
            config, selection, service, _db = make_service(td, source)
            service.pricing_provider.catalog = threshold_catalog()
            from src.watch import WatchCoordinator
            projection = WatchCoordinator(
                selection=selection, report_service=service, config=config, clock_ms=lambda: 2200
            ).initialize().projection
        self.assertIn("root", projection.session_warnings)
        self.assertIn("Approaching price threshold", projection.session_warnings["root"])


if __name__ == "__main__":
    unittest.main()
