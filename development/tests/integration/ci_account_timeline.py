"""Real headless Accounts journey over shipped HTTP, Live and synthetic source facts."""
import argparse
from collections import Counter
from dataclasses import replace
from pathlib import Path
import shutil
import sys
import tempfile
from threading import current_thread
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.account_periods import subscription
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests.fixtures.watch_runtime import make_service
from development.tests.integration.serve_data_dispatch import DispatchJobs
from development.tests.test_account_timeline import NOV_1, NOV_5
from src.accounts.acquisition import AccountUpdate
from src.analysis.account_timeline import DAY_MS
from src.domain import QuotaComponent, TokenUsage
from src.watch.acquisition import LiveAcquisition
from src.watch.web_coordinator import WebWatchCoordinator
from src.web.dispatch import DataDispatcher
from src.web.host import WebHost


class ChartSource(SyntheticMonthSource):
    def __init__(self, accounts):
        super().__init__(0, 0, month_start_ms=NOV_1)
        self.timeline_reads = Counter()
        self.replace_usage(0, NOV_1 + 1, 1_000_000_000, accounts[0].ref)
        self.replace_usage(1, NOV_1 + 2 * DAY_MS, 1_000_000, accounts[1].ref)

    def replace_usage(self, index, at_ms, tokens, account):
        snapshot = make_root_snapshot(index, 1, month_start_ms=at_ms - index * 60_000)
        model = replace(snapshot.invocations[0].model, provider=account.provider_id)
        invocation = replace(snapshot.invocations[0], model=model, account_ref=account, tokens=TokenUsage(input=tokens))
        self.snapshots[snapshot.root.session_id] = replace(snapshot, complete=True, invocations=(invocation,))

    def load_session_snapshot(self, key):
        if current_thread().name.startswith('cost-guard-account-timeline'):
            self.timeline_reads[key] += 1
        return super().load_session_snapshot(key)


