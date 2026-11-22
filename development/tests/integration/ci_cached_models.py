"""Real browser Models interactions against a local cache and a held source."""
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from threading import Lock
import time
from types import SimpleNamespace
from urllib.parse import urlsplit

from development.tests.fixtures.web_reports import current_report
from development.tests.test_display_models import capture, model
from src.sources.opencode_v1 import OpenCodeV1Source
from src.web.display_archive import DisplayArchive
from src.web.host import WebHost
from src.web.jobs import ReportJobs


def check_cached_models(browser, evidence, product_root):
    from playwright.sync_api import expect

    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "config").mkdir()
        shutil.copyfile(product_root / "config/default-config.jsonc", root / "config/default-config.jsonc")
        identity = root / "held-source.db"
        identity.write_bytes(b"fixture identity only; source cannot be opened")
        service = SimpleNamespace(timezone_id="UTC",
            selection=SimpleNamespace(selected="v1", source=OpenCodeV1Source(identity)))
        driver = SimpleNamespace(error=None, terminal=False,
            coordinator=SimpleNamespace(report_service=service, catalog_observation=None))
        host = WebHost(root, jobs=ReportJobs(target=current_report))
        host.cached_models_enabled = True
        archive = host.display_archive = DisplayArchive(root, host.events.publish, models_enabled=True)
        host.start()
        host.publish_ready()
        archive.observe(driver, before_tick=True)
        context = browser.new_context(viewport={"width": 360, "height": 800}, reduced_motion="reduce")
        requests, errors = [], []
        try:
            origin = host.server.origin
            context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(origin + "/")
                          else route.abort())

            def new_page(url):
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda request: requests.append((urlsplit(request.url).path, request.post_data or "")))
                page.goto(url)
                return page

            page = new_page(host.browser_url())
            models = page.locator("#result .models-view")
            result = models.locator(".overview-model-table tbody")
            release = models.get_by_role("button", name="Release date", exact=False)
            cost = models.get_by_role("button", name="Relative Price List Cost", exact=False)
            reference_filters = models.locator(".model-filters").first
            all_models = reference_filters.get_by_role("checkbox", name="Show all Copilot-priced models")
            latest = reference_filters.get_by_role("checkbox", name="Latest versions only")
            expect(release).to_be_enabled()
            expect(models.get_by_text("No Models snapshot is available for this selection.")).to_be_visible()
            release.click()
            latest.uncheck()
            expect(latest).to_be_enabled()
            expect(page.locator("#result")).to_have_attribute("aria-busy", "false")

            def publish(rows, **options):
                now = int(time.time() * 1000)
                bound = archive.models.binding()
                value = capture(rows, scope=bound[0].source, observed=now, **options)
                assert archive.models.offer(bound, value, eligible=lambda: True)
                archive.next_projection(lambda: None)(now, active=lambda: True)

            data = [
                model("Selected newest", ["2"], release="2025-12-01"),
                model("Selected oldest", ["1"], release="2025-11-01", superseded=True, superseded_selectable=True),
                model("Catalog only", ["3"], selectable=False),
                *(model(f"Tied {index:02d}", ["0"], release=None) for index in range(50)),
            ]
            publish(data)
            first = result.locator("tr").first
            expect(first).to_contain_text("Selected oldest")
            expect(latest).to_be_focused()
            expect(result.locator("tr")).to_have_count(50)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

            cost.evaluate("""button => button.addEventListener('click', () => {
                const at = performance.now(), body = document.querySelector('.overview-model-table tbody');
                const observation = new MutationObserver(() => {
                    if (body.firstChild?.textContent.includes('Selected newest')) {
                        window.modelsAppliedMs = performance.now() - at; observation.disconnect();
                    }
                });
                observation.observe(body, {childList: true});
            }, {once: true})""")
            cost.click()
            expect(first).to_contain_text("Selected newest")
            applied = page.wait_for_function("window.modelsAppliedMs").json_value()
            expect(cost).to_be_focused()
            all_models.check()
            expect(first).to_contain_text("Catalog only")
            models.get_by_role("button", name="Next page: reference models").click()
            expect(result.locator("tr")).to_have_count(3)
            expect(models.get_by_text("51–53 of 53")).to_be_visible()
            latest.check()
            expect(first).to_contain_text("Catalog only")
            expect(result.get_by_text("Selected oldest")).to_have_count(0)

            peer = new_page(page.url)
            peer_result = peer.locator(".overview-model-table tbody")
            expect(peer_result.locator("tr").first).to_contain_text("Selected newest")
            assert not errors, errors
            archive.unbind()
            expect(result.locator("tr")).to_have_count(0)
            expect(peer_result.locator("tr")).to_have_count(0)
            archive.observe(driver, before_tick=True)
            expect(first).to_contain_text("Catalog only")
            expect(peer_result.locator("tr").first).to_contain_text("Selected newest")

            expected = archive.history.source_state(archive.views.source)
            assert archive.clear_confirmed(archive.views.binding, expected,
                SimpleNamespace(lock=Lock(), observation_sequence=1), service, eligible=lambda: True)
            expect(result.locator("tr")).to_have_count(0)
            expect(peer_result.locator("tr")).to_have_count(0)
            forbidden = [(path, body) for path, body in requests
                         if path in {"/api/data", "/api/reports", "/api/models/refresh"}
                         or path == "/api/interest" and '"kind":"normal"' in body]
            assert not forbidden, forbidden
            assert not errors, errors
            assert applied < 1000, applied
            evidence["cached_models_sort_applied_ms"] = round(applied, 1)
        finally:
            context.close()
            archive.close()
            host.close()
