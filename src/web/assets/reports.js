'use strict';
// Report scope lives in the fragment; filters never become acquisition parameters.
const ReportRoutes = (() => {
  function resolve(hash) {
    const [path, query = ''] = (hash.replace(/^#\//, '') || 'overview').split('?');
    const params = new URLSearchParams(query);
    const session = /^sessions\/([A-Za-z0-9_-]{1,200})(\/live)?$/.exec(path);
    if (session) return {title: 'Session ' + session[1], section: 'sessions', session,
      request: {kind: 'session', session_id: session[1]}};
    const routes = {overview: ['Overview', 'normal'], watch: ['Watch', null], live: ['Watch', null],
      models: ['Models · selectable catalog', 'normal'], 'models/all': ['Models · all catalog', 'all-models'],
      accounts: ['Accounts', 'normal'], sessions: ['Sessions', 'sessions'],
      reports: ['Date reports', null], 'token-mix': ['Token Mix · deep history', 'token-mix'],
      'cost-per-hour': ['Cost per Active Hour', 'cost-per-hour']};
    if (!routes[path]) return {title: 'Page not found', section: '', request: null};
    const [title, kind] = routes[path];
    let request = kind ? {kind} : null;
    if (path === 'sessions') {
      const n = params.get('limit') || 'all', offset = params.get('offset') || '0', revision = params.get('revision');
      if (n !== 'all' && !/^[1-9][0-9]{0,3}$|^10000$/.test(n)) return {title: 'Invalid session limit', section: 'sessions'};
      if (!/^(0|[1-9][0-9]{0,6})$/.test(offset) || Number(offset) > 1000000 ||
          revision !== null && !/^[0-9a-f]{64}$/.test(revision) || Number(offset) && !revision)
        return {title: 'Invalid session page', section: 'sessions'};
      request.session_limit = n === 'all' ? null : Number(n);
      request.session_page_size = 50;
      request.session_offset = Number(offset);
      if (revision) request.session_catalog_revision = revision;
    }
    if (path === 'reports' && params.has('date')) request = {kind: 'date', date_text: params.get('date')};
    return {title, section: path === 'live' ? 'watch' : path.split('/')[0], request, live: path === 'live' || path === 'watch',
      explicit: path === 'token-mix' || path === 'cost-per-hour' || path === 'reports' && !request, params};
  }
  function controls(parent, route, restartSessions) {
    parent.replaceChildren();
    const e = ReportView.element;
    if (route.section === 'models') {
      parent.className = 'catalog-controls';
      for (const [href, text] of [['#/models', 'Selectable catalog'], ['#/models/all', 'All catalog + native rates']]) {
        const a = e('a', text); a.href = href;
        if ((route.request?.kind === 'all-models') === (href === '#/models/all')) a.setAttribute('aria-current', 'page');
        parent.append(a, e('span', ' '));
      }
    } else parent.className = '';
    if (route.section === 'sessions' && !route.session) {
      const advanced = e('details'); advanced.append(e('summary', 'Advanced session scope'));
      const form = e('form'), label = e('label', 'Available sessions: N (1–10000) or all '), input = e('input');
      input.value = route.params?.get('limit') || 'all'; input.required = true;
      input.pattern = 'all|[1-9][0-9]{0,3}|10000'; label.append(input);
      const submit = e('button', 'Apply scope'); submit.type = 'submit'; form.append(label, submit);
      form.addEventListener('submit', event => { event.preventDefault(); if (form.reportValidity()) location.hash = '#/sessions?limit=' + encodeURIComponent(input.value); });
      advanced.append(form); parent.append(advanced);
      const recent = e('a', 'Latest sessions / restart browsing'); recent.href = '#/sessions'; parent.append(recent);
      if (restartSessions) recent.addEventListener('click', restartSessions);
      parent.append(e('p', 'Recent first (CLI order). Search, filters and column sorting apply only to the loaded page. Catalog changes require restarting browsing; totals count available roots, not missing history.'));
    }
    if (route.section === 'reports') {
      const form = e('form'), start = e('input'), end = e('input');
      start.type = end.type = 'date'; start.required = true;
      const dates = (route.params?.get('date') || '').split(':'); start.value = dates[0]; end.value = dates[1] || '';
      const first = e('label', 'From '), last = e('label', 'Through (inclusive; optional) ');
      first.append(start); last.append(end);
      const submit = e('button', 'Capture date report'); submit.type = 'submit'; form.append(first, last, submit);
      form.addEventListener('submit', event => { event.preventDefault(); if (form.reportValidity()) location.hash = '#/reports?date=' + encodeURIComponent(start.value + (end.value ? ':' + end.value : '')); });
      parent.append(form, e('p', 'Configured-local calendar dates, not browser timezone. Reversed/impossible ranges are rejected, never normalized.'));
    }
    if (route.section === 'token-mix') parent.append(e('p', 'Explicit deep scan of all available history; may take time. Capture/Refresh starts it; Cancel stops only this finite job. Live continues. Reopening retains the frozen result in page memory.'));
    if (route.section === 'cost-per-hour') parent.append(e('p', 'Capture/Refresh explicitly reads available period history (120-second limit). Cancel stops only this view’s finite capture; Watch and accounts continue independently. Opening or revisiting this page never starts a scan.'));
  }
  return {resolve, controls};
})();
