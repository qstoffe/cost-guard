"""Approval-only Chromium acceptance; no personal profile, sources or model calls.

Requires separately approved Playwright/browser provisioning and --approved-browser.
Not an automatic regression-suite or workstation/physical-device acceptance gate.
Uses shipped HTTP/security/SSE/assets and synthetic application results only.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import sys
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.scroll_views import ScrollData, ScrollJobs, ScrollDetails
from src.web.host import WebHost


def settle(page):
    # Wait for native smooth key/wheel scrolling to finish, not just event delivery.
    page.evaluate('''() => new Promise(resolve => {
      let previous = '', stable = 0;
      function frame() {
        const value = JSON.stringify([scrollY, ...[...document.querySelectorAll('.table-scroll')].map(e => [e.scrollTop, e.scrollLeft])]);
        stable = value === previous ? stable + 1 : 0; previous = value;
        if (stable >= 12) resolve(); else requestAnimationFrame(frame);
      }
      requestAnimationFrame(frame);
    })''')


def offsets(page, region):
    return region.evaluate('(e) => ({top:e.scrollTop, left:e.scrollLeft, page:scrollY})')


def scroll_case(page, region):
    region.evaluate('e => { e.scrollTop = 100; e.scrollLeft = 0; e.scrollIntoView({block:"center"}); e.focus({preventScroll:true}); }')
    settle(page)
    before = offsets(page, region)
    box = region.bounding_box()
    page.mouse.move(box['x'] + min(box['width'] / 2, 120), box['y'] + box['height'] / 2)
    page.mouse.wheel(0, 350)
    page.wait_for_function('(e) => e.scrollTop > 100', arg=region.element_handle())
    settle(page)
    wheel = offsets(page, region)
    assert wheel['top'] > before['top'] and abs(wheel['page'] - before['page']) < 1, (before, wheel)
    keyboard = {}
    for key, direction in [('PageDown', 1), ('PageUp', -1), ('ArrowDown', 1), ('ArrowUp', -1)]:
        region.evaluate('e => {e.scrollTop = 600; e.focus({preventScroll:true});}')
        settle(page)
        old = offsets(page, region)
        page.keyboard.press(key)
        settle(page)
        new = offsets(page, region)
        assert (new['top'] - old['top']) * direction > 1, (key, old, new)
        assert abs(new['page'] - old['page']) < 1, (key, old, new)
        keyboard[key] = round(new['top'] - old['top'], 2)
    horizontal = region.evaluate('e => e.scrollWidth - e.clientWidth')
    if horizontal > 0:
        page.mouse.wheel(250, 0)
        page.wait_for_function('(e) => e.scrollLeft > 0', arg=region.element_handle())
        settle(page)
        assert offsets(page, region)['left'] > 0
    region.evaluate('e => {e.scrollTop = e.scrollHeight; e.scrollLeft = e.scrollWidth;}')
    settle(page)
    geometry = region.evaluate('''e => {
      const box=e.getBoundingClientRect(), last=e.querySelector('tbody tr:last-child').getBoundingClientRect();
      const header=e.querySelector('thead th').getBoundingClientRect();
      return {lastVisible:last.bottom <= box.bottom + 1 && last.bottom > box.top,
        sticky:Math.abs(header.top - box.top - 1) < 2, overflow:getComputedStyle(e).overflowY};
    }''')
    # A footer may follow the last row; last row must still be inside the viewport.
    assert geometry['lastVisible'] and geometry['sticky'], geometry
    old = offsets(page, region)
    room = page.evaluate('document.documentElement.scrollHeight-innerHeight-scrollY')
    page.mouse.wheel(0, 300)
    settle(page)
    # Chromium may spend the first wheel consuming a fractional final table
    # pixel (CSSOM rounds scrollHeight/clientHeight). The next gesture must chain.
    page.mouse.wheel(0, 300)
    settle(page)
    boundary = offsets(page, region)
    if room > 1:
        assert boundary['page'] > old['page'], ('boundary chaining', old, boundary, room,
            region.evaluate('e => ({box:e.getBoundingClientRect().toJSON(), doc:document.scrollingElement.scrollHeight, h:innerHeight})'))
    else:
        assert abs(boundary['page'] - old['page']) < 1, 'already at document end'
    # At a document end, upward boundary chaining still proves the list is not a trap.
    region.evaluate('e => {e.scrollTop=0; e.scrollIntoView({block:"center"});}')
    settle(page)
    box = region.bounding_box()
    page.mouse.move(box['x'] + min(box['width'] / 2, 120), box['y'] + box['height'] / 2)
    up_before = page.evaluate('scrollY')
    page.mouse.wheel(0, -300); settle(page)
    page.mouse.wheel(0, -300); settle(page)
    up_delta = page.evaluate('scrollY') - up_before
    assert up_delta < -1, ('upward boundary chaining', up_before, up_delta)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    return dict(wheel_delta=wheel['top'] - before['top'], keyboard=keyboard,
                horizontal_range=horizontal, boundary_page_delta=boundary['page'] - old['page'],
                upward_boundary_delta=up_delta, document_end=room <= 1, **geometry)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-browser', action='store_true', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--screenshots', type=Path, required=True)
    parser.add_argument('--baseline-session', type=Path)
    parser.add_argument('--skip-layout-matrix', action='store_true', help='Focused race/SSE/detail diagnosis, not full layout acceptance')
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright, expect
    evidence = dict(outcome='RUNNING', matrix=[], limitations=[
        'Headless Chromium automated trusted input, not physical mouse/touchpad/touch or assistive technology proof.',
        'Synthetic application results and duplicated layout stress rows; not source/provider acquisition or total-value proof.',
        'Historical colleague browser/route/device remains unknown.'])
    evidence['layout_matrix_requested'] = not args.skip_layout_matrix
    args.screenshots.mkdir(parents=True, exist_ok=True)
    owner = unittest.TestCase()
    host = None
    try:
        data = ScrollData(owner)
        jobs, details = ScrollJobs(data), ScrollDetails(data)
        host = WebHost(ROOT, jobs=jobs)
        host.live = SimpleNamespace(details=details, start=lambda: None, close=lambda: None, stopping=Event())
        host.start(); host.publish_ready()
        host.events.publish('live', data.live)
        if args.baseline_session:
            host.server.assets['session.js'] = args.baseline_session.read_bytes(), 'text/javascript; charset=utf-8'
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                evidence['browser'] = browser.version
                context = browser.new_context(viewport=dict(width=1000, height=800), reduced_motion='reduce')
                origin = host.server.origin
                context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(origin + '/') else route.abort())
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(type(error).__name__))
                page.goto(host.browser_url())
                expect(page.locator('#notice')).to_contain_text('Snapshot captured')
                expect(page.locator('#status')).to_have_text('Live connected.')
                # Causal pending-response case with actual HTTP and native wheel input.
                page.goto(origin + '/#/sessions/root-0000/live')
                page.wait_for_function('() => current.detail?.data != null && !current.detail.busy')
                page.evaluate('current.detail.follow=false; current.detail.detach(); current.detail.attached=true;')
                region = page.locator('.session-detail .table-scroll')
                region.evaluate('e => {e.scrollTop=500; e.scrollIntoView({block:"center"});}')
                settle(page)
                before = offsets(page, region)
                details.pending.clear(); details.release.clear()
                page.evaluate('void current.detail.load()')
                # Pump routed network events before waiting on the server-side gate.
                page.evaluate('() => fetch("/health").then(r => r.json())')
                assert details.pending.wait(2), 'fixture response did not start'
                box = region.bounding_box()
                page.mouse.move(box['x'] + 100, box['y'] + box['height'] / 2)
                page.mouse.wheel(0, 350)
                page.wait_for_function('(e) => e.scrollTop > 500', arg=region.element_handle())
                settle(page)
                during = offsets(page, region)
                details.release.set()
                page.wait_for_function('() => !current.detail.busy')
                settle(page)
                after = offsets(page, region)
                evidence['response_race'] = dict(before=before, during=during, after=after)
                if args.baseline_session:
                    assert abs(after['page'] - during['page']) > 100, evidence['response_race']
                    evidence['outcome'] = 'EXPECTED BASELINE DEFECT'
                    return
                assert abs(after['page'] - during['page']) < 1 and abs(after['top'] - during['top']) < 1, evidence['response_race']
                for width in (() if args.skip_layout_matrix else (1000, 360)):
                    page.set_viewport_size(dict(width=width, height=800))
                    for route in ('watch', 'models', 'models/all', 'sessions', 'token-mix', 'reports?date=2026-10-26:2026-10-27', 'sessions/root-0000', 'sessions/root-0000/live'):
                        page.goto(origin + '/#/' + route)
                        # Wait for hash routing, not the still-visible previous table.
                        # Keep one EventSource: rapid document reloads consume server
                        # stream slots until the next write detects closed sockets.
                        key = 'session/root-0000' if route.startswith('sessions/root-0000') else '#/' + route
                        page.wait_for_function('(key) => current===views.get(key)', arg=key)
                        if route.startswith('sessions/root-0000'):
                            mode = 'live' if route.endswith('/live') else 'snapshot'
                            page.wait_for_function('() => current.detail?.data && !current.detail.busy')
                            if page.evaluate('current.detail.mode') != mode:
                                page.evaluate('() => current.detail.switchMode()')
                            page.wait_for_function('(mode) => current.detail.mode===mode && !current.detail.busy', arg=mode)
                        if route == 'token-mix':
                            expect(page.locator('#refresh')).to_be_enabled()
                            page.locator('#refresh').click()
                        expect(page.locator('#result .table-scroll').first).to_be_visible()
                        page.wait_for_function('() => !current.loading && (current.detail ? current.detail.data && !current.detail.busy : current.live ? current.watch?.result : current.result)')
                        region = page.locator('#result .table-scroll').first
                        assert region.locator('tbody tr').count() >= 50, (route, region.locator('tbody tr').count())
                        if route not in ('watch', 'sessions/root-0000', 'sessions/root-0000/live'):
                            region.evaluate('''e => {
                              window.savedRegion=e; e.scrollTop=250; e.scrollLeft=100;
                              window.savedScroll=[e.scrollTop,e.scrollLeft];
                              window.savedCell=e.querySelector('tbody td');
                              savedCell.tabIndex=0; savedCell.focus({preventScroll:true});
                              window.savedLeaf=savedCell.querySelector('span')?.firstChild || savedCell.firstChild;
                              if(savedLeaf.nodeType===3) getSelection().setBaseAndExtent(savedLeaf,0,savedLeaf,Math.min(5,savedLeaf.length));
                              window.savedText=getSelection().toString();
                            }''')
                            page.evaluate('() => liveConnection.resync()')
                            assert page.evaluate('savedRegion.isConnected && savedCell===document.activeElement && getSelection().toString()===savedText && savedRegion.scrollTop===savedScroll[0] && savedRegion.scrollLeft===savedScroll[1]')
                            page.evaluate('getSelection().removeAllRanges(); document.activeElement.blur()')
                        case = scroll_case(page, region)
                        evidence['matrix'].append(dict(width=width, route=route, **case))
                        # A local filter remains usable after keyboard/wheel browsing.
                        filters = page.locator('#result input[type=search]')
                        if filters.count():
                            filters.first.fill('no-such-synthetic-row')
                            expect(region.locator('tbody')).to_contain_text('No matching rows.' if route == 'watch' else '')
                            if route != 'watch':
                                assert region.locator('tbody tr').count() == 0
                            filters.first.fill('')
                            assert region.locator('tbody tr').count() >= 50
                        region.evaluate('e => { e.scrollLeft=0; e.scrollIntoView({block:"center"}); }')
                        settle(page)
                        name = f'{width}-{route.split("?")[0].replace("/", "-")}'
                        page.screenshot(path=str(args.screenshots / f'{name}.png'))
                        if case['horizontal_range'] > 0:
                            region.evaluate('e => e.scrollLeft=e.scrollWidth')
                            page.screenshot(path=str(args.screenshots / f'{name}-right.png'))
                    page.goto(origin + '/#/accounts')
                    page.wait_for_function('() => current===views.get("#/accounts") && !current.loading && current.result')
                    expect(page.locator('.account-card').first).to_be_visible()
                    assert page.locator('.account-card').count() >= 125
                    page.evaluate('scrollTo(0, 500); document.activeElement?.blur()')
                    settle(page)
                    old = page.evaluate('scrollY')
                    page.mouse.move(width / 2, 400); page.mouse.wheel(0, 350)
                    settle(page)
                    assert page.evaluate('scrollY') > old
                    keys = {}
                    for key, sign in [('PageDown', 1), ('PageUp', -1), ('ArrowDown', 1), ('ArrowUp', -1)]:
                        page.evaluate('scrollTo(0, 1000)'); settle(page)
                        page.keyboard.press(key); settle(page)
                        keys[key] = page.evaluate('scrollY') - 1000
                        assert keys[key] * sign > 1, keys
                    page.keyboard.press('Control+End'); settle(page)
                    assert page.locator('.account-card').last.evaluate('e => e.getBoundingClientRect().bottom <= innerHeight')
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    evidence['matrix'].append(dict(width=width, route='accounts', document_keyboard=keys, last_card_visible=True))
                # Real SSE publications must retain Watch nodes, selection, focus and anchors.
                page.set_viewport_size(dict(width=360, height=800))
                page.goto(origin + '/#/watch')
                region = page.locator('.watch-view .table-scroll')
                expect(region).to_be_visible()
                region.evaluate('e => {e.scrollTop=600; e.scrollLeft=150; e.scrollIntoView({block:"center"});}')
                page.evaluate('''() => {
                  const body=current.watch.body, edge=current.watch.scroll.getBoundingClientRect().top;
                  window.savedRow=[...body.children].find(r=>r.getBoundingClientRect().bottom>edge+80);
                  window.savedTop=savedRow.getBoundingClientRect().top;
                  window.savedOffsets=[current.watch.scroll.scrollLeft, scrollY];
                }''')
                changed = deepcopy(data.live)
                changed['view']['active_count'] = 0
                changed['view']['now_ms'] += 1000
                host.events.publish('live', changed)
                expect(page.locator('.watch-view .snapshot')).to_contain_text('Idle')
                assert page.evaluate('savedRow.isConnected && Math.abs(savedRow.getBoundingClientRect().top-savedTop)<1')
                changed['view']['active_count'] = 1
                changed['view']['now_ms'] += 1000
                changed['view']['rows'][0]['prompt']['preview'] = 'Growing earlier prompt ' * 80
                host.events.publish('live', changed)
                expect(page.locator('.watch-view .snapshot')).to_contain_text('Updating')
                assert page.evaluate('savedRow.isConnected && Math.abs(savedRow.getBoundingClientRect().top-savedTop)<1')
                assert page.evaluate('[current.watch.scroll.scrollLeft, scrollY].every((x,i)=>x===savedOffsets[i])')
                page.evaluate('''() => {
                  window.savedLeaf=savedRow.querySelector('td span').firstChild;
                  getSelection().setBaseAndExtent(savedLeaf,0,savedLeaf,Math.min(5,savedLeaf.length));
                  window.savedText=getSelection().toString();
                  window.savedCells=savedRow.firstChild;
                }''')
                changed['view']['now_ms'] += 1000
                host.events.publish('live', changed)
                page.wait_for_function('(now) => current.watch.result.view.now_ms === now', arg=changed['view']['now_ms'])
                assert page.evaluate('getSelection().toString()===savedText && savedLeaf.isConnected && savedRow.firstChild===savedCells')
                page.evaluate('getSelection().removeAllRanges(); savedRow.querySelector("summary").focus()')
                changed['view']['now_ms'] += 1000
                host.events.publish('live', changed)
                page.wait_for_function('(now) => current.watch.result.view.now_ms === now', arg=changed['view']['now_ms'])
                assert page.evaluate('savedRow.contains(document.activeElement) && savedRow.firstChild===savedCells')
                evidence['watch_sse'] = 'PASS idle/changing rows, visible anchor, horizontal/document offsets, selection and focused disclosure'
                # Paging and frozen/live semantics through real HTTP, 120 rows in 50-row pages.
                page.goto(origin + '/#/sessions/root-0000')
                page.wait_for_function('() => current.detail?.data != null && !current.detail.busy')
                summary = page.locator('.session-detail > p').nth(1).inner_text()
                for mode in ('snapshot', 'live'):
                    if page.evaluate('current.detail.mode') != mode:
                        label = 'Follow live' if mode == 'live' else 'Freeze snapshot'
                        page.get_by_role('button', name=label, exact=True).click()
                        page.wait_for_function('(mode) => current.detail.mode===mode && !current.detail.busy', arg=mode)
                    if page.evaluate('current.detail.offset') != 0:
                        page.get_by_role('button', name='First', exact=True).click()
                        page.wait_for_function('() => current.detail.offset===0 && !current.detail.busy')
                    for offset, button in ((50, 'Next'), (70, 'Jump to latest'), (0, 'First')):
                        page.get_by_role('button', name=button, exact=True).click()
                        page.wait_for_function('(offset) => current.detail.offset===offset && !current.detail.busy', arg=offset)
                        assert page.locator('.session-detail tbody tr').count() == 50
                        assert page.locator('.session-detail > p').nth(1).inner_text() == summary
                page.screenshot(path=str(args.screenshots / '360-live-detail.png'))
                assert not errors, errors
                evidence['detail_paging'] = 'PASS Snapshot/Live first/middle/latest, 50 rows, unchanged whole-session summary'
                page.evaluate('current.detail.detach(); current.detail.attached=true; current.detail.follow=false;')
                region = page.locator('.session-detail .table-scroll')
                region.evaluate('e => {e.scrollTop=600; e.scrollLeft=100; e.scrollIntoView({block:"center"});}')
                settle(page)
                page.evaluate('''() => {
                  window.savedRow=[...current.detail.body.children].find(r=>r.getBoundingClientRect().bottom>current.detail.scroll.getBoundingClientRect().top+80);
                  window.savedTop=savedRow.getBoundingClientRect().top;
                  window.savedOffsets=[current.detail.scroll.scrollLeft,scrollY];
                  window.savedControlsHeight=current.detail.controls.getBoundingClientRect().height;
                  window.savedLeaf=savedRow.querySelector('td span').firstChild;
                  savedRow.firstChild.tabIndex=0; savedRow.firstChild.focus({preventScroll:true});
                  getSelection().setBaseAndExtent(savedLeaf,0,savedLeaf,Math.min(5,savedLeaf.length));
                  window.savedText=getSelection().toString();
                }''')
                details.full['view']['prompt_blocks'][0]['rows'][0]['preview'] = 'Earlier detail growth ' * 80
                details.revision += 1
                page.evaluate('() => current.detail.load()')
                notice_growth = page.evaluate('''() => ({
                  rowDelta:savedRow.getBoundingClientRect().top-savedTop,
                  documentDelta:scrollY-savedOffsets[1],
                  controlsDelta:current.detail.controls.getBoundingClientRect().height-savedControlsHeight,
                  horizontalRetained:current.detail.scroll.scrollLeft===savedOffsets[0],
                  focusRetained:savedRow.contains(document.activeElement),
                  selectionRetained:savedLeaf.isConnected && getSelection().toString()===savedText})''')
                evidence['detail_notice_layout'] = notice_growth
                # Decision Delegate: native page anchoring may compensate for a
                # measured controls-height change; unexplained movement is not OK.
                assert abs(notice_growth['rowDelta']) < 1 and abs(notice_growth['documentDelta'] - notice_growth['controlsDelta']) < 1, notice_growth
                assert all(notice_growth[key] for key in ('horizontalRetained', 'focusRetained', 'selectionRetained')), notice_growth
                page.evaluate('''() => {
                  getSelection().removeAllRanges(); document.activeElement.blur();
                  savedTop=savedRow.getBoundingClientRect().top;
                  savedOffsets=[current.detail.scroll.scrollLeft,scrollY];
                }''')
                page.evaluate('() => current.detail.load()')
                growth = page.evaluate('''() => ({connected:savedRow.isConnected,
                  delta:savedRow.getBoundingClientRect().top-savedTop,
                  before:savedOffsets, after:[current.detail.scroll.scrollLeft,scrollY],
                  top:current.detail.scroll.scrollTop, follow:current.detail.follow,
                  revision:current.detail.revision, offset:current.detail.offset})''')
                evidence['detail_growth'] = growth
                assert growth['connected'] and abs(growth['delta']) < 1 and growth['before'] == growth['after'], growth
                unchanged = offsets(page, region)
                page.evaluate('() => current.detail.load()')
                assert offsets(page, region) == unchanged, 'geometry-neutral update retains all raw offsets'
                page.evaluate('''() => {
                  window.savedLeaf=savedRow.querySelector('td span').firstChild;
                  getSelection().setBaseAndExtent(savedLeaf,0,savedLeaf,Math.min(5,savedLeaf.length));
                  window.savedText=getSelection().toString(); window.savedRevision=current.detail.revision;
                }''')
                details.revision += 1
                page.evaluate('() => current.detail.load()')
                assert page.evaluate('current.detail.revision===savedRevision && savedLeaf.isConnected && getSelection().toString()===savedText')
                page.evaluate('getSelection().removeAllRanges(); savedRow.firstChild.tabIndex=0; savedRow.firstChild.focus({preventScroll:true})')
                page.evaluate('() => current.detail.load()')
                assert page.evaluate('current.detail.revision===savedRevision && savedRow.contains(document.activeElement)')
                page.evaluate('document.activeElement.blur()')
                page.evaluate('() => current.detail.load()')
                assert page.evaluate('(revision) => current.detail.revision===revision', str(details.revision))
                page.get_by_role('button', name='Freeze snapshot', exact=True).click()
                page.wait_for_function('() => current.detail.mode==="snapshot" && !current.detail.busy')
                frozen = page.evaluate('current.detail.revision')
                details.revision += 1
                page.evaluate('() => current.detail.load()')
                assert page.evaluate('current.detail.revision') == frozen
                page.set_viewport_size(dict(width=1000, height=800)); settle(page)
                page.set_viewport_size(dict(width=360, height=800)); settle(page)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert page.locator('#refresh').evaluate('e => getComputedStyle(e).transitionDuration') == '0s'
                evidence['detail_retention'] = 'PASS growth anchor, offsets, selection/focus defer then apply, frozen revision, resize and reduced motion'
                evidence['finite_requests'] = jobs.requests
                evidence['outcome'] = 'PASS'
            except Exception:
                evidence['page_status'] = page.locator('#status').inner_text()
                evidence['notice'] = page.locator('#notice').inner_text()
                page.screenshot(path=str(args.screenshots / 'failure.png'))
                raise
            finally:
                browser.close()
    except Exception as error:
        evidence.update(outcome='FAIL', error=type(error).__name__)
        if isinstance(error, AssertionError):
            evidence['assertion'] = str(error)
        evidence['failure_locations'] = [dict(file=Path(frame.filename).name, line=frame.lineno)
                                         for frame in traceback.extract_tb(error.__traceback__)]
        # Never serialize Playwright call logs, bootstrap URLs or browser credentials.
        raise RuntimeError('Browser acceptance failed; inspect the local assertion location') from None
    finally:
        if host:
            evidence['host_reason_before_close'] = host.reason
            evidence['host_failure'] = type(host.failure).__name__ if host.failure else None
            if host.live:
                host.live.details.release.set()
            host.close()
            evidence['owned_host_closed'] = host.stopped.is_set() and not host.thread.is_alive()
        owner.doCleanups()
        args.output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(evidence))


if __name__ == '__main__':
    main()
