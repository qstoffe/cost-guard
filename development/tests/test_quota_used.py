"""FR000525: shared Used presentation and temporary visible-Watch announcement."""
from dataclasses import replace
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal as D
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from development.tests.fixtures.quota_rendering import NOW, quotas, rolling, watch_text, report_text
from src.application.contracts import record, export
from src.application.display import with_display
from src.analysis.quota_pace import quota_pace
from src.display import quota_usage
from src.domain import QuotaComponent
from src.presentation.accounts import quota_parts
from src.presentation.quota_migration import QuotaMigrationNotice, NOTICE, GLOBAL_SECONDS, PERSONAL_SECONDS
from src.presentation.watch import WatchRenderer
from src.watch.models import WatchProjection

ANCHOR = "2026-10-28T12:00:00Z"  # Synthetic clock, never the delivery anchor.
MERGE = datetime(2026, 10, 28, 12, tzinfo=timezone.utc).timestamp()


class UsedQuotaTests(unittest.TestCase):
    def test_remaining_pace_uses_19392_not_5608_after_bar_inversion(self):
        quota = QuotaComponent("Month", period="fixed", used=D(5608), remaining=D(19392),
            limit=D(25000), unit="AI credits", reset_at_ms=NOW + 4 * 3600_000)
        pace = quota_pace(quota, now_ms=NOW, timezone_id="UTC", workday_calendar="SE")
        self.assertEqual(D(19392), pace.per_day)
        self.assertEqual(D(19392), pace.per_workday)
        row = rolling()
        row = replace(row, account=replace(row.account, quotas=(quota,)), pace=(pace,))
        for text in (report_text(quotas(row)), watch_text(quotas(row), width=160)):
            self.assertIn("22% used", text)
            self.assertIn("19392/day · 19392/workday", text)
            self.assertNotIn("5608/day", text)

    def test_finite_parity_geometry_money_and_separate_remaining_pace(self):
        quota = QuotaComponent("Month", used=D(5608), remaining=D(19392), limit=D(25000),
            remaining_fraction=D("0.77568"), unit="AI credits", remaining_money=D("193.92"), limit_money=D(250))
        row = rolling()
        row = replace(row, account=replace(row.account, quotas=(quota,)))
        for width in (80, 120, 160):
            text = watch_text(quotas(row), width=width)
            self.assertIn("██░░░░░░░░  22% used", text)
            self.assertIn("5608/25000", text)
            self.assertNotIn("19392/25000", text)
            self.assertNotIn("CCost today", text)
            self.assertEqual(1, text.count("used"))
            self.assertTrue(all(len(line) <= width for line in text.splitlines()))
        normal = report_text(quotas(row))
        self.assertIn("5608/25000 AI credits ($56.08/$250.00)", normal)
        self.assertEqual(D("0.77568"), quota.remaining_fraction)
        self.assertEqual(D(19392), quota.remaining)
        dto = export(with_display(record(used=D(5608), remaining=D(19392), limit=D(25000),
            remaining_fraction=D("0.77568"), unit="AI credits", unlimited=False,
            remaining_money=D("193.92"), limit_money=D(250))))
        self.assertEqual("22%", dto["display"]["used_fraction"])
        self.assertEqual("5608/25000 AI credits", dto["display"]["quota_used"])
        self.assertEqual("$56.08", dto["display"]["used_money"])

    def test_unlimited_known_zero_unknown_and_no_denominator(self):
        for used in (None, D(0), D(5608)):
            quota = QuotaComponent("Month", used=used, unlimited=True, unit="AI credits")
            for watch in (True, False):
                text = " ".join(str(part) for part in quota_parts(quota, "UTC", now_ms=NOW, watch=watch, ccost="7"))
                self.assertIn("Unlimited", text)
                self.assertIn("Today: 7", text)
                for invalid in ("%", "█", "░", "/", "remaining", "limit unavailable"):
                    self.assertNotIn(invalid, text)
                if used is not None:
                    self.assertIn(str(used), text)
                    self.assertIn("used", text)
                else:
                    self.assertNotIn("used", text)
        self.assertEqual((None, D(17), None), quota_usage(used=D(17)))
        self.assertEqual((D("0.4"), None, None), quota_usage(remaining_fraction=D("0.6")))
        self.assertEqual((D(1), D(120), None), quota_usage(used=D(120), limit=D(100)))
        self.assertEqual((D(0), D(0), None), quota_usage(used=D(0), limit=D(100)))
        self.assertEqual((None, D(0), None), quota_usage(used=D(0), limit=D(0)))


class MigrationNoticeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "notice.sqlite3"
        self.now = MERGE + 3600

    def notice(self):
        return QuotaMigrationNotice(path=self.path, clock=lambda: self.now, merged_at=ANCHOR)

    def test_first_actual_publication_restart_and_personal_boundary(self):
        notice = self.notice()
        self.assertTrue(notice.eligible())
        self.assertFalse(self.path.exists(), "preparing an unseen frame consumes nothing")
        first = self.now
        notice.displayed(first)
        for elapsed, expected in ((86400, True), (PERSONAL_SECONDS - 1, True), (PERSONAL_SECONDS, False),
                                  (PERSONAL_SECONDS + 1, False)):
            self.now = first + elapsed
            restarted = self.notice()
            self.assertEqual(expected, restarted.eligible())
            self.assertEqual(first, restarted.first_shown)
        self.now = first + 3600
        self.assertFalse(self.notice().eligible(), "observed expiry remains remembered after clock rollback")

    def test_global_boundary_skips_all_initialization_even_with_missing_state(self):
        for elapsed in (GLOBAL_SECONDS, GLOBAL_SECONDS + 86400, GLOBAL_SECONDS + 90 * 86400):
            self.now = MERGE + elapsed
            self.assertFalse(self.notice().eligible())
            self.assertFalse(self.path.exists())
        self.now = MERGE + GLOBAL_SECONDS - 3600
        notice = self.notice()
        self.assertTrue(notice.eligible())
        notice.displayed(self.now)
        self.now += 3600
        self.assertFalse(notice.eligible())

    def test_competing_visible_starts_retain_earliest_not_latest(self):
        first, second = self.notice(), self.notice()
        self.assertTrue(first.eligible())
        self.now += 1
        self.assertTrue(second.eligible())
        second.displayed(self.now)
        first.displayed(self.now - 1)  # Earlier publication commits last.
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual((self.now - 1,), db.execute("SELECT first_shown FROM notice").fetchone())
            self.assertEqual((1,), db.execute("SELECT count(*) FROM notice").fetchone())

    def test_invalid_unwritable_state_and_rollback_fail_closed_without_blocking(self):
        self.path.write_bytes(b"invalid")
        self.assertFalse(self.notice().eligible())
        self.path.unlink()
        notice = self.notice()
        self.assertTrue(notice.eligible())
        with patch("src.presentation.quota_migration.sqlite3.connect", side_effect=sqlite3.OperationalError):
            notice.displayed(self.now)
        self.assertFalse(notice.eligible())
        notice = self.notice()
        self.assertTrue(notice.eligible())
        notice.displayed(self.now)
        self.now -= 10
        self.assertFalse(notice.eligible())
        self.assertFalse(self.notice().eligible(), "persisted future timestamp is not rearmed")

    def test_visible_watch_only_warning_above_table_expiry_redraw_and_failed_publish(self):
        stream = io.StringIO()
        stream.isatty = lambda: True  # Synthetic visible terminal, isolated application state.
        renderer = WatchRenderer({}, stream=stream, interactive=True, terminal_width=120)
        renderer._quota_notice = self.notice()
        projection = WatchProjection("Watch", "V2", (), now_ms=NOW)
        renderer.render_initializing()
        self.assertFalse(self.path.exists())
        renderer.render(projection)
        text = stream.getvalue()
        self.assertEqual(1, text.count(NOTICE))
        self.assertLess(text.index(NOTICE), text.index("| Session / prompt"))
        self.assertTrue(self.path.exists())
        self.now += PERSONAL_SECONDS
        stream.seek(0); stream.truncate()
        renderer.render_status(projection)
        self.assertNotIn(NOTICE, stream.getvalue())
        self.path.unlink()
        hidden = WatchRenderer({}, stream=io.StringIO(), interactive=False)
        hidden._quota_notice = self.notice()
        hidden.render(projection)
        self.assertFalse(self.path.exists())
        renderer._quota_notice = self.notice()
        with patch.object(renderer._screen, "publish", side_effect=OSError):
            with self.assertRaises(OSError):
                renderer.render(projection)
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
