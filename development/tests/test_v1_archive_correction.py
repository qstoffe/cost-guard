"""Source deletion and correction are distinct from explicitly clearing Cost Guard."""
from contextlib import closing, contextmanager
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from development.tests.fixtures.opencode_v1_database import SCHEMA
from development.tests.fixtures.watch_runtime import make_service
from src.application.cached_mix_view import cached_mix_view
from src.application.session_catalog import SessionCatalog
from src.cache.display_history import HistoryState
from src.sources.opencode_v1 import OpenCodeV1Source
from src.watch.observers import observe_catalog
from src.web.display_archive import DisplayArchive


NOW = 1_790_510_400_000
DAY = 86_400_000
RETAINED = "ses_retained"
CORRECTED = "ses_corrected"


def step_usage(input_tokens):
    return json.dumps({"type": "step-finish", "reason": "stop", "cost": 0, "tokens": {
        "input": input_tokens, "output": 10, "reasoning": 0, "cache": {"read": 0, "write": 0}}})


def add_session(db, session_id, title, start, input_tokens, *, duration=3000):
    user, assistant = f"{session_id}-user", f"{session_id}-assistant"
    finish = start + duration
    model = {"providerID": "github-copilot", "modelID": "gpt-test"}
    db.execute("INSERT INTO session(id,project_id,directory,title,time_created,time_updated) VALUES(?,?,?,?,?,?)",
               (session_id, "fixture", "/fixture", title, start, finish))
    db.executemany("INSERT INTO message VALUES(?,?,?,?,?)", [
        (user, session_id, start, start,
         json.dumps({"role": "user", "time": {"created": start}, "model": model, "agent": "build"})),
        (assistant, session_id, start + 200, finish,
         json.dumps({"role": "assistant", "parentID": user, "time": {"created": start + 200, "completed": finish},
                     **model, "finish": "stop", "agent": "build"})),
    ])
    db.executemany("INSERT INTO part VALUES(?,?,?,?,?,?)", [
        (f"{user}-text", user, session_id, start, start, '{"type":"text","text":"Synthetic retained facts"}'),
        (f"{assistant}-step", assistant, session_id, finish, finish, step_usage(input_tokens)),
    ])


@contextmanager
def bound_archive(root, path):
    source = OpenCodeV1Source(path)
    _, selection, service, _ = make_service(root, source, now_ms=NOW, async_accounts=True)
    archive = DisplayArchive(root, lambda *_: None, mix_enabled=True, stats_enabled=True)
    try:
        if not archive.initialize():
            raise AssertionError("fresh display archive did not open")
        driver = SimpleNamespace(error=None, terminal=False,
                                 coordinator=SimpleNamespace(report_service=service, catalog_observation=None))
        archive.observe(driver, before_tick=True)
        yield archive, service, SessionCatalog(clock_ms=lambda: NOW)
    finally:
        archive.close()
        service.close_accounts()


def acquire(archive, service, catalog):
    catalog.observe(observe_catalog(service.source, include_archived_revisions=True))
    for _ in range(8):
        if not archive.catalog_pending(catalog):
            break
        archive.publish_catalog(catalog, service)
    else:
        raise AssertionError("two-root membership did not settle")
    for _ in range(8):
        if not archive.summary_pending(catalog):
            break
        archive.acquire_summaries(catalog, service)
    else:
        raise AssertionError("two-root summary acquisition did not settle")
    for _ in range(80):
        turn = archive.next_projection(lambda: None)
        if turn is None:
            return
        turn(NOW, active=lambda: True)
    raise AssertionError("two-root projections did not settle")


def totals(archive, period):
    views = archive.views
    mix = cached_mix_view(archive.history, views.source, views.timezone_id, period, NOW)
    stats = archive.stats.snapshot(period, NOW)
    return mix["observed_category_totals"], stats["observed_tokens"]


