"""Watch prompt status rows: per-tool usage, failures, long-running tool and compact TODO."""
from __future__ import annotations

from dataclasses import replace
import json
from dataclasses import asdict
import unittest

from development.tests.fixtures.session_snapshots import make_snapshot, part
from src.watch.models import ToolOutcome
from src.watch.tools import observe_tools, without_live_activity


def tool_part(pid, name, state=None, start=2190):
    data = {"tool": name}
    if state is not None:
        data["state"] = state
    return part(pid, "a_next", "root", "tool", data, start)


def observe(parts, now_ms=2200, *, include_invocations=False):
    snapshot = make_snapshot(running=True)
    messages = tuple(
        replace(item, parts=item.parts + tuple(parts)) if item.message_id == "a_next" else item
        for item in snapshot.messages
    )
    snapshot = replace(snapshot, messages=messages, parts=tuple(p for m in messages for p in m.parts))
    return observe_tools(snapshot, "u_next", now_ms=now_ms, include_invocations=include_invocations)


class ToolAggregationTests(unittest.TestCase):
    def test_failed_physical_calls_keep_separate_exact_inputs_even_when_identical(self):
        parts = [replace(tool_part(f"p-{i}", "read", {"status": "error",
                 "input": {"filePath": path}, "error": {"code": "ENOENT"}}),
                 data={"tool": "read", "callID": f"call-{i}", "state": {"status": "error",
                       "input": {"filePath": path}, "error": {"code": "ENOENT"}}})
                 for i, path in enumerate(("src/a.py", "src/b.py", "src/b.py"))]
        copied = replace(parts[0], part_id="copy", updated_at_ms=2300)

        observed = observe([*parts, copied], include_invocations=True)

        self.assertEqual(3, observed.tool_count)
        self.assertEqual((ToolOutcome("read", "failed", 3),), observed.tool_outcomes)
        self.assertEqual(3, len({item.invocation.identity for item in observed.failed_invocations}))
        self.assertEqual(["filePath:\nsrc/a.py", "filePath:\nsrc/b.py", "filePath:\nsrc/b.py"],
                         [item.invocation.text for item in observed.failed_invocations])
        self.assertEqual(["File not found"] * 3, [item.reason for item in observed.failed_invocations])
        self.assertEqual(observed.failed_invocations, without_live_activity(observed).failed_invocations)
        self.assertEqual((), observe(parts).failed_invocations, "CLI has no invocation payload")

    def test_failure_details_reuse_privacy_filter_and_never_copy_arbitrary_error_output(self):
        parts = [
            tool_part("shell", "shell", {"status": "error", "input": {
                "command": "python task.py --token synthetic-private --check", "workdir": "src",
                "environment": {"SECRET": "synthetic-private"}, "content": "synthetic-private"},
                "error": {"code": "EACCES", "message": "synthetic-private"}, "output": "synthetic-private"}),
            tool_part("missing", "read", {"status": "error", "error": "synthetic-private"}),
            tool_part("html", "grep", {"status": "error", "input": {"pattern": "<script>literal</script>", "path": "src"},
                "error": "File not found: synthetic-private"}),
            tool_part("cancelled", "shell", {"status": "error", "error": {"code": "CANCELLED"}}),
            tool_part("fake", "shell", {"status": "completed", "output": "error synthetic-private"}),
        ]

        observed = observe(parts, include_invocations=True)

        self.assertEqual((3, 1, 5), (observed.failed_count, observed.cancelled_count, observed.tool_count))
        self.assertEqual(3, len(observed.failed_invocations))
        wire = json.dumps([asdict(item) for item in observed.failed_invocations])
        self.assertNotIn("synthetic-private", wire)
        by_name = {item.tool_name: item for item in observed.failed_invocations}
        self.assertIn("python task.py --token [redacted] --check", by_name["shell"].invocation.text)
        self.assertIn("workdir:\nsrc", by_name["shell"].invocation.text)
        self.assertEqual("Permission denied", by_name["shell"].reason)
        self.assertIn("No source input", by_name["read"].invocation.qualification)
        self.assertEqual("Failure reason unavailable", by_name["grep"].reason)
        self.assertIn("<script>literal</script>", by_name["grep"].invocation.text)

    def test_large_failure_display_budget_keeps_all_counts_and_deterministic_source_order(self):
        parts = [tool_part(f"p-{i:03}", "read", {"status": "error",
                 "input": {"filePath": "x" * 3000}}, 1000 + i) for i in range(200)]
        observed = observe(parts, include_invocations=True)
        reversed_observation = observe(list(reversed(parts)), include_invocations=True)
        self.assertEqual((200, 200), (observed.tool_count, observed.failed_count))
        self.assertEqual(10, len(observed.failed_invocations))
        self.assertEqual(observed.failed_invocations, reversed_observation.failed_invocations)
        self.assertLessEqual(sum(len(item.invocation.text) for item in observed.failed_invocations), 4096)
        self.assertTrue(all("display budget" in item.invocation.qualification for item in observed.failed_invocations))

    def test_authoritative_success_and_wrong_source_remove_only_affected_failure_details(self):
        first = tool_part("first", "read", {"status": "error", "input": {"filePath": "src/a.py"}})
        second = tool_part("second", "read", {"status": "error", "input": {"filePath": "src/b.py"}})
        corrected = replace(first, updated_at_ms=2300, data={"tool": "read", "state": {"status": "completed"}})
        retired = replace(first, provenance=replace(first.provenance, source_generation="retired"))
        observed = observe([first, second, corrected], include_invocations=True)
        self.assertEqual((ToolOutcome("read", "failed", 1),), observed.tool_outcomes)
        self.assertEqual(["filePath:\nsrc/b.py"], [item.invocation.text for item in observed.failed_invocations])
        uncertain = observe([retired, second], include_invocations=True)
        self.assertEqual(2, uncertain.failed_count)
        self.assertEqual(["filePath:\nsrc/b.py"], [item.invocation.text for item in uncertain.failed_invocations])

    def test_known_direct_script_failure_uses_the_same_physical_input_not_output_details(self):
        command = "python C:/fixture/skills/auto-github-api/scripts/github_api.py rest-get"
        scripted = tool_part("script", "shell", {"status": "completed", "input": {"command": command},
            "output": json.dumps({"schema": "opencode-toolkit/github-api/v1", "status": "error",
                                 "error": {"class": "HTTP_ERROR", "message": "private-output"}})})
        observed = observe([scripted, scripted], include_invocations=True)
        self.assertEqual((1, 1), (observed.tool_count, observed.failed_count))
        self.assertEqual("command:\n" + command, observed.failed_invocations[0].invocation.text)
        self.assertEqual("Failure reason unavailable", observed.failed_invocations[0].reason)
        self.assertNotIn("private-output", json.dumps(asdict(observed)))

    def test_counts_by_actual_tool_name_sorted_descending(self):
        obs = observe([tool_part(f"p{i}", name) for i, name in enumerate(["read", "bash", "read", "grep", "read", "bash"])])
        self.assertEqual(6, obs.tool_count)
        self.assertEqual((("read", 3), ("bash", 2), ("grep", 1)), obs.tool_counts)

    def test_failed_is_additional_and_keeps_normal_count(self):
        obs = observe([
            tool_part("a", "read", {"status": "error", "error": "File not found"}),
            tool_part("b", "read", {"status": "completed", "output": "exit 1 error"}),
            tool_part("c", "bash", {"status": "completed", "metadata": {"exit": 2}}),
        ])
        self.assertEqual(3, obs.tool_count)
        self.assertEqual(1, obs.failed_count)
        self.assertEqual((("read", 2), ("bash", 1)), obs.tool_counts)

    def test_cancellation_is_not_a_failure(self):
        obs = observe([
            tool_part("a", "bash", {"status": "error", "error": "Tool execution aborted"}),
            tool_part("b", "bash", {"status": "error", "error": {"name": "AbortedError"}}),
            tool_part("c", "bash", {"status": "error", "error": "x", "metadata": {"interrupted": True}}),
            tool_part("d", "bash", {"status": "error", "error": "Command failed"}),
        ])
        self.assertEqual(4, obs.tool_count)
        self.assertEqual(1, obs.failed_count)
        self.assertEqual(3, obs.cancelled_count)
        self.assertEqual(4, obs.failed_or_cancelled_count)
        self.assertEqual((ToolOutcome("bash", "failed", 1), ToolOutcome("bash", "cancelled", 3)), obs.tool_outcomes)

    def test_mixed_outcomes_are_subsets_of_all_physical_calls(self):
        obs = observe([
            tool_part("good", "grep", {"status": "completed"}),
            tool_part("bad-1", "grep", {"status": "error", "error": "bad pattern"}),
            tool_part("bad-2", "grep", {"status": "error", "error": "bad pattern"}),
            tool_part("cancel", "grep", {"status": "error", "error": {"code": "CANCELLED"}}),
            tool_part("other", "execute", {"status": "error", "error": "missing"}),
            tool_part("unknown", "", {"status": "error", "metadata": {"interrupted": True}}),
            tool_part("custom", "<custom-tool>", {"status": "error", "error": "missing"}),
        ])
        self.assertEqual(7, obs.tool_count)
        self.assertEqual((("grep", 4), ("<custom-tool>", 1), ("execute", 1), ("unknown", 1)), obs.tool_counts)
        self.assertEqual((ToolOutcome("grep", "failed", 2), ToolOutcome("<custom-tool>", "failed", 1),
                          ToolOutcome("execute", "failed", 1), ToolOutcome("grep", "cancelled", 1),
                          ToolOutcome("unknown", "cancelled", 1)), obs.tool_outcomes)
        self.assertEqual(4, obs.failed_count)
        self.assertEqual(2, obs.cancelled_count)
        self.assertEqual(6, sum(item.count for item in obs.tool_outcomes))
        self.assertEqual(6, obs.failed_or_cancelled_count)

    def test_untrusted_or_missing_outcomes_do_not_invent_failure_or_cancellation(self):
        obs = observe([
            tool_part("a", "execute", {"status": "completed", "output": "error cancelled interrupted"}),
            tool_part("b", "execute", {"status": "completed", "metadata": {"exit": 1}}),
            tool_part("c", "execute", {"error": "command failed"}),
            tool_part("d", "execute", {"status": "completed", "output": {
                "schema": "unverified/v1", "status": "error", "error": {"class": "CANCELLED"}}}),
            tool_part("e", "execute"),
        ])
        self.assertEqual(5, obs.tool_count)
        self.assertEqual((), obs.tool_outcomes)
        self.assertEqual(0, obs.failed_or_cancelled_count)

    def test_latest_call_copy_and_authoritative_correction_replace_outcomes(self):
        early = tool_part("early", "grep", {"status": "error", "error": "bad pattern"})
        early = replace(early, data={**early.data, "callID": "same"})
        final = tool_part("late", "grep", {"status": "error", "error": {"type": "AbortError"}})
        final = replace(final, data={**final.data, "callID": "same"}, updated_at_ms=2300)
        obs = observe([early, final, final, early])
        self.assertEqual(1, obs.tool_count)
        self.assertEqual((ToolOutcome("grep", "cancelled", 1),), obs.tool_outcomes)
        self.assertEqual((0, 1), (obs.failed_count, obs.cancelled_count))
        retained = without_live_activity(replace(obs, running_tool="grep", running_ms=10_000))
        self.assertEqual(obs.tool_outcomes, retained.tool_outcomes)
        self.assertFalse(retained.has_status_row)
        corrected = replace(final, data={**final.data, "state": {"status": "completed"}}, updated_at_ms=2400)
        self.assertEqual((), observe([early, final, corrected]).tool_outcomes)


