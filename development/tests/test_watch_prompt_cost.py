"""Full Watch reuses canonical prompt costs; missing evidence and units stay distinct."""
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from development.tests.fixtures.session_snapshots import make_uncompacted_snapshot
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from src.application.live_projection import project_live
from src.application.display import with_display
from src.application.projection import prompt as report_prompt
from src.domain import ModelRef, TokenUsage
from src.reports import ReportKind, ReportRequest
from src.reports.watch_capture import capture_rows
from src.reports.prompt_costs import PromptCostPart
from src.watch.models import WatchCard, WatchProjection, WatchRow


class WatchPromptCostTests(unittest.TestCase):
    def setUp(self):
        tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.source = MutableSource(make_uncompacted_snapshot())
        self.service = make_service(tmp, self.source, now_ms=4000)[2]
        self.revision = 0

    def capture(self, snapshot):
        self.revision += 1
        snapshot = replace(snapshot, source_revision=f"cost-{self.revision}")
        self.source.snapshot = snapshot
        self.service.invalidate_roots((snapshot.root.session_id,))
        capture, _ = capture_rows(self.service, snapshot.root)
        report = self.service.build(ReportRequest(ReportKind.SESSION, snapshot.root.session_id))
        cli = {row.event_id: row for row in report.prompt_blocks[0].rows}
        return capture.rows, cli

    def wire(self, rows, unit="credits"):
        card = WatchCard("root", "Cost fixture", rows[-1].event_id,
            tuple(WatchRow("root", "Cost fixture", row) for row in rows), "observed")
        return project_live(WatchProjection("Watch", "fixture", (), now_ms=4000,
            active_cards=(card,), history_cards=(replace(card, focal_id=""),)),
            ccost_display_unit=unit).to_json()

    def test_cache_multicall_model_switch_and_child_split_match_cli_raw_values(self):
        snapshot = make_uncompacted_snapshot()
        invocations = tuple(replace(item, tokens=TokenUsage(input=100, cache_read=300))
            if item.invocation_id == "i_wrapper" else
            replace(item, model=ModelRef("github-copilot", "claude-test"))
            if item.invocation_id == "i_child" else item for item in snapshot.invocations)
        rows, cli = self.capture(replace(snapshot, invocations=invocations))
        row = next(row for row in rows if row.event_id == "u_sub")
        self.assertEqual(3, row.calls)
        self.assertEqual((Decimal("0.0222"), Decimal("0.013"), Decimal("0.0092")),
            (row.ccost, row.incoming_context_ccost, row.extra_ccost))
        for unit in ("credits", "usd"):
            wire = self.wire(rows, unit)
            for kind in ("active_cards", "history_cards"):
                for item in wire[kind][0]["rows"]:
                    prompt = item["prompt"]
                    expected = cli[prompt["event_id"]]
                    for key in ("ccost", "incoming_context_ccost", "extra_ccost"):
                        value = getattr(expected, key)
                        self.assertEqual(None if value is None else str(value), prompt[key])
                    self.assertEqual(expected.ccost,
                        expected.incoming_context_ccost + expected.extra_ccost)

    def test_active_snapshot_partial_unpriced_and_zero_keep_canonical_evidence(self):
        cases = ((TokenUsage(input=100, output=40), None),
            (TokenUsage(input=100, known_fields=("input",)), None),
            (TokenUsage(input=100, output=40), ModelRef("missing", "unpriced")),
            (TokenUsage(input=100), None), (TokenUsage(), None))
        for running in (False, True):
            for usage, model in cases:
                with self.subTest(running=running, usage=usage, model=model):
                    snapshot = make_uncompacted_snapshot(running=running)
                    invocations = tuple(replace(item, tokens=usage, model=model or item.model)
                        if item.invocation_id == "i_next" else item for item in snapshot.invocations)
                    rows, cli = self.capture(replace(snapshot, invocations=invocations))
                    row = next(row for row in rows if row.event_id == "u_next")
                    for key in ("ccost", "incoming_context_ccost", "extra_ccost", "unresolved_cost"):
                        self.assertEqual(getattr(cli["u_next"], key), getattr(row, key))
                    prompt = self.wire((row,))["active_cards"][0]["rows"][0]["prompt"]
                    if model:
                        self.assertEqual("N/A", prompt["display"]["ccost"])
                        self.assertIsNone(prompt["incoming_context_ccost"])
                        self.assertIsNone(prompt["extra_ccost"])
                    if running and usage.known_fields == ("input",):
                        self.assertIsNone(prompt["incoming_context_ccost"])
                        self.assertIsNone(prompt["extra_ccost"])
                    if usage.known_fields == ("input",):
                        self.assertEqual("N/A", prompt["display"]["incoming_context_ccost"])
                        self.assertEqual("N/A", prompt["display"]["extra_ccost"])
                    if not model and usage == TokenUsage(input=100):
                        self.assertEqual("0", prompt["display"]["extra_ccost"])
                    if usage == TokenUsage():
                        self.assertEqual("0", prompt["display"]["ccost"])
                        self.assertEqual("N/A", prompt["display"]["incoming_context_ccost"])

    def test_independent_first_request_and_child_coverage_agree_with_cli_unknowns(self):
        snapshot = make_uncompacted_snapshot()
        known = TokenUsage(input=100, cache_read=300, output=40)
        no_output = TokenUsage(input=100, cache_read=300,
            known_fields=("input", "cache_read", "cache_write"))
        cases = ((TokenUsage(input=100, known_fields=("input",)), known, False, False),
            (no_output, known, True, False), (known, no_output, True, False),
            (known, known, True, True), (known, no_output, True, False))
        for first, child, incoming_known, extra_known in cases:
            invocations = tuple(replace(item, tokens=first) if item.invocation_id == "i_wrapper" else
                replace(item, tokens=child) if item.invocation_id == "i_child" else item
                for item in snapshot.invocations)
            rows, cli = self.capture(replace(snapshot, invocations=invocations))
            row = next(row for row in rows if row.event_id == "u_sub")
            legacy = with_display(report_prompt(cli["u_sub"])).to_json()
            self.assertEqual(not extra_known, legacy["display"]["extra_ccost"] == "N/A")
            self.assertNotIn("extra_ccost_known", legacy)
            for unit in ("credits", "usd"):
                wire = self.wire((row,), unit)
                for kind in ("active_cards", "history_cards"):
                    value = wire[kind][0]["rows"][0]["prompt"]
                    for key, supported in (("incoming_context_ccost", incoming_known), ("extra_ccost", extra_known)):
                        self.assertEqual(supported, value[key + "_known"])
                        expected = getattr(cli["u_sub"], key)
                        self.assertEqual(None if expected is None else str(expected), value[key])
                        self.assertEqual(not supported, value["display"][key] == "N/A")

    @unittest.skipUnless(shutil.which("node"), "optional JavaScript VM unavailable")
    def test_both_tables_display_independent_unknown_zero_partial_and_unit_tokens(self):
        rows, _ = self.capture(make_uncompacted_snapshot())
        base = replace(rows[-1], linked_agent_count=2, cost_parts=(
            PromptCostPart("root", 0, "fixture", "main", "high", "Main", "High",
                1, Decimal(800), 1, True, tuple(map(Decimal, (500, 100, 50, 150)))),
            PromptCostPart("child-a", 1, "fixture", "child-a", "low", "Child A", "Low",
                1, Decimal(300), 1, True, tuple(map(Decimal, (100, 100, 50, 50))),
                prompt_ids=(("fixture", "child-a", "first"),), prompts_complete=True),
            PromptCostPart("child-b", 2, "fixture", "child-b", "medium", "Child B", "Medium",
                1, Decimal(150), 1, False, (Decimal(100), None, Decimal(0), Decimal(50)),
                prompt_ids=(("fixture", "child-b", "second"),), prompts_complete=False)))
        cases = (("1250", "900", "350", False), ("12", "5", None, True),
            ("100", None, None, False), ("0", "0", "0", False),
            ("0", None, None, True), ("1.1", "1.05", ".05", False),
            ("0", None, None, False), (".01", None, None, False),
            (".01", None, None, True), ("12", None, "12", False),
            ("12", "12", None, False))
        rows = tuple(replace(base, event_id=str(index), ccost=Decimal(total),
            incoming_context_ccost=None if incoming is None else Decimal(incoming),
            extra_ccost=None if extra is None else Decimal(extra), unresolved_cost=partial,
            incoming_context_ccost_known=True, extra_ccost_known=True)
            for index, (total, incoming, extra, partial) in enumerate(cases))
        rows += (replace(base, event_id="zero-requests", calls=0, ccost=Decimal(0),
            incoming_context_ccost=None, extra_ccost=None),
            replace(base, event_id="unknown", ccost=None),
            replace(base, event_id="sparse", is_compaction=True, calls=0, ccost=Decimal(0)),
            replace(base, event_id="unsupported-zero", ccost=Decimal(0),
                incoming_context_ccost=Decimal(0), extra_ccost=Decimal(0),
                incoming_context_ccost_known=False, extra_ccost_known=False),
            replace(base, event_id="unsupported-rounded-zero", ccost=Decimal(".01"),
                incoming_context_ccost=Decimal(".01"), extra_ccost=Decimal(0),
                incoming_context_ccost_known=True, extra_ccost_known=False))
        result = subprocess.run([shutil.which("node"),
            "development/tests/integration/web_watch_prompt_cost.cjs"],
            input=json.dumps(dict(state="running", view=self.wire(rows))),
            text=True, capture_output=True, cwd=Path(__file__).resolve().parents[2], timeout=10)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("watch prompt cost passed", result.stdout)
