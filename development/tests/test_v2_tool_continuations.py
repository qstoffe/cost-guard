"""Zero-usage V2 tool continuation records never inflate model request Calls."""
from __future__ import annotations

from dataclasses import replace
import unittest

from development.tests.fixtures.opencode_v2_service import source_with_current_service
from development.tests.fixtures.session_snapshots import prov
from src.analysis.causal import build_prompt_records
from src.sources.opencode_v2_normalization import (
    normalize_invocations, normalize_message_bundle, normalize_request_invocations,
)
from src.sources.opencode_v2_wire import normalize_message_items

MODEL = {"providerID": "claude-code", "id": "claude-opus-5-5", "variant": "default"}
USAGE = {"input": 2, "output": 300, "reasoning": 40, "cache": {"read": 90_000, "write": 1_500}}
ZERO = {"input": 0, "output": 0, "reasoning": 0, "cache": {"read": 0, "write": 0}}


def tool(call_id: str, at: int, *, status: str = "completed", name: str = "edit") -> dict:
    return {"type": "tool", "id": call_id, "name": name, "state": {"status": status},
            "time": {"created": at, "ran": at + 2, "completed": at + 15}}


def assistant(message_id: str, created: int, *, stream_delay: int | None = 3_000, tokens: dict | None = None,
              content: list | None = None, finish: str = "tool-calls", response_id: str | None = None,
              error: dict | None = None, cost: float = 0) -> dict:
    """``tokens=None`` is a usage-bearing response; pass ``ZERO`` for an explicit-zero record."""
    time = {"created": created, "completed": created + (stream_delay or 0) + 60}
    if stream_delay is not None:
        time["streamed"] = created + stream_delay
    value = {"id": message_id, "type": "assistant", "agent": "build", "model": dict(MODEL), "time": time,
             "finish": finish, "cost": cost, "tokens": dict(USAGE if tokens is None else tokens),
             "content": content if content is not None else [tool(f"{message_id}_call", created + 50)]}
    if response_id is not None:
        value["providerState"] = {"responseId": response_id}
    if error is not None:
        value["error"] = error
    return value


def user(message_id: str, created: int) -> dict:
    return {"id": message_id, "type": "user", "text": "work", "files": [], "agents": [], "time": {"created": created}}


def requests(*items: dict) -> list[str]:
    bundles, _ = normalize_message_items(items, session={"id": "root"})
    messages = [normalize_message_bundle(bundle, prov)[0] for bundle in bundles]
    return [item.message_id for item in normalize_request_invocations(messages, prov)]


class ToolContinuationClassificationTests(unittest.TestCase):
    def test_one_response_emitting_several_tool_records_is_one_request(self):
        self.assertEqual(["a1"], requests(
            user("u", 1_000),
            assistant("a1", 1_100),
            assistant("a2", 4_300, tokens=ZERO, stream_delay=65),
            assistant("a3", 4_500, tokens=ZERO, stream_delay=70, content=[tool("t3", 4_550, status="error")]),
        ))

    def test_genuine_consecutive_responses_each_count(self):
        self.assertEqual(["a1", "a2", "a3"], requests(
            user("u", 1_000), assistant("a1", 1_100), assistant("a2", 4_300, stream_delay=1_200),
            assistant("a3", 6_000, stream_delay=40, finish="stop", content=[{"type": "text", "text": "done"}]),
        ))

    def test_zero_usage_records_without_continuation_evidence_stay_requests(self):
        cases = {
            "model latency": assistant("z", 4_300, tokens=ZERO, stream_delay=1_500),
            "no stream time": assistant("z", 4_300, tokens=ZERO, stream_delay=None),
            "own output": assistant("z", 4_300, tokens=ZERO, stream_delay=60,
                                    content=[{"type": "text", "text": "x"}, tool("t", 4_350)]),
            "absent counters": assistant("z", 4_300, tokens={"cache": {"read": 0, "write": 0}}, stream_delay=60),
            "aborted": assistant("z", 4_300, tokens=ZERO, stream_delay=60,
                                 error={"name": "MessageAbortedError", "data": {}}),
            "other model": {**assistant("z", 4_300, tokens=ZERO, stream_delay=60),
                            "model": {"providerID": "claude-code", "id": "claude-sonnet-5-5"}},
        }
        for label, record in cases.items():
            with self.subTest(label):
                self.assertIn("z", requests(user("u", 1_000), assistant("a1", 1_100), record))

    def test_continuation_needs_a_usage_bearing_tool_calls_predecessor(self):
        unanchored = requests(user("u", 1_000), assistant("z", 1_100, tokens=ZERO, stream_delay=60))
        after_stop = requests(user("u", 1_000), assistant("a1", 1_100, finish="stop"),
                              assistant("z", 4_300, tokens=ZERO, stream_delay=60))
        after_failure = requests(user("u", 1_000), assistant("a1", 1_100, error={"name": "APIError", "data": {}}),
                                 assistant("z", 4_300, tokens=ZERO, stream_delay=60))
        self.assertEqual((["z"], ["a1", "z"], ["a1", "z"]), (unanchored, after_stop, after_failure))

    def test_prompt_and_compaction_boundaries_reset_the_chain_but_system_notices_do_not(self):
        compaction = {"id": "c", "type": "compaction", "reason": "auto", "status": "completed",
                      "summary": "s", "time": {"created": 4_000}}
        system = {"id": "s", "type": "system", "text": "notice", "time": {"created": 4_200}}
        self.assertEqual(["a1", "z"], requests(user("u", 1_000), assistant("a1", 1_100), user("u2", 4_200),
                                              assistant("z", 4_300, tokens=ZERO, stream_delay=60)))
        self.assertEqual(["a1", "z"], requests(user("u", 1_000), assistant("a1", 1_100), compaction,
                                              assistant("z", 4_300, tokens=ZERO, stream_delay=60)))
        self.assertEqual(["a1"], requests(user("u", 1_000), assistant("a1", 1_100), system,
                                          assistant("z", 4_300, tokens=ZERO, stream_delay=60)))

    def test_provider_response_identity_is_authoritative_when_present(self):
        same = requests(user("u", 1_000), assistant("a1", 1_100, response_id="r1"),
                        assistant("z", 4_300, tokens=ZERO, stream_delay=2_000, response_id="r1"))
        different = requests(user("u", 1_000), assistant("a1", 1_100, response_id="r1"),
                             assistant("z", 4_300, tokens=ZERO, stream_delay=60, response_id="r2"))
        one_sided = requests(user("u", 1_000), assistant("a1", 1_100, response_id="r1"),
                             assistant("z", 4_300, tokens=ZERO, stream_delay=60))
        self.assertEqual((["a1"], ["a1", "z"], ["a1", "z"]), (same, different, one_sided))