class RunningToolTests(unittest.TestCase):
    def test_threshold_and_longest_running(self):
        now = 100_000
        short = tool_part("s", "read", {"status": "running"}, now - 9_999)
        edge = tool_part("e", "grep", {"status": "running"}, now - 10_000)
        longest = tool_part("l", "task", {"status": "running"}, now - 75_000)
        done = tool_part("d", "bash", {"status": "completed"}, now - 90_000)
        self.assertEqual("", observe([short], now).running_tool)
        self.assertEqual(("grep", 10_000), (lambda o: (o.running_tool, o.running_ms))(observe([short, edge], now)))
        both = observe([edge, longest, done, short], now)
        self.assertEqual(("task", 75_000), (both.running_tool, both.running_ms))

    def test_leaving_running_state_removes_status(self):
        start = 1_000
        running = observe([tool_part("a", "bash", {"status": "running"}, start)], 60_000)
        finished = observe([tool_part("a", "bash", {"status": "completed"}, start)], 61_000)
        self.assertTrue(running.has_status_row)
        self.assertFalse(finished.has_status_row)

    def test_explicit_interruption_cannot_linger_as_running(self):
        obs = observe([tool_part("a", "execute", {
            "status": "running", "metadata": {"interrupted": True}}, 1000)], 60_000)
        self.assertEqual((ToolOutcome("execute", "cancelled", 1),), obs.tool_outcomes)
        self.assertFalse(obs.has_status_row)


class TodoCompatibilityTests(unittest.TestCase):
    def todo_state(self):
        return {"status": "completed", "input": {"todos": [
            {"status": "completed", "content": "one"},
            {"status": "in_progress", "content": "two now"},
        ]}}

    def test_current_and_legacy_names(self):
        for name in ("todo", "todowrite", "todo_write", "TodoWrite"):
            with self.subTest(name=name):
                obs = observe([tool_part("t", name, self.todo_state())])
                self.assertEqual((1, 2, "two now"), (obs.todo_completed, obs.todo_total, obs.active_todo))
                self.assertEqual((("todo" if name == "todo" else name.lower(), 1),), obs.tool_counts)

    def test_completed_todo_has_no_status_row(self):
        state = {"status": "completed", "input": {"todos": [{"status": "completed", "content": "one"}]}}
        self.assertFalse(observe([tool_part("t", "todo", state)]).has_status_row)


if __name__ == "__main__":
    unittest.main()
