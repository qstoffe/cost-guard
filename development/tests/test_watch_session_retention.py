"""Watch session idle expiry, recent-session protection and consolidated context warnings."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import io
import tempfile
import unittest

from development.fixtures.session_snapshots import make_snapshot
from development.fixtures.watch_runtime import MutableSource, make_service
from src.analysis.context import PriceWarningSeverity
from src.domain import EventKind, NormalizedEvent
from src.presentation import WatchRenderer
from src.reports.models import PromptProjection, SessionPromptBlock
from src.watch import WatchCoordinator
from src.watch.models import WatchProjection
from src.domain.session_tree import root_activity
from src.watch.session_retention import SESSION_IDLE_EXPIRY_MS, startup_visible_roots
from src.watch.tracker import WatchRowTracker

MINUTE = 60_000
NOW = 1_000 * MINUTE
EXCEEDED = "[Price threshold >200.0K exceeded]"
APPROACHING = "[Approaching price threshold >272.0K]"


def prompt(number, at_ms, *, duration_ms=1_000, **changes):
    return PromptProjection(
        at_ms=at_ms, prompt_number=number, event_id=f"event-{number}",
        label=f"#{number}", preview=f"prompt {number}", model_effort="model",
        ccost=Decimal(1), cost_estimated=False, unresolved_cost=False, calls=1,
        incoming_context_tokens=None, incoming_context_ccost=None,
        extra_ccost=None, token_mix_percent=None, duration_ms=duration_ms, **changes,
    )


def finished_at(number, end_ms, **changes):
    """A completed prompt whose source end time is ``end_ms``."""
    return prompt(number, end_ms - 1_000, **changes)


def inputs(**sessions):
    base = make_snapshot()
    blocks, snapshots = {}, {}
    for session_id, rows in sessions.items():
        root = replace(base.root, session_id=session_id, title=f"Session {session_id}")
        events = tuple(NormalizedEvent(row.event_id, session_id, EventKind.USER_PROMPT, row.at_ms,
                                       base.events[0].provenance) for row in rows)
        blocks[session_id] = SessionPromptBlock(session_id, root.title, tuple(rows), Decimal(0), 0)
        snapshots[session_id] = replace(base, root=root, sessions=(root,), events=events,
                                        messages=(), parts=(), invocations=())
    return blocks, snapshots


def tracker(*, started_at_ms=0, max_rows=20):
    return WatchRowTracker(started_at_ms=started_at_ms, recent_seconds=0, max_rows=max_rows)


def sessions(rows):
    return sorted({row.session_id for row in rows})


def warned(number, at_ms, warning=EXCEEDED, severity=PriceWarningSeverity.EXCEEDED, multiplier="1.9", **changes):
    return finished_at(number, at_ms, watch_next_context_warning=warning,
                       watch_next_context_warning_severity=severity, watch_next_context_tokens=210_000,
                       watch_next_context_cost_multiplier=None if multiplier is None else Decimal(multiplier),
                       **changes)


class SessionExpiryTests(unittest.TestCase):
    def test_idle_session_expires_exactly_at_ten_minutes(self):
        blocks, snapshots = inputs(A=(finished_at(1, NOW - MINUTE),), B=(finished_at(1, NOW - 2 * MINUTE),),
                                   C=(finished_at(1, NOW - 5 * MINUTE),))
        observed = tracker()
        self.assertEqual(["A", "B", "C"], sessions(observed.project(blocks, snapshots, now_ms=NOW)))
        boundary = NOW - 5 * MINUTE + SESSION_IDLE_EXPIRY_MS
        self.assertEqual(["A", "B", "C"], sessions(observed.project(blocks, snapshots, now_ms=boundary - 1)))
        self.assertEqual(["A", "B"], sessions(observed.project(blocks, snapshots, now_ms=boundary)))

    def test_two_most_recent_sessions_stay_visible_regardless_of_age(self):
        blocks, snapshots = inputs(A=(finished_at(1, NOW - 2 * MINUTE),), B=(finished_at(1, NOW - 7 * MINUTE),),
                                   C=(finished_at(1, NOW - 15 * MINUTE),), D=(finished_at(1, NOW - 30 * MINUTE),))
        self.assertEqual(["A", "B"], sessions(tracker().project(blocks, snapshots, now_ms=NOW)))
        old, _ = inputs(A=(finished_at(1, NOW),), B=(finished_at(1, NOW - MINUTE),))
        for days in (0, 1, 30):
            rows = tracker().project(old, snapshots, now_ms=NOW + days * 24 * 60 * MINUTE)
            self.assertEqual(["A", "B"], sessions(rows))

    def test_running_sessions_are_protected_beyond_the_two_recent_slots(self):
        hour_ago = NOW - 60 * MINUTE
        blocks, snapshots = inputs(**{name: (prompt(1, hour_ago, duration_ms=None, in_progress=True),)
                                      for name in "ABCD"}, E=(finished_at(1, NOW - MINUTE),))
        observed = tracker()
        self.assertEqual(list("ABCDE"), sessions(observed.project(blocks, snapshots, now_ms=NOW)))
        # The long-running prompt finishes; its countdown starts at its source end time.
        end = NOW + MINUTE
        blocks["A"] = replace(blocks["A"], rows=(prompt(1, hour_ago, duration_ms=end - hour_ago),))
        self.assertIn("A", sessions(observed.project(blocks, snapshots, now_ms=end + SESSION_IDLE_EXPIRY_MS - 1)))

    def test_displaced_session_expires_immediately_and_returns_on_new_activity(self):
        blocks, snapshots = inputs(A=(finished_at(1, NOW - 40 * MINUTE),), B=(finished_at(1, NOW - 50 * MINUTE),))
        observed = tracker(started_at_ms=NOW)
        self.assertEqual(["A", "B"], sessions(observed.project(blocks, snapshots, now_ms=NOW)))
        more, more_snapshots = inputs(C=(prompt(1, NOW, duration_ms=None, in_progress=True),))
        blocks.update(more)
        snapshots.update(more_snapshots)
        self.assertEqual(["A", "C"], sessions(observed.project(blocks, snapshots, now_ms=NOW + 1)),
                         "B loses protection with 50 idle minutes and gets no new grace period")
        for _ in range(3):  # ordinary polling/resynchronization never resurrects it
            self.assertNotIn("B", sessions(observed.project(blocks, snapshots, now_ms=NOW + 2)))
        blocks["B"] = replace(blocks["B"], rows=blocks["B"].rows + (prompt(2, NOW + 3, duration_ms=None, in_progress=True),))
        rows = observed.project(blocks, snapshots, now_ms=NOW + 4)
        self.assertEqual(["B", "C"], sessions(rows), "two running sessions now hold both recent slots")
        self.assertEqual([2], [row.prompt.prompt_number for row in rows if row.session_id == "B"])

    def test_restart_keeps_remaining_idle_time_without_a_fresh_period(self):
        blocks, snapshots = inputs(A=(finished_at(1, NOW - MINUTE),), B=(finished_at(1, NOW - 2 * MINUTE),),
                                   C=(finished_at(1, NOW - 8 * MINUTE),), D=(finished_at(1, NOW - 30 * MINUTE),))
        restarted = tracker(started_at_ms=NOW)
        rows = restarted.project(blocks, snapshots, now_ms=NOW)
        self.assertEqual(["A", "B", "C"], sessions(rows), "startup shows still-unexpired history only")
        self.assertEqual(["", "", ""], [row.marker for row in rows])
        self.assertEqual(["A", "B"], sessions(restarted.project(blocks, snapshots, now_ms=NOW + 2 * MINUTE)))

    def test_observed_completion_is_the_fallback_without_source_duration(self):
        blocks, snapshots = inputs(A=(finished_at(1, NOW + 5 * MINUTE),), B=(finished_at(1, NOW + 5 * MINUTE),),
                                   C=(prompt(1, NOW - 60 * MINUTE, duration_ms=None, in_progress=True),))
        observed = tracker()
        observed.project(blocks, snapshots, now_ms=NOW)
        blocks["C"] = replace(blocks["C"], rows=(prompt(1, NOW - 60 * MINUTE, duration_ms=None),))
        observed.project(blocks, snapshots, now_ms=NOW + MINUTE)
        self.assertIn("C", sessions(observed.project(blocks, snapshots, now_ms=NOW + MINUTE + SESSION_IDLE_EXPIRY_MS - 1)))
        self.assertNotIn("C", sessions(observed.project(blocks, snapshots, now_ms=NOW + MINUTE + SESSION_IDLE_EXPIRY_MS)))

    def test_row_cap_keeps_one_latest_row_per_protected_session(self):
        blocks, snapshots = inputs(
            A=tuple(finished_at(number, NOW - 60 * MINUTE + number) for number in range(1, 5)),
            B=tuple(finished_at(number, NOW - 70 * MINUTE + number) for number in range(1, 5)),
            C=(prompt(1, NOW - 90 * MINUTE, duration_ms=None, in_progress=True),),
        )
        rows = tracker(max_rows=1).project(blocks, snapshots, now_ms=NOW)
        self.assertEqual([("C", 1), ("A", 4)], [(row.session_id, row.prompt.prompt_number) for row in rows],
                         "running C takes a recent slot; A keeps its latest row; idle B expires")
        rows = tracker(max_rows=3).project(blocks, snapshots, now_ms=NOW)
        self.assertEqual([("C", 1), ("A", 3), ("A", 4)], [(row.session_id, row.prompt.prompt_number) for row in rows])

    def test_startup_hydrates_metadata_recent_and_unexpired_roots(self):
        base = make_snapshot().root
        roots = tuple(replace(base, session_id=name, updated_at_ms=NOW - minutes * MINUTE)
                      for name, minutes in (("A", 20), ("B", 30), ("C", 5), ("D", 40)))
        ordered = tuple(sorted(roots, key=lambda item: item.updated_at_ms, reverse=True))
        activity = root_activity(roots, {root.session_id: root.session_id for root in roots})
        self.assertEqual({"C", "A"}, startup_visible_roots(ordered, activity, NOW))
        self.assertEqual({"C", "A", "B"}, startup_visible_roots(ordered, activity, NOW - 21 * MINUTE + 1))


def rendered(projection, *, width=200):
    stream = io.StringIO()
    WatchRenderer({"colors": {}}, stream=stream, interactive=False, terminal_width=width).render(projection)
    return stream.getvalue()


class WarningConsolidationTests(unittest.TestCase):
    def coordinator_projection(self, blocks, snapshots, now_ms):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        config, selection, service, _ = make_service(temp.name, MutableSource())
        watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 0)
        self.addCleanup(watch.close)
        watch.blocks, watch.snapshots = blocks, snapshots
        return watch, watch._projection(now_ms=now_ms)

    def test_identical_warnings_share_one_explanation_with_ordered_markers(self):
        blocks, snapshots = inputs(**{name: (warned(1, NOW - index),) for index, name in enumerate("ABCD")})
        _watch, projection = self.coordinator_projection(blocks, snapshots, NOW)
        output = rendered(projection)
        self.assertIn("*1,2,3,4 Context: Price threshold >200.0K exceeded (1.9x more expensive)", output)
        self.assertEqual(1, output.count("Context:"))
        for number in range(1, 5):
            self.assertIn(f"*{number} Session ", output)

    def test_different_threshold_severity_or_cost_detail_stays_separate(self):
        blocks, snapshots = inputs(
            A=(warned(1, NOW),), B=(warned(1, NOW - 1),),
            C=(warned(1, NOW - 2, APPROACHING, PriceWarningSeverity.APPROACHING),),
            D=(warned(1, NOW - 3, multiplier="2.2"),),
            E=(warned(1, NOW - 4, multiplier=None, watch_next_context_cached_ccost=Decimal("0.3"),
                      watch_next_context_fresh_ccost=Decimal(3)),),
        )
        _watch, projection = self.coordinator_projection(blocks, snapshots, NOW)
        lines = [line for line in rendered(projection).splitlines() if "Context:" in line]
        self.assertEqual(4, len(lines))
        self.assertEqual(1, sum(">200.0K exceeded (1.9x more expensive)" in line for line in lines))
        self.assertTrue(any(line.startswith("*4,5 ") for line in lines), "only identical A and B are grouped")
        self.assertTrue(any("(2.2x more expensive)" in line for line in lines))
        self.assertTrue(any("Approaching price threshold >272.0K" in line for line in lines))
        self.assertTrue(any("(Next Ictx CCost 0.3–3)" in line for line in lines))
        markers = [line.split(" ", 1)[0] for line in lines]
        self.assertEqual(sorted(markers, key=lambda marker: int(marker[1:].split(",")[0])), markers)

    def test_expired_session_marker_leaves_the_group_and_last_group_disappears(self):
        blocks, snapshots = inputs(A=(finished_at(1, NOW),), B=(finished_at(1, NOW - 1),),
                                   C=(warned(1, NOW - 2 * MINUTE),), D=(warned(1, NOW - 3 * MINUTE),))
        watch, before = self.coordinator_projection(blocks, snapshots, NOW)
        self.assertIn("*1,2 Context:", rendered(before))
        after = watch._projection(now_ms=NOW - 3 * MINUTE + SESSION_IDLE_EXPIRY_MS)
        self.assertNotEqual(watch._transient_signature(before), watch._transient_signature(after),
                            "time-based expiry repaints without a source change")
        self.assertIn("*1 Context: Price threshold", rendered(after))
        self.assertEqual(["A", "B", "C"], sessions(after.rows))
        gone = watch._projection(now_ms=NOW - 2 * MINUTE + SESSION_IDLE_EXPIRY_MS)
        self.assertNotIn("Context:", rendered(gone))
        self.assertEqual({}, dict(gone.session_warnings))

    def test_protected_session_keeps_warning_and_orange_next_ictx(self):
        blocks, snapshots = inputs(A=(warned(1, NOW - 600 * MINUTE),),
                                   B=(warned(1, NOW - 700 * MINUTE, APPROACHING, PriceWarningSeverity.APPROACHING),))
        _watch, projection = self.coordinator_projection(blocks, snapshots, NOW)
        stream = io.StringIO()
        renderer = WatchRenderer({"colors": {}}, stream=stream, interactive=True, terminal_width=200)
        renderer.render(projection)
        output = stream.getvalue()
        self.assertEqual(2, output.count("Context:"))
        warning = renderer.styler.apply("x", "nextIctxWarning")
        start = warning[:warning.index("x")]
        self.assertIn(start + "*2 Context: Price threshold", output, "exceeded colors the whole line")
        self.assertIn(start + "*1" + warning[warning.index("x") + 1:] + " Context: Approaching", output)
        self.assertEqual(2, output.count(start + "   ~210k"), "Next Ictx stays highlighted for both sessions")

    def test_long_grouped_explanation_wraps_without_dropping_information(self):
        blocks, snapshots = inputs(**{name: (warned(1, NOW - index),) for index, name in enumerate("ABCDEFGHIJKL")})
        _watch, projection = self.coordinator_projection(blocks, snapshots, NOW)
        lines = [line for line in rendered(projection, width=50).splitlines()]
        start = next(index for index, line in enumerate(lines) if line.startswith("*1,2,3,4,5,6,7,8,9,10,11,12 "))
        end = next(index for index in range(start + 1, len(lines)) if not lines[index].startswith(" "))
        self.assertGreater(end - start, 1, "the explanation wraps")
        text = " ".join(line.strip() for line in lines[start:end])
        self.assertIn("Context: Price threshold >200.0K exceeded (1.9x more expensive)", text)
        self.assertTrue(all(len(line) <= 50 for line in lines[start + 1:end]))


if __name__ == "__main__":
    unittest.main()
