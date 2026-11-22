"""Own synthetic source fixture; both Watch renderers use the same SQLite publication."""
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from threading import Event
import time
from types import SimpleNamespace
from urllib.parse import urlsplit

from development.tests.fixtures.display_watch import native_account, running_frame
from development.tests.fixtures.web_reports import current_report
from src.analysis.daily_usage import DailyUsage
from src.analysis.timezones import local_day_start_ms
from src.analysis.token_mix import TokenMix
from src.analysis.valuation import ComparisonCost
from src.sources.opencode_v1 import OpenCodeV1Source
from src.web.display_archive import DisplayArchive
from src.web.host import WebHost
from src.web.jobs import ReportJobs


def mini_rows(page):
    return page.evaluate("""() => {
        if (!miniWatch?.measure?.ready) return null;
        miniWatch.measure.read(miniWatch);
        return [...miniWatch.measure.view.body.querySelectorAll('tr[data-id]')].map(row => ({
            label: row.getAttribute('aria-label'),
            metrics: [...row.cells].slice(2).map(cell => cell.textContent),
            running: row.classList.contains('mini-running')
        }));
    }""")


def mini_quota(page):
    return page.evaluate("""() => {
        if (!miniWatch?.measure?.ready) return null;
        miniWatch.measure.read(miniWatch);
        return miniWatch.measure.view.accounts.textContent;
    }""")