class ToolContinuationPromptTests(unittest.TestCase):
    def test_calls_drop_while_history_tools_billing_tokens_and_durations_are_preserved(self):
        with source_with_current_service() as (source, server, _registration):
            server.messages["ses_current"].extend((
                user("u1", 10_000),
                assistant("a1", 10_100, cost=0.5, content=[tool("t1", 13_050), tool("t1b", 13_055, name="read")]),
                assistant("a2", 13_200, tokens=ZERO, stream_delay=65, content=[tool("t2", 13_250, status="error")]),
                assistant("a3", 13_400, tokens=ZERO, stream_delay=65),
                assistant("a4", 13_600, finish="stop", cost=0.25, content=[{"type": "text", "text": "done"}]),
                user("u2", 20_000),
                assistant("b1", 20_100, cost=0.5),
                assistant("b2", 23_200, tokens=ZERO, stream_delay=1_500),
                assistant("b3", 26_000, finish="stop", content=[{"type": "text", "text": "done"}]),
            ))
            snapshot = source.load_session_snapshot("ses_current")

        every_record = sorted((item for message in snapshot.messages for item in normalize_invocations(message, prov)),
                              key=lambda item: (item.completed_at_ms or item.created_at_ms, item.invocation_id))
        before = {r.prompt_id: r for r in build_prompt_records(replace(snapshot, invocations=tuple(every_record)),
                                                               tracked_provider=None, now_ms=99_000)}
        after = {r.prompt_id: r for r in build_prompt_records(snapshot, tracked_provider=None, now_ms=99_000)}

        self.assertLessEqual({"a1", "a2", "a3", "a4", "b1", "b2", "b3"}, {m.message_id for m in snapshot.messages})
        self.assertEqual(6, sum(part.kind == "tool" for part in snapshot.parts if part.message_id[0] in "ab"))
        self.assertEqual(((4, 2), (3, 3)), ((before["u1"].model_calls, after["u1"].model_calls),
                                            (before["u2"].model_calls, after["u2"].model_calls)))
        for prompt in ("u1", "u2"):
            old, new = before[prompt], after[prompt]
            self.assertEqual(
                (old.cost, old.input_tokens, old.output_tokens, old.cache_read_tokens, old.cache_write_tokens,
                 old.duration_ms, old.local_duration_ms, old.model_wait_ms, old.aborted, old.completed_successfully,
                 old.unresolved_fallback_requests, old.estimated_fallback_requests),
                (new.cost, new.input_tokens, new.output_tokens, new.cache_read_tokens, new.cache_write_tokens,
                 new.duration_ms, new.local_duration_ms, new.model_wait_ms, new.aborted, new.completed_successfully,
                 new.unresolved_fallback_requests, new.estimated_fallback_requests), prompt)


if __name__ == "__main__":
    unittest.main()
