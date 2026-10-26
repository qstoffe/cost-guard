"""Actual rendered Chromium against shipped HTTP/assets, synthetic report worker only."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tools.ci_web_beta import hosted_only, save
from development.tests.fixtures.web_reports import finite_report
from src.web.host import WebHost
from src.web.jobs import ReportJobs


def main():
    hosted_only()
    evidence = dict(outcome="NOT RUN", checks=[], limitations=["Chromium headless only; no screen-reader, physical input or system-browser proof"])
    owner = None
    try:
        from playwright.sync_api import sync_playwright, expect
        owner = WebHost(ROOT, jobs=ReportJobs(target=finite_report))
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
                expect(page.locator("#status")).to_contain_text("Live connected", timeout=15000)
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
                page.set_viewport_size({"width": 390, "height": 844})
                page.locator("#skip").focus()
                page.keyboard.press("Enter")
                expect(page.locator("#content")).to_be_focused()
                assert page.locator("#refresh").is_visible()
                evidence["checks"].append("narrow viewport and keyboard skip-to-content focus")
                context.set_offline(True)
                expect(page.locator("#status")).to_contain_text(re.compile("offline|reconnecting"), timeout=45000)
                expect(page.locator("#result")).to_contain_text("<script>PRIVATE_TEXT</script>")
                context.set_offline(False)
                expect(page.locator("#status")).to_contain_text("Live connected", timeout=30000)
                evidence["checks"].append("real browser network loss/reconnect retains report")
                owner.stop("menu")
                expect(page.locator("#status")).to_contain_text("host stopped", timeout=15000)
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
        traceback.print_exc()
    finally:
        if owner:
            owner.close()
            assert owner.thread is None or not owner.thread.is_alive()
    save("browser", evidence)
    return int(evidence["outcome"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
