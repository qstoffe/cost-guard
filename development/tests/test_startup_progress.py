"""Deterministic startup work/time principles and terminal ownership handoff."""
import io
import threading
import unittest

from src.domain.progress import WorkProgress
from src.presentation.progress import StartupProgress
from src.presentation.startup_estimate import StartupEstimate


class StartupEstimateTests(unittest.TestCase):
    def test_all_modes_are_monotonic_and_never_complete_from_elapsed_time(self):
        for mode in ("Report", "All Models", "Sessions", "Session", "Date", "Date Range",
                     "Token Mix", "Watch", "Watch Session"):
            with self.subTest(mode=mode):
                estimate = StartupEstimate(mode, 0)
                values = []
                now = 0
                for phase in estimate.budgets:
                    estimate.update(WorkProgress(phase, phase), now)
                    for duration in (.01, .5, 2, 100):
                        values.append(estimate.percent(now + duration))
                    now += 101
                self.assertEqual(sorted(values), values)
                self.assertLess(max(values), 100)

    def test_long_phase_evolves_with_time_and_known_work_advances_it(self):
        estimate = StartupEstimate("Token Mix", 0)
        estimate.update(WorkProgress("History", "history", 0, 4), 0)
        values = [estimate.percent(now) for now in (0, .5, 2, 8)]
        self.assertGreater(values[-1], values[0])
        estimate.update(WorkProgress("History", "history", 2, 4), 8)
        self.assertGreater(estimate.percent(8), values[-1])
        self.assertLess(estimate.percent(800), 95)

    def test_mode_budgets_reflect_different_history_work_not_call_counts(self):
        report = StartupEstimate("Report", 0)
        history = StartupEstimate("Token Mix", 0)
        for estimate in (report, history):
            estimate.update(WorkProgress("History", "history"), 0)
        self.assertGreater(report.percent(1), history.percent(1))
        before = report.percent(1)
        for _ in range(100):
            report.update(WorkProgress("History", "history"), 1)
        self.assertEqual(before, report.percent(1), "calls alone cannot invent completed work")

    def test_lazy_earlier_dependency_does_not_reset_current_phase(self):
        estimate = StartupEstimate("Sessions", 0)
        estimate.update(WorkProgress("History", "history", 1, 5), 0)
        before = estimate.percent(1)
        estimate.update(WorkProgress("Pricing", "pricing"), 2)
        self.assertEqual("history", estimate.phase)
        self.assertGreaterEqual(estimate.percent(2), before)


class StartupProgressTests(unittest.TestCase):
    def test_unknown_work_is_indeterminate_and_failure_does_not_show_success(self):
        output = io.StringIO()
        progress = StartupProgress(output, interactive=True, animate=False)
        progress.update("Unmeasured recovery")
        progress.stop()
        self.assertIn("Unmeasured recovery", output.getvalue())
        self.assertNotIn("%", output.getvalue())
        self.assertNotIn("100", output.getvalue())

    def test_explicit_percent_cannot_claim_completion_until_success(self):
        lines = []
        progress = StartupProgress(io.StringIO(), interactive=True, animate=False, line_sink=lines.append)
        progress.update("Work", 100)
        progress.update("Work", 10)
        self.assertTrue(all("99%" in line for line in lines))
        progress.stop(complete=True)
        self.assertIn("100%", lines[-1])
        progress.update("Closed", 50)
        self.assertIn("100%", lines[-1])

    def test_redirected_output_keeps_stages_without_animation_or_percent_noise(self):
        output = io.StringIO()
        progress = StartupProgress(output, interactive=False)
        for completed in range(10):
            progress.update(WorkProgress("History", "history", completed, 10))
        progress.stop(complete=True)
        self.assertEqual("Cost Guard: History\n", output.getvalue())
        self.assertIsNone(progress._worker)

    def test_stop_joins_animation_before_dashboard_or_recovery_can_write(self):
        animated = threading.Event()
        lines = []

        def sink(line):
            lines.append(line)
            if len(lines) >= 2:
                animated.set()

        progress = StartupProgress(io.StringIO(), interactive=True, line_sink=sink)
        progress.update(WorkProgress("History", "history"))
        self.assertTrue(animated.wait(2), "finite wait for one animation tick")
        progress.stop(complete=True)
        self.assertFalse(progress._worker.is_alive())
        count = len(lines)
        progress.update("Too late")
        self.assertEqual(count, len(lines))

    def test_fast_start_does_not_wait_for_animation_or_a_target_time(self):
        progress = StartupProgress(io.StringIO(), interactive=True, animate=False, clock=lambda: 0)
        progress.update(WorkProgress("Source", "source"))
        progress.stop(complete=True)
        self.assertTrue(progress._closed)
        self.assertEqual(100, progress._percent)


if __name__ == "__main__":
    unittest.main()
