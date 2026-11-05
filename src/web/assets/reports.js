'use strict';
// Report scope lives in the fragment; filters never become acquisition parameters.
const ReportRoutes = (() => {
  function resolve(hash) {
    let [path, query = ''] = (hash.replace(/^#\//, '') || 'models').split('?');
    if (['overview', 'models/all'].includes(path)) path = 'models';
    const params = new URLSearchParams(query);
    const session = /^sessions\/([A-Za-z0-9_-]{1,200})(\/live)?$/.exec(path);
    if (session) return {title: 'Session ' + session[1], section: 'sessions', session, request: null};
    const routes = {watch: ['Watch', null], live: ['Watch', null],
      models: ['Models', 'normal'],
      accounts: ['Accounts', 'normal'], sessions: ['Sessions', 'sessions'],
      reports: ['Date reports', null], 'token-mix': ['Token Mix · deep history', 'token-mix'],
       'cost-per-hour': ['Cost per Active Hour', 'cost-per-hour'], settings: ['Settings', null]};
    if (!routes[path]) return {title: 'Page not found', section: '', request: null};
    const [title, kind] = routes[path];
    let request = kind ? {kind} : null;
    if (path === 'sessions') {
      const offset = params.get('offset') || '0', epoch = params.get('epoch');
      if (!/^(0|[1-9][0-9]{0,6})$/.test(offset) || Number(offset) > 1000000 ||
          Number(offset) % 50 || epoch !== null && !/^[0-9a-f]{32}$/.test(epoch) || Number(offset) && !epoch)
        return {title: 'Invalid session page', section: 'sessions'};
      request = null;
    }
    if (path === 'reports' && params.has('date')) request = {kind: 'date', date_text: params.get('date')};
    return {title, section: path === 'live' ? 'watch' : path.split('/')[0], request, live: path === 'live' || path === 'watch',
      catalog: path === 'sessions', explicit: path === 'token-mix' || path === 'cost-per-hour' || path === 'reports' && !request, params};
  }
  function controls(parent, route) {
    parent.replaceChildren();
    const e = ReportView.element;
    parent.className = '';
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
