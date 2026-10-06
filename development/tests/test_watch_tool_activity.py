"""Watch prompt status rows: per-tool usage, failures, long-running tool and compact TODO."""
from __future__ import annotations

from dataclasses import replace
import io
import re
import unittest

from development.tests.test_analysis_core import make_snapshot, part
from development.tests.test_watch_rendering import tall_projection
from src.presentation import WatchRenderer
from src.presentation.watch_activity import FAILED_ROLE, status_segments, tool_summary_segments
from src.watch.models import ToolObservation, WatchRow
from src.watch.tools import observe_tools


def tool_part(pid, name, state=None, start=2190):
    data = {"tool": name}
    if state is not None:
        data["state"] = state
    return part(pid, "a_next", "root", "tool", data, start)


def observe(parts, now_ms=2200):
    snapshot = make_snapshot(running=True)
    messages = tuple(
        replace(item, parts=item.parts + tuple(parts)) if item.message_id == "a_next" else item
        for item in snapshot.messages
    )
    snapshot = replace(snapshot, messages=messages, parts=tuple(p for m in messages for p in m.parts))
    return observe_tools(snapshot, "u_next", now_ms=now_ms)


def text(segments):
    return "".join(value for value, _role in segments)


def counts(**values):
    return tuple(values.items())


MANY = counts(read=12, grep=9, edit=7, bash=6, skill=5, task=4, write=4, glob=3, patch=2, fetch=2)


class ToolAggregationTests(unittest.TestCase):
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


class SummaryWidthTests(unittest.TestCase):
    def tool(self, **kwargs):
        defaults = dict(tool_count=54, tool_counts=MANY)
        defaults.update(kwargs)
        return ToolObservation(**defaults)

    def test_other_counts_hidden_calls_and_sorts_with_groups(self):
        line = "54 tool calls · 20× other · 12× read · 9× grep · 7× edit · 6× bash"
        self.assertEqual(line, text(tool_summary_segments(self.tool(), len(line))))

    def test_full_breakdown_has_no_other_and_single_use_keeps_count(self):
        obs = ToolObservation(tool_count=3, tool_counts=counts(read=2, write=1))
        self.assertEqual("3 tool calls · 2× read · 1× write", text(tool_summary_segments(obs, 80)))
        self.assertEqual("1 tool call · 1× read", text(tool_summary_segments(
            ToolObservation(tool_count=1, tool_counts=counts(read=1)), 80)))

    def test_every_width_stays_within_budget_and_accounts_for_total(self):
        obs = self.tool(failed_count=3)
        for width in range(1, 100):
            segments = tool_summary_segments(obs, width)
            rendered = text(segments)
            self.assertLessEqual(len(rendered), width, rendered)
            if width >= len("54 tool calls · 3 failed"):
                self.assertIn("54 tool calls", rendered)
                self.assertTrue(rendered.endswith("3 failed"))
                shown = [int(item.split("×")[0]) for item in rendered.split(" · ") if "×" in item]
                self.assertTrue(not shown or sum(shown) == 54, rendered)

    def test_narrow_width_keeps_total_and_failed_before_breakdown(self):
        obs = self.tool(failed_count=3)
        self.assertEqual("54 tool calls · 3 failed", text(tool_summary_segments(obs, 24)))
        self.assertEqual("54 calls · 3 failed", text(tool_summary_segments(obs, 20)))

    def test_only_failed_part_is_red(self):
        segments = tool_summary_segments(self.tool(failed_count=2), 120)
        red = [value for value, role in segments if role == FAILED_ROLE]
        self.assertEqual(["2 failed"], red)


class StatusRowTests(unittest.TestCase):
    def test_visibility_rules(self):
        self.assertEqual([], status_segments(ToolObservation(tool_count=5), 80, "34s"))
        running = ToolObservation(tool_count=5, running_tool="bash", running_ms=34_000)
        self.assertEqual("running: bash 34s", text(status_segments(running, 80, "34s")))
        todo = ToolObservation(tool_count=5, todo_completed=2, todo_total=4, active_todo="Implement Watch renderer")
        self.assertEqual("TODO 2/4 done · Implement Watch renderer", text(status_segments(todo, 80, "")))
        both = replace(todo, running_tool="task", running_ms=134_000)
        self.assertEqual("running: task 2m14s · TODO 2/4 done · Implement Watch renderer",
                         text(status_segments(both, 80, "2m14s")))

    def test_todo_text_is_trimmed_before_progress(self):
        todo = ToolObservation(todo_completed=2, todo_total=4, active_todo="Implement Watch renderer")
        self.assertEqual("TODO 2/4 done · Implement Watch ren...", text(status_segments(todo, 38, "")))
        self.assertEqual("TODO 2/4 done · Implement...", text(status_segments(todo, 28, "")))
        self.assertEqual("TODO 2/4 done", text(status_segments(todo, 22, "")))
        self.assertEqual("TODO 2/4 done", text(status_segments(todo, 13, "")))


