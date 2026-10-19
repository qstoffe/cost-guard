"""Run-isolated, privacy-safe quota history without changing acquisition policy."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from development.fixtures.account_workers import ControlledQuota, wait_for
from development.tools.collect_diagnostics import _text_summary
from development.tools.diagnostic_logs import create_bundle
from src.accounts.acquisition import AccountAcquisition
from src.accounts.claude_code import ClaudeCodeAccountProvider
from src.accounts.claude_transport import ClaudeUsageResult
from src.accounts.quota_observations import HISTORY_LIMIT, SERIES_LIMIT, QuotaObservations
from src.accounts.refresh_loop import AccountRefreshLoop
from src.cache.account_refresh_state import STATE_FILE, persist_refresh_state, read_refresh_state
from src.domain import AccountRef, AccountSnapshot, QuotaComponent


def account(*, identity="private@example.invalid", percent="15", reset=18_000_000):
    return AccountSnapshot(AccountRef("private-source", "claude-code", identity), 0, "Private email",
                           quotas=(QuotaComponent("private quota text", remaining_fraction=Decimal(percent) / 100,
                                                  reset_at_ms=reset, duration_seconds=18_000),))


class QuotaObservationTests(unittest.TestCase):
    def setUp(self):
        self.clock = [0.0]
        self.provider = ControlledQuota(self.clock, name="claude-code")
        self.provider.snapshot = account()
        self.loop = AccountRefreshLoop((self.provider,), "private-source", clock=lambda: self.clock[0],
                                       wall_ms=lambda: int(1_800_000_000_000 + self.clock[0] * 1000))
        self.addCleanup(self.loop.close)
        self.addCleanup(self.provider.gate.set)

    def step(self, start, *, publish=True):
        self.clock[0] = start
        self.loop.tick()
        wait_for(lambda: self.provider.starts and self.provider.starts[-1] == start)
        self.clock[0] = start + .429
        self.provider.gate.set()
        wait_for(lambda: not self.loop.engine._results.empty())
        self.loop.tick()
        if publish:
            self.loop.poll(self.loop.wall_ms())
        return self.loop.engine.observations.diagnostics(self.loop.wall_ms())["series"][-1]

    def test_ten_minute_unchanged_success_then_direct_fifteen_to_one_transition(self):
        for start in range(0, 601, 30):
            series = self.step(start)
        history = series["history"]
        self.assertEqual([15] * 21, [item["remaining_percent"] for item in history])
        self.assertIsNone(history[0]["value_changed"])  # Baseline, not an invented change.
        self.assertTrue(all(item["value_changed"] is False for item in history[1:]))
        self.assertTrue(all(item["outcome"] == "success" for item in history))
        self.assertEqual(self.loop.wall_ms(), series["last_successful_retrieval_ms"])
        self.assertIsNone(series["last_value_change_ms"])
        self.assertEqual(600, series["observed_unchanged_seconds"])
        self.assertEqual("fresh", self.loop.diagnostics()["providers"]["0"]["freshness"])
        self.assertEqual(0, self.loop.engine.refresh[0].retries)
        self.provider.snapshot = account(percent="1")
        series = self.step(630, publish=False)
        self.assertEqual(1, series["history"][-1]["remaining_percent"])
        self.assertTrue(series["history"][-1]["value_changed"])
        self.assertEqual(self.loop.wall_ms(), series["last_value_change_ms"])
        self.assertEqual(0, series["value_change_age_seconds"])
        self.assertLess(series["last_watch_publication_ms"], series["last_successful_retrieval_ms"])
        self.loop.poll(self.loop.wall_ms())
        series = self.loop.engine.observations.diagnostics(self.loop.wall_ms() + 5000)["series"][0]
        self.assertEqual(self.loop.wall_ms(), series["last_watch_publication_ms"])
        self.assertEqual(5, series["value_change_age_seconds"])
        self.assertEqual(list(range(0, 631, 30)), self.provider.starts)

    def test_errors_timeouts_and_recovery_do_not_become_value_changes_or_success(self):
        good = self.provider.snapshot
        first = self.step(0)
        self.provider.snapshot = replace(good, availability="error", quotas=(),
                                         observations={"parser_reason": "transport_failure"})
        failed = self.step(30)
        self.assertEqual("transient_failure", failed["history"][-1]["outcome"])
        self.assertEqual(first["last_successful_retrieval_ms"], failed["last_successful_retrieval_ms"])
        self.clock[0] = 36
        self.loop.tick()
        wait_for(lambda: self.provider.starts[-1] == 36)
        self.clock[0] = 56
        self.loop.tick()
        timed = self.loop.engine.observations.diagnostics(self.loop.wall_ms())["series"][0]
        self.assertEqual("timeout", timed["history"][-1]["outcome"])
        self.assertIsNone(timed["history"][-1]["remaining_percent"])
        self.provider.gate.set()
        wait_for(lambda: not self.loop.engine._results.empty())
        self.loop.tick()  # Expired result is ignored, not a late success.
        self.provider.snapshot = good
        recovered = self.step(66)
        self.assertEqual("success", recovered["history"][-1]["outcome"])
        self.assertFalse(recovered["history"][-1]["value_changed"])
        self.assertIsNone(recovered["last_value_change_ms"])

    def test_identity_switch_and_reset_boundaries_keep_distinct_baselines(self):
        self.step(0)
        self.provider.snapshot = account(identity="different private identity", percent="1")
        series = self.step(30)
        self.assertIsNone(series["history"][0]["value_changed"])
        self.assertEqual(2, len(self.loop.engine.observations.diagnostics(self.loop.wall_ms())["series"]))
        self.provider.snapshot = account(identity="different private identity", percent="1", reset=36_000_000)
        reset = self.step(60)
        self.assertFalse(reset["history"][-1]["value_changed"])
        self.assertTrue(reset["history"][-1]["reset_changed"])
        self.assertIsNone(reset["last_value_change_ms"])
        self.assertEqual(36_000_000, reset["history"][-1]["reset_at_ms"])

    def test_history_covers_thirty_minutes_and_is_bounded_even_when_identities_churn(self):
        evidence = QuotaObservations(continuous=True)
        for index in range(100):
            evidence.record(0, None, (account(),), at_ms=index * 30_000, duration=.429, outcome="success")
        series = evidence.diagnostics(3_000_000)["series"][0]
        self.assertEqual(HISTORY_LIMIT, len(series["history"]))
        self.assertGreaterEqual(series["history"][-1]["observed_at_ms"] - series["history"][0]["observed_at_ms"], 1_800_000)
        for index in range(100):
            evidence.record(0, None, (account(identity=str(index)),), at_ms=3_000_000, duration=0, outcome="success")
        self.assertEqual(SERIES_LIMIT, len(evidence.diagnostics(3_000_000)["series"]))

    def test_persistence_privacy_and_concurrent_writer_isolation(self):
        self.step(0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = self.loop.engine.diagnostics()
            observation = raw["quota_observations"]
            observation["secret"] = "PRIVATE"
            series = observation["series"][0]
            series["account_email"] = "PRIVATE"
            series["history"][0]["response"] = "PRIVATE"
            persist_refresh_state(root, raw)
            result = read_refresh_state(root)["evidence"]["quota_observations"]
            self.assertEqual(15, result["series"][0]["history"][0]["remaining_percent"])
            for secret in ("PRIVATE", "private@example", "private-source", "private quota", "Private email"):
                self.assertNotIn(secret, (root / STATE_FILE).read_text(encoding="utf-8"))
            other = QuotaObservations(continuous=True)
            other.record(0, None, (account(percent="1"),), at_ms=1000, duration=0, outcome="success")
            persist_refresh_state(root, {"quota_observations": other.diagnostics(1000)})
            latest = read_refresh_state(root)["evidence"]["quota_observations"]
            self.assertNotEqual(result["run_id"], latest["run_id"])
            self.assertEqual(1, len(latest["series"][0]["history"]))
            self.assertIsNone(latest["series"][0]["last_value_change_ms"])

    def test_independent_report_acquisition_calls_claude_again_and_never_reads_watch_history(self):
        auth = {"loggedIn": True, "apiProvider": "firstParty", "authMethod": "claude.ai",
                "subscriptionType": "pro", "email": "synthetic@example.invalid", "orgName": "Synthetic"}
        calls = []

        def usage():
            calls.append(1)
            rates = {"five_hour": {"utilization": 85 if len(calls) == 1 else 99,
                                    "resets_at": "2026-10-19T15:00:00+02:00"},
                     "seven_day": {"utilization": 0, "resets_at": None}}
            return ClaudeUsageResult({"email": auth["email"], "organization": "Synthetic", "apiProvider": "firstParty"},
                                     {"rate_limits_available": True, "rate_limits": rates})

        results = []
        for _ in range(2):
            provider = ClaudeCodeAccountProvider(auth_reader=lambda: auth, usage_reader=usage)
            work = AccountAcquisition((provider,), "fixture")
            self.addCleanup(work.close)
            work.start(0)
            work.finish(0, remaining_wait=2)
            results.append(work.diagnostics()["quota_observations"])
            work.close()
        self.assertEqual(2, len(calls))
        self.assertNotEqual(results[0]["run_id"], results[1]["run_id"])
        self.assertEqual([15, 1], [item["series"][0]["history"][0]["remaining_percent"] for item in results])
        self.assertEqual(int(datetime(2026, 10, 19, 13, tzinfo=timezone.utc).timestamp() * 1000),
                         results[0]["series"][0]["history"][0]["reset_at_ms"])
        self.assertTrue(all(item["origin"] == "report" for item in results))
        self.assertTrue(all(item["series"][0]["last_watch_publication_ms"] is None for item in results))

    def test_untrusted_persisted_fields_are_strictly_allowlisted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = {"quota_observations": {"run_id": "a" * 32, "upstream_freshness": "current",
                   "series": [{"provider_id": "private@example.invalid", "series_id": True,
                               "history": [{"remaining_percent": float("nan"), "observed_at_ms": 10**400, "outcome": {},
                                            "value_changed": "PRIVATE"}] * 100}] * 100}}
            persist_refresh_state(root, raw)
            result = read_refresh_state(root)["evidence"]["quota_observations"]
            self.assertEqual("unknown", result["upstream_freshness"])
            self.assertEqual(64, len(result["series"]))
            self.assertEqual(64, len(result["series"][0]["history"]))
            self.assertNotIn("series_id", result["series"][0])
            self.assertNotIn("private@", json.dumps(result))
            self.assertNotIn("PRIVATE", json.dumps(result))

    def test_existing_diagnostics_zip_carries_history_and_explanatory_summary(self):
        self.step(0)
        self.provider.snapshot = account(percent="1")
        self.step(30)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            persist_refresh_state(root, self.loop.diagnostics())
            data = {"cost_guard": {"version": "fixture"}, "generated_at_utc": "fixture",
                    "environment": {"python_version": "fixture", "platform": "fixture"},
                    "watch_account_refresh": read_refresh_state(root)}
            bundle = root / "diagnostics.zip"
            create_bundle(bundle, root=root, json_bytes=json.dumps(data).encode("utf-8"),
                          text_bytes=_text_summary(data).encode("utf-8"), include_logs=False, cleanup_old=False)
            with zipfile.ZipFile(bundle) as archive:
                stored = json.loads(archive.read("diagnostics.json"))
                summary = archive.read("summary.txt").decode("utf-8")
            series = stored["watch_account_refresh"]["evidence"]["quota_observations"]["series"][0]
            self.assertEqual([15, 1], [item["remaining_percent"] for item in series["history"]])
            self.assertIn("upstream freshness is unknown", summary)
            self.assertIn("2/2 successful observations", summary)
            self.assertIn("latest persisted writer only", summary)

    def test_credential_revision_and_unknown_values_never_invent_transitions(self):
        evidence = QuotaObservations(continuous=True)
        good = account()
        evidence.record(0, 1, (good,), at_ms=1000, duration=0, outcome="success")
        evidence.record(0, 2, (good,), at_ms=2000, duration=0, outcome="success")
        unknown = replace(good, quotas=(replace(good.quotas[0], remaining_fraction=None),), availability="partial")
        evidence.record(0, 2, (unknown,), at_ms=3000, duration=0, outcome="success")
        evidence.published({good.key: 3000}, 4000)
        series = evidence.diagnostics(4000)["series"]
        self.assertEqual(2, len(series))
        self.assertIsNone(series[0]["last_watch_publication_ms"])
        self.assertEqual(4000, series[1]["last_watch_publication_ms"])
        self.assertEqual(3000, series[1]["last_successful_retrieval_ms"])
        self.assertIsNone(series[1]["history"][-1]["value_changed"])
        self.assertIsNone(series[1]["last_value_change_ms"])

    def test_other_provider_values_remain_unmodified(self):
        good = account()
        evidence = QuotaObservations()
        for provider in ("openai", "github-copilot", "anthropic", "minimax", "deepseek", "openrouter"):
            original = replace(good, ref=replace(good.ref, provider_id=provider))
            evidence.record(0, None, (original,), at_ms=1000, duration=.429, outcome="success")
            self.assertEqual(good.quotas, original.quotas)
        self.assertEqual(6, len(evidence.diagnostics(1000)["series"]))

    def test_reset_timestamp_jitter_does_not_hide_unchanged_percentage_age(self):
        evidence = QuotaObservations()
        for index in range(21):
            evidence.record(0, None, (account(reset=18_000_000 + index),),
                            at_ms=index * 30_000, duration=.429, outcome="success")
        series = evidence.diagnostics(600_000)["series"][0]
        self.assertEqual(600, series["observed_unchanged_seconds"])
        self.assertIsNone(series["last_value_change_ms"])
        self.assertTrue(all(item["value_changed"] is False for item in series["history"][1:]))
        self.assertTrue(all(item["reset_changed"] is True for item in series["history"][1:]))

    def test_report_wait_deadline_records_running_and_queued_timeouts(self):
        providers = (self.provider, ControlledQuota(self.clock, name="openai"),
                     ControlledQuota(self.clock, name="github-copilot"))
        for provider in providers:
            self.addCleanup(provider.gate.set)
        work = AccountAcquisition(providers, "fixture", workers=1, clock=lambda: self.clock[0],
                                  wall_ms=lambda: 100_000)
        self.addCleanup(work.close)
        work.start(100_000)
        wait_for(lambda: self.provider.starts == [0])
        snapshots = work.finish(100_000, remaining_wait=0)
        series = work.diagnostics()["quota_observations"]["series"]
        self.assertEqual(3, len(snapshots))
        self.assertTrue(all(item.availability == "error" for item in snapshots))
        self.assertEqual({"claude-code", "openai", "github-copilot"}, {item["provider_id"] for item in series})
        self.assertTrue(all(item["history"][-1]["outcome"] == "timeout" for item in series))
        self.assertTrue(all(item["history"][-1]["acquisition_seconds"] is None
                            for item in series if item["provider_id"] != "claude-code"))


if __name__ == "__main__":
    unittest.main()
