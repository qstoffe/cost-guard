"""Application/CLI projection parity, immutable privacy boundary and job ownership."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from development.tests.fixtures.accounts import account, NormalizedProvider
from development.tests.fixtures.opencode_v1_database import create_v1_database
from development.tests.fixtures.opencode_v2_service import source_with_current_service
from development.tests.fixtures.report_runtime import FakeSource, FakePricingProvider, FakeAccountProvider
from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.analysis.token_mix import TokenMix
from src.analysis.valuation import ComparisonCost
from src.application import ReportApplication
from src.application.contracts import freeze
from src.application.projection import comparison, token_mix
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.domain import AccountRef, ModelRef, TokenUsage
from src.reports import ReportKind, ReportRequest, ReportService
from src.pricing.base import PricingUnavailableError
from src.sources.errors import FailureCode, SourceUnavailableError
from src.sources.opencode_v1 import OpenCodeV1Source
from src.sources.selection import SourceSelection

ROOT = Path(__file__).resolve().parents[2]


class ApplicationReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        database = CacheDatabase(Path(self.tmp.name))
        database.initialize()
        self.cache = CacheRepository(database)
        self.source = FakeSource()
        self.pricing = FakePricingProvider()
        self.provider = FakeAccountProvider()
        self.config = dict(load_configuration(ROOT).values, timezone="UTC")
        self.services = []

    def factory(self, now, progress):
        service = ReportService(
            selection=SourceSelection(self.source, "v2" if self.source.source_id.endswith("v2") else "v1",
                                      (), self.source.probe()),
            pricing_provider=self.pricing, account_provider=self.provider, cache_repository=self.cache,
            config=self.config, now_ms=now, progress=progress,
        )
        self.services.append(service)
        return service

    def assert_parity(self, request, *, now=4000):
        old = self.factory(now, lambda _: None)
        report = (old.build_token_mix_history() if request.kind is ReportKind.TOKEN_MIX else old.build(request))
        result = ReportApplication(self.factory, clock=lambda: now).execute(request)
        self.assertIsNone(result.error)
        view = result.to_json()["view"]
        self.assertEqual(report.kind.value, view["kind"])
        self.assertEqual(report.token_mix.totals, tuple(view["token_mix"]["totals"]))
        self.assertEqual(tuple(str(x) if x is not None else None for x in report.token_mix.shares),
                         tuple(view["token_mix"]["shares"]))
        for expected, actual in zip(report.session_usage, view["session_usage"], strict=True):
            self.assertEqual((expected.session_id, expected.ccost, expected.duration_ms, expected.complete),
                             (actual["session_id"], Decimal(actual["ccost"]), actual["duration_ms"], actual["complete"]))
        for expected, actual in zip(report.model_comparison, view["model_comparison"], strict=True):
            self.assertEqual(expected.relative_cost,
                              Decimal(actual["relative_cost"]) if actual["relative_cost"] is not None else None)
            self.assertEqual((expected.publisher, expected.model, expected.price_summary, expected.release_date,
                              expected.promotional, expected.recent, expected.promotion_marker),
                             tuple(actual[name] for name in ("publisher", "model", "price_summary", "release_date",
                                   "promotional", "recent", "promotion_marker")))
            self.assertEqual([(str(level.relative_cost) if level.relative_cost is not None else None,
                               level.threshold_tokens, level.threshold_operator) for level in expected.relative_levels],
                             [(level["relative_cost"], level["threshold_tokens"], level["threshold_operator"])
                              for level in actual["relative_levels"]])
        for expected, actual in zip(report.model_token_mix, view["model_token_mix"], strict=True):
            self.assertEqual((expected.model, expected.calls, expected.prompts),
                             (actual["model"], actual["calls"], actual["prompts"]))
            self.assertEqual(expected.mix.totals, tuple(actual["mix"]["totals"]))
        for expected, actual in zip(report.prompt_blocks, view["prompt_blocks"], strict=True):
            self.assertEqual(expected.total_ccost, Decimal(actual["total_ccost"]))
            self.assertEqual(expected.duration_ms, actual["duration_ms"])
            for row, dto in zip(expected.rows, actual["rows"], strict=True):
                self.assertEqual((row.event_id, row.ccost, row.calls, row.duration_ms, row.in_progress,
                                  row.aborted, row.is_compaction, row.billed_cost),
                                 (dto["event_id"], Decimal(dto["ccost"]), dto["calls"], dto["duration_ms"],
                                  dto["in_progress"], dto["aborted"], dto["is_compaction"],
                                  Decimal(dto["billed_cost"]) if dto["billed_cost"] is not None else None))
                for field in ("incoming_context_ccost", "extra_ccost", "next_context_cost_multiplier"):
                    self.assertEqual(getattr(row, field), Decimal(dto[field]) if dto[field] is not None else None)
                self.assertEqual(row.next_context_warning_severity.value, dto["next_context_warning_severity"])
                self.assertEqual(row.token_mix_percent, tuple(dto["token_mix_percent"])
                                 if dto["token_mix_percent"] is not None else None)
                self.assert_detail_metrics(row, dto)
        if report.accounts_quotas is not None:
            quotas = view["accounts_quotas"]
            self.assertEqual(report.accounts_quotas.comparison_month.known_ccost,
                             Decimal(quotas["comparison_month"]["known_ccost"]))
            for expected, actual in zip(report.accounts_quotas.accounts, quotas["accounts"], strict=True):
                self.assertEqual(expected.account.fetched_at_ms, actual["observation"]["observed_at_ms"])
                self.assertEqual(expected.account.status.value, actual["observation"]["status"])
                self.assertEqual(expected.billed_month, Decimal(actual["billed_month"])
                                  if actual["billed_month"] is not None else None)
                self.assertEqual([(name, cost.known_ccost, cost.complete) for name, cost in expected.ccost_scopes],
                                 [(scope["name"], Decimal(scope["cost"]["known_ccost"]), scope["cost"]["complete"])
                                  for scope in actual["ccost_scopes"]])
                for quota, exported in zip(expected.account.quotas, actual["observation"]["quotas"], strict=True):
                    self.assertEqual((quota.unit, quota.period, quota.reset_at_ms),
                                     (exported["unit"], exported["period"], exported["reset_at_ms"]))
                    self.assertEqual(quota.remaining, Decimal(exported["remaining"])
                                     if exported["remaining"] is not None else None)
                self.assertEqual([(pace.label, pace.per_day) for pace in expected.pace],
                                 [(pace["label"], Decimal(pace["per_day"]) if pace["per_day"] is not None else None)
                                  for pace in actual["pace"]])
        self.assertTrue(all(service._account_work is None for service in self.services))
        json.dumps(result.to_json(), allow_nan=False)
        return result

    def assert_detail_metrics(self, row, dto):
        for name in ("model_effort", "incoming_context_tokens", "delta_context_tokens", "next_context_tokens",
                     "cost_estimated", "unresolved_cost", "main_estimated", "subagent_estimated",
                     "breakdown_known", "has_cost_breakdown", "completed_successfully", "completed_at_ms"):
            self.assertEqual(getattr(row, name), dto[name], name)
        for name in ("main_ccost", "subagent_ccost", "next_context_cached_ccost", "next_context_fresh_ccost"):
            self.assertEqual(getattr(row, name), Decimal(dto[name]) if dto[name] is not None else None, name)

    def test_all_modes_share_existing_semantics_in_both_canonical_generations(self):
        for generation in ("v1", "v2"):
            for running in (False, True):
                self.source = FakeSource(make_snapshot(generation=generation, running=running))
                self.source.source_id = "fake-" + generation
                requests = [ReportRequest(kind) for kind in (ReportKind.NORMAL, ReportKind.ALL_MODELS,
                                                           ReportKind.SESSIONS, ReportKind.TOKEN_MIX)]
                requests += [ReportRequest(ReportKind.SESSION, session_id="child"),
                             ReportRequest(ReportKind.DATE, date_text="1970-01-01:1970-01-02")]
                for request in requests:
                    with self.subTest(generation=generation, running=running, kind=request.kind):
                        self.assert_parity(request)

    def test_native_v1_and_current_v2_sources_use_the_same_facade(self):
        path = Path(self.tmp.name) / "fixture.db"
        create_v1_database(path)
        self.source = OpenCodeV1Source(path)
        self.assert_parity(ReportRequest(ReportKind.SESSION, session_id="ses_root"), now=10_000)
        with source_with_current_service() as (source, _server, _registration):
            self.source = source
            self.assert_parity(ReportRequest(ReportKind.SESSION, session_id="ses_current"), now=10_000)

    def test_complete_detail_history_and_clone_dedup_are_not_watch_samples(self):
        self.source = SyntheticMonthSource(2, 151, month_start_ms=1000)
        first, second = self.source.snapshots.values()
        clone_id = second.root.session_id
        cloned_root = replace(first.root, session_id=clone_id)
        self.source.snapshots[clone_id] = replace(
            first, root=cloned_root, sessions=(cloned_root,),
            messages=tuple(replace(item, session_id=clone_id) for item in first.messages),
            parts=tuple(replace(item, session_id=clone_id) for item in first.parts),
            events=tuple(replace(item, session_id=clone_id) for item in first.events),
            invocations=tuple(replace(item, session_id=clone_id) for item in first.invocations),
            source_revision="cloned-history",
        )
        result = self.assert_parity(ReportRequest(ReportKind.SESSION, session_id=first.root.session_id), now=300_000)
        self.assertEqual(151, len(result.to_json()["view"]["prompt_blocks"][0]["rows"]))
        history = self.assert_parity(ReportRequest(ReportKind.TOKEN_MIX), now=300_000)
        # The available history contains 302 copied records but 151 distinct requests.
        self.assertEqual(151, history.to_json()["view"]["token_mix"]["request_count"])

    def test_missing_prices_and_telemetry_are_not_zero_or_success(self):
        snapshot = make_snapshot(running=True)
        invocations = tuple(replace(item, model=ModelRef("provider", "missing"),
                                    tokens=TokenUsage(output=4, known_fields=("output",)))
                            if item.invocation_id == "i_next" else item for item in snapshot.invocations)
        self.source = FakeSource(replace(snapshot, invocations=invocations, source_revision="missing"))
        result = self.assert_parity(ReportRequest(ReportKind.SESSION, session_id="root"))
        row = next(row for row in result.to_json()["view"]["prompt_blocks"][0]["rows"] if row["event_id"] == "u_next")
        self.assertIsNone(row["incoming_context_ccost"])
        self.assertIsNone(row["extra_ccost"])
        self.assertIsNone(row["token_mix_percent"])
        self.assertTrue(row["unresolved_cost"])

    def test_deep_history_reuses_only_source_config_and_price_bound_analysis(self):
        app = ReportApplication(self.factory, clock=lambda: 4000)
        request = ReportRequest(ReportKind.TOKEN_MIX)
        with patch.object(self.source, "load_session_snapshot", wraps=self.source.load_session_snapshot) as load:
            first = app.execute(request)
            second = app.execute(request)
            self.assertIsNone(first.error)
            self.assertEqual(first.to_json()["view"], second.to_json()["view"])
            self.assertEqual(1, load.call_count)
            self.source.snapshot = replace(self.source.snapshot, source_revision="history-changed")
            self.assertIsNone(app.execute(request).error)
            self.assertEqual(2, load.call_count)
            self.config["timezone"] = "Europe/Stockholm"
            self.assertIsNone(app.execute(request).error)
            self.assertEqual(3, load.call_count)
            models = self.pricing.catalog.models
            changed = replace(models[0], tiers=tuple(replace(tier, per_million_input=Decimal("123.456"))
                                                     for tier in models[0].tiers))
            self.pricing.catalog = replace(self.pricing.catalog, models=(changed, *models[1:]))
            self.assertIsNone(app.execute(request).error)
            self.assertEqual(4, load.call_count)

    def test_aborted_compaction_child_and_subscription_evidence_stay_shared(self):
        snapshot = make_snapshot()
        messages = tuple(replace(item, error_name="MessageAbortedError") if item.message_id == "a_next" else item
                         for item in snapshot.messages)
        self.source = FakeSource(replace(snapshot, messages=messages, source_revision="aborted"))
        self.assert_parity(ReportRequest(ReportKind.SESSION, session_id="root"))
        # Inclusion is independent of positive CCost; explicit account attribution remains canonical.
        from src.domain import CostDisposition
        invocations = tuple(replace(item, cost_disposition=CostDisposition.INCLUDED_SUBSCRIPTION,
                                    cost=replace(item.cost, amount=Decimal(0))) for item in snapshot.invocations)
        self.source = FakeSource(replace(snapshot, invocations=invocations, source_revision="included"))
        self.assert_parity(ReportRequest(ReportKind.SESSION, session_id="root"))

    def test_dst_range_and_independent_account_freshness(self):
        self.config["timezone"] = "Europe/Stockholm"
        first = account("openai", "first")
        second = replace(account("anthropic", "second"), fetched_at_ms=50_000, availability="error",
                         reason="private-error", observations={"parser_reason": "auth_failure"})
        self.provider = NormalizedProvider(first)
        original = self.factory

        def factory(now, progress):
            service = original(now, progress)
            service.account_providers = (NormalizedProvider(first), NormalizedProvider(second))
            return service

        app = ReportApplication(factory, clock=lambda: 100_000)
        result = app.execute(ReportRequest())
        self.assertIsNone(result.error)
        observations = [x["observation"] for x in result.to_json()["view"]["accounts_quotas"]["accounts"]]
        self.assertEqual({50_000, 100_000}, {x["observed_at_ms"] for x in observations})
        failed = next(x for x in observations if x["provider_id"] == "anthropic")
        self.assertEqual("auth_failure", failed["error_code"])
        self.assertEqual("error", failed["availability"])
        self.assertFalse(result.to_json()["source"]["accounts_atomic_with_sessions"])
        spring = app.execute(ReportRequest(ReportKind.DATE, date_text="2026-03-29")).to_json()["scope"]
        autumn = app.execute(ReportRequest(ReportKind.DATE, date_text="2026-10-25")).to_json()["scope"]
        self.assertEqual(23 * 3_600_000, spring["end_ms"] - spring["start_ms"])
        self.assertEqual(25 * 3_600_000, autumn["end_ms"] - autumn["start_ms"])

    def test_exact_decimals_null_zero_and_immutable_detached_export(self):
        value = comparison(ComparisonCost(Decimal("0.123456789123456789"), 2, 1)).to_json()
        self.assertEqual("0.123456789123456789", value["known_ccost"])
        self.assertIsNone(value["ccost"])
        self.assertEqual("0", comparison(ComparisonCost()).to_json()["ccost"])
        self.assertIsNone(token_mix(TokenMix()).to_json()["total_tokens"])
        result = ReportApplication(self.factory, clock=lambda: 4000).execute(ReportRequest(ReportKind.SESSIONS))
        exported = result.to_json()
        exported["view"]["session_usage"].clear()
        self.assertTrue(result.to_json()["view"]["session_usage"])
        with self.assertRaises(FrozenInstanceError):
            result.sequence = 99
        with self.assertRaises(TypeError):
            freeze(self.source.snapshot)

    def test_fresh_jobs_sequences_revision_and_stable_request_ids(self):
        app = ReportApplication(self.factory, clock=lambda: 4000)
        request = ReportRequest(ReportKind.SESSION, session_id="root")
        first = app.execute(request).to_json()
        self.source.snapshot = replace(self.source.snapshot, source_revision="advanced")
        second = app.execute(request).to_json()
        self.assertEqual((1, 2), (first["sequence"], second["sequence"]))
        self.assertEqual(first["instance_id"], second["instance_id"])
        self.assertNotEqual(first["source"]["revisions"], second["source"]["revisions"])
        self.assertEqual(first["view"]["request_identities"], second["view"]["request_identities"])
        self.assertEqual(1, app.execute(ReportRequest(ReportKind.SESSIONS)).sequence)
        self.assertIsNot(self.services[0], self.services[1])

    def test_privacy_excludes_raw_source_provider_and_diagnostic_fields(self):
        secret = "SENSITIVE_BOUNDARY_CANARY"
        native = replace(account(), ref=AccountRef(secret, "openai", source_account=secret),
                         reason=secret, warnings=(secret,), observations={"raw": secret, "parser_reason": secret})
        self.provider = NormalizedProvider(native)
        app = ReportApplication(self.factory, clock=lambda: 100_000)
        result = app.execute(ReportRequest())
        self.assertIsNone(result.error)
        self.assertNotIn(secret, json.dumps(result.to_json()))
        self.assertNotIn("pricing_diagnostics", result.to_json()["view"])

    def test_typed_source_failure_cleanup_and_retry_no_exception_text(self):
        app = ReportApplication(self.factory, clock=lambda: 4000)
        with patch.object(self.source, "list_sessions", side_effect=SourceUnavailableError(
                "SENSITIVE_ERROR", code=FailureCode.TIMEOUT)):
            failed = app.execute(ReportRequest())
        self.assertEqual("connection_timeout", failed.error.code)
        self.assertTrue(failed.error.retryable)
        self.assertIsNone(failed.view)
        self.assertNotIn("SENSITIVE_ERROR", json.dumps(failed.to_json()))
        self.assertIsNone(self.services[-1]._account_work)
        self.assertIsNone(app.execute(ReportRequest()).error)

    def test_reentrant_calls_are_busy_and_live_or_reused_services_not_closed(self):
        app = ReportApplication(self.factory, clock=lambda: 4000)
        nested = []
        result = app.execute(ReportRequest(), progress=lambda _: nested.append(app.execute(ReportRequest())))
        self.assertIsNone(result.error)
        self.assertTrue(nested)
        self.assertTrue(all(item.error.code == "busy" for item in nested))
        service = self.factory(4000, lambda _: None)
        service.enable_watch_accounts()
        with patch.object(service, "close_accounts") as close:
            rejected = ReportApplication(lambda _now, _progress: service).execute(ReportRequest())
        self.assertEqual("service_ownership", rejected.error.code)
        close.assert_not_called()
        service._watch_accounts = False
        reused = ReportApplication(lambda _now, _progress: service)
        self.assertIsNone(reused.execute(ReportRequest()).error)
        self.assertEqual("service_ownership", reused.execute(ReportRequest()).error.code)

    def test_expected_pricing_and_target_failures_are_distinct_from_software_faults(self):
        app = ReportApplication(self.factory, clock=lambda: 4000)
        with patch.object(self.pricing, "get_catalog", side_effect=PricingUnavailableError("PRIVATE")):
            result = app.execute(ReportRequest())
        self.assertEqual("pricing_unavailable", result.error.code)
        self.assertIsNone(self.services[-1]._account_work)
        self.assertEqual("session_not_found", app.execute(
            ReportRequest(ReportKind.SESSION, session_id="absent")).error.code)
        self.assertEqual("invalid_request", app.execute(
            ReportRequest(ReportKind.DATE, date_text="not-a-date")).error.code)
        with patch.object(self.pricing, "get_catalog", side_effect=ValueError("PRIVATE")), \
                patch("src.application.service.recoverable") as log:
            result = app.execute(ReportRequest())
        self.assertEqual("internal_error", result.error.code)
        log.assert_called_once()
        self.assertIsNone(result.view)
        self.assertIsNone(self.services[-1]._account_work)

    def test_cli_startup_never_imports_optional_application_or_web_modules(self):
        code = """
import importlib.abc, runpy, sys
class Absent(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('src.application', 'src.web', 'starlette', 'uvicorn')):
            raise ImportError('Optional application/web dependencies are absent')
sys.meta_path.insert(0, Absent())
import development.tools.collect_diagnostics
sys.argv = ['cost-guard.py', sys.argv[1]]
runpy.run_path('cost-guard.py', run_name='__main__')
"""
        for argument in ("--version", "--help"):
            proc = subprocess.run([sys.executable, "-c", code, argument], cwd=ROOT,
                                  capture_output=True, text=True, timeout=20)
            self.assertEqual(0, proc.returncode, proc.stderr)


if __name__ == "__main__":
    unittest.main()
