"""Adjacent cache pages keep exact nullable ordering as the archive changes."""
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.application.cached_session_views import CachedSessionViews
from src.cache.display_history import DisplayHistory, SessionChange, SessionFact
from src.cache.display_session_seek import seek_keys


class DisplaySessionSeekTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.history = DisplayHistory(Path(directory.name))
        self.history.initialize()
        self.views = CachedSessionViews(self.history, "source", "UTC", "binding")

    @staticmethod
    def ids(page):
        return [row["session_id"] for row in page["rows"]]

    def test_forward_and_back_across_equal_costs_and_nulls_in_both_directions(self):
        low = Decimal("0.10000000000000000000001")
        high = Decimal("0.10000000000000000000002")
        changes = tuple(SessionChange(SessionFact(f"s{i:03d}", "one", "Fixture",
            ccost=(low, high, None)[i % 3]), None) for i in range(149))
        self.history.commit_sessions("source", changes)
        groups = [[f"s{i:03d}" for i in range(group, 149, 3)] for group in range(3)]

        for direction in (1, -1):
            with self.subTest(direction=direction):
                expected = (groups[0] + groups[1] if direction == 1 else groups[1] + groups[0]) + groups[2]
                args = dict(period="all", sort="ccost", direction=direction)
                previous = self.views.page(**args, offset=75)

                with patch("src.cache.display_history.seek_keys", wraps=seek_keys) as seeks:
                    next_page = self.views.page(**args, offset=100, cursor=previous["next_cursor"])
                    reverse_page = self.views.page(**args, offset=75, cursor=next_page["previous_cursor"])
                    last_page = self.views.page(**args, offset=125, cursor=next_page["next_cursor"])

                self.assertEqual(3, seeks.call_count)
                self.assertEqual(expected[100:125], self.ids(next_page))
                self.assertEqual(expected[75:100], self.ids(reverse_page))
                self.assertEqual(expected[125:], self.ids(last_page))
                self.assertEqual(149, last_page["cached_total"])

    def test_an_adjacent_period_cursor_reuses_count_only_while_window_and_generation_match(self):
        changes = tuple(SessionChange(SessionFact(f"s{i:03d}", "one", "Fixture",
            activity_ms=20_000 if i == 75 else 10_000, prompts=i), None) for i in range(76))
        self.history.commit_sessions("source", changes)
        args = dict(period="today", sort="prompts", direction=1)
        first = self.views.page(**args, now_ms=15_000)
        cursor = first["next_cursor"]
        changed = SessionChange(SessionFact("s000", "two", "Fixture", activity_ms=10_000, prompts=77), "one")

        with patch("src.cache.display_history.seek_keys", wraps=seek_keys) as seeks:
            stable = self.views.page(**args, offset=25, cursor=cursor, now_ms=19_999)
            crossed = self.views.page(**args, offset=25, cursor=cursor, now_ms=20_000)
            self.history.commit_sessions("source", (changed,))
            corrected = self.views.page(**args, offset=25, cursor=cursor, now_ms=19_999)
            other = CachedSessionViews(self.history, "source", "UTC", "rotated")
            foreign = other.page(**args, offset=25, cursor=cursor, now_ms=19_999)

        self.assertEqual(1, seeks.call_count)
        self.assertEqual((75, 76, 75, 75), tuple(p["cached_total"] for p in (stable, crossed, corrected, foreign)))
        self.assertEqual([f"s{i:03d}" for i in range(25, 50)], self.ids(stable))
        self.assertEqual([f"s{i:03d}" for i in range(26, 51)], self.ids(corrected))
        self.assertEqual(self.ids(corrected), self.ids(foreign))

    def test_v29_title_order_is_reindexed_without_losing_tied_casefolded_names(self):
        changes = tuple(SessionChange(SessionFact(f"s{i:03d}", "one", ("AE", "Ä", "ä")[i % 3]), None)
                        for i in range(76))
        self.history.commit_sessions("source", changes)
        with self.history._connect() as db:
            db.executescript("""
                DROP INDEX sessions_name_asc;
                DROP INDEX sessions_name_desc;
                CREATE INDEX sessions_name_asc ON sessions(source,(title_key IS NULL),title_key ASC,session_id,period_clock_ms);
                CREATE INDEX sessions_name_desc ON sessions(source,(title_key IS NULL),title_key DESC,session_id,period_clock_ms);
                PRAGMA user_version=29;
            """)
        expected = [f"s{i:03d}" for i in range(76) if i % 3] + [f"s{i:03d}" for i in range(0, 76, 3)]

        self.history.initialize()
        first = self.views.page(period="all", sort="name", direction=-1)
        second = self.views.page(period="all", sort="name", direction=-1, offset=25, cursor=first["next_cursor"])

        self.assertEqual(expected[:50], self.ids(first) + self.ids(second))
        with self.history._connect(read=True) as db:
            detail = tuple(row[-1] for row in db.execute("""
                EXPLAIN QUERY PLAN SELECT session_id FROM sessions INDEXED BY sessions_name_desc
                WHERE source='source' AND title_key<'ä'
                ORDER BY title_key DESC,session_id LIMIT 25
            """))
        self.assertTrue(any("title_key<" in plan for plan in detail), detail)
        self.assertFalse(any("TEMP B-TREE" in plan for plan in detail), detail)
