"""Web-only hourly reference cost: canonical timing, accounting and finite capture."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service, rendered
from development.tests.fixtures.report_runtime import FakeSource
from development.tests.fixtures.session_snapshots import make_snapshot, make_native_v2_compaction_snapshot
from development.tests.test_report_duration import history
from src.analysis.active_hour import active_hour, period_active_hours, period_windows, ROLLING_MS, HOUR_MS
from src.analysis.core import analyze_snapshot
from src.application import ReportApplication
from src.application.projection import project, hourly
from src.application.display import with_display
from src.application.session_detail import SessionDetails
from src.domain import TokenUsage, BackgroundActivity, TerminalEvidence, TerminalOutcome
from src.reports import ReportKind, ReportRequest
from src.web.jobs import parse_report

ROOT = Path(__file__).resolve().parents[2]
DAY = 24 * HOUR_MS


def epoch(text):
    return int(datetime.fromisoformat(text).timestamp() * 1000)


def bundle(snapshot, now):
    return analyze_snapshot(snapshot, tracked_provider=None, estimator=lambda *_: Decimal(1), now_ms=now)


def clean_service(owner, snapshot=None, *, now=DAY * 40, zone="UTC"):
    service = report_service(owner, FakeSource(snapshot), now_ms=now, timezone_id=zone)
    service.selection = replace(service.selection, warnings=())
    return service


def hourly_result(owner):
    now = epoch("2026-10-30T12:00:00+00:00")
    snapshot = history(((now - HOUR_MS, now - HOUR_MS // 2), (now - HOUR_MS // 4, now)))
    root = replace(snapshot.root, updated_at_ms=now)
    snapshot = replace(snapshot, root=root, sessions=(root,))
    app = ReportApplication(lambda clock, progress: clean_service(owner, snapshot, now=clock), clock=lambda: now)
    return app.execute(ReportRequest(ReportKind.COST_PER_HOUR)).to_json()


class ActiveHourTests(unittest.TestCase):
    def test_decimal_formula_rounds_only_at_display_and_both_units(self):
        value = active_hour("test", 1, 2, Decimal("12.3456789"), 1_234_567)
        expected = Decimal("12.3456789") / (Decimal(1_234_567) / 3_600_000)
        self.assertEqual(expected, value.rate)
        dto = with_display(hourly(value)).to_json()
        self.assertEqual(str(expected), dto["rate"])
        self.assertEqual("37 CCost/h", dto["display"]["rate"])
        self.assertEqual("$0.36/h", dto["display_units"]["usd"]["rate"])
        for duration in (None, 0):
            self.assertIsNone(active_hour("test", 1, 2, Decimal(1), duration).rate)
        zero = active_hour("test", 1, 2, Decimal(0), HOUR_MS)
        self.assertEqual(Decimal(0), zero.rate)
        self.assertEqual("complete", zero.status)
        self.assertIsNone(active_hour("test", 1, 2, Decimal(0), HOUR_MS, complete=False).rate)

    def test_periods_union_sessions_and_deduplicate_requests_not_concurrent_spend(self):
        now = DAY * 40 + HOUR_MS * 12
        a = bundle(history(((now - HOUR_MS * 2, now - HOUR_MS),)), now)
        p = a.prompts[0]
        e = a.trace_entries[0]
        other = replace(e, session_id="other", message_id="different", completed_at_ms=now - HOUR_MS // 2)
        b = replace(a, root_session_id="other", trace_entries=(other,),
                    prompts=(replace(p, session_id="other", prompt_time_ms=now - HOUR_MS * 3 // 2),))
        a = replace(a, trace_entries=(e, e))
        values = period_active_hours((a, b), lambda *_: Decimal("7.12345"), timezone_id="UTC", now_ms=now)
        today = values[0]
        self.assertEqual(Decimal("14.24690"), today.known_ccost)
        self.assertEqual(2, today.observed_requests)
        self.assertEqual(HOUR_MS * 3 // 2, today.duration_ms)
        self.assertEqual(Decimal("14.24690") / Decimal("1.5"), today.rate)

    def test_message_fallback_replaced_by_step_and_clone_fingerprint_reused(self):
        now = DAY * 40 + HOUR_MS
        a = bundle(history(((now - 1000, now),)), now)
        e = a.trace_entries[0]
        step = replace(e, step_part_id="step")
        clone = replace(step, session_id="clone")
        result = period_active_hours((replace(a, trace_entries=(e, step, step, clone)),),
            lambda *_: Decimal(3), timezone_id="UTC", now_ms=now)[0]
        self.assertEqual(1, result.observed_requests)
        self.assertEqual(Decimal(3), result.known_ccost)

    def test_midnight_month_boundary_cost_event_allocation_and_clipped_execution(self):
        midnight = epoch("2026-11-01T00:00:00+00:00")
        now = midnight + HOUR_MS
        a = bundle(history(((midnight - HOUR_MS, now),)), now)
        today, month, rolling = period_active_hours((a,), lambda *_: Decimal(100), timezone_id="UTC", now_ms=now)
        self.assertEqual(HOUR_MS, today.duration_ms)
        self.assertEqual(HOUR_MS, month.duration_ms)
        self.assertEqual(2 * HOUR_MS, rolling.duration_ms)
        self.assertEqual(Decimal(100), today.known_ccost)
        self.assertEqual(Decimal(100), today.rate)
        earlier = replace(a, trace_entries=(replace(a.trace_entries[0], completed_at_ms=midnight - 1),))
        value = period_active_hours((earlier,), lambda *_: Decimal(100), timezone_id="UTC", now_ms=now)[0]
        self.assertEqual(Decimal(0), value.known_ccost)  # no invented proportional token billing
        self.assertEqual(HOUR_MS, value.duration_ms)

    def test_dst_local_days_and_rolling_exact_edge(self):
        for text, hours in (("2026-03-29T21:59:59+00:00", 23), ("2026-10-25T22:59:59+00:00", 25)):
            now = epoch(text)
            windows = dict(period_windows("Europe/Stockholm", now))
            self.assertEqual(hours * HOUR_MS - 1000, now - windows["Today"])
            self.assertEqual(ROLLING_MS, now - windows["Rolling 30 days"])
        now = epoch("2026-11-15T12:00:00+00:00")
        edge = now - ROLLING_MS
        a = bundle(history(((edge - 1000, edge + 1000), (now - 1000, now))), now)
        entries = (replace(a.trace_entries[0], completed_at_ms=edge - 1),
                   replace(a.trace_entries[1], completed_at_ms=edge))
        rolling = period_active_hours((replace(a, trace_entries=entries),), lambda *_: Decimal(10),
                                      timezone_id="UTC", now_ms=now)[2]
        self.assertEqual(2000, rolling.duration_ms)
        self.assertEqual(Decimal(10), rolling.known_ccost)
        self.assertEqual(1, rolling.observed_requests)

    def test_unknown_pricing_partial_telemetry_unknown_duration_and_source(self):
        now = DAY * 40 + HOUR_MS
        a = bundle(history(((now - 1000, now),)), now)
        for b, valuation, source in ((a, lambda *_: None, True),
                (replace(a, trace_entries=(replace(a.trace_entries[0], tokens=TokenUsage(known_fields=())),)), lambda *_: Decimal(0), True),
                (a, lambda *_: Decimal(3), False)):
            result = period_active_hours((b,), valuation, timezone_id="UTC", now_ms=now, source_complete=source)[0]
            self.assertIsNone(result.rate)
            self.assertEqual("partial", result.status)
        unknown = replace(a, prompts=(replace(a.prompts[0], execution_duration_ms=None),))
        result = period_active_hours((unknown,), lambda *_: Decimal(3), timezone_id="UTC", now_ms=now)[0]
        self.assertIsNone(result.duration_ms)
        self.assertIsNone(result.rate)
        self.assertEqual("unavailable", result.status)

    def test_child_compaction_tools_background_and_abort_reuse_canonical_boundaries(self):
        now = 10_000
        a = bundle(make_snapshot(), now)
        self.assertEqual(1300, period_active_hours((a,), lambda *_: Decimal(1), timezone_id="UTC", now_ms=now)[0].duration_ms)
        native = make_native_v2_compaction_snapshot()
        native = replace(native, messages=tuple(replace(m, completed_at_ms=2100) if m.message_id == "u_comp" else m for m in native.messages))
        self.assertEqual(1200, period_active_hours((bundle(native, now),), lambda *_: Decimal(1), timezone_id="UTC", now_ms=now)[0].duration_ms)
        snapshot = history(((1000, 2000),))
        background = BackgroundActivity("job", "root", "shell", 1500, "a0", running=False, ended_at_ms=5000)
        finished = period_active_hours((bundle(replace(snapshot, background=(background,)), now),),
                                      lambda *_: Decimal(1), timezone_id="UTC", now_ms=now)[0]
        self.assertEqual(4000, finished.duration_ms)
        self.assertEqual("complete", finished.status)
        user, assistant = snapshot.messages
        aborted = replace(snapshot, messages=(user, replace(assistant, completed_at_ms=None,
            termination=TerminalEvidence(completed_at_ms=3000, outcome=TerminalOutcome.CANCELLATION))))
        self.assertEqual(2000, period_active_hours((bundle(aborted, now),), lambda *_: Decimal(1), timezone_id="UTC", now_ms=now)[0].duration_ms)

    def test_running_periods_are_frozen_provisional_and_zero_time_has_no_rate(self):
        snapshot = history(((1000, None),))
        a = bundle(snapshot, 4000)
        early = period_active_hours((a,), lambda *_: Decimal(1), timezone_id="UTC", now_ms=4000)[0]
        self.assertEqual("provisional", early.status)
        self.assertEqual(3000, early.duration_ms)
        self.assertEqual(Decimal(1200), early.rate)
        late = period_active_hours((bundle(snapshot, 8000),), lambda *_: Decimal(1), timezone_id="UTC", now_ms=8000)[0]
        self.assertEqual(7000, late.duration_ms)
        self.assertEqual(3000, early.duration_ms)
        empty = period_active_hours((), lambda *_: Decimal(0), timezone_id="UTC", now_ms=8000)[0]
        self.assertEqual(0, empty.duration_ms)
        self.assertIsNone(empty.rate)

    def test_application_finite_capture_progress_no_accounts_and_cached_roots(self):
        now = DAY * 40
        snapshot = history(((now - HOUR_MS, now),))
        root = replace(snapshot.root, updated_at_ms=now)
        snapshot = replace(snapshot, root=root, sessions=(root,))
        service = clean_service(self, snapshot, now=now)
        progress = []
        service.progress = progress.append
        with patch.object(service, "_quotas", side_effect=AssertionError("no quota refresh")), patch.object(
                service.source, "load_session_snapshot", wraps=service.source.load_session_snapshot) as load:
            service.build(ReportRequest(ReportKind.COST_PER_HOUR))
            service.build(ReportRequest(ReportKind.COST_PER_HOUR))
            self.assertEqual(1, load.call_count)
        self.assertTrue(any(getattr(item, "phase", "") == "history" and item.total == 1 for item in progress))
        result = hourly_result(self)
        self.assertIsNone(result["error"])
        self.assertEqual(3, len(result["view"]["active_hours"]))
        self.assertEqual([], result["view"]["request_identities"])
        self.assertEqual("explicit_period_execution_history", result["scope"]["history_policy"])
        self.assertEqual(ReportKind.COST_PER_HOUR, parse_report({"kind": "cost-per-hour"}).kind)

    def test_stale_metadata_does_not_exclude_proven_active_cross_window_work(self):
        now = epoch("2026-10-30T12:00:00+00:00")
        snapshot = history(((now - 31 * DAY, None),))
        root = replace(snapshot.root, created_at_ms=1000, updated_at_ms=1000, active=True)
        snapshot = replace(snapshot, root=root, sessions=(root,))
        service = clean_service(self, snapshot, now=now)
        report = service.build(ReportRequest(ReportKind.COST_PER_HOUR))
        self.assertEqual(ROLLING_MS, report.active_hours[2].duration_ms)
        self.assertEqual(12 * HOUR_MS, report.active_hours[0].duration_ms)
        self.assertEqual("provisional", report.active_hours[2].status)

    def test_session_detail_full_totals_survive_paging_freeze_and_source_loss(self):
        service = clean_service(self, history(((1000, None),)), now=4000)
        details = SessionDetails()
        token = details.open("root", "live")
        details.tick(service)
        early = details.page(token, 0)
        metric = early["result"]["view"]["prompt_blocks"][0]["active_hour"]
        self.assertEqual("provisional", metric["status"])
        self.assertEqual(3000, metric["duration_ms"])
        details.freeze(token)
        service.set_now_ms(9000)
        details.tick(service, unavailable=True)
        self.assertEqual(early["result"], details.page(token, 0)["result"])
        # Shipped CLI rendering ignores the new metadata entirely.
        report = service.build(ReportRequest(ReportKind.SESSION, session_id="root"))
        self.assertEqual(rendered(report), rendered(replace(report,
            prompt_blocks=tuple(replace(b, rate_usage_complete=False, rate_provisional=False) for b in report.prompt_blocks))))

    def test_live_session_rate_advances_only_on_observed_clock_and_freezes_on_outage(self):
        service = clean_service(self, history(((1000, None),)), now=4000)
        clock = [0]
        details = SessionDetails(clock=lambda: clock[0])
        token = details.open("root", "live")
        details.tick(service)
        early = details.page(token, 0)
        service.set_now_ms(8000); clock[0] = 6
        details.tick(service)
        late = details.page(token, 0)
        self.assertEqual(3000, early["result"]["view"]["prompt_blocks"][0]["active_hour"]["duration_ms"])
        self.assertEqual(7000, late["result"]["view"]["prompt_blocks"][0]["active_hour"]["duration_ms"])
        service.set_now_ms(9000); clock[0] = 12
        details.tick(service, unavailable=True)
        lost = details.page(token, 0)
        self.assertEqual("source_unavailable", lost["state"])
        self.assertEqual(late["result"]["view"], lost["result"]["view"])
        self.assertEqual(late["result"]["observed_at_ms"], lost["result"]["observed_at_ms"])
        self.assertEqual("partial", lost["result"]["source"]["status"])

    def test_session_rate_uses_whole_history_not_visible_rows(self):
        snapshot = history(tuple((1000 + n * 3000, 2000 + n * 3000) for n in range(60)))
        service = clean_service(self, snapshot, now=DAY)
        details = SessionDetails()
        token = details.open("root", "snapshot")
        details.tick(service)
        first = details.page(token, 0)
        last = details.page(token, 50)
        self.assertEqual(50, len(first["result"]["view"]["prompt_blocks"][0]["rows"]))
        self.assertEqual(10, len(last["result"]["view"]["prompt_blocks"][0]["rows"]))
        a = first["result"]["view"]["prompt_blocks"][0]["active_hour"]
        b = last["result"]["view"]["prompt_blocks"][0]["active_hour"]
        self.assertEqual(a, b)
        self.assertEqual(60_000, a["duration_ms"])
        self.assertEqual(60, a["observed_requests"])

    @unittest.skipUnless(shutil.which("node"), "optional JS VM unavailable")
    def test_shipped_view_routes_display_units_and_no_browser_calculation(self):
        result = hourly_result(self)
        run = subprocess.run(["node", "development/tests/integration/web_active_hour.cjs"],
            input=json.dumps(result), text=True, capture_output=True, cwd=ROOT, timeout=10)
        self.assertEqual(0, run.returncode, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
