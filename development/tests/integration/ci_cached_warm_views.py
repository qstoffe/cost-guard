"""Real loopback warm restart with typed synthetic facts, not a size benchmark."""
from contextlib import closing
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory
from threading import Event
import time
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit

from development.tests.fixtures.display_watch import running_frame
from development.tests.fixtures.session_snapshots import one_request
from development.tests.integration.ci_cached_cold_views import FORBIDDEN, _journey, _populate
from development.tests.test_archive_stats_evidence import capture as stats_capture
from development.tests.test_display_account_history import REF, observation
from development.tests.test_display_models import capture as models_capture, model
from src.application.session_catalog import SessionCatalog
from src.cache.display_history import BATCH_LIMIT, RunningSession, SessionChange, SessionFact
from src.cache.display_prompts import DisplayPrompt
from src.cache.display_stats_evidence import StatsInterval
from src.domain import AccountSnapshot
from src.sources.opencode_v1 import OpenCodeV1Source
from src.web.display_archive import DisplayArchive
from src.web.host import WebHost
from src.web.jobs import ReportJobs

COUNT = 5_000
RETAINED = "ses_cold_00000"
CURRENT = "ses_cold_00001"
DAY_MS = 86_400_000


def bind(host, root, source):
    for kind in ("models", "watch", "sessions", "stats", "mix", "accounts"):
        setattr(host, f"cached_{kind}_enabled", True)
    archive = DisplayArchive(root, host.events.publish, watch_enabled=True, mix_enabled=True, mix_groups=True,
                             stats_enabled=True, models_enabled=True, accounts_enabled=True)
    host.display_archive = archive
    assert archive.initialize()
    service = SimpleNamespace(timezone_id="UTC", selection=SimpleNamespace(selected="v1", source=source))
    driver = SimpleNamespace(error=None, terminal=False, observed_at_ms=None,
                             coordinator=SimpleNamespace(report_service=service, catalog_observation=None))
    archive.observe(driver, before_tick=True)
    return archive, driver


def request_facts(key, index, clock):
    captured = stats_capture(one_request(running=False))
    sample, = captured.requests
    identity = replace(sample.stats_identity, message_key=key.encode().ljust(32, b"-"))
    request = replace(observation(index, clock, costs=("25", "0", "0", "0"), root=key),
                      session_id=key, stats_identity=identity, tokens=(40, 30, 20, 10, 0))
    interval = StatsInterval(key, "prompt", "prompt", clock - 60_000, 60_000, False)
    prompt = DisplayPrompt("prompt", clock - 60_000, clock, 60_000, "prompt", 1, "Saved model", "medium",
                           1, 773, Decimal(25), True, None, None, "40,30,20,10", "finished")
    return replace(captured, pricing="fixture", requests=(request,), attribution=(), prompts=(prompt,),
                   stats=replace(captured.stats, intervals=(interval,), parents=((key, None),), first_input=None))


def seed(archive, now):
    source = archive.views.source
    for start in range(0, COUNT, BATCH_LIMIT):
        changes = []
        for index in range(start, min(start + BATCH_LIMIT, COUNT)):
            key = f"ses_cold_{index:05d}"
            clock = now - (60 * DAY_MS if index == 0 else index * 60_000)
            title = "Retained oldest fixture" if index == 0 else f"Saved session {index:05d}"
            facts = request_facts(key, index, clock) if index in (0, 1) else None
            change = SessionChange(SessionFact(key, "seed", title, clock, "Saved model",
                Decimal(index), index, 60_000, 773), None, previous_progress=0 if facts else None, request_roster=facts)
            if facts is not None:
                archive.history.commit_sessions(source, (change,))
            else:
                changes.append(change)
        archive.history.commit_sessions(source, tuple(changes))
    scope = archive.models.binding()
    assert archive.models.offer(scope, models_capture((model("Saved reference model", ["3"]),),
        scope=source, observed=now), eligible=lambda: True)
    roster = (SimpleNamespace(account=AccountSnapshot(REF, now, "OpenAI"), label="Saved reference account"),)
    archive.accounts.offer(roster, verified=True)
    for _ in range(300):
        turn = archive.next_projection(lambda: None)
        if turn is None:
            break
        turn(now, active=lambda: True)
    else:
        raise AssertionError("warm fixture did not settle its synthetic projections")
    frame = running_frame(now)
    archive.publish_live((RunningSession("root", "Observed title", now - 2000, now),), frame, now)
    assert archive._live_write.result(timeout=5)
    return roster


