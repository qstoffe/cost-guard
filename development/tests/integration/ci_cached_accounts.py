"""Browser reads four authenticated Accounts periods without recovering the source."""
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from threading import Lock
import time
from types import SimpleNamespace
from urllib.parse import urlsplit

from development.tests.fixtures.web_reports import current_report
from development.tests.test_display_account_history import REF, observation
from src.cache.display_history import SessionChange, SessionFact
from src.cache.display_requests import RequestRoster
from src.domain import AccountSnapshot
from src.sources.opencode_v1 import OpenCodeV1Source
from src.web.display_archive import DisplayArchive
from src.web.host import WebHost
from src.web.jobs import ReportJobs


def check_cached_accounts(browser, evidence, product_root):
    from playwright.sync_api import expect

    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "config").mkdir()
        shutil.copyfile(product_root / "config/default-config.jsonc", root / "config/default-config.jsonc")
        path = root / "unreadable-catalog"
        path.write_bytes(b"Only file identity; no source queries can succeed")
        service = SimpleNamespace(timezone_id="UTC",
            selection=SimpleNamespace(selected="v1", source=OpenCodeV1Source(path)))
        driver = SimpleNamespace(error=None, terminal=False,
            coordinator=SimpleNamespace(report_service=service, catalog_observation=None))
        host = WebHost(root, jobs=ReportJobs(target=current_report))
        host.cached_accounts_enabled = True
        archive = host.display_archive = DisplayArchive(root, host.events.publish, accounts_enabled=True)
        host.start()
        host.publish_ready()
        archive.observe(driver, before_tick=True)
        context = browser.new_context(viewport={"width": 420, "height": 800}, reduced_motion="reduce")
        seen, errors = [], []
        try:
            origin = host.server.origin
            context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(origin + "/")
                          else route.abort())
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda req: seen.append((urlsplit(req.url).path, req.post_data or "")))
            page.goto(host.browser_url())
            page.get_by_role("link", name="Accounts", exact=True).click()
            panel = page.locator(".account-timeline")
            expect(panel.get_by_text("No observed account history is cached for this period.")).to_be_visible()
            for label in ("Today", "7 days", "30 days", "This month"):
                control = panel.get_by_role("button", name=label, exact=True)
                control.click()
                expect(control).to_have_attribute("aria-pressed", "true")
                expect(control).to_be_enabled()

            now = int(time.time() * 1000)
            series = (SimpleNamespace(account=AccountSnapshot(REF, now, "OpenAI"), label="Recorded account"),)
            archive.accounts.offer(series, verified=True)
            key = archive.views.source
            request = observation(1, now - 100, costs=("25", "0", "0", "0"))
            archive.history.commit_sessions(key, (SessionChange(SessionFact("selected", "r1", "Selected"), None,
                previous_progress=0, request_roster=RequestRoster("reference", (request,), ())),))
            for _ in range(20):
                turn = archive.next_projection(lambda: None)
                if not turn:
                    break
                turn(now, active=lambda: True)
            else:
                raise AssertionError("fixture failed to commit the chart")
            expect(panel.get_by_text("Observed reference subtotal, not native quota or billing.", exact=False)).to_be_visible()
            bars = panel.locator(".account-timeline-bar")
            expect(bars).to_have_count(1)
            control = panel.get_by_role("button", name="7 days", exact=True)
            control.evaluate("""button => button.addEventListener('click', () => {
                const start = performance.now(), chart = document.querySelector('.account-timeline-plot');
                const observer = new MutationObserver(() => {
                    const bar = chart.querySelector('.account-timeline-bar');
                    const slots = chart.querySelectorAll('.account-timeline-target').length;
                    if (bar?.checkVisibility() && (slots === 7 || slots === 8)) {
                        chart.dataset.accountsAppliedMs = performance.now() - start;
                        observer.disconnect();
                    }
                });
                observer.observe(chart, {childList: true, subtree: true});
            }, {capture: true, once: true})""")
            with page.expect_response(lambda response: urlsplit(response.url).path == "/api/cache/accounts"
                    and response.request.post_data_json == {"period": "7-days"}) as response:
                control.click()
            assert response.value.ok, response.value.status
            expect(bars).to_be_visible()
            plot = panel.locator(".account-timeline-plot[data-accounts-applied-ms]")
            expect(plot).to_be_visible()
            applied = float(plot.get_attribute("data-accounts-applied-ms"))
            expect(control).to_be_focused()
            archive.unbind()
            expect(bars).to_have_count(0)
            archive.observe(driver, before_tick=True)
            archive.accounts.offer(series, verified=True)
            expect(bars).to_have_count(1)
            current = archive.history.source_state(key)
            assert archive.clear_confirmed(archive.views.binding, current,
                SimpleNamespace(lock=Lock(), observation_sequence=1), service, eligible=lambda: True)
            expect(bars).to_have_count(0)
            assert not any(path == "/api/accounts/timeline" for path, _ in seen), seen
            assert not errors, errors
            assert applied < 1000, applied
            evidence["cached_accounts_period_applied_ms"] = round(applied, 1)
        finally:
            context.close()
            archive.close()
            host.close()
