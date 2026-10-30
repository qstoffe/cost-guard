"""Approval-only synthetic Overview browser acceptance; isolated loopback only.

Requires already provisioned Playwright/Chromium. No personal profile or sources.
Screenshots remain in the caller's owned workspace; output never includes URLs.
"""
import argparse
from copy import deepcopy
from dataclasses import replace
import importlib.metadata
import json
from pathlib import Path
import sys
from threading import Event
from types import SimpleNamespace
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.account_views import account_report, NOW
from development.tests.fixtures.model_views import model_report
from development.tests.fixtures.scroll_views import ScrollData, ScrollJobs
from src.application.projection import project
from src.web.host import WebHost


class OverviewJobs(ScrollJobs):
    def __init__(self, data):
        super().__init__(data)
        self.mode = 'hold'
        self.phase = dict(phase='catalog', completed=2, total=10)

    def snapshot(self, key):
        if self.mode == 'hold':
            return dict(status='running', progress=self.phase)
        if self.mode in ('failed', 'report_timeout'):
            return dict(status='failed', error=self.mode)
        result = deepcopy(super().snapshot(key))
        if self.mode == 'partial':
            result['result']['source']['status'] = 'partial'
        return result


def fixture_host(previous, jobs, data):
    # Whole-document cold starts use distinct owned fixtures. Do not race the
    # four production SSE slots while old sockets await their next write.
    if previous:
        previous.close()
        assert previous.stopped.is_set() and not previous.thread.is_alive()
    host = WebHost(ROOT, jobs=jobs)
    host.live = SimpleNamespace(start=lambda: None, close=lambda: None, stopping=Event())
    host.start(); host.publish_ready(); host.events.publish('live', data.live)
    return host


def geometry(page):
    return page.evaluate('''() => {
      const table=document.querySelector('.overview-model-table'), body=table.tBodies[0];
      const head=[...table.tHead.rows[0].cells].map(e=>e.getBoundingClientRect().toJSON());
      const rows=[...body.rows], cells=[...rows[0].cells].map(e=>e.getBoundingClientRect().toJSON());
      const ratios=rows.map(r=>r.querySelector('.model-ratio').getBoundingClientRect().right);
      return {head, cells, ratioSpread:Math.max(...ratios)-Math.min(...ratios),
        body:body.getBoundingClientRect().toJSON(), rowCount:rows.length,
        scrollRange:body.scrollHeight-body.clientHeight,
        documentOverflow:document.documentElement.scrollWidth-innerWidth,
        last:rows.at(-1).getBoundingClientRect().toJSON(),
        headerOverflow:getComputedStyle(table.tHead).overflowY};
    }''')


