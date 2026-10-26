'use strict';
// Report scope lives in the fragment; filters never become acquisition parameters.
const ReportRoutes = (() => {
  function resolve(hash) {
    const [path, query = ''] = (hash.replace(/^#\//, '') || 'overview').split('?');
    const params = new URLSearchParams(query);
    const session = /^sessions\/([A-Za-z0-9_-]{1,200})(\/live)?$/.exec(path);
    if (session) return {title: 'Session ' + session[1], section: 'sessions', session,
      request: {kind: 'session', session_id: session[1]}};
    const routes = {overview: ['Overview', 'normal'], live: ['Live', null],
      models: ['Models · selectable catalog', 'normal'], 'models/all': ['Models · all catalog', 'all-models'],
      accounts: ['Accounts', 'normal'], sessions: ['Sessions', 'sessions'],
      reports: ['Date reports', null], 'token-mix': ['Token Mix · deep history', 'token-mix']};
    if (!routes[path]) return {title: 'Page not found', section: '', request: null};
    const [title, kind] = routes[path];
    let request = kind ? {kind} : null;
    if (path === 'sessions') {
      const n = params.get('limit') || 'all';
      if (n !== 'all' && !/^[1-9][0-9]{0,3}$|^10000$/.test(n)) return {title: 'Invalid session limit', section: 'sessions'};
      request.session_limit = n === 'all' ? null : Number(n);
    }
    if (path === 'reports' && params.has('date')) request = {kind: 'date', date_text: params.get('date')};
    return {title, section: path.split('/')[0], request, live: path === 'live',
      explicit: path === 'token-mix' || path === 'reports' && !request, params};
  }
  function controls(parent, route) {
    parent.replaceChildren();
    const e = ReportView.element;
    if (route.section === 'models') {
      for (const [href, text] of [['#/models', 'Selectable catalog'], ['#/models/all', 'All catalog + native rates']]) {
        const a = e('a', text); a.href = href; parent.append(a, e('span', ' '));
      }
    }
    if (route.section === 'sessions' && !route.session) {
      const form = e('form'), label = e('label', 'Available sessions: N (1–10000) or all '), input = e('input');
      input.value = route.params?.get('limit') || 'all'; input.required = true;
      input.pattern = 'all|[1-9][0-9]{0,3}|10000'; label.append(input);
      const submit = e('button', 'Apply scope'); submit.type = 'submit'; form.append(label, submit);
      form.addEventListener('submit', event => { event.preventDefault(); if (form.reportValidity()) location.hash = '#/sessions?limit=' + encodeURIComponent(input.value); });
      parent.append(form);
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
  }
  return {resolve, controls};
})();
