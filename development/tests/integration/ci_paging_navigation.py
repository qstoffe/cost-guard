"""Rendered navigation and scroll evidence using only owned synthetic data."""
import subprocess
import time

from development.tests.integration.serve_navigation import ROOT, fixture
from development.tools.ci_web_beta import notice

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


def navigation(page, evidence, *, enforce):
    ready(page)
    page.evaluate(TRACE)
    observations = []
    for section in ('sessions', 'token-mix', 'accounts', 'watch'):
        evidence['scenario'] = ('current-' if enforce else 'baseline-') + section + '-models'
        route(page, section)
        ready(page)
        if section == 'sessions':
            if page.locator('.sessions-periods').count():
                page.get_by_role('button', name='All time', exact=True).click()
            page.wait_for_function('() => current.catalog?.data?.total===963 && !current.catalog.busy')
        if section == 'watch':
            page.wait_for_function('() => !!document.querySelector(".watch-card")')
        before = page.evaluate('''() => {
            document.activeElement?.blur();scrollTo(0,document.documentElement.scrollHeight);
            navigationTrace.length=0;recordNavigation('activation');return scrollY;
        }''')
        evidence['observed'] = dict(before=before)
        assert before > 100, section + ' must actually be scrolled'
        route(page, 'models')  # Page-local native anchor activation; no auto-reveal.
        ready(page)
        page.wait_for_function('() => current.benchmark && !current.benchmark.loading')
        page.evaluate('() => renderedFrames()')
        after = page.evaluate('() => ({y:scrollY,focus:document.activeElement.id,trace:navigationTrace})')
        evidence['observed'] = dict(before=before, **after)
        if enforce:
            assert after['y'] == 0
            assert after['focus'] == 'content'
            assert all(item['y'] == 0 for item in after['trace'] if item['phase'].startswith('frame-'))
        observations.append(dict(origin=section, before=before, **after))
    # Cached browser Back/Forward must apply the same new-route policy.
    route(page, 'token-mix')
    page.go_back()
    page.wait_for_function('() => current.section==="models"')
    page.evaluate('() => renderedFrames()')
    if enforce:
        assert page.evaluate('scrollY') == 0
    page.go_forward()
    page.wait_for_function('() => current.section==="token-mix"')
    notice('Models routes', dict(arm='current' if enforce else 'baseline', routes=[
        {key: item[key] for key in ('origin', 'before', 'y', 'focus')} for item in observations]))
    return observations


