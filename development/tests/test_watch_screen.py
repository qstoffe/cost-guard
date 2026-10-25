"""Buffered frame suppression, safe row patches, shrinking and resize fallback."""
from dataclasses import replace
import io
import os
import unittest
from unittest.mock import patch

from development.tests.fixtures.terminal_buffer import TerminalBuffer
from src.presentation.watch import WatchRenderer
from src.presentation.watch_screen import WatchScreen
from src.watch.models import WatchProjection
from src.watch.redraw import needs_full_render


class WatchScreenTests(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        self.screen = WatchScreen(self.output)
        self.size = patch("src.presentation.watch_screen.shutil.get_terminal_size", return_value=os.terminal_size((160, 50)))
        self.size.start()
        self.addCleanup(self.size.stop)

    def delta(self, action):
        before = len(self.output.getvalue())
        action()
        return self.output.getvalue()[before:]

    def test_first_frame_is_one_buffered_overwrite_and_identical_frame_is_silent(self):
        self.screen.publish("Heading\nData\nWatch: Idle")
        first = self.output.getvalue()
        self.assertTrue(first.startswith("\x1b[H"))
        self.assertTrue(first.endswith("\x1b[0J"))
        self.assertNotIn("\x1b[2J", first)
        self.assertNotIn("\x1b[3J", first)
        self.assertEqual("", self.delta(lambda: self.screen.publish("Heading\nData\nWatch: Idle")))

    def test_value_change_patches_only_its_row_and_restores_status_cursor(self):
        self.screen.publish("Heading\nQuota: 50\nWatch: Idle")
        output = self.delta(lambda: self.screen.publish("Heading\nQuota: 49\nWatch: Idle"))
        self.assertEqual("\x1b[2;1H\x1b[2KQuota: 49\x1b[3;1H", output)
        self.assertNotIn("Heading", output)

    def test_shrinking_frame_erases_old_rows_below_new_status(self):
        self.screen.publish("Heading\nOld row\nOther old row\nWatch: Idle")
        output = self.delta(lambda: self.screen.publish("Heading\nWatch: Idle"))
        self.assertIn("\x1b[2;1H\x1b[2KWatch: Idle", output)
        self.assertIn("\x1b[3;1H\x1b[0J", output)
        self.assertTrue(output.endswith("\x1b[2;1H"))

    def test_status_only_writes_one_row_even_when_dashboard_wraps(self):
        self.screen.publish("X" * 300 + "\nWatch: Idle")
        output = self.delta(lambda: self.screen.status("Watch: Refreshing"))
        self.assertEqual("\r\x1b[2KWatch: Refreshing", output)
        self.assertEqual("", self.delta(lambda: self.screen.status("Watch: Refreshing")))

    def test_resize_into_overflow_clears_before_one_complete_rebuild(self):
        self.screen.publish("Heading\nData\nWatch: Idle")
        with patch("src.presentation.watch_screen.shutil.get_terminal_size", return_value=os.terminal_size((20, 2))):
            self.assertTrue(self.screen.resized())
            output = self.delta(lambda: self.screen.publish("Heading\nLonger data\nWatch: Idle"))
        self.assertTrue(output.startswith("\x1b[2J\x1b[3J\x1b[H"))
        self.assertTrue(output.endswith("\x1b[0J"))
        self.assertEqual(1, output.count("\x1b[2J"))

    def test_wide_unicode_cannot_enable_unsafe_physical_row_patches(self):
        self.assertFalse(self.screen._fits(("界" * 80,), 160, 50))
        self.assertTrue(self.screen._fits(("e\u0301" * 80,), 160, 50))

    def test_overflow_redraw_keeps_only_the_current_frame_in_scrollback(self):
        for columns, rows in ((40, 4), (10, 12)):
            with self.subTest(columns=columns, rows=rows):
                terminal = TerminalBuffer(columns, rows)
                stream = io.StringIO()
                screen = WatchScreen(stream)
                with patch("src.presentation.watch_screen.shutil.get_terminal_size",
                           return_value=os.terminal_size((columns, rows))):
                    for revision in range(3):
                        lines = ["Watch title", *(f"Prompt {index}: {revision}" for index in range(8)),
                                 f"Watch: {revision}"]
                        before = len(stream.getvalue())
                        screen.publish("\n".join(lines))
                        terminal.feed(stream.getvalue()[before:])
                        expected = [line[start:start + columns] for line in lines
                                    for start in range(0, len(line), columns)]
                        self.assertEqual(expected, [line for line in terminal.contents if line])

    def test_safe_resize_overwrites_without_clearing_history(self):
        self.screen.publish("Heading\nData\nWatch: Idle")
        with patch("src.presentation.watch_screen.shutil.get_terminal_size",
                   return_value=os.terminal_size((120, 40))):
            output = self.delta(lambda: self.screen.publish("Heading\nNew data\nWatch: Idle"))
        self.assertTrue(output.startswith("\x1b[H"))
        self.assertNotIn("\x1b[2J", output)
        self.assertNotIn("\x1b[3J", output)

    def test_shrinking_or_widening_after_overflow_removes_stale_scrollback(self):
        for narrow_size in ((160, 2), (5, 50)):
            with self.subTest(size=narrow_size):
                with patch("src.presentation.watch_screen.shutil.get_terminal_size",
                           return_value=os.terminal_size(narrow_size)):
                    self.screen.publish("Heading\nData\nWatch: Idle")
                output = self.delta(lambda: self.screen.publish("Heading\nWatch: Idle"))
                self.assertIn("\x1b[2J\x1b[3J\x1b[H", output)
                self.assertEqual("", self.delta(lambda: self.screen.publish("Heading\nWatch: Idle")))

    def test_initializing_is_idempotent_and_enrichment_becomes_visible(self):
        renderer = WatchRenderer({}, stream=self.output, interactive=True, terminal_width=160)
        renderer.render_initializing()
        self.assertEqual("", self.delta(lambda: renderer.render_initializing("V2")))
        initial = WatchProjection("Watch", "V2", (), today_pending=True)
        renderer.render(initial)
        self.assertEqual("", self.delta(lambda: renderer.render(replace(initial, now_ms=10))))
        output = self.delta(lambda: renderer.render(replace(initial, today_pending=False)))
        self.assertIn("CCost", output)
        self.assertNotIn("\x1b[H", output, "history completion patches the quota/totals row")

    def test_equal_source_resync_is_not_a_visible_change_but_real_data_is(self):
        initial = WatchProjection("Watch", "V2", (), today_pending=True)
        self.assertFalse(needs_full_render(initial, replace(initial, now_ms=10), source_changed=True))
        self.assertTrue(needs_full_render(initial, replace(initial, today_pending=False), source_changed=False))
        self.assertTrue(needs_full_render(initial, replace(initial, source_warnings=("Warning",)), source_changed=False))


if __name__ == "__main__":
    unittest.main()
