from __future__ import annotations

import io
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from development.tests.test_analysis_core import make_snapshot
from development.tests.test_step8_watch import MutableSource, make_service
from development.tests.test_v783_regressions import _Pricing, _Source
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.domain import IntegrationHealth, ProviderCapabilities
from src.presentation import WatchRenderer
from src.reports import ReportService
from src.reports.models import PromptProjection
from src.sources.model_availability import OpenCodeModelAvailabilitySource
from src.sources.selection import SourceSelection
from src.version import DISPLAY_VERSION, RELEASE_DATE
from src.watch import WatchCoordinator
from src.watch.coordinator import WatchCycle
from src.watch.models import ToolObservation, WatchProjection, WatchRow

ROOT = Path(__file__).resolve().parents[2]


class _UnavailableAccount:
    capabilities = ProviderCapabilities(account_quota=True)
    included_usage = False

    def __init__(self, provider_id: str = "openai") -> None:
        self.provider_id = provider_id
        self.quota_calls = 0

    def probe(self):
        return IntegrationHealth(False, False, "not configured")

    def get_quota_snapshot(self):
        self.quota_calls += 1
        raise AssertionError("an unavailable account provider must not be queried")


def _prompt(**changes) -> PromptProjection:
    base = PromptProjection(
        at_ms=1_000,
        prompt_number=1,
        label="prompt",
        preview="hello",
        model_effort="GPT Test",
        watch_model_effort="GPT Test",
        ccost=Decimal("3"),
        cost_estimated=False,
        unresolved_cost=False,
        calls=19,
        incoming_context_tokens=1_000,
        incoming_context_ccost=None,
        extra_ccost=None,
        token_mix_percent=None,
        event_id="u1",
        duration_ms=121_000,
        watch_delta_context_tokens=25_400,
        watch_next_context_tokens=42_200,
    )
    return replace(base, **changes)


class V784RegressionTests(unittest.TestCase):
    def test_opencode_model_listing_executes_windows_cmd_shim_through_comspec(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout="github-copilot/gpt-test\n")
        with mock.patch("src.sources.model_availability.shutil.which", return_value=r"C:\Tools\opencode.cmd"), \
             mock.patch.dict("src.sources.model_availability.os.environ", {"COMSPEC": r"C:\Windows\System32\cmd.exe"}), \
             mock.patch("src.sources.model_availability.subprocess.run", return_value=completed) as run:
            source = OpenCodeModelAvailabilitySource()
            self.assertEqual(("github-copilot/gpt-test",), source.available_model_ids())
        command = run.call_args.args[0]
        self.assertEqual(r"C:\Windows\System32\cmd.exe", command[0])
        self.assertEqual(["/d", "/s", "/c"], command[1:4])
        self.assertIn("opencode.cmd", command[4].lower())
        self.assertTrue(command[4].lower().endswith("models"))

    def test_absent_account_provider_is_not_queried_or_exposed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            database = CacheDatabase(Path(td))
            database.initialize()
            source = _Source()
            missing = _UnavailableAccount()
            service = ReportService(
                selection=SourceSelection(source, "v1", (), source.probe()),
                pricing_provider=_Pricing(),
                account_provider=None,
                account_providers=(missing,),
                cache_repository=CacheRepository(database),
                config=dict(load_configuration(ROOT).values),
                now_ms=4_000,
            )
            self.assertEqual((), service.account_quota_snapshots())
            self.assertEqual(0, missing.quota_calls)

    def test_watch_restores_whole_k_approximation_compact_duration_and_spanning_tool_row(self) -> None:
        prompt = _prompt(in_progress=True)
        projection = WatchProjection(
            title="Cost Guard Watch",
            source_label="V1",
            rows=(WatchRow("root", "Session", prompt, marker=">", tool=ToolObservation(4, 0, 3, "Read saved Payment Window")),),
            active_count=1,
            status="1 prompt running · Next refresh: 00:05",
            now_ms=122_000,
        )
        stream = io.StringIO()
        WatchRenderer({"timezone": "UTC", "colors": {}, "thresholds": {}}, stream=stream, interactive=False).render(projection)
        text = stream.getvalue()
        self.assertIn(f"Cost Guard {DISPLAY_VERSION} ({RELEASE_DATE}) — Prompt watch — Source: OpenCode V1", text)
        self.assertIn("+25k", text)
        self.assertIn("~42k", text)
        self.assertNotIn("25.4k", text)
        self.assertNotIn("42.2k", text)
        self.assertIn("2m1s", text)
        self.assertNotIn("2m 01s", text)
        activity = next(line for line in text.splitlines() if "tool calls" in line)
        self.assertEqual(2, activity.count("|"), "running tool activity must span the complete Watch table")

    def test_running_prompt_uses_live_session_context_instead_of_na(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(make_snapshot(running=True))
            config, selection, service, _db = make_service(td, source)
            projection = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 2_200).initialize().projection
            row = next(item for item in projection.rows if item.prompt.event_id == "u_next")
            self.assertIsNotNone(row.prompt.watch_delta_context_tokens)
            self.assertIsNotNone(row.prompt.watch_next_context_tokens)
            stream = io.StringIO()
            WatchRenderer(config, stream=stream, interactive=False).render(projection)
            running_line = next(line for line in stream.getvalue().splitlines() if "#2 " in line)
            self.assertNotIn("N/A", running_line)

    def test_expired_recent_marker_requires_full_dashboard_repaint(self) -> None:
        old = WatchProjection("Cost Guard Watch", "V1", (WatchRow("root", "Session", _prompt(), marker="✓"),), now_ms=1_000)
        current = replace(old, rows=(WatchRow("root", "Session", _prompt(), marker=""),), now_ms=32_000)
        cycle = WatchCycle(current, (), (), False)
        self.assertTrue(WatchCoordinator._needs_full_render(old, current, cycle))

    def test_completed_marker_expires_without_another_source_poll(self) -> None:
        clock = [2_200]
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(make_snapshot(running=True))
            config, selection, service, _db = make_service(td, source)
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: clock[0])
            watch.initialize()
            source.snapshot = replace(make_snapshot(running=False), source_revision="v1-rev-2")
            clock[0] = 2_400
            completed = watch.poll_once().projection
            row = next(item for item in completed.rows if item.prompt.event_id == "u_next")
            self.assertEqual("✓", row.marker)
            loads_after_completion = source.load_count

            clock[0] += 30_001
            aged = watch.status_projection(seconds_until_check=1)
            row = next(item for item in aged.rows if item.prompt.event_id == "u_next")
            self.assertEqual("", row.marker)
            self.assertEqual(loads_after_completion, source.load_count, "marker aging must be presentation-only")

    def test_v77_style_watch_status_uses_clock_countdown(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(make_snapshot(running=False))
            config, selection, service, _db = make_service(td, source)
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 2_200)
            self.assertEqual("Idle · Next prompt check: 00:30", watch._steady_status(0, 30))
            self.assertEqual("1 prompt running · Next refresh: 00:05", watch._steady_status(1, 5))


if __name__ == "__main__":
    unittest.main()
