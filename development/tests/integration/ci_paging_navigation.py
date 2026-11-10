"""Rendered paging lifetime and navigation evidence using only owned synthetic data."""
import subprocess
import time

from development.tests.integration.serve_comparisons_paging import ROOT, fixture

BASELINE = '288b08358ad3b543d86447c68f40677ecb92fe25'
TRACE = '''() => {
    window.navigationTrace=[];
    window.recordNavigation=phase=>{
        if(navigationTrace.length>=12 && !phase.startsWith('frame-')) return;
        navigationTrace.push({phase,y:scrollY,section:current?.section,loading:!!current?.loading,
            focus:document.activeElement?.id || document.activeElement?.tagName,
            toolbarHidden:document.querySelector('.toolbar').hidden,
            models:document.querySelectorAll('.overview-models tbody tr').length,
            benchmark:document.querySelectorAll('.benchmark-table tbody tr').length});
    };
    const render=show;
    show=function(state){recordNavigation('before-show');render(state);recordNavigation('after-show');};
    new MutationObserver(()=>recordNavigation('dom-publication')).observe(output,{childList:true,subtree:true});
    window.renderedFrames=()=>new Promise(resolve=>requestAnimationFrame(()=>{
        recordNavigation('frame-1');requestAnimationFrame(()=>{recordNavigation('frame-2');resolve();});
    }));
}'''


def route(page, section):
    page.evaluate("section=>document.querySelector('nav a[href=\"#/'+section+'\"]').click()", section)
    page.wait_for_function('section=>current?.section===section', arg=section)


def ready(page):
    page.wait_for_function('() => current && !current.loading && !current.failed && (current.result || current.live || current.catalog?.usable)', timeout=30000)


def page_at(page, offset):
    page.wait_for_function('offset=>current.section==="comparisons" && !current.loading && !current.failed && current.result?.view.comparisons.offset===offset', arg=offset, timeout=30000)


def navigation(page, origin, *, enforce):
    ready(page)
    page.evaluate(TRACE)
    observations = []
    for section in ('comparisons', 'sessions', 'token-mix', 'accounts', 'watch'):
        route(page, section)
        ready(page)
        if section == 'comparisons':
            page_at(page, 0)
        if section == 'sessions':
            page.wait_for_function('() => current.catalog?.data?.total===963 && !current.catalog.busy')
        if section == 'watch':
            page.wait_for_function('() => !!document.querySelector(".watch-card")')
        before = page.evaluate('''() => {
            document.activeElement?.blur();scrollTo(0,document.documentElement.scrollHeight);
            navigationTrace.length=0;recordNavigation('activation');return scrollY;
        }''')
        assert before > 100, section + ' must actually be scrolled'
        route(page, 'models')  # Page-local native anchor activation; no auto-reveal.
        ready(page)
        page.wait_for_function('() => current.benchmark && !current.benchmark.loading')
        page.evaluate('() => renderedFrames()')
        after = page.evaluate('() => ({y:scrollY,focus:document.activeElement.id,trace:navigationTrace})')
        if enforce:
            assert after['y'] == 0
            assert after['focus'] == 'content'
            assert all(item['y'] == 0 for item in after['trace'] if item['phase'].startswith('frame-'))
        observations.append(dict(origin=section, before=before, **after))
    # Cached browser Back/Forward must apply the same new-route policy.
    route(page, 'comparisons')
    page.go_back()
    page.wait_for_function('() => current.section==="models"')
    page.evaluate('() => renderedFrames()')
    if enforce:
        assert page.evaluate('scrollY') == 0
    page.go_forward()
    page.wait_for_function('() => current.section==="comparisons"')
    return observations


def cold_models(context, host, root):
    (root / 'models-delay').write_text('2')
    host.dispatcher.invalidate()  # Only our disposable host's publications/jobs.
    page = context.new_page()
    try:
        page.goto(host.server.origin + '/#/sessions')
        page.wait_for_function('() => current.catalog?.usable && !current.catalog.busy', timeout=30000)
        page.evaluate(TRACE)
        before = page.evaluate('() => {scrollTo(0,document.documentElement.scrollHeight);recordNavigation("activation");return scrollY;}')
        assert before > 100
        route(page, 'models')
        assert page.evaluate('!current.result && current.loading')
        page.evaluate('() => renderedFrames()')
        assert page.evaluate('scrollY') == 0
        ready(page)
        page.wait_for_function('() => current.benchmark && !current.benchmark.loading')
        page.evaluate('() => renderedFrames()')
        assert page.evaluate('scrollY') == 0
        trace = page.evaluate('navigationTrace')
        # Same-route user actions/async updates cannot reapply new-route scroll.
        page.evaluate('''() => {
            scrollTo(0,500);
            document.querySelector('[data-benchmark-control="3"]').click();
            document.querySelector('[data-model-control="latest"]').click();
        }''')
        page.evaluate('() => current.benchmark.load(api,true)')
        page.evaluate('() => acquire(current)')
        page.evaluate('() => renderedFrames()')
        assert page.evaluate('scrollY') == 500
        assert page.locator('.benchmark-table th').nth(3).get_attribute('aria-sort') == 'descending'
        # A keyboard activation is tested separately from the bottom-of-page diagnostic.
        route(page, 'sessions')
        page.get_by_role('link', name='Models', exact=True).focus()
        page.keyboard.press('Enter')
        page.wait_for_function('() => current.section==="models"')
        page.evaluate('() => renderedFrames()')
        assert page.evaluate('scrollY') == 0
        return dict(before=before, trace=trace, same_route_y=500, keyboard=True)
    finally:
        page.close()
        (root / 'models-delay').write_text('0')


