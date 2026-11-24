"""Real headless Accounts journey over shipped HTTP, Live and synthetic source facts."""
import argparse
import re
from collections import Counter
from contextlib import contextmanager
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
from src.analysis.account_timeline import DAY_MS, PERIODS
from src.application.account_timeline import timeline_view
from src.domain import QuotaComponent, TokenUsage
from src.sources.errors import SourceConcurrentChangeError
from src.watch.account_timeline import ROOTS_PER_TURN
from src.watch.acquisition import LiveAcquisition
from src.watch.web_coordinator import WebWatchCoordinator
from src.web.dispatch import DataDispatcher
from src.web.host import WebHost


class ChartSource(SyntheticMonthSource):
    source_instance = 'synthetic-month'

    def __init__(self, accounts):
        super().__init__(0, 0, month_start_ms=NOV_1)
        self.clock_offset_ms = 0
        self.clock_scale = 1
        self.timeline_reads = Counter()
        self.first_read = Event()
        self.continue_history = Event()
        for i, tokens in enumerate((1_000_000_000, 600_000_000, 200_000_000)):
            self.replace_usage(i, NOV_1 + i * 1000, tokens, accounts[i].ref)
        for i, tokens in enumerate((100_000, 1_000_000, 1_000_000)):
            self.replace_usage(i + 3, NOV_1 + 2 * DAY_MS + i * 1000, tokens, accounts[i].ref)
        for index in range(6, 14):
            self.replace_usage(index, NOV_1 + 2 * DAY_MS + index * 1000, 0, accounts[1].ref)
        for index in range(14, 25):
            self.replace_usage(index, NOV_1 + 4 * DAY_MS + index * 1000,
                               1 if index == 14 else 0, accounts[2].ref)

    def replace_usage(self, index, at_ms, tokens, account):
        snapshot = make_root_snapshot(index, 1, month_start_ms=at_ms - index * 60_000)
        model = replace(snapshot.invocations[0].model, provider=account.provider_id)
        invocation = replace(snapshot.invocations[0], model=model, account_ref=account, tokens=TokenUsage(input=tokens),
                             cost=None)
        self.snapshots[snapshot.root.session_id] = replace(snapshot, complete=True, invocations=(invocation,))

    def load_session_snapshot(self, key):
        if current_thread().name.startswith('cost-guard-account-timeline'):
            if not self.first_read.wait(25):
                raise RuntimeError('browser did not observe the card-seeded chart')
            if len(self.timeline_reads) >= ROOTS_PER_TURN and not self.continue_history.wait(25):
                raise RuntimeError('browser did not observe the first acquisition slice')
            self.timeline_reads[key] += 1
        return super().load_session_snapshot(key)


