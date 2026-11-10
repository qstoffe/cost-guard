"""One actual Chromium page-zoom navigation, never CSS zoom or desktop input."""
import json
from pathlib import Path
import tempfile

from development.tests.integration.ci_paging_navigation import TRACE, ready, route
from development.tools.ci_web_beta import notice


def check_zoom(browser, host, root, evidence):
    evidence['scenario'] = 'actual-browser-zoom'
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        extension = temporary / 'extension'
        extension.mkdir()
        (extension / 'manifest.json').write_text(json.dumps(dict(manifest_version=3,
            name='Synthetic navigation zoom probe', version='1.0',
            background=dict(service_worker='worker.js'))))
        (extension / 'worker.js').write_text('chrome.runtime.onInstalled.addListener(() => {});')
        context = browser.browser_type.launch_persistent_context(str(temporary / 'profile'),
            channel='chromium', headless=True, no_viewport=True,
            args=['--disable-extensions-except=' + str(extension), '--load-extension=' + str(extension)])
        worker = None
        try:
            worker = context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker', timeout=10000)
            page = context.pages[0] if context.pages else context.new_page()
            for extra in context.pages[1:]:
                extra.close()
            context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(host.server.origin + '/') else route.abort())
            page.goto(host.browser_url())
            ready(page)
            before = page.evaluate('() => ({width:innerWidth,dpr:devicePixelRatio})')
            zoom = worker.evaluate('''async () => {
                const tabs=await chrome.tabs.query({});
                if(tabs.length!==1) throw new Error('owned_zoom_tab_count');
                await chrome.tabs.setZoomSettings(tabs[0].id,{mode:'automatic',scope:'per-tab'});
                await chrome.tabs.setZoom(tabs[0].id,1.25);
                return chrome.tabs.getZoom(tabs[0].id);
            }''')
            page.wait_for_function('width=>innerWidth<width', arg=before['width'])
            after = page.evaluate('() => ({width:innerWidth,dpr:devicePixelRatio})')
            assert zoom == 1.25
            (root / 'models-release').unlink(missing_ok=True)
            (root / 'models-delay').write_text('gated')
            host.dispatcher.invalidate()
            page.goto(host.server.origin + '/#/sessions')
            page.reload()
            page.wait_for_function('() => current.catalog?.usable && !current.catalog.busy', timeout=30000)
            page.evaluate(TRACE)
            outgoing = page.evaluate('() => {scrollTo(0,document.documentElement.scrollHeight);recordNavigation("activation");return scrollY;}')
            assert outgoing > 100
            page.wait_for_function('() => hostState.writable', timeout=15000)
            route(page, 'models')
            page.wait_for_function('() => current.loading && !current.result', timeout=15000)
            page.evaluate('() => renderedFrames()')
            assert page.evaluate('scrollY') == 0
            (root / 'models-release').write_text('release')
            ready(page)
            page.wait_for_function('() => current.benchmark && !current.benchmark.loading')
            page.evaluate('() => renderedFrames()')
            assert page.evaluate('scrollY') == 0
            assert page.evaluate('document.activeElement.id') == 'content'
            evidence['browser_zoom'] = dict(zoom=zoom, before=before, after=after,
                outgoing=outgoing, y=0, trace=page.evaluate('navigationTrace'))
            notice('actual browser zoom', evidence['browser_zoom'])
        finally:
            if worker:
                try:
                    worker.evaluate('''async () => {
                        for(const tab of await chrome.tabs.query({})) await chrome.tabs.setZoom(tab.id,1);
                    }''')
                except Exception:
                    pass  # Disposal below closes every owned tab/profile even if a worker exited.
            context.close()
            (root / 'models-delay').write_text('0')
