"""Opt-in protected browser probe for real V1 running and finished bursts."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
from threading import Condition
import time
from unittest.mock import patch

from .cached_p0_v1 import _wall, check_p0_v1


def _root(index):
    return f"burst-root-{index:02d}"


def _event(index, wave):
    return f"{_root(index)}-p{wave:02d}"


def _write_wave(path, indexes, wave, *, previous=None):
    """Stage actual V1 messages; derive expectations from the fixture clocks."""
    now = _wall()
    facts = {}
    with closing(sqlite3.connect(path)) as db, db:
        for index in indexes:
            root = _root(index)
            start = now - 2_000 - index
            finish = now - index if wave else None
            if previous is not None:
                start = max(start, previous[root][2])
                assert start + 1 <= finish
            event = _event(index, wave)
            answer = event + "-answer"
            if wave == 0:
                db.execute("INSERT INTO session(id,project_id,directory,title,time_created,time_updated) VALUES(?,?,?,?,?,?)",
                           (root, "fixture", "/fixture", f"Burst root {index:02d}", start, now))
            else:
                db.execute("UPDATE session SET time_updated=? WHERE id=?", (now, root))
            user = {"role": "user", "time": {"created": start}, "agent": "build"}
            assistant = {"role": "assistant", "parentID": event, "time": {"created": start + 1},
                         "providerID": "github-copilot", "modelID": "gpt-test", "agent": "build",
                         "tokens": {"input": 800 + 100 * wave, "output": 17,
                                    "reasoning": 0, "cache": {"read": 100, "write": 0}}}
            if finish is not None:
                assistant["time"]["completed"] = finish
                assistant["finish"] = "stop"
            db.executemany("INSERT INTO message VALUES(?,?,?,?,?)",
                           ((event, root, start, now, json.dumps(user)),
                            (answer, root, start + 1, now, json.dumps(assistant))))
            db.execute("INSERT INTO part VALUES(?,?,?,?,?,?)",
                       (event + "-text", event, root, start, start, '{"type":"text","text":"Burst fixture"}'))
            facts[root] = (event, start, finish)
    return now, facts


def _finish_first_wave(path, running):
    now = _wall()
    facts = {}
    with closing(sqlite3.connect(path)) as db, db:
        for index, (root, (event, start, _)) in enumerate(sorted(running.items())):
            finish = now - index
            answer = event + "-answer"
            raw, = db.execute("SELECT data FROM message WHERE id=?", (answer,)).fetchone()
            data = json.loads(raw)
            data["time"]["completed"] = finish
            data["finish"] = "stop"
            db.execute("UPDATE message SET data=?,time_updated=? WHERE id=?", (json.dumps(data), now, answer))
            db.execute("UPDATE session SET time_updated=? WHERE id=?", (now, root))
            facts[root] = (event, start, finish)
    return now, facts


class FinishCapture:
    """Observe accepted real-source terminal facts before the five-card UI cap."""
    def __init__(self, cards):
        self.cards = cards
        self.accept = cards.accept
        self.condition = Condition()
        self.finished = {}

    def observe(self, result, now_ms):
        self.accept(result, now_ms)
        entry = self.cards.sessions.get(result.session_id)
        if (result.phase != "rows" or entry is None or entry.capture is None
                or entry.generation != result.generation or entry.verified_generation != result.generation
                or entry.capture.retained or not entry.capture.authoritative):
            return
        with self.condition:
            for row in entry.capture.rows:
                if row.completed_successfully and not row.execution_unverified and row.completed_at_ms is not None:
                    self.finished[row.event_id] = (row.at_ms, row.completed_at_ms)
            self.condition.notify_all()

    def require(self, facts):
        expected = {key: (start, end) for key, start, end in facts.values()}
        with self.condition:
            complete = self.condition.wait_for(lambda: expected.keys() <= self.finished.keys(), timeout=22)
            assert complete, sorted(expected.keys() - self.finished.keys())
            assert {key: self.finished[key] for key in expected} == expected


def _running_cache(page, expected, *, metrics=False):
    from playwright.sync_api import TimeoutError

    try:
        return page.wait_for_function("""({expected, metrics}) => {
          const value = watchCache.value;
          const running = value?.cards.filter(fact => fact.outcome === 'running') || [];
          if (value?.freshness !== 'current' || running.length !== Object.keys(expected).length) return false;
          if (!running.every(fact => expected[fact.session_id]?.[0] === fact.event_id &&
              expected[fact.session_id][1] === fact.start_ms &&
              (!metrics || fact.context_tokens === 917 && Number(fact.prompt_cost) === .0878 &&
                Number(fact.session_cost) === .0878 && fact.session_cost_complete))) return false;
          return {generation: value.generation, received: Date.now()};
        }""", arg=dict(expected=expected, metrics=metrics), timeout=24_000).json_value()
    except TimeoutError as error:
        actual = page.evaluate("""() => watchCache.value?.cards.filter(fact => fact.outcome === 'running')
          .map(fact => [fact.session_id, fact.context_tokens, fact.prompt_cost, fact.session_cost,
                        fact.session_cost_complete])""")
        raise AssertionError((len(expected), metrics, actual)) from error


def _running_dom(page, expected, *, mini):
    page.wait_for_function("""({keys, mini}) => {
      const root = mini ? documentPictureInPicture.window?.document : document;
      if (!root) return false;
      const nodes = mini ? root.querySelectorAll('tr.mini-running') :
        root.querySelectorAll('.watch-active article:has(tr.watch-running)');
      const ids = [...nodes].map(node => mini ? node.dataset.id : node.dataset.session).sort();
      return JSON.stringify(keys) === JSON.stringify(ids);
    }""", arg=dict(keys=sorted(expected), mini=mini), timeout=8_000)


def _latest_finish(page, facts, committed):
    from playwright.sync_api import TimeoutError

    root, (event, _, end) = max(facts.items(), key=lambda item: item[1][2])
    try:
        mark = page.wait_for_function("""({root, event, end}) => {
          const value = watchCache.value;
          const fact = value?.cards.find(card => card.session_id === root && card.event_id === event &&
            card.finish_ms === end && card.outcome === 'finished');
          return value?.freshness === 'current' && fact ?
            {generation: value.generation, received: Date.now()} : false;
        }""", arg=dict(root=root, event=event, end=end), timeout=10_000).json_value()
    except TimeoutError as error:
        actual = page.evaluate("""() => ({
          fresh: watchCache.value?.freshness, observed: watchCache.value?.observed_ms,
          cards: watchCache.value?.cards.filter(card => card.session_id.startsWith('burst-'))
            .map(card => [card.session_id, card.event_id, card.group, card.outcome, card.finish_ms]),
          history: liveValue?.view?.history_state,
          recent: liveValue?.view?.recent_finished_cards?.map(card => card.session_id),
        })""")
        raise AssertionError((event, end, actual)) from error
    return root, event, mark, committed[mark["generation"]]


def _finished_dom(page, root, event, wave, *, mini):
    return page.wait_for_function("""({root, event, number, mini}) => {
      const full = document.querySelector(`.watch-recent article[data-session="${root}"] tr[data-id="${event}"]`);
      if (!full?.getClientRects().length) return false;
      const row = documentPictureInPicture.window?.document.querySelector(`tr[data-id="${root}"]`);
      if (mini && !row?.getAttribute('aria-label')?.endsWith(` · Prompt ${number} · Completed`)) return false;
      return Date.now();
    }""", arg=dict(root=root, event=event, number=wave + 1, mini=mini), timeout=8_000).json_value()


def measure_burst(page, path, cards, requests, committed):
    running = {}
    counts = []
    captures = FinishCapture(cards)
    with patch.object(cards, "accept", side_effect=captures.observe):
        _running_cache(page, running)
        for before, after in ((0, 1), (1, 5), (5, 26)):
            started, facts = _write_wave(path, range(before, after), 0)
            running.update(facts)
            first = _running_cache(page, running)
            qualified = _running_cache(page, running, metrics=True)
            counts.append([after, committed[first["generation"]] - started,
                           committed[qualified["generation"]] - started])

        page.wait_for_function("() => !watchCache.dirty && !watchCache.flight && !watchCache.timer")
        reads = requests.count("/api/cache/watch")
        started = time.perf_counter()
        page.get_by_role("link", name="Watch", exact=True).click()
        _running_dom(page, running, mini=False)
        full_ms = (time.perf_counter() - started) * 1000
        assert requests.count("/api/cache/watch") == reads
        started = time.perf_counter()
        page.locator("#mini-watch-toggle").click()
        _running_dom(page, running, mini=True)
        mini_ms = (time.perf_counter() - started) * 1000
        assert requests.count("/api/cache/watch") == reads
        assert max(full_ms, mini_ms) < 1000
        page.evaluate("() => { location.hash = '#/sessions?period=all'; }")
        order = sorted(running, key=lambda root: (-running[root][1], root))
        _running_sessions(page, order[:25])
        page.get_by_role("button", name="Next", exact=True).click(timeout=8_000)
        _running_sessions(page, order[25:])
        page.get_by_role("link", name="Watch", exact=True).click()

        waves = []
        previous = None
        for wave in range(10):
            source_ms, facts = (_finish_first_wave(path, running) if wave == 0 else
                                _write_wave(path, range(26 if wave < 9 else 16), wave, previous=previous))
            captures.require(facts)
            root, event, mark, saved = _latest_finish(page, facts, committed)
            rendered = _finished_dom(page, root, event, wave, mini=wave < 5)
            assert source_ms <= saved <= mark["received"] <= rendered
            waves.append([len(facts), saved - source_ms, mark["received"] - saved, rendered - saved])
            if wave == 0:
                _running_dom(page, {}, mini=True)
            if wave == 4:
                page.evaluate("() => documentPictureInPicture.window.close()")
            previous = facts
        assert len(captures.finished) == 250, len(captures.finished)
    return dict(running_count_commit_ms=counts, full_first_ms=round(full_ms, 1), mini_first_ms=round(mini_ms, 1),
                finished_source_capture_count=len(captures.finished), finish_wave_commit_ms=waves)


def _running_sessions(page, keys):
    page.wait_for_function("""keys => {
      const running = [...document.querySelectorAll('.sessions-catalog tbody tr')].filter(row => row.value?.running);
      return JSON.stringify(keys) === JSON.stringify(running.map(row => row.dataset.id)) &&
        running.every(row => row.value.context_tokens === 917 && Number(row.value.ccost) === .0878);
    }""", arg=keys, timeout=8_000)


if __name__ == "__main__":
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.environ.get("BROWSER_PROBE_EXECUTABLE"), headless=True)
        try:
            for history in (0, 5_000):
                print(json.dumps(dict(history=history, **check_p0_v1(
                    browser, Path.cwd(), history=history, burst=measure_burst))), flush=True)
        finally:
            browser.close()
