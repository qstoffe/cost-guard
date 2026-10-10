from __future__ import annotations

from contextlib import closing

import io
import sqlite3
import tempfile
import threading
import unittest
from unittest import mock
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from development.fixtures.session_snapshots import make_snapshot, part
from development.fixtures.watch_runtime import (
    MutableSource, FakeLiveSource, CountingAccountProvider, openai_account, make_service,
)
from src.config import load_configuration
from src.domain import QuotaComponent, TokenUsage
from src.presentation import ReportRenderer, WatchRenderer
from src.reports import ReportRequest
from src.sources.base import SourceChange
from src.version import DISPLAY_VERSION, RELEASE_DATE
from src.watch import LiveEventPump, WatchCoordinator
from src.watch.observers import PumpResult

ROOT = Path(__file__).resolve().parents[2]


class WatchGatingTests(unittest.TestCase):
    def test_v1_unchanged_inactive_root_uses_batch_revision_without_rehydration(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(make_snapshot(running=False))
            config, selection, service, _db = make_service(td, source)
            clock = [2200]
            watch = WatchCoordinator(
                selection=selection, report_service=service, config=config,
                clock_ms=lambda: clock[0], sleep=lambda _s: None,
            )
            initial = watch.initialize()
            self.assertEqual(1, source.load_count)
            self.assertEqual(("root",), initial.hydrated_roots)
            analysis_revision_calls = source.revision_calls
            clock[0] = 2250
            cycle = watch.poll_once()
            self.assertEqual((), cycle.changed_roots)
            self.assertEqual(1, source.load_count, "unchanged roots must not hydrate again")
            self.assertGreaterEqual(source.batch_calls, 2)
            self.assertEqual(analysis_revision_calls, source.revision_calls, "unchanged Watch gating must not invoke per-root analysis revisions")

    def test_running_root_rehydrates_each_refresh_even_when_cheap_revision_is_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            snapshot = make_snapshot(running=True)
            messages = tuple(item for item in snapshot.messages if item.message_id not in {"u_comp", "a_comp"})
            snapshot = replace(
                snapshot,
                messages=messages,
                parts=tuple(part for message in messages for part in message.parts),
                events=tuple(item for item in snapshot.events if item.event_id != "u_comp"),
                invocations=tuple(item for item in snapshot.invocations if item.invocation_id != "i_comp"),
            )
            source = MutableSource(snapshot)
            config, selection, service, _db = make_service(td, source)
            clock = [2200]
            watch = WatchCoordinator(
                selection=selection, report_service=service, config=config, clock_ms=lambda: clock[0]
            )
            initial = watch.initialize()
            initial_row = next(row for row in initial.projection.rows if row.prompt.event_id == "u_next")
            initial_next = initial_row.prompt.watch_next_context_tokens
            self.assertIsNotNone(initial_next)

            updated_invocations = tuple(
                replace(item, tokens=TokenUsage(input=30, output=14))
                if item.invocation_id == "i_next" else item
                for item in source.snapshot.invocations
            )
            source.snapshot = replace(source.snapshot, invocations=updated_invocations)
            clock[0] = 2300
            cycle = watch.poll_once()

            self.assertEqual((), cycle.changed_roots, "cheap V1 revision intentionally stayed unchanged")
            self.assertEqual(("root",), cycle.hydrated_roots)
            self.assertEqual(2, source.load_count)
            current = next(row for row in cycle.projection.rows if row.prompt.event_id == "u_next")
            self.assertEqual(initial_next + 10, current.prompt.watch_next_context_tokens)
            self.assertEqual(10, current.prompt.watch_delta_context_tokens - initial_row.prompt.watch_delta_context_tokens)

    def test_changed_revision_rehydrates_and_running_to_completed_gets_recent_marker(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource()
            config, selection, service, _db = make_service(td, source)
            clock = [2200]
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: clock[0])
            initial = watch.initialize()
            running = next(row for row in initial.projection.rows if row.prompt.event_id == "u_next")
            self.assertEqual("+", running.marker)
            source.snapshot = replace(make_snapshot(running=False), source_revision="v1-rev-2")
            clock[0] = 2400
            cycle = watch.poll_once()
            self.assertEqual(("root",), cycle.changed_roots)
            self.assertEqual(2, source.load_count)
            completed = next(row for row in cycle.projection.rows if row.prompt.event_id == "u_next")
            self.assertEqual("✓", completed.marker)

    def test_session_watch_maps_child_id_to_root_tree(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource()
            config, selection, service, _db = make_service(td, source)
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, session_id="child", clock_ms=lambda: 2200)
            cycle = watch.initialize()
            self.assertEqual(("root",), cycle.hydrated_roots)
            self.assertTrue(cycle.projection.rows)
            self.assertTrue(all(row.session_id == "root" for row in cycle.projection.rows))

    def test_watch_shows_plus_native_quota_without_fictional_remaining_equivalent(self):
        with tempfile.TemporaryDirectory() as td:
            config, selection, service, _db = make_service(td, MutableSource())
            projection = WatchCoordinator(
                selection=selection, report_service=service, config=config, clock_ms=lambda: 2200,
            ).initialize().projection
            self.assertEqual(Decimal("70"), projection.quota.accounts[0].account.quotas[0].remaining)
            openai = openai_account()
            projection = replace(projection, quota=replace(
                projection.quota, accounts=projection.quota.accounts + (openai,),
            ))
            stream = io.StringIO()
            WatchRenderer(config, stream=stream, interactive=False).render(projection)
            text = stream.getvalue()
            self.assertIn("OpenAI Plus", text)
            self.assertIn("5h     " + "█" * 8 + "░" * 2 + "  75%", text)
            self.assertIn("Week " + "█" * 6 + "░" * 4 + "  60%", text)
            self.assertNotIn(" used", text)
            self.assertNotIn("equiv", text)

    def test_watch_quota_footer_lists_detected_accounts_and_status_stays_last(self):
        with tempfile.TemporaryDirectory() as td:
            config, selection, service, _db = make_service(td, MutableSource())
            projection = WatchCoordinator(
                selection=selection, report_service=service, config=config, clock_ms=lambda: 2200,
            ).initialize().projection
            openai = openai_account()

            def footer(accounts):
                quota = replace(projection.quota, accounts=accounts)
                stream = io.StringIO()
                WatchRenderer(config, stream=stream, interactive=False).render(replace(projection, quota=quota))
                return stream.getvalue().splitlines()

            copilot = replace(projection.quota.accounts[0], label="GitHub Copilot Business")
            copilot_only = footer((copilot,))
            self.assertTrue(any("GitHub Copilot Business" in line for line in copilot_only))
            self.assertTrue(any("Month  " + "█" * 7 + "░" * 3 + "  70%" in line for line in copilot_only))
            self.assertFalse(any(line.startswith(("Cost today %:", "Local calculated:", "GitHub reported:", "~Copilot equiv:")) for line in copilot_only))
            self.assertFalse(any(line.startswith("OpenAI ") for line in copilot_only))

            openai_only = footer((openai,))
            self.assertTrue(any(line.startswith("Token Mix % · ") for line in openai_only))
            self.assertNotIn("Quotas:", openai_only)
            self.assertFalse(any(line.startswith(("Cost today %:", "Local calculated:", "GitHub reported:", "Copilot ")) for line in openai_only))
            self.assertTrue(any("OpenAI Plus" in line for line in openai_only))
            self.assertTrue(any("5h    " + "█" * 8 + "░" * 2 + "  75% · Reset@" in line for line in openai_only))
            self.assertTrue(any("Week " + "█" * 6 + "░" * 4 + "  60% · Reset@" in line for line in openai_only))
            self.assertTrue(openai_only[-1].startswith("Watch:"))

            both = footer((copilot, openai))
            self.assertLess(next(i for i, line in enumerate(both) if line.startswith("GitHub Copilot")),
                            next(i for i, line in enumerate(both) if line.startswith("OpenAI Plus")))
            self.assertTrue(both[-1].startswith("Watch:"))

            neither = footer(())
            self.assertNotIn("Quotas:", neither)
            self.assertFalse(any(line.startswith(("Copilot ", "OpenAI ")) for line in neither))
            self.assertTrue(neither[-1].startswith("Watch:"))

            unknown = replace(openai, account=replace(openai.account, quotas=(QuotaComponent("5-hour"),)))
            unknown_lines = footer((unknown,))
            self.assertTrue(any("5h    N/A" in line for line in unknown_lines))

            unknown_copilot = replace(copilot, account=replace(copilot.account, quotas=(), plan=None))
            missing = footer((unknown_copilot,))
            self.assertTrue(any("Quota available" in line for line in missing))

    def test_cost_quota_shows_plus_windows_without_unsupported_dollar_equivalents(self):
        with tempfile.TemporaryDirectory() as td:
            config, _selection, service, _db = make_service(td, MutableSource())
            report = service.build(ReportRequest())
            openai = openai_account()
            report = replace(report, accounts_quotas=replace(
                report.accounts_quotas, accounts=report.accounts_quotas.accounts + (openai,),
            ))
            stream = io.StringIO()
            ReportRenderer(config, stream=stream, color_enabled=False, terminal_width=160).render(report)
            section = stream.getvalue().split("OpenAI Plus", 1)[1]
            section = "OpenAI Plus" + section
            for text in ("OpenAI Plus", "5h", "Week", "75%", "60%"):
                self.assertIn(text, section)
            self.assertNotIn("~5-hour remaining", section)
            self.assertNotIn("~weekly remaining", section)


    def test_source_changes_do_not_multiply_account_quota_network_refreshes(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource()
            account = CountingAccountProvider()
            config, selection, service, _db = make_service(td, source, account_provider=account)
            clock = [100_000]
            watch = WatchCoordinator(
                selection=selection, report_service=service, config=config, clock_ms=lambda: clock[0]
            )
            watch.initialize()
            self.assertEqual(1, account.calls)

            for index, now in enumerate((110_000, 120_000, 150_000), start=2):
                source.snapshot = replace(source.snapshot, source_revision=f"change-{index}")
                clock[0] = now
                watch.poll_once()
            self.assertEqual(1, account.calls, "OpenCode changes must not trigger repeated account requests")

            source.snapshot = replace(source.snapshot, source_revision="change-after-minute")
            clock[0] = 161_000
            watch.poll_once()
            self.assertEqual(2, account.calls)

    def test_event_hint_conservatively_rehydrates_even_before_revision_changes(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource()
            config, selection, service, _db = make_service(td, source)
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 2200)
            watch.initialize()
            cycle = watch.poll_once(hinted_session_ids=("child",))
            self.assertEqual(("root",), cycle.changed_roots)
            self.assertEqual(2, source.load_count)


class LivePumpTests(unittest.TestCase):
    def test_v2_change_then_disconnect_requires_resync(self):
        source = FakeLiveSource(SourceChange("fake-v2", "session.updated", "root"))
        pump = LiveEventPump(source)
        pump.start()
        first = pump.get(1.0)
        second = pump.get(1.0)
        self.assertIsNotNone(first)
        self.assertEqual("root", first.change.session_id)
        self.assertIsNotNone(second)
        self.assertTrue(second.resync_required)
        pump.stop()

    def test_force_resync_hydrates_even_with_equal_revision(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource()
            config, selection, service, _db = make_service(td, source)
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 2200)
            watch.initialize()
            cycle = watch.poll_once(force_resync=True)
            self.assertTrue(cycle.resynced)
            self.assertEqual(("root",), cycle.hydrated_roots)
            self.assertEqual(2, source.load_count)


    def test_v2_event_hint_is_buffered_until_scheduled_active_refresh(self):
        class Renderer:
            def __init__(self):
                self.statuses = []
            def render_status(self, projection):
                self.statuses.append(projection.status)

        class Pump:
            def __init__(self, now):
                self.now = now
                self.calls = 0
            def get(self, timeout):
                self.calls += 1
                if self.calls == 1:
                    return PumpResult(change=SourceChange("fake-v2", "session.updated", "root"))
                self.now[0] += timeout
                return None

        with tempfile.TemporaryDirectory() as td:
            source = FakeLiveSource()
            config, selection, service, _db = make_service(td, source)
            config["sessionWatchIntervalSeconds"] = 5
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 2200)
            watch.initialize()
            now = [0.0]
            pump = Pump(now)
            watch._event_pump = pump  # deterministic scheduler seam; no live thread in this regression
            renderer = Renderer()
            with mock.patch("src.watch.coordinator.time.monotonic", side_effect=lambda: now[0]):
                resync, hints = watch._v2_wait(renderer)
            self.assertFalse(resync)
            self.assertEqual(("root",), hints)
            self.assertGreaterEqual(now[0], 5.0, "event hints must not trigger an early/flappy refresh")
            self.assertTrue(any("Next refresh" in value for value in renderer.statuses))


class WatchPresentationTests(unittest.TestCase):
    def test_running_tool_todo_is_derived_from_same_hydrated_snapshot(self):
        snapshot = make_snapshot(running=True)
        todo = part("todo", "a_next", "root", "tool", {
            "tool": "todowrite",
            "state": {
                "time": {"start": 2190},
                "input": {"todos": [
                    {"status": "completed", "content": "one"},
                    {"status": "in_progress", "content": "two now"},
                ]},
            },
        }, 2190)
        messages = tuple(replace(item, parts=item.parts + (todo,)) if item.message_id == "a_next" else item for item in snapshot.messages)
        snapshot = replace(snapshot, messages=messages, parts=tuple(p for m in messages for p in m.parts), source_revision="tool-rev")
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(snapshot)
            config, selection, service, _db = make_service(td, source)
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 2200)
            projection = watch.initialize().projection
            row = next(item for item in projection.rows if item.prompt.event_id == "u_next")
            self.assertIsNotNone(row.tool)
            self.assertEqual(1, row.tool.tool_count)
            self.assertEqual(1, row.tool.todo_completed)
            self.assertEqual(2, row.tool.todo_total)
            self.assertEqual("two now", row.tool.active_todo)

    def test_current_v2_tool_name_and_top_level_time_show_count_and_todo_text(self):
        snapshot = make_snapshot(running=True)
        todo = replace(part("todo-v2", "a_next", "root", "tool", {
            "name": "todowrite",
            "state": {"status": "running", "input": {"todos": [
                {"status": "completed", "content": "one"},
                {"status": "in_progress", "content": "current"},
            ]}},
        }, 2190), updated_at_ms=0)
        messages = tuple(replace(item, parts=item.parts + (todo,)) if item.message_id == "a_next" else item for item in snapshot.messages)
        snapshot = replace(snapshot, messages=messages, parts=tuple(p for m in messages for p in m.parts), source_revision="current-v2-tool")
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(snapshot)
            config, selection, service, _db = make_service(td, source)
            projection = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 2200).initialize().projection
            row = next(item for item in projection.rows if item.prompt.event_id == "u_next")
            self.assertEqual(1, row.tool.tool_count)
            self.assertEqual("current", row.tool.active_todo)
            stream = io.StringIO()
            WatchRenderer(config, stream=stream, interactive=False).render(projection)
            self.assertIn("1/2 done · current", stream.getvalue())

    def test_redirected_renderer_is_stable_and_uses_ascii_tool_marker(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource()
            config, selection, service, _db = make_service(td, source)
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 2200)
            projection = watch.initialize().projection
            stream = io.StringIO()
            WatchRenderer(config, stream=stream, interactive=False).render(projection)
            text = stream.getvalue()
            self.assertIn(f"Cost Guard {DISPLAY_VERSION} ({RELEASE_DATE}) — Prompt watch — Source: OpenCode V1", text)
            self.assertIn("Session / prompt", text)
            self.assertIn("Δctx → Next Ictx", text)
            self.assertIn("Month", text)
            self.assertNotIn("Cost today %:", text)
            self.assertIn("->", text)
            self.assertNotIn("\x1b[2J", text)
            self.assertNotIn("\x1b[3J", text)