def check_cached_watch(browser, evidence, product_root):
    from playwright.sync_api import expect

    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "config").mkdir()
        shutil.copyfile(product_root / "config/default-config.jsonc", root / "config/default-config.jsonc")
        source_file = root / "blocked-source.db"
        source_file.write_bytes(b"identity only; no source query could succeed")
        service = SimpleNamespace(timezone_id="UTC",
            selection=SimpleNamespace(selected="v1", source=OpenCodeV1Source(source_file)))
        driver = SimpleNamespace(coordinator=SimpleNamespace(report_service=service, catalog_observation=None),
                                 terminal=False, error=None, observed_at_ms=None)
        host = WebHost(root, jobs=ReportJobs(target=current_report))
        host.cached_watch_enabled = True
        archive = DisplayArchive(root, host.events.publish, watch_enabled=True)
        host.display_archive = archive
        host.start()
        host.live = SimpleNamespace(driver=driver, stopping=Event(), close=lambda: host.display_archive.close())
        host.publish_ready()
        archive.observe(driver, before_tick=True)
        context = browser.new_context(viewport={"width": 1100, "height": 800})
        peer_context = browser.new_context(viewport={"width": 1100, "height": 800})
        try:
            origin = host.server.origin
            for isolated in (context, peer_context):
                isolated.route("**/*", lambda route: route.continue_()
                               if route.request.url.startswith(origin + "/") else route.abort())
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(host.browser_url())
            expect(page.locator("#result .overview-models")).to_be_visible(timeout=15000)
            requests = []
            page.on("request", lambda request: requests.append(urlsplit(request.url).path))

            now = int(time.time() * 1000)
            daily = DailyUsage(local_day_start_ms("UTC", now_ms=now), now,
                               ComparisonCost(Decimal("400"), observed_requests=4, priced_requests=3),
                               TokenMix(), 3, False)
            frame = replace(running_frame(now), daily_usage=daily)
            account = native_account(now)
            refresh = SimpleNamespace(snapshots=(account,), seen_ms={account.key: now})
            driver.observed_at_ms = now
            archive.publish_live(None, frame, now, account_refresh=refresh)
            archive._live_write.result(timeout=5)
            page.wait_for_function("() => watchCache?.value?.cards[0]?.title === 'Observed title'")
            page.get_by_role("link", name="Watch", exact=True).click()
            card = page.locator(".watch-active article")
            expect(card.get_by_role("link", name="Observed title")).to_be_visible()
            expect(card.get_by_text("Total CCost:", exact=True)).to_be_visible()
            expect(card.locator(".watch-session-context")).to_have_text("1k")
            expect(card.locator(".watch-activity")).to_be_visible()
            expect(card.locator("tr.watch-running")).to_have_count(1)
            expect(card.locator(".watch-prompt-number")).to_have_text("#1")
            expect(card.get_by_text("12/34/5/49", exact=True)).to_be_visible()
            expect(page.locator(".watch-daily")).to_contain_text("3 observed prompts")
            quota = page.locator(".watch-view .mini-accounts")
            expect(quota).to_contain_text("Fixture Pro · 25%")
            # Current committed observations lend, but never persist, live detail.
            expect(card).to_contain_text("private transcript sample")

            # Exercise the actual Mini renderer on the opener's prepared PiP
            # layout, with no separate native window or acquisition.
            page.evaluate("() => miniWatch?.measure?.loaded")
            peer = peer_context.new_page()
            peer.on("pageerror", lambda error: errors.append(str(error)))
            peer.goto(host.browser_url())
            peer.get_by_role("link", name="Watch", exact=True).click()
            expect(peer.locator(".watch-active article h3")).to_have_text("Observed title")
            peer_quota = peer.locator(".watch-view .mini-accounts")
            expect(peer_quota).to_contain_text("Fixture Pro · 25%")
            # Wait for the required startup/resync work before measuring local actions.
            page.wait_for_function("() => !watchCache?.dirty && !watchCache?.flight && !watchCache?.timer")
            reads = requests.count("/api/cache/watch")
            mini = mini_rows(page)
            if mini is not None:
                active, = mini
                assert active["label"].startswith("Observed title") and active["running"]
                assert active["metrics"][0] != active["metrics"][1] and active["metrics"][2] == "1k"
                assert "Fixture Pro · 25%" in mini_quota(page)
            assert requests.count("/api/cache/watch") == reads

            title = card.locator("h3 a")
            title.focus()
            later = now + 1
            updated = replace(frame, now_ms=later, active_cards=(replace(frame.active_cards[0], title="New commit"),))
            driver.observed_at_ms = later
            archive.publish_live(None, updated, later, account_refresh=refresh)
            archive._live_write.result(timeout=5)
            expect(title).to_have_text("New commit")
            expect(title).to_be_focused()
            expect(peer.locator(".watch-active article h3")).to_have_text("New commit")
            if mini is not None:
                updated_mini, = mini_rows(page)
                assert updated_mini["label"].startswith("New commit") and updated_mini["running"]

            # The provider can revoke access without a fresh prompt/source tick.
            refresh.snapshots = (replace(account, availability="error", observations={"parser_reason": "auth_failure"}),)
            archive.publish_live(None, account_refresh=refresh)
            archive._live_write.result(timeout=5)
            expect(quota).to_have_text("Subscription quota unavailable")
            expect(peer_quota).to_have_text("Subscription quota unavailable")
            if mini is not None:
                assert mini_quota(page) == "Subscription quota unavailable"
            expect(title).to_have_text("New commit")

            # Any protected read (including a simultaneous connection resync)
            # can discover auth loss first and cancel the scheduled Watch read.
            peer.bring_to_front()
            peer_context.clear_cookies()
            peer.evaluate("() => watchCache.catchUp()")
            expect(peer.locator("#host-state")).to_have_attribute("data-kind", "authorization_required")
            assert peer_context.request.get(origin + "/api/cache/watch").status == 401
            expect(peer.locator(".watch-card")).to_have_count(0)
            if mini is not None:
                assert mini_rows(peer) == []
            archive.close()
            driver.observed_at_ms = None
            host.display_archive = replacement = DisplayArchive(root, host.events.publish, watch_enabled=True)
            replacement.observe(driver, before_tick=True)
            historical = page.locator(".watch-recent article")
            expect(historical.get_by_role("link", name="New commit")).to_be_visible()
            expect(historical.get_by_text("Unverified", exact=False)).to_be_visible()
            expect(historical.get_by_text("12/34/5/49", exact=True)).to_be_visible()
            expect(page.locator(".watch-daily")).to_contain_text("3 observed prompts")
            expect(page.locator(".watch-active article")).to_have_count(0)
            expect(historical).not_to_contain_text("private transcript sample")
            expect(historical.locator(".watch-activity")).to_be_hidden()
            if mini is not None:
                retained, = mini_rows(page)
                assert retained["label"].endswith("Unverified") and not retained["running"]
            replacement.unbind()
            expect(historical).to_have_count(0)
            if mini is not None:
                assert mini_rows(page) == []
            assert "/api/cache/watch" in requests
            assert not set(requests).intersection(("/api/detail", "/api/interest", "/api/reports",
                                                   "/api/cache/session-detail/demand"))
            assert not errors, errors
            evidence["cached_watch"] = dict(
                mini_render="opener's actual Mini renderer" if mini is not None else "unavailable in this browser",
                checked="unvisited publication, common native quota and provider revocation, one read path, "
                        "two tabs, focus, auth loss, as-of restart, source unbind")
        finally:
            peer_context.close()
            context.close()
            host.close()
