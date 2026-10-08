from __future__ import annotations

import io
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from development.tests.test_analysis_core import make_snapshot
from development.tests.test_step6_context_comparisons import catalog as sample_catalog
from src.cache import CacheDatabase, CacheRepository
from src.analysis.context import PriceWarningSeverity
from src.bootstrap import _prepare_console_output
from src.cli import CliUsageError, CommandKind, parse_command
from src.config import load_configuration
from src.domain import (
    AccountUsageStatus, CostDisposition, IntegrationHealth, ModelRef, ModelPricing, ProviderCapabilities, QuotaSnapshot, QuotaWindow,
    QuotaWindowKind, SessionCapabilities,
)
from src.presentation import AnsiStyler, ReportRenderer
from src.presentation.report import _MetricProfile
from src.pricing.catalog import PricingCatalog
from src.reports import ReportKind, ReportRequest, ReportService
from src.reports.service import _chronological_blocks
from src.sources.selection import SourceSelection
from src.version import DISPLAY_VERSION, RELEASE_DATE

ROOT = Path(__file__).resolve().parents[2]


def shifted_snapshot_with_stale_root():
    """Put causal work on 1970-01-02 while root metadata remains on day one."""
    base = make_snapshot()
    shift = 86_400_000

    def shift_part(item):
        return replace(item, created_at_ms=item.created_at_ms + shift, updated_at_ms=item.updated_at_ms + shift)

    messages = tuple(
        replace(
            item,
            created_at_ms=item.created_at_ms + shift,
            completed_at_ms=(item.completed_at_ms + shift if item.completed_at_ms is not None else None),
            parts=tuple(shift_part(part) for part in item.parts),
        )
        for item in base.messages
    )
    parts = tuple(part for message in messages for part in message.parts)
    events = tuple(replace(item, created_at_ms=item.created_at_ms + shift) for item in base.events)
    invocations = tuple(
        replace(
            item,
            created_at_ms=item.created_at_ms + shift,
            completed_at_ms=(item.completed_at_ms + shift if item.completed_at_ms is not None else None),
        )
        for item in base.invocations
    )
    root, child = base.sessions
    root = replace(root, updated_at_ms=5_000)
    child = replace(child, created_at_ms=child.created_at_ms + shift, updated_at_ms=child.updated_at_ms + shift)
    return replace(
        base,
        root=root,
        sessions=(root, child),
        messages=messages,
        parts=parts,
        events=events,
        invocations=invocations,
        source_revision="stale-root-child-active",
    )


class FakeSource:
    source_id = "fake-v1"
    capabilities = SessionCapabilities(native_cost=True, child_sessions=True, compaction_events=True)

    def __init__(self, snapshot=None):
        self.snapshot = snapshot or make_snapshot()

    def probe(self):
        return IntegrationHealth(True, True, "ok")

    def list_sessions(self, since_ms=None):
        values = self.snapshot.sessions
        if since_ms is None:
            return values
        return tuple(item for item in values if item.updated_at_ms >= since_ms)

    def get_session_tree_revision(self, session_id):
        if session_id != self.snapshot.root.session_id:
            raise ValueError("missing")
        return self.snapshot.source_revision

    def load_session_snapshot(self, session_id):
        if session_id != self.snapshot.root.session_id:
            raise ValueError("missing")
        return self.snapshot


class FakePricingProvider:
    provider_id = "github-copilot"
    capabilities = ProviderCapabilities(model_pricing=True, long_context_pricing=True)

    def __init__(self):
        self.catalog = replace(sample_catalog(), retrieved_at_ms=1, source_revision="prices-1")

    def probe(self):
        return IntegrationHealth(True, True, "ok")

    def get_model_pricing(self):
        return self.catalog.models

    def get_catalog(self, force=False):
        return self.catalog


class FakeAccountProvider:
    provider_id = "github-copilot"
    display_name = "GitHub Copilot"
    capabilities = ProviderCapabilities(account_quota=True)

    def probe(self):
        return IntegrationHealth(True, True, "ok")

    def get_quota_snapshot(self):
        return QuotaSnapshot(
            provider="github-copilot", fetched_at_ms=4_000, capabilities=self.capabilities,
            windows=(QuotaWindow(
                "monthly_ai_credits", QuotaWindowKind.FIXED,
                used_fraction=Decimal("0.30"), remaining_fraction=Decimal("0.70"),
                native_used=Decimal("30"), native_limit=Decimal("100"), native_unit="AI credits",
            ),), available=True, usage_status=AccountUsageStatus.AVAILABLE,
        )


