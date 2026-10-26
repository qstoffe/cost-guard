'use strict';
// Erase the one-use credential before any fetch, preserving ordinary deep links.
let credential = new URLSearchParams(location.hash.slice(1)).get('bootstrap');
if (credential !== null) history.replaceState(null, '', '/#/overview');
const statusLine = document.getElementById('status');
const output = document.getElementById('result');
const notice = document.getElementById('notice');
const refresh = document.getElementById('refresh');
const cancel = document.getElementById('cancel');
const heading = document.getElementById('heading');
const views = new Map(); // Bounded page-memory only; never browser storage/history payloads.
let csrf = null;
let current = null;
let liveConnection = null;
let liveValue = null;
let sessionDetailAvailable = false;
async function api(path, value) {
  const options = {credentials: 'same-origin', cache: 'no-store'};
  if (value !== undefined) Object.assign(options, {method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CG-CSRF': csrf || ''}, body: JSON.stringify(value)});
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'request_unavailable');
  return data;
}
function show(state) {
  if (state !== current) return;
  refresh.disabled = !csrf || !state.request || state.loading;
  cancel.disabled = !state.active;
  output.setAttribute('aria-busy', state.loading ? 'true' : 'false');
  notice.textContent = state.message;
  if (state.detail) {
    state.detail.attach(output);
  } else if (state.live) {
    if (liveValue?.view) ReportView.renderLive(output, liveValue, state);
    else output.replaceChildren(ReportView.element('p', liveValue?.state || 'Live acquisition starting…'));
  } else if (state.result) ReportView.render(output, state.result, state);
  else output.replaceChildren(ReportView.element('p', state.loading ? 'Loading snapshot…' : state.message));
}
function failure(code) {
  const errors = {session_not_found: 'No matching session. It may have been removed or is unavailable in this source.',
    result_too_large: 'Report exceeds the finite result size limit; no truncated totals are shown. Use a specific session or the CLI.',
    report_timeout: 'Report timed out; no empty result was substituted.', cancelled: 'Report cancelled.',
    invalid_request: 'Invalid report scope. Check dates/limits; no alternate range was substituted.',
    pricing_unavailable: 'Reference pricing unavailable.', busy: 'Report service busy. Retry Refresh.'};
  return errors[code] || 'Source/report unavailable. Check the local source and retry Refresh.';
}
async function acquire(state) {
  if (state.loading) return;
  state.loading = true;
  state.message = state.result ? 'Refreshing; last known snapshot retained until success.' : 'Loading snapshot…';
  show(state);
  try {
    state.active = (await api('/api/reports', state.request)).id;
    show(state);
    while (true) {
      const job = await api('/api/jobs/' + state.active);
      if (!['queued', 'running'].includes(job.status)) {
        if (job.status !== 'complete' || !job.result || job.result.error) {
          throw new Error(job.result?.error?.code || job.error || job.status);
        }
        state.result = job.result;
        state.pages = {};
        state.message = 'Snapshot captured. Navigation and source activity do not update it.';
        break;
      }
      state.message = `${job.status}: ${job.progress.phase} · ${job.progress.completed ?? 0}${job.progress.total == null ? '' : '/' + job.progress.total}. ${state.result ? 'Last known snapshot retained.' : ''}`;
      // Do not redraw a retained report while polling: keep selection and scroll useful.
      if (state === current) notice.textContent = state.message;
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  } catch (error) {
    state.message = `${state.result ? 'STALE — last known snapshot retained. ' : ''}${failure(error.message)}`;
  } finally { state.loading = false; state.active = null; show(state); }
}
function navigate() {
  const route = ReportRoutes.resolve(location.hash), match = route.session;
  const key = match ? 'session/' + match[1] : location.hash || '#/overview';
  heading.textContent = route.title;
  ReportRoutes.controls(document.getElementById('scope-controls'), route);
  for (const item of document.querySelectorAll('nav a')) {
    if (item.getAttribute('href') === '#/' + route.section) item.setAttribute('aria-current', 'page');
    else item.removeAttribute('aria-current');
  }
  if (!views.has(key)) {
    // Never evict in-flight work. Its completion belongs to its original view.
    if (views.size >= 12) {
      const victim = [...views].find(([, value]) => !value.loading);
      if (victim) views.delete(victim[0]);
    }
    const request = route.request;
    // Overview, selectable Models and Accounts are projections of one finite normal report.
    // Reuse its timestamp, never silently reacquire accounts just to change presentation.
    const cached = request && [...views.values()].find(value => value.result && JSON.stringify(value.request) === JSON.stringify(request));
    views.set(key, {request, live: route.live, section: route.section, result: cached?.result || null,
      pages: {}, loading: false, active: null, explicit: route.explicit,
      message: route.live ? 'Live acquisition starting; one runtime shared across tabs.' : cached ? 'Snapshot captured. Reused frozen observation.' : request ? 'Capture/Refresh to acquire this report.' : 'Choose a report scope.'});
  }
  if (current?.detail) current.detail.detach();
  current = views.get(key);
  document.getElementById('search').value = current.search || '';
  if (match && csrf && sessionDetailAvailable && !current.detail) {
    current.detail = new SessionDetail.View(api, match[1], match[2] ? 'live' : 'snapshot');
    current.message = 'Complete session history; explicit Snapshot/Live. Acquisition is shared across tabs.';
  }
  document.getElementById('search').disabled = !!current.detail;
  show(current);
  if (csrf && current.request && !current.explicit && !current.detail && !current.result && !current.attempted) {
    current.attempted = true;
    acquire(current);
  }
}
async function connect() {
  try {
    const session = credential ? await api('/api/bootstrap', {credential}) : await api('/api/session');
    csrf = session.csrf;
    const state = await api('/api/status');
    sessionDetailAvailable = state.session_detail === true && typeof SessionDetail !== 'undefined';
    statusLine.textContent = `HTTP ${state.http}; analysis ${state.analysis}; source ${state.source}; accounts ${state.accounts}. Snapshot health is shown below.`;
    if (!liveConnection && typeof LiveConnection !== 'undefined') {
      liveConnection = LiveConnection.connect(api, (value, progress) => {
        liveValue = value;
        if (current?.live) { current.message = 'Live observation; source/account freshness shown below.'; show(current); }
        for (const job of progress?.jobs || []) {
          if (current?.active === job.id) notice.textContent = `${job.status}: ${job.progress?.phase || job.status} · ${job.progress?.completed ?? 0}${job.progress?.total == null ? '' : '/' + job.progress.total}`;
        }
      }, message => { statusLine.textContent = message; });
    }
    navigate();
  } catch (_) {
    statusLine.textContent = 'Browser session unavailable. Use a fresh one-use link from this host; restart it if expired.';
  } finally { credential = null; }
}
refresh.addEventListener('click', () => {
  if (current?.detail) current.detail.refresh();
  else if (current?.request) acquire(current);
});
cancel.addEventListener('click', async () => {
  const state = current;
  if (state?.active) {
    try { await api('/api/jobs/' + state.active + '/cancel', {}); }
    catch (_) { if (state === current) notice.textContent = 'Cancellation unavailable.'; }
  }
});
window.addEventListener('hashchange', navigate);
document.getElementById('search').addEventListener('input', event => {
  if (current) { current.search = event.target.value; current.pages = {}; show(current); }
});
document.getElementById('skip').addEventListener('click', () => document.getElementById('content').focus());
navigate();
connect();
