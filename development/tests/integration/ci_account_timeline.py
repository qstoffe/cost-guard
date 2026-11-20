"""Real headless Accounts journey over shipped HTTP, Live and synthetic source facts."""
import argparse
from collections import Counter
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
import shutil
import sys
import tempfile
from threading import Event, current_thread
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.account_periods import subscription
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests.fixtures.watch_runtime import make_service
from development.tests.integration.serve_data_dispatch import DispatchJobs
from development.tests.test_account_timeline import NOV_1, NOV_5, stamp
from src.accounts.acquisition import AccountUpdate
from src.analysis.account_timeline import DAY_MS, timeline_window
from src.domain import QuotaComponent, TokenUsage
from src.watch.account_timeline import ROOTS_PER_TURN
from src.watch.acquisition import LiveAcquisition
from src.watch.web_coordinator import WebWatchCoordinator
from src.web.dispatch import DataDispatcher
from src.web.host import WebHost


class ChartSource(SyntheticMonthSource):
    def __init__(self, accounts):
        super().__init__(0, 0, month_start_ms=NOV_1)
        self.timeline_reads = Counter()
        self.continue_history = Event()
        self.replace_usage(0, NOV_1 + 1, 1_000_000_000, accounts[0].ref)
        self.replace_usage(1, NOV_1 + 2 * DAY_MS + 40_000, 1_000_000, accounts[1].ref)
        for index in range(2, 14):
            self.replace_usage(index, NOV_1 + 2 * DAY_MS + index * 1000, 0, accounts[1].ref)
        for index in range(14, 25):
            self.replace_usage(index, NOV_1 + 4 * DAY_MS + index * 1000,
                               1 if index == 14 else 0, accounts[2].ref)

    def replace_usage(self, index, at_ms, tokens, account):
        snapshot = make_root_snapshot(index, 1, month_start_ms=at_ms - index * 60_000)
        model = replace(snapshot.invocations[0].model, provider=account.provider_id)
        invocation = replace(snapshot.invocations[0], model=model, account_ref=account, tokens=TokenUsage(input=tokens))
        self.snapshots[snapshot.root.session_id] = replace(snapshot, complete=True, invocations=(invocation,))

    def load_session_snapshot(self, key):
        if current_thread().name.startswith('cost-guard-account-timeline'):
            if len(self.timeline_reads) >= ROOTS_PER_TURN and not self.continue_history.wait(25):
                raise RuntimeError('browser did not observe the first acquisition slice')
            self.timeline_reads[key] += 1
        return super().load_session_snapshot(key)


def replace_geometry(page, period, now, zone, width=20):
    window = timeline_window(period, now, zone)
    page.evaluate('''({period, zone, window, width}) => {
        const chart = current.accountTimeline;
        clearTimeout(chart.timer);
        chart.generation++;
        chart.schedule = () => {};
        const sample = chart.view.series.find(row => row.points.some(point => Number(point?.amount) > 0));
        const peak = sample.points.find(point => Number(point?.amount) > 0);
        const series = chart.view.series.slice(0, width).map((row, i) => ({...row, account: 'Account with same name',
            quota: `Quota ${i + 1} with a deliberately long label to exercise clipping`,
            peak: sample.peak, ticks: sample.ticks, points: window.buckets.map(() => peak)}));
        const view = {period, timezone_id: zone, ...window, series, pending_buckets: []};
        chart.period = period;
        chart.cache.set(period, {view});
        chart.inspect(null);
        chart.focusKey = null;
        chart.draw();
    }''', dict(period=period, zone=zone, width=width,
              window=dict(buckets=window.buckets, slot_dates=window.dates, partial_buckets=window.partial,
                          future_buckets=window.future, start_ms=window.start, end_ms=now)))


