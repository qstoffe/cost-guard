"""Real V1 mutation → Live → SQLite → Full Watch, native Mini PiP and Sessions."""
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory
from threading import Event
import time
from unittest.mock import patch
from urllib.parse import urlsplit

from development.tests.fixtures.opencode_v1_database import SCHEMA
from development.tests.fixtures.watch_runtime import make_service
from src.application.live import LiveRuntime
from src.sources.opencode_v1 import OpenCodeV1Source
from src.watch.acquisition import LiveAcquisition
from src.watch.web_coordinator import WebWatchCoordinator
from src.web.display_archive import DisplayArchive
from src.web.host import WebHost
from src.web.jobs import ReportJobs

ROOT_ID = "p0-visible-root"
TITLE = "Source-backed live fixture"
DAY_MS = 86_400_000
CONTEXT_TOKENS = 917  # 800 uncached + 100 cached + 17 output
PROMPT_COST = "0.087800"
TOTAL_COST = "0.165600"  # Current CCost plus the earlier 700-input request.


def _wall():
    return time.time_ns() // 1_000_000


def _seed_source(path, history):
    now = _wall()
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript(SCHEMA.read_text(encoding="utf-8"))
        db.execute("PRAGMA journal_mode=WAL")
        db.executemany("INSERT INTO session(id,project_id,directory,title,time_created,time_updated) VALUES(?,?,?,?,?,?)",
            ((f"history-{index:05d}", "fixture", "/fixture", f"Historical session {index}",
              now - 35 * DAY_MS - index * 60_000, now - 35 * DAY_MS - index * 60_000)
             for index in range(history)))


def _write_prompt(path, *, finish=False):
    now = _wall()
    started = now - 2_000
    with closing(sqlite3.connect(path)) as db, db:
        assistant = {"role": "assistant", "time": {"created": started + 1}, "parentID": "p0-current",
                     "providerID": "github-copilot", "modelID": "gpt-test", "agent": "build",
                     "tokens": {"input": 800, "output": 17, "reasoning": 0, "cache": {"read": 100, "write": 0}}}
        if finish:
            raw, = db.execute("SELECT data FROM message WHERE id='p0-answer'").fetchone()
            assistant = json.loads(raw)
            assistant["time"]["completed"] = now
            assistant["finish"] = "stop"
            db.execute("UPDATE message SET time_updated=?,data=? WHERE id='p0-answer'", (now, json.dumps(assistant)))
            db.execute("UPDATE session SET time_updated=? WHERE id=?", (now, ROOT_ID))
        else:
            db.execute("INSERT INTO session(id,project_id,directory,title,time_created,time_updated) VALUES(?,?,?,?,?,?)",
                       (ROOT_ID, "fixture", "/fixture", TITLE, started - 30_000, now))
            previous = {**assistant, "parentID": "p0-prior", "finish": "stop",
                        "time": {"created": started - 29_000, "completed": started - 28_000},
                        # The new request must cover the old input, old output and new text.
                        # Equal input would be an unproven shrink, not a valid V1 anchor.
                        "tokens": {**assistant["tokens"], "input": 700}}
            for key, offset in (("p0-prior", -30_000), ("p0-current", 0)):
                at = started + offset
                data = {"role": "user", "time": {"created": at}, "agent": "build"}
                db.execute("INSERT INTO message VALUES(?,?,?,?,?)", (key, ROOT_ID, at, at, json.dumps(data)))
                db.execute("INSERT INTO part VALUES(?,?,?,?,?,?)",
                           (key + "-text", key, ROOT_ID, at, at, '{"type":"text","text":"Fixture only"}'))
            for key, data in (("p0-old-answer", previous), ("p0-answer", assistant)):
                at = data["time"]["created"]
                db.execute("INSERT INTO message VALUES(?,?,?,?,?)", (key, ROOT_ID, at, now, json.dumps(data)))
    return now


def _cache_mark(page, observation, *, need_metrics=False):
    from playwright.sync_api import TimeoutError

    # Observe the already-committed snapshot in the unopened route lineup.
    try:
        return page.wait_for_function("""({key, status, needMetrics}) => {
          const value = watchCache.value;
          const fact = value?.cards.find(row => row.session_id === key && row.outcome === status &&
            (!needMetrics || row.session_cost != null && row.context_tokens != null));
          return fact ? {fact, generation: value.generation, observed: value.observed_ms, received: Date.now()} : false;
        }""", arg=dict(key=ROOT_ID, status=observation, needMetrics=need_metrics), timeout=20_000).json_value()
    except TimeoutError as error:
        state = page.evaluate("""() => ({
          fresh: watchCache.value?.freshness, generation: watchCache.value?.generation,
          cards: watchCache.value?.cards.map(({session_id, outcome, group, session_cost, context_tokens}) =>
            [session_id, outcome, group, session_cost, context_tokens]),
          live: liveValue?.state, liveCards: liveValue?.view?.active_cards?.map(card => card.session_id),
        })""")
        raise AssertionError((observation, state)) from error


