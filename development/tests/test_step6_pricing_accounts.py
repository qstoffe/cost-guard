from __future__ import annotations

import json
import sqlite3
from contextlib import closing
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from src.accounts.github_copilot import (
    ENTITLEMENT_URL,
    INTERNAL_USER_URL,
    GitHubCopilotAccountProvider,
    JsonResponse,
    convert_entitlement_payload,
    convert_internal_user_payload,
    credential_from_auth_object,
)
from src.accounts.openai_subscription import (
    OpenAIAccountProvider,
    UsageResponse,
    convert_usage_payload,
    credential_from_auth_object as openai_credential_from_auth_object,
)
from src.cache import CacheDatabase, CacheRepository
from src.domain import AccountUsageStatus, ModelRef, TokenUsage
from src.pricing.github_copilot import GitHubCopilotPricingProvider, parse_pricing_markdown


def pricing_markdown(*, promo: bool = False) -> str:
    rows = "\n".join(
        f"GPT-Test-{i} | GA | Test | Default | Not applicable | ${i}.00 | $0.{i}0 | "
        f"{'$0.50' if i == 1 else 'Not applicable'} | ${i * 2}.00"
        for i in range(1, 6)
    )
    tail = ""
    if promo:
        tail = "\nGPT-Test-1 is available at promotional pricing at 50% off through December 31, 2026.\n"
    return (
        "## OpenAI\n"
        "Model | Release status | Category | Tier | Threshold (input tokens) | Input | Cached input | Cache write | Output\n"
        "--- | --- | --- | --- | --- | --- | --- | --- | ---\n"
        + rows + "\n" + tail
    )


