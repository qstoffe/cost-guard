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
const sessionsNav = document.querySelector('nav a[href="#/sessions"]');
let rememberedSession = null;
let csrf = null;
let current = null;
let liveConnection = null;
let liveValue = null;
let sourceValue = null;
let liveStatus = 'Connecting';
let sessionDetailAvailable = false;
let accountTimelineAvailable = false;
let archiveHistory = false;
let hostState = {kind: 'starting', writable: false, terminal: false};
let hostInstance = null;
let snapshotRender = null;
let settingsView = null;
let cachedReportTimer = null;
let cachedReportOwner = null;
let demand = null; // Enabled only after the authenticated host advertises it.
let tokenMixBinding = null;
const sourceNotice = document.getElementById('source-compatibility');
function sourceNoticeGeometry() {
  document.documentElement.style.setProperty('--source-notice-height', `${sourceNotice?.getBoundingClientRect().height || 0}px`);
}
if (sourceNotice && typeof ResizeObserver !== 'undefined') new ResizeObserver(sourceNoticeGeometry).observe(sourceNotice);
function historical(state) { return !!CachedReports.cadences[state?.section]; }
function automaticHistory(state) { return ['token-mix', 'ai-stats'].includes(state?.section); }
function archiveReadable() {
  return !!csrf && archiveHistory && !ReportLoading.interrupted(hostState);
}
function historyBlocked() {
  return hostState.terminal || (hostState.sourceBlocked && !archiveHistory);
}
function reportReadable(state) {
  return hostState.writable || (automaticHistory(state) && archiveReadable());
}
function watchValue(source, history) {
  if (!archiveHistory || !history) return source;
  if (!source?.view || hostState.sourceBlocked || source.state === 'failed' || source.state === 'source_unavailable') {
    return {...source, state: 'retained_history', view: history, source_observed_at_ms: null};
  }
  const view = source.view;
  const liveRoots = new Set([...(view.active_cards || []), ...(view.recent_finished_cards || [])]
    .map(card => card.session_id));
  const cards = new Map(history.history_cards.filter(card => !liveRoots.has(card.session_id))
    .map(card => [card.session_id, card]));
  for (const card of view.history_cards || []) cards.set(card.session_id, card);
  const historyCards = [...cards.values()].sort((a, b) =>
    (a.rows?.[0]?.prompt?.completed_at_ms ?? 0) - (b.rows?.[0]?.prompt?.completed_at_ms ?? 0)).slice(-5);
  const previews = new Map(history.earlier_previews.map(item => [item.session_id, item]));
  for (const item of view.earlier_previews || []) previews.set(item.session_id, item);
  const earlier = [...previews.values()].filter(item => !liveRoots.has(item.session_id))
    .sort((a, b) => (b.activity_ms || 0) - (a.activity_ms || 0)).slice(0, 5);
  const retainedDay = history.daily_usage?.day_end_ms > Date.now() ? history.daily_usage : null;
  const currentDay = hostState.kind === 'connected' && view.daily_usage?.day_end_ms > Date.now() &&
    ['observed', 'refreshing'].includes(view.daily_state);
  return {...source, view: {...view, history_cards: historyCards,
    history_epoch: Math.max(view.history_epoch || 0, history.history_epoch),
    earlier_previews: earlier, daily_usage: currentDay ? view.daily_usage : retainedDay ?? view.daily_usage,
    daily_state: !currentDay && retainedDay ? history.daily_state : view.daily_state}};
}
function firstReport(state = current) {
  if (csrf && reportReadable(state) && state?.request &&
      !state.detail && !state.result && !state.attempted && !document.hidden) {
    state.attempted = true; acquire(state);
  }
}
function scheduleCachedReport() {
  const state = current;
  const recoverCold = automaticHistory(state) && state.failed && state.section !== 'token-mix';
  if (!historical(state) || !state.result && !recoverCold ||
      state.loading || state.pageNavigation && state.failed || document.hidden || !reportReadable(state)) {
    clearTimeout(cachedReportTimer); cachedReportTimer = null; cachedReportOwner = null; return;
  }
  // Live health arrives more often than the lookup interval. Keep the existing
  // deadline rather than debouncing automatic recovery forever on a healthy host.
  if (demand && cachedReportTimer !== null && cachedReportOwner === state) return;
  clearTimeout(cachedReportTimer); cachedReportOwner = state;
  const check = () => {
    cachedReportTimer = null; cachedReportOwner = null;
    if (current === state && !document.hidden && reportReadable(state)) {
      if (demand) state.benchmark?.load(api);
      acquire(state, true);
    }
  };
  if (demand) {
    cachedReportTimer = setTimeout(check, automaticHistory(state) ? 1500 : 5000);
    return; // Lookup a publication, never schedule a browser-owned source refresh.
  }
  const cadence = CachedReports.cadences[state.section];
  const delay = Math.max(0, (state.checkedAt || CachedReports.observation(state.result)) + cadence - Date.now());
  cachedReportTimer = setTimeout(check, delay);
}
function enterCachedReport(state) {
  if (!historical(state)) return;
  if (state.pageNavigation && state.failed) return; // Explicit Retry owns failed paging, not a lookup timer.
  const band = CachedReports.entry(state.result, state.section);
  state.withheld = state.section === 'ai-stats' ? !!state.result && !AIStatsView.valid(state.result) : band === 'withhold';
  if (demand && !document.hidden && reportReadable(state)) { acquire(state, !!state.result && !state.withheld); return; }
  if (!document.hidden && hostState.writable && state.result && ['quiet', 'withhold'].includes(band))
    acquire(state, !state.withheld);
}
function selectStats(state, period) {
  if (state.period === period) return;
  state.period = period;
  state.request = {kind: 'ai-stats', stats_scope: period};
  demand?.update();
  state.result = state.statsResults?.get(period) || null;
  state.statsAcquisitionFailed = false;
  state.failed = false; state.message = '';
  state.actionRequested = true;
  ReportLoading.reset(state);
  if (state.loading) AIStatsView.prioritize(state, api, !!demand);
  enterCachedReport(state); show(state);
  if (!state.result && !document.hidden) acquire(state);
  scheduleCachedReport();
}
function selectTokenMix(state, period) {
  if (state.period === period) return;
  // Retire only this browser attempt, not shared host work or another tab's demand.
  state.attempt?.controller.abort(); state.attempt = null; state.loading = false; state.active = null;
  state.period = period; state.request = {kind: 'token-mix', token_mix_scope: period};
  state.result = null; state.withheld = false; state.dataRevision = null;
  state.failed = false; state.message = ''; state.attempted = false;
  state.actionRequested = true;
  ReportLoading.reset(state); demand?.update();
  show(state); firstReport(state); scheduleCachedReport();
}
function bindTokenMix(state, admission) {
  const binding = admission.source_identity ? `${admission.source_identity}:${admission.projection_epoch}` : null;
  if (admission.stale || admission.error === 'source_identity_changed' ||
      binding && state.mixBinding && binding !== state.mixBinding) {
    state.result = null; state.dataRevision = null; state.withheld = false;
    show(state);
  }
  if (binding) tokenMixBinding = state.mixBinding = binding;
}
const miniWatch = typeof MiniWatch === 'undefined' ? null : new MiniWatch.Controller(window,
  document.getElementById('mini-watch-toggle'), document.getElementById('mini-watch-feedback'),
  () => { if (location.hash !== '#/watch') location.hash = '#/watch'; });
