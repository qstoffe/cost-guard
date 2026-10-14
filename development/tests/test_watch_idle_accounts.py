"""Idle Watch publishes asynchronous account results in the actual rendered dashboard."""
from __future__ import annotations

import io
import tempfile
import unittest

from development.fixtures.session_snapshots import make_snapshot
from development.fixtures.watch_runtime import FakeLiveSource, MutableSource, make_service
from src.accounts.acquisition import AccountUpdate
from src.presentation import WatchRenderer
from src.watch import WatchCoordinator

ACCOUNT = "GitHub Copilot"


class RecordingRenderer(WatchRenderer):
    """Real renderer output plus a count of full frames versus status-only repaints."""

    def __init__(self):
        self.output = io.StringIO()
        super().__init__({"colors": {}, "timezone": "UTC"}, stream=self.output, interactive=True, terminal_width=160)
        self.frames: list[str] = []
        self.status_repaints = 0

    def render(self, projection):
        start = self.output.tell()
        super().render(projection)
        self.frames.append(self.output.getvalue()[start:])

    def render_status(self, projection):
        self.status_repaints += 1
        super().render_status(projection)


class NoEvents:
    """V2 pump stand-in: one quiet second per wake without real waiting."""

    def __init__(self, advance):
        self.advance = advance

    def get(self, timeout):
        self.advance(timeout)
        return None

    def stop(self):
        return None


class IdleAccountPublicationTests(unittest.TestCase):
    def watch(self, source):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        config, selection, service, _ = make_service(temp.name, source)
        snapshots = service.account_quota_snapshots()
        self.published: list[AccountUpdate] = []
        self.starts: list[int] = []
        service.begin_account_refresh = lambda: self.starts.append(service.now_ms)
        service.poll_account_refresh = lambda: self.published.pop(0) if self.published else None
        self.update = AccountUpdate(snapshots, tuple(item.key for item in snapshots))
        self.clock = [10_000_000, 0.0]
        watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                 clock_ms=lambda: int(self.clock[0]), sleep=self.advance,
                                 monotonic=lambda: self.clock[1])
        self.addCleanup(watch.close)
        return watch

    def advance(self, seconds):
        self.clock[0] += seconds * 1000
        self.clock[1] += seconds

    def idle_dashboard(self, source):
        watch = self.watch(source)
        renderer = RecordingRenderer()
        cycle = watch.initialize()
        self.assertEqual(0, cycle.projection.active_count, "OpenCode is idle")
        watch._render(renderer, cycle.projection)
        self.assertNotIn(ACCOUNT, renderer.frames[-1], "startup never waits for remote accounts")
        return watch, renderer, cycle

    def test_v1_idle_wake_renders_a_published_account_without_prompt_activity(self):
        watch, renderer, _cycle = self.idle_dashboard(MutableSource(make_snapshot()))
        loads, starts = watch.source.load_count, len(self.starts)
        self.published.append(self.update)
        watch._v1_wait(renderer)
        self.assertEqual(2, len(renderer.frames), "exactly one full redraw for the published account")
        self.assertIn(ACCOUNT, renderer.frames[-1])
        self.assertGreater(renderer.status_repaints, 1, "countdown-only wakes stay status repaints")
        self.assertEqual(loads, watch.source.load_count, "no source hydration was needed")
        self.assertEqual(starts, len(self.starts), "no redundant provider request")

    def test_projection_absorbed_before_a_source_poll_is_still_drawn(self):
        watch, renderer, cycle = self.idle_dashboard(MutableSource(make_snapshot()))
        self.published.append(self.update)
        absorbed = watch.status_projection(seconds_until_check=5)  # internal state only, never drawn
        self.assertIsNotNone(absorbed.quota)
        self.assertTrue(absorbed.quota.accounts)
        watch.poll_once()
        self.assertTrue(watch._needs_full_render(watch._rendered_projection, watch._last_projection, cycle))
        watch._advance(renderer, cycle)
        self.assertIn(ACCOUNT, renderer.frames[-1])

    def test_v2_idle_wake_renders_a_published_account(self):
        source = FakeLiveSource()
        source.snapshot = make_snapshot(generation="v2")
        watch, renderer, _cycle = self.idle_dashboard(source)
        if watch._event_pump is not None:
            watch._event_pump.stop()
        watch._event_pump = NoEvents(self.advance)
        self.published.append(self.update)
        watch._v2_wait(renderer)
        self.assertEqual(2, len(renderer.frames))
        self.assertIn(ACCOUNT, renderer.frames[-1])


if __name__ == "__main__":
    unittest.main()