def check_cached_warm_views(browser, evidence, product_root):
    from playwright.sync_api import expect

    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "config").mkdir()
        shutil.copyfile(product_root / "config/default-config.jsonc", root / "config/default-config.jsonc")
        path = root / "source.db"
        now = int(time.time() * 1000)
        _populate(path, now)
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("UPDATE session SET time_updated=? WHERE id=?", (now - 60 * DAY_MS, RETAINED))
        first_host = WebHost(root, jobs=ReportJobs())
        archive, _ = bind(first_host, root, OpenCodeV1Source(path))
        try:
            roster = seed(archive, now)
            # Delete one seeded root from the real V1 fixture; explicitly feed
            # that proven absence into the archive's membership write.
            with closing(sqlite3.connect(path)) as db, db:
                assert db.execute("DELETE FROM session WHERE id=?", (RETAINED,)).rowcount == 1
                assert db.execute("SELECT id FROM session WHERE id=?", (RETAINED,)).fetchone() is None
            partition = archive.views.source
            checkpoint = archive.history.session_checkpoints(partition, (RETAINED,))[RETAINED]
            assert archive.history.commit_sessions(partition, missing=((RETAINED, checkpoint),)) is not None
        finally:
            first_host.close()

        source = OpenCodeV1Source(path)
        host = WebHost(root, jobs=ReportJobs())
        archive, driver = bind(host, root, source)
        host.start()
        host.live = SimpleNamespace(driver=driver, catalog=SessionCatalog(), stopping=Event(), close=archive.close)
        host.publish_ready()
        context = browser.new_context(viewport={"width": 1100, "height": 800})
        requests, errors, first_ms = [], [], {}
        try:
            origin = host.server.origin
            context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(origin + "/")
                          else route.abort())
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(type(error).__name__))
            page.on("request", lambda req: requests.append(urlsplit(req.url).path))
            with patch.object(source, "_connection", side_effect=AssertionError("warm view accessed source")) as reads, \
                    patch.object(host.jobs, "submit", side_effect=AssertionError("warm view submitted report")) as jobs, \
                    patch.object(host.benchmark.jobs, "submit",
                                 side_effect=AssertionError("warm view started benchmark")) as benchmark:
                page.goto(host.browser_url())
                models, first_ms["models"] = _journey(page, None, ".models-view", "Saved reference model")
                expect(models.get_by_role("button", name="Release date", exact=False)).to_be_enabled()
                session_time = time.perf_counter()
                sessions, _ = _journey(page, "Sessions", ".sessions-catalog")
                sessions.get_by_role("button", name="All time", exact=True).click()
                expect(sessions.get_by_text("of 5000 cached sessions", exact=False)).to_be_visible()
                first_ms["sessions_all_time"] = round((time.perf_counter() - session_time) * 1000, 1)
                sessions.get_by_role("button", name="Prompts", exact=False).click()
                expect(sessions.get_by_role("link", name="Retained oldest fixture")).to_be_visible()
                sessions.get_by_role("button", name="Next", exact=True).click()
                expect(sessions.get_by_text("26–50 of 5000 cached sessions", exact=False)).to_be_visible()

                stats_time = time.perf_counter()
                stats, _ = _journey(page, "AI Stats", ".cached-stats")
                stats.get_by_role("button", name="All time", exact=True).click()
                expect(stats.locator('[data-metric="tokens"]')).to_have_text("200")
                first_ms["stats_all_time"] = round((time.perf_counter() - stats_time) * 1000, 1)
                stats.get_by_role("button", name="7 days", exact=True).click()
                expect(stats.locator('[data-metric="tokens"]')).to_have_text("100")
                mix, first_ms["mix"] = _journey(page, "Token Mix", ".token-mix-view", "Cached Token Mix · 200 tokens")
                mix.get_by_role("button", name="7 days", exact=True).click()
                expect(mix.get_by_text("Cached Token Mix · 100 tokens", exact=True)).to_be_visible()
                watch, first_ms["watch"] = _journey(page, "Watch", ".watch-view", "Observed title")
                expect(watch.locator(".watch-active article")).to_have_count(0)
                expect(watch.get_by_text("Unverified", exact=False)).to_be_visible()
                page.evaluate("(id) => { location.hash = '#/sessions/' + id; }", RETAINED)
                detail, first_ms["detail"] = _journey(page, None, ".session-detail-cache",
                                                     "Saved history; the original source session is unavailable.")
                expect(detail.get_by_text("Saved model", exact=False).first).to_be_visible()

                accounts, first_ms["accounts_unknown_roster"] = _journey(page, "Accounts", ".account-timeline",
                    "No observed account history is cached for this period.")
                # Delayed account authorization is intentionally distinct from
                # the retained OpenCode source binding and cached chart rows.
                archive.accounts.offer(roster, verified=True)
                accounts.get_by_role("button", name="7 days", exact=True).click()
                expect(accounts.locator(".account-timeline-bar")).to_have_count(1)
                reads.assert_not_called()
                jobs.assert_not_called()
                benchmark.assert_not_called()
            assert not FORBIDDEN.intersection(requests), sorted(FORBIDDEN.intersection(requests))
            assert not errors, errors
            assert max(first_ms.values()) < 1_000, first_ms
            evidence["cached_warm_views"] = dict(metadata_rows=COUNT, typed_usage_roots=2,
                source_reads=0, finite_submits=0, benchmark_submits=0, synthetic_deleted_roots=1, views_exercised=7,
                accounts="still requires independently qualified account roster after restart",
                first_route_wall_ms=first_ms)
        finally:
            context.close()
            host.close()


if __name__ == "__main__":
    import os
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.environ.get("BROWSER_PROBE_EXECUTABLE"), headless=True)
        try:
            evidence = {}
            check_cached_warm_views(browser, evidence, Path.cwd())
            print(evidence)
        finally:
            browser.close()
