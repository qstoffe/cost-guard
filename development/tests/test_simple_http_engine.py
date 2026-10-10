"""Deterministic mapping, transport, inventory and privacy contracts; no accounts/network."""
from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.accounts.credentials import configured_credentials
from src.accounts.diagnostics import sanitized_account_observation
from src.accounts.http_transport import (AccountHttpResponse, MaintainedEndpoint, MAX_BODY_BYTES,
    bearer_key, decode_json, finite_number, get_account_json)
from src.accounts.simple_http import SimpleHttpAccountProvider
from src.accounts.simple_http_mapping import (ComponentMapping as C, SimpleHttpDefinition,
    MAX_COMPONENTS, normalize_simple_account, timestamp_ms)
from src.domain import AccountRef, AccountSnapshot, AccountUsageStatus

D = Decimal
ENDPOINT = MaintainedEndpoint("https://provider.example/account")
ACCOUNT = AccountSnapshot(AccountRef("installation", "test", source_account="credential:1"), 1000, "Test")


def definition(*components, **kwargs):
    return SimpleHttpDefinition("test", "Test", ("test",), ENDPOINT, components, **kwargs)


def normalized(spec, payload, **kwargs):
    return normalize_simple_account(ACCOUNT, payload, definition(spec, **kwargs))


class MappingTests(unittest.TestCase):
    def test_percent_remaining_and_used(self):
        for kind, value in (("percentage_remaining", "72"), ("percentage_used", "28")):
            account = normalized(C(kind, "Window", ("value",)), {"value": value})
            self.assertEqual(D(".72"), account.quotas[0].remaining_fraction)
            self.assertEqual("available", account.availability)

    def test_native_capacity_primitives_and_decimal_precision(self):
        for kind, value in (("used_limit", "28.125"), ("spend_budget", "28.125"),
                            ("remaining_limit", "71.875"), ("remaining_budget", "71.875")):
            account = normalized(C(kind, "Window", ("value",), limit_path=("limit",)),
                                 {"value": value, "limit": "100"})
            quota = account.quotas[0]
            self.assertEqual(D("28.125"), quota.used)
            self.assertEqual(D("71.875"), quota.remaining)
            self.assertEqual(D(".71875"), quota.remaining_fraction)
            self.assertEqual(D(100), quota.limit)
            self.assertEqual("provider_native", quota.origin)

    def test_no_capacity_without_genuine_denominator(self):
        for kind in ("balance", "spend", "budget"):
            account = normalized(C(kind, "Native value", ("value",)), {"value": "42.73001"})
            self.assertFalse(account.quotas)
            self.assertEqual(D("42.73001"), account.billing[0].amount)
            self.assertEqual(kind, account.billing[0].kind)

    def test_used_above_limit_is_exhausted_but_invalid_remaining_not_clamped(self):
        over = normalized(C("used_limit", "Limit", ("v",), limit_path=("l",)), {"v": 101, "l": 100})
        self.assertEqual(D(0), over.quotas[0].remaining_fraction)
        self.assertEqual(D(101), over.quotas[0].used)
        invalid = normalized(C("remaining_limit", "Limit", ("v",), limit_path=("l",)), {"v": 101, "l": 100})
        self.assertIsNone(invalid.quotas[0].remaining_fraction)
        self.assertEqual("partial", invalid.availability)

    def test_malformed_missing_null_and_zero_denominators_never_become_zero(self):
        spec = C("used_limit", "Limit", ("value",), limit_path=("limit",))
        for value in (None, "bad", True, "NaN", "Infinity", "1e999", "-1", " 2 "):
            account = normalized(spec, {"value": value, "limit": 100})
            self.assertEqual("partial", account.availability)
            self.assertIsNone(account.quotas[0].used)
            self.assertIsNone(account.quotas[0].remaining_fraction)
        for payload in ({}, {"value": 1}, {"value": 0, "limit": 0}):
            account = normalized(spec, payload)
            self.assertIn(account.availability, ("partial", "error"))
            self.assertTrue(not account.quotas or account.quotas[0].remaining_fraction is None)

    def test_currency_rows_preserve_native_values_without_sum_or_fx(self):
        spec = C("balance", "Balance", ("balance",), unit_path=("currency",), allowed_units=("USD", "CNY"))
        account = normalized(spec, {"rows": [{"balance": "4.1", "currency": "USD"},
                                           {"balance": "9.2", "currency": "CNY"}]}, rows_path=("rows",), max_rows=2)
        self.assertEqual([(D("4.1"), "USD"), (D("9.2"), "CNY")], [(b.amount, b.currency) for b in account.billing])
        invalid = normalized(spec, {"rows": [{"balance": "5", "currency": "untrusted"}]}, rows_path=("rows",))
        self.assertFalse(invalid.billing)
        self.assertEqual("error", invalid.availability)

    def test_rows_and_components_are_bounded_and_malformed_rows_partial(self):
        spec = C("balance", "Balance", ("balance",))
        account = normalized(spec, {"rows": [{"balance": 1}] * 100}, rows_path=("rows",), max_rows=2)
        self.assertEqual(2, len(account.billing))
        self.assertEqual(98, account.observations["ignored_rows"])
        self.assertEqual("partial", account.availability)
        many = definition(*(spec for _ in range(4)), rows_path=("rows",), max_rows=16)
        capped = normalize_simple_account(ACCOUNT, {"rows": [{"balance": 1}] * 16}, many)
        self.assertEqual(MAX_COMPONENTS, len(capped.billing))
        malformed = normalized(spec, {"rows": [None, {"balance": 7}, []]}, rows_path=("rows",), max_rows=3)
        self.assertEqual(1, len(malformed.billing))
        self.assertEqual("partial", malformed.availability)

    def test_explicit_reset_encodings(self):
        expected = 1_790_856_000_000
        for encoding, raw in (("iso8601", "2026-10-01T12:00:00Z"),
                              ("unix_seconds", expected // 1000), ("unix_milliseconds", expected)):
            account = normalized(C("percentage_remaining", "Day", ("p",), reset_path=("reset",), reset_encoding=encoding),
                                 {"p": 72, "reset": raw})
            self.assertEqual(expected, account.quotas[0].reset_at_ms)
        for raw in ("2026-10-01T12:00:00", "bad", True):
            self.assertIsNone(timestamp_ms(raw, "iso8601"))
        self.assertIsNone(timestamp_ms(expected, "guessed"))
        self.assertIsNone(timestamp_ms(expected, "unix_seconds"))  # Not guessed as milliseconds.
        self.assertEqual(expected // 1000, timestamp_ms(expected // 1000, "unix_milliseconds"))

    def test_status_and_explicit_plan_allowlist_no_raw_text_or_inference(self):
        spec = C("balance", "Balance", ("balance",))
        options = dict(status_path=("available",), status_values=((True, AccountUsageStatus.AVAILABLE),
                       (False, AccountUsageStatus.BLOCKED), ("paused", AccountUsageStatus.BLOCKED)),
                       plan_path=("plan",), plan_values=(("plus", "Plus"),))
        for raw in (False, "paused"):
            account = normalized(spec, {"balance": 1, "available": raw, "plan": "plus"}, **options)
            self.assertEqual("Plus", account.plan)
            self.assertEqual(AccountUsageStatus.BLOCKED, account.status)
        account = normalized(spec, {"balance": 1, "available": 1, "plan": "secret-content"}, **options)
        self.assertIsNone(account.plan)
        self.assertEqual(AccountUsageStatus.UNKNOWN, account.status)
        self.assertNotIn("secret-content", repr(account))
        self.assertEqual("partial", account.availability)

    def test_missing_root_and_malformed_reset_fail_soft(self):
        spec = C("percentage_used", "Day", ("p",), reset_path=("r",), reset_encoding="unix_seconds")
        result = normalized(spec, {"p": 25, "r": "bad"})
        self.assertEqual("partial", result.availability)
        self.assertEqual(D(".75"), result.quotas[0].remaining_fraction)
        self.assertEqual("error", normalized(spec, [], root_path=("data",)).availability)

    def test_definition_rejects_executable_mapping_and_unbounded_shapes(self):
        with self.assertRaises(ValueError):
            C("eval", "Bad", ("value",))
        with self.assertRaises(ValueError):
            definition(C("balance", "Balance", ("balance",)), max_rows=999)
        with self.assertRaises(ValueError):
            C("balance", "Balance", ("balance",), reset_path=("reset",), reset_encoding="auto")


class TransportTests(unittest.TestCase):
    def call(self, body=b'{"ok":1}', *, headers=None, status=200):
        response = MagicMock()
        response.status = status
        header_map = {"Content-Type": "application/json", **(headers or {})}
        response.getheader.side_effect = lambda name, default=None: header_map.get(name, default)
        response.read1.side_effect = [body, b""]
        connection = MagicMock()
        connection.getresponse.return_value = response
        with patch("src.accounts.http_transport.http.client.HTTPSConnection", return_value=connection) as factory:
            value = get_account_json(ENDPOINT, "test-key")
        return value, connection, response, factory

    def test_get_only_fixed_host_no_cookies_proxy_body_or_headers(self):
        value, conn, _, factory = self.call()
        self.assertFalse(value.classification)
        factory.assert_called_once_with("provider.example", timeout=8)
        conn.request.assert_called_once_with("GET", "/account", headers={"Authorization": "Bearer test-key", "Accept": "application/json"})
        conn.close.assert_called_once()
        self.assertNotIn("payload", repr(value))

    def test_redirects_never_follow_or_read_account_body(self):
        for status in (301, 302, 303, 307, 308):
            result, conn, response, _ = self.call(status=status, headers={"Location": "https://attacker.example"})
            self.assertEqual("redirect_rejected", result.classification)
            self.assertEqual(status, result.http_status)
            conn.request.assert_called_once()
            response.read1.assert_not_called()

    def test_http_auth_and_server_errors_omit_body(self):
        for status, cause in ((401, "auth_failure"), (403, "auth_failure"), (429, "http_failure"), (503, "http_failure")):
            result, _, response, _ = self.call(status=status)
            self.assertEqual(cause, result.classification)
            response.read1.assert_not_called()

    def test_non_json_compressed_oversized_and_malformed_responses_rejected(self):
        cases = ((b"{}", {"Content-Type": "text/html"}, "non_json"),
                 (b"{}", {"Content-Encoding": "gzip"}, "encoding_rejected"),
                 (b"{}", {"Content-Length": str(MAX_BODY_BYTES + 1)}, "body_too_large"),
                 (b"a" * (MAX_BODY_BYTES + 1), {}, "body_too_large"),
                 (b"not json test-key", {}, "parser_failure"),
                 (b'{"number":NaN}', {}, "parser_failure"),
                 (b'{"number":1,"number":2}', {}, "parser_failure"),
                 (b"[" * 20 + b"0" + b"]" * 20, {}, "parser_failure"),
                 (b"[" + b"0," * 4096 + b"0]", {}, "parser_failure"))
        for body, headers, cause in cases:
            result, _, _, _ = self.call(body, headers=headers)
            self.assertEqual(cause, result.classification)
            self.assertIsNone(result.payload)
            self.assertNotIn("test-key", repr(result))

    def test_number_precision_and_string_braces_do_not_count_as_nesting(self):
        result = decode_json(b'{"amount":42.730000000001,"text":"[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[["}')
        self.assertEqual(D("42.730000000001"), result["amount"])
        for raw in (True, None, float("nan"), float("inf"), "1e999", "-1", "0x10", "1_000", {}):
            self.assertIsNone(finite_number(raw))

    def test_timeout_and_network_failure_are_sanitized(self):
        for error, cause in ((TimeoutError("test-key"), "timeout"), (OSError("test-key"), "network_failure")):
            conn = MagicMock()
            conn.request.side_effect = error
            with patch("src.accounts.http_transport.http.client.HTTPSConnection", return_value=conn):
                result = get_account_json(ENDPOINT, "test-key")
            self.assertEqual(cause, result.classification)
            self.assertNotIn("test-key", repr(result))
            conn.close.assert_called_once()

    def test_endpoint_and_credential_injection_rejected_before_network(self):
        for url in ("http://provider.example/account", "https://user:password@provider.example/account",
                    "https://provider.example:123/account", "https://provider.example/account?redirect=yes"):
            with self.assertRaises(ValueError):
                MaintainedEndpoint(url)
        for value in ({"type": "oauth", "access": "test-key"}, {"type": "api", "key": "key\r\nCookie: bad"},
                      {"type": "api", "key": ""}, {"type": "api", "key": "x" * 8193}):
            self.assertIsNone(bearer_key(value))
        with patch("src.accounts.http_transport.http.client.HTTPSConnection") as factory:
            self.assertEqual("credential_invalid", get_account_json(ENDPOINT, "bad\nkey").classification)
            factory.assert_not_called()


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.auth = self.root / "auth.json"
        self.auth.write_text(json.dumps({"test": {"type": "api", "key": "legacy-key"}}))
        self.db = self.root / "opencode.db"
        self.definition = definition(C("balance", "Balance", ("balance",)))

    def rows(self, records):
        conn = sqlite3.connect(self.db)
        try:
            conn.execute("CREATE TABLE credential(id TEXT, integration_id TEXT, value TEXT, active INTEGER)")
            conn.executemany("INSERT INTO credential VALUES (?,?,?,?)", records)
            conn.commit()
        finally:
            conn.close()

    def provider(self, reader, **kwargs):
        return SimpleHttpAccountProvider(self.definition, home=self.root, http_get=reader,
            auth_json_path=str(self.auth), clock_ms=lambda: 1000, **kwargs)

    def test_one_credential_one_snapshot_full_source_identity_no_secret_hash(self):
        reader = MagicMock(return_value=AccountHttpResponse({"balance": "4.2"}, 200))
        account = self.provider(reader).get_account_snapshots()[0]
        self.assertEqual("auth:test", account.ref.source_account)
        self.assertEqual(D("4.2"), account.billing[0].amount)
        reader.assert_called_once_with(ENDPOINT, "legacy-key")
        self.auth.write_text(json.dumps({"test": {"type": "api", "key": "rotated-key"}}))
        self.assertEqual(account.key, self.provider(reader).get_account_snapshots()[0].key)
        self.assertNotIn("legacy-key", repr(account))

    def test_multi_account_v2_precedence_inactive_and_failure_isolation(self):
        self.rows([("one", "test", json.dumps({"type": "api", "key": "bad-key"}), 1),
                   ("two", "test", json.dumps({"type": "api", "key": "good-key"}), 0)])
        reader = MagicMock(side_effect=lambda endpoint, key: AccountHttpResponse(http_status=401, classification="auth_failure")
                          if key == "bad-key" else AccountHttpResponse({"balance": 42}, 200))
        provider = SimpleHttpAccountProvider(self.definition, home=self.root, credential_db_path=self.db,
                                            http_get=reader, clock_ms=lambda: 1000)
        provider.auth_json_path = self.auth
        before = self.db.read_bytes()
        accounts = provider.get_account_snapshots()
        self.assertEqual(2, len(accounts))
        self.assertEqual(2, len({a.key for a in accounts}))
        self.assertEqual(["unavailable", "available"], [a.availability for a in accounts])
        self.assertFalse(accounts[1].observations["credential_active"])
        self.assertEqual(before, self.db.read_bytes())
        self.assertNotIn("legacy-key", str(reader.call_args_list))
        self.assertEqual(2, provider.diagnostic_inventory()["qualifying_records"])

    def test_v2_oauth_or_invalid_rows_never_fall_back_to_legacy_key(self):
        for value in ({"type": "oauth", "access": "oauth-secret"}, {"type": "api", "key": ""}):
            if self.db.exists():
                self.db.unlink()
            self.rows([("v2", "test", json.dumps(value), 1)])
            reader = MagicMock()
            provider = SimpleHttpAccountProvider(self.definition, credential_db_path=self.db, home=self.root, http_get=reader)
            provider.auth_json_path = self.auth
            accounts = provider.get_account_snapshots()
            self.assertEqual(1, len(accounts))
            self.assertEqual("unavailable", accounts[0].availability)
            reader.assert_not_called()

    def test_explicit_auth_override_is_file_only_and_fail_closed_schema(self):
        self.rows([("v2", "test", json.dumps({"type": "api", "key": "v2-key"}), 1)])
        reader = MagicMock(return_value=AccountHttpResponse({"balance": 1}, 200))
        provider = self.provider(reader, credential_db_path=self.db)
        self.assertIsNone(provider.credential_db_path)
        provider.get_account_snapshots()
        reader.assert_called_once_with(ENDPOINT, "legacy-key")
        conn = sqlite3.connect(self.db)
        try:
            conn.execute("ALTER TABLE credential RENAME COLUMN value TO broken")
            conn.commit()
        finally:
            conn.close()
        self.assertEqual((), configured_credentials(self.auth, self.db, ("test",)))

    def test_diagnostics_exclude_keys_raw_responses_labels_and_account_locator(self):
        reader = MagicMock(return_value=AccountHttpResponse({"balance": 5, "unrelated": "raw-secret"}, 200))
        account = self.provider(reader).get_account_snapshots()[0]
        diagnostic = sanitized_account_observation(account)
        text = json.dumps(diagnostic)
        for secret in ("legacy-key", "raw-secret", "auth:test", "Authorization"):
            self.assertNotIn(secret, text)
        self.assertTrue(diagnostic["quota_shape"]["mapping_matched"])
        self.assertEqual(["balance"], diagnostic["billing_categories"])
        self.assertTrue(diagnostic["account_source_hash"])
        reader.side_effect = ValueError("legacy-key raw response")
        failed = self.provider(reader).get_account_snapshots()[0]
        self.assertNotIn("legacy-key", repr(failed))
        self.assertEqual("error", failed.availability)

    def test_absent_and_disabled_accounts_never_query_and_inventory_is_actionable(self):
        reader = MagicMock()
        self.auth.write_text("{}")
        provider = self.provider(reader)
        self.assertFalse(provider.probe().available)
        self.assertEqual((), provider.get_account_snapshots())
        self.assertEqual(0, provider.diagnostic_inventory()["configured_records"])
        reader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
