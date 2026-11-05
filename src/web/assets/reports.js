'use strict';
// Report scope lives in the fragment; filters never become acquisition parameters.
const ReportRoutes = (() => {
  function resolve(hash) {
    let [path, query = ''] = (hash.replace(/^#\//, '') || 'models').split('?');
    if (['overview', 'models/all'].includes(path)) path = 'models';
    // Retired date-page bookmarks discard their scope; Sessions has no date filter.
    if (path === 'reports') return {redirect: '#/sessions'};
    const params = new URLSearchParams(query);
    const session = /^sessions\/([A-Za-z0-9_-]{1,200})(\/live)?$/.exec(path);
    if (session) return {title: 'Session ' + session[1], section: 'sessions', session, request: null};
    const routes = {watch: ['Watch', null], live: ['Watch', null],
      models: ['Models', 'normal'],
      accounts: ['Accounts', null], sessions: ['Sessions', 'sessions'],
      'token-mix': ['Token Mix · deep history', 'token-mix'],
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
    return {title, section: path === 'live' ? 'watch' : path.split('/')[0], request, live: ['live', 'watch', 'accounts'].includes(path),
      catalog: path === 'sessions', explicit: path === 'token-mix' || path === 'cost-per-hour', params};
  }
  function controls(parent, route) {
    parent.replaceChildren();
    const e = ReportView.element;
    parent.className = '';
    if (route.section === 'token-mix') parent.append(e('p', 'Explicit deep scan of all available history; may take time. Capture/Refresh starts it; Cancel stops only this finite job. Live continues. Reopening retains the frozen result in page memory.'));
    if (route.section === 'cost-per-hour') parent.append(e('p', 'Capture/Refresh explicitly reads available period history (120-second limit). Cancel stops only this view’s finite capture; Watch and accounts continue independently. Opening or revisiting this page never starts a scan.'));
  }
  return {resolve, controls};
})();