def assert_geometry(plot, series_count):
    result = plot.evaluate('''plot => {
        const labels = [...plot.querySelectorAll('.account-timeline-slot-label')].map(label => label.getBBox());
        const targets = [...plot.querySelectorAll('.account-timeline-target')].map(target => target.getBBox());
        const bars = [...plot.querySelectorAll('.account-timeline-bar')].map(bar => [bar.dataset.bucket, bar.getBBox()]);
        return {ticks: labels.length, cells: targets.length, bars: bars.length,
            fit: targets.every((target, i) => {
                const tick = labels[i], columns = bars.filter(([slot]) => Number(slot) === i).map(([, box]) => box);
                return tick.x >= target.x && tick.x + tick.width <= target.x + target.width
                    && columns.every((bar, j) => bar.width >= .99 && bar.x >= target.x
                        && bar.x + bar.width <= target.x + target.width
                        && (!j || columns[j - 1].x + columns[j - 1].width < bar.x));
            })};
    }''')
    assert result == {'ticks': 30, 'cells': 30, 'bars': 30 * series_count, 'fit': True}, result


def assert_hover(page, plot, scroller, dates):
    # Real mouse movement across both edges and the middle of every cell. Bring
    # its center into the scrollport when needed, then probe each of its bars.
    targets = plot.locator('.account-timeline-target')
    for index, expected in enumerate(dates):
        target = targets.nth(index)
        points = target.evaluate('''(cell, index) => {
            const svg = cell.ownerSVGElement;
            const scroll = svg.parentElement;
            const clip = scroll.getBoundingClientRect();
            const old = cell.getBoundingClientRect();
            if (old.left < clip.left || old.right > clip.right)
                scroll.scrollLeft += (old.left + old.right - clip.left - clip.right) / 2;
            const bounds = cell.getBoundingClientRect();
            const bars = [...svg.querySelectorAll(`.account-timeline-bar[data-bucket="${index}"]`)];
            const pixels = bars.map(bar => {
                const box = bar.getBoundingClientRect();
                return [box.x + box.width / 2, box.bottom - 1];
            });
            return [[bounds.left + 1, bounds.top + 36], [bounds.right - 1, bounds.top + 36],
                [bounds.x + bounds.width / 2, bounds.top + 36], ...pixels]
                .filter(([x, y]) => x > clip.left && x < clip.right && y > clip.top && y < clip.bottom);
        }''', index)
        assert len(points) == 23, (index, points)
        for x, y in points:
            page.mouse.move(x, y)
            actual = plot.evaluate('''plot => {
                const chart = current.accountTimeline;
                const highlight = plot.querySelector('.account-timeline-highlight');
                const cell = [...plot.querySelectorAll('.account-timeline-target')]
                    .find(cell => Math.abs(Number(cell.getAttribute('x')) + 1 - Number(highlight.getAttribute('x'))) < .001);
                return [chart.tipTitle.textContent, cell?.dataset.slot, !chart.tooltip.hidden];
            }''')
            assert actual == [expected, str(index), True], (index, x, y, actual)
    assert scroller.evaluate('el => Math.abs(el.scrollWidth - el.clientWidth - el.scrollLeft) < 2')