def _mini_visible(page, *, finished=False):
    return page.wait_for_function("""({title, finished}) => {
      const win = documentPictureInPicture.window;
      const row = [...(win?.document.querySelectorAll('tr[data-id]') || [])].find(node =>
        node.getAttribute('aria-label')?.startsWith(title));
      if (!row || row.classList.contains('mini-running') === finished) return false;
      return [...row.cells].slice(2).map(cell => cell.textContent);
    }""", arg=dict(title=TITLE, finished=finished), timeout=8000).json_value()


def _check_cache_metrics(observation):
    fact = observation["fact"]
    assert fact["context_tokens"] == CONTEXT_TOKENS, fact
    assert (fact["prompt_cost"], fact["session_cost"]) == (PROMPT_COST, TOTAL_COST), fact


def _sessions_metrics(page, *, running):
    from playwright.sync_api import TimeoutError

    try:
        return page.wait_for_function("""({key, running}) => {
          const row = document.querySelector(`.sessions-catalog tbody tr[data-id="${key}"]`);
          const fact = row?.value;
          if (fact && fact.running === running && fact.context_tokens != null && fact.ccost != null)
            return {context: fact.context_tokens, cost: Number(fact.ccost), ctxText: row.cells[6].textContent};
          return false;
        }""", arg=dict(key=ROOT_ID, running=running), timeout=8_000).json_value()
    except TimeoutError as error:
        state = page.evaluate("""key => {
          const row = document.querySelector(`.sessions-catalog tbody tr[data-id="${key}"]`);
          return {fact: row?.value, cells: row && [...row.cells].map(cell => cell.textContent)};
        }""", ROOT_ID)
        raise AssertionError((running, state)) from error


