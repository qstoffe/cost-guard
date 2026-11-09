"""Actual rendered Chromium against shipped HTTP/assets, synthetic report worker only."""
from pathlib import Path
import json
import re
import shutil
import socket
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tools.ci_web_beta import hosted_only, save
from development.tests.fixtures.web_reports import current_report, SyntheticSessionsRuntime
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
    temporary = tempfile.TemporaryDirectory()
    try:
        from playwright.sync_api import sync_playwright, expect
        config_root = Path(temporary.name).resolve()
        (config_root / "config").mkdir()
        shutil.copyfile(ROOT / "config/default-config.jsonc", config_root / "config/default-config.jsonc")
        user_config = config_root / "config/user-config.jsonc"
        owner = WebHost(config_root, jobs=ReportJobs(target=current_report))
        owner.live = SyntheticSessionsRuntime(config_root, clock_ms=lambda: int(time.time() * 1000))
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
                # Observe actual stream readiness without changing its behavior.
                # HTTP /api/live recovery alone does not prove SSE reconnection.
                page.add_init_script('''
                    window.ciEventStreams = [];
                    const NativeEventSource = window.EventSource;
                    window.EventSource = class extends NativeEventSource {
                        constructor(...args) {
                            super(...args);
                            window.ciEventStreams.push(this);
                        }
                    };
                ''')
                errors = []
                page.on("pageerror", lambda error: errors.append(type(error).__name__))
                page.goto(owner.browser_url())
                expect(page.locator("#result .overview-models")).to_be_visible(timeout=30000)
                assert "bootstrap" not in page.url
                assert any(cookie["httpOnly"] for cookie in context.cookies())
                assert page.locator("#result table").count() > 0
                # Synthetic Sessions acquisition publishes no Watch observation.
                # An authenticated SSE socket must not claim source readiness.
                expect(page.locator("#status")).to_have_text("Connection: starting. See notice below.", timeout=15000)
                assert streams, "authenticated real SSE connection was not established"
                expect(page.locator("#host-state")).to_be_hidden()
                expect(page.locator("#host-state")).to_have_text("")
                evidence["checks"].append("one-use bootstrap, HttpOnly auth cookie, actual report table, real SSE connection")
                assert page.url.endswith('/#/models')
                assert page.get_by_role("link", name="Models", exact=True).count() == 1
                for legacy in ('overview', 'models/all'):
                    page.goto(origin + '/#/' + legacy)
                    expect(page.locator("#heading")).to_have_text("Models")
                    expect(page).to_have_url(re.compile(r'/#/models$'))
                    expect(page.locator('#content')).to_be_focused()
                    expect(page.get_by_role("link", name="Models", exact=True)).to_have_attribute('aria-current', 'page')
                expect(page.locator("#heading")).to_contain_text("Models")
                page.get_by_role("link", name="Accounts", exact=True).click()
                expect(page.locator("#heading")).to_contain_text("Accounts")
                page.go_back()
                expect(page.locator("#heading")).to_contain_text("Models")
                page.go_forward()
                expect(page.locator("#heading")).to_contain_text("Accounts")
                evidence["checks"].append("rendered navigation and browser Back/Forward")
                page.goto(origin + "/#/sessions/root")
                expect(page.locator("#result tbody tr").first).to_be_visible(timeout=30000)
                expect(page.locator("#result")).to_contain_text("<script>PRIVATE_TEXT</script>")
                assert page.locator("#result script").count() == 0
                assert page.locator("#result table tbody tr").count() > 0
                assert page.locator("#result th").all_text_contents() == [
                    "Prompt", "Model", "Effort", "CCost", "Calls", "Duration", "Ictx", "Ictx CCost", "Extra CCost", "Token Mix %"]
                assert page.locator("#result tfoot td").count() == 10
                expect(page.locator("#result")).to_contain_text("Session ID: root")
                assert not page.locator(".toolbar").is_visible()
                evidence["checks"].append("live complete ten-column session history and canonical footer; hostile title remains literal text")
                page.set_viewport_size({"width": 360, "height": 844})
                page.locator("#skip").focus()
                page.keyboard.press("Enter")
                expect(page.locator("#content")).to_be_focused()
                assert not page.locator("#refresh").is_visible()
                evidence["narrow_layout"] = page.evaluate('''() => {
                    const heading=document.querySelector('#result h1'), pan=document.querySelector('.sessions-table-pan');
                    return {viewport:innerWidth,page_width:document.documentElement.scrollWidth,
                        heading_width:heading.clientWidth,heading_scroll:heading.scrollWidth,
                        pan_width:pan.clientWidth,table_width:pan.scrollWidth};
                }''')
                assert evidence["narrow_layout"]["page_width"] <= evidence["narrow_layout"]["viewport"]
                assert evidence["narrow_layout"]["heading_scroll"] <= evidence["narrow_layout"]["heading_width"]
                assert page.locator("th").first.evaluate("el => getComputedStyle(el).position") == "sticky"
                page.emulate_media(color_scheme="dark", reduced_motion="reduce")
                expect(page.locator("html")).to_have_attribute("data-theme", "classic")
                assert page.locator("html").evaluate("el => getComputedStyle(el).getPropertyValue('--bg').trim()") == "#101112"
                assert page.locator("#refresh").evaluate("el => getComputedStyle(el).transitionDuration") == "0s"
                help_button = page.locator("#result th button").first
                help_button.focus()
                assert help_button.evaluate("el => getComputedStyle(el).outlineStyle") != "none"
                page.emulate_media(color_scheme="light", reduced_motion="no-preference")
                assert page.locator("html").evaluate("el => getComputedStyle(el).getPropertyValue('--bg').trim()") == "#101112"
                assert not user_config.exists(), "theme reads must not create configuration"
                evidence["checks"].append("360px no page overflow, keyboard focus, sticky headings, Classic dark in both preferences and reduced motion")
                report_requests = []
                page.on("request", lambda request: report_requests.append(request.url) if request.url.endswith('/api/reports') else None)
                page.get_by_role("link", name="Settings", exact=True).click()
                expect(page.locator("#heading")).to_have_text("Settings")
                theme = page.get_by_role("combobox", name="Theme", exact=True)
                expect(theme).to_be_enabled()
                expect(theme).to_have_value("default")
                assert theme.locator("option").evaluate_all("items => items.map(item => item.getAttribute('aria-label') || item.label)") == ["Default (Classic)", "Classic", "Web"]
                theme.select_option("web")
                expect(page.locator("#settings-feedback")).to_have_text("Theme saved.")
                expect(page.locator("html")).to_have_attribute("data-theme", "web")
                assert json.loads(user_config.read_text()) == {"webSettings": {"theme": "web"}}
                ccost = page.get_by_role("combobox", name="CCost display", exact=True)
                expect(ccost).to_have_value("default")
                assert ccost.locator("option").evaluate_all("items => items.map(item => item.getAttribute('aria-label') || item.label)") == ["Default (USD)", "Credits", "USD"]
                for choice in ("credits", "default"):
                    ccost.select_option(choice)
                    expect(page.locator("#settings-feedback")).to_have_text("CCost display saved.")
                    expect(ccost).to_have_value(choice)
                    assert json.loads(user_config.read_text()) == {"webSettings": {"theme": "web", "ccostDisplayUnit": choice}}
                ccost.select_option("usd")
                expect(page.locator("#settings-feedback")).to_have_text("CCost display saved.")
                assert json.loads(user_config.read_text()) == {"webSettings": {"theme": "web", "ccostDisplayUnit": "usd"}}
                placement = page.get_by_role("combobox", name="Mini Watch position", exact=True)
                expect(placement).to_have_value("default")
                assert page.locator(".web-settings select").count() == 5
                assert placement.locator("option").evaluate_all("items => items.map(item => item.getAttribute('aria-label') || item.label)") == ["Default (Remember last)", "Remember last", "Standard position"]
                size = page.get_by_role("combobox", name="Mini Watch size", exact=True)
                expect(size).to_have_value("default")
                assert size.locator("option").evaluate_all("items => items.map(item => item.getAttribute('aria-label') || item.label)") == ["Default (Fit on open)", "Fit on open", "Remember last size"]
                placement.select_option("remember-last")
                expect(page.locator("#settings-feedback")).to_have_text("Mini Watch position saved.")
                expect(placement).to_have_value("remember-last")
                quota = page.get_by_role("combobox", name="Quota display", exact=True)
                expect(quota).to_have_value("default")
                assert quota.locator("option").evaluate_all("items => items.map(item => item.getAttribute('aria-label') || item.label)") == ["Default (Used)", "Used", "Remaining"]
                quota.select_option("remaining")
                expect(page.locator("#settings-feedback")).to_have_text("Quota display saved.")
                assert page.locator("html").evaluate("el => getComputedStyle(el).getPropertyValue('--bg').trim()") == "#eef2f8"
                page.emulate_media(color_scheme="dark")
                assert page.locator("html").evaluate("el => getComputedStyle(el).getPropertyValue('--bg').trim()") == "#0c1422"
                page.reload()
                expect(page.get_by_role("combobox", name="Theme", exact=True)).to_have_value("web")
                expect(page.get_by_role("combobox", name="CCost display", exact=True)).to_have_value("usd")
                expect(page.get_by_role("combobox", name="Mini Watch position", exact=True)).to_have_value("remember-last")
                expect(page.get_by_role("combobox", name="Quota display", exact=True)).to_have_value("remaining")
                page.get_by_role("combobox", name="Mini Watch position", exact=True).select_option("default")
                expect(page.locator("#settings-feedback")).to_have_text("Mini Watch position saved.")
                expect(page.locator("html")).to_have_attribute("data-theme", "web")
                fresh = context.new_page()
                try:
                    fresh.goto(origin + '/#/settings')
                    expect(fresh.get_by_role("combobox", name="Theme", exact=True)).to_have_value("web")
                    expect(fresh.get_by_role("combobox", name="CCost display", exact=True)).to_have_value("usd")
                    expect(fresh.get_by_role("combobox", name="Mini Watch position", exact=True)).to_have_value("default")
                    expect(fresh.get_by_role("combobox", name="Quota display", exact=True)).to_have_value("remaining")
                    expect(fresh.locator("html")).to_have_attribute("data-theme", "web")
                finally:
                    fresh.close()
                page.get_by_role("combobox", name="Theme", exact=True).select_option("classic")
                expect(page.locator("#settings-feedback")).to_have_text("Theme saved.")
                expect(page.locator("html")).to_have_attribute("data-theme", "classic")
                page.get_by_role("combobox", name="Quota display", exact=True).select_option("default")
                expect(page.locator("#settings-feedback")).to_have_text("Quota display saved.")
                assert json.loads(user_config.read_text()) == {"webSettings": {"theme": "classic", "ccostDisplayUnit": "usd", "miniWatchPlacement": "default", "quotaDisplayMode": "default"}}
                assert not report_requests, "Settings must not acquire reports"
                page.go_back()
                # Settings reload discarded process-local view state. Reopening
                # a live lease can await the next 5s poll, just like first entry;
                # Playwright's default 5s assertion would race that valid cadence.
                expect(page.locator("#result")).to_contain_text("<script>PRIVATE_TEXT</script>", timeout=30000)
                page.emulate_media(color_scheme="light")
                evidence["checks"].append("actual Settings saves in disposable canonical config, Classic/Web round trip, adaptive Web, reload/new tab and no Settings report acquisition")
                owner.events.publish("live", {"state": "CI synthetic Live observation"})
                page.get_by_role("link", name="Watch", exact=True).click()
                page.wait_for_function("() => liveValue?.state === 'CI synthetic Live observation'", timeout=15000)
                expect(page.locator("#host-message")).to_contain_text("SOURCE UNAVAILABLE")
                expect(page.locator("#result")).to_have_text("")
                page.evaluate("""() => {const now=Date.now; try {
                    Date.now=()=>now()+180000; show(current);
                } finally {Date.now=now;}}""")
                expect(page.locator("#result")).to_have_text("")
                expect(page.locator("#host-message")).to_contain_text("SOURCE UNAVAILABLE")
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
                expect(page.locator("#result")).to_contain_text("<script>PRIVATE_TEXT</script>", timeout=30000)
                evidence["checks"].append("actual synthetic SSE updates source health; initial Watch stays quiet even after three virtual minutes")
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
                # Do not shut down the fixture in the gap between the successful
                # HTTP health probe and EventSource's asynchronous retry. A dead
                # server cannot deliver a terminal event to a disconnected tab.
                page.wait_for_function('() => ciEventStreams.some(stream => stream.readyState === EventSource.OPEN)', timeout=30000)
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
        temporary.cleanup()
    save("browser", evidence)
    return int(evidence["outcome"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
