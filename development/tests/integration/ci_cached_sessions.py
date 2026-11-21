"""Render the draft Sessions cache controller against protected HTTP and SQLite."""
from decimal import Decimal
from pathlib import Path
import shutil
import tempfile
import time
from types import SimpleNamespace
from urllib.parse import urlsplit

from src.reports.models import SessionUsageRow
from src.sources.opencode_v1 import OpenCodeV1Source
from src.web.display_archive import DisplayArchive
from src.web.host import WebHost
from src.web.jobs import ReportJobs

from development.tests.fixtures.web_reports import current_report


def check_cached_sessions(browser, evidence, product_root):
    from playwright.sync_api import expect

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "config").mkdir()
        shutil.copyfile(product_root / "config/default-config.jsonc", root / "config/default-config.jsonc")
        source_path = root / "fixture.db"
        source_path.write_bytes(b"fixture identity; intentionally not an OpenCode database")
        selection = SimpleNamespace(selected="v1", source=OpenCodeV1Source(source_path))
        service = SimpleNamespace(selection=selection, timezone_id="UTC")
        driver = SimpleNamespace(coordinator=SimpleNamespace(report_service=service, catalog_observation=None),
                                 terminal=False, error=None)
        host = WebHost(root, jobs=ReportJobs(target=current_report))
        host.display_archive = DisplayArchive(root, host.events.publish)
        host.cached_sessions_enabled = True
        host.display_archive.observe(driver, before_tick=True)
        views = host.cached_session_views
        owner = host.display_archive.sessions
        now = int(time.time() * 1000)
        host.start()
        host.publish_ready()
        context = browser.new_context(viewport={"width": 1100, "height": 800})
        try:
            origin = host.server.origin
            context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(origin + "/") else route.abort())
            first = context.new_page()
            first.goto(host.browser_url())
            expect(first.locator("#result .overview-models")).to_be_visible(timeout=15000)
            requests = []
            first.on("request", lambda request: requests.append(urlsplit(request.url).path))
            start = time.perf_counter()
            first.get_by_role("link", name="Sessions", exact=True).click()
            pager = first.locator(".sessions-catalog .page-navigation")
            expect(pager).to_contain_text("No cached sessions yet", timeout=5000)
            first_ms = (time.perf_counter() - start) * 1000
            expect(first.get_by_role("button", name="Next", exact=True)).to_be_disabled()

            def commit(offset, amount):
                rows = {f"s-{index:03d}": SessionUsageRow(f"s-{index:03d}", f"Session {index}", "Example",
                    False, Decimal(index), index, last_activity_ms=now - 1000, activity_qualified=True)
                    for index in range(offset, offset + amount)}
                revisions = dict.fromkeys(rows, "revision")
                owner.commit(owner.admit(revisions), rows, revisions)

            first.get_by_role("button", name="All time", exact=True).click()
            expect(first.get_by_role("button", name="All time", exact=True)).to_have_attribute("aria-pressed", "true")
            commit(1, 30)
            expect(pager).to_contain_text("of 30 cached sessions", timeout=5000)
            prompts = first.locator("th").filter(has_text="Prompts")
            prompts.get_by_role("button").click()
            expect(prompts).to_have_attribute("aria-sort", "ascending", timeout=5000)
            with first.expect_response(lambda response: urlsplit(response.url).path == "/api/cache/sessions"
                                       and response.request.post_data_json.get("offset") == 25) as page_two:
                first.get_by_role("button", name="Next", exact=True).click()
            assert page_two.value.ok
            assert page_two.value.request.post_data_json == dict(period="all", sort="prompts", direction=1, offset=25)
            expect(pager).to_contain_text("26–30 of 30 cached sessions", timeout=5000)
            names = first.locator(".sessions-catalog tbody .session-name")
            expect(names).to_have_text([f"Session {index}" for index in range(26, 31)])
            first.go_back()
            expect(pager).to_contain_text("1–25 of 30 cached sessions")
            first.go_forward()
            expect(pager).to_contain_text("26–30 of 30 cached sessions")
            second = context.new_page()
            second.goto(first.url)
            expect(second.locator(".sessions-catalog .page-navigation")).to_contain_text("26–30 of 30 cached sessions")

            commit(31, 10)
            expect(pager).to_contain_text("26–40 of 40 cached sessions", timeout=5000)
            expect(second.locator(".sessions-catalog .page-navigation")).to_contain_text("26–40 of 40 cached sessions")
            assert "offset=25" in first.url and "offset=25" in second.url
            assert "/api/cache/sessions" in requests and "/api/sessions" not in requests and "/api/reports" not in requests
            assert host.display_archive.history.session_page(views.source).total == 40
            host.display_archive.unbind()
            expect(pager).to_contain_text("Session cache unavailable", timeout=5000)
            expect(first.locator(".sessions-catalog tbody tr")).to_have_count(0)
            evidence["cached_sessions"] = dict(first_cache_dom_ms=round(first_ms, 1), committed_rows=40,
                checked="cold empty, held source, period/sort/page, reactive page two in two tabs, source unbind")
        finally:
            context.close()
            host.close()