def check_p0_v1(browser, product_root, *, history=0):
    from playwright.sync_api import expect

    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "config").mkdir()
        shutil.copyfile(product_root / "config/default-config.jsonc", root / "config/default-config.jsonc")
        path = root / "synthetic-source.db"
        _seed_source(path, history)
        source = OpenCodeV1Source(path)
        config, selection, service, _ = make_service(root, source, now_ms=_wall(), async_accounts=True)
        config["sessionWatchIntervalSeconds"] = "auto"
        # One independent fixture service per worker, using the same local source and pricing.
        def worker(now):
            return make_service(root, OpenCodeV1Source(path), now_ms=now, async_accounts=True)[2]

        coordinator = WebWatchCoordinator(selection=selection, report_service=service, config=config,
            service_factory=worker, clock_ms=_wall, record_observations=False)
        driver = LiveAcquisition(coordinator)
        host = WebHost(root, jobs=ReportJobs())
        host.cached_sessions_enabled = host.cached_watch_enabled = host.cached_models_enabled = True
        committed = {}

        def publish(kind, hint):
            if kind == "watch-cache" and "generation" in hint:
                committed[hint["generation"]] = _wall()
            host.events.publish(kind, hint)

        archive = host.display_archive = DisplayArchive(root, publish, watch_enabled=True, models_enabled=True)
        host.live = LiveRuntime(lambda: driver, host.events.publish, host.runtime_failed, display_archive=archive)
        entered, release = Event(), Event()
        history_factory = coordinator.history_factory

        def hold_catalog(now):
            entered.set()
            if not release.wait(45):
                raise AssertionError("fixture did not release held historical read")
            return history_factory(now)

        if history:
            coordinator.history_factory = hold_catalog
        context = browser.new_context(viewport={"width": 1100, "height": 800})
        try:
            host.start()
            host.publish_ready()
            origin = host.server.origin
            context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(origin + "/") else route.abort())
            page = context.new_page()
            requests, errors = [], []
            page.on("request", lambda request: requests.append(urlsplit(request.url).path))
            page.on("pageerror", lambda error: errors.append(str(error)))
            with patch.object(host.jobs, "submit", side_effect=AssertionError("a normal page started a finite job")) as jobs:
                page.goto(host.browser_url())
                expect(page.locator("#result .models-view")).to_be_visible()
                page.wait_for_function("() => watchCache?.value?.freshness === 'current'", timeout=15_000)
                assert page.evaluate("() => !!documentPictureInPicture && !documentPictureInPicture.window")
                assert not page.locator(".watch-view").count()
                if history:
                    assert entered.wait(8) and not coordinator.catalog_job.done()
                started = _write_prompt(path)
                running = _cache_mark(page, "running")
                assert running["fact"]["start_ms"] == started - 2_000
                assert running["observed"] >= started
                qualified = _cache_mark(page, "running", need_metrics=True)
                _check_cache_metrics(qualified)
                page.wait_for_function("() => !watchCache.dirty && !watchCache.flight && !watchCache.timer")

                reads = requests.count("/api/cache/watch")
                start = time.perf_counter()
                page.get_by_role("link", name="Watch", exact=True).click()
                card = page.locator(".watch-active article").filter(has_text=TITLE)
                expect(card).to_be_visible()
                expect(card.locator("tr.watch-running")).to_have_count(1)
                context_text = card.locator(".watch-session-context").text_content()
                assert context_text
                full_ms = (time.perf_counter() - start) * 1000
                assert requests.count("/api/cache/watch") == reads
                start = time.perf_counter()
                page.locator("#mini-watch-toggle").click()
                metrics = _mini_visible(page)
                mini_ms = (time.perf_counter() - start) * 1000
                assert metrics[0] and metrics[1] and metrics[2] == context_text
                assert requests.count("/api/cache/watch") == reads
                assert max(full_ms, mini_ms) < 1000
                page.evaluate("location.hash = '#/sessions?period=all'")
                sessions = page.locator(".sessions-catalog")
                expect(sessions.get_by_role("link", name=f"[RUNNING] {TITLE}", exact=True)).to_be_visible()
                assert _sessions_metrics(page, running=True) == dict(
                    context=CONTEXT_TOKENS, cost=float(TOTAL_COST), ctxText=context_text)
                page.get_by_role("link", name="Watch", exact=True).click()

                finished = _write_prompt(path, finish=True)
                terminal = _cache_mark(page, "finished")
                assert terminal["fact"]["finish_ms"] == finished and terminal["observed"] >= finished
                verified = _cache_mark(page, "finished", need_metrics=True)
                _check_cache_metrics(verified)
                terminal_metrics = _mini_visible(page, finished=True)
                assert terminal_metrics == metrics
                expect(page.locator(".watch-recent article").filter(has_text=TITLE)).to_be_visible()
                page.evaluate("documentPictureInPicture.window.close()")
                page.evaluate("location.hash = '#/sessions?period=all'")
                sessions = page.locator(".sessions-catalog")
                expect(sessions).to_be_visible()
                expect(sessions.get_by_role("link", name=f"[RUNNING] {TITLE}", exact=True)).to_have_count(0)
                if not history:
                    expect(sessions.locator("tbody").get_by_role("link", name=TITLE, exact=True)).to_be_visible()
                    assert _sessions_metrics(page, running=False) == dict(
                        context=CONTEXT_TOKENS, cost=float(TOTAL_COST), ctxText=context_text)
                if history:
                    assert not coordinator.catalog_job.done()
                jobs.assert_not_called()
            assert not errors, errors
            assert not {"/api/reports", "/api/detail", "/api/sessions"}.intersection(requests)
            def latency(value, source_ms):
                saved = committed[value["generation"]]
                assert source_ms <= saved <= value["received"], (source_ms, saved, value["received"])
                return dict(source_to_commit=saved - source_ms, commit_to_browser_snapshot=value["received"] - saved)

            return dict(history_source_roots=history, real_v1_mutation=True, running_watch_wall_ms=round(full_ms, 1),
                        running_native_mini_wall_ms=round(mini_ms, 1), running=latency(running, started),
                        qualified_running_cost_and_context=latency(qualified, started),
                        finish=latency(terminal, finished), qualified_finish_cost=latency(verified, finished),
                        mini_running_metrics=metrics, mini_finished_metrics=terminal_metrics,
                        context_tokens=CONTEXT_TOKENS, finish_costs=[PROMPT_COST, TOTAL_COST])
        finally:
            context.close()
            host.stop()
            release.set()
            host.close()


if __name__ == "__main__":
    import os
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.environ.get("BROWSER_PROBE_EXECUTABLE"), headless=True)
        try:
            for history in (0, 5_000):
                print(json.dumps(check_p0_v1(browser, Path.cwd(), history=history)), flush=True)
        finally:
            browser.close()
