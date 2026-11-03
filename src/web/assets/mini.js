'use strict';
// App-owned PiP presentation. No auth, source calls, totals or lifecycle inference.
const MiniWatch = (() => {
  function reconcile(parent, wanted) {
    const keep = new Set(wanted);
    for (const node of [...parent.children]) if (!keep.has(node)) node.remove();
    wanted.forEach((node, index) => {
      if (parent.children[index] !== node) parent.insertBefore(node, parent.children[index] || null);
    });
  }
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
    constructor(doc, returnToWatch) {
      this.doc = doc;
      const el = (tag, text, name) => {
        const node = doc.createElement(tag);
        if (text !== undefined) node.textContent = text;
        if (name) node.className = name;
        return node;
      };
      this.el = el;
      this.root = el('main', undefined, 'mini-watch');
      this.summary = el('button', undefined, 'mini-summary'); this.summary.type = 'button';
      this.summary.setAttribute('aria-label', 'Return to Watch in the existing Cost Guard tab');
      this.summary.title = 'Return to Watch. If the browser cannot restore a minimized window, use its native return-to-tab control.';
      this.summary.addEventListener('click', returnToWatch);
      this.summary.append(el('span', 'Cost Guard · Watch', 'mini-brand'));
      this.health = el('p', 'Acquiring live prompts…', 'mini-health'); this.health.setAttribute('role', 'status');
      this.prompts = el('div', undefined, 'mini-prompts'); this.prompts.tabIndex = 0;
      this.prompts.setAttribute('role', 'region'); this.prompts.setAttribute('aria-label', 'Active and recently ended prompts');
      const table = el('table', undefined, 'mini-prompt-table'), head = el('thead'), header = el('tr');
      table.setAttribute('aria-label', 'Per-prompt CCost, Duration and estimated next incoming context (CTX), not session totals');
      for (const name of ['Session', '#', 'CCost', 'Duration', 'CTX']) {
        const cell = el('th', name); cell.scope = 'col';
        cell.title = {Session: 'Full session title is available on focus', '#': 'Canonical session-local prompt number',
          CCost: 'This prompt only; reference-price cost, not billed spending', Duration: 'This prompt’s elapsed execution duration',
          CTX: 'Estimated next incoming context for this prompt; N/A means unavailable'}[name];
        header.append(cell);
      }
      head.append(header); this.body = el('tbody'); table.append(head, this.body); this.prompts.append(table);
      this.promptRows = new Map(); this.emptyPrompts = el('tr');
      const empty = el('td', 'No running or recently ended prompts'); empty.colSpan = 5; this.emptyPrompts.append(empty);
      this.accounts = el('ul', undefined, 'mini-accounts'); this.lines = new Map();
      this.accounts.tabIndex = 0; this.accounts.setAttribute('aria-label', 'Primary subscription usage and same-period observed CCost');
      this.root.append(this.summary, this.health, this.prompts, this.accounts); doc.body.replaceChildren(this.root);
    }
    update(publication, health, overdue) {
      const view = publication?.view, running = view?.running;
      const fresh = health.kind === 'connected' && publication?.state === 'running' && !overdue;
      const text = ReportView.text;
      const state = {authorization_required: 'Authorization expired', identity_changed: 'Host changed',
        stopped: 'Host stopped', offline: 'Offline', reconnecting: 'Reconnecting', source_unavailable: 'Source unavailable'}[health.kind];
      text(this.health, !fresh ? `${state || (overdue ? 'Waiting for live update' : 'Acquiring live prompts')} · ${view ? 'not live' : 'no observation yet'}` :
        running?.state === 'unavailable' ? 'Prompt source unavailable · retained values' :
        running?.state === 'loading' || !running ? 'Acquiring prompts · partial observation' :
        !running.complete || running.unresolved_cost ? 'Partial prompt / pricing data' : '');
      this.health.hidden = !this.health.textContent;
      this.root.dataset.live = fresh && running?.state === 'observed' ? 'true' : 'false';
      this.health.title = 'Figures use the last canonical publication; elapsed time is never extrapolated while disconnected.';
      this.drawPrompts(view);
      this.drawAccounts(view);
    }
    drawPrompts(view) {
      const wanted = [], seen = new Set(), text = ReportView.text, display = ReportView.display;
      const values = (view?.active_cards || []).flatMap(card => card.rows.filter(item =>
        card.focal_id && item.prompt.event_id === card.focal_id && !item.prompt.is_compaction).map(item => ({card, item})));
      values.sort((a, b) => a.item.prompt.at_ms - b.item.prompt.at_ms ||
        a.card.session_id.localeCompare(b.card.session_id) || a.item.prompt.event_id.localeCompare(b.item.prompt.event_id));
      for (const {card, item} of values) {
        const prompt = item.prompt, key = JSON.stringify([card.session_id, prompt.event_id]);
        if (seen.has(key)) continue;
        seen.add(key);
        let row = this.promptRows.get(key);
        if (!row) {
          row = this.el('tr'); row.dataset.id = key;
          for (let index = 0; index < 5; index++) row.append(this.el('td'));
          row.children[0].tabIndex = 0; this.promptRows.set(key, row);
        }
        const outcome = prompt.in_progress ? 'Running' : prompt.aborted ? 'Aborted' : prompt.has_error ? 'Error' : prompt.completed_successfully ? 'Completed' : 'Ended';
        const reason = !prompt.in_progress && prompt.abort_reason ? ' · ' + prompt.abort_reason.replaceAll('_', ' ') : '';
        const state = ['partial', 'retrying', 'unavailable'].includes(card.state) ? ' · ' + card.state + ' source evidence' : '';
        row.title = `${outcome}${reason}${state}; per-prompt CCost, Duration and CTX.${prompt.cost_estimated ? ' Estimated cost.' : ''}${prompt.unresolved_cost ? ' Partial pricing.' : ''}`;
        row.setAttribute('aria-label', `${card.title} · Prompt ${prompt.prompt_number} · ${row.title}`);
        row.className = prompt.in_progress ? 'mini-running' : prompt.aborted || prompt.has_error ? 'mini-error' : prompt.completed_successfully ? 'mini-success' : '';
        text(row.children[0], card.title || card.session_id); row.children[0].title = row.children[0].textContent;
        const context = display(item.live_context, 'watch_next_context_tokens');
        const cells = ['#' + prompt.prompt_number, display(prompt, 'ccost'), display(item, 'watch_duration_ms'), context === 'N/A' ? context : '~' + context];
        cells.forEach((value, index) => text(row.children[index + 1], value)); wanted.push(row);
      }
      text(this.emptyPrompts.children[0], view?.cards_state === 'observed' ? 'No running or recently ended prompts' : 'Prompt observations unavailable or pending');
      reconcile(this.body, wanted.length ? wanted : [this.emptyPrompts]);
      for (const key of this.promptRows.keys()) if (!seen.has(key)) this.promptRows.delete(key);
    }
    drawAccounts(view) {
      const text = ReportView.text, display = ReportView.display;
      const accounts = view?.accounts?.accounts;
      const wanted = [];
      for (const item of accounts || []) {
        const obs = item.observation, primary = item.primary;
        const key = JSON.stringify([obs.provider_id, obs.id]);
        let line = this.lines.get(key);
        if (!line) {
          line = this.el('li'); line.tabIndex = 0;
          line.append(this.el('div'), this.el('progress')); this.lines.set(key, line);
        }
        const used = primary.quota.unlimited ? 'Unlimited' : primary.used_percent === '—' ? 'Usage unavailable' : primary.used_percent + ' used';
        const cost = primary.cost, amount = cost == null || (cost.observed_requests && !cost.priced_requests) ? '—' : display(cost, 'known_ccost');
        const stale = !['available', 'partial'].includes(obs.availability) || view.quota_stale;
        const warning = stale ? ' · quota stale/unavailable' : primary.restricted ? ' · provider restriction' : obs.availability === 'partial' ? ' · partial quota' : '';
        text(line.children[0], `${obs.label} · ${used} (${amount})${warning}`);
        line.title = `${primary.quota.label} Used; same native-period observed CCost, independent of native usage and not billed spending. ${primary.note || 'Period cost unavailable until verified history and boundaries are available.'}${primary.estimated ? ' Estimated account attribution.' : ''}${cost && !cost.complete ? ' ? indicates partial pricing.' : ''}`;
        line.className = stale || primary.restricted || obs.availability === 'partial' ? 'mini-warning' : '';
        const bar = line.children[1]; bar.hidden = primary.quota.unlimited || primary.used_fraction == null;
        bar.max = 1; bar.value = primary.used_fraction ?? 0;
        bar.className = primary.exhausted && !bar.hidden ? 'mini-exhausted' : '';
        bar.setAttribute('aria-label', obs.label + ' · ' + primary.quota.label + ' Used'); bar.setAttribute('aria-valuetext', used + warning);
        wanted.push(line);
      }
      if (!wanted.length) {
        if (!this.empty) this.empty = this.doc.createElement('li');
        text(this.empty, accounts ? 'No configured subscriptions' : 'Acquiring subscriptions…'); wanted.push(this.empty);
      }
      const keep = new Set(wanted); reconcile(this.accounts, wanted);
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
        win = await this.owner.documentPictureInPicture.requestWindow({width: 560, height: 450});
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
        });
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