class RenderingTests(unittest.TestCase):
    def render(self, tool, width_note=""):
        projection = tall_projection()
        rows = (WatchRow("A", "Session A", projection.rows[0].prompt, tool=tool),) + projection.rows[1:]
        stream = io.StringIO()
        WatchRenderer({"colors": {}}, stream=stream, interactive=False).render(replace(projection, rows=rows))
        return stream.getvalue().splitlines()

    def activity_lines(self, lines):
        return [line for line in lines if line.startswith("|     ->")]

    def test_both_status_arrows_align_with_prompt_hash_and_keep_colors(self):
        colors = {"watchToolActivity": {"ansi256": 94}, "costQuotaCritical": {"ansi256": 160}}
        tool = ToolObservation(tool_count=4, tool_counts=counts(read=4), failed_count=1,
                               running_tool="bash", running_ms=34_000)
        for marker in ("", "*", "✓"):
            for interactive in (False, True):
                with self.subTest(marker=marker, interactive=interactive):
                    projection = tall_projection()
                    row = replace(projection.rows[0], marker=marker, tool=tool)
                    stream = io.StringIO()
                    WatchRenderer({"colors": colors}, stream=stream, interactive=interactive).render(
                        replace(projection, rows=(row,)))
                    raw = stream.getvalue()
                    lines = re.sub(r"\x1b\[[0-9;]*m", "", raw).splitlines()
                    prompt = next(line for line in lines if "#1 work" in line)
                    arrow = "↳" if interactive else "->"
                    status = [line for line in lines if arrow in line and line.startswith("|")]
                    self.assertEqual(2, len(status))
                    self.assertEqual([prompt.index("#")] * 2, [line.index(arrow) for line in status])
                    self.assertEqual(6, prompt.index("#"), "prompt indentation is unchanged")
                    if interactive:
                        self.assertIn("\x1b[38;5;94m    ↳ \x1b[0m", raw)
                        self.assertIn("\x1b[38;5;94mrunning: bash 34s", raw)
                        self.assertIn("\x1b[38;5;160m1 failed\x1b[0m", raw)

    def test_second_row_appears_and_disappears_dynamically(self):
        base = ToolObservation(tool_count=5, tool_counts=counts(read=3, bash=2))
        one = self.activity_lines(self.render(base))
        self.assertEqual(1, len(one))
        self.assertIn("5 tool calls · 3× read · 2× bash", one[0])
        busy = replace(base, running_tool="bash", running_ms=34_000, todo_completed=2, todo_total=4, active_todo="Do it")
        two = self.activity_lines(self.render(busy))
        self.assertEqual(2, len(two))
        self.assertIn("running: bash 34s · TODO 2/4 done · Do it", two[1])
        self.assertEqual(len(one[0]), len(two[1]))
        self.assertEqual(1, len(self.activity_lines(self.render(replace(busy, running_tool="", running_ms=0, todo_completed=4)))))

    def test_failed_is_red_when_colors_enabled(self):
        projection = tall_projection()
        tool = ToolObservation(tool_count=4, tool_counts=counts(read=4), failed_count=1)
        rows = (WatchRow("A", "Session A", projection.rows[0].prompt, tool=tool),) + projection.rows[1:]
        stream = io.StringIO()
        colors = {"costQuotaCritical": {"foreground": "Red", "background": None, "ansi256": 160},
                  "watchToolActivity": {"foreground": "DarkYellow", "background": None, "ansi256": 94}}
        WatchRenderer({"colors": colors}, stream=stream, interactive=True).render(replace(projection, rows=rows))
        self.assertIn("\x1b[38;5;160m1 failed\x1b[0m", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
