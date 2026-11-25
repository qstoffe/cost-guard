"""Shared report projections for models, sessions, attribution and accounts."""
from __future__ import annotations

import io
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.report_runtime import (
    FakeSource, FakePricingProvider, FakeAccountProvider, shifted_snapshot_with_stale_root,
)
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.domain import (
    AccountUsageStatus, CostDisposition, IntegrationHealth, ModelRef, ProviderCapabilities, QuotaSnapshot, QuotaWindow,
    QuotaWindowKind,
)
from src.presentation import ReportRenderer
from src.reports import ReportKind, ReportRequest, ReportService
from src.reports.service import _chronological_blocks
from src.sources.selection import SourceSelection

ROOT = Path(__file__).resolve().parents[2]


class ReportProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        package = Path(self.tmp.name)
        database = CacheDatabase(package)
        database.initialize()
        self.repo = CacheRepository(database)
        loaded = load_configuration(ROOT)
        self.config = dict(loaded.values)
        self.config["timezone"] = "UTC"
        self.config["monthlyAiCredits"] = 100
        self.source = FakeSource()
        selection = SourceSelection(self.source, "v1", (), self.source.probe())
        self.service = ReportService(
            selection=selection,
            pricing_provider=FakePricingProvider(),
            account_provider=FakeAccountProvider(),
            cache_repository=self.repo,
            config=self.config,
            now_ms=4_000,
        )

    def make_service(self, source, *, pricing_provider=None, now_ms=4_000):
        selection = SourceSelection(source, "v1", (), source.probe())
        return ReportService(
            selection=selection,
            pricing_provider=pricing_provider or FakePricingProvider(),
            account_provider=FakeAccountProvider(),
            cache_repository=self.repo,
            config=self.config,
            now_ms=now_ms,
        )

    def test_normal_report_projects_models_and_independent_account_periods(self) -> None:
        report = self.service.build(ReportRequest())
        self.assertEqual(ReportKind.NORMAL, report.kind)
        self.assertTrue(report.model_comparison)
        self.assertFalse(report.session_usage)
        self.assertFalse(report.prompt_blocks)
        self.assertIsNotNone(report.accounts_quotas)
        self.assertEqual(Decimal("30"), report.accounts_quotas.accounts[0].account.quotas[0].used)
        self.assertEqual(5, report.accounts_quotas.comparison_month.observed_requests)

    def test_v2_openai_provider_usage_is_included_in_local_cost_and_prompt_attribution(self) -> None:
        snapshot = make_snapshot()
        messages = tuple(
            replace(item, model=replace(item.model, provider="openai") if item.model else None)
            for item in snapshot.messages
        )
        events = []
        for item in snapshot.events:
            metadata = dict(item.metadata)
            if "provider_id" in metadata:
                metadata["provider_id"] = "openai"
            events.append(replace(item, metadata=metadata))
        invocations = tuple(
            replace(item, model=replace(item.model, provider="openai"))
            for item in snapshot.invocations
        )
        source = FakeSource(replace(
            snapshot, messages=messages, events=tuple(events), invocations=invocations,
            source_revision="v2-openai-provider-regression",
        ))
        service = self.make_service(source)
        sessions = service.build(ReportRequest(ReportKind.SESSIONS))
        self.assertEqual(1, len(sessions.session_usage))
        self.assertGreater(sessions.session_usage[0].ccost, Decimal("0"))
        report = service.build(ReportRequest(ReportKind.SESSION, session_id="root"))
        prompt_rows = [row for block in report.prompt_blocks for row in block.rows if not row.is_compaction]
        self.assertTrue(any(row.calls > 0 and row.ccost > 0 for row in prompt_rows))

    def test_session_and_date_modes_filter_without_reimplementing_analysis(self) -> None:
        session = self.service.build(ReportRequest(ReportKind.SESSION, session_id="child"))
        self.assertEqual("Session child", session.title)
        self.assertEqual("root", session.prompt_blocks[0].session_id)
        date = self.service.build(ReportRequest(ReportKind.DATE, date_text="1970-01-01"))
        self.assertEqual(ReportKind.DATE, date.kind)
        self.assertTrue(date.prompt_blocks)
        self.assertIn("CCost for range", date.notes[0])

    def test_date_candidate_selection_uses_descendant_activity_not_only_root_timestamp(self) -> None:
        source = FakeSource(shifted_snapshot_with_stale_root())
        now_ms = 2 * 86_400_000
        service = self.make_service(source, now_ms=now_ms)
        report = service.build(ReportRequest(ReportKind.DATE, date_text="1970-01-02"))
        self.assertTrue(report.prompt_blocks, "child activity must keep the root causal tree eligible")
        self.assertEqual("root", report.prompt_blocks[0].session_id)

    def test_sessions_report_keeps_available_archived_roots(self) -> None:
        snapshot = make_snapshot()
        archived_root = replace(snapshot.root, archived_at_ms=3_500)
        source = FakeSource(replace(
            snapshot, root=archived_root,
            sessions=(archived_root,) + tuple(snapshot.sessions[1:]),
            source_revision="archived-root-current-month",
        ))
        report = self.make_service(source).build(ReportRequest(ReportKind.SESSIONS))
        self.assertEqual(1, len(report.session_usage))
        self.assertEqual("root", report.session_usage[0].session_id)
        self.assertGreater(report.session_usage[0].ccost, Decimal(0))
        self.assertIsNone(report.accounts_quotas)

    def test_session_primary_model_is_selected_by_attributed_spend_not_request_count(self) -> None:
        snapshot = make_snapshot()
        invocations = tuple(
            replace(item, model=ModelRef("github-copilot", "claude-test"), tokens=replace(item.tokens, input=2_000_000),
                    cost=replace(item.cost, amount=Decimal("2.00")))
            if item.invocation_id == "i_next" else item
            for item in snapshot.invocations
        )
        source = FakeSource(replace(snapshot, invocations=invocations, source_revision="spend-primary"))
        report = self.make_service(source).build(ReportRequest(ReportKind.SESSIONS))
        self.assertEqual("Claude Test", report.session_usage[0].model)
        self.assertTrue(report.session_usage[0].multiple_models)

    def test_model_comparison_renders_flat_provider_neutral_rates_without_explicit_tiers(self) -> None:
        provider = FakePricingProvider()
        flat_models = tuple(replace(model, tiers=()) for model in provider.catalog.models)
        provider.catalog = replace(provider.catalog, models=flat_models)
        report = self.make_service(FakeSource(), pricing_provider=provider).build(ReportRequest())
        self.assertTrue(report.model_comparison)
        self.assertNotEqual("N/A", report.model_comparison[0].price_summary)

    def test_model_comparison_preserves_sample_across_month_boundaries(self) -> None:
        report = self.make_service(FakeSource(), now_ms=40 * 86_400_000).build(ReportRequest())
        self.assertEqual(2, len(report.model_comparison))
        self.assertTrue(all(item.relative_cost is not None for item in report.model_comparison))
        self.assertEqual(2, report.model_comparison_sample_size)
        stream = io.StringIO()
        ReportRenderer(self.config, stream=stream, color_enabled=False, terminal_width=160).render(report)
        comparison = stream.getvalue()
        model_lines = [line for line in comparison.splitlines() if "Claude Test" in line or "GPT Test" in line]
        self.assertTrue(all(line.split("|")[3].strip().endswith("x") for line in model_lines))

    def test_daily_blocks_are_ordered_by_latest_visible_event_oldest_to_newest(self) -> None:
        report = self.service.build(ReportRequest(ReportKind.DATE, date_text="1970-01-01"))
        block = report.prompt_blocks[0]
        older = replace(block, session_id="older", rows=(replace(block.rows[0], at_ms=100),))
        newer = replace(block, session_id="newer", rows=(replace(block.rows[0], at_ms=300),))
        middle = replace(block, session_id="middle", rows=(replace(block.rows[0], at_ms=200),))
        ordered = _chronological_blocks((newer, older, middle))
        self.assertEqual(["older", "middle", "newer"], [item.session_id for item in ordered])

    def test_openai_subscription_is_separate_from_billed_cost_and_has_equivalent_windows(self) -> None:
        class OpenAIAccount:
            provider_id = "openai"
            included_usage = False
            capabilities = ProviderCapabilities(account_quota=True, reset_windows=True)
            def probe(self): return IntegrationHealth(True, True, "oauth")
            def get_quota_snapshot(self):
                return QuotaSnapshot(
                    provider="openai", fetched_at_ms=4_000, capabilities=self.capabilities,
                    plan="plus", windows=(QuotaWindow(
                        "5-hour", QuotaWindowKind.ROLLING,
                        used_fraction=Decimal("0.25"), remaining_fraction=Decimal("0.75"),
                        reset_at_ms=5_000, duration_seconds=18_000,
                    ),), available=True, usage_status=AccountUsageStatus.AVAILABLE,
                )

        snapshot = make_snapshot()
        invocations = tuple(replace(
            item, model=replace(item.model, provider="openai"),
            cost=replace(item.cost, amount=Decimal("0")),
            cost_disposition=CostDisposition.INCLUDED_SUBSCRIPTION,
        ) for item in snapshot.invocations)
        messages = tuple(replace(item, model=replace(item.model, provider="openai") if item.model else None) for item in snapshot.messages)
        events = tuple(replace(item, metadata={**dict(item.metadata), "provider_id": "openai"}) for item in snapshot.events)
        source = FakeSource(replace(snapshot, invocations=invocations, messages=messages, events=events, source_revision="subscription"))
        selection = SourceSelection(source, "v2", (), source.probe())
        service = ReportService(
            selection=selection, pricing_provider=FakePricingProvider(), account_provider=FakeAccountProvider(),
            account_providers=(FakeAccountProvider(), OpenAIAccount()), cache_repository=self.repo,
            config=self.config, now_ms=4_000,
        )
        quota = service.build_watch_quota()
        self.assertEqual(Decimal("0"), quota.billed_month)
        self.assertGreater(quota.comparison_month.ccost, 0)
        self.assertGreater(quota.included_subscription_requests, 0)
        openai = next(item for item in quota.accounts if item.account.ref.provider_id == "openai")
        self.assertEqual("plus", openai.account.plan)
        self.assertEqual(5, openai.ccost_scopes[0][1].observed_requests)
        self.assertIn('today', openai.ccost_estimated_scopes)
        self.assertIn('not verified account/billing attribution', openai.ccost_notes[0])
        # Acquired Today remains independent of an unavailable longer quota period;
        # a sole-provider estimate still does not establish historical account proof.
        report = service.build(ReportRequest())
        stream = io.StringIO()
        ReportRenderer(self.config, stream=stream, color_enabled=False, terminal_width=160).render(report)
        self.assertNotIn("~5-hour full", stream.getvalue())
        self.assertNotIn("~5-hour remaining", stream.getvalue())
        self.assertFalse(any("Current-price fallback" in note for note in report.notes))

    def test_openai_oauth_quota_does_not_prove_unknown_invocations_are_subscription_usage(self) -> None:
        from src.accounts.openai_subscription import OpenAIAccountProvider

        self.assertFalse(OpenAIAccountProvider.included_usage)
        class OAuthQuota:
            provider_id = "openai"
            capabilities = OpenAIAccountProvider.capabilities
            def probe(self): return IntegrationHealth(True, True, "oauth")
            def get_quota_snapshot(self):
                return QuotaSnapshot(
                    provider="openai", fetched_at_ms=4_000, capabilities=self.capabilities,
                    available=True, usage_status=AccountUsageStatus.AVAILABLE,
                )

        snapshot = make_snapshot()
        invocations = tuple(replace(
            item, model=replace(item.model, provider="openai"),
            cost=replace(item.cost, amount=Decimal("0")),
        ) for item in snapshot.invocations)
        source = FakeSource(replace(snapshot, invocations=invocations, source_revision="unknown-openai"))
        service = ReportService(
            selection=SourceSelection(source, "v2", (), source.probe()), pricing_provider=FakePricingProvider(),
            account_provider=FakeAccountProvider(), account_providers=(FakeAccountProvider(), OAuthQuota()),
            cache_repository=self.repo, config=self.config, now_ms=4_000,
        )
        quota = service.build_watch_quota()
        self.assertEqual(0, quota.included_subscription_requests)
        self.assertIsNone(quota.billed_month)
        self.assertGreater(quota.comparison_month.ccost, Decimal(0))
        self.assertIsNotNone(next(item for item in quota.accounts if item.account.ref.provider_id == "openai"))

    def test_model_comparison_restores_pricing_metadata_and_promotion_note(self) -> None:
        pricing = FakePricingProvider()
        models = list(pricing.catalog.models)
        first = models[0]
        metadata = dict(first.metadata)
        metadata.update({
            "promotion_active": "true",
            "promotion_expires_ms": str(86_400_000),
            "promotion_discount_percent": "50",
        })
        models[0] = replace(first, metadata=metadata)
        pricing.catalog = replace(pricing.catalog, models=tuple(models), retrieved_at_ms=1_000)
        report = self.make_service(FakeSource(), pricing_provider=pricing).build(ReportRequest())
        promoted = next(row for row in report.model_comparison if row.model == (first.model.display_name or first.model.model))
        self.assertEqual(1, promoted.promotion_marker)
        self.assertNotIn("*1", promoted.price_summary)

        stream = io.StringIO()
        ReportRenderer(self.config, stream=stream, color_enabled=False, terminal_width=160).render(report)
        text = stream.getvalue()
        self.assertIn("Pricing/cache metadata: 1970-01-01 00:00", text)
        self.assertIn(
            "*1 Price Promotion: GPT Test — 50% off standard GitHub Copilot rates through 1970-01-01; "
            "standard pricing resumes 1970-01-02.",
            text,
        )


if __name__ == "__main__":
    unittest.main()
