"""Cold opt-in views share one blank archive while a 10k-root source is held."""
from contextlib import closing
from pathlib import Path
import re
import shutil
import sqlite3
from tempfile import TemporaryDirectory
from threading import Event
import time
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit

from development.tests.fixtures.opencode_v1_database import SCHEMA
from src.application.session_catalog import SessionCatalog
from src.sources.opencode_v1 import OpenCodeV1Source
from src.web.display_archive import DisplayArchive
from src.web.host import WebHost
from src.web.jobs import ReportJobs


PERIODS = {"today": "Today", "7-days": "7 days", "30-days": "30 days", "month": "This month", "all": "All time"}
SESSION_SORTS = {"activity": "Last activity", "name": "Session name", "model": "Model",
                 "ccost": "CCost", "prompts": "Prompts", "duration": "Duration", "ctx": "Ctx"}
FORBIDDEN = {"/api/data", "/api/reports", "/api/sessions", "/api/detail", "/api/accounts/timeline"}


def _populate(path, now_ms, activity=None, *, count=200):
    def roots():
        for index in range(count):
            clock = activity(now_ms, index) if activity is not None else now_ms - index * 60_000
            yield f"ses_cold_{index:05d}", "fixture", "/fixture", f"Synthetic root {index}", clock - 60_000, clock

    with closing(sqlite3.connect(path)) as db, db:
        db.executescript(SCHEMA.read_text(encoding="utf-8"))
        db.executemany("""
            INSERT INTO session(id,project_id,directory,title,time_created,time_updated) VALUES(?,?,?,?,?,?)
        """, roots())
        assert db.execute("SELECT count(*) FROM session").fetchone() == (count,)


def _periods(page, panel, endpoint, *, start, empty, keys=tuple(PERIODS)):
    from playwright.sync_api import expect

    for key in (*[key for key in keys if key != start], start):
        control = panel.get_by_role("button", name=PERIODS[key], exact=True)
        with page.expect_response(lambda response: urlsplit(response.url).path == endpoint
                                 and response.request.post_data_json.get("period") == key) as read:
            control.click()
        assert read.value.ok, (endpoint, read.value.status)
        expect(control).to_have_attribute("aria-pressed", "true")
        expect(panel.get_by_text(empty)).to_be_visible()
        expect(page.locator("#result")).to_have_attribute("aria-busy", "false")


def _sessions(page, panel):
    from playwright.sync_api import expect

    endpoint = "/api/cache/sessions"
    empty = "No cached sessions yet"
    _periods(page, panel, endpoint, start="today", empty=empty)
    expect(panel.get_by_role("img", name="Loading older history")).to_be_visible()
    for key, label in SESSION_SORTS.items():
        control = panel.get_by_role("button", name=re.compile(rf"^{label}( [↑↓])?$"))
        for direction, order in ((1, "ascending"), (-1, "descending")):
            with page.expect_response(lambda response: urlsplit(response.url).path == endpoint
                    and response.request.post_data_json.get("sort") == key
                    and response.request.post_data_json.get("direction") == direction) as read:
                control.click()
            data = read.value.json()
            assert read.value.ok and data["cached_total"] == 0 and data["rows"] == []
            expect(control.locator("..")).to_have_attribute("aria-sort", order)
    expect(panel.get_by_role("button", name="Previous", exact=True)).to_be_disabled()
    expect(panel.get_by_role("button", name="Next", exact=True)).to_be_disabled()


def _models(page, panel):
    from playwright.sync_api import expect

    endpoint = "/api/cache/models"
    release = panel.get_by_role("button", name="Release date", exact=False)
    seen = []
    for _ in range(2):
        with page.expect_response(lambda response: urlsplit(response.url).path == endpoint
                and response.request.post_data_json["orders"][0][0] == "release") as read:
            release.click()
        assert read.value.ok and read.value.json()["rows"] == []
        seen.append(read.value.request.post_data_json["orders"][0][1])
    assert set(seen) == {"asc", "desc"}
    filters = panel.locator(".model-filters").first
    for name in ("Latest versions only", "Show all Copilot-priced models"):
        with page.expect_response(lambda response: urlsplit(response.url).path == endpoint) as read:
            filters.get_by_role("checkbox", name=name, exact=True).click()
        assert read.value.ok and read.value.json()["rows"] == []


def _journey(page, link, selector, empty=None):
    from playwright.sync_api import expect

    start = time.perf_counter()
    if link:
        page.get_by_role("link", name=link, exact=True).click()
    panel = page.locator("#result " + selector)
    expect(panel).to_be_visible(timeout=5000)
    if empty:
        expect(panel.get_by_text(empty)).to_be_visible()
    expect(page.locator("#result")).to_have_attribute("aria-busy", "false")
    return panel, round((time.perf_counter() - start) * 1000, 1)


