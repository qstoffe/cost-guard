"""Real browser and loopback proof for opt-in cached AI Stats subtotals."""
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from threading import Lock
import time
from types import SimpleNamespace
from urllib.parse import urlsplit

from development.tests.fixtures.session_snapshots import one_request
from development.tests.fixtures.web_reports import current_report
from development.tests.test_archive_stats_evidence import capture
from src.cache.display_history import SessionChange, SessionFact
from src.cache.display_stats_evidence import StatsInterval
from src.sources.opencode_v1 import OpenCodeV1Source
from src.web.display_archive import DisplayArchive
from src.web.host import WebHost
from src.web.jobs import ReportJobs


def check_cached_stats(browser, evidence, product_root):
    from playwright.sync_api import expect

    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "config").mkdir()
        shutil.copyfile(product_root / "config/default-config.jsonc", root / "config/default-config.jsonc")
        identity = root / "source.db"
        identity.write_bytes(b"fixture identity only; source history cannot be opened")
        service = SimpleNamespace(timezone_id="UTC",
            selection=SimpleNamespace(selected="v1", source=OpenCodeV1Source(identity)))
        driver = SimpleNamespace(error=None, terminal=False,
            coordinator=SimpleNamespace(report_service=service, catalog_observation=None))
        host = WebHost(root, jobs=ReportJobs(target=current_report))
        host.cached_stats_enabled = True
        archive = host.display_archive = DisplayArchive(root, host.events.publish, stats_enabled=True)
        host.start()
        host.publish_ready()
        archive.observe(driver, before_tick=True)
        context = browser.new_context(viewport={"width": 360, "height": 800}, reduced_motion="reduce")
        requests, errors = [], []
        try:
            origin = host.server.origin
            context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(origin + "/")
                          else route.abort())

            def new_page(seen):
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda request: seen.append((urlsplit(request.url).path, request.post_data or "")))
                return page

            page = new_page(requests)
            page.goto(host.browser_url())
            page.wait_for_function("() => statsCache !== null")
            page.get_by_role("link", name="AI Stats", exact=True).click()
            view = page.locator("#result .cached-stats")
            working = view.locator('[data-metric="working"]')
            tokens = view.locator('[data-metric="tokens"]')
            reference = view.locator('[data-metric="referenceCost"]')
            subagent = view.locator('[data-metric="subagentReferenceCost"]')
            overnight_share = view.locator('[data-metric="overnightShare"]')
            expect(view.get_by_text("No measured work is cached for this period yet."),
                   f"Page errors: {errors!r}; requests: {[path for path, _ in requests]!r}").to_be_visible()
            for label in ("Today", "7 days", "30 days", "This month", "All time"):
                button = view.get_by_role("button", name=label, exact=True)
                button.click()
                expect(button).to_have_attribute("aria-pressed", "true")
                expect(working).to_have_text("—")
                expect(tokens).to_have_text("—")
                expect(reference).to_have_text("—")
                expect(subagent).to_have_text("—")
                expect(overnight_share).to_have_text("—")
                expect(page.locator("#result")).to_have_attribute("aria-busy", "false")

            now = int(time.time() * 1000)
            base = capture(one_request(running=False))

            def publish(root_id, start, elapsed, clock, *, child=None):
                interval = StatsInterval(root_id, "prompt", "prompt", start, elapsed, False)
                request, = base.requests
                identity = replace(request.stats_identity, message_key=root_id.encode().ljust(32, b"-"))
                observed = replace(request, key=root_id.encode(), clock_ms=start + elapsed, session_id=child or root_id,
                                   dedup_tree=root_id, fork_key=None, stats_identity=identity, response=None,
                                   tokens=(10, 20, 30, 5, 2), known=0b1111,
                                   category_costs=(Decimal(10), Decimal(20), Decimal(5), Decimal(15)))
                parents = ((root_id, None),) + (((child, root_id),) if child else ())
                roster = replace(base, requests=(observed,), attribution=(), prompts=None,
                    stats=replace(base.stats, intervals=(interval,), parents=parents, first_input=None))
                archive.history.commit_sessions(archive.views.source, (SessionChange(
                    SessionFact(root_id, "r1", root_id), None, previous_progress=0, request_roster=roster),))
                archive.close_catalog_work()
                for _ in range(50):
                    archive.stats.advance(clock, active=lambda: True)
                    if not archive.stats.pending():
                        return
                raise AssertionError("fixture failed to commit measured time")

            midnight = now // 86_400_000 * 86_400_000
            publish("recent", midnight - 12 * 3_600_000, 60_000, now, child="recent-child")
            expect(working).to_have_text("1m")
            expect(tokens).to_have_text("67")
            expect(reference).to_have_text("$0.50")
            expect(subagent).to_have_text("$0.50")
            view.evaluate("root => ReportView.setUnit('credits', root)")
            expect(reference).to_have_text("50")
            expect(subagent).to_have_text("50")
            expect(view.locator('[data-metric="longest"]')).to_have_text("1m")
            expect(view.locator('[data-metric="parallel"]')).to_have_text("1")
            expect(overnight_share).to_have_text("0%")
            expect(view.get_by_role("button", name="All time", exact=True)).to_be_focused()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

            peer_requests = []
            peer = new_page(peer_requests)
            peer.goto(page.url)
            peer_view = peer.locator("#result .cached-stats")
            peer_view.get_by_role("button", name="7 days", exact=True).click()
            peer_working = peer_view.locator('[data-metric="working"]')
            peer_tokens = peer_view.locator('[data-metric="tokens"]')
            expect(peer_working).to_have_text("1m")
            expect(peer_tokens).to_have_text("67")
            peer.wait_for_function("() => statsCache.hint?.marks?.['7-days'] && !statsCache.flight")
            peer_reads = sum(path == "/api/cache/ai-stats" for path, _ in peer_requests)

            publish("aged", midnight - 60 * 86_400_000 + 3 * 3_600_000, 120_000, now + 1)
            expect(working).to_have_text("3m")
            expect(tokens).to_have_text("134")
            expect(reference).to_have_text("100")
            expect(subagent).to_have_text("50")
            expect(overnight_share).to_have_text("67%")
            peer.wait_for_function("(clock) => statsCache.hint?.marks?.all?.[1] === clock", arg=now + 1)
            expect(peer_working).to_have_text("1m")
            expect(peer_tokens).to_have_text("67")
            expect(peer_view.locator('[data-metric="overnightShare"]')).to_have_text("0%")
            assert sum(path == "/api/cache/ai-stats" for path, _ in peer_requests) == peer_reads

            period = view.get_by_role("button", name="7 days", exact=True)
            period.evaluate("""button => button.addEventListener('click', () => {
                const at = performance.now(), node = document.querySelector('[data-metric="working"]');
                const observer = new MutationObserver(() => {
                    if (node.textContent === '1m') { window.statsAppliedMs = performance.now() - at; observer.disconnect(); }
                });
                observer.observe(node, {childList: true, characterData: true, subtree: true});
            }, {once: true})""")
            period.click()
            expect(working).to_have_text("1m")
            expect(overnight_share).to_have_text("0%")
            applied = page.wait_for_function("window.statsAppliedMs").json_value()
            expect(period).to_be_focused()

            archive.unbind()
            expect(working).to_have_text("—")
            expect(peer_working).to_have_text("—")
            expect(tokens).to_have_text("—")
            expect(reference).to_have_text("—")
            expect(subagent).to_have_text("—")
            expect(overnight_share).to_have_text("—")
            archive.observe(driver, before_tick=True)
            expect(working).to_have_text("1m")
            expect(peer_working).to_have_text("1m")
            expect(tokens).to_have_text("67")
            expect(period).to_be_focused()

            state = archive.history.source_state(archive.views.source)
            assert archive.clear_confirmed(archive.views.binding, state, SimpleNamespace(lock=Lock(), observation_sequence=1),
                                           service, eligible=lambda: True)
            expect(working).to_have_text("—")
            expect(peer_working).to_have_text("—")
            expect(tokens).to_have_text("—")

            legacy = [(path, body) for path, body in requests + peer_requests
                      if path in {"/api/data", "/api/interest", "/api/reports"} and '"kind":"ai-stats"' in body]
            assert not legacy, legacy
            assert not errors, errors
            assert applied < 1000, applied
            evidence["cached_stats_period_applied_ms"] = round(applied, 1)
        finally:
            context.close()
            archive.close_catalog_work()
            archive.close()
            host.close()