def stress_plot(page, chart, screenshots):
    from playwright.sync_api import expect

    plot = chart.locator('.account-timeline-plot')
    scroller = chart.locator('.account-timeline-scroll')
    chooser = chart.get_by_role('button', name='Accounts & quotas', exact=False)
    legend = chart.get_by_role('group', name='Accounts and quotas')
    selected = chart.get_by_role('list', name='Selected Accounts and quotas')
    tip = chart.locator('.account-timeline-tip')
    labels = plot.locator('.account-timeline-slot-label')
    bands = plot.locator('.account-timeline-month-label')
    axis = chart.locator('.account-timeline-axis')
    status = chart.get_by_role('status')
    now = stamp('2026-11-20T10:15:00+01:00')
    replace_geometry(page, '30-days', now, 'Europe/Stockholm')
    dates = [(date(2026, 10, 22) + timedelta(days=i)).isoformat() for i in range(30)]
    assert labels.all_text_contents() == [str(int(day[-2:])) for day in dates]
    assert bands.all_text_contents() == ['October', 'November']

    chart.evaluate('chart => chart.scrollIntoView({block:"center"})')
    chooser.click()
    inputs = legend.get_by_role('checkbox')
    slots = plot.locator('.account-timeline-target')
    x_positions = slots.evaluate_all("cells => cells.map(cell => cell.getAttribute('x'))")
    for checked in (0, 1, 2, 5, 10, 20):
        # 'Weekly' was retained in the source journey; make each state exact.
        for i, checkbox in enumerate(inputs.all()):
            checkbox.set_checked(i < checked)
        if checked:
            assert_geometry(plot, checked)
            expect(selected.get_by_role('listitem')).to_have_count(checked)
        else:
            expect(selected).not_to_be_visible()
        assert slots.evaluate_all("cells => cells.map(cell => cell.getAttribute('x'))") == x_positions
    expect(chooser).to_contain_text('20 selected')
    page.keyboard.press('Escape')
    expect(legend).not_to_be_visible()
    chooser.tap()
    expect(legend).to_be_visible()
    assert legend.evaluate('''el => {
        const panel = el.parentElement, box = panel.getBoundingClientRect();
        return box.left >= 0 && box.right <= innerWidth && box.top >= 0 && box.bottom <= innerHeight
            && panel.scrollHeight > panel.clientHeight;
    }''')
    if screenshots:
        page.screenshot(path=screenshots / '03-chooser.png', animations='disabled')
    page.keyboard.press('Escape')

    layouts = []
    for theme, scheme in [('web', 'light'), ('web', 'dark'), ('classic', 'light')]:
        page.evaluate("(theme) => document.documentElement.dataset.theme = theme", theme)
        page.emulate_media(color_scheme=scheme, reduced_motion='reduce')
        for width in (360, 768, 1280, 1920):
            page.set_viewport_size({'width': width, 'height': 900})
            expect(labels).to_have_count(30)
            assert_geometry(plot, 20)
            inspect_layout = '''chart => {
                const chooser = chart.querySelector('.account-timeline-chooser').getBoundingClientRect();
                const graph = chart.querySelector('.account-timeline-graph').getBoundingClientRect();
                const scroller = chart.querySelector('.account-timeline-scroll').getBoundingClientRect();
                const legend = chart.querySelector('.account-timeline-selected').getBoundingClientRect();
                const ticks = [...chart.querySelectorAll('.account-timeline-tick')];
                const range = document.createRange();
                const widest = Math.max(...ticks.map(tick => {
                    range.selectNodeContents(tick);
                    return range.getBoundingClientRect().width;
                }));
                const swatch = chart.querySelector('.account-timeline-selected .account-timeline-swatch');
                const bar = chart.querySelector('.account-timeline-bar');
                return {toolbar: chooser.bottom <= graph.top && Math.abs(chooser.right - graph.right) < 2,
                    gap: graph.top - chart.querySelector('.account-timeline-header').getBoundingClientRect().bottom,
                    gutter: scroller.left - graph.left, widest,
                    alignment: Math.abs(legend.left - scroller.left), under: legend.top > scroller.bottom,
                    overflow: chart.scrollWidth > chart.clientWidth || document.documentElement.scrollWidth > innerWidth,
                    fill: getComputedStyle(swatch).backgroundColor, bar: getComputedStyle(bar).fill};
            }'''
            for zoom in (1, 1.5, 2):
                chart.evaluate('(el, zoom) => el.style.zoom = zoom', zoom)
                layout = chart.evaluate(inspect_layout)
                assert layout['toolbar'] and not layout['overflow'], (theme, width, zoom, layout)
                assert layout['gap'] >= 19 * zoom and 0 < layout['gutter'] - layout['widest'] < 13 * zoom, layout
                assert layout['alignment'] < 2 and layout['under'], layout
                assert layout['fill'] == layout['bar'] != 'rgba(0, 0, 0, 0)', layout
                layouts.append(layout)
            chart.evaluate("el => el.style.removeProperty('zoom')")
            chart.evaluate('el => el.scrollIntoView({block:"center"})')
            plot.focus()
            page.keyboard.press('Home')
            expect(tip).to_contain_text('2026-10-22')
            if screenshots:
                page.screenshot(path=screenshots / f'02-{theme}-{scheme}-{width}.png', animations='disabled')
    assert layouts[0]['fill'] != layouts[12]['fill'], layouts
    page.set_viewport_size({'width': 360, 'height': 850})
    chart.evaluate('el => el.scrollIntoView({block:"center"})')
    plot.focus()
    page.keyboard.press('End')
    expect(status).to_contain_text('2026-11-20. Partial')
    assert scroller.evaluate('el => el.scrollLeft > 0')
    assert axis.is_visible()
    assert tip.evaluate('''el => {
        const box = el.getBoundingClientRect(), values = el.querySelector('.account-timeline-tip-values');
        return box.right <= innerWidth && box.bottom <= innerHeight &&
            values.scrollHeight > values.clientHeight && values.children.length === 20;
    }''')
    page.keyboard.press('Tab')
    expect(tip.locator('.account-timeline-tip-values')).to_be_focused()
    page.keyboard.press('PageDown')
    page.wait_for_function("() => document.activeElement.scrollTop > 0")
    page.keyboard.press('Escape')
    expect(plot).to_be_focused()
    page.mouse.move(8, 8)
    for zoom in (1, 1.5, 2):
        page.set_viewport_size({'width': 900, 'height': 960})
        plot.evaluate('(plot, zoom) => plot.style.zoom = zoom', zoom)
        chart.evaluate('el => el.scrollIntoView({block:"center"})')
        assert_hover(page, plot, scroller, dates)
    plot.evaluate("plot => plot.style.removeProperty('zoom')")
    page.mouse.move(8, 8)
    page.set_viewport_size({'width': 360, 'height': 850})
    chart.evaluate('el => el.scrollIntoView({block:"center"})')
    cdp = page.context.new_cdp_session(page)
    cdp.send('Emulation.setPageScaleFactor', {'pageScaleFactor': 2})
    try:
        chooser.evaluate('el => el.click()')
        expect(legend).to_be_visible()
        page.wait_for_function('''() => {
            const {left, right, top, bottom} = current.accountTimeline.panel.getBoundingClientRect();
            const {offsetLeft, offsetTop, width, height} = visualViewport;
            return left >= offsetLeft && right <= offsetLeft + width &&
                top >= offsetTop && bottom <= offsetTop + height;
        }''')
        page.keyboard.press('Escape')
    finally:
        cdp.send('Emulation.setPageScaleFactor', {'pageScaleFactor': 1})
        page.set_viewport_size({'width': 900, 'height': 960})

    replace_geometry(page, '30-days', stamp('2027-01-02T11:00:00+01:00'), 'Europe/Stockholm')
    assert bands.all_text_contents() == ['December', '2026', 'Jan', '2027']
    replace_geometry(page, 'today', stamp('2026-10-25T23:50:00+01:00'), 'Europe/Stockholm')
    expect(labels).to_have_count(25)
    assert labels.all_text_contents()[2:4] == ['02¹', '02²']
    plot.focus()
    page.keyboard.press('Home')
    for title in ('2026-10-25 01:00–02:00', '2026-10-25 02:00–02:00 (first)',
                  '2026-10-25 02:00–03:00 (second)'):
        page.keyboard.press('ArrowRight')
        expect(tip.locator('strong')).to_have_text(title)
    replace_geometry(page, 'today', stamp('2026-03-29T23:50:00+02:00'), 'Europe/Stockholm')
    expect(labels).to_have_count(23)
    assert '02' not in labels.all_text_contents()
    replace_geometry(page, 'today', stamp('2026-11-20T23:50:00+01:00'), 'Europe/Stockholm')
    expect(labels).to_have_count(24)
    page.keyboard.press('End')
    expect(tip.locator('strong')).to_have_text('2026-11-20 23:00–Now')
    return len(layouts)