def check_cached_cold_views(browser, evidence, product_root):
    from playwright.sync_api import expect

    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "config").mkdir()
        shutil.copyfile(product_root / "config/default-config.jsonc", root / "config/default-config.jsonc")
        path = root / "source.db"
        now = int(time.time() * 1000)
        _populate(path, now)
        source = OpenCodeV1Source(path)
        service = SimpleNamespace(timezone_id="UTC", selection=SimpleNamespace(selected="v1", source=source))
        driver = SimpleNamespace(error=None, terminal=False, observed_at_ms=None,
                                 coordinator=SimpleNamespace(report_service=service, catalog_observation=None))
        host = WebHost(root, jobs=ReportJobs())
        for kind in ("accounts", "mix", "models", "sessions", "stats", "watch"):
            setattr(host, f"cached_{kind}_enabled", True)
        archive = host.display_archive = DisplayArchive(root, host.events.publish, watch_enabled=True, mix_enabled=True,
            mix_groups=True, stats_enabled=True, models_enabled=True, accounts_enabled=True)
        assert archive.initialize()
        archive.observe(driver, before_tick=True)
        host.start()
        host.live = SimpleNamespace(driver=driver, catalog=SessionCatalog(), stopping=Event(), close=archive.close)
        host.publish_ready()
        context = browser.new_context(viewport={"width": 1100, "height": 800}, reduced_motion="reduce")
        requests, errors, first_ms = [], [], {}
        try:
            origin = host.server.origin
            context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(origin + "/")
                          else route.abort())
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(type(error).__name__))
            page.on("request", lambda req: requests.append(urlsplit(req.url).path))
            with patch.object(source, "_connection", side_effect=AssertionError("cold view opened the held source")) as reads, \
                    patch.object(host.jobs, "submit", side_effect=AssertionError("cold view submitted a report")) as jobs, \
                    patch.object(host.benchmark.jobs, "submit",
                                 side_effect=AssertionError("cold view started benchmark work")) as benchmark:
                page.goto(host.browser_url())
                models, first_ms["models"] = _journey(page, None, ".models-view",
                                                      "No Models snapshot is available for this selection.")
                _models(page, models)
                sessions, first_ms["sessions"] = _journey(page, "Sessions", ".sessions-catalog", "No cached sessions yet")
                _sessions(page, sessions)
                stats_empty = "No measured work is cached for this period yet."
                stats, first_ms["stats"] = _journey(page, "AI Stats", ".cached-stats", stats_empty)
                _periods(page, stats, "/api/cache/ai-stats", start="30-days", empty=stats_empty)
                expect(stats.locator('[data-metric="tokens"]')).to_have_text("—")
                mix_empty = "No cached usage yet."
                mix, first_ms["mix"] = _journey(page, "Token Mix", ".token-mix-view", mix_empty)
                _periods(page, mix, "/api/cache/token-mix", start="all", empty=mix_empty)
                groups = mix.get_by_role("region", name="Cached Token Mix by model")
                for _ in range(2):
                    groups.get_by_role("button", name="Tokens", exact=True).click()
                expect(groups.locator("tbody tr")).to_have_count(0)
                accounts_empty = "No observed account history is cached for this period."
                accounts, first_ms["accounts"] = _journey(page, "Accounts", ".account-timeline", accounts_empty)
                _periods(page, accounts, "/api/cache/accounts", start="month", empty=accounts_empty,
                         keys=("today", "7-days", "30-days", "month"))
                watch, first_ms["watch"] = _journey(page, "Watch", ".watch-view")
                expect(watch.get_by_text("No running prompts", exact=True)).to_be_hidden()
                expect(watch.locator(".watch-active article")).to_have_count(0)
                page.wait_for_function("watchCache.value?.freshness === 'empty'")
                page.evaluate("location.hash = '#/sessions/ses_cold_00000'")
                detail, first_ms["detail"] = _journey(page, None, ".session-detail-cache", "No cached detail yet.")
                expect(detail.get_by_role("button", name="Next", exact=True)).to_be_disabled()
                assert archive.history.session_page(archive.views.source).total == 0
                reads.assert_not_called()
                jobs.assert_not_called()
                benchmark.assert_not_called()
            required = {f"/api/cache/{kind}" for kind in ("models", "sessions", "ai-stats", "token-mix",
                                                         "accounts", "watch", "session-detail")}
            assert required <= set(requests), sorted(required - set(requests))
            assert "/api/models/benchmark" in requests
            assert not FORBIDDEN.intersection(requests), sorted(FORBIDDEN.intersection(requests))
            assert not errors, errors
            evidence["cached_cold_views"] = dict(source_roots=200, committed_roots=0,
                source_reads=0, finite_submits=0, benchmark_submits=0)
        finally:
            context.close()
            host.close()


if __name__ == "__main__":
    import json
    import os
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.environ.get("BROWSER_PROBE_EXECUTABLE"), headless=True)
        try:
            evidence = {}
            check_cached_cold_views(browser, evidence, Path.cwd())
            print(json.dumps(evidence))
        finally:
            browser.close()
