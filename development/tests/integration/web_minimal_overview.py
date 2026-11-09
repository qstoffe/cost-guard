"""Headless Models loading acceptance over real Normal work and bounded lifecycle fixtures.

Uses provisioned Playwright/Chromium with no personal profile, providers or history.
The legacy filename is retained; Models now owns the former Overview route.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from threading import Event
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.models_progress import models_progress_report
from development.tests.fixtures.scroll_views import ScrollData, ScrollJobs
from src.web.host import WebHost
from src.web.jobs import ReportJobs


class OverviewJobs(ScrollJobs):
    def __init__(self, data):
        super().__init__(data)
        self.mode = "hold"
        self.phase = dict(phase="catalog", completed=2, total=10)

    def snapshot(self, key):
        if self.mode == "hold":
            return dict(status="running", progress=self.phase)
        if self.mode in ("failed", "report_timeout", "cancelled"):
            return dict(status="failed", error=self.mode)
        result = deepcopy(super().snapshot(key))
        if self.mode == "partial":
            result["result"]["source"]["status"] = "partial"
        return result


def fixture_host(jobs, data=None):
    host = WebHost(ROOT, jobs=jobs)
    host.live = SimpleNamespace(start=lambda: None, close=lambda: None, stopping=Event())
    host.start()
    host.publish_ready()
    if data is not None:
        host.events.publish("live", data.live)
    return host


def browser_page(browser, host, *, width=1280):
    context = browser.new_context(viewport=dict(width=width, height=900), reduced_motion="reduce")
    context.route("**/*", lambda route: route.continue_()
                  if route.request.url.startswith(host.server.origin + "/") else route.abort())
    page = context.new_page()
    page.add_init_script("""window.loadingSamples=[]; window.loadingRoots=new Set();
      new MutationObserver(() => {
        const root=document.querySelector('.report-loading'), bar=root?.querySelector('progress');
        if(bar) { loadingRoots.add(root); const sample={value:bar.value,text:root.textContent,
          accessible:bar.getAttribute('aria-valuetext'),height:root.getBoundingClientRect().height};
          if(JSON.stringify(sample)!==JSON.stringify(loadingSamples.at(-1))) loadingSamples.push(sample); }
      }).observe(document,{subtree:true,childList:true,characterData:true,attributes:true});""")
    return context, page


def real_workflow(browser, screenshots):
    from playwright.sync_api import expect
    jobs = ReportJobs(target=models_progress_report)
    host = fixture_host(jobs)
    context, page = browser_page(browser, host)
    try:
        page.goto(host.browser_url())
        expect(page.locator(".report-loading")).to_be_visible()
        expect(page.locator(".report-loading-stage")).to_contain_text("Sampling recent sessions")
        page.screenshot(path=str(screenshots / "sampling.png"))
        expect(page.locator(".report-loading-stage")).to_contain_text("Analyzing account history", timeout=15000)
        page.screenshot(path=str(screenshots / "account-history.png"))
        expect(page.locator(".overview-model-table")).to_be_visible(timeout=15000)
        samples = page.evaluate("loadingSamples")
        values = [sample["value"] for sample in samples]
        sampling = {sample["value"] for sample in samples if "Sampling recent sessions" in sample["text"]}
        accounts = {sample["value"] for sample in samples if "Analyzing account history" in sample["text"]}
        assert values == sorted(values) and values[-1] == 100, values
        assert len(sampling) >= 3 and len(accounts) >= 5, samples
        assert max(sampling) < 50 and max(accounts) <= 88
        assert all(sample["accessible"] == f'{sample["value"]} percent' for sample in samples)
        heights = [sample["height"] for sample in samples if sample["value"] >= 5]
        assert max(heights) - min(heights) < 1, heights
        assert page.evaluate("loadingRoots.size") == 1, "progress DOM was replaced"
        assert page.locator(".report-loading").count() == 0
        assert page.locator(".overview-model-table th").all_text_contents() == ["Publisher ↕", "Model ↕", "Relative Price List Cost ↓", "Release date ↕"]
        key = page.evaluate("[...views.values()].find(v=>v.section==='models').result.observed_at_ms")
        page.locator('nav a[href="#/accounts"]').click()
        page.locator('nav a[href="#/models"]').click()
        assert page.evaluate("current.result.observed_at_ms") == key
        assert len(jobs.updates()["jobs"]) == 1, "navigation reacquired a frozen result"
        page.screenshot(path=str(screenshots / "ready.png"))
        return dict(case="real Normal through process/HTTP/events/browser", samples=samples, outcome="PASS")
    finally:
        context.close()
        host.close()
        assert host.stopped.is_set() and not host.thread.is_alive()


def lifecycle(browser):
    from playwright.sync_api import expect
    owner = unittest.TestCase()
    data = ScrollData(owner)
    facts = []
    try:
        for mode in ("success", "partial", "failed", "report_timeout", "cancelled"):
            jobs = OverviewJobs(data)
            host = fixture_host(jobs, data)
            context, page = browser_page(browser, host, width=360)
            try:
                page.goto(host.browser_url())
                expect(page.locator(".report-loading")).to_be_visible()
                for phase, done, total, label in [("history", 2, 10, "Loading source history"),
                        ("projection", 1, 4, "Comparing models"), ("finalizing", 1, 2, "Preparing report")]:
                    jobs.phase = dict(phase=phase, completed=done, total=total)
                    expect(page.locator(".report-loading-stage")).to_contain_text(label)
                assert page.evaluate("current.percent") < 100
                jobs.mode = mode
                expect(page.locator(".report-loading")).to_have_count(0)
                assert page.evaluate("current.percent === 100") == (mode in ("success", "partial"))
                if mode in ("failed", "report_timeout", "cancelled"):
                    expect(page.locator("#result [role=alert]")).to_be_visible()
                facts.append(dict(case=mode, outcome="PASS"))
            finally:
                context.close()
                host.close()
    finally:
        owner.doCleanups()
    return facts


def connection_cases(browser):
    from playwright.sync_api import expect
    owner = unittest.TestCase()
    data = ScrollData(owner)
    facts = []
    try:
        for kind in ("unauthorized", "offline", "interrupted"):
            jobs = OverviewJobs(data)
            host = fixture_host(jobs, data)
            context, page = browser_page(browser, host, width=360)
            try:
                if kind != "interrupted":
                    def reject(route):
                        if kind == "unauthorized":
                            route.fulfill(status=401, json=dict(error="authentication_required"))
                        else:
                            route.abort()
                    page.route("**/api/bootstrap", reject)
                page.goto(host.browser_url())
                if kind == "interrupted":
                    page.wait_for_function("() => current.active != null")
                    requests = len(jobs.requests)
                    context.set_offline(True)
                expect(page.locator("#result [role=alert]")).to_be_visible()
                expect(page.locator(".report-loading")).to_have_count(0)
                assert page.evaluate("current.percent || 0") < 100
                if kind == "interrupted":
                    context.set_offline(False)
                    page.evaluate("liveConnection.resync()")
                    page.wait_for_function('() => hostState.kind === "connected"')
                    assert len(jobs.requests) == requests, "reconnect silently replaced acquisition"
                facts.append(dict(case=kind, outcome="PASS"))
            finally:
                context.close()
                host.close()
    finally:
        owner.doCleanups()
    return facts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approved-browser", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--screenshots", type=Path, required=True)
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright
    args.screenshots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            evidence = dict(outcome="PASS", chromium=browser.version,
                cases=[real_workflow(browser, args.screenshots), *lifecycle(browser), *connection_cases(browser)],
                limitations=["Synthetic bounded acquisition, not private provider timing.",
                              "Headless Chromium, not physical input or screen-reader certification."])
        finally:
            browser.close()
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
