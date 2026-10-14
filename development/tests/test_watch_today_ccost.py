"""Deletion-resilient local-day CCost retention and Watch line presentation."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import io
import tempfile
import unittest
from unittest.mock import patch

from development.fixtures.session_snapshots import make_snapshot
from development.fixtures.watch_runtime import MutableSource, make_service
from src.analysis.models import TraceEntry
from src.analysis.timezones import local_day_start_ms
from src.analysis.valuation import ComparisonCost
from src.domain import ModelRef, TokenUsage
from src.presentation import WatchRenderer
from src.presentation.token_mix import comparison_cost_text, watch_total_line
from src.watch import WatchCoordinator
from src.watch.models import WatchProjection
from src.watch.today_ccost import WatchTodayCCost
from src.analysis.token_mix import TokenMix

MODEL = ModelRef("github-copilot", "priced")
UNPRICED = ModelRef("github-copilot", "unpriced")


def reference_value(model, usage):
    return None if model == UNPRICED else Decimal(usage.input + usage.output)


def entry(
    amount: int,
    completed_at_ms: int,
    *,
    message_id: str | None = "message",
    session_id: str = "session",
    step_part_id: str | None = None,
    sort_order: int = 0,
    model: ModelRef = MODEL,
    known_fields: tuple[str, ...] = ("input", "cache_read", "cache_write", "output"),
) -> TraceEntry:
    return TraceEntry(
        session_id, "event", message_id, step_part_id, completed_at_ms, sort_order,
        model, None, TokenUsage(input=amount, known_fields=known_fields), source_instance="source",
    )


def epoch_ms(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> int:
    return int(datetime(year, month, day, hour, minute, tzinfo=timezone.utc).timestamp() * 1000)


def single_invocation(invocation_id: str):
    snapshot = make_snapshot(running=False)
    invocation = next(item for item in snapshot.invocations if item.invocation_id == invocation_id)
    messages = tuple(item for item in snapshot.messages
                     if item.message_id in {invocation.initiating_event_id, invocation.message_id})
    events = tuple(item for item in snapshot.events if item.event_id == invocation.initiating_event_id)
    return replace(snapshot, sessions=(snapshot.root,), messages=messages,
                   parts=tuple(part for item in messages for part in item.parts),
                   events=events, invocations=(invocation,), source_revision="initial")


class WatchTodayCCostTests(unittest.TestCase):
    def project(self, tracker, now_ms):
        return tracker.project(now_ms=now_ms, valuation=reference_value)

    def test_historical_daily_usage_survives_deleted_source_rows(self):
        tracker = WatchTodayCCost("UTC")
        historical = entry(20, 100)
        tracker.observe((historical,), now_ms=200, historical=True)
        first = self.project(tracker, 200)
        tracker.observe((), now_ms=300, historical=True)
        self.assertEqual(first, self.project(tracker, 300))
        self.assertEqual((Decimal(20), 1), (first.known_ccost, first.observed_requests))

    def test_new_observations_deduplicate_and_reconcile_telemetry(self):
        tracker = WatchTodayCCost("UTC")
        partial = entry(10, 100, message_id=None, known_fields=("input",))
        complete = entry(15, 120, message_id=None)
        tracker.observe((partial,), now_ms=200, historical=True)
        tracker.observe((complete,), now_ms=200)
        tracker.observe((complete,), now_ms=200)
        total = self.project(tracker, 200)
        self.assertEqual((Decimal(15), 1), (total.known_ccost, total.observed_requests))

    def test_fork_clones_and_message_to_step_replacement_follow_usage_identity(self):
        tracker = WatchTodayCCost("UTC")
        original = entry(10, 100, message_id="clone")
        fork = replace(original, session_id="fork")
        fallback = entry(50, 150, message_id="stepped")
        tracker.observe((original, fork, fallback), now_ms=200, historical=True)
        steps = (entry(10, 160, message_id="stepped", step_part_id="one"),
                 entry(20, 170, message_id="stepped", step_part_id="two", sort_order=1))
        tracker.observe(steps, now_ms=200)
        tracker.observe((fallback,), now_ms=200)
        total = self.project(tracker, 200)
        self.assertEqual((Decimal(40), 3), (total.known_ccost, total.observed_requests))

    def test_unobserved_deleted_history_is_not_reconstructed(self):
        tracker = WatchTodayCCost("UTC")
        tracker.observe((), now_ms=100, historical=True)
        self.assertEqual((Decimal(0), 0), (self.project(tracker, 100).known_ccost,
                                          self.project(tracker, 100).observed_requests))

    def test_midnight_replaces_today_scope_and_cross_day_observations(self):
        tracker = WatchTodayCCost("UTC")
        day_one = epoch_ms(2026, 10, 14, 23, 30)
        day_two = epoch_ms(2026, 10, 15, 0, 30)
        tracker.observe((entry(20, day_one),), now_ms=day_one + 1, historical=True)
        self.assertEqual(Decimal(20), self.project(tracker, day_one + 1).known_ccost)
        tracker.observe((entry(5, day_two, message_id="next-day"),),
                        now_ms=day_two + 1, historical=True)
        total = self.project(tracker, day_two + 1)
        self.assertEqual((Decimal(5), 1), (total.known_ccost, total.observed_requests))

    def test_stockholm_midnight_and_dst_day_lengths(self):
        tracker = WatchTodayCCost("Europe/Stockholm")
        now_ms = epoch_ms(2026, 3, 29, 12)
        before_midnight = entry(50, epoch_ms(2026, 3, 28, 22, 59), message_id="before")
        after_midnight = entry(20, epoch_ms(2026, 3, 28, 23), message_id="after")
        tracker.observe((before_midnight, after_midnight), now_ms=now_ms, historical=True)
        self.assertEqual(Decimal(20), self.project(tracker, now_ms).known_ccost)
        spring_start = local_day_start_ms("Europe/Stockholm", now_ms=now_ms)
        spring_next = epoch_ms(2026, 3, 30, 12)
        self.assertEqual(23 * 60 * 60 * 1000,
                         local_day_start_ms("Europe/Stockholm", now_ms=spring_next) - spring_start)
        fall_start = local_day_start_ms("Europe/Stockholm", now_ms=epoch_ms(2026, 10, 25, 12))
        fall_next = local_day_start_ms("Europe/Stockholm", now_ms=epoch_ms(2026, 10, 26, 12))
        self.assertEqual(25 * 60 * 60 * 1000, fall_next - fall_start)

    def test_unpriced_partial_and_zero_values_keep_existing_display_conventions(self):
        self.assertEqual("0", comparison_cost_text(ComparisonCost()))
        self.assertEqual("N/A", comparison_cost_text(ComparisonCost(Decimal(0), 1, 0)))
        self.assertEqual("?2", comparison_cost_text(ComparisonCost(Decimal("1.1"), 2, 1)))
        line = watch_total_line(TokenMix(), ComparisonCost(Decimal(2458), 1, 1))
        self.assertEqual(
            "Watch total CCost: 0 (Today: 2458; Deleted sessions before Watch start excluded)", line
        )

    def test_unchanged_status_projection_does_not_recalculate_retained_history(self):
        tracker = WatchTodayCCost("UTC")
        tracker.observe((entry(10, 100),), now_ms=200, historical=True)
        expected = self.project(tracker, 200)
        with patch("src.watch.today_ccost.comparison_cost", side_effect=AssertionError("unexpected daily rescan")):
            self.assertEqual(expected, self.project(tracker, 200))

    def test_coordinator_retains_prestart_history_after_session_deletion_without_accounts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = MutableSource(single_invocation("i_syn"))
            config, selection, service, _ = make_service(temp_dir, source)
            service.account_provider = None
            service.account_providers = ()
            watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                     clock_ms=lambda: 4000, record_observations=False)
            before_delete = watch.initialize().projection
            self.assertEqual(4000, before_delete.watch_started_at_ms)
            self.assertEqual(1, before_delete.today_total.observed_requests)
            self.assertEqual(before_delete.quota.comparison_today, before_delete.today_total)
            self.assertEqual(0, before_delete.run_total.request_count)
            self.assertEqual((), before_delete.quota.accounts)
            with patch("src.watch.today_ccost.comparison_cost", side_effect=AssertionError("status rescan")):
                self.assertEqual(before_delete.today_total, watch.status_projection().today_total)
            source.snapshot = replace(source.snapshot, sessions=(), source_revision="deleted")
            after_delete = watch.poll_once().projection
            self.assertEqual(before_delete.today_total, after_delete.today_total)
            self.assertEqual(0, after_delete.quota.comparison_today.observed_requests)
            output = io.StringIO()
            WatchRenderer(config, stream=output, interactive=False).render(after_delete)
            line = next(value for value in output.getvalue().splitlines()
                        if value.startswith("Watch total CCost:"))
            self.assertIn("(Today: ", line)
            self.assertIn("; Deleted sessions before Watch start excluded)", line)
            lines = output.getvalue().splitlines()
            mix_index = next(index for index, value in enumerate(lines) if value.startswith("Token Mix %"))
            self.assertEqual(line, lines[mix_index + 1])
            self.assertEqual(1, sum(value.startswith("Watch total CCost:") for value in lines))

    def test_newly_observed_request_survives_deletion_and_keeps_run_total(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = MutableSource(single_invocation("i_next"))
            config, selection, service, _ = make_service(temp_dir, source, now_ms=2200)
            service.account_provider = None
            service.account_providers = ()
            clock = [2200]
            watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                     clock_ms=lambda: clock[0], record_observations=False)
            initial = watch.initialize().projection
            self.assertEqual(1, initial.run_total.request_count)
            self.assertEqual(0, initial.today_total.observed_requests)
            clock[0] = 2400
            source.snapshot = replace(source.snapshot, source_revision="completed")
            observed = watch.poll_once(force_resync=True).projection
            self.assertEqual(1, observed.today_total.observed_requests)
            self.assertEqual(initial.run_total, observed.run_total)
            source.snapshot = replace(source.snapshot, sessions=(), source_revision="deleted")
            clock[0] = 2500
            deleted = watch.poll_once().projection
            self.assertEqual(observed.today_total, deleted.today_total)
            self.assertEqual(observed.run_total, deleted.run_total)
            clock[0] = epoch_ms(1970, 1, 2, 0, 1)
            next_day = watch.status_projection()
            self.assertEqual(0, next_day.today_total.observed_requests)
            self.assertEqual(observed.run_total, next_day.run_total)


if __name__ == "__main__":
    unittest.main()
