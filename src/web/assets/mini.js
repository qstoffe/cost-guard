'use strict';
// App-owned PiP presentation. No auth, source calls, totals or lifecycle inference.
const MiniWatch = (() => {
  function unavailable(owner) {
    if (!owner.isSecureContext) return 'Requires a secure browser context (loopback is supported).';
    if (owner.top !== owner) return 'Open Cost Guard in a top-level browser tab.';
    if (typeof owner.documentPictureInPicture?.requestWindow !== 'function')
      return 'Document Picture-in-Picture is unavailable in this browser.';
    const policy = owner.document.permissionsPolicy || owner.document.featurePolicy;
    if (policy?.allowsFeature && !policy.allowsFeature('picture-in-picture'))
      return 'Picture-in-Picture is disabled by browser policy.';
    return '';
  }
  class View {
    constructor(doc, returnToWatch, close) {
      this.doc = doc;
      const el = (tag, text, name) => {
        const node = doc.createElement(tag);
        if (text !== undefined) node.textContent = text;
        if (name) node.className = name;
        return node;
      };
      this.root = el('main', undefined, 'mini-card');
      const top = el('div', undefined, 'mini-top');
      this.summary = el('button', undefined, 'mini-summary'); this.summary.type = 'button';
      this.summary.setAttribute('aria-label', 'Return to Watch in the existing Cost Guard tab');
      this.summary.title = 'Return to Watch. If the browser cannot restore a minimized window, use its native return-to-tab control.';
      this.summary.addEventListener('click', returnToWatch);
      this.summary.append(el('span', 'Cost Guard · Watch', 'mini-brand'));
      const metrics = el('span', undefined, 'mini-metrics');
      this.values = [];
      for (const label of ['Running prompts', 'Running CCost', 'Longest running']) {
        const group = el('span'), value = el('strong', '—');
        group.append(el('span', label, 'mini-label'), value); metrics.append(group); this.values.push(value);
      }
      this.summary.append(metrics);
      const exit = el('button', '×', 'mini-close'); exit.type = 'button';
      exit.setAttribute('aria-label', 'Close Mini Watch'); exit.title = 'Close Mini Watch';
      exit.addEventListener('click', close);
      top.append(this.summary, exit);
      this.health = el('p', 'Acquiring live prompts…', 'mini-health'); this.health.setAttribute('role', 'status');
      this.accounts = el('ul', undefined, 'mini-accounts'); this.lines = new Map();
      this.root.append(top, this.health, this.accounts); doc.body.replaceChildren(this.root);
    }
    update(publication, health, overdue) {
      const view = publication?.view, running = view?.running;
      const fresh = health.kind === 'connected' && publication?.state === 'running' && !overdue;
      const text = ReportView.text, display = ReportView.display;
      text(this.values[0], running?.count ?? '—');
      text(this.values[1], running?.ccost == null ? '—' : display(running, 'ccost') + (running.cost_estimated ? ' ~' : ''));
      text(this.values[2], running?.duration_ms == null ? '—' : display(running, 'duration_ms'));
      const state = {authorization_required: 'Authorization expired', identity_changed: 'Host changed',
        stopped: 'Host stopped', offline: 'Offline', reconnecting: 'Reconnecting', source_unavailable: 'Source unavailable'}[health.kind];
      text(this.health, !fresh ? `${state || (overdue ? 'Waiting for live update' : 'Acquiring live prompts')} · ${view ? 'not live' : 'no observation yet'}` :
        running?.state === 'unavailable' ? 'Prompt source unavailable · retained values' :
        running?.state === 'loading' || !running ? 'Acquiring prompts · partial observation' :
        !running.complete || running.unresolved_cost ? 'Partial prompt / pricing data' : 'Live');
      this.root.dataset.live = fresh && running?.state === 'observed' ? 'true' : 'false';
      this.health.title = 'Figures use the last canonical publication; elapsed time is never extrapolated while disconnected.';
      const accounts = view?.accounts?.accounts;
      const wanted = [];
      for (const [index, item] of (accounts || []).entries()) {
        const obs = item.observation, primary = item.primary;
        const key = JSON.stringify([obs.label, index]);
        let line = this.lines.get(key);
        if (!line) { line = this.doc.createElement('li'); this.lines.set(key, line); }
        const used = primary.quota.unlimited ? 'Unlimited' : primary.used_percent === '—' ? 'Usage unavailable' : primary.used_percent + ' used';
        const cost = primary.cost, amount = cost == null || (cost.observed_requests && !cost.priced_requests) ? '—' : display(cost, 'known_ccost');
        const stale = !['available', 'partial'].includes(obs.availability) || view.quota_stale;
        text(line, `${obs.label} · ${used} (${primary.estimated && amount !== '—' ? '~' : ''}${amount})${stale ? ' · quota stale/unavailable' : ''}`);
        line.title = `${primary.quota.label} Used; same native-period CCost. ${primary.note || 'Period cost unavailable until verified history and boundaries are available.'}${primary.estimated ? ' ~ indicates estimated account attribution.' : ''}${cost && !cost.complete ? ' ? indicates partial pricing.' : ''}`;
        line.className = stale || primary.exhausted || primary.restricted ? 'mini-warning' : '';
        wanted.push(line);
      }
      if (!wanted.length) {
        if (!this.empty) this.empty = this.doc.createElement('li');
        text(this.empty, accounts ? 'No configured subscriptions' : 'Acquiring subscriptions…'); wanted.push(this.empty);
      }
      const keep = new Set(wanted);
      for (const child of [...this.accounts.children]) if (!keep.has(child)) child.remove();
      wanted.forEach((line, index) => {
        if (this.accounts.children[index] !== line) this.accounts.insertBefore(line, this.accounts.children[index] || null);
      });
      for (const [key, line] of this.lines) if (!keep.has(line)) this.lines.delete(key);
    }
  }
  class Controller {
    constructor(owner, button, feedback, returnToWatch) {
      this.owner = owner; this.button = button; this.feedback = feedback; this.returnToWatch = returnToWatch;
      this.window = null; this.view = null; this.pending = null; this.ended = false;
      this.publication = null; this.healthState = {kind: 'starting'}; this.receivedAt = 0;
      this.reason = unavailable(owner);
      button.addEventListener('click', () => this.toggle());
      owner.addEventListener('pagehide', () => { this.ended = true; this.close(); });
      this.sync();
    }
    sync() {
      const win = this.window;
      if (win && (win.closed || this.owner.documentPictureInPicture.window !== win)) this.release(win);
      this.button.textContent = `Mini Watch: ${this.window ? 'On' : 'Off'}`;
      this.button.setAttribute('aria-pressed', this.window ? 'true' : 'false');
      this.button.disabled = Boolean(this.reason);
      if (this.reason) this.feedback.textContent = this.reason;
    }
    release(win) {
      if (this.window !== win) return;
      win.clearInterval(this.timer);
      this.window = this.view = null;
    }
    close() {
      if (this.pending) this.pending.cancelled = true;
      const win = this.window;
      if (win) { this.release(win); win.close(); }
      this.feedback.textContent = '';
      this.sync();
    }
    async toggle() {
      this.sync();
      if (this.reason || this.ended) return;
      if (this.window) { this.close(); return; }
      if (this.pending) {
        this.pending.cancelled = true; this.feedback.textContent = 'Opening cancelled.'; return;
      }
      const request = {cancelled: false}; this.pending = request;
      this.feedback.textContent = 'Opening Mini Watch…';
      let win = null;
      try {
        // Called synchronously inside the explicit click's user activation.
        win = await this.owner.documentPictureInPicture.requestWindow({width: 380, height: 270});
        if (request.cancelled || this.ended || win.closed || this.owner.documentPictureInPicture.window !== win) {
          win.close(); return;
        }
        this.window = win;
        win.addEventListener('pagehide', () => { this.release(win); this.sync(); }, {once: true});
        const doc = win.document; doc.title = 'Mini Watch · Cost Guard'; doc.documentElement.lang = 'en';
        for (const name of ['app.css', 'mini.css']) {
          const link = doc.createElement('link'); link.rel = 'stylesheet';
          link.href = new URL('/' + name, this.owner.location.href).href; doc.head.append(link);
        }
        this.view = new View(doc, () => {
          this.returnToWatch();
          try { this.owner.focus(); }
          catch (_) { this.view.health.textContent = 'Use the browser’s native return-to-tab control.'; }
        }, () => this.close());
        // A visible PiP document owns this freshness timer, not a hidden main rAF.
        this.timer = win.setInterval(() => { this.sync(); this.render(); }, 5000);
        this.render(); this.feedback.textContent = '';
      } catch (_) {
        if (win) { this.release(win); win.close(); }
        this.feedback.textContent = 'Mini Watch could not open. Check browser support, policy and user-activation restrictions; click to retry.';
      } finally { this.pending = null; this.sync(); }
    }
    update(value) {
      // Progress events and repeated HTTP snapshots may contain the same retained
      // Live value. They are not fresh source/presentation publications.
      const epoch = JSON.stringify([value?.view?.now_ms, value?.source_observed_at_ms, value?.state]);
      if (epoch !== this.epoch) { this.epoch = epoch; this.receivedAt = Date.now(); }
      this.publication = value; this.sync(); this.render();
    }
    health(value) { this.healthState = value; this.sync(); this.render(); }
    settings() { this.render(); }
    render() {
      if (!this.view) return;
      this.view.doc.documentElement.dataset.theme = this.owner.document.documentElement.dataset.theme;
      this.view.update(this.publication, this.healthState, Date.now() - this.receivedAt > 15000);
    }
  }
  return {Controller};
})();