def replace_geometry(page, period, now, zone, width=20, *, sample=None):
    view = timeline_view(period, now, zone, (), None, first_covered_ms=None, gaps=()).to_json()
    page.evaluate('''({period, zone, window, width, seed}) => {
        const chart = current.accountTimeline;
        clearTimeout(chart.timer);
        chart.generation++;
        chart.schedule = () => {};
        const sample = seed ?? chart.view.series.find(row => row.points.some(point => Number(point?.amount) > 0));
        const peak = sample.points.find(point => Number(point?.amount) > 0);
        const totals = [
            {amount: '123456', display: {credits: '123456', usd: '$1234.56'}},
            {amount: '123', display: {credits: '~123', usd: '~$1.23'}},
            {amount: '0.01', display: {credits: '~<0.1', usd: '~<$0.01'}},
            {amount: '0', display: {credits: '0', usd: '$0.00'}},
            null,
        ];
        const series = Array.from({length: width}, (_, i) => ({...sample,
            id: (i + 1).toString(16).padStart(8, '0'),
            account: i === width - 1 ? `Provider${'UnbrokenQuotaName'.repeat(4)}${i + 1}` :
                i % 3 ? `Provider · ${i % 3 === 1 ? 'Weekly' : 'Model daily'} quota ${i + 1}` : `Account ${i + 1}`,
            total: totals[i % totals.length],
            peak: sample.peak, ticks: sample.ticks, points: window.buckets.map(() => peak)}));
        const view = {period, timezone_id: zone, ...window, series, pending_buckets: []};
        chart.period = period;
        chart.cache.set(period, {view});
        chart.inspect(null);
        chart.focusKey = null;
        chart.draw();
    }''', dict(period=period, zone=zone, width=width, window=view, seed=sample))


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
                        && (!j || columns[0].x === bar.x && columns[0].width === bar.width
                            && Math.abs(columns[0].y + columns[0].height - bar.y - bar.height) < .001));
            })};
    }''')
    assert result == {'ticks': 30, 'cells': 30, 'bars': 30 * series_count, 'fit': True}, result


def assert_legend_geometry(selected, *, compact=False, wraps=False):
    layout = selected.evaluate('''list => {
        const plot = list.parentElement.querySelector('.account-timeline-scroll').getBoundingClientRect();
        const bounds = list.getBoundingClientRect();
        const range = document.createRange();
        const rows = [...list.children].map(row => {
            const [, name, value] = row.children;
            const label = name.getBoundingClientRect(), cell = value.getBoundingClientRect();
            range.selectNodeContents(name);
            const lines = [...range.getClientRects()];
            range.selectNodeContents(value.firstElementChild ?? value);
            const cost = range.getBoundingClientRect();
            return {column: cell.left, right: cost.right, labelRight: Math.max(...lines.map(line => line.right)),
                wrapped: lines.length > 1,
                fit: lines.every(line => line.left >= label.left - 1 && line.right <= label.right + 1) &&
                    cost.width > 0 && cost.left >= cell.left - 1 && cost.right <= bounds.right + 1 &&
                    getComputedStyle(value).fontVariantNumeric === 'tabular-nums'};
        });
        const [{column, right}] = rows;
        return {
            fit: bounds.right <= plot.right + 1 && rows.every(row => row.fit),
            aligned: rows.every(row => Math.abs(row.right - right) < 1 && Math.abs(row.column - column) < 1),
            gap: column - Math.max(...rows.map(row => row.labelRight)),
            room: plot.right - bounds.right,
            wrapped: rows.some(row => row.wrapped),
        };
    }''')
    assert layout['fit'] and layout['aligned'] and layout['gap'] >= 3, layout
    if compact:
        assert layout['room'] >= 32 and layout['gap'] <= 16 and not layout['wrapped'], layout
    if wraps:
        assert layout['wrapped'], layout


def assert_highlight(plot, index):
    bounds = plot.evaluate('''(plot, index) => {
        const band = plot.querySelector('.account-timeline-highlight').getBoundingClientRect();
        const text = plot.querySelector(`.account-timeline-slot-label[data-bucket="${index}"]`).getBoundingClientRect();
        const slot = plot.querySelector(`.account-timeline-target[data-slot="${index}"]`).getBoundingClientRect();
        const section = plot.querySelector('.account-timeline-month-label')?.getBoundingClientRect();
        return {left: band.left - slot.left, right: slot.right - band.right,
            labelLeft: text.left - band.left, labelRight: band.right - text.right, padding: band.bottom - text.bottom,
            clearance: (section?.top ?? plot.getBoundingClientRect().bottom) - band.bottom};
    }''', index)
    assert bounds['left'] > 0 and bounds['right'] > 0, (index, bounds)
    assert bounds['labelLeft'] >= 0 and bounds['labelRight'] >= 0, (index, bounds)
    assert bounds['padding'] >= 2 and bounds['clearance'] >= 0, (index, bounds)


def assert_loading_cues(plot, waiting, active=None):
    actual = plot.evaluate('''plot => {
        const shades = [...plot.querySelectorAll('.account-timeline-loading')];
        const cues = [...plot.querySelectorAll('path.account-timeline-ring, path.account-timeline-hourglass')];
        return {
            waiting: shades.map(node => +node.dataset.bucket),
            active: cues.find(node => node.matches('.account-timeline-ring'))?.dataset.bucket ?? null,
            correct: cues.length === shades.length && shades.every(shade => {
                const items = cues.filter(node => node.dataset.bucket === shade.dataset.bucket);
                if (items.length !== 1) return false;
                const [cue] = items, a = cue.getBBox(), b = shade.getBBox();
                return Math.abs((a.x + a.width / 2) - (b.x + b.width / 2)) < .05
                    && Math.abs((a.y + a.height / 2) - (b.y + b.height / 2)) < .05
                    && getComputedStyle(cue).pointerEvents === 'none';
            }),
            dots: plot.querySelectorAll('.account-timeline-partial').length
        };
    }''')
    assert actual == dict(waiting=waiting, active=None if active is None else str(active), correct=True, dots=0), actual


def assert_hover(page, plot, scroller, dates):
    # Real mouse movement across both edges and the middle of every cell. Bring
    # its center into the scrollport when needed, then probe each of its bars.
    targets = plot.locator('.account-timeline-target')
    for index, day in enumerate(dates):
        weekdays = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
        expected = f'{day} {weekdays[date.fromisoformat(day).weekday()]}'
        target = targets.nth(index)
        points = target.evaluate('''(cell, index) => {
            const svg = cell.ownerSVGElement;
            const scroll = svg.parentElement;
            const clip = scroll.getBoundingClientRect();
            const old = cell.getBoundingClientRect();
            if (old.left < clip.left || old.right > clip.right)
                scroll.scrollLeft += (old.left + old.right - clip.left - clip.right) / 2;
            const bounds = cell.getBoundingClientRect();
            const bar = svg.querySelector(`.account-timeline-bar[data-bucket="${index}"]`).getBoundingClientRect();
            return [[bounds.left + 1, bounds.top + 36], [bounds.right - 1, bounds.top + 36],
                [bounds.x + bounds.width / 2, bounds.top + 36], [bar.x + bar.width / 2, bar.bottom - 1]]
                .filter(([x, y]) => x > clip.left && x < clip.right && y > clip.top && y < clip.bottom);
        }''', index)
        assert len(points) == 4, (index, points)
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
        assert_highlight(plot, index)
    assert scroller.evaluate('el => Math.abs(el.scrollWidth - el.clientWidth - el.scrollLeft) < 2')


def stress_plot(page, chart, screenshots, *, sample):
    from playwright.sync_api import expect

    plot = chart.locator('.account-timeline-plot')
    scroller = chart.locator('.account-timeline-scroll')
    chooser = chart.get_by_role('button', name='Accounts', exact=False)
    legend = chart.get_by_role('group', name='Accounts', exact=True)
    selected = chart.get_by_role('list', name='Selected accounts')
    tip = chart.locator('.account-timeline-tip')
    labels = plot.locator('.account-timeline-slot-label')
    bands = plot.locator('.account-timeline-month-label')
    axis = chart.locator('.account-timeline-axis')
    status = chart.get_by_role('status')
    now = stamp('2026-11-20T10:15:00+01:00')
    replace_geometry(page, '30-days', now, 'Europe/Stockholm', sample=sample)
    dates = [(date(2026, 10, 22) + timedelta(days=i)).isoformat() for i in range(30)]
    assert labels.all_text_contents() == [str(int(day[-2:])) for day in dates]
    assert bands.all_text_contents() == ['October', 'November']

    chooser.scroll_into_view_if_needed()
    chooser.click()
    inputs = legend.get_by_role('checkbox')
    expect(inputs).to_have_count(20)
    slots = plot.locator('.account-timeline-target')
    x_positions = slots.evaluate_all("cells => cells.map(cell => cell.getAttribute('x'))")
    # The synthetic series start selected. Only drive inputs that change.
    selected_count = 20
    for checked in (0, 1, 3, 10, 20):
        for i in range(min(selected_count, checked), max(selected_count, checked)):
            inputs.nth(i).set_checked(i < checked)
        selected_count = checked
        if checked:
            assert_geometry(plot, checked)
            expect(selected.get_by_role('listitem')).to_have_count(checked)
            assert_legend_geometry(selected, compact=True)
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

    totals = selected.locator('.account-timeline-legend-value')
    for unit, expected in (
        ('credits', ['123456', '123', '<0.1', '0', '—']),
        ('usd', ['$1234.56', '$1.23', '<$0.01', '$0.00', '—']),
    ):
        page.evaluate('(unit) => { ReportView.setUnit(unit); current.accountTimeline.draw(); }', unit)
        assert totals.evaluate_all("cells => cells.map(cell => (cell.firstElementChild ?? cell).textContent)") == expected * 4

    layouts = []
    holiday_inks = []
    for theme, scheme in [('web', 'light'), ('web', 'dark'), ('classic', 'light')]:
        page.evaluate("(theme) => document.documentElement.dataset.theme = theme", theme)
        page.emulate_media(color_scheme=scheme, reduced_motion='reduce')
        for width in (360, 768, 1280, 1920):
            page.set_viewport_size({'width': width, 'height': 900})
            expect(labels).to_have_count(30)
            assert_geometry(plot, 20)
            # Read both styles in the same attached SVG snapshot. Resize and
            # redraw can replace a tspan between locator resolution and evaluation.
            holiday_ink, ordinary_ink = plot.evaluate('''plot => {
                const holiday = plot.querySelector('.account-timeline-non-working');
                const ordinary = plot.querySelector('.account-timeline-slot-label:not(:has(.account-timeline-non-working))');
                return [holiday, ordinary].map(label => label?.isConnected ? getComputedStyle(label).fill : '');
            }''')
            assert holiday_ink and ordinary_ink and holiday_ink != ordinary_ink, (holiday_ink, ordinary_ink)
            holiday_inks.append(holiday_ink)
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
                const bar = chart.querySelector('.account-timeline-bar');
                const swatch = chart.querySelector(`.account-timeline-selected [data-ink="${bar.dataset.ink}"]`);
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
                assert_legend_geometry(selected, compact=width == 1920, wraps=width == 360 and zoom == 2)
                layouts.append(layout)
            chart.evaluate("el => el.style.removeProperty('zoom')")
            scroller.evaluate('el => el.scrollIntoView({block:"center"})')
            plot.focus()
            page.keyboard.press('Home')
            expect(tip).to_contain_text('2026-10-22')
            assert_highlight(plot, 0)
            if screenshots:
                page.screenshot(path=screenshots / f'02-{theme}-{scheme}-{width}.png', animations='disabled')
    assert layouts[0]['fill'] != layouts[12]['fill'], layouts
    assert len(set(holiday_inks)) == 3, holiday_inks
    page.set_viewport_size({'width': 360, 'height': 850})
    scroller.evaluate('el => el.scrollIntoView({block:"center"})')
    plot.focus()
    page.keyboard.press('End')
    expect(status).to_contain_text('2026-11-20 Friday. Account')
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
        scroller.evaluate('el => el.scrollIntoView({block:"center"})')
        assert_hover(page, plot, scroller, dates)
    plot.evaluate("plot => plot.style.removeProperty('zoom')")
    page.mouse.move(8, 8)
    page.set_viewport_size({'width': 360, 'height': 850})
    scroller.evaluate('el => el.scrollIntoView({block:"center"})')
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
    expect(chart.locator('.account-timeline-range')).to_have_text('Range: 2026-12-04 – 2027-01-02')
    replace_geometry(page, '7-days', stamp('2026-11-22T00:15:00+01:00'), 'Europe/Stockholm')
    expect(labels.first).to_have_text('15/11')
    expect(labels.first.locator('.account-timeline-non-working')).to_have_text('15')
    expect(chart.locator('.account-timeline-range')).to_have_text('Range: 2026-11-15 – 2026-11-22')
    assert page.evaluate('current.accountTimeline.view.partial_buckets') == [0, 7]
    assert_loading_cues(plot, [])
    plot.focus()
    page.keyboard.press('End')
    expect(tip.locator('strong')).to_have_text('2026-11-22 Sunday')
    expect(status).to_contain_text('Swedish non-working day')
    assert_highlight(plot, 7)
    scroller.evaluate('el => el.scrollIntoView({block:"center"})')
    plot.locator('.account-timeline-target[data-slot="7"]').tap()
    expect(tip.locator('strong')).to_have_text('2026-11-22 Sunday')
    replace_geometry(page, '7-days', stamp('2027-01-01T00:00:00+01:00'), 'Europe/Stockholm')
    expect(chart.locator('.account-timeline-range')).to_have_text('Range: 2026-12-25 – 2026-12-31')
    replace_geometry(page, 'today', stamp('2026-10-25T02:25:00+01:00'), 'Europe/Stockholm')
    expect(chart.locator('.account-timeline-range')).to_have_text('Range: 2026-10-25 00:00–02:25 (second)')
    replace_geometry(page, 'today', stamp('2026-10-25T23:50:00+01:00'), 'Europe/Stockholm')
    expect(labels).to_have_count(25)
    assert labels.all_text_contents()[2:4] == ['02¹', '02²']
    expect(plot.locator('.account-timeline-non-working')).to_have_count(0)
    plot.focus()
    page.keyboard.press('Home')
    for title in ('2026-10-25 01:00–02:00', '2026-10-25 02:00–02:00 (first)',
                  '2026-10-25 02:00–03:00 (second)'):
        page.keyboard.press('ArrowRight')
        expect(tip.locator('strong')).to_have_text(title)
    assert_highlight(plot, 3)
    page.evaluate('''() => {
        const chart = current.accountTimeline;
        const view = chart.view;
        view.initial_pending_buckets = [2, 3];
        for (const row of view.series) row.points[2] = row.points[3] = null;
        chart.working = true;
        chart.draw();
    }''')
    for theme, scheme in [('web', 'light'), ('web', 'dark'), ('classic', 'light')]:
        page.evaluate("(theme) => document.documentElement.dataset.theme = theme", theme)
        page.emulate_media(color_scheme=scheme, reduced_motion='reduce')
        page.set_viewport_size({'width': 360, 'height': 900})
        plot.evaluate("plot => plot.style.zoom = 1.5")
        assert_loading_cues(plot, [2, 3], active=2)
    page.evaluate("() => { current.accountTimeline.working = false; current.accountTimeline.draw(); }")
    assert_loading_cues(plot, [2, 3])
    plot.evaluate("plot => plot.style.removeProperty('zoom')")
    page.set_viewport_size({'width': 900, 'height': 960})
    replace_geometry(page, 'today', stamp('2026-03-29T23:50:00+02:00'), 'Europe/Stockholm')
    expect(labels).to_have_count(23)
    assert '02' not in labels.all_text_contents()
    replace_geometry(page, 'today', stamp('2026-11-20T23:50:00+01:00'), 'Europe/Stockholm')
    expect(labels).to_have_count(24)
    page.keyboard.press('End')
    expect(tip.locator('strong')).to_have_text('2026-11-20 23:00–Now')
    return len(layouts)


@contextmanager
def chart_fixture(browser, root, source_setup=ChartSource):
    config = root / 'config/default-config.jsonc'
    config.parent.mkdir(exist_ok=True)
    if not config.exists():
        shutil.copyfile(ROOT / 'config/default-config.jsonc', config)
    high = subscription('github-copilot')
    high = replace(high, quotas=(*high.quotas, QuotaComponent('Model weekly', scope='model', model_id='GPT-Test'),
                                 *(QuotaComponent(f'Quota {i:02}') for i in range(1, 14))))
    low = replace(subscription('github-copilot', identity='second'), quotas=())
    accounts = (high, low, subscription())
    source = source_setup(accounts)
    started = time.monotonic()
    clock = lambda: NOV_5 + source.clock_offset_ms + int(1000 * source.clock_scale * (time.monotonic() - started))
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
    host.live.timeline_demand = host.dispatcher.account_timeline_foreground
    host.start()
    host.publish_ready()
    context = browser.new_context(viewport={'width': 1280, 'height': 900}, has_touch=True, device_scale_factor=2,
                                  locale='en-US', timezone_id='America/New_York')
    context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(host.server.origin + '/') else route.abort())
    page = context.new_page()
    errors, lookups, interests = [], [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda item: lookups.append(item.post_data_json['period'])
            if item.url.endswith('/api/accounts/timeline') else None)
    page.on('request', lambda item: interests.append(item.post_data_json.get('account_period'))
            if item.url.endswith('/api/interest') else None)
    try:
        yield page, host, coordinator, source, accounts, provider_refreshes, errors, lookups, interests
    finally:
        source.first_read.set()
        source.continue_history.set()
        context.close()
        host.close()


def check(browser, root, screenshots=None):
    from playwright.sync_api import expect

    with chart_fixture(browser, root) as (page, host, _, source, accounts, provider_refreshes, errors, lookups, interests):
        high_label = 'GitHub Copilot Plus · account 1'
        low_label = 'GitHub Copilot Plus · account 2'
        today_label = 'Claude Code Plus'
        page.goto(host.browser_url())
        page.wait_for_function("""() => liveValue?.view?.accounts?.accounts?.some(account =>
            Number(account.ccost_scopes.find(scope => scope.name === 'today')?.cost?.known_ccost) > 0)""")
        card_seen = time.monotonic()
        page.get_by_role('link', name='Accounts', exact=True).click()
        chart = page.get_by_role('region', name='CCost', exact=True)
        chooser = chart.get_by_role('button', name='Accounts 3 selected')
        legend = chart.get_by_role('group', name='Accounts', exact=True)
        plot = chart.locator('.account-timeline-plot')
        shades = plot.locator('.account-timeline-loading')
        rings = plot.locator('.account-timeline-ring')
        labels = plot.locator('.account-timeline-slot-label')
        axis = chart.locator('.account-timeline-axis')
        selected = chart.get_by_role('list', name='Selected accounts')
        scroller = chart.locator('.account-timeline-scroll')
        tip = chart.locator('.account-timeline-tip')
        bars = chart.locator('.account-timeline-bar')
        status = chart.get_by_role('status')
        expect(chart.locator('.ai-stats-periods button')).to_have_text(['Today', '7 days', '30 days', 'This month'])
        expect(chart.get_by_role('button', name='This month')).to_have_attribute('aria-pressed', 'true')
        expect(bars).to_have_count(1, timeout=20_000)
        assert not source.timeline_reads, 'Today painted before even the first chart root could be acquired'
        expect(bars.first).to_have_attribute('data-bucket', '4')
        expect(shades).to_have_count(4)
        page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
        first_paint = time.monotonic()
        chooser.click()
        expect(legend.get_by_role('checkbox')).to_have_count(3)
        expect(legend.locator('input:checked')).to_have_count(3)
        names = legend.locator('label').all_text_contents()
        assert names == page.locator('.watch-account-grid .account-card h4').all_text_contents()
        assert set(names) == {high_label, low_label, today_label}
        page.keyboard.press('Escape')
        expect(chooser).to_be_focused()
        expect(legend).not_to_be_visible()
        expect(rings).to_have_count(1)
        assert_loading_cues(plot, [0, 1, 2, 3], active=0)
        page.emulate_media(reduced_motion='reduce')
        assert rings.first.evaluate("el => getComputedStyle(el).animationName") == 'none'
        expect(chart.get_by_text('Loading usage…', exact=True)).to_have_count(0)
        assert labels.all_text_contents() == list(map(str, range(1, 31)))
        source.first_read.set()
        page.wait_for_function("() => JSON.stringify(current.accountTimeline.view?.pending_buckets) === '[0]'",
                               timeout=8000)
        assert page.evaluate('current.accountTimeline.view.pending_buckets') == [0]
        assert len(source.timeline_reads) == 12
        expect(selected.get_by_role('listitem')).to_have_count(3)
        positions = labels.evaluate_all("labels => labels.map(label => label.getAttribute('x'))")
        plot.focus()
        page.keyboard.press('Home')
        expect(status).to_contain_text(f'{today_label}: $200.00')
        page.keyboard.press('ArrowRight')
        expect(status).to_contain_text('$0.00')
        page.keyboard.press('ArrowRight')
        expect(status).to_contain_text(f'{low_label}: $1.00')
        if screenshots:
            chart.screenshot(path=screenshots / '01-cold-loading.png', animations='disabled')

        expect(rings).to_have_count(0, timeout=8000)
        expect(shades).to_have_count(0)
        assert_loading_cues(plot, [])
        assert len(source.timeline_reads) == 12
        source.continue_history.set()
        expect(shades).to_have_count(0, timeout=20_000)
        expect(rings).to_have_count(0)
        expect(chart.get_by_text('Loading usage…', exact=True)).to_have_count(0)
        expect(bars).to_have_count(7)
        assert page.evaluate('''name => {
            const cards = liveValue.view.accounts.accounts;
            const card = cards.find(row => row.observation.label === name);
            const point = current.accountTimeline.view.series.find(row => row.account === name).points[4];
            return +point.amount === +card.ccost_scopes.find(scope => scope.name === 'today').cost.known_ccost
                && !point.display.usd.startsWith('~');
        }''', today_label)
        completed_paint = time.monotonic()
        expect(plot).to_be_focused()
        assert labels.evaluate_all("labels => labels.map(label => label.getAttribute('x'))") == positions
        expect(tip).not_to_contain_text('so far')
        assert not plot.locator('line, [stroke-dasharray]').count()
        assert chart.evaluate("el => getComputedStyle(el).backgroundColor === 'rgba(0, 0, 0, 0)'"
                              " && getComputedStyle(el).borderTopWidth === '0px'")
        assert chart.evaluate("(chart) => chart.previousElementSibling.classList.contains('watch-account-grid')")
        assert not chart.get_by_role('combobox').count()

        chart.get_by_role('button', name='Accounts 3 selected').click()
        chart.get_by_role('checkbox', name=high_label, exact=True).uncheck()
        expect(axis.locator('span').last).to_have_text('$800.00')
        chart.get_by_role('checkbox', name=high_label, exact=True).check()
        expect(axis.locator('span').last).to_have_text('$1200.00')
        expect(selected.get_by_text(high_label, exact=True)).to_be_visible()
        expect(selected.get_by_text(low_label, exact=True)).to_be_visible()
        rows = selected.get_by_role('listitem')
        total = selected.locator('.account-timeline-legend-value')
        range_line = chart.locator('.account-timeline-range')
        expect(range_line).to_have_text('Range: 2026-11-01 – 2026-11-05')
        assert rows.evaluate_all('''rows => rows.every((row, i) => row.getBoundingClientRect().top >=
            (i ? rows[i - 1] : row.parentElement.previousElementSibling).getBoundingClientRect().bottom)''')
        expect(rows.filter(has_text=low_label)).to_have_text(f'{low_label}$601.00')
        stable_totals = total.all_text_contents()
        assert 'checkbox' in chart.aria_snapshot()
        page.keyboard.press('Escape')
        first = plot.locator('.account-timeline-bar[data-bucket="0"]')
        second = plot.locator('.account-timeline-bar[data-bucket="2"]')
        expect(first).to_have_count(3)
        expect(second).to_have_count(3)
        inks = [chart.locator('label').filter(has_text=name).locator('[data-ink]').get_attribute('data-ink')
                for name in (high_label, low_label, today_label)]
        stable_order = page.evaluate('''() => {
            const chart = current.accountTimeline;
            return chart.series.toSorted((a, b) => a.id.localeCompare(b.id)).map(row => String(chart.colors.get(row.id)));
        }''')
        for bars_at, order in ((first, inks), (second, [ink for ink in stable_order if ink != inks[0]] + inks[:1])):
            shape = bars_at.evaluate_all('''bars => bars.map(bar => {
                const {x, y, width, height} = bar.getBBox();
                return {x, y, width, height, ink: bar.dataset.ink, fill: getComputedStyle(bar).fill};
            })''')
            assert [bar['ink'] for bar in shape] == order, shape
            assert len({(bar['x'], bar['width'], round(bar['y'] + bar['height'], 3)) for bar in shape}) == 1
            assert len({bar['fill'] for bar in shape}) == 3
        heights = first.evaluate_all("bars => bars.map(bar => bar.getBBox().height)")
        assert all(abs(height / heights[0] - ratio) < .001 for height, ratio in zip(heights, (1, .6, .2)))
        if screenshots:
            cdp = page.context.new_cdp_session(page)
            try:
                for theme, scheme in (('web', 'light'), ('web', 'dark'), ('classic', 'light')):
                    page.evaluate("(theme) => document.documentElement.dataset.theme = theme", theme)
                    page.emulate_media(color_scheme=scheme, reduced_motion='reduce')
                    for mode in ('protanopia', 'deuteranopia', 'tritanopia'):
                        cdp.send('Emulation.setEmulatedVisionDeficiency', {'type': mode})
                        chart.screenshot(path=screenshots / f'overlays-{theme}-{scheme}-{mode}.png',
                                         animations='disabled')
            finally:
                cdp.send('Emulation.setEmulatedVisionDeficiency', {'type': 'none'})
                cdp.detach()
        plot.focus()
        page.keyboard.press('Home')
        expect(status).to_contain_text(f'{high_label}: $1000.00')
        expect(status).to_contain_text(f'{low_label}: $600.00')
        assert 'Usage by time' in chart.aria_snapshot()
        page.keyboard.press('ArrowRight')
        expect(status).to_contain_text(f'{low_label}: $0.00')
        page.keyboard.press('ArrowRight')
        expect(status).to_contain_text(f'{low_label}: $1.00')
        expect(status).to_contain_text(f'{today_label}: $1.00')
        target = plot.locator('.account-timeline-target[data-slot="2"]')
        target.hover()
        expect(tip).to_contain_text(f'{low_label}$1.00')
        target.tap()
        expect(tip).to_contain_text(f'{today_label}$1.00')
        assert total.all_text_contents() == stable_totals
        expect(tip.locator('strong')).to_have_text('2026-11-03 Tuesday')
        chart.get_by_role('button', name='Accounts 3 selected').click()
        for checkbox in legend.locator('input:checked').all()[::-1]:
            checkbox.uncheck()
        expect(chart.get_by_text('Select an account to show its usage.')).to_be_visible()
        expect(selected).not_to_be_visible()
        expect(range_line).not_to_be_visible()
        chart.get_by_role('checkbox', name=today_label, exact=True).check()
        expect(selected.get_by_role('listitem')).to_have_count(1)
        expect(range_line).to_have_text('Range: 2026-11-01 – 2026-11-05')
        chart.get_by_role('heading', name='CCost').click()
        expect(legend).not_to_be_visible()
        # Accept normal passive lookup cadence, but never let a legend toggle
        # submit report/provider work or a second history acquisition.
        assert len(source.timeline_reads) == 14 and set(source.timeline_reads.values()) == {1}, source.timeline_reads
        for name, period, count in (('Today', 'today', 6), ('7 days', '7-days', 8),
                                     ('30 days', '30-days', 30), ('This month', 'month', 30)):
            button = chart.get_by_role('button', name=name, exact=True)
            button.click()
            expect(button).to_have_attribute('aria-pressed', 'true')
            page.wait_for_function("(period) => current.accountTimeline.view?.period === period",
                                   arg=period, timeout=18_000)
            assert page.evaluate('current.accountTimeline.view.buckets.length') == count
            expect(plot.locator('.account-timeline-partial')).to_have_count(0)
        plot.focus()
        page.keyboard.press('End')
        expect(tip).to_have_text('2026-11-30 MondayUpcoming')
        expect(status).to_have_text('2026-11-30 Monday. Upcoming')
        chart.get_by_role('button', name='Accounts 1 selected').click()
        expect(chart.get_by_role('checkbox', name=today_label, exact=True)).to_be_checked()
        page.keyboard.press('Escape')
        assert len(source.timeline_reads) == 14 and set(source.timeline_reads.values()) == {1}
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
        expect(range_line).to_have_text('Range: 2026-11-05 00:00–05:00')
        before_total = total.inner_text()
        before = page.evaluate('''() => {
            const chart = current.accountTimeline;
            const point = chart.view.series.find(row => Number(row.peak) > 0);
            window.liveCueFlashes = 0;
            const observer = new MutationObserver(records => {
                for (const record of records) for (const node of record.addedNodes)
                    if (node.matches?.('path.account-timeline-ring')) window.liveCueFlashes++;
            });
            observer.observe(chart.layers, {childList: true});
            return {id: point.id, peak: Number(point.peak), revision: chart.cache.get('today').revision,
                sample: structuredClone(point)};
        }''')
        live_key = 'root-0014'
        source.replace_usage(14, NOV_1 + 4 * DAY_MS + 14_000, 100_000_000, accounts[2].ref)
        fact = source.snapshots[live_key]
        live_root = replace(fact.root, active=True)
        source.clock_offset_ms = 75_000
        source.snapshots[live_key] = replace(fact, root=live_root, sessions=(live_root,), source_revision='revised-today')
        page.wait_for_function("""before => {
            const chart = current.accountTimeline, value = chart.cache.get('today');
            return value?.revision > before.revision &&
                Number(value.view.series.find(row => row.id === before.id)?.peak) > before.peak;
        }""", arg=before, timeout=30_000)
        expect(range_line).to_have_text('Range: 2026-11-05 00:00–05:01')
        assert total.inner_text() != before_total
        usd_total = total.inner_text()
        page.evaluate("() => { ReportView.setUnit('credits'); current.accountTimeline.draw(); }")
        assert '$' not in total.inner_text()
        page.evaluate("() => { ReportView.setUnit('usd'); current.accountTimeline.draw(); }")
        expect(total).to_have_text(usd_total)
        assert page.evaluate('window.liveCueFlashes') == 0
        assert source.timeline_reads[live_key] == 1 and sum(source.timeline_reads.values()) == 15

        # Seed the synthetic geometry from the verified Today view, not from
        # a live period switch whose background acquire can evict a cached view.
        layouts = stress_plot(page, chart, screenshots, sample=before['sample'])

        page.get_by_role('link', name='Watch', exact=True).click()
        expect(page.locator('body')).to_have_attribute('data-section', 'watch')
        assert not chart.count()
        while_tabs = len(lookups)
        page.wait_for_timeout(1000)
        assert while_tabs == len(lookups)
        assert not host.dispatcher.account_timeline_foreground()
        assert host.failure is None and host.live.failure is None and not errors, errors
        print(f'Accounts timeline PASS: {layouts} layouts, four periods, staged acquisition and quiet live revision, '
              f'{sum(source.timeline_reads.values())} history root reads, {len(provider_refreshes)} quota refresh; '
              f'card-ready → first paint {(first_paint - card_seen) * 1000:.0f} ms, '
              f'card-ready → complete chart paint {(completed_paint - card_seen) * 1000:.0f} ms (gated reads)')


def check_unvisited(browser, root):
    from playwright.sync_api import expect

    class MonthSource(ChartSource):
        def __init__(self, accounts):
            super().__init__(accounts)
            self.clock_scale = 4
            for index in range(25, 217):
                at = NOV_1 + index % 4 * DAY_MS + index * 1000
                self.replace_usage(index, at, 1000, accounts[index % 3].ref)

    with chart_fixture(browser, root, MonthSource) as (page, host, coordinator, source, _, _, errors, lookups, interests):
        lane = coordinator.account_timeline
        page.goto(host.browser_url())
        page.get_by_role('link', name='Models', exact=True).click()
        expect(page.locator('body')).to_have_attribute('data-section', 'models')
        source.first_read.set()
        source.continue_history.set()
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            views = [lane.lookup(period)['view'] for period in PERIODS]
            if all(view and not view['pending_buckets'] and not view['initial_pending_buckets'] for view in views):
                break
            page.wait_for_timeout(100)
        else:
            raise AssertionError('host did not warm all four chart periods without Accounts')
        warmed = sum(source.timeline_reads.values())
        assert sum(source.timeline_reads.values()) == 206 and len(source.timeline_reads) == 206
        assert not lookups and not any(interests)
        assert not host.dispatcher.account_timeline_foreground()
        source.clock_offset_ms += 3_600_000
        start = time.monotonic()
        page.get_by_role('link', name='Accounts', exact=True).click()
        page.wait_for_function("""() => current.accountTimeline?.view?.series.some(row =>
            +row.points[2]?.amount > 0) && !current.accountTimeline.view.pending_buckets.length""", timeout=5000)
        chart = page.get_by_role('region', name='CCost', exact=True)
        expect(chart.locator('.account-timeline-plot .account-timeline-loading, .account-timeline-ring:visible')).to_have_count(0)
        assert sum(source.timeline_reads.values()) == warmed and not errors, errors
        assert host.failure is None and host.live.failure is None
        print(f'Unvisited Accounts PASS: {warmed} historical reads, four prepared periods; '
              f'entry to populated month {(time.monotonic() - start) * 1000:.0f} ms, zero replayed reads')


def check_best_effort(browser, root):
    from playwright.sync_api import expect

    class IncompleteSource(ChartSource):
        def __init__(self, accounts):
            super().__init__(accounts)
            self.replace_usage(25, NOV_1 + 2 * DAY_MS + 1_000, 1, accounts[1].ref)
            key = 'root-0025'
            snapshot = self.snapshots[key]
            call = snapshot.invocations[0]
            self.snapshots[key] = replace(snapshot, invocations=(replace(call,
                model=replace(call.model, model='alias-without-reference-rate')),))
            self.first_read.set()
            self.continue_history.set()

        def load_session_snapshot(self, key):
            if key in {'root-0000', 'root-0004'}:
                raise SourceConcurrentChangeError('fixture: two unavailable roots')
            return super().load_session_snapshot(key)

    with chart_fixture(browser, root, IncompleteSource) as (page, host, _, _, _, _, errors, _, _):
        page.goto(host.browser_url())
        page.get_by_role('link', name='Accounts', exact=True).click()
        page.wait_for_function("""() => current.accountTimeline?.view?.series.some(row =>
            +row.points[2]?.amount > 0) && !current.accountTimeline.view.initial_pending_buckets.length""")
        chart = page.get_by_role('region', name='CCost', exact=True)
        plot = chart.locator('.account-timeline-plot')
        bar = plot.locator('.account-timeline-bar[data-bucket="2"]')
        assert any(height > 0 for height in bar.evaluate_all("bars => bars.map(bar => bar.getBBox().height)"))
        low = page.evaluate("""() => current.accountTimeline.view.series
            .find(row => row.account.endsWith('account 2'))""")
        point = low['points'][2]
        assert 0 < float(point['amount']) < 0.1 and point['display'] == {'usd': '~<$0.01', 'credits': '~<0.1'}, point
        total = chart.get_by_role('listitem').filter(has_text=low['account']).locator('.account-timeline-legend-value')
        for unit in ('credits', 'usd'):
            qualified = low['total']['display'][unit]
            assert qualified.startswith('~') and float(low['total']['amount']) > 0, low['total']
            page.evaluate('(unit) => { ReportView.setUnit(unit); current.accountTimeline.draw(); }', unit)
            expect(total).to_have_text(qualified.removeprefix('~'))
        target = plot.locator('.account-timeline-target[data-slot="2"]')
        tip = chart.locator('.account-timeline-tip')
        status = chart.get_by_role('status')
        for inspect in (target.hover, target.tap):
            inspect()
            expect(tip).to_contain_text('account 2<$0.01')
        plot.focus()
        page.keyboard.press('Home')
        page.keyboard.press('ArrowRight')
        page.keyboard.press('ArrowRight')
        expect(status).to_contain_text('account 2: <$0.01')
        for surface in (tip, status):
            expect(surface).not_to_contain_text(re.compile(r'Unavailable|N/A|Unknown|Partial|Provisional'))
        expect(plot.locator('.account-timeline-ring')).to_have_count(0)
        assert host.failure is None and host.live.failure is None and not errors, errors
        print('Accounts best effort PASS: failed reads, tiny estimated wire value, SVG, hover, touch and keyboard')


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
            root = Path(directory)
            check(browser, root, options.screenshots)
            best_effort = root / 'best-effort'
            best_effort.mkdir()
            check_best_effort(browser, best_effort)
            unvisited = root / 'unvisited'
            unvisited.mkdir()
            check_unvisited(browser, unvisited)
        finally:
            browser.close()


if __name__ == '__main__':
    main()