class _TtyBuffer(io.StringIO):
    def isatty(self):
        return True


class WatchLayoutRegressionTests(unittest.TestCase):
    def test_watch_table_width_is_fixed_and_status_is_single_overwritable_row(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource()
            config, selection, service, _db = make_service(td, source)
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 2200)
            projection = watch.initialize().projection
            layout_stream = io.StringIO()
            WatchRenderer(config, stream=layout_stream, interactive=False).render(projection)
            layout_text = layout_stream.getvalue()
            table_lines = [line for line in layout_text.splitlines() if line.startswith("|")]
            self.assertTrue(table_lines)
            self.assertTrue(all(len(line) == 119 for line in table_lines))
            self.assertNotIn("\n\n|", layout_text)

            stream = _TtyBuffer()
            renderer = WatchRenderer(config, stream=stream, interactive=True)
            renderer.render(projection)
            text = stream.getvalue()
            clear = "\x1b[2J\x1b[3J\x1b[H"
            self.assertEqual(text.count(clear), 1)
            self.assertFalse(text.endswith("\n"), "interactive status must remain on the current row")
            renderer.render_status(replace(projection, status="Refreshing...", status_active=True))
            renderer.render_status(replace(projection, status="Idle · Next prompt check: 00:30", status_active=False, active_count=0))
            tail = stream.getvalue()
            self.assertEqual(tail.count(clear), 1, "status updates must not clear the dashboard")
            self.assertIn("\r\x1b[2K", tail)
            self.assertIn("Watch: Refreshing...", tail)
            self.assertIn("Watch: Idle · Next prompt check: 00:30", tail)
            self.assertNotIn("Refreshing...\nWatch: Idle", tail)
            renderer.render(projection)
            self.assertEqual(stream.getvalue().count(clear), 2, "each full redraw must clear scrollback")

    def test_watch_initialization_has_transient_heading_and_adjacent_progress(self):
        config = dict(load_configuration(ROOT).values)
        stream = _TtyBuffer()
        renderer = WatchRenderer(config, stream=stream, interactive=True)
        renderer.render_initializing("V2")
        renderer.render_startup_status("Watch: [####----] 50% / Analyzing")
        text = stream.getvalue()
        self.assertEqual(text.count("\x1b[2J\x1b[3J\x1b[H"), 1)
        from src.version import mode_heading
        self.assertIn(mode_heading("Watch") + "\n", text)
        self.assertNotIn("Session / prompt", text)
        self.assertNotIn("Token Mix %", text)
        self.assertNotIn("\n\n", text)
        self.assertNotIn("Quotas:", text)
        self.assertNotIn("Cost today %:     loading...", text)
        self.assertIn("\r\x1b[2K", text)
        self.assertIn("Watch: [####----] 50% / Analyzing", text)

    def test_running_watch_uses_active_refresh_cadence_and_hash_prompt_marker(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(make_snapshot(running=True))
            config, selection, service, _db = make_service(td, source)
            config["sessionWatchIntervalSeconds"] = 5
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 2200)
            projection = watch.initialize().projection
            self.assertGreater(projection.active_count, 0)
            self.assertIn("Next refresh: 00:05", projection.status)
            self.assertNotIn("next prompt check", projection.status)
            stream = io.StringIO()
            WatchRenderer(config, stream=stream, interactive=False).render(projection)
            self.assertIn("#2 ", stream.getvalue())
            self.assertNotIn("~$", "\n".join(line for line in stream.getvalue().splitlines() if line.startswith("|")))

    def test_refresh_completion_resets_countdown_to_full_interval(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(make_snapshot(running=False))
            config, selection, service, _db = make_service(td, source)
            config["sessionWatchIntervalSeconds"] = 5
            clock = [2200]
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: clock[0])
            initial = watch.initialize()
            self.assertIn("Next prompt check: 00:30", initial.projection.status)
            clock[0] = 99_000
            cycle = watch.poll_once()
            self.assertIn("Next prompt check: 00:30", cycle.projection.status)
            self.assertNotIn("Refreshing", cycle.projection.status)

    def test_auto_interval_uses_bounded_refresh_ema(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(make_snapshot(running=False))
            config, selection, service, _db = make_service(td, source)
            config["sessionWatchIntervalSeconds"] = "auto"
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 2200)
            watch._record_refresh_duration(2.0)
            self.assertEqual(12, watch._delay_seconds(0))
            watch._record_refresh_duration(20.0)
            self.assertEqual(30, watch._delay_seconds(1))


