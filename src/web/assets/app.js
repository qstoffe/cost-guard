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
document.getElementById('ccost-unit').addEventListener('change', event => {
  ReportView.setUnit(event.target.value, output);
});
const views = new Map(); // Bounded page-memory only; never browser storage/history payloads.
let csrf = null;
let current = null;
let liveConnection = null;
let liveValue = null;
let liveStatus = 'Connecting';
let sessionDetailAvailable = false;
let hostState = {kind: 'starting', writable: false, terminal: false};
let hostInstance = null;
let snapshotRender = null;
function connectionStatus(message, state = {}) {
  if (hostState.terminal && state.kind !== hostState.kind) return;
  hostState = {...hostState, ...state};
  liveStatus = message;
  statusLine.textContent = hostState.kind === 'connected' ? message : `Connection: ${hostState.kind.replaceAll('_', ' ')}. See notice below.`;
  const banner = document.getElementById('host-state');
  if (banner) {
    banner.dataset.kind = hostState.kind;
    const time = value => value == null ? 'not yet observed' : new Date(value).toLocaleString();
    banner.hidden = hostState.kind === 'connected';
    const summary = document.getElementById('host-message');
    const details = document.getElementById('host-details');
    const timing = `Last authenticated host check: ${time(hostState.authenticatedAt)} · Last source update: ${time(hostState.observedAt)}. Reports remain frozen snapshots; account freshness is independent.`;
    if (summary && details) { summary.textContent = message; details.textContent = timing; }
    else banner.textContent = `${message} · ${timing}`;
    statusLine.title = `${message} ${timing}`;
  }
  if (hostState.terminal) for (const view of views.values()) view.detail?.detach();
  document.getElementById('scope-controls').inert = !hostState.writable;
  if (current) show(current);
}
async function api(path, value) {
  if (hostState.terminal) throw new Error(hostState.kind === 'authorization_required' ? 'authentication_required' :
    hostState.kind === 'identity_changed' ? 'host_identity_changed' : 'instance_stopping');
  const options = {credentials: 'same-origin', cache: 'no-store'};
  if (value !== undefined) Object.assign(options, {method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CG-CSRF': csrf || ''}, body: JSON.stringify(value)});
  const controller = new AbortController();
  options.signal = controller.signal;
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(path, options);
    const data = await response.json();
    const identity = response.headers?.get('X-CG-Instance');
    if (identity && hostInstance && identity !== hostInstance) {
      connectionStatus('HOST IDENTITY CHANGED — NOT LIVE. Use a fresh authorized launcher link.',
        {kind: 'identity_changed', terminal: true, writable: false});
      throw new Error('host_identity_changed');
    }
    if (response.ok && identity) hostInstance = identity;
    if (!response.ok) {
      if (response.status === 401 || data.error === 'csrf_required') {
        connectionStatus('AUTHENTICATION EXPIRED — NOT LIVE. Use a fresh launcher link.',
          {kind: 'authorization_required', terminal: true, writable: false});
      }
      throw new Error(data.error || 'request_unavailable');
    }
    if (hostState.terminal) throw new Error('instance_stopping');
    return data;
  } finally { clearTimeout(timeout); }
}
function show(state) {
  if (state !== current) return;
  refresh.disabled = !csrf || !hostState.writable || !(state.request || state.detail) || state.loading;
  cancel.disabled = !hostState.writable || !state.active;
  output.setAttribute('aria-busy', state.loading ? 'true' : 'false');
    notice.textContent = hostState.writable ? state.message : 'Last known contents are retained, not updating. See connection notice above.';
  if (state.detail) {
    ReportView.syncUnits(state.detail.root);
    if (!hostState.terminal) state.detail.attach(output);
    else output.replaceChildren(state.detail.root);
    state.detail.controls.inert = !hostState.writable;
  } else if (state.live) {
    state.connection = liveStatus;
    if (liveValue?.view) ReportView.renderLive(output, liveValue, state);
    else output.replaceChildren(ReportView.element('p', liveValue?.state || 'Live acquisition starting…'));
  } else if (state.result) {
    // Connection/source status is not a new frozen report. Replacing its DOM
    // discards scroll, focus and selection during ordinary health checks.
    const retained = snapshotRender?.state === state &&
      snapshotRender.result === state.result && snapshotRender.search === state.search &&
      snapshotRender.first === output.firstChild;
    if (!retained) {
      ReportView.render(output, state.result, state);
      snapshotRender = {state, result: state.result, search: state.search, first: output.firstChild};
    }
  }
  else if (state.loading) {
    const activity = ReportView.element('progress');
    activity.setAttribute('aria-label', 'Acquiring initial report');
    output.replaceChildren(activity, ReportView.element('p', state.message));
  } else output.replaceChildren(ReportView.element('p', state.message));
}
function failure(code) {
  const errors = {session_not_found: 'No matching session. It may have been removed or is unavailable in this source.',
    result_too_large: 'Report exceeds the finite result size limit; no truncated totals are shown. Use a specific session or the CLI.',
    report_timeout: 'Report timed out; no empty result was substituted.', cancelled: 'Report cancelled.',
    invalid_request: 'Invalid report scope. Check dates/limits; no alternate range was substituted.',
    session_catalog_changed: 'Session catalog changed. Use Latest sessions / restart browsing to avoid skipped or duplicate rows.',
    pricing_unavailable: 'Reference pricing unavailable.', busy: 'Report service busy. Retry Refresh.'};
  return errors[code] || 'Source/report unavailable. Check the local source and retry Refresh.';
}
async function acquire(state) {
  if (state.loading || !hostState.writable) return;
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
        if (hostState.terminal) break;
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
  // Replace, never push: legacy bookmarks keep their place in Back/Forward history.
  if (/^#\/live(?:\?|$)/.test(location.hash)) history.replaceState(null, '', '/#/watch' + location.hash.slice(6));
  const route = ReportRoutes.resolve(location.hash), match = route.session;
  const key = match ? 'session/' + match[1] : location.hash || '#/overview';
  heading.textContent = route.title;
  ReportRoutes.controls(document.getElementById('scope-controls'), route, event => {
    event.preventDefault();
    // Restart must not reuse a stale first-page revision from page-memory.
    for (const state of views.values()) {
      if (state.request?.kind === 'sessions' && !state.loading) {
        state.result = null; state.attempted = false;
      }
    }
    if (location.hash === '#/sessions') navigate();
    else location.hash = '#/sessions';
  });
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
  if (match && csrf && !hostState.terminal && sessionDetailAvailable && !current.detail) {
    current.detail = new SessionDetail.View(api, match[1], match[2] ? 'live' : 'snapshot');
    current.message = 'Complete session history; explicit Snapshot/Live. Acquisition is shared across tabs.';
  }
  document.getElementById('search').disabled = !!current.detail;
  if (csrf) show(current);
  if (csrf && hostState.writable && current.request && !current.explicit && !current.detail && !current.result && !current.attempted) {
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
        liveValue = value?.view || !liveValue?.view ? value : {...value,
          view: liveValue.view, source_observed_at_ms: liveValue.source_observed_at_ms};
        if (current?.live) { current.message = 'Live observation; source/account freshness shown below.'; show(current); }
        for (const job of progress?.jobs || []) {
          if (current?.active === job.id) notice.textContent = `${job.status}: ${job.progress?.phase || job.status} · ${job.progress?.completed ?? 0}${job.progress?.total == null ? '' : '/' + job.progress.total}`;
        }
        if (hostState.writable && current?.request && !current.explicit && !current.result && !current.attempted) {
          current.attempted = true; acquire(current);
        }
      }, connectionStatus);
    }
    navigate();
  } catch (_) {
    if (!hostState.terminal) connectionStatus('OFFLINE — host unreachable or browser session unavailable. Use the OS launcher; no host is started automatically.',
      {kind: 'offline', writable: false});
    output.setAttribute('aria-busy', 'false');
    output.replaceChildren(ReportView.element('p', 'Unable to establish the private browser session. Use tray Open Cost Guard for a fresh link, or relaunch Cost Guard Web Beta. No source data has been assumed ready.'));
  } finally { credential = null; }
}
refresh.addEventListener('click', () => {
  if (!hostState.writable) return;
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
window.addEventListener('pageshow', () => liveConnection?.resync());
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) liveConnection?.resync();
});
document.getElementById('search').addEventListener('input', event => {
  if (current) { current.search = event.target.value; current.pages = {}; show(current); }
});
document.getElementById('skip').addEventListener('click', () => document.getElementById('content').focus());
navigate();
connect();
