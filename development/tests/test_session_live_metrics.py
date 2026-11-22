"""P0 running metrics are a scoped overlay, never a historical correction."""
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from development.tests.fixtures.display_watch import running_frame
from src.application.session_live_metrics import with_live_metrics
from src.cache.display_history import DisplayHistory, RunningSession, SessionChange, SessionFact


class SessionLiveMetricsTests(unittest.TestCase):
    def test_requires_same_prompt_and_capture_and_independent_cost_qualification(self):
        at = 100_000
        frame = running_frame(at)
        card, = frame.active_cards
        card = replace(card, session_context=SimpleNamespace(tokens=773, context_state="ready-current"),
                       session_cost_state="observed")
        frame = replace(frame, active_cards=(card,))
        current = RunningSession("root", "Observed title", 98_000, at, "prompt-1")
        wrong_prompt = replace(current, prompt_id="other")
        wrong_start = replace(current, started_ms=97_000)
        old_capture = replace(current, observed_ms=99_999)

        qualified, = with_live_metrics((current,), frame)
        pending, = with_live_metrics((current,), replace(frame, active_cards=(replace(card, session_cost_state="checking"),)))
        unverified, = with_live_metrics((current,), replace(frame, active_cards=(replace(card, invocation_verified=False),)))
        mismatched = tuple(with_live_metrics((row,), frame)[0] for row in (wrong_prompt, wrong_start, old_capture))

        self.assertEqual((Decimal("1.25000001"), 773), (qualified.ccost, qualified.context_tokens))
        self.assertEqual((None, 773), (pending.ccost, pending.context_tokens))
        self.assertEqual(current, unverified)
        self.assertEqual((wrong_prompt, wrong_start, old_capture), mismatched)

    def test_running_metrics_update_generation_and_never_replace_saved_values(self):
        with TemporaryDirectory() as directory:
            history = DisplayHistory(Path(directory))
            history.initialize()
            at = 100_000
            saved = SessionFact("root", "r1", "Older title", ccost=Decimal("0.1"),
                                context_tokens=600, context_detail="Earlier source observation")
            history.commit_sessions("source", (SessionChange(saved, None),))
            running = RunningSession("root", "Observed title", at - 2_000, at, "prompt-1",
                                     Decimal("1.25000001"), 773)
            generation = history.replace_running("source", "host", (running,), archive_epoch=0)
            current, = history.session_page("source", live_binding="host", now_ms=at).rows

            rewritten = replace(running, context_tokens=None, context_invalidated=True)
            next_generation = history.replace_running("source", "host", (rewritten,), archive_epoch=0)
            pending, = history.session_page("source", live_binding="host", now_ms=at).rows
            restarted, = history.session_page("source", live_binding="next-host", now_ms=at).rows
            history.replace_running("source", "host", (), archive_epoch=0)
            ended, = history.session_page("source", live_binding="host", now_ms=at).rows

        self.assertEqual(("1.25000001", 773, None, True),
                         (current.ccost, current.context_tokens, current.context_detail, current.running))
        self.assertEqual(generation + 1, next_generation)
        self.assertEqual(("1.25000001", None, None, True),
                         (pending.ccost, pending.context_tokens, pending.context_detail, pending.running))
        self.assertEqual(("0.1", 600, False), (ended.ccost, ended.context_tokens, ended.running))
        self.assertEqual(ended, restarted)

    def test_version_30_running_overlay_upgrades_without_dropping_saved_rows(self):
        with TemporaryDirectory() as directory:
            history = DisplayHistory(Path(directory))
            history.initialize()
            history.commit_sessions("source", (SessionChange(SessionFact("root", "r1", "Saved", context_tokens=600), None),))
            with history._connect() as db:
                db.executescript("""
                    ALTER TABLE session_running DROP COLUMN ccost;
                    ALTER TABLE session_running DROP COLUMN context_tokens;
                    ALTER TABLE session_running DROP COLUMN context_invalidated;
                    INSERT INTO session_running VALUES('source','old-host','root','Live',98000,100000);
                    PRAGMA user_version=30;
                """)
            history.initialize()

            saved, = history.session_page("source", live_binding="new-host", now_ms=100_000).rows
            live, = history.session_page("source", live_binding="old-host", now_ms=100_000).rows

        self.assertEqual(("Saved", False, 600), (saved.title, saved.running, saved.context_tokens))
        self.assertEqual(("Live", True, 600), (live.title, live.running, live.context_tokens))