class ConcurrentRuntimeTests(unittest.TestCase):
    def test_two_watch_instances_and_one_report_share_cache_without_deadlock_or_corruption(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(make_snapshot(running=False))
            config, selection, _service, db = make_service(td, source, now_ms=4000)
            failures = []
            barrier = threading.Barrier(3)

            def watch_worker():
                try:
                    _, sel, service, _ = make_service(td, source, now_ms=4000)
                    watch = WatchCoordinator(selection=sel, report_service=service, config=config, clock_ms=lambda: 4000)
                    barrier.wait()
                    watch.initialize()
                    for _ in range(3):
                        watch.poll_once()
                except BaseException as exc:
                    failures.append(exc)

            def report_worker():
                try:
                    _, sel, service, _ = make_service(td, source, now_ms=4000)
                    barrier.wait()
                    for _ in range(3):
                        service.build(ReportRequest())
                except BaseException as exc:
                    failures.append(exc)

            threads = [threading.Thread(target=watch_worker), threading.Thread(target=watch_worker), threading.Thread(target=report_worker)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(15)
            self.assertFalse(any(thread.is_alive() for thread in threads), "concurrent Cost Guard work deadlocked")
            self.assertEqual([], failures)
            with closing(sqlite3.connect(db.paths.database)) as connection:
                self.assertEqual("ok", connection.execute("PRAGMA integrity_check").fetchone()[0])

    def test_watch_hot_path_contains_no_subprocess_start(self):
        paths = [
            ROOT / "src" / "watch" / "coordinator.py",
            ROOT / "src" / "watch" / "observers.py",
            ROOT / "src" / "sources" / "opencode_v1.py",
            ROOT / "src" / "sources" / "opencode_v2.py",
        ]
        forbidden = ("import subprocess", "from subprocess", "Popen(", "subprocess.run(", "subprocess.Popen(")
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, f"{path.name}: {token}")


if __name__ == "__main__":
    unittest.main()
