from __future__ import annotations

import io
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from development.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.test_analysis_core import make_snapshot
from development.tests.test_step6_context_comparisons import catalog as sample_catalog
from development.tests.test_step7_reports_cli import FakePricingProvider, FakeSource
from development.tests.test_step8_watch import MutableSource, make_service
from src.analysis.comparisons import compaction_model_timeline_name, watch_model_timeline_name
from src.analysis.models import LocalUsageSummary
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.domain import CostKind, CostObservation, ModelRef, ModelPricing, PricingTier, TokenUsage
from src.presentation import ReportRenderer, WatchRenderer
from src.reports import ReportKind, ReportRequest, ReportService
from src.sources.selection import SourceSelection
from src.reports.models import PromptProjection, ReportProjection, SessionPromptBlock
from src.watch import WatchCoordinator
from src.watch.models import WatchProjection, WatchRow

ROOT = Path(__file__).resolve().parents[2]
NOW_MS = 1_790_510_400_000  # 2026-09-27T12:00:00Z
MONTH_START_MS = 1_788_220_800_000


def _usage(dollars: str, *, requests: int = 0, by_day=None) -> LocalUsageSummary:
    return LocalUsageSummary(
        Decimal(dollars), requests, 1 if requests else 0, 0, 0, 0, 0, Decimal(0), {}, by_day or {}
    )