class PricingProviderTests(unittest.TestCase):
    def test_parser_preserves_tiers_and_explicit_cache_write(self) -> None:
        markdown = (
            "## OpenAI\n"
            "Model | Tier | Threshold (input tokens) | Input | Cached input | Cache write | Output\n"
            "--- | --- | --- | --- | --- | --- | ---\n"
            "GPT-X | Default | ≤ 100K | $1 | $0.10 | $0.25 | $4\n"
            "GPT-X | Long | > 100K | $2 | $0.20 | $0.50 | $8\n"
        )
        models = parse_pricing_markdown(markdown)
        self.assertEqual(1, len(models))
        self.assertEqual(2, len(models[0].tiers))
        self.assertEqual(100_000, models[0].tiers[0].max_input_tokens)
        self.assertEqual(100_001, models[0].tiers[1].min_input_tokens)
        self.assertEqual(Decimal("0.50"), models[0].tiers[1].per_million_cache_write)

    def test_catalog_estimator_uses_long_tier_and_cache_write_fallback(self) -> None:
        models = parse_pricing_markdown(
            "## OpenAI\n"
            "Model | Tier | Threshold (input tokens) | Input | Cached input | Cache write | Output\n"
            "--- | --- | --- | --- | --- | --- | ---\n"
            "GPT-X | Default | ≤ 100K | $1 | $0.10 | Not applicable | $4\n"
            "GPT-X | Long | > 100K | $2 | $0.20 | $0.50 | $8\n"
        )
        with tempfile.TemporaryDirectory() as td:
            db = CacheDatabase(Path(td)); db.initialize()
            provider = GitHubCopilotPricingProvider(
                cache=CacheRepository(db), max_age_hours=6,
                fetch_text=lambda url, timeout: pricing_markdown(), now_ms=lambda: 1000,
            )
            # Use a direct catalog from the parser to isolate pricing math.
            from src.pricing.catalog import PricingCatalog
            catalog = PricingCatalog(models)
            low = catalog.estimate(ModelRef("github-copilot", "GPT-X"), TokenUsage(input=10, cache_write=5, output=2))
            high = catalog.estimate(ModelRef("github-copilot", "GPT-X"), TokenUsage(input=100_001, cache_write=5, output=2))
            self.assertEqual(Decimal("0.000023"), low)
            self.assertGreater(high, Decimal("0.20"))
            self.assertIsNotNone(provider)

    def test_official_changelog_exact_model_release_date_fallback(self) -> None:
        from src.pricing.github_copilot import _add_changelog_dates
        from src.domain import ModelPricing, ModelRef
        sample = (
            ModelPricing(ModelRef("github-copilot", "claude-haiku-5-5", "Claude Haiku 5.5"), "USD"),
            ModelPricing(ModelRef("github-copilot", "claude-sonnet-5-5", "Claude Sonnet 5.5"), "USD"),
        )
        feed = """<rss><channel><item><title>Claude Haiku 5.5 in GitHub Copilot</title>
        <pubDate>Wed, 07 Oct 2026 11:00:00 +0000</pubDate></item>
        <item><title>Unrelated AI news</title>
        <pubDate>Wed, 07 Oct 2026 11:00:00 +0000</pubDate></item></channel></rss>"""
        models = _add_changelog_dates(sample, feed)
        self.assertEqual("2026-10-07", models[0].metadata.get("release_date"))
        self.assertFalse(models[1].metadata.get("release_date"))
        self.assertEqual(sample[0].per_million_input, models[0].per_million_input)

    def test_provider_caches_and_uses_last_success_on_refresh_failure(self) -> None:
        calls: list[str] = []
        def fetch(url: str, timeout: int) -> str:
            calls.append(url)
            if "models.json" in url:
                return "{}"
            return pricing_markdown()
        with tempfile.TemporaryDirectory() as td:
            db = CacheDatabase(Path(td)); db.initialize(); repo = CacheRepository(db)
            provider = GitHubCopilotPricingProvider(cache=repo, fetch_text=fetch, now_ms=lambda: 1_000_000)
            first = provider.get_catalog()
            self.assertEqual(5, len(first.models))
            failing = GitHubCopilotPricingProvider(
                cache=repo, max_age_hours=0,
                fetch_text=lambda *_: (_ for _ in ()).throw(OSError("offline")),
                now_ms=lambda: 2_000_000,
            )
            second = failing.get_catalog()
            self.assertEqual(first.source_revision, second.source_revision)

    def test_expired_promotion_restores_inferred_standard_rate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = CacheDatabase(Path(td)); db.initialize(); repo = CacheRepository(db)
            def fetch(url: str, timeout: int) -> str:
                if "models.json" in url: return "{}"
                return pricing_markdown(promo=True)
            before = 1_798_761_600_000  # 2027-01-01T00:00:00Z is expiry; just before it.
            provider = GitHubCopilotPricingProvider(cache=repo, fetch_text=fetch, now_ms=lambda: before - 1)
            active = provider.get_catalog()
            model = active.resolve("GPT-Test-1")
            self.assertEqual("true", model.metadata.get("promotion_active"))
            self.assertEqual(Decimal("1.00"), model.tiers[0].per_million_input)
            self.assertEqual(Decimal(100), active.reference_prices("GPT-Test-1").tiers[0].per_million_input)
            expired = GitHubCopilotPricingProvider(cache=repo, max_age_hours=100000, fetch_text=fetch, now_ms=lambda: before + 1).get_catalog()
            restored = expired.resolve("GPT-Test-1")
            self.assertIsNotNone(restored)
            self.assertEqual("true", restored.metadata.get("expired_promotion_fallback"))
            self.assertEqual(Decimal("2.0"), restored.tiers[0].per_million_input)
            self.assertEqual(Decimal(200), expired.reference_prices("GPT-Test-1").tiers[0].per_million_input)


    def test_promotion_metadata_survives_markup_change_when_rates_still_match(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = CacheDatabase(Path(td)); db.initialize(); repo = CacheRepository(db)
            phase = {"promo": True}
            def fetch(url: str, timeout: int) -> str:
                if "models.json" in url: return "{}"
                return pricing_markdown(promo=phase["promo"])
            now = 1_790_000_000_000
            first = GitHubCopilotPricingProvider(cache=repo, fetch_text=fetch, now_ms=lambda: now).get_catalog()
            self.assertEqual("true", first.resolve("GPT-Test-1").metadata.get("promotion_active"))
            phase["promo"] = False
            refreshed = GitHubCopilotPricingProvider(cache=repo, max_age_hours=0, fetch_text=fetch, now_ms=lambda: now + 1).get_catalog()
            self.assertEqual("true", refreshed.resolve("GPT-Test-1").metadata.get("promotion_active"))

    def test_expired_promotion_fallback_is_applied_when_refresh_is_offline(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = CacheDatabase(Path(td)); db.initialize(); repo = CacheRepository(db)
            def fetch(url: str, timeout: int) -> str:
                if "models.json" in url: return "{}"
                return pricing_markdown(promo=True)
            expiry = 1_798_761_600_000
            GitHubCopilotPricingProvider(cache=repo, fetch_text=fetch, now_ms=lambda: expiry - 1).get_catalog()
            offline = GitHubCopilotPricingProvider(
                cache=repo, max_age_hours=100000,
                fetch_text=lambda *_: (_ for _ in ()).throw(OSError("offline")),
                now_ms=lambda: expiry + 1,
            ).get_catalog()
            model = offline.resolve("GPT-Test-1")
            self.assertEqual("false", model.metadata.get("promotion_active"))
            self.assertEqual("true", model.metadata.get("expired_promotion_fallback"))
            self.assertEqual(Decimal("2.0"), model.tiers[0].per_million_input)
            self.assertEqual(Decimal(200), offline.reference_prices("GPT-Test-1").tiers[0].per_million_input)

    def test_cached_release_date_survives_optional_metadata_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = CacheDatabase(Path(td)); db.initialize(); repo = CacheRepository(db)
            metadata_ok = {"value": True}
            def fetch(url: str, timeout: int) -> str:
                if "models.json" in url:
                    if not metadata_ok["value"]: raise OSError("metadata offline")
                    return json.dumps({"openai/gpt-test-1": {"name":"GPT-Test-1", "release_date":"2026-09-01"}})
                return pricing_markdown()
            first = GitHubCopilotPricingProvider(cache=repo, fetch_text=fetch, now_ms=lambda: 1_790_000_000_000).get_catalog()
            self.assertEqual("2026-09-01", first.resolve("GPT-Test-1").metadata.get("release_date"))
            metadata_ok["value"] = False
            second = GitHubCopilotPricingProvider(cache=repo, max_age_hours=0, fetch_text=fetch, now_ms=lambda: 1_790_000_000_001).get_catalog()
            self.assertEqual("2026-09-01", second.resolve("GPT-Test-1").metadata.get("release_date"))

    def test_month_boundary_forces_refresh_even_with_large_max_age(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = CacheDatabase(Path(td)); db.initialize(); repo = CacheRepository(db)
            calls = {"pricing": 0}
            def fetch(url: str, timeout: int) -> str:
                if "models.json" in url: return "{}"
                calls["pricing"] += 1
                return pricing_markdown()
            sep30 = 1_759_276_740_000  # 2025-09-30 23:59 UTC; exact year is irrelevant to month-boundary logic.
            GitHubCopilotPricingProvider(cache=repo, max_age_hours=100000, fetch_text=fetch, now_ms=lambda: sep30).get_catalog()
            GitHubCopilotPricingProvider(cache=repo, max_age_hours=100000, fetch_text=fetch, now_ms=lambda: sep30 + 120_000).get_catalog()
            self.assertEqual(2, calls["pricing"])


class AccountProviderTests(unittest.TestCase):
    def test_auth_selection_preserves_zero_config_refresh_credential(self) -> None:
        credential = credential_from_auth_object({
            "github-copilot": {"type": "oauth", "refresh": "secret-token"},
        })
        self.assertTrue(credential.available)
        self.assertEqual("github-copilot", credential.provider)
        self.assertEqual("secret-token", credential.token)

    def test_explicit_has_quota_false_is_blocked_but_missing_is_unknown(self) -> None:
        blocked = convert_entitlement_payload({"quotas": {"premiumInteractionsQuota": {"total": 100, "creditsUsed": 20, "hasQuota": False}}}, fetched_at_ms=1)
        unknown = convert_entitlement_payload({"quotas": {"premiumInteractionsQuota": {"total": 100, "creditsUsed": 20}}}, fetched_at_ms=1)
        self.assertTrue(blocked.available)
        self.assertEqual(AccountUsageStatus.BLOCKED, blocked.usage_status)
        self.assertEqual(AccountUsageStatus.UNKNOWN, unknown.usage_status)
        self.assertEqual(1, unknown.fetched_at_ms)

    def test_internal_payload_maps_ai_credits_without_universal_dollar_conversion(self) -> None:
        snap = convert_internal_user_payload({"quota_snapshots": {"premium_interactions": {
            "entitlement": 200, "credits_used": 50, "percent_remaining": 75, "has_quota": True,
        }}, "copilot_plan": "business"}, fetched_at_ms=1)
        self.assertTrue(snap.available)
        self.assertEqual("Business", snap.plan)
        window = snap.windows[0]
        self.assertEqual(Decimal("50"), window.native_used)
        self.assertEqual(Decimal("200"), window.native_limit)
        self.assertEqual("AI credits", window.native_unit)
        self.assertEqual(Decimal("0.25"), window.used_fraction)

    def test_copilot_plan_is_read_even_when_entitlement_quota_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            auth = home / ".local/share/opencode/auth.json"
            auth.parent.mkdir(parents=True)
            auth.write_text(json.dumps({"github-copilot": {"type": "oauth", "refresh": "TOP-SECRET"}}), encoding="utf-8")
            calls = []

            def get(url: str, token: str, copilot: bool, timeout: int) -> JsonResponse:
                calls.append(url)
                if url == ENTITLEMENT_URL:
                    return JsonResponse(True, 200, {"quotas": {"premiumInteractionsQuota": {
                        "total": 100, "creditsUsed": 20, "hasQuota": True,
                    }}})
                return JsonResponse(True, 200, {"copilot_plan": "enterprise", "quota_snapshots": {
                    "premium_interactions": {"entitlement": 200, "credits_used": 50, "has_quota": True},
                }})

            snap = GitHubCopilotAccountProvider(home=home, json_get=get, now_ms=lambda: 99).get_quota_snapshot()
            self.assertEqual([ENTITLEMENT_URL, INTERNAL_USER_URL], calls)
            self.assertEqual("Enterprise", snap.plan)
            self.assertEqual(Decimal("20"), snap.windows[0].native_used, "entitlement remains quota authority")
            self.assertNotIn("TOP-SECRET", repr(snap))

            def plan_offline(url: str, token: str, copilot: bool, timeout: int) -> JsonResponse:
                if url == INTERNAL_USER_URL:
                    return JsonResponse(False, 503, None, True)
                return get(url, token, copilot, timeout)

            fallback = GitHubCopilotAccountProvider(home=home, json_get=plan_offline, now_ms=lambda: 99).get_quota_snapshot()
            self.assertTrue(fallback.available, "plan lookup failure must not hide the primary quota")
            self.assertIsNone(fallback.plan)

    def test_unknown_plan_is_not_echoed_or_guessed(self) -> None:
        snap = convert_internal_user_payload({"copilot_plan": "unrecognized private plan", "quota_snapshots": {
            "premium_interactions": {"entitlement": 200, "credits_used": 50, "has_quota": True},
        }}, fetched_at_ms=1)
        self.assertIsNone(snap.plan)
        base = {"quota_snapshots": {"premium_interactions": {
            "entitlement": 200, "credits_used": 50, "has_quota": True,
        }}, "copilot_plan": "individual_pro"}
        self.assertEqual("Individual", convert_internal_user_payload(base, fetched_at_ms=1).plan)
        self.assertEqual("Pro+", convert_internal_user_payload({
            **base, "access_type_sku": "plus_monthly_subscriber_quota",
        }, fetched_at_ms=1).plan)

    def test_primary_usage_status_overrides_fallback_status_but_fallback_supplies_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            auth = home / ".local/share/opencode/auth.json"
            auth.parent.mkdir(parents=True)
            auth.write_text(json.dumps({"github-copilot": {"type":"oauth", "refresh":"TOP-SECRET"}}), encoding="utf-8")
            def get(url: str, token: str, copilot: bool, timeout: int) -> JsonResponse:
                self.assertEqual("TOP-SECRET", token)
                if url == ENTITLEMENT_URL:
                    return JsonResponse(True, 200, {"quotas": {"premiumInteractionsQuota": {"total": 100, "creditsUsed": None, "hasQuota": False}}})
                self.assertEqual(INTERNAL_USER_URL, url)
                return JsonResponse(True, 200, {"quota_snapshots": {"premium_interactions": {
                    "entitlement": 100, "credits_used": 30, "has_quota": True,
                }}})
            provider = GitHubCopilotAccountProvider(home=home, json_get=get, now_ms=lambda: 99)
            snap = provider.get_quota_snapshot()
            self.assertTrue(snap.available)
            self.assertEqual(AccountUsageStatus.BLOCKED, snap.usage_status)
            self.assertEqual(Decimal("30"), snap.windows[0].native_used)
            self.assertNotIn("TOP-SECRET", repr(snap))

    def test_transport_exception_never_leaks_oauth_token(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td); auth = home / ".local/share/opencode/auth.json"; auth.parent.mkdir(parents=True)
            auth.write_text(json.dumps({"github-copilot": {"type":"oauth", "refresh":"LEAK-ME-NOT"}}), encoding="utf-8")
            provider = GitHubCopilotAccountProvider(
                home=home,
                json_get=lambda url, token, copilot, timeout: (_ for _ in ()).throw(RuntimeError("bad " + token)),
                now_ms=lambda: 5,
            )
            snap = provider.get_quota_snapshot()
            self.assertFalse(snap.available)
            self.assertNotIn("LEAK-ME-NOT", snap.reason)
            self.assertNotIn("LEAK-ME-NOT", repr(snap))

    def test_rejected_sign_in_tells_user_how_to_restore_quota(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td); auth = home / ".local/share/opencode/auth.json"; auth.parent.mkdir(parents=True)
            auth.write_text(json.dumps({"github-copilot": {"type": "oauth", "refresh": "REVOKED-SECRET"},
                                        "openai": {"type": "oauth", "access": "REVOKED-SECRET"}}), encoding="utf-8")
            for status in (401, 403):
                copilot = GitHubCopilotAccountProvider(
                    home=home, json_get=lambda *_: JsonResponse(False, status, None), now_ms=lambda: 5).get_quota_snapshot()
                openai = OpenAIAccountProvider(
                    home=home, usage_get=lambda *_: UsageResponse(False, status), now_ms=lambda: 5).get_quota_snapshot()
                for snap, reason, action in (
                    (copilot, "GitHub Copilot sign-in was rejected; sign in to GitHub Copilot again in OpenCode.",
                     "Sign-in rejected; sign in to GitHub again in OpenCode"),
                    (openai, "OpenAI sign-in was rejected; reconnect OpenAI in OpenCode.",
                     "Sign-in rejected; reconnect OpenAI in OpenCode"),
                ):
                    self.assertEqual((reason, action, "auth_failure"),
                                     (snap.reason, snap.observations["user_action"], snap.observations["parser_reason"]))
                    self.assertNotIn("REVOKED-SECRET", repr(snap))

    def test_openai_usage_maps_windows_by_duration_plan_reset_and_credits(self) -> None:
        snap = convert_usage_payload({
            "plan_type": "plus",
            "rate_limit": {
                "allowed": True,
                "primary_window": {"used_percent": 25, "limit_window_seconds": 18_000, "reset_at": 100},
                "secondary_window": {"used_percent": 40, "limit_window_seconds": 604_800, "reset_at": 200},
            },
            "credits": {"balance": 12.5},
        }, fetched_at_ms=1)
        self.assertTrue(snap.available)
        self.assertEqual("plus", snap.plan)
        self.assertEqual(["5-hour", "weekly"], [window.name for window in snap.windows])
        self.assertEqual(Decimal("0.25"), snap.windows[0].used_fraction)
        self.assertEqual(100_000, snap.windows[0].reset_at_ms)
        self.assertEqual(Decimal("12.5"), snap.credit_balance)

    def test_sanitized_plus_usage_fixture_maps_native_windows(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "fixtures/openai/usage-plus.json"
        snap = convert_usage_payload(json.loads(fixture.read_text(encoding="utf-8")), fetched_at_ms=1000)
        self.assertEqual("plus", snap.plan)
        self.assertEqual(["5-hour", "weekly"], [window.name for window in snap.windows])
        self.assertEqual(Decimal("0.25"), snap.windows[0].used_fraction)
        self.assertEqual(Decimal("0.75"), snap.windows[0].remaining_fraction)
        self.assertEqual(7_201_000, snap.windows[0].reset_at_ms)
        self.assertEqual(Decimal(0), snap.credit_balance)

    def test_active_v2_openai_oauth_supplies_quota_without_auth_json(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "fixtures/openai/usage-plus.json"
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "opencode.db"
            with closing(sqlite3.connect(db)) as conn:
                conn.execute("CREATE TABLE credential (integration_id TEXT, active INTEGER, time_updated INTEGER, value TEXT)")
                for active, updated, token in ((0, 20, "INACTIVE-SECRET"), (1, 10, "ACTIVE-SECRET")):
                    conn.execute("INSERT INTO credential VALUES (?, ?, ?, ?)", (
                        "openai", active, updated, json.dumps({
                            "type": "oauth", "access": token, "expires": 20_000_000_000_000,
                            "metadata": {"accountID": "synthetic-account"},
                        }),
                    ))
                conn.commit()
            original = db.read_bytes()
            calls = []
            def usage(url, token, account_id, timeout):
                calls.append((url, token, account_id))
                return UsageResponse(True, 200, payload)
            provider = OpenAIAccountProvider(home=Path(td), credential_db_path=db, usage_get=usage, now_ms=lambda: 1000)
            self.assertTrue(provider.probe().healthy)
            snapshot = provider.get_quota_snapshot()
            self.assertEqual("plus", snapshot.plan)
            self.assertEqual(["5-hour", "weekly"], [window.name for window in snapshot.windows])
            self.assertEqual(1, len(calls))
            self.assertEqual(("ACTIVE-SECRET", "synthetic-account"), calls[0][1:])
            self.assertNotIn("ACTIVE-SECRET", repr(snapshot))
            self.assertNotIn("ACTIVE-SECRET", repr(provider.probe()))
            self.assertEqual(original, db.read_bytes(), "credential storage must remain read-only")

    def test_expired_active_v2_oauth_never_switches_to_other_identity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "opencode.db"
            with closing(sqlite3.connect(db)) as conn:
                conn.execute("CREATE TABLE credential (integration_id TEXT, active INTEGER, time_updated INTEGER, value TEXT)")
                conn.execute("INSERT INTO credential VALUES (?, ?, ?, ?)", (
                    "openai", 1, 1, json.dumps({"type": "oauth", "access": "EXPIRED-SECRET", "expires": 100}),
                ))
                conn.commit()
            auth = root / ".local/share/opencode/auth.json"
            auth.parent.mkdir(parents=True)
            auth.write_text(json.dumps({"openai": {"type": "oauth", "access": "OTHER-SECRET"}}), encoding="utf-8")
            provider = OpenAIAccountProvider(
                home=root, credential_db_path=db, now_ms=lambda: 1_000_000,
                usage_get=lambda *_: self.fail("expired credentials must never be sent"),
            )
            snap = provider.get_quota_snapshot()
            self.assertFalse(snap.available)
            self.assertEqual("OpenAI token expired; it renews automatically on your next OpenAI prompt in OpenCode.", snap.reason)
            self.assertEqual("credential_expired", snap.observations["parser_reason"])
            self.assertNotIn("SECRET", repr(snap))
            (account,) = provider.get_account_snapshots()
            self.assertEqual(("unavailable", snap.reason), (account.availability, account.reason))
            self.assertEqual("credential_expired", account.observations["parser_reason"])
            self.assertEqual("Token expired; your next prompt with this account renews it", account.observations["user_action"])

    def test_explicit_legacy_path_takes_precedence_over_v2_account(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "opencode.db"
            with closing(sqlite3.connect(db)) as conn:
                conn.execute("CREATE TABLE credential (integration_id TEXT, active INTEGER, time_updated INTEGER, value TEXT)")
                conn.execute("INSERT INTO credential VALUES (?, ?, ?, ?)", (
                    "openai", 1, 1, json.dumps({"type": "oauth", "access": "DB-SECRET"}),
                ))
                conn.commit()
            auth = root / "auth.json"
            auth.write_text(json.dumps({"openai": {"type": "oauth", "access": "FILE-SECRET"}}), encoding="utf-8")
            calls = []
            provider = OpenAIAccountProvider(
                auth_json_path=str(auth), credential_db_path=db, now_ms=lambda: 1000,
                usage_get=lambda _url, token, *_: (calls.append(token), UsageResponse(True, 200, {
                    "rate_limit": {"primary_window": {"used_percent": 25, "limit_window_seconds": 18000}},
                }))[1],
            )
            self.assertTrue(provider.get_quota_snapshot().available)
            self.assertEqual(["FILE-SECRET"], calls)

    def test_openai_reader_reuses_access_token_without_refresh_or_persistence(self) -> None:
        credential = openai_credential_from_auth_object({
            "openai": {"type": "oauth", "access": "ACCESS-SECRET", "accountId": "acct-test"},
        })
        self.assertTrue(credential.available)
        with tempfile.TemporaryDirectory() as td:
            auth = Path(td) / "auth.json"
            original = json.dumps({"openai": {"type": "oauth", "access": "ACCESS-SECRET", "accountId": "acct-test"}})
            auth.write_text(original, encoding="utf-8")
            calls = []
            def get(url, token, account_id, timeout):
                calls.append((url, token, account_id, timeout))
                return UsageResponse(True, 200, {
                    "plan_type": "pro", "rate_limit": {
                        "primary_window": {"used_percent": 10, "limit_window_seconds": 18_000},
                    },
                })
            snapshot = OpenAIAccountProvider(
                auth_json_path=str(auth), usage_get=get, now_ms=lambda: 10,
            ).get_quota_snapshot()
            self.assertTrue(snapshot.available)
            self.assertEqual("ACCESS-SECRET", calls[0][1])
            self.assertEqual("acct-test", calls[0][2])
            self.assertEqual(original, auth.read_text(encoding="utf-8"))
            self.assertNotIn("ACCESS-SECRET", repr(snapshot))

    def test_openai_reader_does_not_use_untyped_or_api_key_credentials(self) -> None:
        for auth in (
            {"openai": {"access": "ACCESS-SECRET"}},
            {"openai": {"type": "api", "access": "ACCESS-SECRET"}},
            {"tokens": {"access": "ACCESS-SECRET"}},
        ):
            with self.subTest(auth=tuple(auth)):
                credential = openai_credential_from_auth_object(auth)
                self.assertFalse(credential.available)
                self.assertNotIn("ACCESS-SECRET", repr(credential))


if __name__ == "__main__":
    unittest.main()
