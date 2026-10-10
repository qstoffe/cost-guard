"""V2 normalization is independently testable without a service/registration."""
from copy import deepcopy
from decimal import Decimal
import unittest

from development.fixtures.session_snapshots import prov
from src.domain import ModelRef
from src.sources.errors import SourceDataError
from src.sources.opencode_v2_normalization import normalize_invocations, normalize_message_bundle


def assistant_bundle():
    return {"info": {"id": "a", "sessionID": "root", "role": "assistant", "parentID": "u",
                     "providerID": "provider", "modelID": "model", "variant": "high",
                     "time": {"created": 100, "completed": 200}, "finish": "stop",
                     "tokens": {"input": 999, "output": 99}, "cost": 9}, "parts": []}


class V2NormalizationTests(unittest.TestCase):
    def test_parts_and_structured_metadata_are_defensive_copies(self):
        bundle = assistant_bundle()
        bundle["info"]["structured"] = {"values": [1]}
        bundle["parts"] = [{"id": "p", "sessionID": "root", "messageID": "a", "type": "tool",
                            "state": {"status": "running"}}]
        original = deepcopy(bundle)

        message, parts = normalize_message_bundle(bundle, prov)
        bundle["parts"][0]["state"]["status"] = "completed"
        bundle["info"]["structured"]["values"].append(2)

        self.assertEqual("running", parts[0].data["state"]["status"])
        self.assertEqual({"values": [1]}, message.metadata["structured"])
        self.assertFalse({"id", "sessionID", "messageID"} & parts[0].data.keys())
        self.assertEqual(prov("root", "p"), parts[0].provenance)
        self.assertEqual(original["parts"][0]["state"], parts[0].data["state"])

    def test_step_usage_replaces_cumulative_message_usage(self):
        bundle = assistant_bundle()
        bundle["parts"] = [{"id": "step", "type": "step-finish", "tokens": {"input": 10, "output": 2},
                            "cost": "0.25", "time": {"start": 110, "end": 150}}]

        message, _ = normalize_message_bundle(bundle, prov)
        invocations = normalize_invocations(message, prov)

        self.assertEqual(1, len(invocations))
        self.assertEqual((10, 2, Decimal("0.25")),
                         (invocations[0].tokens.input, invocations[0].tokens.output, invocations[0].cost.amount))
        self.assertEqual(("a:step", "step", "u", "high"),
                         (invocations[0].invocation_id, invocations[0].step_part_id,
                          invocations[0].initiating_event_id, invocations[0].variant))

    def test_fallback_preserves_message_usage_and_provenance(self):
        message, _ = normalize_message_bundle(assistant_bundle(), prov)

        invocation, = normalize_invocations(message, prov)

        self.assertEqual(message.tokens, invocation.tokens)
        self.assertEqual(message.cost, invocation.cost)
        self.assertEqual(message.provenance, invocation.provenance)
        self.assertIsNone(invocation.step_part_id)

    def test_user_model_is_request_bound_and_is_never_an_invocation(self):
        bundle = {"info": {"id": "u", "sessionID": "root", "role": "user",
                            "model": {"providerID": "provider", "id": "request-model", "variant": "low"}}, "parts": []}

        message, _ = normalize_message_bundle(bundle, prov)

        self.assertEqual(ModelRef("provider", "request-model"), message.model)
        self.assertEqual("low", message.variant)
        self.assertEqual([], normalize_invocations(message, prov))

    def test_missing_usage_is_not_fabricated(self):
        bundle = assistant_bundle()
        bundle["info"].pop("tokens")

        message, _ = normalize_message_bundle(bundle, prov)

        self.assertIsNone(message.tokens)
        self.assertEqual([], normalize_invocations(message, prov))

    def test_invalid_cost_fails_without_echoing_value(self):
        for value in ("secret-input", "NaN", "Infinity", "-1"):
            bundle = assistant_bundle()
            bundle["info"]["cost"] = value
            with self.subTest(value=value), self.assertRaises(SourceDataError) as caught:
                normalize_message_bundle(bundle, prov)
            self.assertNotIn(value, str(caught.exception))

    def test_invalid_identity_and_part_shapes_fail_closed(self):
        for bundle in ({}, {"info": {"id": 123, "sessionID": "root"}, "parts": []},
                       {"info": assistant_bundle()["info"], "parts": [None]}):
            with self.subTest(bundle=bundle), self.assertRaises(SourceDataError):
                normalize_message_bundle(bundle, prov)