class Step9ParityTests(unittest.TestCase):
    def _service(self, source=None, *, pricing=None, now_ms=4_000):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        db = CacheDatabase(Path(td.name)); db.initialize()
        config = dict(load_configuration(ROOT).values)
        config["timezone"] = "UTC"
        config["monthlyAiCredits"] = 100
        src = source or FakeSource()
        return ReportService(
            selection=SourceSelection(src, "v1", (), src.probe()),
            pricing_provider=pricing or FakePricingProvider(),
            account_provider=None,
            cache_repository=CacheRepository(db),
            config=config,
            now_ms=now_ms,
        ), config

    def test_prompt_projection_restores_breakdown_additional_model_and_abort_timeline(self):
        snapshot = make_snapshot()
        invocations = tuple(
            replace(item, model=ModelRef("github-copilot", "claude-test", "Claude Test"))
            if item.invocation_id == "i_child" else
            replace(item, tokens=TokenUsage(), cost=CostObservation(Decimal(0), "USD", CostKind.PROVIDER_REPORTED))
            if item.invocation_id == "i_next" else item
            for item in snapshot.invocations
        )
        messages = tuple(replace(item, error_name="AbortedError") if item.message_id == "a_next" else item for item in snapshot.messages)
        source = FakeSource(replace(snapshot, invocations=invocations, messages=messages, source_revision="step9-parity"))
        service, config = self._service(source)
        report = service.build(ReportRequest(ReportKind.SESSION, session_id="root"))
        block = report.prompt_blocks[0]
        subtask = next(row for row in block.rows if row.event_id == "u_sub")
        aborted = next(row for row in block.rows if row.event_id == "u_next")
        self.assertTrue(subtask.has_cost_breakdown)
        # Claude Test: (20 input * 200 + 5 output * 600) / 1M CCost.
        self.assertEqual(Decimal("0.0070"), subtask.subagent_ccost)
        self.assertEqual(Decimal("0.30"), subtask.billed_cost)
        self.assertTrue(subtask.has_additional_model)
        self.assertTrue(aborted.aborted)
        self.assertGreater(aborted.abort_at_ms, 0)
        out = io.StringIO()
        ReportRenderer(config, stream=out, color_enabled=False).render(report)
        text = out.getvalue()
        self.assertIn("Main:", text)
        self.assertIn("Subagents:", text)
        self.assertIn("[ABORTED]", text)
        self.assertIn("Additional model(s)", text)

    def test_compaction_and_watch_effort_semantics_remain_independent(self):
        tier = PricingTier(per_million_input=Decimal(1), per_million_cache_read=Decimal("0.1"), per_million_output=Decimal(4))
        model = ModelPricing(ModelRef("github-copilot", "gpt-5.6", "GPT-5.6"), "USD", tiers=(tier,), metadata={"publisher":"OpenAI"})
        prices = replace(sample_catalog(), models=(model,))
        self.assertEqual("GPT-5.6", compaction_model_timeline_name(prices, "gpt-5.6", ""))
        self.assertEqual("GPT-5.6 (Default)", watch_model_timeline_name(prices, "gpt-5.6", "github-copilot", ""))

    def test_recent_model_notice_and_release_flag_use_seven_day_window(self):
        provider = FakePricingProvider()
        provider.catalog = replace(provider.catalog, models=tuple(
            replace(item, metadata={**dict(item.metadata), "release_date":"2026-09-25"})
            if item.model.model == "gpt-test" else item
            for item in provider.catalog.models
        ))
        service, _ = self._service(pricing=provider, now_ms=NOW_MS)
        report = service.build(ReportRequest())
        self.assertIn("* New Models: GPT Test", report.recent_model_notice)
        self.assertTrue(next(row for row in report.model_comparison if row.model == "GPT Test").recent)

    def test_native_quota_does_not_manufacture_usage_or_local_budget(self):
        service, _ = self._service(now_ms=NOW_MS)
        quota = service._accounts_quotas(None, today_prompt_count=2, today_session_count=1)
        self.assertFalse(hasattr(quota, "configured_monthly_budget"))
        self.assertEqual(2, quota.today_prompt_count)
        self.assertEqual(0, quota.today_request_count, "Native account capacity cannot manufacture observed requests")

    def test_session_auto_follow_runtime_stops_when_running_prompt_completes(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(make_snapshot(running=True))
            config, selection, service, _ = make_service(td, source, now_ms=2_200)
            clock = [2_200]
            coordinator = WatchCoordinator(
                selection=selection, report_service=service, config=config, session_id="root",
                clock_ms=lambda: clock[0], sleep=lambda _seconds: None,
            )
            completed = make_snapshot(running=False)
            def finish_prompt(_renderer):
                source.snapshot = replace(completed, source_revision="completed")
                clock[0] = 2_400
            coordinator._v1_wait = finish_prompt  # bounded deterministic test seam
            class Renderer:
                def __init__(self): self.finished = ""; self.renders = 0
                def render(self, _projection): self.renders += 1
                def render_status(self, _projection): pass
                def finish(self, text): self.finished = text
            renderer = Renderer()
            coordinator.run_until_inactive(renderer)
            self.assertGreaterEqual(renderer.renders, 2)
            self.assertEqual("Prompt completed.", renderer.finished)


    def test_report_session_warning_is_header_marker_and_footnote_not_inline_next_ictx(self):
        service, config = self._service()
        report = service.build(ReportRequest(ReportKind.SESSION, session_id="root"))
        block = replace(report.prompt_blocks[0], next_context_warning="Price threshold >100k exceeded")
        report = replace(report, prompt_blocks=(block,))
        out = io.StringIO()
        ReportRenderer(config, stream=out, color_enabled=False).render(report)
        text = out.getvalue()
        header = next(line for line in text.splitlines() if "| *1 " in line)
        self.assertIn("*1", header)
        self.assertNotIn("Price threshold", header)
        self.assertIn("*1 Price threshold >100k exceeded", text)

    def test_watch_renders_recent_notice_warning_marker_and_resolved_effort(self):
        _, config = self._service()
        prompt = PromptProjection(
            at_ms=1_000, prompt_number=1, label="prompt", preview="hello",
            model_effort="GPT-5.6 (Medium)", watch_model_effort="GPT-5.6 (Medium)",
            ccost=Decimal("100"), cost_estimated=False, unresolved_cost=False, calls=1,
            incoming_context_tokens=1_000, incoming_context_ccost=Decimal("1"),
            extra_ccost=Decimal("0"), token_mix_percent=(70, 10, 0, 20),
            next_context_tokens=1_200, delta_context_tokens=200, next_context_warning="price threshold approaching",
        )
        projection = WatchProjection(
            title="Cost Guard Watch", source_label="V2",
            rows=(WatchRow("root", "Root session", prompt, marker="▶"),),
            now_ms=1_500, session_warnings={"root": "price threshold approaching"},
            recent_model_notice="* New Models: GPT-5.6 · released 2026-09-25",
        )
        out = io.StringIO()
        WatchRenderer(config, stream=out, interactive=False).render(projection)
        text = out.getvalue()
        self.assertIn("* New Models: GPT-5.6", text)
        self.assertIn("*1 Root session", text)
        self.assertIn("*1 Next Ictx: price threshold approaching", text)
        self.assertIn("GPT-5.6 (Medium)", text)
        self.assertNotIn("Default -> Medium", text)



class Step9PerformanceTests(unittest.TestCase):
    def test_large_month_second_report_reuses_derived_cache_without_rehydration(self):
        roots = 20
        source = SyntheticMonthSource(roots, 15, month_start_ms=MONTH_START_MS)
        with tempfile.TemporaryDirectory() as td:
            db = CacheDatabase(Path(td)); db.initialize()
            repo = CacheRepository(db)
            config = dict(load_configuration(ROOT).values)
            config["timezone"] = "UTC"
            selection = SourceSelection(source, "v1", (), source.probe())
            first = ReportService(
                selection=selection, pricing_provider=FakePricingProvider(), account_provider=None,
                cache_repository=repo, config=config, now_ms=NOW_MS,
            )
            report = first.build(ReportRequest())
            self.assertEqual(7, source.load_count, "Latest 100 prompts need only seven 15-prompt roots")
            self.assertEqual(100, report.pricing_diagnostics["relcost_sample_prompts"])
            self.assertFalse(report.session_usage)
            first_loads = source.load_count
            first_revisions = source.revision_count
            second = ReportService(
                selection=selection, pricing_provider=FakePricingProvider(), account_provider=None,
                cache_repository=repo, config=config, now_ms=NOW_MS,
            )
            second.build(ReportRequest())
            self.assertEqual(first_loads, source.load_count, "stable month must reuse derived bundles without source hydration")
            self.assertLessEqual(source.revision_count - first_revisions, roots, "second run change proof must remain O(root count)")


if __name__ == "__main__":
    unittest.main()