miniWatch?.measure?.loaded?.then(() => { if (current?.section === 'watch') show(current); });
function applySettings(value) {
  ReportView.setTimezone(value.timezone_id);
  const confirmed = WebSettings.apply(value, output);
  for (const state of views.values()) {
    if (state.detail) ReportView.syncUnits(state.detail.root);
    if (state.catalog) ReportView.syncUnits(state.catalog.root);
    if (state.watch) ReportView.syncUnits(state.watch.root);
    if (state.accounts) ReportView.syncUnits(state.accounts.root);
    state.accountTimeline?.draw();
    if (state.tokenMix) ReportView.syncUnits(state.tokenMix.root);
    if (state.stats) ReportView.syncUnits(state.stats.root);
  }
  miniWatch?.settings(confirmed.values, hostInstance);
  return confirmed;
}
function connectionStatus(message, state = {}) {
  if (hostState.terminal && state.kind !== hostState.kind) return;
  const wasWritable = hostState.writable;
  const couldReadHistory = archiveReadable();
  hostState = {...hostState, ...state};
  hostState.sourceBlocked = ['http_auth_failure', 'source_permission_denied', 'permission_denied',
    'registration_unreadable', 'unsupported_schema', 'unsupported_version', 'registration_invalid']
    .includes(hostState.sourceError);
  if (hostState.sourceBlocked) hostState.writable = false;
  if (hostState.kind !== 'connected' || hostState.sourceBlocked) current?.detail?.updateInvocations();
  if (!wasWritable && hostState.writable || !couldReadHistory && archiveReadable()) {
    current?.detail?.catchUp();
  }
  if (sourceNotice) {
    sourceNotice.hidden = hostState.kind !== 'connected' || state.sourceGeneration !== 'v1';
    sourceNoticeGeometry();
  }
  if (hostState.terminal) demand?.close?.(false);
  else if (wasWritable !== hostState.writable || couldReadHistory !== archiveReadable()) demand?.update();
  liveStatus = message;
  miniWatch?.health(hostState);
  // Health governs admission, not narration of automatic retries.
  const recovery = hostState.terminal || ['authorization_required', 'identity_changed', 'stopped'].includes(hostState.kind) ?
    'Reopen Cost Guard from the launcher to reconnect.' :
    ['http_auth_failure', 'source_permission_denied', 'permission_denied', 'registration_unreadable'].includes(hostState.sourceError) ?
      'Check OpenCode access, then reopen Cost Guard.' :
    hostState.sourceBlocked ? 'Update OpenCode, then reopen Cost Guard.' : '';
  const visibleMessage = recovery || (hostState.sourceOutage ? 'OpenCode connection lost. Trying to reconnect…' : '');
  ReportView.text(statusLine, '');
  statusLine.removeAttribute('aria-description');
  const banner = document.getElementById('host-state');
  if (banner) {
    banner.dataset.kind = hostState.kind;
    banner.hidden = !visibleMessage;
    const summary = document.getElementById('host-message');
    const details = document.getElementById('host-details');
    if (summary && details) { ReportView.text(summary, visibleMessage); ReportView.text(details, ''); }
    else ReportView.text(banner, visibleMessage);
    const warning = document.getElementById('host-warning');
    if (warning) {
      ReportView.text(warning, '');
    }
  }
  const blocked = historyBlocked();
  for (const view of views.values()) {
    view.catalog?.sourceHealth(blocked || hostState.sourceBlocked || hostState.sourceOutage, blocked);
    if (blocked) {
      view.detail?.invalidateValues(); view.detail?.detach();
      view.accountTimeline?.invalidate();
    }
  }
  document.getElementById('scope-controls').inert = !hostState.writable;
  if (current) show(current);
  if ((!wasWritable && hostState.writable || !couldReadHistory && archiveReadable()) &&
      automaticHistory(current) && !current.loading)
    enterCachedReport(current);
  scheduleCachedReport();
}
function retryableReadError(message, cause) {
  return Object.assign(new Error(message, {cause}), {retryable: true});
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
  // ZIPs allow up to 240 s of preparation plus the bounded response transfer.
  let timedOut = false;
  const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, attachment ? 270000 : 5000);
  const detail = path === '/api/detail';
  try {
    const response = await fetch(path, options).catch(cause => {
      if (signal?.aborted || !detail && !['/api/data', '/api/reports'].includes(path) && !path.startsWith('/api/jobs/')) throw cause;
      throw retryableReadError(detail ? 'detail_transport_unavailable' : 'report_transport_unavailable', cause);
    });
    const identity = response.headers?.get('X-CG-Instance');
    if (identity && hostInstance && identity !== hostInstance) {
      connectionStatus('HOST IDENTITY CHANGED — NOT LIVE. Use a fresh authorized launcher link.',
        {kind: 'identity_changed', terminal: true, writable: false});
      throw new Error('host_identity_changed');
    }
    const data = response.ok && attachment ? null : await response.json().catch(cause => {
      // Headers can arrive before a transport fault. Malformed JSON (SyntaxError)
      // and definitive HTTP errors do not qualify for Detail's bounded read retry.
      if (detail && response.ok && !signal?.aborted &&
          (cause instanceof TypeError || timedOut && cause.name === 'AbortError'))
        throw retryableReadError('detail_transport_unavailable', cause);
      throw cause;
    });
    if (response.ok && identity) hostInstance = identity;
    if (!response.ok) {
      if (response.status === 401 || data.error === 'csrf_required') {
        connectionStatus('AUTHENTICATION EXPIRED — NOT LIVE. Use a fresh launcher link.',
          {kind: 'authorization_required', terminal: true, writable: false});
      } else if (data.error === 'instance_stopping') {
        connectionStatus('STOPPED — NOT LIVE. Use a fresh launcher link.',
          {kind: 'stopped', terminal: true, writable: false});
      }
      const error = new Error(data.error || 'request_unavailable');
      error.retryable = data.retryable === true;
      throw error;
    }
    if (hostState.terminal) throw new Error('instance_stopping');
    if (attachment) {
      const disposition = response.headers.get('Content-Disposition') || '';
      const filename = /^attachment; filename="(opencode-ses_[A-Za-z0-9_-]{1,160}-analysis\.zip)"$/.exec(disposition)?.[1];
      const length = Number(response.headers.get('Content-Length'));
      // Keep this in sync with MAX_ARCHIVE_BYTES on the server.
      if (!identity || !filename || !Number.isInteger(length) || length <= 0 || length > 64 * 1024 * 1024 ||
          response.headers.get('Content-Type') !== 'application/zip') throw new Error('export_invalid_response');
      const blob = await response.blob();
      if (blob.size !== length || controller.signal.aborted || hostState.terminal) throw new Error('export_invalid_response');
      return {blob, filename};
    }
    return data;
  } catch (error) {
    if (attachment && timedOut) throw new Error('export_timed_out', {cause: error});
    throw error;
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
  if (automaticHistory(state)) {
    refresh.hidden = true;
    heading.hidden = true;
    output.setAttribute('aria-busy', state.loading && (!state.result || state.withheld) ? 'true' : 'false');
     if (state.section !== 'token-mix' && state.userInitiated && state.failed) notice.textContent = state.message;
  } else { refresh.textContent = 'Refresh snapshot'; refresh.hidden = false; heading.hidden = false; }
   if (state.section === 'models') { refresh.textContent = 'Try again'; refresh.hidden = !state.failed || !!state.result; heading.hidden = true; }
  const toolbar = document.querySelector('.toolbar');
  if (toolbar) toolbar.hidden = refresh.hidden && heading.hidden;
  if (state.section === 'ai-stats') {
    const blocked = historyBlocked();
    output.setAttribute('aria-busy', String(state.loading && !state.result && !blocked &&
      !state.interrupted && !state.statsAcquisitionFailed));
    ReportView.defaultUnit();
    state.stats ||= new AIStatsView.View(period => selectStats(state, period));
    state.stats.update(state, blocked); state.stats.attach(output);
    return;
  }
  if (state.section === 'token-mix') {
    ReportView.defaultUnit();
    state.tokenMix ||= new TokenMixView.View(period => selectTokenMix(state, period));
    const ready = !!state.result && !state.withheld && TokenMixView.compatible(state.result, state.period) &&
      (!state.mixBinding || state.mixBinding === tokenMixBinding);
    output.setAttribute('aria-busy', String(!ready && !state.failed && !state.interrupted && !historyBlocked()));
    state.tokenMix.selection(state.period || 'all', ready);
    if (ready) state.tokenMix.update(state.result);
    state.tokenMix.attach(output);
    if (!ready) {
      state.mixLoading ||= ReportView.element('div');
      if (state.mixLoading.parentNode !== state.tokenMix.root) state.tokenMix.root.append(state.mixLoading);
      ReportLoading.show(state.mixLoading, state);
    } else state.mixLoading?.remove();
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
    if (!historyBlocked()) state.detail.attach(output);
    else output.replaceChildren(state.detail.root);
  } else if (state.catalog) {
    ReportView.syncUnits(state.catalog.root);
    if (!historyBlocked()) state.catalog.attach(output);
    else if (state.catalog.root.parentNode !== output) output.replaceChildren(state.catalog.root);
  } else if (state.live) {
    state.connection = liveStatus;
    state.connectionKind = hostState.kind;
    if (state.section === 'accounts') {
      state.accounts ||= new AccountCards.View(true);
      state.accounts.update(liveValue?.view || {});
      state.accounts.attach(output);
      if (accountTimelineAvailable) {
        state.accountTimeline ||= new AccountTimelineView.View(api, () => demand?.update());
        const chart = state.accountTimeline;
        chart.sharedHistory = archiveHistory;
        if (!archiveHistory && !historyBlocked()) chart.setScope(liveValue?.account_timeline_scope ?? null);
        if (state.accounts.root.lastChild !== chart.root) state.accounts.root.append(chart.root);
        chart.active(!document.hidden && !!csrf && (hostState.writable || archiveReadable()));
      }
    } else if (liveValue?.view) {
      state.miniControls = miniWatch?.button.parentNode;
      ReportView.renderLive(output, liveValue, state);
    } else {
      // Host/source health owns startup and failure feedback, not an elapsed timer.
      output.replaceChildren();
    }
   } else if (state.result) {
    // Connection/source status is not a new frozen report. Replacing its DOM
    // discards scroll, focus and selection during ordinary health checks.
    const retained = snapshotRender?.state === state &&
      snapshotRender.result === state.result && snapshotRender.search === state.search &&
      snapshotRender.first === output.firstChild;
    if (!retained) {
      const scroll = output.querySelector('.overview-models')?.scrollLeft;
      ReportView.render(output, state.result, state);
      if (scroll != null && state.section === 'models') output.querySelector('.overview-models').scrollLeft = scroll;
      snapshotRender = {state, result: state.result, search: state.search, first: output.firstChild};
    }
    state.priceControls?.(!!csrf && hostState.writable);
    state.benchmark?.controls(!!csrf && hostState.writable, api);
    // Initial attach only. Independent polling/route entry, not price publication,
    // owns subsequent benchmark lookups.
    if (state.section === 'models' && state.benchmark && (!state.benchmark.checked || state.benchmark.manual) &&
        csrf && hostState.writable && !document.hidden) state.benchmark.load(api);
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
function failure(code, state) {
  return 'Could not load. Try again.';
}
async function acquire(state, background = false, prices = false) {
  if (state.loading || !reportReadable(state)) return;
  // A disabled native button loses focus before the replacement DOM is captured.
  // Restore only this explicit action, unless the user focused/clicked elsewhere.
  let priceFocus = prices && document.activeElement?.getAttribute('data-model-control') === 'refresh' &&
    (typeof ControlFocus === 'undefined' ? document.activeElement.matches(':focus-visible') : ControlFocus.keyboard(document));
  const movedPriceFocus = event => {
    if (event.target?.getAttribute('data-model-control') !== 'refresh') priceFocus = false;
  };
  const priceFocusEvents = priceFocus ? ['focusin', 'pointerdown'] : [];
  for (const event of priceFocusEvents) document.addEventListener(event, movedPriceFocus);
   const request = state.request;
   const mix = state.section === 'token-mix';
    state.userInitiated = !background && (prices || state.actionRequested === true);
    state.actionRequested = false;
  if (state.section === 'ai-stats' && state.userInitiated) state.statsAcquisitionFailed = false;
  let publication = null;
  let retry = !!state.failed && !background && !automaticHistory(state);
  state.loading = true;
  const attempt = state.attempt = new ReportLoading.Attempt({paging: state.pageNavigation === true});
  state.priceRefreshing = prices; state.priceMessage = '';
  state.failed = false;
  state.dispatchError = null;
  if (mix) state.mixFailure = null;
  ReportLoading.reset(state);
  state.lastWork = null;
  ReportLoading.observe(state, {phase: 'queued'});
   state.message = state.userInitiated ? 'Loading…' : '';
  show(state);
   let keepRetained = false;
   function canRetry(error) {
     return mix ? ReportLoading.retryable(error) || error.retryable === true : ReportLoading.retryable(error);
   }
   async function pause(error) {
     ReportLoading.waiting(state, error.message, attempt.paging ? attempt.retries + 1 : null); show(state);
     await attempt.backoff(error, mix);
   }
   async function admit() {
    while (true) {
      attempt.check(hostState, true);
      try {
        const scope = state.section === 'ai-stats' ? state.request : request;
        const retryOnce = retry;
        retry = false; // Only the explicit user attempt may clear host backoff.
         const admission = await api(prices ? '/api/models/refresh' : demand ? '/api/data' : '/api/reports', prices ? {} :
           demand ? {request: scope, retry: retryOnce} : scope, attempt.controller.signal);
        if (state.attempt !== attempt) return;
         state.active = admission.id;
         state.waitingReason = null;
        if (attempt.retries && !automaticHistory(state)) ReportLoading.reset(state);
        if (demand && !prices) {
          // Retained publication identity is independent of an active refresh.
           state.dispatchRefresh = admission.refresh;
           state.dispatchError = admission.terminal ? admission.error || 'report_unavailable' : null;
           if (state.section === 'ai-stats' && scope === state.request && state.statsAcquisitionFailed &&
               admission.terminal === false && !admission.result) {
             state.statsAcquisitionFailed = false;
             show(state);
           }
           if (mix) bindTokenMix(state, admission);
           else if (admission.error === 'source_identity_changed' && automaticHistory(state)) {
               state.result = null; state.statsResults?.clear(); state.statsIdentity = 'invalidated';
            }
           if (!admission.result && state.result && !automaticHistory(state) && !state.pageNavigation) { state.withheld = true; show(state); }
          if (admission.result) publication = {status: 'complete', result: admission.result,
             publication_id: admission.result_id || admission.id};
           else if (admission.cache_first) {
             await attempt.poll(null, 500); continue; // Wait only for the host's local projection.
           }
           else if (mix && state.result && !admission.terminal && TokenMixView.compatible(state.result, state.period)) {
             keepRetained = true; return; // Let the host finish a quiet refresh.
           }
           else if (!admission.id && !admission.terminal && automaticHistory(state)) {
             ReportLoading.waiting(state, admission.error || 'report_pending'); show(state);
             await attempt.poll(null, 5000); continue; // Host due/backoff owns readmission, not explicit Retry.
           } else if (admission.terminal || !admission.id) throw new Error(admission.error || 'report_unavailable');
        }
        state.progressSequence = 0;
        return;
      } catch (error) {
         if (!canRetry(error)) throw error;
         if (mix && state.result && TokenMixView.compatible(state.result, state.period)) { keepRetained = true; return; }
         await pause(error);
      }
    }
  }
  try {
    await admit();
    if (state.attempt !== attempt) return;
    if (state.section === 'ai-stats' && request.stats_scope !== state.request.stats_scope)
      AIStatsView.prioritize(state, api, !!demand);
    show(state);
    while (!keepRetained) {
      // Poll the same logical work even after a long hidden/background period.
      attempt.check(hostState);
       const published = !!publication;
       let job;
       try {
         job = publication || await api('/api/jobs/' + state.active, undefined, attempt.controller.signal);
       } catch (error) {
         if (!mix || state.attempt !== attempt) throw error;
         if (demand && error.message === 'not_found') {
           await attempt.poll(null, 5000); await admit(); continue;
         }
         if (!canRetry(error)) throw error;
         await pause(error); continue; // A failed HTTP poll does not retire the host job.
       }
        publication = null;
       if (state.attempt !== attempt) return;
      attempt.check(hostState);
      const statsProgress = state.section === 'ai-stats' && AIStatsView.observe(state, job);
      if (job.progress?.stage?.startsWith('date-')) state.lastWork = reportWork(job.progress);
      if (!['queued', 'running'].includes(job.status)) {
        if (mix && demand && !published) {
          // Dispatcher owns calendar/identity qualification and the atomic
          // swap. A finished worker may be stale or weaker than the last good result.
          const finished = state.active;
          state.active = null; await admit();
          if (state.active === finished && !publication && !keepRetained) await attempt.poll(null, 5000);
          continue;
        }
          if (job.status !== 'complete' || !job.result || job.result.error) {
           if (demand && automaticHistory(state)) { state.active = null; await admit(); continue; }
          const error = new Error(job.result?.error?.code || job.error || job.status);
          error.retryable = job.result?.error?.retryable === true;
            if (!ReportLoading.retryable(error)) throw error;
           state.active = null; ReportLoading.waiting(state, error.message, attempt.paging ? attempt.retries + 1 : null); show(state);
          await attempt.backoff(error); await admit(); continue;
        }
        if (hostState.terminal) break;
           if (state.section === 'token-mix' && (!TokenMixView.valid(job.result) ||
               job.result.view.token_mix_period?.period !== state.period)) throw new Error('report_invalid_result');
          if (state.section === 'ai-stats' && !AIStatsView.valid(job.result)) throw new Error('report_invalid_result');
          if (state.section === 'ai-stats' && !job.result.view.ai_stats_work?.scopes?.[state.period]?.ready) {
            // A finished slice is not a ready period. Keep demand and a bounded
            // lookup interval even for an old host's incomplete publication.
            await attempt.poll(null, 5000); await admit(); continue;
         }
          const initial = !state.result || state.withheld;
          const revision = [job.publication_id || state.active, job.result.instance_id,
            job.result.sequence, CachedReports.observation(job.result)].join(':');
          if (demand && !prices && state.result && state.dataRevision === revision) break;
         if (state.section === 'models' && (!job.result.view || job.result.view.kind !== 'normal' ||
             !['acquired', 'partial'].includes(job.result.source?.status))) throw new Error('report_unavailable');
          if (state.section === 'ai-stats') {
            AIStatsView.remember(state, job.result);
            if (!state.result) throw new Error('report_unavailable');
          } else state.result = job.result;
          state.dataRevision = revision;
          if (demand && !prices && !job.publication_id) state.dispatchRefresh = 'scheduled';
         // A usable partial response finishes this attempt, not source coverage.
           if (state.result && !mix) {
            state.percent = 100; state.stage = state.stageLabel = 'Report ready';
            if (initial && !job.result.cache_first && state === current && state.loader?.root.isConnected)
              await ReportLoading.paintCompletion(state, attempt.controller.signal);
          }
         if (mix) state.percent = 100; // No completion paint on Token Mix's indeterminate loader.
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
    if (state.attempt !== attempt) return;
    if (attempt.reason) error = new Error(attempt.reason);
    if (mix) state.mixFailure = error.message;
    state.message = prices || state.userInitiated ? 'Could not load. Try again.' : '';
    if (prices) state.priceMessage = state.message;
    state.failed = !prices; // A retained price failure belongs only to its toolbar.
  } finally {
     const owned = state.attempt === attempt;
      if (owned) {
      if (state.dispatchError && !prices) { state.failed = true; state.message = state.userInitiated ? failure(state.dispatchError, state) : ''; }
      // A background lookup alone does not make failed metrics pending again.
      if (state.section === 'ai-stats' && state.failed && !ReportLoading.interrupted(hostState) && !historyBlocked())
        state.statsAcquisitionFailed = true;
      state.loading = false; state.priceRefreshing = false; state.active = null; state.attempt = null; state.checkedAt = Date.now();
      show(state); scheduleCachedReport();
     }
    for (const event of priceFocusEvents) document.removeEventListener(event, movedPriceFocus);
    if (owned && priceFocus && state === current && document.activeElement === document.body)
      output.querySelector('[data-model-control="refresh"]')?.focus({preventScroll: true});
    if (owned && state === current && state.section === 'ai-stats' && !state.result && !state.failed && !document.hidden &&
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
  if (match) rememberedSession = '#/sessions/' + match[1];
  else if (route.catalog) rememberedSession = null; // Explicit list URLs/history always win.
  if (sessionsNav) sessionsNav.setAttribute('href', rememberedSession || '#/sessions');
  document.title = `${route.title} · Cost Guard`;
  document.body.dataset.section = route.section;
  const key = match ? 'session/' + match[1] : route.section === 'sessions' ? 'sessions-catalog' : location.hash || '#/models';
  heading.textContent = route.title;
   ReportRoutes.controls(document.getElementById('scope-controls'), route);
  for (const item of document.querySelectorAll('nav a')) {
    if (item === sessionsNav && route.section === 'sessions' ||
        item !== sessionsNav && item.getAttribute('href') === '#/' + route.section) item.setAttribute('aria-current', 'page');
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
      mixBinding: cached?.mixBinding,
      pages: {}, loading: false, active: null,
      message: route.live ? 'Live acquisition starting; one runtime shared across tabs.' : cached ?
        (demand ? 'Reusing the last verified observation; the host checks freshness.' : 'Snapshot captured. Reused frozen observation.') :
        request ? (demand ? 'Loading the host-owned report…' : 'Capture/Refresh to acquire this report.') : 'Choose a report scope.'});
  }
  const previous = current;
  if (current?.detail) {
    current.detailScroll = window.scrollY;
    current.detailFocus = current.detail.root.contains(document.activeElement) ? document.activeElement : null;
  }
  if (current?.detail) current.detail.detach();
  current = views.get(key);
  if (current !== previous) {
    previous?.catalog?.detach();
    previous?.accountTimeline?.active(false);
  }
  // A requested report (including bounded admission backoff) belongs to its view,
  // not the active route. Navigation never abandons it or starts another attempt.
  if (current.section === 'ai-stats') {
    current.period ||= '30-days'; current.statsResults ||= new Map();
    current.request = {kind: 'ai-stats', stats_scope: current.period};
  }
  if (current.section === 'token-mix') {
    current.period ||= current.request?.token_mix_scope || 'all';
    current.request = {kind: 'token-mix', token_mix_scope: current.period};
  }
  if (route.section === 'models') {
    const models = current;
    models.refreshPrices = () => acquire(models, false, true);
    if (csrf && hostState.writable && !document.hidden) models.benchmark?.load(api);
  }
  document.getElementById('search').value = current.search || '';
  if (match && csrf && !hostState.terminal && sessionDetailAvailable && !current.detail) {
    current.detail = new SessionDetail.View(api, match[1],
      () => hostState.kind === 'connected' && !hostState.sourceBlocked ? liveValue : null);
    current.message = '';
  }
  if (match && current.detail) {
    // Origin belongs to this history entry, not a cached detail or global preference.
    // Reload/Back/Forward retain it; Watch, pasted URLs and new tabs do not inherit it.
    const origin = history.state?.sessionsReturn;
    current.detail.back.href = origin?.detail === location.hash ? origin.list : '#/sessions';
  }
   if (route.catalog && csrf && sessionDetailAvailable && typeof SessionsCatalog !== 'undefined') {
    if (!current.catalog) {
      current.catalog = new SessionsCatalog.View(api);
      current.catalog.sourceHealth(historyBlocked() || hostState.sourceBlocked || hostState.sourceOutage, historyBlocked());
    }
    current.catalog.configure(route.params);
     current.request = null; current.message = '';
   }
   if ((match || route.catalog) && csrf && !sessionDetailAvailable) current.message = 'Live session source unavailable.';
  document.getElementById('search').disabled = !!current.detail;
  show(current);
  if (csrf && !hostState.terminal && current.stats && (current !== previous || !current.stats.databaseRefresh))
    current.stats.refreshDatabaseSizes();
  if (current !== previous && current.detail) {
    if (current.detailFocus?.isConnected) current.detailFocus.focus({preventScroll: true});
    else focusReport({preventScroll: true});
    window.scrollTo(0, current.detailScroll || 0);
  }
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
   catch (_) { /* Saved settings are optional here; explicit Settings owns errors. */ }
     const state = await api('/api/status');
     archiveHistory = state.archive_history === true;
     if (state.data_dispatcher && typeof DataDemand !== 'undefined') {
       // This controller writes only expiring view leases, not source/settings mutations.
       const writable = () => !!csrf && (hostState.writable || archiveReadable());
       demand = new DataDemand.Controller(api, () => current && {...current, history: false}, writable,
         {history: state.history_demand === true});
       if (state.history_demand === true) miniWatch?.setDemandFactory(win => new DataDemand.Controller(api,
         () => ({section: 'watch', history: miniWatch.window === win && miniWatch.view?.needsHistory !== false}),
         writable, {owner: win, history: true}));
     }
    if (typeof state.product_version === 'string') document.getElementById('product-version').textContent = state.product_version;
    sessionDetailAvailable = state.session_detail === true && typeof SessionDetail !== 'undefined';
    accountTimelineAvailable = state.account_timeline === true && typeof AccountTimelineView !== 'undefined';
   statusLine.textContent = '';
    if (!liveConnection && typeof LiveConnection !== 'undefined') {
      liveConnection = LiveConnection.connect(api, (value, progress, watchHistory, historyHints, reconnected) => {
        const firstLiveView = !sourceValue?.view && !!value?.view;
        sourceValue = value?.view || !sourceValue?.view ? value : {...value,
          view: sourceValue.view, source_observed_at_ms: sourceValue.source_observed_at_ms};
        liveValue = watchValue(sourceValue, watchHistory);
        // A first entry can precede source selection. Use the existing Live
        // readiness signal once rather than polling the optional facts.
        if (firstLiveView && current?.stats && !current.stats.hasOpenCodeSize)
          current.stats.refreshDatabaseSizes();
        miniWatch?.update(liveValue);
        if (reconnected) {
          current?.catalog?.catchUp();
          if (archiveReadable()) current?.detail?.catchUp();
        }
        current?.catalog?.wake(historyHints?.catalog_hint ?? value?.catalog_hint);
        current?.detail?.wake(historyHints?.detail_hints ?? value?.detail_hints);
        current?.detail?.updateInvocations();
        if (current?.live) { current.message = 'Live observation; source/account freshness shown below.'; show(current); }
        for (const job of progress?.jobs || []) {
            if (current?.active === job.id && !ReportLoading.sections.includes(current.section)) {
             notice.textContent = current.userInitiated ? 'Loading…' : '';
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
   if (current?.request) { current.actionRequested = true; acquire(current); }
});
output.addEventListener('click', event => {
  const link = event.target.closest?.('a.session-name');
  if (!current?.catalog || !link || event.defaultPrevented || event.button !== 0 ||
      event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || link.target || link.hasAttribute('download')) return;
  const detail = link.getAttribute('href');
  if (!/^#\/sessions\/[A-Za-z0-9_-]{1,200}$/.test(detail)) return;
  event.preventDefault();
  // Push one ordinary entry, carrying only canonical filters (never offset/epoch/data).
  history.pushState({sessionsReturn: {detail, list: current.catalog.firstPageDestination()}}, '', detail);
  navigate(); // pushState does not emit hashchange; native Back/Forward still does.
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
window.addEventListener('focus', () => current?.detail?.catchUp());
if (sessionsNav) {
  sessionsNav.addEventListener('click', event => {
    if (rememberedSession || event.button > 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const catalog = views.get('sessions-catalog')?.catalog;
    if (catalog?.sectionDestination) { event.preventDefault(); location.hash = catalog.sectionDestination(); }
  });
}
window.addEventListener('offline', () => connectionStatus('OFFLINE — last observation retained, not live. Check the connection and reload to retry.', {kind: 'offline', writable: false}));
window.addEventListener('online', () => liveConnection?.resync(true));
document.addEventListener('visibilitychange', () => {
  current?.catalog?.interest();
  current?.accountTimeline?.active(!document.hidden && !!csrf && (hostState.writable || archiveReadable()));
  // Keep existing acquisitions, but never schedule new hidden-route refreshes.
  if (!document.hidden) liveConnection?.resync();
  if (!document.hidden) {
    current?.catalog?.poll(); current?.detail?.catchUp();
    enterCachedReport(current);
    firstReport();
  }
  scheduleCachedReport();
});
document.getElementById('search').addEventListener('input', event => {
  if (current) { current.search = event.target.value; current.pages = {}; show(current); }
});
document.getElementById('skip').addEventListener('click', () => focusReport());
navigate();
connect();
