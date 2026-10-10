"""Invisible synthetic V2 notices continue the current prompt instead of hiding its work."""
from __future__ import annotations

import unittest

from development.tests.test_effort_presentation import project
from development.fixtures.opencode_v2_service import source_with_current_service


def assistant(message_id: str, created: int, *, completed: int | None = None, tokens: int = 100) -> dict:
    value = {"id": message_id, "type": "assistant", "agent": "build",
             "model": {"providerID": "anthropic", "id": "claude-opus-5-5", "variant": "default"},
             "content": [{"type": "text", "id": f"{message_id}_text", "text": "work"}],
             "time": {"created": created}}
    if completed is not None:
        value.update(finish="tool-calls", cost=0.1, time={"created": created, "completed": completed},
                     tokens={"input": tokens, "output": 10, "reasoning": 0, "cache": {"read": 1000, "write": 0}})
    return value


def notice(message_id: str, created: int) -> dict:
    return {"id": message_id, "type": "synthetic", "text": '<subagent state="completed">done</subagent>',
            "time": {"created": created}}


class SyntheticNoticeAttributionTests(unittest.TestCase):
    def test_subagent_notices_and_mid_run_prompt_keep_work_cost_and_model(self):
        with source_with_current_service() as (source, server, _registration):
            server.active = {"ses_current": {"type": "running"}}
            server.messages["ses_current"].extend((
                notice("msg_notice_a", 4500),
                assistant("msg_after_notice", 4600, completed=4700),
                {"id": "msg_mid_run", "type": "user", "text": "typed while running", "time": {"created": 5000}},
                notice("msg_notice_b", 5001),  # injected 1 ms later; carries the continuing work
                assistant("msg_b1", 5100, completed=5200),
                assistant("msg_b2", 5300, completed=5400),
                assistant("msg_b3", 5500),  # still streaming
            ))
            snapshot = source.load_session_snapshot("ses_current")
            _, block = project(snapshot)
            rows = {row.event_id: row for row in block.rows if not row.is_compaction}
            self.assertEqual(["msg_current_user", "msg_mid_run"], list(rows))
            first, mid_run = rows["msg_current_user"], rows["msg_mid_run"]
            self.assertEqual(2, first.calls, "work after a notice stays on the prompt current at that time")
            self.assertEqual(2, mid_run.calls)
            self.assertTrue(mid_run.in_progress)
            self.assertGreater(mid_run.billed_cost or 0, 0, "its reported request cost is not hidden")
            self.assertTrue(mid_run.model_effort.startswith("claude-opus-5-5"), mid_run.model_effort)
            self.assertEqual(len(snapshot.invocations), sum(row.calls for row in rows.values()),
                             "no request is hidden from the session rows")

    def test_context_grown_after_a_notice_is_the_next_prompts_delta_baseline(self):
        """v80.26 showed #1 → 24k and #2 +59k → 220k; v80.27–29 turned that into +196k.

        The 137k growth happened after a subagent notice inside #1, so it belongs to
        #1's Next Ictx and #2 grew only ~59k.
        """
        with source_with_current_service() as (source, server, _registration):
            server.messages["ses_current"].extend((
                {"id": "msg_a", "type": "user", "text": "implement", "time": {"created": 5000}},
                assistant("msg_a1", 5100, completed=5200, tokens=24_000),
                notice("msg_a_notice", 5500),
                assistant("msg_a2", 5600, completed=5700, tokens=161_000),
                {"id": "msg_b", "type": "user", "text": "actually", "time": {"created": 6000}},
                assistant("msg_b1", 6100, completed=6200, tokens=220_000),
            ))
            _, block = project(source.load_session_snapshot("ses_current"))
            rows = {row.event_id: row for row in block.rows}
            self.assertEqual(162_010, rows["msg_a"].watch_next_context_tokens)
            self.assertEqual((59_000, 221_010), (rows["msg_b"].watch_delta_context_tokens,
                                                 rows["msg_b"].watch_next_context_tokens))

    def test_completed_prompt_whose_only_work_follows_a_notice_is_still_listed(self):
        with source_with_current_service() as (source, server, _registration):
            server.messages["ses_current"].extend((
                {"id": "msg_second", "type": "user", "text": "second", "time": {"created": 5000}},
                notice("msg_notice", 5001),
                assistant("msg_answer", 5100, completed=5200),
                {"id": "msg_third", "type": "user", "text": "third", "time": {"created": 6000}},
                assistant("msg_third_answer", 6100, completed=6200),
            ))
            _, block = project(source.load_session_snapshot("ses_current"))
            calls = {row.event_id: row.calls for row in block.rows if not row.is_compaction}
            self.assertEqual(1, calls.get("msg_second"))
            self.assertEqual(1, calls.get("msg_third"))


if __name__ == "__main__":
    unittest.main()