def check(browser, root):
    from playwright.sync_api import expect

    (root / 'config').mkdir()
    shutil.copyfile(ROOT / 'config/default-config.jsonc', root / 'config/default-config.jsonc')
    high = subscription('github-copilot')
    high = replace(high, quotas=(*high.quotas, QuotaComponent('Model weekly', scope='model', model_id='GPT-Test')))
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
    context = browser.new_context(viewport={'width': 1280, 'height': 900})
    context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(host.server.origin + '/') else route.abort())
    page = context.new_page()
    errors, lookups = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda item: lookups.append(item.post_data_json['period'])
            if item.url.endswith('/api/accounts/timeline') else None)
    try:
        page.goto(host.browser_url())
        page.get_by_role('link', name='Accounts', exact=True).click()
        chart = page.get_by_role('region', name='Used CCost')
        legend = chart.get_by_role('group', name='Accounts and quotas')
        plot = chart.locator('.account-timeline-plot')
        expect(chart.get_by_role('button', name='This month')).to_have_attribute('aria-pressed', 'true')
        expect(legend.get_by_role('checkbox')).to_have_count(7)
        expect(legend.locator('input:checked')).to_have_count(3)
        expect(plot).to_have_attribute('tabindex', '0', timeout=20_000)
        assert chart.locator('.account-timeline-line').count() == 3
        assert chart.evaluate("(chart) => chart.previousElementSibling.classList.contains('watch-account-grid')")
        assert not chart.get_by_role('combobox').count()

        chart.get_by_role('checkbox', name='GitHub Copilot Plus · 5-hour').uncheck()
        expect(plot.locator('text').nth(4)).to_have_text('$1.20')
        chart.get_by_role('checkbox', name='GitHub Copilot Plus · Weekly').check()
        expect(plot.locator('text').nth(4)).to_have_text('$1200.00')
        chart.get_by_role('checkbox', name='GitHub Copilot Plus · 5-hour').check()
        plot.focus()
        page.keyboard.press('Home')
        expect(chart.get_by_role('status')).to_contain_text('GitHub Copilot Plus · 5-hour: ~$1000.00')
        expect(chart.get_by_role('status')).to_contain_text('GitHub Copilot Plus · Weekly: ~$1000.00')
        assert 'checkbox' in chart.aria_snapshot() and 'Usage by time' in chart.aria_snapshot()
        page.keyboard.press('ArrowRight')
        expect(chart.get_by_role('status')).to_contain_text('GitHub Copilot Plus · Weekly: $0.00')
        plot.hover(position={'x': 85, 'y': 220})
        expect(chart.locator('.account-timeline-tip')).to_contain_text('GitHub Copilot Plus · Weekly:')
        for checkbox in legend.get_by_role('checkbox').all():
            checkbox.uncheck()
        expect(chart.get_by_text('Select a series to show its usage.')).to_be_visible()
        chart.get_by_role('checkbox', name='GitHub Copilot Plus · Weekly').check()
        # Accept normal passive lookup cadence, but never let a legend toggle
        # submit report/provider work or a second history acquisition.
        assert source.timeline_reads == {'root-0000': 1, 'root-0001': 1}
        ids = ('Today', '7 days', '30 days', 'All time', 'This month')
        for name in ids:
            button = chart.get_by_role('button', name=name, exact=True)
            button.click()
            expect(button).to_have_attribute('aria-pressed', 'true')
            if name != 'This month':
                page.wait_for_function("(period) => current.accountTimeline.view?.period === period",
                    arg=dict(zip(ids, ('today', '7-days', '30-days', 'all', 'month')))[name], timeout=18_000)
        expect(chart.get_by_role('checkbox', name='GitHub Copilot Plus · Weekly')).to_be_checked()
        assert source.timeline_reads == {'root-0000': 1, 'root-0001': 1}
        assert len(provider_refreshes) == 1

        layouts = []
        page.evaluate("document.documentElement.dataset.theme = 'web'")
        for scheme in ['light', 'dark']:
            page.emulate_media(color_scheme=scheme)
            for width in (360, 768, 1280, 1920):
                page.set_viewport_size({'width': width, 'height': 900})
                layout = chart.evaluate('''chart => {
                    const graph = chart.querySelector('.account-timeline-graph').getBoundingClientRect(),
                        key = chart.querySelector('fieldset').getBoundingClientRect(),
                        swatch = chart.querySelector('fieldset svg line');
                    return {below: key.top >= graph.bottom, right: key.left >= graph.right,
                        overflow: chart.scrollWidth > chart.clientWidth, stroke: getComputedStyle(swatch).stroke};
                }''')
                assert layout['below' if width < 800 else 'right'] and not layout['overflow'], layout
                assert layout['stroke'] not in ('none', 'rgba(0, 0, 0, 0)')
                layouts.append((scheme, width, layout['stroke']))
        assert layouts[0][2] != layouts[4][2], layouts
        # Browser zoom changes the responsive layout without requiring any
        # real desktop/window focus. Use Chromium's isolated page scale.
        cdp = context.new_cdp_session(page)
        cdp.send('Emulation.setPageScaleFactor', {'pageScaleFactor': 2})
        expect(chart.get_by_role('checkbox', name='GitHub Copilot Plus · 5-hour')).to_be_visible()
        cdp.send('Emulation.setPageScaleFactor', {'pageScaleFactor': 1})

        page.get_by_role('link', name='Watch', exact=True).click()
        expect(page.locator('body')).to_have_attribute('data-section', 'watch')
        assert not chart.count()
        while_tabs = len(lookups)
        page.wait_for_timeout(1000)
        assert while_tabs == len(lookups)
        assert not host.dispatcher.account_timeline_demand()[0]
        assert host.failure is None and host.live.failure is None and not errors, errors
        print(f'Accounts timeline PASS: {len(layouts)} layouts, 5 periods, '
              f'{sum(source.timeline_reads.values())} history root reads, {len(provider_refreshes)} quota refresh')
    finally:
        context.close()
        host.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', type=Path, help='Explicit local Chromium executable; CI uses bundled Playwright')
    parser.add_argument('--scratch', type=Path, help='Parent directory for isolated fixture files')
    options = parser.parse_args()
    if options.browser is None:
        from development.tools.ci_web_beta import hosted_only
        hosted_only()
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory(prefix='accounts-timeline-', dir=options.scratch) as directory, sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=options.browser)
        try:
            check(browser, Path(directory))
        finally:
            browser.close()


if __name__ == '__main__':
    main()
