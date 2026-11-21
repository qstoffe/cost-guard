"""Browser proof for the opt-in SQLite-only Token Mix period route."""
from dataclasses import replace
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
from threading import Lock
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
            models = view.get_by_role("region", name="Cached Token Mix by model")
            model_table = models.locator("..")
            tokens = models.get_by_role("button", name="Tokens")
            rows = models.locator("tbody tr")
            tokens.click()
            expect(models.get_by_role("columnheader", name="Tokens")).to_have_attribute("aria-sort", "ascending")
            expect(rows).to_have_count(0)

            now = int(time.time() * 1000)
            snapshot = make_snapshot()
            reference = SimpleNamespace(analysis_signature="fixture", reference_category_valuation=lambda *_: None)
            roster = request_roster(snapshot, analyze_snapshot(snapshot, now_ms=10_000), reference)
            entry = replace(roster.requests[0], clock_ms=now, fork_key=None, dedup_tree=None, category_costs=None)

            def model(index, name, tokens, *, clock=now, known=0b1111):
                return replace(entry, key=index.to_bytes(2, "big"), model=name, recorded_model=name,
                               clock_ms=clock, tokens=tokens, known=known)

            def publish(root_id, entries, clock):
                archive.history.commit_sessions(archive.views.source, (SessionChange(
                    SessionFact(root_id, "r1", root_id), None, previous_progress=0,
                    request_roster=replace(roster, requests=entries, attribution=(), prompts=None)),))
                archive.close_catalog_work()  # Re-arm the synchronous fixture's catalog lane.
                for _ in range(16):
                    archive.advance_mix(clock, active=lambda: True)
                    if not archive.mix_pending():
                        break

            publish("root", tuple(model(i, f"fixture-{i:02}", (20 + i, 10, 0, 10, 0)) for i in range(52)) +
                    (model(52, "fixture-unknown", (0,) * 5, known=0),), now)
            summary = view.get_by_role("heading", name=re.compile(r"^Cached Token Mix · .+ tokens$"))
            expect(summary).to_be_visible()
            expect(rows).to_have_count(25)
            expect(rows.first.get_by_role("cell", name="fixture-00", exact=True)).to_be_visible()
            expect(view.get_by_role("region", name="Cached Token Mix by publisher").locator("tbody")).to_contain_text(
                "Unknown / unverified")

            next_page = model_table.get_by_role("button", name="Next", exact=True)
            prev_page = model_table.get_by_role("button", name="Previous", exact=True)
            next_page.click()
            expect(rows.first.get_by_role("cell", name="fixture-25", exact=True)).to_be_visible()
            expect(next_page).to_be_focused()
            next_page.click()
            expect(rows).to_have_count(3)
            expect(rows.last.get_by_role("cell", name="fixture-unknown", exact=True)).to_be_visible()
            expect(next_page).to_have_attribute("aria-disabled", "true")
            prev_page.click()
            expect(rows.first.get_by_role("cell", name="fixture-25", exact=True)).to_be_visible()

            peer = context.new_page()
            peer_requests = []
            peer.on("pageerror", lambda error: errors.append(str(error)))
            peer.on("request", lambda request: peer_requests.append(
                (urlsplit(request.url).path, request.post_data or "")))
            peer.goto(page.url)
            peer_view = peer.locator("#result .token-mix-view")
            peer_view.get_by_role("button", name="Today", exact=True).click()
            peer_rows = peer_view.get_by_role("region", name="Cached Token Mix by model").locator("tbody tr")
            expect(peer_rows).to_have_count(25)
            peer.wait_for_function("() => mixCache.hint?.marks?.today && !mixCache.flight")
            peer_reads = [path for path, _ in peer_requests if path.startswith("/api/cache/token-mix")]

            aged = now - 45 * 86_400_000
            publish("extra", (model(53, "fixture-added", (48, 10, 0, 10, 0), clock=aged),), now + 1)
            expect(rows.get_by_role("cell", name="fixture-added", exact=True)).to_be_visible()
            expect(rows.first.get_by_role("cell", name="fixture-25", exact=True)).to_be_visible()
            expect(prev_page).to_be_focused()
            peer.wait_for_function("(clock) => mixCache.hint?.end_ms === clock", arg=now + 1)
            expect(peer_rows.get_by_role("cell", name="fixture-added", exact=True)).to_have_count(0)
            assert [path for path, _ in peer_requests if path.startswith("/api/cache/token-mix")] == peer_reads, peer_requests

            tokens.click()
            expect(models.get_by_role("columnheader", name="Tokens")).to_have_attribute("aria-sort", "descending")
            expect(rows.first.get_by_role("cell", name="fixture-51", exact=True)).to_be_visible()
            expect(tokens).to_be_focused()
            today = view.get_by_role("button", name="Today", exact=True)
            today.evaluate("""button => button.addEventListener('click', () => {
                const start = performance.now();
                const body = document.querySelector('[aria-label="Cached Token Mix by model"] tbody');
                const observer = new MutationObserver(() => {
                    if (body.rows[0]?.cells[1].textContent === 'fixture-51') {
                        window.cachedMixApplied = performance.now() - start;
                        observer.disconnect();
                    }
                });
                observer.observe(body, {childList: true, subtree: true});
            }, {once: true})""")
            today.click()
            expect(rows.first.get_by_role("cell", name="fixture-51", exact=True)).to_be_visible()
            applied_ms = page.wait_for_function("window.cachedMixApplied").json_value()
            expect(today).to_be_focused()
            archive.unbind()
            expect(summary).to_be_hidden()
            expect(rows).to_have_count(0)
            expect(peer_rows).to_have_count(0)
            archive.observe(driver, before_tick=True)
            expect(rows.first.get_by_role("cell", name="fixture-51", exact=True)).to_be_visible()
            expect(peer_rows).to_have_count(25)
            expect(today).to_be_focused()

            binding, source = archive.views.binding, archive.views.source
            state = archive.history.source_state(source)
            catalog = SimpleNamespace(lock=Lock(), observation_sequence=1)
            assert archive.clear_confirmed(binding, state, catalog, service, eligible=lambda: True)
            expect(rows).to_have_count(0)
            expect(peer_rows).to_have_count(0)
            expect(summary).to_be_hidden()

            assert not errors, errors
            legacy = [(path, body) for path, body in requests + peer_requests
                      if path in {"/api/reports", "/api/data", "/api/interest"} and '"kind":"token-mix"' in body]
            assert not legacy, legacy
            assert applied_ms < 1000, applied_ms
            evidence["cached_mix_period_applied_ms"] = round(applied_ms, 1)
        finally:
            context.close()
            archive.close_catalog_work()
            archive.close()
            host.close()
