"""Browser proof for the opt-in SQLite-only Token Mix period route."""
from dataclasses import replace
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import time
from types import SimpleNamespace
from urllib.parse import urlsplit

from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.web_reports import current_report
from src.analysis import analyze_snapshot
from src.application.request_archive_projection import request_roster
from src.cache.display_history import SessionChange, SessionFact
from src.sources.opencode_v1 import OpenCodeV1Source
from src.web.display_archive import DisplayArchive
from src.web.host import WebHost
from src.web.jobs import ReportJobs


def check_cached_mix(browser, evidence, product_root):
    from playwright.sync_api import expect

    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "config").mkdir()
        shutil.copyfile(product_root / "config/default-config.jsonc", root / "config/default-config.jsonc")
        identity = root / "source.db"
        identity.write_bytes(b"not a readable OpenCode database")
        service = SimpleNamespace(timezone_id="UTC",
            selection=SimpleNamespace(selected="v1", source=OpenCodeV1Source(identity)))
        driver = SimpleNamespace(error=None, terminal=False,
            coordinator=SimpleNamespace(report_service=service, catalog_observation=None))
        host = WebHost(root, jobs=ReportJobs(target=current_report))
        host.cached_mix_enabled = True
        archive = host.display_archive = DisplayArchive(root, host.events.publish, mix_enabled=True, mix_groups=True)
        host.start()
        host.publish_ready()
        archive.observe(driver, before_tick=True)
        context = browser.new_context()
        requests, errors = [], []
        try:
            origin = host.server.origin
            context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(origin + "/")
                          else route.abort())
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: requests.append((urlsplit(request.url).path, request.post_data or "")))
            page.goto(host.browser_url())
            page.wait_for_function("() => mixCache !== null")
            page.get_by_role("link", name="Token Mix", exact=True).click()
            view = page.locator("#result .token-mix-view")
            expect(view.get_by_text("No cached usage yet.")).to_be_visible()
            for label in ("Today", "7 days", "30 days", "This month", "All time"):
                button = view.get_by_role("button", name=label, exact=True)
                button.click()
                expect(button).to_have_attribute("aria-pressed", "true")

            now = int(time.time() * 1000)
            snapshot = make_snapshot()
            reference = SimpleNamespace(analysis_signature="fixture", reference_category_valuation=lambda *_: None)
            roster = request_roster(snapshot, analyze_snapshot(snapshot, now_ms=10_000), reference)
            entry = replace(roster.requests[0], clock_ms=now, fork_key=None, tokens=(20, 10, 0, 10, 0),
                            known=0b1111, category_costs=None)
            archive.history.commit_sessions(archive.views.source, (SessionChange(SessionFact("root", "r1", "Root"),
                None, previous_progress=0, request_roster=replace(roster, requests=(entry,), attribution=())),))
            for _ in range(3):
                archive.advance_mix(now, active=lambda: True)
            expect(view.get_by_role("heading", name="Cached Token Mix · 40 tokens")).to_be_visible()
            expect(view.get_by_role("region", name="Cached Token Mix by model").locator("tbody tr")).to_have_count(1)
            expect(view.get_by_role("region", name="Cached Token Mix by publisher").locator("tbody")).to_contain_text(
                "Unknown / unverified")

            today = view.get_by_role("button", name="Today", exact=True)
            start = time.perf_counter()
            today.click()
            expect(view.get_by_role("heading", name="Cached Token Mix · 40 tokens")).to_be_visible()
            applied_ms = (time.perf_counter() - start) * 1000
            expect(today).to_be_focused()
            archive.unbind()
            expect(view.get_by_role("heading")).to_be_hidden()
            archive.observe(driver, before_tick=True)
            expect(view.get_by_role("heading", name="Cached Token Mix · 40 tokens")).to_be_visible()
            expect(today).to_be_focused()

            assert not errors, errors
            assert not [(path, body) for path, body in requests if path in {"/api/reports", "/api/data", "/api/interest"}
                        and '"kind":"token-mix"' in body], requests
            assert applied_ms < 1000, applied_ms
            evidence["cached_mix_period_applied_ms"] = round(applied_ms, 1)
        finally:
            context.close()
            archive.close_catalog_work()
            archive.close()
            host.close()
