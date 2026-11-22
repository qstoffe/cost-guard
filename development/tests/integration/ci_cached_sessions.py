"""Render the draft Sessions cache controller against protected HTTP and SQLite."""
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import shutil
import tempfile
from threading import Event
import time
from types import SimpleNamespace
from urllib.parse import urlsplit

from src.application.session_catalog import SessionCatalog
from src.cache.display_history import RunningSession, SessionCoverage
from src.cache.display_prompts import DisplayPrompt
from src.cache.display_requests import RequestRoster
from src.domain.effort import EffortEvidence
from src.reports.models import SessionUsageRow
from src.reports.session_models import SessionModel
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
        host.live = SimpleNamespace(catalog=SessionCatalog(), driver=driver, stopping=Event(),
                                    close=host.display_archive.close)
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
            older = first.get_by_role("img", name="Loading older history")
            expect(older).to_be_visible()
            first.emulate_media(reduced_motion="reduce")
            assert older.evaluate("(element) => getComputedStyle(element).animationName") == "none"
            first_ms = (time.perf_counter() - start) * 1000
            expect(first.get_by_role("button", name="Next", exact=True)).to_be_disabled()

            def commit(offset, amount):
                rows = {f"s-{index:03d}": SessionUsageRow(f"s-{index:03d}", f"Session {index}", "Example",
                    False, Decimal(index), index, last_activity_ms=now - 1000, activity_qualified=True,
                    context_qualified=index != 27, context_tokens=773 if index == 28 else None,
                    context_detail="Provisional text estimate." if index == 28 else "No supported context.",
                    main_models=(SessionModel("provider", "recorded-selector", efforts=(
                        EffortEvidence("default", "medium", "current-configuration"),)),) if index == 28 else ())
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
            with first.expect_request(lambda request: urlsplit(request.url).path == "/api/cache/sessions/demand"
                                      and "s-027" in request.post_data_json.get("session_ids", ())) as demand, \
                 first.expect_response(lambda response: urlsplit(response.url).path == "/api/cache/sessions"
                                       and response.request.post_data_json.get("offset") == 25) as page_two:
                first.get_by_role("button", name="Next", exact=True).click()
            assert page_two.value.ok
            request = page_two.value.request.post_data_json
            assert request.pop("cursor")
            assert request == dict(period="all", sort="prompts", direction=1, offset=25)
            hint = demand.value.post_data_json
            assert hint["binding"] == views.binding and hint["demand_epoch"] == 0 and hint["session_ids"] == ["s-027"]
            assert len(hint["tab"]) == 32 and hint["sequence"] >= 1
            expect(pager).to_contain_text("26–30 of 30 cached sessions", timeout=5000)
            names = first.locator(".sessions-catalog tbody .session-name")
            expect(names).to_have_text([f"Session {index}" for index in range(26, 31)])
            with first.expect_request(lambda request: urlsplit(request.url).path == "/api/cache/sessions/demand"
                                      and request.post_data_json.get("remember") is True) as recent:
                first.get_by_role("button", name="Previous", exact=True).click()
            assert recent.value.post_data_json["session_ids"] == []
            assert recent.value.post_data_json["sequence"] > hint["sequence"]
            expect(pager).to_contain_text("1–25 of 30 cached sessions")
            first.get_by_role("button", name="Next", exact=True).click()
            expect(names).to_have_text([f"Session {index}" for index in range(26, 31)])
            absent_context = first.locator('tr[data-id="s-026"] td:last-child span').first
            expect(absent_context).to_have_text("?")
            first.keyboard.press("Tab")
            absent_context.focus()
            expect(first.get_by_text("The source did not provide context for this session.", exact=True)).to_be_visible()
            first.keyboard.press("Escape")
            expect(first.locator('tr[data-id="s-027"]').get_by_role("img", name="Loading context")).to_be_visible()
            archived = first.locator('tr[data-id="s-028"]')
            owner.commit(owner.admit({"s-028": "revision"}), {}, {}, missing=("s-028",))
            archived.locator("td:nth-child(3) span").first.focus()
            expect(first.get_by_text("provider/recorded-selector", exact=False)).to_be_visible()
            expect(first.get_by_text("historical settings may differ", exact=False)).to_be_visible()
            first.keyboard.press("Escape")
            archived.locator("td:last-child span").first.focus()
            expect(first.get_by_text("Provisional text estimate.", exact=False)).to_be_visible()
            first.keyboard.press("Escape")
            detail_rows = tuple(DisplayPrompt(f"prompt-{index:02d}", now - (30 - index) * 1000, now - 1000,
                750, "prompt", index, "Recorded Model", "medium", 2, 773, Decimal("1.25"), True,
                None, None, "30,20,0,50", "finished") for index in range(1, 31))
            admitted = owner.admit({"s-028": "revision"})
            detail_summary = SessionUsageRow("s-028", "Session 28", "Example", False, Decimal(28), 30,
                last_activity_ms=now - 1000, context_tokens=773, context_detail="Provisional text estimate.")
            owner.commit(admitted, {"s-028": detail_summary}, {"s-028": "revision"},
                         usage=RequestRoster("fixture-prices", (), (), detail_rows))
            owner.commit(owner.admit({"s-028": "revision"}), {}, {}, missing=("s-028",))
            with first.expect_request(lambda request: urlsplit(request.url).path == "/api/cache/sessions/demand"
                                      and request.post_data_json.get("session_ids") == []) as withdrawn:
                archived.get_by_role("link", name="Session 28").click()
            expiry = withdrawn.value.post_data_json
            assert expiry["tab"] == hint["tab"] and expiry["sequence"] > hint["sequence"]
            detail = first.locator(".session-detail-cache")
            expect(detail.get_by_text("Saved history; the original source session is unavailable.")).to_be_visible()
            expect(detail.locator(".page-navigation")).to_contain_text("1–25 of 30 cached events")
            detail.get_by_role("button", name="Next").click()
            expect(detail.locator(".page-navigation")).to_contain_text("26–30 of 30 cached events")
            assert "/api/cache/session-detail" in requests and "/api/detail" not in requests
            reads = requests.count("/api/cache/session-detail")
            unrelated = owner.commit(owner.admit({"s-030": "revision"}), {}, {}, missing=("s-030",))
            first.wait_for_function("generation => current.detail.observedHint?.generation === generation", arg=unrelated)
            assert first.evaluate("!current.detail.timer && !current.detail.dirty && !current.detail.flight")
            assert requests.count("/api/cache/session-detail") == reads

            revisions = {"s-028": "revision"}
            owner.publish_catalog(owner.admit(revisions), {"s-028": "Session 28"}, revisions)
            expect(detail.get_by_text("Saved history; the original source session is unavailable.")).to_be_hidden()
            late = replace(detail_rows[0], event_id="prompt-late", start_ms=now - 31_000)
            owner.commit(owner.admit(revisions), {"s-028": detail_summary}, revisions,
                         usage=RequestRoster("fixture-prices", (), (), (late,)))
            expect(detail.locator(".page-navigation")).to_contain_text("26–31 of 31 cached events")
            # Drop a relevant hint at the publisher. A later unrelated hint
            # cannot rule out changes in the skipped cache generation.
            history = host.display_archive.history
            checkpoint = history.session_checkpoints(views.source, ("s-028",))["s-028"]
            history.commit_sessions(views.source, missing=(("s-028", checkpoint),))
            owner.commit(owner.admit({"s-029": "revision"}), {}, {}, missing=("s-029",))
            expect(detail.get_by_text("Saved history; the original source session is unavailable.")).to_be_visible()
            expect(detail.locator(".page-navigation")).to_contain_text("26–31 of 31 cached events")
            first.go_back()
            expect(pager).to_contain_text("26–30 of 30 cached sessions")
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
            owner.commit_live(views.source, views.binding, running=(RunningSession("running", "Live fixture", now - 1000,
                                                                                 int(time.time() * 1000)),), clear_fence=0)
            expect(pager).to_contain_text("26–41 of 41 cached sessions")
            expect(second.locator(".sessions-catalog .page-navigation")).to_contain_text("26–41 of 41 cached sessions")
            first.get_by_role("button", name="Previous", exact=True).click()
            expect(first.locator(".sessions-catalog tbody .session-name").first).to_have_text("[RUNNING] Live fixture")
            owner.commit_live(views.source, views.binding, running=(), clear_fence=0)
            expect(first.locator(".sessions-catalog tbody .session-name").first).to_have_text("Session 1")
            assert "offset=25" in second.url
            owner.publish_coverage(views.source, views.binding, 0, SessionCoverage(now, False, False, None),
                                   eligible=lambda: True)
            expect(older).to_be_hidden()
            clear = first.get_by_role("button", name="Clear local Sessions history")
            expect(clear).to_be_hidden()
            first.get_by_text("Clear saved Sessions history…", exact=True).click()
            expect(clear).to_be_visible()
            expect(pager).to_contain_text("of 40 cached sessions")
            clear.click()
            expect(first.get_by_text("Saved Sessions history cleared.", exact=True)).to_be_visible()
            expect(pager).to_contain_text("No cached sessions yet")
            expect(older).to_be_visible()
            expect(second.locator(".sessions-catalog .page-navigation")).to_contain_text("No cached sessions yet")
            assert source_path.read_bytes() == b"fixture identity; intentionally not an OpenCode database"
            host.display_archive.unbind()
            expect(pager).to_contain_text("Session cache unavailable", timeout=5000)
            expect(first.locator(".sessions-catalog tbody tr")).to_have_count(0)
            evidence["cached_sessions"] = dict(first_cache_dom_ms=round(first_ms, 1), committed_rows=40,
                checked="cold empty, held source, period/sort/page, scoped spinner, field help, root-scoped detail, two-tab requery, running, confirmed clear, source unbind")
        finally:
            context.close()
            host.close()
