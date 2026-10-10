from __future__ import annotations

import io
import unittest
from decimal import Decimal

from development.fixtures.session_snapshots import make_snapshot
from src.presentation import WatchRenderer
from src.reports.models import PromptProjection, SessionPromptBlock
from src.watch.models import WatchProjection, WatchRow
from src.watch.tracker import WatchRowTracker


def _prompt(
    *,
    at_ms: int,
    number: int,
    event_id: str,
    next_tokens: int | None,
    watch_warning: str = "",
    report_warning: str = "",
    is_compaction: bool = False,
) -> PromptProjection:
    return PromptProjection(
        at_ms=at_ms,
        prompt_number=number,
        label="/compact" if is_compaction else "prompt",
        preview="" if is_compaction else f"prompt {number}",
        model_effort="GPT Test",
        watch_model_effort="GPT Test",
        ccost=Decimal("1"),
        cost_estimated=False,
        unresolved_cost=False,
        calls=1,
        incoming_context_tokens=10_000,
        incoming_context_ccost=Decimal("1"),
        extra_ccost=Decimal("0"),
        token_mix_percent=(90, 0, 0, 10),
        is_compaction=is_compaction,
        event_id=event_id,
        duration_ms=1_000,
        watch_delta_context_tokens=1_000,
        watch_next_context_tokens=next_tokens,
        watch_next_context_warning=watch_warning,
        next_context_warning=report_warning,
    )


class V788RegressionTests(unittest.TestCase):
    def test_newer_session_event_suppresses_historical_watch_threshold_warning(self) -> None:
        exceeded = "[Price threshold >200.0K exceeded]"
        old = _prompt(at_ms=1_000, number=2, event_id="old", next_tokens=236_000, watch_warning=exceeded)
        compact = _prompt(at_ms=2_000, number=0, event_id="compact", next_tokens=4_000, is_compaction=True)
        latest = _prompt(at_ms=3_000, number=5, event_id="latest", next_tokens=25_000)
        block = SessionPromptBlock("root", "DFP-10524 – Review", (old, compact, latest), Decimal("0.03"), 3)
        tracker = WatchRowTracker(started_at_ms=0, recent_seconds=0, max_rows=20)

        rows = tracker.project({"root": block}, {"root": make_snapshot(running=False)}, now_ms=4_000)
        by_event = {row.prompt.event_id: row for row in rows}
        self.assertFalse(by_event["old"].is_latest_session_event)
        self.assertEqual("", by_event["old"].next_context_warning)
        self.assertTrue(by_event["latest"].is_latest_session_event)
        self.assertEqual("", by_event["latest"].next_context_warning)

        warnings = {row.session_id: row.next_context_warning for row in rows if row.next_context_warning}
        projection = WatchProjection("Cost Guard Watch", "V1", rows, now_ms=4_000, session_warnings=warnings)
        stream = io.StringIO()
        WatchRenderer({"timezone": "UTC", "colors": {}, "thresholds": {}}, stream=stream, interactive=False).render(projection)
        text = stream.getvalue()
        self.assertNotIn("*1 DFP-10524", text)
        self.assertNotIn("Next Ictx: Price threshold", text)

    def test_live_context_drop_can_clear_stale_report_warning_on_latest_event(self) -> None:
        prompt = _prompt(
            at_ms=3_000,
            number=5,
            event_id="latest",
            next_tokens=25_000,
            watch_warning="",
            report_warning="[Price threshold >200.0K exceeded]",
        )
        row = WatchRow("root", "DFP-10524 – Review", prompt, is_latest_session_event=True)
        self.assertEqual("", row.next_context_warning)


if __name__ == "__main__":
    unittest.main()
