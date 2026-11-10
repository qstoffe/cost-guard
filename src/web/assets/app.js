'use strict';
// Erase the one-use credential before any fetch, preserving ordinary deep links.
let credential = new URLSearchParams(location.hash.slice(1)).get('bootstrap');
if (credential !== null) history.replaceState(null, '', '/#/models');
const statusLine = document.getElementById('status');
const output = document.getElementById('result');
const notice = document.getElementById('notice');
const refresh = document.getElementById('refresh');
const heading = document.getElementById('heading');
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
let settingsView = null;
let cachedReportTimer = null;
let demand = null; // Enabled only after the authenticated host advertises it.
const sourceNotice = document.getElementById('source-compatibility');
function sourceNoticeGeometry() {
  document.documentElement.style.setProperty('--source-notice-height', `${sourceNotice?.getBoundingClientRect().height || 0}px`);
}
if (sourceNotice && typeof ResizeObserver !== 'undefined') new ResizeObserver(sourceNoticeGeometry).observe(sourceNotice);
function historical(state) { return !!CachedReports.cadences[state?.section]; }
function firstReport(state = current) {
  if (csrf && hostState.writable && state?.request && !state.detail && !state.result && !state.attempted && !document.hidden) {
    state.attempted = true; acquire(state);
  }
}
function scheduleCachedReport() {
  clearTimeout(cachedReportTimer);
  const state = current;
  if (!historical(state) || !state.result || state.loading || state.pageNavigation && state.failed || document.hidden || !hostState.writable) return;
  if (demand) {
    cachedReportTimer = setTimeout(() => { if (current === state) { state.benchmark?.load(api); acquire(state, true); } }, 5000);
    return; // Lookup a publication, never schedule a browser-owned source refresh.
  }
  const cadence = CachedReports.cadences[state.section];
  const delay = Math.max(0, (state.checkedAt || CachedReports.observation(state.result)) + cadence - Date.now());
  cachedReportTimer = setTimeout(() => {
    if (current === state && !document.hidden && hostState.writable) acquire(state, true);
  }, delay);
}
function enterCachedReport(state) {
  if (!historical(state)) return;
  if (state.pageNavigation && state.failed) return; // Explicit Retry owns failed paging, not a lookup timer.
  const band = CachedReports.entry(state.result, state.section);
  state.withheld = state.section === 'ai-stats' ? !!state.result && !AIStatsView.valid(state.result) : band === 'withhold';
  if (demand && !document.hidden && hostState.writable) { acquire(state, !!state.result && !state.withheld); return; }
  if (!document.hidden && hostState.writable && state.result && ['quiet', 'withhold'].includes(band))
    acquire(state, !state.withheld);
}
function selectStats(state, period) {
  if (state.period === period) return;
  state.period = period;
  state.request = {kind: 'ai-stats', stats_scope: period};
  demand?.update();
  state.result = state.statsResults?.get(period) || null;
  state.failed = false; state.message = '';
  ReportLoading.reset(state);
  if (state.loading) AIStatsView.prioritize(state, api, !!demand);
  enterCachedReport(state); show(state);
  if (!state.result && !document.hidden) acquire(state);
  scheduleCachedReport();
}
const miniWatch = typeof MiniWatch === 'undefined' ? null : new MiniWatch.Controller(window,
  document.getElementById('mini-watch-toggle'), document.getElementById('mini-watch-feedback'),
  () => { if (location.hash !== '#/watch') location.hash = '#/watch'; });