class V1ArchiveCorrectionTests(unittest.TestCase):
    def test_deleted_root_keeps_facts_corrected_root_replaces_usage_and_clear_does_not_touch_v1(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "fixture.db"
            old_start, recent_start = NOW - 60 * DAY, NOW - 60_000
            with closing(sqlite3.connect(path)) as db, db:
                db.executescript(SCHEMA.read_text(encoding="utf-8"))
                add_session(db, RETAINED, "Retained original", old_start, 100, duration=5000)
                add_session(db, CORRECTED, "Present original", recent_start, 200)

            with bound_archive(root, path) as (archive, service, catalog):
                acquire(archive, service, catalog)
                self.assertEqual((["300", "0", "0", "20"], "320"), totals(archive, "all"))
                self.assertEqual((["200", "0", "0", "10"], "210"), totals(archive, "7-days"))
                old_prompt, = archive.views.detail(session_id=RETAINED)["rows"]
                present_prompt, = archive.views.detail(session_id=CORRECTED)["rows"]
                self.assertIsNotNone(old_prompt["ccost"])
                self.assertEqual({"session_id": RETAINED, "title": "Retained original"},
                                 archive.stats.snapshot("all", NOW)["longest_session"])

            with closing(sqlite3.connect(path)) as db, db:
                db.execute("DELETE FROM part WHERE session_id=?", (RETAINED,))
                db.execute("DELETE FROM message WHERE session_id=?", (RETAINED,))
                self.assertEqual(1, db.execute("DELETE FROM session WHERE id=?", (RETAINED,)).rowcount)
                db.execute("UPDATE session SET title=?,time_updated=? WHERE id=?",
                           ("Present corrected", recent_start + 3001, CORRECTED))
                self.assertEqual(1, db.execute("UPDATE part SET data=? WHERE id=?",
                    (step_usage(300), f"{CORRECTED}-assistant-step")).rowcount)

            source_before_clear = path.read_bytes()
            with bound_archive(root, path) as (archive, service, catalog):
                acquire(archive, service, catalog)

                rows = archive.views.page(period="all", now_ms=NOW)["rows"]
                self.assertEqual([(CORRECTED, "Present corrected", True, recent_start + 3000),
                                  (RETAINED, "Retained original", False, old_start + 5000)],
                    [(row["session_id"], row["title"], row["source_present"], row["activity_ms"]) for row in rows])
                retained = archive.views.detail(session_id=RETAINED)
                self.assertEqual("retained", retained["history_coverage"])
                self.assertEqual([old_prompt], retained["rows"])
                corrected, = archive.views.detail(session_id=CORRECTED)["rows"]
                self.assertEqual(present_prompt["finish_ms"], corrected["finish_ms"])
                self.assertGreater(Decimal(corrected["ccost"]), Decimal(present_prompt["ccost"]))
                self.assertEqual((["400", "0", "0", "20"], "420"), totals(archive, "all"))
                self.assertEqual((["300", "0", "0", "10"], "310"), totals(archive, "7-days"))
                self.assertEqual({"session_id": RETAINED, "title": "Retained original"},
                                 archive.stats.snapshot("all", NOW)["longest_session"])
                self.assertEqual({"session_id": CORRECTED, "title": "Present corrected"},
                                 archive.stats.snapshot("7-days", NOW)["longest_session"])

                saved = archive.clear_snapshot()
                state = HistoryState(saved["generation"], saved["archive_epoch"])
                cleared = archive.clear_confirmed(saved["binding"], state, catalog, service, eligible=lambda: True)

                self.assertEqual(state.archive_epoch + 1, cleared["archive_epoch"])
                self.assertEqual([], archive.views.page(period="all", now_ms=NOW)["rows"])
                self.assertEqual((None, None), totals(archive, "all"))
                self.assertEqual(source_before_clear, path.read_bytes())

                acquire(archive, service, catalog)
                row, = archive.views.page(period="all", now_ms=NOW)["rows"]
                self.assertEqual(CORRECTED, row["session_id"])
                self.assertEqual((["300", "0", "0", "10"], "310"), totals(archive, "all"))
