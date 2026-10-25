"""Synthetic OAuth switch regressions; no real credentials or paid requests."""
from contextlib import closing
from dataclasses import replace
import base64
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from development.tests.fixtures.account_workers import wait_for
from development.tests.fixtures.quota_rendering import quotas, report_text, watch_text
from src.accounts.acquisition import AccountAcquisition
from src.accounts.discovery import AccountDiscovery
from src.accounts.diagnostics import sanitized_account_observation
from src.accounts.openai_subscription import OpenAIAccountProvider, UsageResponse, USAGE_URL
from src.accounts.credentials import provider_credentials
from src.reports.models import AccountProjection
from src.watch.accounts import reconcile_accounts


def oauth(account, token=None, **extra):
    return {"type": "oauth", "access": token or "synthetic-" + account, "accountId": account, **extra}


def usage(plan="pro_lite"):
    return UsageResponse(True, 200, {"plan_type": plan, "rate_limit": {
        "primary_window": {"used_percent": 25, "limit_window_seconds": 18000},
        "secondary_window": {"used_percent": 60, "limit_window_seconds": 604800}}})


class OpenAISwitchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.auth = self.root / "auth.json"
        self.db = self.root / "opencode.db"
        self.auth.write_text("{}", encoding="utf-8")
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("CREATE TABLE credential(id TEXT, integration_id TEXT, value TEXT, active INTEGER)")
            conn.commit()

    def rows(self, rows):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("DELETE FROM credential")
            conn.executemany("INSERT INTO credential VALUES(?,?,?,?)",
                             [(key, provider, json.dumps(value), active) for key, provider, value, active in rows])
            conn.commit()

    def provider(self, get=lambda *_: usage()):
        provider = OpenAIAccountProvider(usage_get=get, now_ms=lambda: 1000)
        provider.auth_json_path, provider.credential_db_path = self.auth, self.db
        return provider

    def test_restart_canonical_v2_suppresses_stale_legacy_alias_and_deduplicates_v2_alias(self):
        self.auth.write_text(json.dumps({"codex": oauth("old"), "openai": oauth("old")}))
        self.rows([("new", "openai", oauth("new"), 1),
                   ("alias", "openai-codex", oauth("new", "stale-alias"), 0)])
        calls = []
        provider = self.provider(lambda url, token, account, timeout: (calls.append((url, token, account)), usage())[1])
        before = self.db.read_bytes(), self.auth.read_bytes()
        engine = AccountAcquisition((provider,), "fixture")
        self.addCleanup(engine.close)
        engine.start(1000)
        snapshots = engine.finish(1000)
        self.assertEqual(["new"], [s.ref.account_id for s in snapshots])
        self.assertEqual([(USAGE_URL, "synthetic-new", "new")], calls)
        self.assertEqual("pro_lite", snapshots[0].plan)
        self.assertEqual("available", snapshots[0].availability)
        self.assertEqual(2, len(snapshots[0].quotas))
        self.assertEqual(before, (self.db.read_bytes(), self.auth.read_bytes()))

    def test_jwt_alias_identity_without_metadata_and_true_two_accounts(self):
        payload = base64.urlsafe_b64encode(json.dumps({"https://api.openai.com/auth": {
            "chatgpt_account_id": "one"}}).encode()).decode().rstrip("=")
        self.rows([("one", "openai", oauth("one"), 1),
                   ("alias", "codex", {"type": "oauth", "access": "e30." + payload + ".fixture"}, 1),
                   ("two", "openai", oauth("two"), 0)])
        snapshots = self.provider().get_account_snapshots()
        self.assertEqual({"one", "two"}, {s.ref.account_id for s in snapshots})
        self.assertEqual(2, len(snapshots))

    def test_unusable_canonical_record_does_not_resurrect_legacy_oauth(self):
        self.auth.write_text(json.dumps({"codex": oauth("old")}))
        self.rows([("new", "openai", {"type": "oauth"}, 1)])
        snapshots = self.provider(lambda *_: self.fail("must not try stale auth")).get_account_snapshots()
        self.assertEqual(1, len(snapshots))
        self.assertFalse(snapshots[0].quotas)
        self.assertEqual("unavailable", snapshots[0].availability)

    def test_watch_removal_and_replacement_discards_inflight_old_response(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        calls = []

        def get(url, token, account, timeout):
            calls.append(account)
            if len(calls) == 2:
                entered.set()
                release.wait(2)
            return usage("plus" if account == "old" else "pro_lite")

        self.rows([("old", "openai", oauth("old"), 1)])
        engine = AccountAcquisition((self.provider(get),), "fixture")
        self.addCleanup(engine.close)
        engine.start(1000)
        old = engine.finish(1000)
        engine.poll(1000)
        engine.start(2000)
        self.assertTrue(entered.wait(1))
        self.rows([])
        engine.start(3000)
        removed = engine.poll(3000)
        shown, seen, _ = reconcile_accounts(old, removed.snapshots, {old[0].key: 1000},
                                            now_ms=3000, observed_keys=removed.observed_keys)
        self.assertEqual((), shown)
        self.assertEqual({}, seen)
        self.rows([("new", "openai", oauth("new"), 1)])
        engine.start(4000)
        release.set()
        wait_for(lambda: (engine.poll(4000), bool(engine.snapshots))[1])
        self.assertEqual(["new"], [s.ref.account_id for s in engine.snapshots])
        self.assertEqual("pro_lite", engine.snapshots[0].plan)
        self.assertEqual(["old", "old", "new"], calls)

    def test_replacement_without_empty_inventory_removes_old_key_in_same_update(self):
        self.rows([("old", "openai", oauth("old"), 1)])
        engine = AccountAcquisition((self.provider(),), "fixture")
        self.addCleanup(engine.close)
        engine.start(1000)
        old = engine.finish(1000)
        engine.poll(1000)
        self.rows([("new", "openai", oauth("new"), 1)])
        engine.start(2000)
        updates = []

        def completed():
            update = engine.poll(2000)
            if update is not None:
                updates.append(update)
            return any(s.ref.account_id == "new" for s in engine.snapshots)

        wait_for(completed)
        self.assertEqual(["new"], [s.ref.account_id for s in engine.snapshots])
        observed = {key for update in updates for key in update.observed_keys}
        self.assertIn(old[0].key, observed)
        shown, _, _ = reconcile_accounts(old, engine.snapshots, {}, now_ms=2000,
                                         observed_keys=tuple(observed))
        self.assertEqual(["new"], [s.ref.account_id for s in shown])

    def test_rejected_current_generation_recovers_only_after_external_refresh(self):
        calls = []

        def get(url, token, account, timeout):
            calls.append((token, account))
            return usage() if (token, account) == ("current-token", "new") else UsageResponse(False, 401)

        self.rows([("same-row", "openai", oauth("old", "stale-token"), 1)])
        provider = self.provider(get)
        engine = AccountAcquisition((provider,), "fixture")
        self.addCleanup(engine.close)
        engine.start(1000)
        failed = engine.finish(1000)[0]
        self.assertEqual("auth_failure", failed.observations["parser_reason"])
        self.assertEqual(401, failed.observations["http_status"])
        self.assertFalse(failed.quotas)
        self.rows([("same-row", "openai", oauth("new", "current-token"), 1)])
        engine.start(2000)
        recovered = engine.finish(2000)
        self.assertEqual([("stale-token", "old"), ("current-token", "new")], calls)
        self.assertEqual("available", recovered[0].availability)
        evidence = repr(engine.diagnostics()) + repr(recovered)
        for secret in ("stale-token", "current-token"):
            self.assertNotIn(secret, evidence)

    def test_403_network_parser_and_expiration_are_truthful_and_nonsecret(self):
        self.rows([("one", "openai", oauth("one"), 1)])
        for response, reason in ((UsageResponse(False, 403), "access_denied"),
                                 (UsageResponse(False, network_error=True), "network_failure"),
                                 (UsageResponse(True, 200, {}), "parser_failure"),
                                 (UsageResponse(False, 200), "parser_failure")):
            with self.subTest(reason=reason):
                snapshot = self.provider(lambda *_: response).get_account_snapshots()[0]
                self.assertEqual(reason, snapshot.observations["parser_reason"])
                self.assertFalse(snapshot.quotas)
                self.assertNotEqual("available", snapshot.availability)
        self.rows([("one", "openai", oauth("one", expires=0), 1)])
        expired = self.provider(lambda *_: self.fail("expired credential must not be sent")).get_account_snapshots()[0]
        self.assertEqual("credential_expired", expired.observations["parser_reason"])

    def test_unknown_or_absent_plan_does_not_discard_valid_windows_or_invent_tier(self):
        self.rows([("one", "openai", oauth("one"), 1)])
        for plan in ("novel_2026", None, "bad\nplan"):
            with self.subTest(plan=plan):
                snapshot = self.provider(lambda *_: usage(plan)).get_account_snapshots()[0]
                self.assertEqual("available", snapshot.availability)
                self.assertEqual(2, len(snapshot.quotas))
                self.assertEqual(plan if plan == "novel_2026" else None, snapshot.plan)

    def test_watch_does_not_restore_previous_plan_or_quota_after_failed_lookup(self):
        self.rows([("one", "openai", oauth("one"), 1)])
        old = self.provider(lambda *_: usage("plus")).get_account_snapshots()
        unknown = self.provider(lambda *_: usage(None)).get_account_snapshots()
        shown, seen, _ = reconcile_accounts(old, unknown, {old[0].key: 1000}, now_ms=2000)
        self.assertIsNone(shown[0].plan)
        failed = self.provider(lambda *_: UsageResponse(False, network_error=True)).get_account_snapshots()
        shown, _, stale = reconcile_accounts(shown, failed, seen, now_ms=3000)
        self.assertEqual("error", shown[0].availability)
        self.assertFalse(shown[0].quotas)
        self.assertFalse(stale)

    def test_partial_openai_response_does_not_restore_missing_old_fraction(self):
        self.rows([("one", "openai", oauth("one"), 1)])
        old = self.provider().get_account_snapshots()
        partial = replace(old[0], availability="partial", quotas=(replace(old[0].quotas[0], remaining_fraction=None),))
        shown, _, stale = reconcile_accounts(old, (partial,), {old[0].key: 1000}, now_ms=2000)
        self.assertIsNone(shown[0].quotas[0].remaining_fraction)
        self.assertEqual(1, len(shown[0].quotas))
        self.assertFalse(stale)

    def test_token_sharing_and_future_methods_never_send_tokens_to_wham(self):
        for method, metadata, category in (
            ("chatgpt-token-sharing", {}, "token-sharing"),
            ("chatgpt-browser", {"scopes": ["chatgpt.tokens.use.direct", "resource.invoke"]}, "token-sharing"),
            ("future-private-method", {}, "unknown"),
        ):
            with self.subTest(method=method):
                self.rows([("one", "openai", oauth("one", "private-token", methodID=method,
                                                  metadata=metadata, expires=5000), 1)])
                provider = self.provider(lambda *_: self.fail("incompatible resource must not be called"))
                account = provider.get_account_snapshots()[0]
                self.assertEqual("unavailable", account.availability)
                self.assertFalse(account.quotas)
                self.assertIsNone(account.plan)
                self.assertEqual(category, account.observations["credential_category"])
                evidence = sanitized_account_observation(account)["quota_shape"]
                self.assertFalse(evidence["request_attempted"])
                self.assertEqual("none", evidence["endpoint_family"])
                self.assertEqual("unsupported_auth_method", evidence["parser_reason"])
                self.assertNotIn("private-token", repr(account) + repr(evidence))
                self.assertNotIn("future-private-method", repr(account) + repr(evidence))
                # Legacy direct callers must obey the same method eligibility.
                provider.auth_json_path.write_text(json.dumps({"openai": oauth("one", methodID=method, metadata=metadata)}))
                provider.credential_db_path = None
                self.assertFalse(provider.get_quota_snapshot().available)

    def test_scope_claim_without_method_blocks_legacy_fallback_and_missing_header_is_not_guessed(self):
        payload = base64.urlsafe_b64encode(json.dumps({"scope": "resource.invoke chatgpt.tokens.use.direct"}).encode()).decode().rstrip("=")
        self.rows([("one", "openai", {"type": "oauth", "access": "e30." + payload + ".fixture"}, 1)])
        account = self.provider(lambda *_: self.fail("scope rules out WHAM")).get_account_snapshots()[0]
        self.assertFalse(account.observations["account_header_present"])
        self.assertEqual("token-sharing", account.observations["credential_category"])

    def test_method_guidance_is_actionable_once_on_both_surfaces_and_never_guessed(self):
        for method in ("chatgpt-token-sharing", "chatgpt-browser", "chatgpt-headless", None,
                       "future-method", "api", "legacy-401"):
            with self.subTest(method=method):
                value = ({"type": "api", "key": "synthetic-api-key"} if method == "api" else
                         oauth("one", "private-token", **({} if method is None else
                               {"methodID": "chatgpt-browser" if method == "legacy-401" else method})))
                self.rows([("one", "openai", value, 1)])
                calls = []
                def get(*_args):
                    calls.append(True)
                    return UsageResponse(False, 401) if method == "legacy-401" else usage()
                before = self.db.read_bytes(), self.auth.read_bytes()
                native = self.provider(get).get_account_snapshots()[0]
                quota = quotas(AccountProjection(native, "OpenAI"))
                for width in (80, 120, 160):
                    for text in (report_text(quota, width=width), watch_text(quota, width=width)):
                        plain = " ".join(text.split())
                        for label in ("Codex browser (legacy)", "Codex device code (legacy)"):
                            self.assertEqual(1 if method == "chatgpt-token-sharing" else 0, plain.count(label))
                        if method == "chatgpt-token-sharing":
                            self.assertIn("For now, try", plain)
                            self.assertIn("Model access and Codex quota access use different authentication", plain)
                            self.assertIn("quota availability is not guaranteed", plain)
                            self.assertIn("API keys also do not provide Codex subscription quota", plain)
                        self.assertNotIn("private-token", text)
                        self.assertNotIn("synthetic-api-key", text)
                        self.assertTrue(all(len(line) <= width for line in text.splitlines()))
                self.assertEqual(before, (self.db.read_bytes(), self.auth.read_bytes()))
                self.assertEqual(0 if method in {"api", "future-method", "chatgpt-token-sharing"} else 1, len(calls))

    def test_active_sharing_and_inactive_legacy_remain_distinct_without_alias_fallback(self):
        self.auth.write_text(json.dumps({"codex": oauth("stale")}))
        self.rows([("active", "openai", {"type": "oauth", "access": "sharing", "methodID": "chatgpt-token-sharing"}, 1),
                   ("inactive", "openai", oauth("other", methodID="chatgpt-headless"), 0)])
        calls = []
        provider = self.provider(lambda url, token, account, timeout: (calls.append(account), usage())[1])
        records = provider_credentials(provider, provider.integration_ids)
        self.assertEqual([False, True], sorted(r.active for r in records))
        accounts = provider.get_account_snapshots()
        self.assertEqual(["other"], calls)
        self.assertEqual(2, len(accounts))
        self.assertEqual({"available", "unavailable"}, {a.availability for a in accounts})

    def test_legacy_methods_preserve_quota_without_required_account_header(self):
        for method in ("chatgpt-browser", "chatgpt-headless"):
            with self.subTest(method=method):
                self.rows([("one", "openai", {"type": "oauth", "access": "legacy", "methodID": method}, 1)])
                calls = []
                account = self.provider(lambda url, token, account, timeout: (calls.append((url, account)), usage())[1]).get_account_snapshots()[0]
                self.assertEqual([(USAGE_URL, "")], calls)
                self.assertEqual("available", account.availability)
                self.assertEqual(2, len(account.quotas))
                self.assertTrue(account.observations["request_attempted"])

    def test_watch_method_switch_clears_native_quota_and_matches_report_acquisition(self):
        self.rows([("one", "openai", oauth("one", methodID="chatgpt-browser"), 1)])
        engine = AccountAcquisition((self.provider(),), "fixture")
        self.addCleanup(engine.close)
        engine.start(1000)
        old = engine.finish(1000)
        self.rows([("one", "openai", oauth("one", methodID="chatgpt-token-sharing"), 1)])
        engine.start(2000)
        new = engine.finish(2000)
        shown, _, stale = reconcile_accounts(old, new, {old[0].key: 1000}, now_ms=2000)
        report = self.provider().get_account_snapshots()
        self.assertEqual(report, shown)
        self.assertFalse(stale)
        self.assertFalse(shown[0].quotas)
        self.assertIsNone(shown[0].plan)
        self.assertEqual("unsupported_auth_method", shown[0].observations["parser_reason"])

    def test_quota_rejection_does_not_diagnose_model_login_and_throttling_is_separate(self):
        self.rows([("one", "openai", oauth("one", methodID="chatgpt-browser"), 1)])
        rejected = self.provider(lambda *_: UsageResponse(False, 401)).get_account_snapshots()[0]
        self.assertNotIn("reconnect", rejected.observations["user_action"].lower())
        limited = self.provider(lambda *_: UsageResponse(False, 429)).get_account_snapshots()[0]
        self.assertEqual("rate_limited", limited.observations["parser_reason"])
        self.assertFalse(limited.quotas)


if __name__ == "__main__":
    unittest.main()
