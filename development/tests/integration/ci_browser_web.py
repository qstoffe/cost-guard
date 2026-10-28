"""Actual rendered Chromium against shipped HTTP/assets, synthetic report worker only."""
from pathlib import Path
import re
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tools.ci_web_beta import hosted_only, save
from development.tests.fixtures.web_reports import finite_report
from src.web.host import WebHost
from src.web.jobs import ReportJobs
from src.web.http import RequestHandler


def main():
    hosted_only()
    evidence = dict(outcome="NOT RUN", checks=[], limitations=["Chromium headless only; no screen-reader, physical input or system-browser proof"])
    owner = None
    streams = []
    original_stream = RequestHandler.stream_events

    def record_stream(handler):
        streams.append(handler.connection)
        return original_stream(handler)

    stream_patch = patch.object(RequestHandler, "stream_events", record_stream)
    try:
        from playwright.sync_api import sync_playwright, expect
        owner = WebHost(ROOT, jobs=ReportJobs(target=finite_report))
        stream_patch.start()
        owner.start()
        owner.publish_ready()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                evidence["browser_version"] = browser.version
                context = browser.new_context(viewport={"width": 1100, "height": 800})
                origin = owner.server.origin
                context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(origin + "/") else route.abort())
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(type(error).__name__))
                page.goto(owner.browser_url())
                expect(page.locator("#notice")).to_contain_text("Snapshot captured", timeout=30000)
                assert "bootstrap" not in page.url
                assert any(cookie["httpOnly"] for cookie in context.cookies())
                assert page.locator("#result table").count() > 0
                # This finite-report fixture has no live acquisition owner. An
                # authenticated SSE socket must not claim source readiness.
                expect(page.locator("#status")).to_have_text("Connection: starting. See notice below.", timeout=15000)
                assert streams, "authenticated real SSE connection was not established"
                expect(page.locator("#host-state")).to_contain_text("source observation pending")
                evidence["checks"].append("one-use bootstrap, HttpOnly auth cookie, actual report table, real SSE connection")
                page.get_by_role("link", name="Models", exact=True).click()
                expect(page.locator("#heading")).to_contain_text("Models")
                page.get_by_role("link", name="Accounts", exact=True).click()
                expect(page.locator("#heading")).to_contain_text("Accounts")
                page.go_back()
                expect(page.locator("#heading")).to_contain_text("Models")
                page.go_forward()
                expect(page.locator("#heading")).to_contain_text("Accounts")
                evidence["checks"].append("rendered navigation and browser Back/Forward")
                page.goto(origin + "/#/sessions/root")
                expect(page.locator("#notice")).to_contain_text("Snapshot captured", timeout=30000)
                expect(page.locator("#result")).to_contain_text("<script>PRIVATE_TEXT</script>")
                assert page.locator("#result script").count() == 0
                assert page.locator("#result table tbody tr").count() > 0
                evidence["checks"].append("canonical session detail table; hostile title remains literal text")
                page.set_viewport_size({"width": 360, "height": 844})
                page.locator("#skip").focus()
                page.keyboard.press("Enter")
                expect(page.locator("#content")).to_be_focused()
                assert page.locator("#refresh").is_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                assert page.locator("th").first.evaluate("el => getComputedStyle(el).position") == "sticky"
                page.emulate_media(color_scheme="dark", reduced_motion="reduce")
                assert page.locator("html").evaluate("el => getComputedStyle(el).getPropertyValue('--bg').trim()") == "#0c1422"
                assert page.locator("#refresh").evaluate("el => getComputedStyle(el).transitionDuration") == "0s"
                page.locator("#search").focus()
                assert page.locator("#search").evaluate("el => getComputedStyle(el).outlineStyle") != "none"
                page.emulate_media(color_scheme="light", reduced_motion="no-preference")
                evidence["checks"].append("360px no page overflow, keyboard focus, sticky headings, dark theme and reduced motion")
                owner.events.publish("live", {"state": "CI synthetic Live observation"})
                page.get_by_role("link", name="Watch", exact=True).click()
                expect(page.locator("#result")).to_contain_text("CI synthetic Live observation", timeout=15000)
                assert page.url.endswith("/#/watch")
                page.goto(origin + "/#/live")
                expect(page.locator("#heading")).to_have_text("Watch")
                assert page.url.endswith("/#/watch")
                page.reload()
                expect(page.locator("#heading")).to_have_text("Watch")
                page.get_by_role("link", name="Models", exact=True).click()
                page.go_back()
                expect(page.locator("#heading")).to_have_text("Watch")
                page.go_forward()
                expect(page.locator("#heading")).to_contain_text("Models")
                page.go_back()
                page.go_back()
                page.go_back()
                expect(page.locator("#result")).to_contain_text("<script>PRIVATE_TEXT</script>")
                evidence["checks"].append("rendered Live state from actual synthetic SSE publication")
                context.set_offline(True)
                # Browser offline emulation does not necessarily drop an already
                # open SSE TCP socket. Inject actual loss of our owned connection.
                for connection in tuple(streams):
                    try:
                        connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                expect(page.locator("#status")).to_contain_text(re.compile("offline|reconnecting"), timeout=45000)
                expect(page.locator("#result")).to_contain_text("<script>PRIVATE_TEXT</script>")
                context.set_offline(False)
                expect(page.locator("#status")).to_have_text("Connection: source unavailable. See notice below.", timeout=30000)
                expect(page.locator("#host-message")).to_contain_text("SOURCE UNAVAILABLE")
                expect(page.locator("#host-state")).to_contain_text("HTTP connected")
                evidence["checks"].append("real browser network loss/reconnect retains report")
                owner.stop("menu")
                expect(page.locator("#status")).to_have_text("Connection: stopped. See notice below.", timeout=15000)
                expect(page.locator("#host-message")).to_contain_text("host stopped")
                expect(page.locator("#host-state")).to_be_visible()
                assert page.locator("#refresh").is_disabled()
                assert owner.stopped.wait(10)
                assert not errors
                evidence["checks"].append("terminal SSE and clean owned server shutdown; no JavaScript errors")
            finally:
                browser.close()
        evidence["outcome"] = "PASS"
    except ImportError:
        evidence.update(outcome="BLOCKED", reason="CI-only Playwright/Chromium provisioning unavailable")
    except Exception as error:
        evidence.update(outcome="FAIL", reason=type(error).__name__)
        import traceback
        evidence["failure_locations"] = [dict(file=Path(frame.filename).name, line=frame.lineno, function=frame.name)
                                         for frame in traceback.extract_tb(error.__traceback__)]
        # Playwright exception text can contain a one-use bootstrap URL.
        # Retain only source locations and type, never its raw call log.
    finally:
        stream_patch.stop()
        if owner:
            owner.close()
            assert owner.thread is None or not owner.thread.is_alive()
    save("browser", evidence)
    return int(evidence["outcome"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
