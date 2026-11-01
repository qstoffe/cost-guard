'use strict';
// Run in the synthetic fixture's outer page through the integrated browser.
// No browser driver, OS-setting mutation, providers or real user configuration.
window.checkThemeLayouts = async () => {
  const iframe = document.querySelector('iframe'), win = iframe.contentWindow, doc = win.document;
  // Review can defer animation frames while a long tool call owns the pane.
  // Observe actual DOM conditions, not frame counts or arbitrary sleep periods.
  const until = predicate => new Promise((resolve, reject) => {
    const observer = new MutationObserver(check);
    const deadline = setTimeout(() => { observer.disconnect(); reject(new Error('theme condition timeout: ' + win.location.hash)); }, 10000);
    function check() { if (predicate()) { observer.disconnect(); clearTimeout(deadline); resolve(); } }
    observer.observe(doc, {subtree: true, childList: true, attributes: true, characterData: true});
    check();
  });
  const frame = () => new Promise(resolve => {
    const channel = new MessageChannel();
    channel.port1.onmessage = () => { doc.body.getBoundingClientRect(); channel.port1.close(); channel.port2.close(); resolve(); };
    channel.port2.postMessage(null);
  });
  const go = async route => {
    window.themeLayoutProgress = route;
    if (win.location.hash !== '#/' + route) await new Promise(resolve => {
      win.addEventListener('hashchange', resolve, {once: true}); win.location.hash = '#/' + route;
    });
    await until(() => doc.body.dataset.section === route.split(/[/?]/)[0]);
    await frame(); await frame();
  };
  const routes = ['settings', 'models', 'accounts', 'sessions',
    'reports?date=2026-10-26:2026-10-27', 'token-mix', 'cost-per-hour', 'watch', 'sessions/root-0000'];
  for (const route of routes) {
    await go(route);
    if (route === 'token-mix') {
      doc.querySelector('#refresh').click();
      await until(() => doc.querySelector('#notice').textContent.includes('running:'));
      await fetch('/fixture/finish-history', {method: 'POST'});
    }
    if (['models', 'accounts', 'sessions', 'token-mix'].includes(route) || route.startsWith('reports?')) {
      await until(() => doc.querySelector('#notice').textContent.includes('Snapshot captured'));
    }
    if (route === 'sessions/root-0000') await until(() => doc.querySelector('.session-detail table'));
  }
  const cases = [];
  for (const theme of ['classic', 'web']) {
    await go('settings');
    await until(() => doc.querySelector('#web-theme') && !doc.querySelector('#web-theme').disabled);
    const select = doc.querySelector('#web-theme');
    if (select.value !== theme) {
      select.value = theme; select.dispatchEvent(new win.Event('change'));
      await until(() => !select.disabled && doc.documentElement.dataset.theme === theme);
    }
    for (const scheme of ['light', 'dark']) for (const width of [360, 1366, 1920]) {
      iframe.style.colorScheme = scheme; iframe.style.width = width + 'px';
      await frame(); await frame();
      for (const route of routes) {
        await go(route);
        cases.push({theme, scheme, width, route,
          preferredDark: win.matchMedia('(prefers-color-scheme: dark)').matches,
          background: win.getComputedStyle(doc.body).backgroundColor,
          overflow: doc.documentElement.scrollWidth > win.innerWidth,
          settingsLast: doc.querySelector('nav a:last-child').textContent === 'Settings',
          visibleSelects: [...doc.querySelectorAll('select')].filter(node => node.getClientRects().length).length});
      }
    }
  }
  window.themeLayoutCases = cases;
  return {cases: cases.length, overflows: cases.filter(value => value.overflow),
    wrongPreference: cases.filter(value => value.preferredDark !== (value.scheme === 'dark')),
    settingsChoices: cases.filter(value => value.route === 'settings').map(value => value.visibleSelects),
    backgrounds: [...new Set(cases.map(value => value.theme + '/' + value.scheme + '/' + value.background))]};
};