class CliParityTests(unittest.TestCase):
    def test_legacy_encoded_console_replaces_unsupported_glyphs_without_crashing(self) -> None:
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")
        with patch.object(sys, "stdout", stream):
            _prepare_console_output()
            print("Cost → █")
            stream.flush()
        self.assertEqual(["Cost ? ?"], buffer.getvalue().decode("cp1252").splitlines())

    def test_v77_argument_shape_matrix(self) -> None:
        cases = {
            (): (CommandKind.NORMAL, None, False),
            ("--watch",): (CommandKind.NORMAL, None, True),
            ("-watch",): (CommandKind.NORMAL, None, True),
            ("ses_abc-1",): (CommandKind.SESSION, "ses_abc-1", False),
            ("ses_abc", "--watch"): (CommandKind.SESSION, "ses_abc", True),
            ("2026-09-27",): (CommandKind.DATE, "2026-09-27", False),
            ("2026-09-01:2026-09-27",): (CommandKind.DATE, "2026-09-01:2026-09-27", False),
        }
        for argv, expected in cases.items():
            with self.subTest(argv=argv):
                item = parse_command(argv)
                self.assertEqual(expected, (item.kind, item.target, item.watch))

    def test_invalid_and_duplicate_arguments_fail_closed(self) -> None:
        bad = [
            ("--watch", "-watch"),
            ("2026-09-27", "--watch"),
            ("nonsense",),
            ("ses_a", "ses_b"),
            ("--unknown",),
        ]
        for argv in bad:
            with self.subTest(argv=argv):
                with self.assertRaises(CliUsageError):
                    parse_command(argv)


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

    def test_normal_report_projects_only_models_and_native_quotas(self) -> None:
        report = self.service.build(ReportRequest())
        self.assertEqual(ReportKind.NORMAL, report.kind)
        self.assertTrue(report.model_comparison)
        self.assertFalse(report.session_usage)
        self.assertFalse(report.prompt_blocks)
        self.assertIsNotNone(report.accounts_quotas)
        self.assertEqual(Decimal("30"), report.accounts_quotas.accounts[0].account.quotas[0].used)
        self.assertEqual(0, report.accounts_quotas.comparison_month.observed_requests)

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
        self.assertIsNone(openai.ccost_scopes[0][1], "Quota login alone cannot attribute historical CCost")
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

    def test_renderer_contains_stable_section_and_column_contracts_without_ansi(self) -> None:
        report = self.service.build(ReportRequest())
        stream = io.StringIO()
        ReportRenderer(self.config, stream=stream, color_enabled=False).render(report)
        text = stream.getvalue()
        for expected in (
            "Relative CCost", "GitHub Copilot", "Pricing/cache metadata",
        ):
            self.assertIn(expected, text)
        for excluded in ("## Model comparison", "Monthly usage", "Today's user prompts", "Daily CCost", "## Accounts & quotas", "CCost today", "CCost month", "Sample:"):
            self.assertNotIn(excluded, text)
        self.assertNotIn("\x1b[", text)
        self.assertNotIn("GitHub USD/M I/C/W/O", text)
        self.assertNotIn("Copilot CCost/M tokens I/C/W/O", text)
        self.assertNotIn("Same prompt comparison", text)
        self.assertNotIn("* Current Ictx:", text)

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

    def test_accounts_quota_removes_global_totals_and_local_budget_but_keeps_native_capacity(self) -> None:
        report = self.service.build(ReportRequest())
        stream = io.StringIO()
        ReportRenderer(self.config, stream=stream, color_enabled=False, terminal_width=160).render(report)
        section = stream.getvalue().split("GitHub Copilot", 1)[1]
        self.assertNotIn("Billed today:", section)
        self.assertNotIn("CCost today:", section)
        self.assertNotIn("configured monthly CCost budget", section)
        self.assertIn("70/100 AI credits", section)
        self.assertNotIn("Native", section)
        self.assertIn("█" * 7 + "░" * 3 + "  70%", section)
        self.assertNotIn("Difference", section)

    def test_renderer_restores_responsive_width_without_truncating_session_id_or_numeric_cells(self) -> None:
        report = self.service.build(ReportRequest(ReportKind.SESSIONS))
        session = report.session_usage[0]
        protected_id = "ses_0123456789ABCDEF"
        report = replace(report, session_usage=(replace(
            session, session_id=protected_id,
            title="A deliberately very long session title that must flex and truncate",
            model="A deliberately very long model display name that must flex",
        ),))
        stream = io.StringIO()
        ReportRenderer(self.config, stream=stream, color_enabled=False, terminal_width=100).render(report)
        text = stream.getvalue()
        self.assertTrue(text.startswith(f"# Cost Guard {DISPLAY_VERSION} ({RELEASE_DATE}) — Source: OpenCode V1\n"))
        self.assertIn(protected_id, text)
        self.assertIn("...", text)
        table_lines = [line for line in text.splitlines() if line.startswith("|")]
        self.assertTrue(table_lines)
        self.assertLessEqual(max(map(len, table_lines)), 100)

    def test_v77_table_contract_restores_prompt_numbers_totals_and_cost_cell_format(self) -> None:
        report = self.service.build(ReportRequest(ReportKind.SESSION, session_id="root"))
        # Force fallback provenance flags on representative rows: the visual cost
        # cell contract must remain plain dollars and rely on one report note.
        blocks = tuple(
            replace(block, rows=tuple(replace(item, cost_estimated=True) for item in block.rows))
            for block in report.prompt_blocks
        )
        report = replace(report, prompt_blocks=blocks)
        stream = io.StringIO()
        ReportRenderer(self.config, stream=stream, color_enabled=False, terminal_width=160).render(report)
        lines = stream.getvalue().splitlines()
        table_lines = [line for line in lines if line.startswith("|")]
        self.assertFalse(any("~$" in line for line in table_lines), "cost cells must never encode fallback with ~")
        self.assertTrue(any("#1 " in line for line in table_lines), "ordinary prompt rows keep the v77 #N marker")
        total_indexes = [i for i, line in enumerate(lines) if line.startswith("| ") and line.split("|", 2)[1].strip().startswith("Total")]
        self.assertEqual(len(total_indexes), 1, "Dedicated prompt table retains its Total")
        for index in total_indexes:
            self.assertTrue(set(lines[index - 1]) <= {"|", "-"}, lines[index - 1])

    def test_prompt_diagnostic_approximation_is_in_headers_not_repeated_as_money_prefix(self) -> None:
        report = self.service.build(ReportRequest(ReportKind.SESSION, session_id="root"))
        stream = io.StringIO()
        ReportRenderer(self.config, stream=stream, color_enabled=False, terminal_width=140).render(report)
        prompt_lines = [line for line in stream.getvalue().splitlines() if " next " in line and line.startswith("|")]
        self.assertTrue(prompt_lines)
        cells = [cell.strip() for cell in prompt_lines[0].split("|")[1:-1]]
        self.assertGreaterEqual(len(cells), 7)
        self.assertFalse(cells[4].startswith("~$"), cells)
        self.assertFalse(cells[5].startswith("~$"), cells)

    def test_model_comparison_price_components_are_compact_and_slash_aligned(self) -> None:
        report = self.service.build(ReportRequest(ReportKind.ALL_MODELS))
        stream = io.StringIO()
        ReportRenderer(self.config, stream=stream, color_enabled=False, terminal_width=160).render(report)
        lines = stream.getvalue().splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith("|") and "GitHub USD/M I/C/W/O" in line)
        model_rows = []
        for line in lines[start + 2:]:
            if not line.startswith("|"):
                break
            if line.startswith("|") and not set(line) <= {"|", "-"}:
                model_rows.append(line)
        self.assertGreaterEqual(len(model_rows), 2)
        price_cells = [[cell for cell in row.split("|")[1:-1]][3] for row in model_rows]
        slash_positions = [[i for i, ch in enumerate(cell) if ch == "/"] for cell in price_cells]
        self.assertTrue(all(pos == slash_positions[0] for pos in slash_positions[1:]))
        self.assertTrue(any("0.1" in cell for cell in price_cells), price_cells)

    def test_prompt_mix_colors_are_component_scoped_like_v77(self) -> None:
        report = self.service.build(ReportRequest(ReportKind.SESSION, session_id="root"))
        block = report.prompt_blocks[0]
        ordinary = [row for row in block.rows if not row.is_compaction]
        self.assertGreaterEqual(len(ordinary), 2)
        rewritten = []
        ordinary_index = 0
        for row in block.rows:
            if row.is_compaction:
                rewritten.append(row)
                continue
            if ordinary_index == 0:
                rewritten.append(replace(row, ccost=Decimal("10"), token_mix_percent=(90, 10, 0, 0)))
            else:
                rewritten.append(replace(row, ccost=Decimal("90"), token_mix_percent=(10, 90, 0, 0)))
            ordinary_index += 1
        config = dict(self.config)
        thresholds = dict(config["thresholds"]); thresholds["promptCostMinSamples"] = 2; config["thresholds"] = thresholds
        report = replace(report, prompt_blocks=(replace(block, rows=tuple(rewritten)),))
        stream = io.StringIO()
        ReportRenderer(config, stream=stream, color_enabled=True, terminal_width=140).render(report)
        row = next(line for line in stream.getvalue().splitlines() if "#1 " in line)
        mix_cell = row.split("|")[-2]
        self.assertIn("\x1b[", mix_cell)
        self.assertIn("\x1b[0m/10/0/0", mix_cell, "only the high I component should own its color")

    def test_negative_and_positive_ictx_deltas_align_on_the_arrow(self) -> None:
        report = self.service.build(ReportRequest(ReportKind.SESSION, session_id="root"))
        block = report.prompt_blocks[0]
        rewritten = []
        ordinary_index = 0
        for row in block.rows:
            if row.is_compaction:
                rewritten.append(row)
                continue
            if ordinary_index == 0:
                rewritten.append(replace(row, delta_context_tokens=-142100, next_context_tokens=40800))
            elif ordinary_index == 1:
                rewritten.append(replace(row, delta_context_tokens=4500, next_context_tokens=45300))
            else:
                rewritten.append(row)
            ordinary_index += 1
        self.assertGreaterEqual(ordinary_index, 2)
        report = replace(report, prompt_blocks=(replace(block, rows=tuple(rewritten)),))
        stream = io.StringIO()
        ReportRenderer(self.config, stream=stream, color_enabled=False, terminal_width=160).render(report)
        lines = [line for line in stream.getvalue().splitlines() if line.startswith("|") and "#" in line and " → " in line]
        self.assertGreaterEqual(len(lines), 2)
        cells = [line.split("|")[4] for line in lines[:2]]
        self.assertEqual(cells[0].index(" → "), cells[1].index(" → "), cells)
        self.assertIn("-142k → 41k", cells[0])
        self.assertIn("+5k → 45k", cells[1])
        self.assertNotIn(".0k", "".join(cells))

    def test_v77_percentile_and_quota_warning_thresholds_are_preserved(self) -> None:
        thresholds = self.config["thresholds"]
        profile = _MetricProfile((Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"), Decimal("5")), thresholds)
        self.assertIsNone(profile.role(Decimal("2")))
        self.assertEqual("promptCostP50", profile.role(Decimal("3")))
        self.assertEqual("promptCostP75", profile.role(Decimal("4")))
        self.assertEqual("promptCostP90", profile.role(Decimal("5")))

    def test_next_ictx_warning_colors_share_economic_warning_semantics(self) -> None:
        report = self.service.build(ReportRequest(ReportKind.SESSION, session_id="root"))
        block = report.prompt_blocks[0]
        styler = AnsiStyler(self.config["colors"], enabled=True)

        approaching = replace(report, prompt_blocks=(replace(block, next_context_warning="Approaching price threshold >100k",
                              next_context_warning_severity=PriceWarningSeverity.APPROACHING),))
        stream = io.StringIO()
        ReportRenderer(self.config, stream=stream, color_enabled=True, terminal_width=160).render(approaching)
        next_line = next(line for line in stream.getvalue().splitlines() if "* Next Ictx:" in line)
        self.assertIn(styler.apply("* Next Ictx:", "nextIctxWarning").split("* Next Ictx:")[0], next_line)

        exceeded = replace(report, prompt_blocks=(replace(block, next_context_warning="Price threshold >100k exceeded",
                           next_context_warning_severity=PriceWarningSeverity.EXCEEDED),))
        stream = io.StringIO()
        ReportRenderer(self.config, stream=stream, color_enabled=True, terminal_width=160).render(exceeded)
        next_line = next(line for line in stream.getvalue().splitlines() if "* Next Ictx:" in line)
        self.assertIn(styler.apply("* Next Ictx:", "nextIctxWarning").split("* Next Ictx:")[0], next_line)

    def test_semantic_color_roles_remain_independently_resolved(self) -> None:
        colors = self.config["colors"]
        self.assertNotEqual(colors["activeRunning"], colors["nextIctxWarningReason"])
        styler = AnsiStyler(colors, enabled=True)
        running = styler.apply("X", "activeRunning")
        warning = styler.apply("X", "nextIctxWarningReason")
        self.assertNotEqual(running, warning)
        self.assertTrue(running.startswith("\x1b["))
        self.assertTrue(warning.endswith("\x1b[0m"))


if __name__ == "__main__":
    unittest.main()
