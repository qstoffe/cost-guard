"""Headless shipped-UI/native-pointer proof; no OS input or provider requests."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.scripted_parent import scripted_parent, catalog
from development.tests.fixtures.report_runtime import FakeSource
from development.tests.fixtures.web_reports import SyntheticSessionsRuntime, current_report
from src.web.host import WebHost
from src.web.jobs import ReportJobs
from src.analysis import analyze_snapshot
from src.analysis.session_cost import reconcile_session_cost
from src.reports.prompt_rows import PromptRowProjector
from src.application.live_projection import project_live
from src.watch.models import WatchCard, WatchRow, WatchProjection


def main():
    from playwright.sync_api import sync_playwright, expect
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=61)
    args = parser.parse_args()
    evidence = {"checks": [], "limitations": ["Headless Chromium; physical desktop/window switching NOT OBSERVED"]}
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as playwright:
        root = Path(tmp)
        (root / "config").mkdir()
        shutil.copyfile(ROOT / "config/default-config.jsonc", root / "config/default-config.jsonc")
        source = FakeSource(scripted_parent(start=int(time.time() * 1000) - 180_000))
        host = WebHost(root, jobs=ReportJobs(target=current_report))
        host.live = SyntheticSessionsRuntime(root, source=source, clock_ms=lambda: int(time.time() * 1000))
        host.live.service.pricing_provider.catalog = catalog()
        host.start()
        host.publish_ready()
        browser = playwright.chromium.launch(headless=True, executable_path=playwright.chromium.executable_path)
        context = browser.new_context(viewport={"width": 1366, "height": 900}, has_touch=True)
        page = context.new_page()
        errors = []
        refreshes = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: refreshes.append(request.url) if request.url.endswith("/api/detail") else None)
        origin = host.server.origin
        help_source = (ROOT / "src/web/assets/help.js").read_text()
        # Read-only lifecycle diagnostics in the browser copy; never alter hover,
        # hit testing, timing, input events, native APIs or the closure decision.
        help_source = help_source.replace("function close(suppress = false) {", """function close(suppress = false) {
          (window.helpCloses ||= []).push({at:performance.now(),stack:new Error().stack,
            active:active?.textContent,connected:active?.isConnected,origin,
            triggerHover:active && hovered(entries.get(active).pointerTarget),panelHover:hovered(panel),
            pointer,hit:pointer && doc.elementFromPoint(pointer.x,pointer.y)?.outerHTML.slice(0,200)});
        """)

        def route(request):
            if not request.request.url.startswith(origin + "/"):
                request.abort()
            elif request.request.url.endswith("/help.js"):
                request.fulfill(body=help_source, content_type="application/javascript")
            else:
                request.continue_()

        context.route("**/*", route)
        try:
            page.goto(host.browser_url())
            for view, selector in (
                ("sessions/root", ".session-history-table tbody tr:first-child td:nth-child(2) .help-value"),
                ("sessions", ".sessions-table tbody tr:first-child td:nth-child(3) .help-value"),
            ):
                page.goto(origin + "/#/" + view)
                if view == "sessions":
                    page.get_by_role("button", name="All time", exact=True).click()
                target = page.locator(selector)
                expect(target).to_have_text("Scripted*", timeout=30000)
                if view == "sessions":
                    expect(page.locator(".sessions-table tbody tr:first-child td:first-child")).to_have_text(
                        re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}\*"), timeout=30000)
                page.mouse.move(1, 1)
                target.hover()
                panel = page.locator("#context-help")
                expect(panel).to_be_visible()
                page.evaluate("""selector => {
                  window.holdTarget=document.querySelector(selector);window.holdSamples=[];window.holdMoves=0;
                  window.holdInput=()=>holdMoves++;document.addEventListener('pointermove',holdInput,true);
                  window.holdTimer=setInterval(()=>holdSamples.push({
                    at:performance.now(),open:!document.getElementById('context-help').hidden,
                    connected:holdTarget.isConnected,hover:holdTarget.matches(':hover'),
                    panelHover:document.getElementById('context-help').matches(':hover'),
                    text:document.getElementById('context-help').textContent}),250);
                }""", selector)
                began, changed = time.monotonic(), 0
                while time.monotonic() - began < args.seconds:
                    remaining = args.seconds - (time.monotonic() - began)
                    page.wait_for_timeout(min(5100, max(0, remaining * 1000)))
                    changed += 1
                    saved = source.snapshot
                    # Actual acquired-source revisions refresh help through the
                    # ordinary scheduler and 5s Detail polling, not direct UI calls.
                    source.snapshot = replace(saved, source_revision=f"help-update-{view}-{changed}",
                        messages=tuple(replace(message, variant="max" if changed % 2 else "high")
                            if message.message_id == "cu" else message for message in saved.messages))
                result = page.evaluate("""() => {
                  clearInterval(holdTimer);document.removeEventListener('pointermove',holdInput,true);
                  return {samples:holdSamples,moves:holdMoves,closes:window.helpCloses,
                    text:document.getElementById('context-help').textContent};
                }""")
                result.update(view=view, seconds=args.seconds)
                result["source_revisions"] = changed
                evidence["checks"].append(result)
                assert result["moves"] == 0
                assert all(sample["open"] and sample["connected"] and (sample["hover"] or sample["panelHover"])
                    for sample in result["samples"]), f"Stationary hover closed in {view}"
                assert "Selected/attempted subagents" in result["text"]
                assert "Opus 5.5" in result["text"]
                if args.seconds >= 61:
                    assert len({sample["text"] for sample in result["samples"]}) > 1, "No actual Model help update observed"
                page.mouse.move(1, 1)
                expect(panel).to_be_hidden()
                # Real native input after a deliberate re-hover: keyboard,
                # pin/touch and narrow layout must retain their own lifetimes.
                page.set_viewport_size({"width": 360, "height": 844})
                target.hover()
                expect(panel).to_be_visible()
                page.keyboard.press("Escape")
                expect(panel).to_be_hidden()
                page.mouse.move(1, 1)
                page.keyboard.press("Tab")
                target.focus()
                expect(panel).to_be_visible()
                page.keyboard.press("Escape")
                expect(panel).to_be_hidden()
                target.blur()
                target.tap()
                expect(panel).to_be_visible()
                page.keyboard.press("Escape")
                expect(panel).to_be_hidden()
                target.blur()  # Retire touch focus before the separate mouse/tab scenario.
                page.set_viewport_size({"width": 1366, "height": 900})
                for _ in range(2):
                    page.mouse.move(1, 1)
                    target.hover()
                    expect(panel).to_be_visible()
                    other = context.new_page()
                    other.goto(origin + "/")
                    other.bring_to_front()
                    evidence.setdefault("tab_visibility", []).append(page.evaluate(
                        "({visibility:document.visibilityState,focused:document.hasFocus()})"))
                    page.bring_to_front()
                    page.mouse.move(1, 1)
                    expect(panel).to_be_hidden()
                    target.hover()
                    expect(panel).to_be_visible()
                    page.wait_for_timeout(3100)
                    expect(panel).to_be_visible()
                    other.close()
                    page.mouse.move(1, 1)
                    expect(panel).to_be_hidden()
            # Missing/late child selection is not permission to retain an older
            # identity. Acquire both revisions through the actual Detail route.
            start = source.snapshot.events[0].created_at_ms
            source.snapshot = scripted_parent(start=start, complete=False, selection=False)
            page.goto(origin + "/#/sessions/root")
            target = page.locator(".session-history-table tbody tr:first-child td:nth-child(2) .help-value")
            expect(target).to_have_text("Scripted*", timeout=30000)
            page.mouse.move(1, 1)
            target.hover()
            panel = page.locator("#context-help")
            expect(panel).to_contain_text("model unknown", timeout=30000)
            page.wait_for_timeout(3100)
            expect(panel).to_be_visible()
            source.snapshot = scripted_parent(start=start)
            expect(panel).to_contain_text("Selected/attempted subagents", timeout=30000)
            expect(panel).to_contain_text("Opus 5.5")
            page.wait_for_timeout(3100)
            expect(panel).to_be_visible()
            page.mouse.move(1, 1)
            expect(panel).to_be_hidden()
            saved = source.snapshot
            bundle = analyze_snapshot(saved, now_ms=int(time.time() * 1000))
            projector = PromptRowProjector(snapshot=saved, bundle=bundle, catalog=catalog(), config={})
            parent = next(projector.prompt(record) for record in bundle.prompts if record.session_id == "root")
            cost = reconcile_session_cost(host.live.service.cache_repository, saved, catalog())
            card = WatchCard("root", "Scripted parent", "u", (WatchRow("root", "Scripted parent", parent),),
                "observed", session_cost=cost, session_cost_state="observed")
            wire = project_live(WatchProjection("Watch", "Synthetic", (), now_ms=int(time.time() * 1000),
                active_cards=(card,), cards_state="observed")).to_json()
            # Publish the canonical fixture through the real shared SSE owner.
            # A direct Mini-only update races later empty Live publications.
            host.events.publish("live", dict(state="running", view=wire))
            page.wait_for_function("miniWatch.measure?.ready && miniWatch.placement")
            owner_cdp = context.new_cdp_session(page)
            with context.expect_page(timeout=15000) as opened:
                owner_cdp.send("Runtime.evaluate", dict(expression="miniWatch.toggle()", userGesture=True, awaitPromise=True))
            mini = opened.value
            mini.wait_for_load_state()
            expect(mini.locator(".mini-activity")).to_be_visible()
            mini_panel = mini.locator("#context-help")
            for selector, text in ((".mini-activity", "Selected/attempted subagents"),
                                   (".mini-cost-value", "not a proven zero upstream bill")):
                mini.mouse.move(1, 1)
                mini.locator(selector).first.hover()
                expect(mini_panel).to_contain_text(text)
                mini.wait_for_timeout(3100)
                expect(mini_panel).to_be_visible()
                mini.mouse.move(1, 1)
                expect(mini_panel).to_be_hidden()
            page.evaluate("miniWatch.close()")
            evidence["mini"] = "PASS: actual headless native Document PiP, canonical Activity and prompt CCost help, mouse exit/re-hover"
            assert not errors, errors
            evidence.update(browser=browser.version, errors=errors, detail_requests=len(refreshes), outcome="PASS")
        finally:
            evidence["tail_closes"] = page.evaluate("window.helpCloses || []")
            args.output.write_text(json.dumps(evidence, indent=2))
            context.close()
            browser.close()
            host.close()
    print(json.dumps({**{key: value for key, value in evidence.items() if key != "tail_closes"}, "checks": [
        dict(view=c["view"], samples=len(c["samples"]), closed=sum(not s["open"] for s in c["samples"]),
            moves=c["moves"], text=c["text"]) for c in evidence["checks"]]}, indent=2))


if __name__ == "__main__":
    main()