function applySettings(value) {
  ReportView.setTimezone(value.timezone_id);
  const confirmed = WebSettings.apply(value, output);
  for (const state of views.values()) {
    if (state.detail) ReportView.syncUnits(state.detail.root);
    if (state.catalog) ReportView.syncUnits(state.catalog.root);
    if (state.watch) ReportView.syncUnits(state.watch.root);
    if (state.accounts) ReportView.syncUnits(state.accounts.root);
    if (state.tokenMix) ReportView.syncUnits(state.tokenMix.root);
    if (state.stats) ReportView.syncUnits(state.stats.root);
    if (state.comparisons) ReportView.syncUnits(state.comparisons.root);
  }
  miniWatch?.settings(confirmed.values, hostInstance);
  return confirmed;
}
function connectionStatus(message, state = {}) {
  if (hostState.terminal && state.kind !== hostState.kind) return;
  const wasWritable = hostState.writable;
  hostState = {...hostState, ...state};
  if (sourceNotice) {
    sourceNotice.hidden = hostState.kind !== 'connected' || state.sourceGeneration !== 'v1';
    sourceNoticeGeometry();
  }
  if (hostState.terminal) demand?.close?.(false);
  else if (wasWritable !== hostState.writable) demand?.update();
  liveStatus = message;
  miniWatch?.health(hostState);
  const quiet = hostState.kind === 'source_retrying' && liveValue?.view && hostState.observedAt != null;
  statusLine.textContent = quiet ? 'Live connected.' : ['connected', 'source_starting'].includes(hostState.kind) ? message : `Connection: ${hostState.kind.replaceAll('_', ' ')}. See notice below.`;
  statusLine.setAttribute('aria-description', quiet ? '' : message);
  const banner = document.getElementById('host-state');
  if (banner) {
    banner.dataset.kind = hostState.kind;
    const time = value => value == null ? 'not yet observed' : ReportView.timestamp(value);
    banner.hidden = quiet || hostState.kind === 'connected' || (hostState.kind === 'starting' && !(current?.result || current?.detail?.data || liveValue?.view));
    const summary = document.getElementById('host-message');
    const details = document.getElementById('host-details');
    const timing = `Last host check: ${time(hostState.authenticatedAt)}\nLast source update: ${time(hostState.observedAt)}\n${demand ? 'Reports refresh through the host; retained results keep their source observation time.' : 'Reports stay frozen.'} Account updates are separate.`;
    if (summary && details) { summary.textContent = banner.hidden ? '' : message; details.textContent = banner.hidden ? '' : timing; }
    else banner.textContent = banner.hidden ? '' : `${message} · ${timing}`;
    const warning = document.getElementById('host-warning');
    if (warning) {
      const recovery = ['authorization_required', 'identity_changed', 'stopped'].includes(hostState.kind) ? 'Use a fresh OS launcher link.' : 'Check the local source/host; reload to retry.';
      warning.textContent = banner.hidden ? '' : hostState.kind === 'source_starting' ? 'Starting OpenCode server…' : `${hostState.kind.replaceAll('_', ' ')} — ${recovery}`;
    }
  }
  if (hostState.terminal) for (const view of views.values()) { view.detail?.detach(); view.catalog?.detach(); }
  document.getElementById('scope-controls').inert = !hostState.writable;
  if (current) show(current);
  scheduleCachedReport();
}
async function api(path, value, signal, attachment = false) {
  if (hostState.terminal) throw new Error(hostState.kind === 'authorization_required' ? 'authentication_required' :
    hostState.kind === 'identity_changed' ? 'host_identity_changed' : 'instance_stopping');
  const options = {credentials: 'same-origin', cache: 'no-store'};
  if (value !== undefined) Object.assign(options, {method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CG-CSRF': csrf || ''}, body: JSON.stringify(value)});
  if (attachment) options.headers['X-CG-Instance'] = hostInstance || '';
  // Only a visible, actually selected view renews disposable history retention.
  // Hidden polling, passive host warming and diagnostic API clients do not.
  const viewed = path === '/api/interest' ? value?.visible === true : !document.hidden && (
    path === '/api/data' && value?.request === current?.request ||
    path === '/api/jobs/' + current?.active || path === '/api/sessions' && current?.section === 'sessions' ||
    path === '/api/detail' && current?.detail);
  if (viewed) options.headers = {...options.headers, 'X-CG-Viewed': '1'};
  const controller = new AbortController();
  options.signal = controller.signal;
  const aborted = () => controller.abort();
  if (signal?.aborted) controller.abort();
  else signal?.addEventListener('abort', aborted, {once: true});
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(path, options);
    const data = response.ok && attachment ? null : await response.json();
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
      const error = new Error(data.error || 'request_unavailable');
      error.retryable = data.retryable === true;
      throw error;
    }
    if (hostState.terminal) throw new Error('instance_stopping');
    if (attachment) {
      const disposition = response.headers.get('Content-Disposition') || '';
      const filename = /^attachment; filename="(opencode-ses_[A-Za-z0-9_-]+-sanitized\.json)"$/.exec(disposition)?.[1];
      const length = Number(response.headers.get('Content-Length'));
      if (!identity || !filename || !Number.isInteger(length) || length <= 0 || length > 16 * 1024 * 1024 ||
          response.headers.get('Content-Type') !== 'application/json; charset=utf-8') throw new Error('export_invalid_response');
      const blob = await response.blob();
      if (blob.size !== length || controller.signal.aborted || hostState.terminal) throw new Error('export_invalid_response');
      return {blob, filename};
    }
    return data;
  } finally { clearTimeout(timeout); signal?.removeEventListener('abort', aborted); }
}
function show(state) {
  if (state !== current) return;
  refresh.disabled = !csrf || !hostState.writable || !(state.request || state.detail) || state.loading;
  output.setAttribute('aria-busy', state.loading ? 'true' : 'false');
  notice.textContent = '';
  const finite = ReportLoading.sections.includes(state.section);
  if (finite) output.setAttribute('aria-busy', state.loading && (!state.result || state.withheld) ? 'true' : 'false');
  state.interrupted = ReportLoading.interrupted(hostState) ?
    'Report interrupted. Check the connection notice; use a fresh launcher link if authorization or host identity changed.' : null;
  if (state.section === 'token-mix') {
    refresh.textContent = 'Retry Token Mix';
    refresh.hidden = !state.failed;
    heading.hidden = !!state.result && !state.withheld;
    output.setAttribute('aria-busy', state.loading && (!state.result || state.withheld) ? 'true' : 'false');
  } else { refresh.textContent = 'Refresh snapshot'; refresh.hidden = false; heading.hidden = false; }
  if (state.section === 'models') { refresh.textContent = 'Retry Models'; refresh.hidden = !state.failed; heading.hidden = true; }
  const toolbar = document.querySelector('.toolbar');
  if (toolbar) toolbar.hidden = refresh.hidden && heading.hidden;
  if (state.section === 'ai-stats') {
    refresh.textContent = 'Retry AI Stats'; refresh.hidden = !state.failed;
    notice.textContent = ''; output.setAttribute('aria-busy', state.loading && (!state.result || state.withheld) ? 'true' : 'false');
    ReportView.defaultUnit();
    state.stats ||= new AIStatsView.View(period => selectStats(state, period));
    state.stats.update(state); state.stats.attach(output);
    return;
  }
  if (state.section === 'comparisons') {
    refresh.textContent = 'Retry Comparisons'; refresh.hidden = !state.failed;
    notice.textContent = '';
    ReportView.defaultUnit();
    state.comparisons ||= new ComparisonsView.View((offset, revision) => {
      if (state.loading) return;
      state.request = {kind: 'comparisons', comparison_offset: offset, comparison_revision: revision};
      state.pageNavigation = true; state.orderRetried = false; state.orderReset = false;
      demand?.update(); acquire(state);
    });
    state.comparisons.update(state); state.comparisons.attach(output);
    return;
  }
  if (state.section === 'settings') {
    heading.hidden = true;
    if (!settingsView) settingsView = new WebSettings.View(api, applySettings);
    settingsView.attach(output);
    return;
  }
  if (finite && (!state.result || state.withheld)) {
    output.setAttribute('aria-busy', state.failed || state.interrupted ? 'false' : 'true');
    ReportLoading.show(output, state);
    return;
  }
  if (state.detail) {
    ReportView.syncUnits(state.detail.root);
    if (!hostState.terminal) state.detail.attach(output);
    else output.replaceChildren(state.detail.root);
  } else if (state.catalog) {
    ReportView.syncUnits(state.catalog.root);
    if (!hostState.terminal) state.catalog.attach(output);
    else output.replaceChildren(state.catalog.root);
  } else if (state.live) {
    state.connection = liveStatus;
    state.connectionKind = hostState.kind;
    if (state.section === 'accounts') {
      state.accounts ||= new AccountCards.View(true);
      state.accounts.update(liveValue?.view || {});
      state.accounts.attach(output);
    } else if (liveValue?.view) {
      ReportView.renderLive(output, liveValue, state);
    } else {
      // Host/source health owns startup and failure feedback, not an elapsed timer.
      output.replaceChildren();
    }
  } else if (state.result && state.section === 'token-mix' && !state.withheld) {
    ReportView.defaultUnit();
    state.tokenMix ||= new TokenMixView.View();
    state.tokenMix.update(state.result); state.tokenMix.attach(output);
  } else if (state.result) {
    // Connection/source status is not a new frozen report. Replacing its DOM
    // discards scroll, focus and selection during ordinary health checks.
    const retained = snapshotRender?.state === state &&
      snapshotRender.result === state.result && snapshotRender.search === state.search &&
      snapshotRender.first === output.firstChild;
    if (!retained) {
      const scroll = output.querySelector('.overview-models')?.scrollLeft;
      const focused = document.activeElement?.getAttribute('data-model-control');
      ReportView.render(output, state.result, state);
      if (scroll != null && state.section === 'models') output.querySelector('.overview-models').scrollLeft = scroll;
      if (focused && state.section === 'models') output.querySelector(`[data-model-control="${focused}"]`)?.focus({preventScroll: true});
      snapshotRender = {state, result: state.result, search: state.search, first: output.firstChild};
    }
    state.priceControls?.(!!csrf && hostState.writable);
    state.benchmark?.controls(!!csrf && hostState.writable, api);
    if (state.section === 'models' && csrf && hostState.writable && !document.hidden) state.benchmark?.load(api);
  }
  else if (state.loading) {
    const activity = ReportView.element('progress');
    activity.setAttribute('aria-label', 'Acquiring initial report');
    output.replaceChildren(activity, ReportView.element('p', state.message));
  } else output.replaceChildren(ReportView.element('p', state.message));
}
function reportWork(progress) {
  const labels = {'date-cache': 'Checking date-history cache', 'date-load': 'Loading date history',
    'date-catalog-before': 'Reading before-catalog', 'date-messages': 'Reading session trees (not yet revision-verified)',
    'date-catalog-after': 'Verifying after-catalog', 'date-analysis': 'Analyzing date-history roots'};
  return `${labels[progress.stage] || progress.phase} · ${progress.completed ?? 0}${progress.total == null ? '' : '/' + progress.total}`;
}
function failure(code) {
  const errors = {session_not_found: 'No matching session. It may have been removed or is unavailable in this source.',
    result_too_large: 'Report exceeds the finite result size limit; no truncated totals are shown. Use a specific session or the CLI.',
    cancelled: 'Report cancelled.',
    invalid_request: 'Invalid report scope or limits; no alternate scope was substituted.',
      session_catalog_changed: 'Session catalog changed. Use Latest sessions / restart browsing to avoid skipped or duplicate rows.',
      comparison_page_no_progress: 'Page navigation made no forward progress for 45 seconds. Last page retained; Retry Comparisons to try again.',
      comparison_page_retries: 'Page navigation exhausted three recovery attempts. Last page retained; Retry Comparisons to try again.',
     pricing_unavailable: 'Reference pricing unavailable.', busy: 'Report service busy. Retry when a slot is available.',
     ai_stats_revision_churn: 'History kept changing without verified forward progress. Saved stable work is retained; Retry when the source settles.',
     ai_stats_checkpoint_unavailable: 'AI Stats could not save resumable evidence. Check local cache access or disk space, then Retry.',
      ai_stats_resource_limit: 'AI Stats reached its bounded history/live-root resource limit. No truncated totals are shown.',
      history_no_progress: 'History made no verified forward progress. Saved stable work is retained; check the source and Retry.',
      history_revision_churn: 'History kept changing. Saved stable work is retained; Retry when the source settles.',
      history_checkpoint_unavailable: 'History could not save resumable evidence. Check local cache access or disk space, then Retry.',
      history_resource_limit: 'History reached its bounded work limit. No truncated totals are shown.',
     source_permission_denied: 'Permission denied reading the source. Correct source access before Retry.',
     http_auth_failure: 'Source authentication failed. Restore OpenCode source authorization before Retry.',
     registration_invalid: 'OpenCode source registration is invalid. Repair it before Retry.',
     registration_unreadable: 'OpenCode source registration is unreadable. Check permissions before Retry.',
     unsupported_version: 'This OpenCode source version is unsupported. Use a supported source version.',
     unsupported_schema: 'This OpenCode source schema is unsupported. Use a supported source version.',
     offline: 'Host is offline. Check the local host and reload.',
     authorization_required: 'Browser authorization expired. Use a fresh OS launcher link.',
     identity_changed: 'Host identity changed. Use a fresh OS launcher link.'};
  return errors[code] || 'Source/report unavailable. Check the local source and retry Refresh.';
}
async function acquire(state, background = false, prices = false) {
  if (state.loading || !hostState.writable) return;
  // A disabled native button loses focus before the replacement DOM is captured.
  // Restore only this explicit action, unless the user focused/clicked elsewhere.
  let priceFocus = prices && document.activeElement?.getAttribute('data-model-control') === 'refresh';
  const movedPriceFocus = event => {
    if (event.target?.getAttribute('data-model-control') !== 'refresh') priceFocus = false;
  };
  const priceFocusEvents = priceFocus ? ['focusin', 'pointerdown'] : [];
  for (const event of priceFocusEvents) document.addEventListener(event, movedPriceFocus);
  const request = state.request;
  let publication = null;
  let retry = !!state.failed && !background;
  state.loading = true;
  const attempt = state.attempt = new ReportLoading.Attempt({paging: state.pageNavigation === true});
  state.priceRefreshing = prices; state.priceMessage = '';
  state.failed = false;
  state.dispatchError = null;
  ReportLoading.reset(state);
  state.lastWork = null;
  ReportLoading.observe(state, {phase: 'queued'});
  state.message = background ? '' : state.result ? 'Refreshing; last known snapshot retained until success.' : 'Loading snapshot…';
  show(state);
  async function admit() {
    while (true) {
      attempt.check(hostState, true);
      try {
        const scope = state.section === 'ai-stats' ? state.request : request;
        const retryOnce = retry;
        retry = false; // Only the explicit user attempt may clear host backoff.
        const admission = await api(prices ? '/api/models/refresh' : demand ? '/api/data' : '/api/reports', prices ? {} :
          demand ? {request: scope, retry: retryOnce} : scope, attempt.controller.signal);
        state.active = admission.id;
        if (attempt.retries) ReportLoading.reset(state);
        if (demand && !prices) {
          // Retained publication identity is independent of an active refresh.
          state.dispatchRefresh = admission.refresh;
          state.dispatchError = admission.terminal ? admission.error || 'report_unavailable' : null;
          if (!admission.result && state.result && state.section !== 'ai-stats' && !state.pageNavigation) { state.withheld = true; show(state); }
          if (admission.result) publication = {status: 'complete', result: admission.result,
            publication_id: admission.result_id || admission.id};
          else if (admission.terminal || !admission.id) throw new Error(admission.error || 'report_unavailable');
        }
        state.progressSequence = 0;
        return;
      } catch (error) {
        if (state.section === 'comparisons' && error.message === 'session_catalog_changed' || !ReportLoading.retryable(error)) throw error;
        if (state.section === 'ai-stats' && attempt.retries >= 3) throw error;
        ReportLoading.waiting(state, error.message, attempt.paging ? attempt.retries + 1 : null); show(state);
        await attempt.backoff(error);
      }
    }
  }
  try {
    await admit();
    if (state.section === 'ai-stats' && request.stats_scope !== state.request.stats_scope)
      AIStatsView.prioritize(state, api, !!demand);
    show(state);
    while (true) {
      // Poll the same logical work even after a long hidden/background period.
      attempt.check(hostState);
       const job = publication || await api('/api/jobs/' + state.active, undefined, attempt.controller.signal);
       publication = null;
      attempt.check(hostState);
      const statsProgress = state.section === 'ai-stats' && AIStatsView.observe(state, job);
      if (job.progress?.stage?.startsWith('date-')) state.lastWork = reportWork(job.progress);
      if (!['queued', 'running'].includes(job.status)) {
         if (job.status !== 'complete' || !job.result || job.result.error) {
          const error = new Error(job.result?.error?.code || job.error || job.status);
          error.retryable = job.result?.error?.retryable === true;
            if (state.section === 'comparisons' && error.message === 'session_catalog_changed' || !ReportLoading.retryable(error)) throw error;
           if (state.section === 'ai-stats' && attempt.retries >= 3) throw error;
           state.active = null; ReportLoading.waiting(state, error.message, attempt.paging ? attempt.retries + 1 : null); show(state);
          await attempt.backoff(error); await admit(); continue;
        }
        if (hostState.terminal) break;
         if (state.section === 'token-mix' && !TokenMixView.valid(job.result)) throw new Error('report_unavailable');
         if (state.section === 'ai-stats' && !AIStatsView.valid(job.result)) throw new Error('report_unavailable');
         if (state.section === 'comparisons' && !ComparisonsView.valid(job.result)) throw new Error('report_unavailable');
          if (state.section === 'comparisons') state.pageNavigation = false;
         if (state.section === 'ai-stats' && !job.result.view.ai_stats.some(row => row.period === state.period)) {
           await admit(); continue; // A simultaneous scope change finished a different period.
         }
          const initial = !state.result || state.withheld;
          const revision = [job.publication_id || state.active, job.result.instance_id,
            job.result.sequence, CachedReports.observation(job.result)].join(':');
          if (demand && !prices && state.result && state.dataRevision === revision) break;
         if (state.section === 'models' && (!job.result.view || job.result.view.kind !== 'normal' ||
             !['acquired', 'partial'].includes(job.result.source?.status))) throw new Error('report_unavailable');
         if (state.section === 'ai-stats') {
           AIStatsView.remember(state, job.result);
          } else state.result = job.result;
          state.dataRevision = revision;
          if (demand && !prices && !job.publication_id) state.dispatchRefresh = 'scheduled';
         // A usable partial response finishes this attempt, not source coverage.
          if (state.result) {
            state.percent = 100; state.stage = state.stageLabel = 'Report ready';
            if (initial && state === current && state.loader?.root.isConnected)
              await ReportLoading.paintCompletion(state, attempt.controller.signal);
          }
        state.withheld = state.section !== 'ai-stats' && historical(state) && state.result &&
          CachedReports.entry(state.result, state.section) === 'withhold';
        state.pages = {};
        state.message = historical(state) ? '' : 'Snapshot captured. Navigation and source activity do not update it.';
        break;
      }
       attempt.observe(job.progress);
       attempt.check(hostState, true);
           if (!statsProgress) ReportLoading.observe(state, job.progress);
        if (state.section === 'ai-stats' && (!state.result || state.withheld)) state.lastWork = reportWork(job.progress);
      // Do not redraw a retained report while polling: keep selection and scroll useful.
         if (state === current && (!background || statsProgress)) show(state);
        await attempt.poll(state.active, state.pageNavigation ? 1000 : 500);
    }
  } catch (error) {
    if (attempt.reason) error = new Error(attempt.reason);
    if (state.section === 'comparisons' && error.message === 'session_catalog_changed' && !state.orderRetried) {
      state.request = {kind: 'comparisons'}; state.orderReset = true; state.retryOrder = true;
      state.orderRetried = true;
      demand?.update(); // Retire the old pin's foreground interest as well as its browser retry.
    }
    state.message = prices ? 'Price list refresh failed; previous prices retained' : background ? 'Update delayed; last completed report retained.' :
      `${state.result ? 'STALE — last known snapshot retained. ' : ''}${failure(error.message)}`;
    if (prices) state.priceMessage = state.message;
    state.failed = true;
  } finally {
     if (state.dispatchError && !prices) { state.failed = true; state.message = failure(state.dispatchError); }
     state.loading = false; state.priceRefreshing = false; state.active = null; state.attempt = null; state.checkedAt = Date.now();
     show(state); scheduleCachedReport();
    for (const event of priceFocusEvents) document.removeEventListener(event, movedPriceFocus);
    if (priceFocus && state === current && document.activeElement === document.body)
      output.querySelector('[data-model-control="refresh"]')?.focus({preventScroll: true});
    if (state.retryOrder && state === current && !document.hidden && hostState.writable) {
      state.retryOrder = false; acquire(state);
    }
    if (state === current && state.section === 'ai-stats' && !state.result && !state.failed && !document.hidden &&
         JSON.stringify(request) !== JSON.stringify(state.request)) acquire(state);
  }
}
function focusReport(options) {
  const content = document.getElementById('content');
  // The browser may treat initial scripted focus as focus-visible. Only an
  // intentional keyboard transfer gets the landmark's inset focus cue.
  content.classList.toggle('keyboard-focus', document.activeElement !== content &&
    !!document.activeElement?.matches(':focus-visible'));
  content.focus(options);
}
function navigate() {
  // Replace, never push: legacy bookmarks keep their place in Back/Forward history.
  if (/^#\/live(?:\?|$)/.test(location.hash)) history.replaceState(null, '', '/#/watch' + location.hash.slice(6));
  if (/^#\/sessions\/[A-Za-z0-9_-]{1,200}\/live$/.test(location.hash)) history.replaceState(null, '', '/' + location.hash.replace(/\/live$/, ''));
  if (!location.hash || /^#\/(?:overview|models\/all)(?:\?|$)/.test(location.hash)) {
    const query = location.hash.includes('?') ? location.hash.slice(location.hash.indexOf('?')) : '';
    history.replaceState(null, '', '/#/models' + query);
  }
  let route = ReportRoutes.resolve(location.hash);
  const redirected = !!route.redirect;
  if (redirected) {
    history.replaceState(null, '', '/' + route.redirect);
    route = ReportRoutes.resolve(location.hash);
  }
  const match = route.session;
  document.title = `${route.title} · Cost Guard`;
  document.body.dataset.section = route.section;
  const key = match ? 'session/' + match[1] : route.section === 'sessions' ? 'sessions-catalog' : location.hash || '#/models';
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
    // Reuse only matching finite observations. Live Accounts never owns a job.
    const cached = request && [...views.values()].find(value => value.result && JSON.stringify(value.request) === JSON.stringify(request));
    views.set(key, {request, live: route.live, section: route.section, result: cached?.result || null,
      pages: {}, loading: false, active: null,
      message: route.live ? 'Live acquisition starting; one runtime shared across tabs.' : cached ?
        (demand ? 'Reusing the last verified observation; the host checks freshness.' : 'Snapshot captured. Reused frozen observation.') :
        request ? (demand ? 'Loading the host-owned report…' : 'Capture/Refresh to acquire this report.') : 'Choose a report scope.'});
  }
  const previous = current;
  if (current?.detail) current.detail.detach();
  if (current?.catalog) current.catalog.detach();
  current = views.get(key);
  // A requested report (including bounded admission backoff) belongs to its view,
  // not the active route. Navigation never abandons it or starts another attempt.
  if (current.section === 'ai-stats') {
    current.period ||= '30-days'; current.statsResults ||= new Map();
    current.request = {kind: 'ai-stats', stats_scope: current.period};
  }
  if (route.section === 'models') current.refreshPrices = () => acquire(current, false, true);
  document.getElementById('search').value = current.search || '';
  if (match && csrf && !hostState.terminal && sessionDetailAvailable && !current.detail) {
    current.detail = new SessionDetail.View(api, match[1]);
    current.message = '';
  }
   if (route.catalog && csrf && sessionDetailAvailable && typeof SessionsCatalog !== 'undefined') {
    current.catalog ||= new SessionsCatalog.View(api);
    current.catalog.configure(route.params);
     current.request = null; current.message = '';
   }
   if ((match || route.catalog) && csrf && !sessionDetailAvailable) current.message = 'Live session source unavailable.';
  document.getElementById('search').disabled = !!current.detail;
  show(current);
  demand?.update();
  if (current !== previous) enterCachedReport(current);
  scheduleCachedReport();
     if (redirected) focusReport();
     if (route.section === 'models' && current !== previous) {
       focusReport({preventScroll: true});
      window.scrollTo(0, 0); // New-route policy only; never refresh/filter/sort arrival.
    }
  if (route.section === 'settings' && csrf && !hostState.terminal) settingsView.read();
  firstReport();
}
async function connect() {
  try {
    const session = credential ? await api('/api/bootstrap', {credential}) : await api('/api/session');
    csrf = session.csrf;
    // Lightweight file read precedes reports; HTML already carries the early-paint theme.
    try { applySettings(await api('/api/settings')); }
    catch (_) { notice.textContent = 'Unable to read saved Web settings. Open Settings for details.'; }
     const state = await api('/api/status');
     if (state.data_dispatcher && typeof DataDemand !== 'undefined') {
       const writable = () => !!csrf && hostState.writable && !hostState.terminal;
       demand = new DataDemand.Controller(api, () => current && {...current,
         history: current.section === 'watch' && current.watch?.earlier.open === true}, writable,
         {history: state.history_demand === true});
       if (state.history_demand === true) miniWatch?.setDemandFactory(win => new DataDemand.Controller(api,
         () => ({section: 'watch', history: miniWatch.window === win && miniWatch.view?.needsHistory !== false}),
         writable, {owner: win, history: true}));
     }
    if (typeof state.product_version === 'string') document.getElementById('product-version').textContent = state.product_version;
    sessionDetailAvailable = state.session_detail === true && typeof SessionDetail !== 'undefined';
    statusLine.textContent = `HTTP ${state.http}; analysis ${state.analysis}; source ${state.source}; accounts ${state.accounts}. Snapshot health is shown below.`;
    if (!liveConnection && typeof LiveConnection !== 'undefined') {
      liveConnection = LiveConnection.connect(api, (value, progress) => {
        liveValue = value?.view || !liveValue?.view ? value : {...value,
          view: liveValue.view, source_observed_at_ms: liveValue.source_observed_at_ms};
        miniWatch?.update(liveValue);
        if (current?.live) { current.message = 'Live observation; source/account freshness shown below.'; show(current); }
        for (const job of progress?.jobs || []) {
            if (current?.active === job.id && !ReportLoading.sections.includes(current.section)) {
              notice.textContent = `${job.status}: ${job.progress?.phase || job.status} · ${job.progress?.completed ?? 0}${job.progress?.total == null ? '' : '/' + job.progress.total}`;
            }
            if (current?.active === job.id && ReportLoading.sections.includes(current.section) &&
                (!current.result || current.withheld) && ['queued', 'running'].includes(job.status)) {
              if (current.section !== 'ai-stats') ReportLoading.observe(current, job.progress || {});
              show(current);
            }
            // A terminal Live hint only wakes the visible view's status wait; its fetch decides.
            if (current?.active === job.id && current.attempt && !document.hidden &&
                !['queued', 'running'].includes(job.status)) current.attempt.notify(job.id);
        }
         firstReport();
      }, connectionStatus);
    }
    navigate();
  } catch (_) {
    if (!hostState.terminal) connectionStatus('OFFLINE — host unreachable or browser session unavailable. Use the OS launcher; no host is started automatically.',
      {kind: 'offline', writable: false});
    output.setAttribute('aria-busy', 'false');
    const error = ReportView.element('p', 'Unable to establish the private browser session. Use tray Open Cost Guard for a fresh link, or relaunch Cost Guard. No source data has been assumed ready.', 'error');
    error.setAttribute('role', 'alert'); output.replaceChildren(error);
  } finally { credential = null; }
}
refresh.addEventListener('click', () => {
  if (!hostState.writable) return;
   if (current?.request) acquire(current);
});
window.addEventListener('hashchange', () => {
  // Pasting into an already-open unauthorized tab can be same-document navigation.
  // Erase first, exchange through the existing guard, then reload only the clean URL.
  const handoff = new URLSearchParams(location.hash.slice(1)).get('bootstrap');
  if (handoff !== null) {
    history.replaceState(null, '', '/#/models');
    return fetch('/api/bootstrap', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({credential: handoff})}).catch(() => {}).then(() => location.reload());
  }
  navigate();
});
window.addEventListener('pageshow', () => liveConnection?.resync());
for (const link of document.querySelectorAll('nav a')) {
  if (link.getAttribute('href') === '#/sessions') link.addEventListener('click', event => {
    const catalog = views.get('sessions-catalog')?.catalog;
    if (catalog?.rememberedDestination) { event.preventDefault(); location.hash = catalog.rememberedDestination(); }
  });
}
window.addEventListener('offline', () => connectionStatus('OFFLINE — last observation retained, not live. Check the connection and reload to retry.', {kind: 'offline', writable: false}));
window.addEventListener('online', () => liveConnection?.resync());
document.addEventListener('visibilitychange', () => {
  current?.catalog?.interest();
  // Keep existing acquisitions, but never schedule new hidden-route refreshes.
  if (!document.hidden) liveConnection?.resync();
  if (!document.hidden) {
    current?.catalog?.poll(); current?.detail?.poll();
    enterCachedReport(current);
    firstReport();
  }
  scheduleCachedReport();
});
document.addEventListener('toggle', event => {
  if (event.target === current?.watch?.earlier) demand?.update();
}, true);
document.getElementById('search').addEventListener('input', event => {
  if (current) { current.search = event.target.value; current.pages = {}; show(current); }
});
document.getElementById('skip').addEventListener('click', () => focusReport());
navigate();
connect();