def cold_models(context, host, root, evidence):
    (root / 'models-delay').write_text('gated')
    host.dispatcher.invalidate()  # Only our disposable host's publications/jobs.
    page = context.new_page()
    try:
        page.goto(host.server.origin + '/#/sessions?period=all')
        page.wait_for_function('() => current.catalog?.usable && !current.catalog.busy', timeout=30000)
        page.evaluate(TRACE)
        before = page.evaluate('() => {scrollTo(0,document.documentElement.scrollHeight);recordNavigation("activation");return scrollY;}')
        assert before > 100
        page.wait_for_function('() => hostState.writable', timeout=15000)
        route(page, 'models')
        page.wait_for_function('() => !current.result && current.loading', timeout=15000)
        page.evaluate('() => renderedFrames()')
        assert page.evaluate('scrollY') == 0
        (root / 'models-release').write_text('release')
        ready(page)
        page.wait_for_function('() => current.benchmark && !current.benchmark.loading')
        assert page.locator('.benchmark-table tbody tr').count() == 4
        assert page.locator('.benchmark-table th').nth(4).get_attribute('aria-sort') == 'descending'
        page.evaluate('() => renderedFrames()')
        assert page.evaluate('scrollY') == 0
        trace = page.evaluate('navigationTrace')
        evidence['models_delayed'] = dict(before=before, trace=trace, after=0)
        notice('Models cold publication', dict(before=before, after=0, benchmark_rows=4))
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
        notice('Models same-route', dict(y=500, retained_sort=3))
        # A keyboard activation is tested separately from the bottom-of-page diagnostic.
        route(page, 'sessions')
        page.get_by_role('link', name='Models', exact=True).focus()
        page.keyboard.press('Enter')
        page.wait_for_function('() => current.section==="models"')
        page.evaluate('() => renderedFrames()')
        assert page.evaluate('scrollY') == 0
        evidence['scenario'] = 'session-detail-refresh-scroll'
        page.evaluate('() => {location.hash="#/sessions/root-0000";}')
        page.wait_for_function('() => current.detail?.data?.result.view.prompt_blocks[0].rows.length===70', timeout=30000)
        page.evaluate('() => scrollTo(0,500)')
        detail_y = page.evaluate('scrollY')
        assert detail_y == 500
        page.evaluate('() => current.detail.poll()')
        page.evaluate('() => renderedFrames()')
        assert page.evaluate('scrollY') == detail_y
        return dict(before=before, trace=trace, same_route_y=500, keyboard=True, detail_refresh_y=detail_y)
    except Exception:
        observed = page.evaluate('''() => ({section:current?.section,detail:!!current?.detail,
            rows:current?.detail?.body.children.length,total:current?.detail?.data?.total,
            detailStatus:current?.detail?.status.textContent,host:hostState.kind,
            hidden:document.hidden,message:current?.message})''')
        evidence['observed'] = observed
        notice('cold/detail state', dict(scenario=evidence.get('scenario'), **observed))
        raise
    finally:
        page.close()
        (root / 'models-delay').write_text('0')


def check_navigation_paging(browser, evidence):
    from playwright.sync_api import expect
    with fixture() as (host, root):
        current_asset = host.server.assets['app.js']
        baseline = subprocess.run(['git', 'show', BASELINE + ':src/web/assets/app.js'], cwd=ROOT, capture_output=True)
        context = browser.new_context(viewport={'width': 1366, 'height': 650})
        context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(host.server.origin + '/') else route.abort())
        def delayed_benchmark(route):
            response = route.fetch()
            time.sleep(.25)
            route.fulfill(response=response)
        context.route('**/api/models/benchmark', delayed_benchmark)
        errors = []
        try:
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(type(error).__name__))
            page.goto(host.browser_url())
            expect(page.locator('.overview-models')).to_be_visible(timeout=30000)
            if baseline.returncode == 0:
                host.server.assets['app.js'] = (baseline.stdout, current_asset[1])
                page.reload()
                assert not page.evaluate('navigate.toString().includes("New-route policy only")')
                evidence['models_baseline'] = navigation(page, evidence, enforce=False)
            else:
                evidence['models_baseline'] = dict(outcome='NOT RUN', reason='historical object absent in shallow checkout')
            host.server.assets['app.js'] = current_asset
            page.goto(host.server.origin + '/#/models')
            # A same-document hash goto does not reload JavaScript. Prove that the
            # current arm really executes shipped current bytes, not the baseline.
            page.reload()
            assert page.evaluate('navigate.toString().includes("New-route policy only")')
            expect(page.locator('.overview-models')).to_be_visible(timeout=30000)
            evidence['models_navigation'] = navigation(page, evidence, enforce=True)
            evidence['scenario'] = 'models-delayed-same-route-detail'
            evidence['models_delayed'] = cold_models(context, host, root, evidence)
            notice('Models delayed', evidence['models_delayed'])
            from development.tests.integration.ci_browser_zoom import check_zoom
            check_zoom(browser, host, root, evidence)
            assert not errors
            evidence['checks'].append('real job/dispatcher lifecycle: Models anchor navigation and delayed publication')
        except Exception:
            evidence['current_observation'] = page.evaluate('''() => ({section:current?.section,loading:current?.loading,
                failed:current?.failed,message:current?.message,stage:current?.stage})''')
            notice('scenario state', dict(scenario=evidence.get('scenario'), **evidence['current_observation']))
            raise
        finally:
            context.close()
