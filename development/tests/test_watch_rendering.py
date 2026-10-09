"""Watch full-frame tail cleanup stays separate from status-only updates."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import io
import unittest

from src.domain import AccountRef, AccountSnapshot, QuotaComponent
from src.presentation import WatchRenderer
from src.reports.models import AccountProjection, AccountsQuotasProjection, PromptProjection
from src.watch.models import ToolObservation, WatchProjection, WatchRow

CLEAR = "\x1b[2J\x1b[3J\x1b[H"
ERASE_TAIL = "\x1b[0J"
STATUS = "Idle · Next prompt check: 00:30"


class FlushedBuffer(io.StringIO):
    def __init__(self):
        super().__init__()
        self.flushed = []

    def flush(self):
        self.flushed.append(self.getvalue())


def tall_projection():
    prompt = PromptProjection(
        at_ms=1000, prompt_number=1, event_id="event", label="#1", preview="work",
        model_effort="model", ccost=Decimal(0), cost_estimated=False,
        unresolved_cost=False, calls=0, incoming_context_tokens=None,
        incoming_context_ccost=None, extra_ccost=None, token_mix_percent=None,
        in_progress=True,
    )
    account = AccountProjection(AccountSnapshot(
        AccountRef("fixture", "provider", "account"), 2000, "Provider", "Plan",
        quotas=(QuotaComponent("weekly", "rolling", remaining_fraction=Decimal("0.5")),),
    ), "Provider Plan")
    return WatchProjection(
        "Watch", "V2", (
            WatchRow("A", "Session A", prompt, tool=ToolObservation(2, 1, 2, "current task")),
            WatchRow("B", "Session B", replace(prompt, in_progress=False)),
        ),
        source_warnings=("source warning",),
        quota=AccountsQuotasProjection((account,), ()),
        quota_stale=True, session_warnings={"A": "[context threshold exceeded]"},
        recent_model_notice="new model notice", now_ms=2000, status=STATUS,
    )


class WatchRenderingTests(unittest.TestCase):
    def test_empty_watch_explains_observation_window(self):
        stream = io.StringIO()
        WatchRenderer({"colors": {}}, stream=stream, interactive=False).render(
            WatchProjection("Watch", "V2", (), now_ms=2000))
        self.assertIn("No prompts since Watch started", stream.getvalue())


    def assert_full_frame(self, frame):
        self.assertTrue(frame.startswith(CLEAR))
        self.assertEqual(1, frame.count(CLEAR), "full redraw still clears scrollback")
        self.assertEqual(1, frame.count(ERASE_TAIL))
        self.assertTrue(frame.endswith("Watch: " + STATUS + ERASE_TAIL),
                        "cleanup follows the final status cursor without a newline")

    def test_removed_session_shortens_frame_and_erases_below_final_status(self):
        tall = tall_projection()
        stream = FlushedBuffer()
        renderer = WatchRenderer({"colors": {}}, stream=stream, interactive=True)
        renderer.render(tall)
        first = stream.getvalue()
        renderer.render(replace(tall, rows=tall.rows[:1]))
        second = stream.getvalue()[len(first):]
        self.assertIn("Session B", first)
        self.assertNotIn("Session B", second)
        self.assertLess(second.count("\n"), first.count("\n"))
        self.assert_full_frame(first)
        self.assert_full_frame(second)
        self.assertEqual([first, first + second], stream.flushed,
                         "tail cleanup must be sent before each full-frame flush")

    def test_other_height_reductions_also_erase_tail(self):
        tall = tall_projection()
        shorter = {
            "quota": replace(tall, quota=None, quota_stale=False),
            "warnings": replace(tall, source_warnings=(), session_warnings={}, recent_model_notice=""),
            "tools": replace(tall, rows=tuple(replace(row, tool=None) for row in tall.rows)),
            "empty": WatchProjection("Watch", "V2", (), status=STATUS),
        }
        for reason, projection in shorter.items():
            with self.subTest(reason=reason):
                stream = io.StringIO()
                renderer = WatchRenderer({"colors": {}}, stream=stream, interactive=True)
                renderer.render(tall)
                first = stream.getvalue()
                renderer.render(projection)
                second = stream.getvalue()[len(first):]
                self.assertLess(second.count("\n"), first.count("\n"))
                self.assert_full_frame(second)

    def test_status_updates_only_replace_status_line_after_shorter_redraw(self):
        stream = io.StringIO()
        renderer = WatchRenderer({"colors": {}}, stream=stream, interactive=True)
        tall = tall_projection()
        renderer.render(tall)
        renderer.render(replace(tall, rows=tall.rows[:1]))
        before = stream.getvalue()
        for countdown in (29, 28):
            renderer.render_status(replace(tall, status=f"Idle · Next prompt check: 00:{countdown}"))
        self.assertEqual(
            "\r\x1b[2KWatch: Idle · Next prompt check: 00:29"
            "\r\x1b[2KWatch: Idle · Next prompt check: 00:28",
            stream.getvalue()[len(before):],
        )
        self.assertEqual(2, stream.getvalue().count(CLEAR))
        self.assertEqual(2, stream.getvalue().count(ERASE_TAIL))

    def test_initializing_full_frame_also_erases_after_status(self):
        stream = FlushedBuffer()
        renderer = WatchRenderer({"colors": {}}, stream=stream, interactive=True)
        renderer.render_initializing("V2")
        text = stream.getvalue()
        self.assertTrue(text.startswith(CLEAR))
        self.assertTrue(text.endswith("Watch: Initializing..." + ERASE_TAIL))
        self.assertEqual([text], stream.flushed)
        renderer.render_startup_status("Watch: [####----] 50% / Analyzing")
        self.assertEqual("\r\x1b[2KWatch: [####----] 50% / Analyzing", stream.getvalue()[len(text):])

    def test_active_status_resets_style_before_erasing_and_flushes_once(self):
        stream = FlushedBuffer()
        renderer = WatchRenderer({"colors": {"activeRunning": {"foreground": "Green"}}},
                                 stream=stream, interactive=True)
        projection = replace(tall_projection(), status="Refreshing...", status_active=True)
        renderer.render(projection)
        frame = stream.getvalue()
        self.assertTrue(frame.endswith("\x1b[92mWatch: Refreshing...\x1b[0m" + ERASE_TAIL))
        self.assertEqual([frame], stream.flushed)
        renderer.render_status(projection)
        update = "\r\x1b[2K\x1b[92mWatch: Refreshing...\x1b[0m"
        self.assertEqual(update, stream.getvalue()[len(frame):])
        self.assertEqual([frame, frame + update], stream.flushed)

    def test_redirected_frames_remain_plain_newline_terminated_output(self):
        stream = FlushedBuffer()
        renderer = WatchRenderer({"colors": {}}, stream=stream, interactive=False)
        tall = tall_projection()
        renderer.render(tall)
        first = stream.getvalue()
        renderer.render(replace(tall, rows=tall.rows[:1]))
        second = stream.getvalue()[len(first):]
        self.assertLess(second.count("\n"), first.count("\n"))
        for frame in (first, second):
            self.assertNotIn("\x1b", frame)
            self.assertTrue(frame.endswith("Watch: " + STATUS + "\n"))
        renderer.render_status(tall)
        renderer.render_initializing("V2")
        self.assertEqual(first + second, stream.getvalue())
        self.assertEqual([first, first + second], stream.flushed)

    def test_empty_table_has_placeholder_row_and_unobserved_mix_is_explicit(self):
        rule = "|" + "|".join("-" * 10 for _ in range(2))  # prefix only
        for render, placeholder in (
            (lambda r: r.render(WatchProjection("Watch", "V2", (), status=STATUS)), "No prompts yet"),
        ):
            stream = io.StringIO()
            render(WatchRenderer({"colors": {}}, stream=stream, interactive=True))
            lines = stream.getvalue().replace(CLEAR, "").splitlines()
            table = [line for line in lines if line.startswith("|")]
            self.assertEqual(5, len(table), "rule, header, rule, placeholder, rule")
            self.assertIn(placeholder, table[3])
            self.assertTrue(table[2].startswith(rule[:5]) and table[4].startswith(rule[:5]))
            mix = next(line for line in lines if line.startswith("Token Mix %"))
            self.assertTrue(mix.endswith("no token data yet"))
            self.assertNotIn("--", mix)
        frame = io.StringIO()
        WatchRenderer({"colors": {}}, stream=frame, interactive=False).render(tall_projection())
        self.assertNotIn("No prompts yet", frame.getvalue())


if __name__ == "__main__":
    unittest.main()
