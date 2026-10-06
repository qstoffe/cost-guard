"""Current V2 availability contract, HTTP integration and CLI compatibility."""
from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from development.tests.test_opencode_v2 import fixture, source_with_service
from development.tests.test_step7_reports_cli import FakePricingProvider
from src.bootstrap import _model_availability_source
from src.reports.model_comparison import selectable_catalog
from src.sources.errors import SourceDataError, SourceUnavailableError
from src.sources.model_availability import (
    OpenCodeModelAvailabilitySource, model_ids_from_v2_snapshot, settled_v2_model_ids,
)


def model(identity="gpt-test", provider="openai", *, enabled=True):
    return {"id": identity, "modelID": "upstream-request-name",
            "providerID": provider, "enabled": enabled}


class V2ModelAvailabilityTests(unittest.TestCase):
    def test_ids_are_opaque_including_context_and_future_formats(self):
        identities = ("claude-opus-5-5[1m]", "claude-haiku-4-5-20251001", "new+variant@v2:β")
        expected = tuple("claude-code/" + identity for identity in identities)
        self.assertEqual(expected, model_ids_from_v2_snapshot([model(i, "claude-code") for i in identities]))
        self.assertEqual(expected, OpenCodeModelAvailabilitySource(runner=lambda: (0, "\n".join(expected))).available_model_ids())

    def test_control_characters_never_establish_availability(self):
        for identity in ("test\x00id", "test\x7fid", "test\x85id", "test\u202eid", " test", "test id"):
            self.assertIsNone(model_ids_from_v2_snapshot([model(identity)]))
        for control in ("\x00", "\x7f", "\x85", "\u202e"):
            output = "openai/test" + control + "anthropic/other"
            self.assertIsNone(OpenCodeModelAvailabilitySource(runner=lambda: (0, output)).available_model_ids())

    def test_empty_cli_success_is_authoritative_but_malformed_output_is_not(self):
        self.assertEqual((), OpenCodeModelAvailabilitySource(runner=lambda: (0, "")).available_model_ids())
        self.assertIsNone(OpenCodeModelAvailabilitySource(runner=lambda: (0, "invalid result")).available_model_ids())

    def test_current_envelope_enabled_models_and_selectable_not_upstream_identity(self):
        values = [model(), model("GPT-TEST"), model("claude-test", "anthropic", enabled=False),
                  model("gpt-test-fast"), model("free/model", "custom")]
        expected = ("openai/gpt-test", "openai/gpt-test-fast", "custom/free/model")
        for payload in (values, {"location": {"directory": None}, "data": values}):
            self.assertEqual(expected, model_ids_from_v2_snapshot(payload))

    def test_empty_and_disabled_only_are_authoritative_not_lookup_failures(self):
        for values in ([], [model(enabled=False)]):
            self.assertEqual((), model_ids_from_v2_snapshot({"data": values}))

    def test_unknown_or_partial_contract_is_not_authoritative(self):
        for payload in (None, {}, {"data": {}}, {"data": "models"}, [None],
                        [model(), {}], [{**model(), "enabled": "true"}],
                        [{**model(), "enabled": 1}], [{**model(), "id": ""}],
                        [{**model(), "id": "private\ntext"}],
                        [{**model(), "providerID": None}],
                        [{k: v for k, v in model().items() if k != "enabled"}]):
            with self.subTest(payload=payload):
                self.assertIsNone(model_ids_from_v2_snapshot(payload))

    @staticmethod
    def _settle(snapshots, **timing):
        clock = [0.0]
        replies = iter(snapshots)
        last = [None]

        def fetch():
            last[0] = next(replies, last[0])
            return {"location": {"directory": "home"}, "data": last[0]}

        def sleep(seconds):
            clock[0] += seconds

        result = settled_v2_model_ids(fetch, sleep=sleep, clock=lambda: clock[0], **timing)
        return result, clock[0]

    def test_cold_location_boot_waits_for_late_plugin_providers(self):
        # Observed v78.28 live race: a fresh service location answered [] and
        # then OpenAI/Zen-only snapshots before the Claude Code plugin loaded.
        zen, gpt, claude = model("free", "opencode"), model("gpt-test"), model("claude-test", "claude-code")
        result, elapsed = self._settle([[], [zen, gpt], [zen, gpt], [zen, gpt, claude]])
        self.assertEqual(("opencode/free", "openai/gpt-test", "claude-code/claude-test"), result)
        self.assertGreaterEqual(elapsed, 0.9 + 1.0)

    def test_warm_list_needs_one_confirmation_and_order_is_not_a_change(self):
        a, b = model("a"), model("b")
        result, elapsed = self._settle([[a, b], [b, a]])
        self.assertEqual(("openai/a", "openai/b"), result)
        self.assertAlmostEqual(0.3, elapsed)

    def test_persistent_empty_is_authoritative_only_after_timeout(self):
        self.assertEqual(((), 6.0), self._settle([[]], interval=0.5))

    def test_unsettled_or_invalid_list_is_not_established(self):
        flapping = [[model(str(i % 2))] for i in range(100)]
        self.assertIsNone(self._settle(flapping)[0])
        self.assertIsNone(self._settle([[model()], [{}]])[0])

    def test_registered_authenticated_http_source_filters_without_cli(self):
        payload = fixture()
        payload["models"] = {"location": {"directory": None}, "data": [
            model(), model("claude-test", "anthropic", enabled=False)]}
        with source_with_service(payload) as (source, server, _):
            self.assertTrue(source.probe().healthy)
            availability = _model_availability_source(SimpleNamespace(source=source))
            with patch.object(OpenCodeModelAvailabilitySource, "available_model_ids",
                              side_effect=AssertionError("CLI must not run")) as cli:
                selected, warnings = selectable_catalog(
                    FakePricingProvider().catalog, availability_source=availability)
                cli.assert_not_called()
            self.assertEqual(["gpt-test"], [m.model.model for m in selected.models])
            self.assertFalse(warnings)
            # A warm list is confirmed by exactly one extra read.
            self.assertEqual(["/api/info", "/api/model", "/api/model"], [p for p, _ in server.requests])
            self.assertTrue(all(auth for _, auth in server.requests))

    def test_empty_live_list_never_falls_back_to_full_cli_catalog(self):
        live = Mock(available_model_ids=Mock(return_value=()))
        source = _model_availability_source(SimpleNamespace(source=live))
        with patch.object(OpenCodeModelAvailabilitySource, "available_model_ids") as cli:
            selected, warnings = selectable_catalog(FakePricingProvider().catalog,
                                                   availability_source=source)
            cli.assert_not_called()
        self.assertFalse(selected.models)
        self.assertIn("No available OpenCode models match", warnings[0])

    def test_unavailable_invalid_or_older_service_uses_cli_once(self):
        for failure in (None, SourceUnavailableError("private auth"), SourceDataError("private payload")):
            live = Mock()
            if isinstance(failure, Exception):
                live.available_model_ids.side_effect = failure
            else:
                live.available_model_ids.return_value = failure
            source = _model_availability_source(SimpleNamespace(source=live))
            with patch.object(OpenCodeModelAvailabilitySource, "available_model_ids",
                              return_value=("openai/gpt-test",)) as cli:
                self.assertEqual(("openai/gpt-test",), source.available_model_ids())
                cli.assert_called_once_with()
            live.available_model_ids.assert_called_once_with()

    def test_v1_wiring_keeps_global_cli_and_both_failures_remain_visible(self):
        self.assertIsInstance(_model_availability_source(SimpleNamespace(source=object())),
                              OpenCodeModelAvailabilitySource)
        live = Mock(available_model_ids=Mock(side_effect=SourceUnavailableError("private auth")))
        source = _model_availability_source(SimpleNamespace(source=live))
        with patch.object(OpenCodeModelAvailabilitySource, "available_model_ids", return_value=None):
            catalog = FakePricingProvider().catalog
            selected, warnings = selectable_catalog(catalog, availability_source=source)
        self.assertEqual(catalog, selected)
        self.assertIn("showing full pricing catalog", warnings[0])
        self.assertNotIn("private", warnings[0])


if __name__ == "__main__":
    unittest.main()