def check(browser, root, screenshots=None):
    from playwright.sync_api import expect

    (root / 'config').mkdir()
    shutil.copyfile(ROOT / 'config/default-config.jsonc', root / 'config/default-config.jsonc')
    high = subscription('github-copilot')
    high = replace(high, quotas=(*high.quotas, QuotaComponent('Model weekly', scope='model', model_id='GPT-Test'),
                                 *(QuotaComponent(f'Quota {i:02}') for i in range(1, 14))))
    low = subscription('openai')
    accounts = (high, low, subscription())
    source = ChartSource(accounts)
    started = time.monotonic()
    clock = lambda: NOV_5 + int(1000 * (time.monotonic() - started))
    provider_refreshes = []
    config, selection, service, _ = make_service(str(root), source, now_ms=clock())
    config['sessionWatchIntervalSeconds'] = 'auto'
    service.begin_account_refresh = lambda: provider_refreshes.append(clock())
    observed = set()

    def poll_accounts():
        if len(provider_refreshes) in observed:
            return None
        observed.add(len(provider_refreshes))
        snapshots = tuple(replace(account, fetched_at_ms=clock()) for account in accounts)
        return AccountUpdate(snapshots, tuple(account.key for account in accounts))

    service.poll_account_refresh = poll_accounts

    def workers(now):
        return make_service(str(root), source, now_ms=now)[2]

    coordinator = WebWatchCoordinator(selection=selection, report_service=service, config=config,
        service_factory=workers, clock_ms=clock, record_observations=False)
    host = WebHost(root, jobs=DispatchJobs(), live_factory=lambda: LiveAcquisition(coordinator))
    host.dispatcher = DataDispatcher(host.jobs)
    host.live.timeline_demand = host.dispatcher.account_timeline_demand
    host.start()
    host.publish_ready()
    context = browser.new_context(viewport={'width': 1280, 'height': 900}, has_touch=True, device_scale_factor=2)
    context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(host.server.origin + '/') else route.abort())
    page = context.new_page()
    errors, lookups, interests = [], [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda item: lookups.append(item.post_data_json['period'])
            if item.url.endswith('/api/accounts/timeline') else None)
    page.on('request', lambda item: interests.append(item.post_data_json.get('account_period'))
            if item.url.endswith('/api/interest') else None)
    try:
        page.goto(host.browser_url())
        page.get_by_role('link', name='Accounts', exact=True).click()
        chart = page.get_by_role('region', name='CCost', exact=True)
        chooser = chart.get_by_role('button', name='Accounts & quotas 3 selected')
        legend = chart.get_by_role('group', name='Accounts and quotas')
        plot = chart.locator('.account-timeline-plot')
        shades = plot.locator('.account-timeline-loading')
        rings = plot.locator('.account-timeline-ring')
        labels = plot.locator('.account-timeline-slot-label')
        axis = chart.locator('.account-timeline-axis')
        selected = chart.get_by_role('list', name='Selected Accounts and quotas')
        scroller = chart.locator('.account-timeline-scroll')
        tip = chart.locator('.account-timeline-tip')
        bars = chart.locator('.account-timeline-bar')
        status = chart.get_by_role('status')
        assert chart.locator('.ai-stats-periods button').all_text_contents() == ['Today', '7 days', '30 days', 'This month']
        expect(chart.get_by_role('button', name='This month')).to_have_attribute('aria-pressed', 'true')
        expect(shades).to_have_count(2, timeout=20_000)
        chooser.click()
        expect(legend.get_by_role('checkbox')).to_have_count(20)
        expect(legend.locator('input:checked')).to_have_count(3)
        page.keyboard.press('Escape')
        expect(chooser).to_be_focused()
        expect(legend).not_to_be_visible()
        expect(rings).to_have_count(1)
        page.emulate_media(reduced_motion='reduce')
        assert rings.first.evaluate("el => getComputedStyle(el).animationName") == 'none'
        expect(chart.get_by_text('Loading usage…', exact=True)).to_have_count(0)
        assert labels.all_text_contents() == list(map(str, range(1, 31)))
        assert page.evaluate('current.accountTimeline.view.pending_buckets') == [0, 2]
        assert len(source.timeline_reads) == 12
        expect(selected.get_by_role('listitem')).to_have_count(3)
        positions = labels.evaluate_all("labels => labels.map(label => label.getAttribute('x'))")
        plot.focus()
        page.keyboard.press('Home')
        expect(status).to_contain_text('Loading')
        page.keyboard.press('ArrowRight')
        expect(status).to_contain_text('$0.00')
        page.keyboard.press('ArrowRight')
        expect(status).to_contain_text('~$1.00 (so far)')
        if screenshots:
            chart.screenshot(path=screenshots / '01-cold-loading.png', animations='disabled')

        expect(rings).to_have_count(0, timeout=8000)
        expect(shades).to_have_count(2)
        assert len(source.timeline_reads) == 12
        source.continue_history.set()
        expect(shades).to_have_count(0, timeout=20_000)
        expect(rings).to_have_count(0)
        expect(chart.get_by_text('Loading usage…', exact=True)).to_have_count(0)
        expect(bars).to_have_count(3)
        expect(plot).to_be_focused()
        assert labels.evaluate_all("labels => labels.map(label => label.getAttribute('x'))") == positions
        expect(tip).not_to_contain_text('so far')
        assert not plot.locator('line, [stroke-dasharray]').count()
        assert chart.evaluate("el => getComputedStyle(el).backgroundColor === 'rgba(0, 0, 0, 0)'"
                              " && getComputedStyle(el).borderTopWidth === '0px'")
        assert chart.evaluate("(chart) => chart.previousElementSibling.classList.contains('watch-account-grid')")
        assert not chart.get_by_role('combobox').count()

        chart.get_by_role('button', name='Accounts & quotas', exact=False).click()
        chart.get_by_role('checkbox', name='GitHub Copilot Plus · 5-hour').uncheck()
        expect(axis.locator('span').last).to_have_text('$1.20')
        chart.get_by_role('checkbox', name='GitHub Copilot Plus · Weekly').check()
        expect(axis.locator('span').last).to_have_text('$1200.00')
        chart.get_by_role('checkbox', name='GitHub Copilot Plus · 5-hour').check()
        expect(selected.get_by_text('GitHub Copilot Plus · 5-hour', exact=True)).to_be_visible()
        expect(selected.get_by_text('GitHub Copilot Plus · Weekly', exact=True)).to_be_visible()
        assert 'checkbox' in chart.aria_snapshot()
        page.keyboard.press('Escape')
        pair = plot.locator('.account-timeline-bar[data-bucket="0"]')
        expect(pair).to_have_count(2)
        assert pair.evaluate_all('''([first, second]) => {
            const a = first.getBBox(), b = second.getBBox();
            return a.x + a.width < b.x && a.y === b.y && a.height === b.height
                && getComputedStyle(first).fill !== getComputedStyle(second).fill;
        }''')
        plot.focus()
        page.keyboard.press('Home')
        expect(status).to_contain_text('GitHub Copilot Plus · 5-hour: ~$1000.00')
        expect(status).to_contain_text('GitHub Copilot Plus · Weekly: ~$1000.00')
        assert 'Usage by time' in chart.aria_snapshot()
        page.keyboard.press('ArrowRight')
        expect(status).to_contain_text('GitHub Copilot Plus · Weekly: $0.00')
        first_x = pair.first.evaluate("bar => bar.getBBox().x + 2")
        weekly_tip = tip.locator('.account-timeline-tip-row').filter(has_text='GitHub Copilot Plus · Weekly')
        plot.hover(position={'x': first_x, 'y': 160})
        expect(weekly_tip.locator('span').last).to_have_text('~$1000.00')
        plot.tap(position={'x': first_x, 'y': 170})
        expect(weekly_tip.locator('span').last).to_have_text('~$1000.00')
        chart.get_by_role('button', name='Accounts & quotas', exact=False).click()
        for checkbox in legend.locator('input:checked').all()[::-1]:
            checkbox.uncheck()
        expect(chart.get_by_text('Select a series to show its usage.')).to_be_visible()
        expect(selected).not_to_be_visible()
        chart.get_by_role('checkbox', name='GitHub Copilot Plus · Weekly').check()
        expect(selected.get_by_role('listitem')).to_have_count(1)
        chart.get_by_role('heading', name='CCost').click()
        expect(legend).not_to_be_visible()
        # Accept normal passive lookup cadence, but never let a legend toggle
        # submit report/provider work or a second history acquisition.
        assert len(source.timeline_reads) == 25 and set(source.timeline_reads.values()) == {1}
        for name, period, count in (('Today', 'today', 6), ('7 days', '7-days', 8),
                                     ('30 days', '30-days', 30), ('This month', 'month', 30)):
            button = chart.get_by_role('button', name=name, exact=True)
            button.click()
            expect(button).to_have_attribute('aria-pressed', 'true')
            page.wait_for_function("(period) => current.accountTimeline.view?.period === period",
                                   arg=period, timeout=18_000)
            assert page.evaluate('current.accountTimeline.view.buckets.length') == count
        plot.focus()
        page.keyboard.press('End')
        expect(tip).to_have_text('2026-11-30Upcoming')
        expect(status).to_have_text('2026-11-30. Upcoming')
        chart.get_by_role('button', name='Accounts & quotas', exact=False).click()
        expect(chart.get_by_role('checkbox', name='GitHub Copilot Plus · Weekly')).to_be_checked()
        page.keyboard.press('Escape')
        assert len(source.timeline_reads) == 25 and set(source.timeline_reads.values()) == {1}
        assert len(provider_refreshes) == 1
        assert 'all' not in lookups and 'all' not in interests
        rejected_periods = page.evaluate("""async () => {
            const result = path => api(path, path.endsWith('timeline') ? {period: 'all', revision: null} :
              {tab: crypto.randomUUID(), section: 'accounts', visible: true, request: null, account_period: 'all'})
              .then(() => 'accepted', error => error.message);
            return [await result('/api/accounts/timeline'), await result('/api/interest')];
        }""")
        assert rejected_periods == ['invalid_request', 'invalid_request'], rejected_periods

        chart.get_by_role('button', name='Today', exact=True).click()
        page.wait_for_function("() => current.accountTimeline.view?.period === 'today'")
        before = page.evaluate('''() => {
            const chart = current.accountTimeline;
            const point = chart.view.series.find(row => row.primary && Number(row.peak) > 0);
            window.liveCueFlashes = 0;
            const observer = new MutationObserver(records => {
                for (const record of records) for (const node of record.addedNodes)
                    if (node.matches?.('path.account-timeline-ring')) window.liveCueFlashes++;
            });
            observer.observe(chart.layers, {childList: true});
            return {id: point.id, peak: Number(point.peak), revision: chart.cache.get('today').revision};
        }''')
        live_key = 'root-0014'
        source.replace_usage(14, NOV_1 + 4 * DAY_MS + 14_000, 100_000_000, accounts[2].ref)
        fact = source.snapshots[live_key]
        live_root = replace(fact.root, active=True)
        source.snapshots[live_key] = replace(fact, root=live_root, sessions=(live_root,), source_revision='revised-today')
        page.wait_for_function("""before => {
            const chart = current.accountTimeline, value = chart.cache.get('today');
            return value?.revision > before.revision &&
                Number(value.view.series.find(row => row.id === before.id)?.peak) > before.peak;
        }""", arg=before, timeout=30_000)
        assert page.evaluate('window.liveCueFlashes') == 0
        assert source.timeline_reads[live_key] == 2 and sum(source.timeline_reads.values()) == 26

        chart.get_by_role('button', name='30 days', exact=True).click()
        page.wait_for_function("() => current.accountTimeline.view?.period === '30-days'")
        layouts = stress_plot(page, chart, screenshots)

        page.get_by_role('link', name='Watch', exact=True).click()
        expect(page.locator('body')).to_have_attribute('data-section', 'watch')
        assert not chart.count()
        while_tabs = len(lookups)
        page.wait_for_timeout(1000)
        assert while_tabs == len(lookups)
        assert not host.dispatcher.account_timeline_demand()
        assert host.failure is None and host.live.failure is None and not errors, errors
        print(f'Accounts timeline PASS: {layouts} layouts, four periods, staged acquisition and quiet live revision, '
               f'{sum(source.timeline_reads.values())} history root reads, {len(provider_refreshes)} quota refresh')
    finally:
        source.continue_history.set()
        context.close()
        host.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', type=Path, help='Explicit local Chromium executable; CI uses bundled Playwright')
    parser.add_argument('--scratch', type=Path, help='Parent directory for isolated fixture files')
    parser.add_argument('--screenshots', type=Path, help='Owned directory for rendered chart evidence')
    options = parser.parse_args()
    if options.screenshots:
        options.screenshots.mkdir(parents=True, exist_ok=True)
    if options.browser is None:
        from development.tools.ci_web_beta import hosted_only
        hosted_only()
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory(prefix='accounts-timeline-', dir=options.scratch) as directory, sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=options.browser)
        try:
            check(browser, Path(directory), options.screenshots)
        finally:
            browser.close()


if __name__ == '__main__':
    main()