def paging(page, host, root):
    route(page, 'comparisons')
    page_at(page, 0)
    revision = page.evaluate('current.result.view.comparisons.revision')
    ranges = []
    for name, offset in [('Next', 10), ('Previous', 0)]:
        page.get_by_role('button', name=name, exact=True).click()
        page_at(page, offset)
        assert page.evaluate('current.result.view.comparisons.revision') == revision
        ranges.append(page.locator('.page-navigation').inner_text())
    # Large offsets use the same real pager callback, not a hand-built publication.
    for offset in (170, 320, 0):
        page.evaluate('''offset=>{const s=current;s.request={kind:'comparisons',comparison_offset:offset,
            comparison_revision:s.result.view.comparisons.revision};s.pageNavigation=true;s.orderRetried=false;
            demand.update();acquire(s);}''', offset)
        page_at(page, offset)
        assert page.evaluate('current.result.view.comparisons.revision') == revision
        assert page.locator('.comparison-group').count() == (1 if offset == 320 else 10)
        if offset == 320:
            assert page.get_by_role('button', name='Next', exact=True).is_disabled()
        ranges.append(page.locator('.page-navigation').inner_text())
    # Actual source failure/admission faults, not only immediate fake jobs.
    faults = []
    for mode in ('busy', 'source-error', 'preview-error'):
        (root / 'mode').write_text(mode)
        host.dispatcher.invalidate()
        page.get_by_role('button', name='Next', exact=True).click()
        page.wait_for_function('() => !current.loading && current.failed', timeout=30000)
        assert page.locator('.comparison-group').count() == 10
        assert page.evaluate('current.result.view.comparisons.offset') == 0
        faults.append(dict(mode=mode, message=page.locator('.comparison-feedback').inner_text()))
        (root / 'mode').write_text('stable')
        page.get_by_role('button', name='Retry Comparisons', exact=True).click()
        page_at(page, 10)
        page.get_by_role('button', name='Previous', exact=True).click()
        page_at(page, 0)
        # Rejecting host entries may retain a completed page10; discard only fixture jobs.
        host.dispatcher.invalidate()
    (root / 'mode').write_text('changed')
    page.get_by_role('button', name='Next', exact=True).click()
    page.wait_for_function('() => current.orderReset && !current.loading && !current.failed', timeout=30000)
    page_at(page, 0)
    assert 'history changed' in page.locator('.comparison-feedback').inner_text()
    (root / 'mode').write_text('stable')
    # Rebase to stable first, then stop work at a real comparison-groups callback.
    host.dispatcher.invalidate()
    page.evaluate('() => acquire(current)')
    page_at(page, 0)
    (root / 'mode').write_text('stalled')
    host.dispatcher.invalidate()
    started = time.monotonic()
    page.get_by_role('button', name='Next', exact=True).click()
    page.wait_for_function('() => current.loading && current.stage.includes("Preparing matched groups")', timeout=30000)
    route(page, 'models')
    ready(page)
    assert page.locator('.overview-models').is_visible()
    route(page, 'comparisons')
    page.wait_for_function('() => !current.loading && current.failed', timeout=60000)
    seconds = time.monotonic() - started
    assert 45 <= seconds < 60
    assert 'no forward progress for 45 seconds' in page.locator('.comparison-feedback').inner_text()
    assert page.locator('.comparison-group').count() == 10
    assert page.evaluate('current.result.view.comparisons.offset') == 0
    (root / 'mode').write_text('stable')
    page.get_by_role('button', name='Retry Comparisons', exact=True).click()
    page_at(page, 10)
    empty = []
    for count in (0, 1):
        (root / 'groups').write_text(str(count))
        host.dispatcher.invalidate()
        page.evaluate('() => {current.request={kind:"comparisons"};demand.update();return acquire(current);}')
        page_at(page, 0)
        assert page.locator('.comparison-group').count() == count
        if count == 0:
            assert not page.locator('.page-navigation').is_visible()
        else:
            assert page.get_by_role('button', name='Next', exact=True).is_disabled()
        empty.append(dict(groups=count, total=page.evaluate('current.result.view.comparisons.total')))
    return dict(ranges=ranges, faults=faults, stalled_seconds=round(seconds, 2), retry=True, empty=empty)


def check_navigation_paging(browser, evidence):
    from playwright.sync_api import expect
    with fixture() as (host, root):
        current_asset = host.server.assets['app.js']
        baseline = subprocess.run(['git', 'show', BASELINE + ':src/web/assets/app.js'], cwd=ROOT, capture_output=True)
        context = browser.new_context(viewport={'width': 1366, 'height': 650})
        context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(host.server.origin + '/') else route.abort())
        errors = []
        try:
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(type(error).__name__))
            page.goto(host.browser_url())
            expect(page.locator('.overview-models')).to_be_visible(timeout=30000)
            if baseline.returncode == 0:
                host.server.assets['app.js'] = (baseline.stdout, current_asset[1])
                page.reload()
                evidence['models_baseline'] = navigation(page, host.server.origin, enforce=False)
            else:
                evidence['models_baseline'] = dict(outcome='NOT RUN', reason='historical object absent in shallow checkout')
            host.server.assets['app.js'] = current_asset
            page.goto(host.server.origin + '/#/models')
            expect(page.locator('.overview-models')).to_be_visible(timeout=30000)
            evidence['models_navigation'] = navigation(page, host.server.origin, enforce=True)
            evidence['models_delayed'] = cold_models(context, host, root)
            evidence['paging_lifetime'] = paging(page, host, root)
            assert not errors
            evidence['checks'].append('real job/dispatcher/source lifecycle: pinned321-group pages, bounded faults/45s no-progress/Retry, empty/one; Models anchor navigation and delayed publication')
        finally:
            context.close()