def loading(page, expect):
    expect(page.locator('.overview-loading')).to_be_visible()
    for selector in ('#heading', '#refresh', '#cancel', '#notice', '.report-search', '#ccost-help'):
        expect(page.locator(selector)).not_to_be_visible()
    assert page.locator('#result table, #result section, #result details').count() == 0
    assert page.locator('#result progress').get_attribute('aria-valuetext').startswith('Approximately')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-browser', action='store_true', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--screenshots', type=Path, required=True)
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright, expect
    evidence = dict(outcome='RUNNING', cases=[], playwright=importlib.metadata.version('playwright'),
        limitations=['Synthetic frozen CLI projections, not private installed provider/history acquisition.',
            'Automated Chromium input, not physical touchpad/touch or screen-reader certification.',
            'No macOS, Firefox or Safari acceptance.'])
    args.screenshots.mkdir(parents=True, exist_ok=True)
    owner = unittest.TestCase()
    host = None
    try:
        data = ScrollData(owner)
        accounts = account_report().accounts_quotas
        accounts = replace(accounts, accounts=accounts.accounts[:-1] + (replace(accounts.accounts[-1],
            label='Long subscription account — international research and development'),))
        report = replace(model_report(), accounts_quotas=accounts)
        value = project(report, 'UTC').to_json()
        # At least 25 rows, varied publishers and a complete very long model name.
        value['model_comparison'] = [deepcopy(row) for _ in range(5) for row in value['model_comparison']]
        for index, row in enumerate(value['model_comparison']):
            row['publisher'] = 'A' if index % 2 else 'Long Publisher Name'
            if index % 9 == 0:
                row['release_date'] = None
            if index % 7 == 0:
                row['superseded'] = True
                row['display_roles'] = list(set(row.get('display_roles', []) + ['superseded']))
        data.reports['normal']['view'] = value
        jobs = OverviewJobs(data)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            evidence['chromium'] = browser.version
            for width in (360, 1280, 1920):
                for theme in ('light', 'dark'):
                    host = fixture_host(host, jobs, data)
                    jobs.mode = 'hold'
                    jobs.phase = dict(phase='catalog', completed=2, total=10)
                    context = browser.new_context(viewport=dict(width=width, height=900), color_scheme=theme, reduced_motion='reduce', has_touch=width == 360)
                    origin = host.server.origin
                    context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(origin + '/') else route.abort())
                    page = context.new_page()
                    errors = []
                    page.on('pageerror', lambda error: errors.append(type(error).__name__))
                    held = []
                    page.route('**/api/bootstrap', lambda route: held.append(route))
                    page.goto(host.browser_url(), wait_until='domcontentloaded')
                    page.wait_for_function('() => document.querySelector(".overview-loading progress")?.value === 0')
                    loading(page, expect)
                    page.screenshot(path=str(args.screenshots / f'{width}-{theme}-authorizing.png'))
                    assert held
                    held.pop().continue_()
                    page.wait_for_function('() => current.active != null')
                    samples = []
                    for phase, completed, total in [('catalog', 2, 10), ('history', 20, 40), ('projection', 0, None),
                            ('quotas', 2, 4), ('catalog', 1, 10), ('finalizing', 1, 1)]:
                        jobs.phase = dict(phase=phase, completed=completed, total=total)
                        # Use actual poll delivery rather than injecting renderer output.
                        label = {'catalog': 'Loading source', 'history': 'Loading source history', 'projection': 'Comparing models',
                                 'quotas': 'Acquiring accounts', 'finalizing': 'Preparing report'}[phase]
                        expect(page.locator('.overview-loading p')).to_contain_text(label)
                        samples.append(page.locator('.overview-loading progress').evaluate('e=>e.value'))
                        loading(page, expect)
                    assert samples == sorted(samples) and max(samples) < 100, samples
                    jobs.mode = 'success'
                    expect(page.locator('.overview-model-table')).to_be_visible()
                    expect(page.locator('.overview-loading')).to_have_count(0)
                    assert page.evaluate('current.percent') == 100
                    expect(page.locator('#host-state')).not_to_be_visible()
                    assert page.locator('#result').evaluate('e=>e.firstElementChild.className') == 'overview-models'
                    assert page.locator('.overview-model-table th').all_text_contents() == ['Publisher', 'Model', 'Relative CCost', 'Release date']
                    assert page.locator('.overview-model-table tbody tr').count() == len(value['model_comparison'])
                    assert page.locator('.overview-explanations').get_attribute('open') is None
                    assert page.locator('#result input, #result .pager, #result .snapshot, footer').count() == 0
                    case = geometry(page)
                    assert case['rowCount'] >= 25 and case['documentOverflow'] <= 0 and case['scrollRange'] > 0, case
                    assert case['ratioSpread'] < 1, case
                    for head, cell in zip(case['head'], case['cells']):
                        assert abs(head['x'] - cell['x']) < 1 and abs(head['right'] - cell['right']) < 1, case
                    assert case['body']['top'] >= case['head'][0]['bottom'] - 1, case
                    if width == 1920:
                        assert case['cells'][3]['width'] > case['cells'][1]['width'], case
                    rows = page.locator('.overview-model-table tbody')
                    old_head = case['head'][0]['y']
                    box = rows.bounding_box()
                    page.mouse.move(box['x'] + 40, box['y'] + 80); page.mouse.wheel(0, 250)
                    page.wait_for_function('() => document.querySelector(".overview-model-table tbody").scrollTop > 0')
                    assert abs(geometry(page)['head'][0]['y'] - old_head) < 1
                    rows.focus(); page.keyboard.press('End')
                    page.wait_for_function('''() => {const b=document.querySelector('.overview-model-table tbody'); return b.scrollHeight-b.clientHeight-b.scrollTop<2}''')
                    end = geometry(page)
                    assert end['last']['bottom'] <= end['body']['bottom'] + 1
                    page.keyboard.press('Home')
                    page.wait_for_function('() => document.querySelector(".overview-model-table tbody").scrollTop === 0')
                    if width == 360:
                        # Browser-emulated touch, not workstation/physical input.
                        session = context.new_cdp_session(page)
                        touch = dict(x=100, y=500)
                        session.send('Input.dispatchTouchEvent', dict(type='touchStart', touchPoints=[touch]))
                        for step in range(1, 9):
                            session.send('Input.dispatchTouchEvent', dict(type='touchMove', touchPoints=[dict(x=100, y=500-step*20)]))
                        session.send('Input.dispatchTouchEvent', dict(type='touchEnd', touchPoints=[]))
                        page.wait_for_function('() => document.querySelector(".overview-model-table tbody").scrollTop > 0')
                        rows.evaluate('e=>e.scrollTop=0')
                        session.detach()
                    page.screenshot(path=str(args.screenshots / f'{width}-{theme}-ready.png'))
                    if width == 360:
                        horizontal = page.locator('.overview-models')
                        horizontal.focus(); page.keyboard.press('ArrowRight')
                        page.wait_for_function('() => document.querySelector(".overview-models").scrollLeft > 0')
                        horizontal.evaluate('e=>e.scrollLeft=e.scrollWidth')
                        page.screenshot(path=str(args.screenshots / f'{width}-{theme}-right.png'))
                        horizontal.evaluate('e=>e.scrollLeft=0')
                    # Frozen report and actual text selection survive host updates.
                    page.evaluate('''() => { window.savedTable=document.querySelector('table'); const t=savedTable.querySelector('tbody td span').firstChild;
                      getSelection().setBaseAndExtent(t,0,t,1); }''')
                    requests = len(jobs.requests)
                    page.evaluate('liveConnection.resync()')
                    assert page.evaluate('savedTable===document.querySelector("table") && getSelection().toString().length===1')
                    assert len(jobs.requests) == requests
                    page.evaluate('getSelection().removeAllRanges()')
                    cards = page.locator('.compact-accounts .account-card')
                    heights = cards.evaluate_all('items=>items.map(e=>e.getBoundingClientRect().height)')
                    assert max(heights) - min(heights) < 1, heights
                    assert cards.count() == len(value['accounts_quotas']['accounts'])
                    for index, account in enumerate(value['accounts_quotas']['accounts']):
                        card = cards.nth(index)
                        expect(card.locator('h4')).to_have_text(account['observation']['label'])
                        for scope in account['ccost_scopes']:
                            text = scope['cost']['display']['account_ccost'] if scope['cost'] else '—'
                            expect(card).to_contain_text(f"CCost {scope['name']}: {text}")
                    summary = cards.first.locator('summary')
                    summary.tap() if width == 360 else summary.click()
                    assert cards.first.bounding_box()['height'] > heights[0]
                    assert cards.nth(1).bounding_box()['height'] < cards.first.bounding_box()['height']
                    summary.tap() if width == 360 else summary.click()
                    page.locator('.overview-explanations > summary').click()
                    expect(page.locator('#ccost-unit')).to_be_visible()
                    page.locator('#ccost-unit').select_option('usd')
                    assert len(jobs.requests) == requests
                    # Other routes keep controls and reuse the same frozen Normal report.
                    page.locator('nav a[href="#/models"]').click()
                    expect(page.locator('#refresh')).to_be_visible()
                    expect(page.locator('.report-search')).to_be_visible()
                    assert page.locator('th button').count() > 0
                    page.go_back()
                    expect(page.locator('.overview-model-table')).to_be_visible()
                    assert len(jobs.requests) == requests
                    page.evaluate("connectionStatus('OFFLINE — retained, not live. Check host.', {kind:'offline', writable:false})")
                    expect(page.locator('#host-state')).to_be_visible()
                    page.locator('#host-warning').focus()
                    expect(page.locator('#host-message')).to_be_visible()
                    page.locator('#host-warning').click()
                    expect(page.locator('#host-details')).to_be_visible()
                    assert page.evaluate('current.result != null')
                    # Empty and single-account grids use the same presenter and
                    # frozen values, without acquisition or unknown-to-zero casts.
                    for count in (0, 1):
                        page.evaluate('''count => {
                          const result=structuredClone(current.result);
                          result.view.accounts_quotas.accounts=result.view.accounts_quotas.accounts.slice(0,count);
                          ReportView.render(output,result,{section:'overview',pages:{}});
                        }''', count)
                        assert page.locator('.account-card').count() == count
                        if count == 0:
                            expect(page.locator('#result')).to_contain_text('No configured accounts detected.')
                    assert len(jobs.requests) == requests
                    assert not errors, errors
                    evidence['cases'].append(dict(width=width, theme=theme, progress=samples, geometry=case, account_heights=heights, outcome='PASS'))
                    context.close()
            # Actual report errors and partial completion, without perpetual activity.
            for mode in ('failed', 'report_timeout', 'partial'):
                host = fixture_host(host, jobs, data)
                jobs.mode = mode
                context = browser.new_context()
                context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(host.server.origin + '/') else route.abort())
                page = context.new_page(); page.goto(host.browser_url())
                expect(page.locator('.overview-loading')).to_have_count(0)
                if mode == 'partial':
                    expect(page.locator('#result .warning').first).to_contain_text('Partial source data')
                    assert page.evaluate('current.percent < 100')
                else:
                    expect(page.locator('#result [role=alert]')).to_contain_text('reload to retry' if mode == 'failed' else 'timed out')
                    assert page.locator('#result table').count() == 0
                evidence['cases'].append(dict(mode=mode, outcome='PASS'))
                context.close()
            for kind in ('unauthorized', 'offline'):
                host = fixture_host(host, jobs, data)
                context = browser.new_context()
                context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(host.server.origin + '/') else route.abort())
                page = context.new_page()
                def reject(route):
                    if kind == 'unauthorized':
                        route.fulfill(status=401, json=dict(error='authentication_required'))
                    else:
                        route.abort()
                page.route('**/api/bootstrap', reject)
                page.goto(host.browser_url())
                expect(page.locator('#result [role=alert]')).to_be_visible()
                expect(page.locator('.overview-loading')).to_have_count(0)
                expect(page.locator('#host-state')).to_be_visible()
                evidence['cases'].append(dict(mode=kind, outcome='PASS'))
                context.close()
            # A detected mid-acquisition outage stops activity immediately.
            # Recovery never submits a replacement job behind the user's back.
            host = fixture_host(host, jobs, data)
            jobs.mode = 'hold'; jobs.phase = dict(phase='history', completed=1, total=5)
            context = browser.new_context()
            context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(host.server.origin + '/') else route.abort())
            page = context.new_page(); page.goto(host.browser_url())
            page.wait_for_function('() => current.active != null')
            before = len(jobs.requests)
            context.set_offline(True)
            expect(page.locator('#result [role=alert]')).to_be_visible()
            expect(page.locator('.overview-loading')).to_have_count(0)
            context.set_offline(False)
            page.evaluate('liveConnection.resync()')
            page.wait_for_function('() => hostState.kind === "connected"')
            if page.evaluate('current.failed === true'):
                expect(page.locator('#result [role=alert]')).to_be_visible()
            else:
                expect(page.locator('.overview-loading')).to_be_visible()
            assert len(jobs.requests) == before
            host.events.close('test')
            expect(page.locator('#host-warning')).to_contain_text('stopped')
            expect(page.locator('.overview-loading')).to_have_count(0)
            expect(page.locator('#result [role=alert]')).to_be_visible()
            evidence['cases'].append(dict(mode='interrupted/reconnected/stopped', outcome='PASS'))
            context.close()
            browser.close()
        evidence['outcome'] = 'PASS'
    except Exception as error:
        evidence.update(outcome='FAIL', error=type(error).__name__,
            locations=[dict(file=Path(frame.filename).name, line=frame.lineno) for frame in traceback.extract_tb(error.__traceback__)])
        if isinstance(error, AssertionError) and not str(error).startswith('Locator'):
            evidence['assertion'] = str(error)
    finally:
        if host:
            host.close()
            evidence['owned_host_closed'] = host.stopped.is_set() and not host.thread.is_alive()
        owner.doCleanups()
        args.output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(evidence))
    return int(evidence['outcome'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
