"""Measure real browser clicks through the first matching committed-cache DOM."""
import math
from urllib.parse import urlsplit


START_OBSERVATION = """
(button, {selector, text, count}) => {
  const matches = () => {
    const nodes = [...document.querySelectorAll(selector)].filter(node => node.checkVisibility());
    return (count == null || nodes.length === count) &&
      (text == null || nodes.some(node => node.textContent.trim().includes(text)));
  };
  if (matches()) throw new Error('measurement marker already matched before click: ' + selector);
  window.cachedActionMs = null;
  button.addEventListener('click', () => {
    const start = performance.now();
    const observer = new MutationObserver(() => {
      if (!matches()) return;
      window.cachedActionMs = performance.now() - start;
      observer.disconnect();
    });
    observer.observe(document.getElementById('result'), {
      childList: true, subtree: true, attributes: true, characterData: true,
    });
  }, {capture: true, once: true});
}
"""


def _measure(page, button, endpoint, requested, selector, *, text=None, count=None):
    button.evaluate(START_OBSERVATION, dict(selector=selector, text=text, count=count))

    def matching_response(response):
        return urlsplit(response.url).path == endpoint and all(
            response.request.post_data_json.get(key) == value for key, value in requested.items())

    with page.expect_response(matching_response, timeout=5000) as read:
        button.click()
    assert read.value.ok, (endpoint, requested, read.value.status)
    return page.wait_for_function("window.cachedActionMs", timeout=5000).json_value()


def _summary(values):
    ordered = sorted(values)
    return dict(samples=len(ordered), p95_ms=round(ordered[math.ceil(len(ordered) * .95) - 1], 1),
                max_ms=round(ordered[-1], 1))


def measure_warm_actions(page, *, samples=24):
    """Five distinct actions under the same warm restart holds; no production hook."""
    from playwright.sync_api import expect

    outcomes = {}

    def open_section(section, panel):
        if section == "Sessions":
            page.evaluate("location.hash = '#/sessions'")  # Don't re-open a remembered Detail route.
        else:
            page.get_by_role("link", name=section, exact=True).click()
        view = page.locator("#result " + panel)
        expect(view).to_be_visible()
        return view

    sessions = open_section("Sessions", ".sessions-catalog")
    sessions.get_by_role("button", name="All time", exact=True).click()
    expect(sessions.get_by_text("of 5000 cached sessions", exact=False)).to_be_visible()
    if sessions.get_by_text("26–50 of 5000 cached sessions", exact=False).is_visible():
        sessions.get_by_role("button", name="Previous", exact=True).click()
    expect(sessions.get_by_text("1–25 of 5000 cached sessions", exact=False)).to_be_visible()
    outcomes["sessions_page"] = _summary([
        _measure(page, sessions.get_by_role("button", name="Previous" if first else "Next", exact=True),
                 "/api/cache/sessions", {"offset": 0 if first else 25}, ".sessions-catalog .pager span",
                 text=("1–25" if first else "26–50") + " of 5000 cached sessions")
        for first in ((index % 2) == 1 for index in range(samples))
    ])

    for route, section, marker, endpoint, values in (
        ("AI Stats", ".cached-stats", '[data-metric="tokens"]', "/api/cache/ai-stats", ("200", "100")),
        ("Token Mix", ".token-mix-view", ".token-mix-view h2", "/api/cache/token-mix",
         ("Cached Token Mix · 200 tokens", "Cached Token Mix · 100 tokens")),
    ):
        panel = open_section(route, section)
        panel.get_by_role("button", name="7 days", exact=True).click()
        expect(page.locator(marker)).to_have_text(values[1])
        outcomes["stats_period" if route == "AI Stats" else "mix_period"] = _summary([
            _measure(page, panel.get_by_role("button", name="All time" if wide else "7 days", exact=True),
                     endpoint, {"period": "all" if wide else "7-days"}, marker,
                     text=values[0] if wide else values[1])
            for wide in ((index % 2) == 0 for index in range(samples))
        ])

    models = open_section("Models", ".models-view")
    first_model = models.locator(".overview-model-table tbody tr:first-child td:nth-child(2)")
    expect(first_model).to_have_text("Second reference model")
    outcomes["models_sort"] = _summary([
        _measure(page, models.get_by_role("button", name="Relative Price List Cost", exact=False),
                 "/api/cache/models", {"orders": [["cost", "asc" if low else "desc"]]},
                 ".overview-model-table tbody tr:first-child td:nth-child(2)",
                 text="Saved reference model" if low else "Second reference model")
        for low in ((index % 2) == 0 for index in range(samples))
    ])

    accounts = open_section("Accounts", ".account-timeline")
    accounts.get_by_role("button", name="7 days", exact=True).click()
    expect(accounts.locator(".account-timeline-bar")).to_have_count(1)
    target = ".account-timeline .account-timeline-target"
    counts = {}
    for period in ("30 days", "7 days"):
        button = accounts.get_by_role("button", name=period, exact=True)
        key = period.replace(" ", "-")
        with page.expect_response(lambda response: urlsplit(response.url).path == "/api/cache/accounts"
                and response.request.post_data_json == {"period": key}) as read:
            button.click()
        chart = read.value.json()["view"]
        counts[period] = len(chart["buckets"])
        expect(accounts.locator(".account-timeline-target")).to_have_count(counts[period])
    outcomes["accounts_period"] = _summary([
        _measure(page, accounts.get_by_role("button", name=period, exact=True),
                 "/api/cache/accounts", {"period": period.replace(" ", "-")}, target, count=counts[period])
        for period in ("30 days" if index % 2 == 0 else "7 days" for index in range(samples))
    ])
    assert all(result["p95_ms"] <= 250 for result in outcomes.values()), outcomes
    return outcomes
