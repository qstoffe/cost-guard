'use strict';
// Pending-work presentation and admission only; never scans or clock-driven progress.
const ReportLoading = (() => {
  const sections = ['models', 'token-mix', 'ai-stats', 'comparisons'];
  const phases = {authorizing: [0, 5, 'Authorizing browser session'], queued: [5, 10, 'Waiting for report slot…'],
    pricing: [10, 20, 'Loading reference prices'], catalog: [20, 30, 'Loading source'],
    history: [30, 80, 'Checking history'], projection: [80, 94, 'Preparing report'],
    availability: [85, 90, 'Checking model availability'], finalizing: [94, 99, 'Preparing report']};
  const normal = {sampling: [30, 48, 'Sampling recent sessions'], availability: [48, 50, 'Checking model availability'],
    comparison: [50, 56, 'Comparing models'], models: [56, 62, 'Preparing model catalog'],
    quotas: [62, 64, 'Acquiring accounts'], 'account-cache': [64, 70, 'Checking account history cache'],
    'account-load': [70, 73, 'Loading account history'], 'account-analysis': [73, 88, 'Analyzing account history'],
    'account-projection': [88, 94, 'Preparing account periods'], finalizing: [94, 99, 'Preparing report']};
  const history = {'history-cache': [30, 45, 'Checking history cache'],
    'history-load': [45, 80, 'Updating changed history'], 'history-projection': [80, 94, 'Preparing report'],
    'comparison-verify': [80, 84, 'Verifying history revisions'],
    'comparison-groups': [84, 86, 'Preparing matched groups'],
    'comparison-previews': [86, 94, 'Reading page previews'],
    finalizing: [94, 99, 'Preparing report']};
  const nested = {'date-cache': 'Checking batch cache', 'date-load': 'Loading history batch',
    'date-catalog-before': 'Reading before-catalog', 'date-messages': 'Reading session trees',
    'date-catalog-after': 'Verifying after-catalog', 'date-analysis': 'Analyzing history batch'};
  function reset(state) {
    Object.assign(state, {percent: 0, progressSequence: 0, progressStart: 0, stagedProgress: false, waitingReason: null,
      stage: 'Authorizing browser session', stageLabel: 'Authorizing browser session'});
  }
  function observe(state, progress = {}) {
    if (Number.isFinite(progress.sequence)) {
      if (progress.sequence <= (state.progressSequence || 0)) return;
      state.progressSequence = progress.sequence;
    }
    state.waitingReason = null;
    const measured = Number.isFinite(progress.completed) && Number.isFinite(progress.total) && progress.total > 0;
    const completed = Math.max(0, progress.completed || 0);
    const counts = measured ? ` (${completed.toLocaleString()}/${progress.total.toLocaleString()})` : '';
    const models = !state.section || state.section === 'models';
    if (!models && nested[progress.stage]) {
      if ((state.progressStart || 0) >= 80) return;
      state.stageLabel = nested[progress.stage]; state.stage = state.stageLabel + counts;
      return; // Batch-local counts cannot consume the whole-history denominator.
    }
    const owned = (models ? normal : history)[progress.stage];
    if (state.stagedProgress && !owned) return;
    if (owned) state.stagedProgress = true;
    const fallback = models ? {history: [30, 55, 'Loading source history'],
      projection: [55, 70, 'Comparing models'], quotas: [70, 90, 'Acquiring accounts']} : {};
    const [start, end, label] = owned || fallback[progress.phase] || phases[progress.phase] || [5, 10, 'Acquiring report'];
    if (start < (state.progressStart || 0)) return;
    state.progressStart = start;
    const fraction = measured ? Math.max(0, Math.min(1, completed / progress.total)) :
      progress.stage === 'sampling' ? completed / (completed + 8) : 0;
    state.percent = Math.max(state.percent || 0, Math.min(99, Math.floor(start + (end - start) * fraction)));
    state.stageLabel = label;
    state.stage = label + (counts || (progress.stage === 'sampling' && completed ? ` (${completed} completed)` : ''));
  }
  function waiting(state, code, attempt) {
    state.waitingReason = code;
    state.stageLabel = code === 'busy' ? 'Waiting for report slot…' : 'Waiting for source…';
    state.stage = state.stageLabel + (attempt ? ` Recovery ${Math.min(3, attempt)}/3 (${code}).` : '');
  }
  class View {
    constructor(root) {
      const e = ReportView.element;
      this.root = root || e('div', undefined, 'report-loading');
      if (!root) {
        const bar = e('progress'); bar.max = 100; bar.value = 0;
        bar.setAttribute('aria-label', 'Report loading progress');
        const percent = e('p', '', 'report-loading-percent'); percent.setAttribute('aria-hidden', 'true');
        const stage = e('p', '', 'report-loading-stage');
        const status = e('p', '', 'sr-only'); status.setAttribute('role', 'status');
        this.root.append(bar, percent, stage, status);
      }
      this.bar = this.root.querySelector('progress');
      this.percent = this.root.querySelector('.report-loading-percent');
      this.stage = this.root.querySelector('.report-loading-stage');
      this.status = this.root.querySelector('.sr-only');
    }
    update(state) {
      const percent = state.percent || 0;
      if (state.waitingReason) this.bar.removeAttribute('value');
      else this.bar.value = percent;
      this.bar.setAttribute('aria-valuetext', state.waitingReason ? state.stage : `${percent} percent`);
      ReportView.text(this.percent, state.waitingReason ? 'Waiting' : `${percent}%`);
      ReportView.text(this.stage, state.stage || 'Authorizing browser session');
      // Announce stage transitions, not every count/poll/percentage mutation.
      ReportView.text(this.status, state.stageLabel || 'Authorizing browser session');
    }
  }
  function show(parent, state) {
    if (state.failed || state.interrupted) {
      state.loadingError ||= ReportView.element('p', '', 'error');
      state.loadingError.setAttribute('role', 'alert');
      ReportView.text(state.loadingError, state.failed ? state.message : state.interrupted);
      if (parent.firstChild !== state.loadingError) parent.replaceChildren(state.loadingError);
      return;
    }
    state.loader ||= new View(parent.querySelector('.report-loading'));
    state.loader.update(state);
    if (parent.firstChild !== state.loader.root) parent.replaceChildren(state.loader.root);
  }
  function paintCompletion(state, signal) {
    state.loader?.update(state);
    if (typeof requestAnimationFrame !== 'function' || document.hidden) return;
    // Permit one real completion paint, never hold a hidden/cancelled document
    // waiting for animation frames (background browsers may suspend them).
    return new Promise(resolve => {
      let frame;
      const finish = () => {
        cancelAnimationFrame(frame);
        document.removeEventListener('visibilitychange', finish);
        signal.removeEventListener('abort', finish); resolve();
      };
      document.addEventListener('visibilitychange', finish, {once: true});
      signal.addEventListener('abort', finish, {once: true});
      if (signal.aborted) finish();
      else frame = requestAnimationFrame(() => { frame = requestAnimationFrame(finish); });
    });
  }
  const transient = ['registration_missing', 'endpoint_unresponsive', 'connection_refused',
    'connection_reset', 'connection_disconnected', 'connection_timeout', 'http_status_failure',
    'concurrent_source_change', 'history_revision_churn', 'ai_stats_revision_churn', 'ai_stats_checkpoint_busy', 'session_catalog_changed'];
  function retryable(error) {
    return ['busy', 'source_starting'].includes(error.message) ||
      error.retryable === true && (error.message === 'source_unavailable' || transient.includes(error.message));
  }
  function interrupted(host) {
    return host.terminal || ['offline', 'stopped', 'identity_changed', 'authorization_required'].includes(host.kind);
  }
  class Attempt {
    constructor({paging = false} = {}) {
      this.retries = 0;
      this.paging = paging; this.advancedAt = Date.now(); this.work = new Map();
      this.controller = new AbortController(); this.reason = null;
      this.waiting = null; this.hint = null; this.woken = null;
    }
    cancel(reason = 'cancelled') { this.reason = reason; this.controller.abort(); }
    check(host, pending = false) {
      if (this.reason) throw new Error(this.reason);
      // Stream reconnect is not failed HTTP/source readiness. Admission and typed
      // replies prove the finite source independently of the Live connection.
      if (interrupted(host)) throw new Error(host.kind);
      if (pending && this.paging && Date.now() - this.advancedAt >= 45000) throw new Error('comparison_page_no_progress');
    }
    observe(progress) {
      if (!this.paging || !progress) return;
      const key = progress.stage || progress.phase, completed = progress.completed || 0;
      if (!this.work.has(key) || completed > this.work.get(key)) {
        this.work.set(key, completed); this.advancedAt = Date.now();
      } // New sequence numbers or revisiting old counts are not forward progress.
    }
    pause(milliseconds, job) {
      return new Promise((resolve, reject) => {
        const signal = this.controller.signal;
        let waiter = null;
        const settle = () => {
          clearTimeout(timer); signal.removeEventListener('abort', aborted);
          if (this.waiting === waiter) this.waiting = null;
        };
        const aborted = () => { settle(); reject(new Error(this.reason || 'cancelled')); };
        const timer = setTimeout(() => { settle(); resolve(); }, Math.max(0, milliseconds));
        if (signal.aborted) return aborted();
        signal.addEventListener('abort', aborted, {once: true});
        if (job !== undefined) this.waiting = waiter = {job, wake: () => { settle(); resolve(); }};
      });
    }
    // Only a status-poll wait may end early, once per job; the authenticated job
    // fetch that follows stays authoritative and recovery backoff is never shortened.
    poll(job, milliseconds) {
      const hinted = this.hint === job; this.hint = null;
      if (hinted && !this.reason && this.woken !== job) { this.woken = job; return Promise.resolve(); }
      return this.pause(milliseconds, job);
    }
    notify(job) {
      if (this.reason || this.woken === job) return;
      if (!this.waiting) { this.hint = job; return; }
      if (this.waiting.job !== job) return;
      // The caller admits only its current active identity; retired jobs never
      // return here. An unlimited recovery lifetime needs no retired-ID ledger.
      this.woken = job; this.waiting.wake();
    }
    async backoff(error) {
      if (!retryable(error)) throw error;
      if (this.paging && this.retries >= 3) throw new Error('comparison_page_retries');
      this.retries = Math.min(4, this.retries + 1);
      await this.pause(Math.min(4000, 500 * 2 ** (this.retries - 1)));
    }
  }
  return {sections, reset, observe, waiting, show, paintCompletion, View, Attempt, retryable, interrupted};
})();
