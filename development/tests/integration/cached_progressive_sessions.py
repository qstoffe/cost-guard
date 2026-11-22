"""Production cache queries and applied Sessions DOM at controlled cohort boundaries."""
from datetime import datetime, timezone
from decimal import Decimal
import math
from time import perf_counter_ns
from unittest.mock import patch
from urllib.parse import urlsplit

from src.cache.display_history import BATCH_LIMIT, SessionChange, SessionFact

SCALES = (0, 3, 50, 300, 1_000, 10_000)
DAY_MS = 86_400_000
CLICK_TO_PAINT = """
(button, query) => {
  window.sessionAction = null;
  button.addEventListener('click', () => {
    window.sessionAction = {query, start: performance.now()};
  }, {capture: true, once: true});
}
"""
ATTACH_OBSERVER = """
() => {
  const view = current.catalog;
  const paint = view.paint.bind(view);
  view.paint = data => {
    paint(data);
    const action = window.sessionAction;
    if (!action || action.result ||
        !Object.keys(action.query).every(key => data[key] === action.query[key])) return;
    const {textContent: footer} = view.label;
    const rows = [...view.body.querySelectorAll('tr[data-id]')];
    action.result = {footer, ids: rows.map(row => row.dataset.id),
      elapsedMs: performance.now() - action.start};
  };
}
"""


def fixture_activity(now, index):
    return now - index * 60_000 - (index % 3) * 35 * DAY_MS


def _sort_key(row, sort, direction):
    value = row.ccost if sort == "ccost" else row.prompts
    return value is None, value * direction if value is not None else 0, row.session_id


def _timings(values):
    ordered = sorted(values)
    return dict(samples=len(ordered), p95_ms=round(ordered[math.ceil(len(ordered) * .95) - 1], 2),
                max_ms=round(ordered[-1], 2))


def _check_action(page, button, request, expected):
    button.evaluate(CLICK_TO_PAINT, request)
    with page.expect_response(lambda response: urlsplit(response.url).path == "/api/cache/sessions"
            and all(response.request.post_data_json.get(key) == value for key, value in request.items()),
            timeout=5000) as observed:
        button.click()
    assert observed.value.ok, (request, observed.value.status)
    result = page.wait_for_function("window.sessionAction?.result", timeout=5000).json_value()
    payload = observed.value.json()
    offset = request["offset"]
    wanted = [row.session_id for row in expected[offset:offset + 25]]
    assert payload["cached_total"] == len(expected) and result["ids"] == wanted, (request, result, wanted)
    footer = (f"Showing {offset + 1}–{offset + len(wanted)} of {len(expected)} cached sessions"
              if wanted else "No cached sessions yet")
    assert result["footer"].startswith(footer), (request, result["footer"], footer)
    return result["elapsedMs"]


def check_progressive_sessions(page, archive, events, now):
    from playwright.sync_api import expect

    page.evaluate("location.hash = '#/sessions?period=all'")
    view = page.locator(".sessions-catalog")
    expect(view.get_by_text("No cached sessions yet")).to_be_visible()
    expect(view.get_by_role("img", name="Loading older history")).to_be_visible()
    page.wait_for_function("current?.catalog?.data?.period === 'all'")
    page.evaluate(ATTACH_OBSERVER)
    today = datetime.fromtimestamp(now / 1000, timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    floors = {"today": int(today.timestamp() * 1000), "month": int(today.replace(day=1).timestamp() * 1000), "all": 0}

    run_sql = archive.history.session_page
    sql = []

    def timed_sql(*args, **kwargs):
        start = perf_counter_ns()
        try:
            return run_sql(*args, **kwargs)
        finally:
            sql.append((perf_counter_ns() - start) / 1_000_000)

    binding = archive.views.binding
    source = archive.views.source
    rows = []
    results = {}
    def button(label):
        return view.get_by_role("button", name=label, exact=True)

    def sort_button(label):
        return view.locator("th").filter(has_text=label).get_by_role("button")

    controls = (
        (sort_button("CCost"), "all", "ccost", 1, 0),
        (sort_button("CCost"), "all", "ccost", -1, 0),
        (sort_button("Prompts"), "all", "prompts", 1, 0),
        (sort_button("Prompts"), "all", "prompts", -1, 0),
        (button("This month"), "month", "prompts", -1, 0),
        (button("Today"), "today", "prompts", -1, 0),
        (button("All time"), "all", "prompts", -1, 0),
    )
    paging = ((button("Next"), "all", "prompts", -1, 25),
              (button("Previous"), "all", "prompts", -1, 0))
    with patch("src.application.cached_session_views.wall_ms", return_value=now), \
         patch.object(archive.history, "session_page", side_effect=timed_sql):
        for count in SCALES:
            sql_before = len(sql)
            for offset in range(len(rows), count, BATCH_LIMIT):
                batch = tuple(SessionFact(f"ses_cold_{i:05d}", "fixture", f"Synthetic root {i}",
                    activity_ms=fixture_activity(now, i), ccost=Decimal(i % 40) if i % 11 else None,
                    prompts=i % 31 if i % 13 else None)
                    for i in range(offset, min(count, offset + BATCH_LIMIT)))
                generation = archive.history.commit_sessions(source, tuple(SessionChange(row, None) for row in batch))
                assert generation is not None
                rows.extend(batch)
            if count:
                events.publish("cache", dict(view="sessions", binding=binding, generation=generation))
                expect(view.get_by_text(f"of {count} cached sessions", exact=False)).to_be_visible(timeout=5000)
            if count > 25:
                expect(button("Next")).to_be_enabled()
            else:
                expect(button("Next")).to_be_disabled()
            samples = []
            for _ in range(4):
                for control, period, sort, direction, offset in (*controls, *(paging if count > 25 else ())):
                    expected = sorted((row for row in rows if row.activity_ms >= floors[period]),
                                      key=lambda row: _sort_key(row, sort, direction))
                    request = dict(period=period, sort=sort, direction=direction, offset=offset)
                    samples.append(_check_action(page, control, request, expected))
            timings = _timings(samples)
            assert timings["p95_ms"] <= 250, (count, timings)
            results[count] = dict(click_to_dom=timings, sql_page_call=_timings(sql[sql_before:]))
    return dict(scales=results, controlled_cache_commits=True, source_roots=SCALES[-1], coverage="Sessions only")
