from __future__ import annotations

import io
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from development.tests.test_analysis_core import make_snapshot
from development.tests.test_step6_context_comparisons import catalog as sample_catalog
from src.analysis import analyze_snapshot
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.domain import IntegrationHealth, ProviderCapabilities, SessionCapabilities
from src.presentation import ReportRenderer
from src.reports import ReportRequest, ReportService
from src.reports.models import SessionUsageRow, PromptProjection, ReportKind, ReportProjection, SessionPromptBlock
from src.reports.prompts import build_prompt_block
from src.sources.model_availability import OpenCodeModelAvailabilitySource
from src.sources.selection import SourceSelection

ROOT = Path(__file__).resolve().parents[2]


class _Source:
    source_id = "fake-v1"
    capabilities = SessionCapabilities(native_cost=True, child_sessions=True, compaction_events=True)

    def __init__(self) -> None:
        self.snapshot = make_snapshot()

    def probe(self):
        return IntegrationHealth(True, True, "ok")

    def list_sessions(self, since_ms=None):
        return self.snapshot.sessions

    def get_session_tree_revision(self, session_id):
        return self.snapshot.source_revision

    def load_session_snapshot(self, session_id):
        return self.snapshot


class _Pricing:
    provider_id = "github-copilot"
    capabilities = ProviderCapabilities(model_pricing=True, long_context_pricing=True)

    def __init__(self) -> None:
        self.catalog = replace(sample_catalog(), retrieved_at_ms=1, source_revision="prices")

    def probe(self):
        return IntegrationHealth(True, True, "ok")

    def get_model_pricing(self):
        return self.catalog.models

    def get_catalog(self, force=False):
        return self.catalog


class _Account:
    capabilities = ProviderCapabilities(account_quota=True)
    included_usage = False

    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id

    def probe(self):
        return IntegrationHealth(True, True, "ok")

    def get_quota_snapshot(self):
        raise AssertionError("quota is not needed by these focused tests")


class _Availability:
    def __init__(self, ids):
        self.ids = ids
        self.calls = 0

    def available_model_ids(self):
        self.calls += 1
        return self.ids


class V783RegressionTests(unittest.TestCase):
    def _service(self, availability, providers=("github-copilot",)) -> ReportService:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        database = CacheDatabase(Path(tmp.name))
        database.initialize()
        source = _Source()
        config = dict(load_configuration(ROOT).values)
        config["timezone"] = "UTC"
        accounts = tuple(_Account(provider) for provider in providers)
        return ReportService(
            selection=SourceSelection(source, "v1", (), source.probe()),
            pricing_provider=_Pricing(),
            account_provider=accounts[0] if accounts else None,
            account_providers=accounts,
            model_availability_source=availability,
            cache_repository=CacheRepository(database),
            config=config,
            now_ms=4_000,
        )

    def test_opencode_model_availability_uses_one_global_listing(self) -> None:
        source = OpenCodeModelAvailabilitySource(runner=lambda: (0, "github-copilot/gpt-test\nopenai/claude-test\n"))
        self.assertEqual(
            ("github-copilot/gpt-test", "openai/claude-test"),
            source.available_model_ids(),
        )

    def test_opencode_model_availability_fails_open_when_listing_fails(self) -> None:
        source = OpenCodeModelAvailabilitySource(
            runner=lambda: (1, "github-copilot/gpt-test\n")
        )
        self.assertIsNone(source.available_model_ids())

    def test_model_comparison_is_limited_to_selectable_models_for_detected_accounts(self) -> None:
        availability = _Availability(("github-copilot/gpt-test", "openai/claude-test"))
        report = self._service(availability, ("github-copilot", "openai")).build(ReportRequest())
        self.assertEqual(1, availability.calls)
        self.assertEqual({"GPT Test", "Claude Test"}, {row.model for row in report.model_comparison})

        restricted = _Availability(("github-copilot/gpt-test",))
        report = self._service(restricted).build(ReportRequest())
        self.assertEqual(["GPT Test"], [row.model for row in report.model_comparison])

    def test_model_comparison_keeps_full_catalog_if_availability_is_unknown(self) -> None:
        report = self._service(_Availability(None)).build(ReportRequest())
        self.assertEqual({"GPT Test", "Claude Test"}, {row.model for row in report.model_comparison})

    def test_sessions_render_whole_session_cost_without_total(self) -> None:
        report = ReportProjection(
            ReportKind.SESSIONS, "", "v1",
            session_usage=(SessionUsageRow("ses_a", "A", "GPT", False, Decimal("123"), 2),),
        )
        stream = io.StringIO()
        ReportRenderer({"timezone": "UTC", "colors": {}}, stream=stream, color_enabled=False, terminal_width=120)._render_sessions(report)
        row = next(line for line in stream.getvalue().splitlines() if "ses_a" in line)
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        self.assertEqual("123", cells[3])
        self.assertEqual("2", cells[4])
        self.assertNotIn("Total", stream.getvalue())

    def test_prompt_table_restores_v77_session_header_arrow_and_total_diagnostics(self) -> None:
        row = PromptProjection(
            at_ms=1_000, prompt_number=1, label="prompt", preview="If DFP-10524 is a Jira key",
            model_effort="GPT-5.6 Luna (XHigh)", ccost=Decimal("28"), cost_estimated=False,
            unresolved_cost=False, calls=49, incoming_context_tokens=9_000,
            incoming_context_ccost=Decimal("0.26"), extra_ccost=Decimal("25.74"),
            token_mix_percent=(4, 95, 0, 1), delta_context_tokens=218_000, next_context_tokens=227_000,
        )
        block = SessionPromptBlock(
            "ses_example", "DFP-10524 - Review workflow and state management", (row,), Decimal("28"), 49,
            total_ictx_cost_text="1%", total_extra_cost_text="99%", total_mix_text="4/95/0/1",
        )
        stream = io.StringIO()
        renderer = ReportRenderer({"timezone": "UTC", "colors": {}, "thresholds": {}}, stream=stream, color_enabled=False, terminal_width=180)
        renderer._render_prompt_block(block, warning_number=1)
        text = stream.getvalue()
        self.assertIn("| Session: ses_example", text)
        self.assertIn("| *1 DFP-10524 - Review workflow and state management", text)
        self.assertNotIn("### DFP-10524", text)
        self.assertIn("+218k → 227k", text)
        total = next(line for line in text.splitlines() if "| Total" in line)
        self.assertIn("1%", total)
        self.assertIn("99%", total)
        self.assertIn("4/95/0/1", total)

    def test_prompt_block_calculates_total_diagnostic_columns(self) -> None:
        snapshot = make_snapshot()
        bundle = analyze_snapshot(snapshot, now_ms=4_000)
        block = build_prompt_block(
            session_id=snapshot.root.session_id,
            title=snapshot.root.title,
            bundle=bundle,
            snapshot=snapshot,
            catalog=sample_catalog(),
            config={"thresholds": {}, "runningPromptWarningCCost": 1800},
        )
        self.assertTrue(block.total_mix_text)
        self.assertTrue(block.total_ictx_cost_text)
        self.assertTrue(block.total_extra_cost_text)


if __name__ == "__main__":
    unittest.main()
