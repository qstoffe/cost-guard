"""Actual SQLite → separate CLI/Web owners → canonical Live publication parity."""
import json
from contextlib import closing
from dataclasses import replace
import tempfile
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from development.tests.fixtures.v1_watch import V1Watch
from development.tests.fixtures.opencode_v2_service import FakeV2Service, fixture
from src.application.live import LiveRuntime
from src.application.live_projection import project_live
from src.sources.errors import SourceUnavailableError
from src.sources.opencode_v2 import OpenCodeV2Source
from src.sources.selection import SourceSelector
from src.web.source_startup import SourceStartup
from src.reports import ReportKind, ReportRequest


class V1WebWatchTests(unittest.TestCase):
    def test_v1_finite_reports_share_the_source_without_changing_its_database(self):
        with tempfile.TemporaryDirectory() as root, closing(V1Watch(root)) as scenario:
            before = scenario.path.read_bytes()
            for kind in (ReportKind.NORMAL, ReportKind.ALL_MODELS, ReportKind.SESSIONS,
                    ReportKind.SESSION, ReportKind.TOKEN_MIX, ReportKind.AI_STATS, ReportKind.COMPARISONS):
                with self.subTest(kind=kind):
                    report = scenario.cli.report_service.build(ReportRequest(kind,
                        session_id="ses_root" if kind is ReportKind.SESSION else None))
                    self.assertEqual(kind, report.kind)
                    self.assertEqual("v1", scenario.cli.report_service.selection.selected)
            self.assertEqual(before, scenario.path.read_bytes())

    def test_both_sources_present_auto_agrees_but_forced_cli_v1_can_differ_from_web(self):
        with tempfile.TemporaryDirectory() as root, closing(V1Watch(root)) as scenario, FakeV2Service(fixture()) as v2:
            registration = Path(root) / "v2.json"
            registration.write_text(json.dumps({"url": v2.url, "pid": 4242, "password": "secret"}), encoding="utf-8")
            def selector():
                return SourceSelector(v1_factory=lambda: scenario.selector().select("v1").source,
                    v2_factory=lambda: OpenCodeV2Source(registration), inspect_migration_gap=False)
            cli = selector().select("auto")
            with patch("src.web.source_startup.load_configuration", return_value=SimpleNamespace(values={"openCode": {"source": "auto"}})), \
                    patch("src.web.source_startup.SourceSelector", side_effect=lambda **_: selector()), \
                    patch("src.web.source_startup.wake_cli_service") as wake:
                web = SourceStartup(Path(root), lambda *_: None, Event()).prepare()
            self.assertEqual(("v2", "v2"), (cli.selected, web.selected))
            self.assertNotEqual(scenario.cli_selection.selected, web.selected)
            self.assertIsNot(cli.source, web.source)
            wake.assert_not_called()
            cli.source.close_reads()
            web.source.close_reads()

    def test_minimal_and_plugin_rich_v1_polling_preserves_cli_values_and_lifecycle(self):
        for mode in ("auto", "v1"):
            for plugins in (False, True):
                for ending in ("complete", "cancelled", "error"):
                    with self.subTest(mode=mode, plugins=plugins, ending=ending), tempfile.TemporaryDirectory() as root, \
                            closing(V1Watch(root, mode=mode, plugins=plugins)) as scenario:
                        self.assertEqual(("v1", "v1"), (scenario.cli_selection.selected, scenario.web_selection.selected))
                        self.assertIsNot(scenario.cli.source, scenario.web.source)
                        self.assertFalse(scenario.web.source.capabilities.live_changes)
                        self.assertIsNone(scenario.web._event_pump)
                        for phase in ("initial", "idle", ending, "earlier"):
                            if phase == ending:
                                scenario.phase(ending)
                            elif phase == "idle":
                                scenario.now += 5000  # Cross the existing 10-second running-tool threshold.
                            elif phase == "earlier":
                                scenario.now += 120_000
                            cli = scenario.cli.acquire_cycle().projection
                            scenario.driver.tick()
                            web = scenario.settle()
                            # Async cards and terminal table have intentionally different layouts;
                            # their source-backed focal prompt, activity and context must agree.
                            cards = (*web.active_cards, *web.history_cards)
                            card = next(card for card in cards if card.session_id == "ses_root")
                            cli_row = next(row for row in cli.rows if row.prompt.event_id == "live-user")
                            web_row = next(row for row in card.rows if row.prompt.event_id == "live-user")
                            if phase in {"initial", "idle"}:
                                # No usage invocation yet: CLI retains its zero-duration value;
                                # Web cards deliberately show observed prompt age while running.
                                self.assertEqual(0, cli_row.prompt.duration_ms)
                                self.assertEqual(scenario.now - 10_000, web_row.prompt.duration_ms)
                            else:
                                self.assertEqual(cli_row.prompt.duration_ms, web_row.prompt.duration_ms)
                            self.assertEqual(cli_row.prompt, replace(web_row.prompt, duration_ms=cli_row.prompt.duration_ms))
                            # Rich bounded invocation help is deliberately Web-only;
                            # shared counts/outcomes/running timing remain identical.
                            if cli_row.tool is None:
                                self.assertIsNone(web_row.tool)
                            else:
                                self.assertEqual(cli_row.tool, replace(web_row.tool,
                                    running_invocation=cli_row.tool.running_invocation,
                                    background_invocation=cli_row.tool.background_invocation,
                                    running_invocations=(), background_invocations=(),
                                    running_invocation_count=0, background_invocation_count=0))
                                self.assertEqual((), cli_row.tool.running_invocations)
                                self.assertEqual((), cli_row.tool.background_invocations)
                            wire = project_live(web).to_json()
                            self.assertEqual(1, sum(c["session_id"] == "ses_root" for c in wire["active_cards"] + wire["history_cards"]))
                            self.assertEqual(phase in {"initial", "idle"}, web_row.prompt.in_progress)
                            if phase == "earlier":
                                self.assertIn(card, web.history_cards)
                            if plugins and phase == "initial":
                                self.assertIn(("custom_lookup", 2), web_row.tool.tool_counts)
                                self.assertIn(("custom_running", 1), web_row.tool.tool_counts)
                                self.assertIn(("skill", 1), web_row.tool.tool_counts)
                                self.assertEqual(6, web_row.tool.tool_count, "duplicate callID and opaque plugin part add no calls")
                                self.assertEqual((), web_row.tool.skills, "V1 has no native registry proof of custom skill origin")
                            if plugins and phase == "idle":
                                self.assertEqual("custom_running", web_row.tool.running_tool)
                                self.assertEqual(13_000, web_row.tool.running_ms)
                                self.assertIsNotNone(web_row.tool.running_invocation)

    def test_live_generation_is_allowlisted_and_withheld_without_fresh_source_proof(self):
        published = []
        runtime = LiveRuntime(None, lambda _, value: published.append(value.to_json()))
        driver = SimpleNamespace(source_state="running", error=None, observed_at_ms=123,
            coordinator=SimpleNamespace(selection=SimpleNamespace(selected="v1"),
                report_service=SimpleNamespace(timezone_id="UTC", config={})))
        with patch("src.application.live.project_live", return_value=None):
            for selected, frame, error, expected in (("v1", object(), None, "v1"),
                    ("v2", object(), None, "v2"), ("/private/path", object(), None, "unknown"),
                    ("v1", None, None, "unknown"), ("v1", object(), SourceUnavailableError("private"), "unknown")):
                driver.coordinator.selection.selected = selected
                driver.error = error
                runtime._publish_frame(driver, frame)
                self.assertEqual(expected, published[-1]["source_generation"])
        self.assertNotIn("private", json.dumps(published))


if __name__ == "__main__":
    unittest.main()
