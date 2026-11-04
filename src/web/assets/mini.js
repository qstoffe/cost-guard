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
  // Presentation retention only. A retry/state change is not a new observation.
  // Independent clocks prevent healthy prompt ticks from hiding a stuck Daily lane.
  class Observations {
    constructor() {
      this.started = Date.now(); this.clocks = new Map(); this.view = null;
    }
    observed(key, token, now) {
      if (token != null && this.clocks.get(key)?.token !== token) this.clocks.set(key, {token, at: now});
    }
    update(publication, now) {
      const view = publication?.view;
      if (!view || publication.state !== 'running') return;
      const previous = this.view;
      const prompts = view.cards_state === 'observed';
      const oldCards = new Map((previous?.active_cards || []).map(card =>
        [JSON.stringify([card.session_id, card.focal_id]), card]));
      const cards = (view.active_cards || []).map(card => {
        const key = JSON.stringify([card.session_id, card.focal_id]);
        const old = oldCards.get(key);
        const value = card.state === 'observed' ? {...card, mini_observed_at_ms: view.now_ms} :
          old ? {...old, state: card.state, session_summary: card.session_summary} : card;
        oldCards.set(key, value); return value;
      });
      const oldHistory = new Map((previous?.history_cards || []).map(card => [card.session_id, card]));
      const history = (view.history_cards || []).map(card => {
        const old = oldHistory.get(card.session_id);
        return card.state === 'observed' ? {...card, mini_observed_at_ms: view.now_ms} :
          old ? {...old, state: card.state, session_summary: card.session_summary} : card;
      });
      if (prompts) {
        this.observed('prompts', JSON.stringify([view.now_ms, publication.source_observed_at_ms]), now);
        this.promptObservedAt = view.now_ms;
      }
      const daily = view.daily_usage;
      const dailyUsable = daily && !(daily.day_end_ms <= now) && ['observed', 'refreshing'].includes(view.daily_state);
      if (dailyUsable) this.observed('daily', daily.observed_at_ms, now);
      const oldAccounts = new Map((previous?.accounts?.accounts || []).map(item =>
        [JSON.stringify([item.observation.provider_id, item.observation.id]), item]));
      const accounts = view.accounts?.accounts.map(item => {
        const obs = item.observation, key = JSON.stringify([obs.provider_id, obs.id]);
        if (!this.clocks.has('quota:' + key)) this.clocks.set('quota:' + key, {token: null, at: this.started});
        const usable = !view.quota_stale && ['available', 'partial'].includes(obs.availability);
        if (usable) this.observed('quota:' + key, obs.observed_at_ms, now);
        const old = oldAccounts.get(key);
        return usable || item.primary.restricted || item.primary.exhausted || !old ? item :
          {...old, observation: {...old.observation, availability: obs.availability}};
      });
      const activeKeys = new Set((view.accounts?.accounts || previous?.accounts?.accounts || []).map(item =>
        'quota:' + JSON.stringify([item.observation.provider_id, item.observation.id])));
      for (const key of this.clocks.keys()) if (key.startsWith('quota:') && !activeKeys.has(key)) this.clocks.delete(key);
      this.view = {...view,
        active_cards: prompts ? cards : [...oldCards.values()],
        history_cards: view.history_state === 'observed' ? history : history.length ? history : previous?.history_cards || [],
        // A canonical null clears the previous day. Never carry it across rollover.
        daily_usage: !daily || dailyUsable || !previous?.daily_usage ||
          daily.day_start_ms !== previous.daily_usage.day_start_ms ? daily : previous.daily_usage,
        accounts: accounts ? {...view.accounts, accounts} : previous?.accounts};
    }
    snapshot(now) {
      const view = this.view;
      return view?.daily_usage?.day_end_ms <= now ? {...view, daily_usage: null} : view;
    }
    delayed(now) {
      const keys = ['prompts', 'daily', ...[...this.clocks.keys()].filter(key => key.startsWith('quota:'))];
      return keys.some(key => now - (this.clocks.get(key)?.at ?? this.started) >= 600000);
    }
  }
  function observedAt(value) {
    return Number.isFinite(value) ? new Date(value).toISOString() : 'unknown';
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
      this.daily = el('p', 'CCost Today · Loading…', 'mini-daily'); this.daily.tabIndex = 0;
      this.earlierToggle = el('button', 'Earlier Sessions', 'mini-earlier-toggle'); this.earlierToggle.type = 'button';
      this.earlierToggle.id = 'mini-earlier-toggle';
      this.earlierToggle.setAttribute('aria-expanded', 'false');
      this.earlierToggle.setAttribute('aria-controls', 'mini-earlier-sessions');
      this.earlierToggle.addEventListener('click', () => {
        this.earlier.hidden = !this.earlier.hidden;
        this.earlierToggle.setAttribute('aria-expanded', String(!this.earlier.hidden));
      });
      const top = el('header', undefined, 'mini-header'); top.append(this.summary, this.earlierToggle, this.daily);
      this.health = el('p', '', 'mini-health'); this.health.setAttribute('role', 'status');
      this.prompts = el('div', undefined, 'mini-prompts'); this.prompts.tabIndex = 0;
      this.prompts.setAttribute('role', 'region'); this.prompts.setAttribute('aria-label', 'Earlier sessions and active or recently ended prompts');
      this.earlier = el('section'); this.earlier.id = 'mini-earlier-sessions'; this.earlier.hidden = true;
      this.earlier.setAttribute('role', 'region'); this.earlier.setAttribute('aria-labelledby', this.earlierToggle.id);
      this.historyBody = this.table(this.earlier, true); this.historyRows = new Map();
      this.body = this.table(this.prompts, false); this.prompts.insertBefore(this.earlier, this.prompts.children[0]);
      this.promptRows = new Map(); this.emptyPrompts = this.emptyRow(5); this.emptyHistory = this.emptyRow(2);
      this.accounts = el('ul', undefined, 'mini-accounts'); this.lines = new Map();
      this.accounts.tabIndex = 0; this.accounts.setAttribute('aria-label', 'Primary subscription usage and same-period observed CCost');
      this.root.append(top, this.health, this.prompts, this.accounts); doc.body.replaceChildren(this.root);
    }
    table(parent, historical) {
      const table = this.el('table', undefined, 'mini-prompt-table'), head = this.el('thead'), header = this.el('tr');
      table.setAttribute('aria-label', historical ? 'Earlier sessions: whole-session CCost and latest valid session context (CTX)' :
        'Active prompts: whole-session CCost in Session; per-prompt CCost, Duration and estimated next incoming context (CTX)');
      for (const name of historical ? ['Session', 'CTX'] : ['Session', '#', 'CCost', 'Duration', 'CTX']) {
        const cell = this.el('th', name); cell.scope = 'col'; cell.tabIndex = 0;
        if (name === 'Session') {
          const value = this.el('span', undefined, 'mini-session-value mini-session-heading');
          value.append(this.el('span', 'Session'), this.el('span', ' | Total CCost', 'mini-session-total'));
          cell.replaceChildren(value);
        }
        cell.title = {Session: 'Full session title and entire root/session-tree CCost, including pre-Watch history and child work; not prompt cost or billing',
          '#': 'Canonical session-local prompt number', CCost: 'This prompt only; reference-price cost, not billed spending',
          Duration: 'This prompt’s elapsed execution duration', CTX: historical ?
            'Estimated latest valid session/current-next context, not historical prompt context or a sum; N/A means unavailable' :
            'Estimated next incoming context for this prompt; N/A means unavailable'}[name];
        cell.setAttribute('aria-description', cell.title); header.append(cell);
      }
      head.append(header); const body = this.el('tbody'); table.append(head, body); parent.append(table); return body;
    }
    emptyRow(columns) {
      const row = this.el('tr'), cell = this.el('td'); cell.colSpan = columns;
      cell.append(this.el('span', '', 'mini-empty')); row.append(cell); return row;
    }
    sessionRow(columns) {
      const row = this.el('tr');
      for (let index = 0; index < columns; index++) row.append(this.el('td'));
      const cell = row.children[0], value = this.el('span', undefined, 'mini-session-value');
      cell.tabIndex = 0; value.append(this.el('span', '', 'mini-session'), this.el('span', '', 'mini-session-total'));
      const help = this.el('div', '', 'mini-session-help'); help.setAttribute('popover', 'auto');
      help.setAttribute('role', 'tooltip');
      const show = () => { if (help.showPopover && help.isConnected && !help.matches(':popover-open')) help.showPopover(); };
      const hide = () => help.hidePopover?.();
      cell.addEventListener('focus', show); cell.addEventListener('blur', hide);
      cell.addEventListener('pointerenter', show);
      cell.addEventListener('pointerleave', () => { if (this.doc.activeElement !== cell) hide(); });
      cell.addEventListener('click', show);
      cell.append(value, help); return row;
    }
    drawSession(cell, card) {
      const summary = card.session_summary, cost = summary?.cost;
      const amount = cost ? cost.observed_requests && !cost.priced_requests ? 'N/A' : ReportView.display(cost, 'known_ccost') :
        summary?.state === 'unavailable' ? 'N/A' : 'Loading…';
      const title = card.title || card.session_id;
      ReportView.text(cell.children[0].children[0], title);
      ReportView.text(cell.children[0].children[1], ' | ' + amount);
      cell.title = `${title}. Whole-session CCost: ${amount}; all root/session-tree usage, including history, child and provisional work; not prompt cost, Today or billing.` +
        ` Aggregate: ${summary?.state || 'loading'}; source: ${card.state || 'loading'}.` +
        (cost && !cost.complete ? ' Partial/unknown pricing or source coverage.' : '') +
        (summary?.cache_available === false ? ' Persistent cache unavailable.' : '');
      ReportView.text(cell.children[1], cell.title);
      cell.setAttribute('aria-label', cell.title); return cell.title;
    }
    update(publication, health, overdue, observations, now) {
      const view = observations.snapshot(now);
      const fresh = health.kind === 'connected' && publication?.state === 'running' && !overdue;
      const text = ReportView.text;
      const state = {authorization_required: 'Authorization expired · return to Cost Guard',
        identity_changed: 'Host changed · reopen Cost Guard', stopped: 'Host stopped · restart Cost Guard'}[health.kind];
      text(this.health, state || (observations.delayed(now) ? 'Updates unavailable' +
        (view ? ' · showing last values' : '') : ''));
      this.health.hidden = !this.health.textContent;
      this.root.dataset.live = fresh && publication?.view?.cards_state === 'observed' ? 'true' : 'false';
      const disclosure = `Last coherent prompt publication: ${observedAt(observations.promptObservedAt)}. ` +
        `Connection: ${health.kind}; source: ${publication?.state || 'loading'}; prompt acquisition: ${publication?.view?.cards_state || 'loading'}. ` +
        'Retained values are not new live observations; elapsed time is never extrapolated.';
      this.health.title = disclosure; this.prompts.title = disclosure;
      this.prompts.setAttribute('aria-description', disclosure);
      this.drawDaily(view, fresh);
      this.drawPrompts(view);
      this.drawHistory(view);
      this.drawAccounts(view);
    }
    drawDaily(view, fresh) {
      const value = view?.daily_usage, state = view?.daily_state;
      let label = 'CCost Today · Loading…';
      const notes = [];
      if (value) {
        const cost = value.total.observed_requests && !value.total.priced_requests ? 'N/A' : ReportView.display(value.total, 'known_ccost');
        label = `CCost Today ${cost} · ${value.prompt_count} prompts`;
        if (!value.total.complete || !value.mix.cost_complete || value.mix.request_count && value.mix.totals.some(amount => amount == null))
          notes.push('Partial pricing / telemetry');
        if (state === 'unavailable') notes.push('Source unavailable · retained daily observation');
        else if (state === 'retrying') notes.push('Retrying daily refresh · retained observation, not current');
        else if (state !== 'observed') notes.push('Partial daily observation');
        if (!fresh) notes.push('Not live · retained observation');
        notes.push('Last daily observation: ' + observedAt(value.observed_at_ms));
      }
      ReportView.text(this.daily, label);
      this.daily.title = 'Global configured local-day CCost and distinct initiating prompts, including pre-Watch activity; not visible-row totals. ' + notes.join('. ');
      this.daily.setAttribute('aria-label', this.daily.textContent + '. ' + this.daily.title);
      this.daily.className = 'mini-daily';
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
          row = this.sessionRow(5); row.dataset.id = key;
          this.promptRows.set(key, row);
        }
        const outcome = prompt.in_progress ? 'Running' : prompt.aborted ? 'Aborted' : prompt.has_error ? 'Error' : prompt.completed_successfully ? 'Completed' : 'Ended';
        const reason = !prompt.in_progress && prompt.abort_reason ? ' · ' + prompt.abort_reason.replaceAll('_', ' ') : '';
        const state = ['partial', 'retrying', 'unavailable'].includes(card.state) ? ' · ' + card.state + ' source evidence' : '';
        row.title = `${outcome}${reason}${state}; per-prompt CCost, Duration and CTX.${prompt.cost_estimated ? ' Estimated cost.' : ''}${prompt.unresolved_cost ? ' Partial pricing.' : ''}`;
        row.title += ` Last prompt observation: ${observedAt(card.mini_observed_at_ms)}.`;
        const session = this.drawSession(row.children[0], card);
        row.setAttribute('aria-label', `${session} Prompt ${prompt.prompt_number} · ${row.title}`);
        row.className = prompt.in_progress ? 'mini-running' : prompt.aborted || prompt.has_error ? 'mini-error' : prompt.completed_successfully ? 'mini-success' : '';
        const context = display(item.live_context, 'watch_next_context_tokens');
        const cells = ['#' + prompt.prompt_number, display(prompt, 'ccost'), display(item, 'watch_duration_ms'), context];
        cells.forEach((value, index) => text(row.children[index + 1], value)); wanted.push(row);
      }
      text(this.emptyPrompts.children[0].children[0], view?.cards_state === 'observed' ? 'No running or recently ended prompts' : 'Loading…');
      reconcile(this.body, wanted.length ? wanted : [this.emptyPrompts]);
      for (const key of this.promptRows.keys()) if (!seen.has(key)) this.promptRows.delete(key);
    }
    drawHistory(view) {
      this.earlier.title = `History acquisition: ${view?.history_state || 'loading'}. Retained values are not new live observations.`;
      this.earlier.setAttribute('aria-description', this.earlier.title);
      const seen = new Set((view?.active_cards || []).map(card => card.session_id));
      // Shared history is already eligible, session-distinct and oldest-to-newest.
      // No clock/ranking/valuation or new acquisition belongs in this view.
      const cards = (view?.history_cards || []).filter(card => {
        if (seen.has(card.session_id)) return false;
        seen.add(card.session_id); return true;
      }).slice(-3);
      const wanted = cards.map(card => {
        let row = this.historyRows.get(card.session_id);
        if (!row) { row = this.sessionRow(2); row.dataset.id = card.session_id; this.historyRows.set(card.session_id, row); }
        const session = this.drawSession(row.children[0], card);
        const context = ReportView.display(card.session_summary?.context, 'watch_next_context_tokens');
        ReportView.text(row.children[1], context);
        row.title = `Earlier session. ${session} Latest valid session CTX: ${context}. Last prompt observation: ${observedAt(card.mini_observed_at_ms)}. ${this.earlier.title}`;
        row.setAttribute('aria-label', row.title); return row;
      });
      ReportView.text(this.emptyHistory.children[0].children[0], view?.history_state === 'observed' ? 'No earlier sessions' :
        view?.history_state === 'unavailable' ? 'Earlier sessions unavailable' : 'Loading earlier sessions…');
      reconcile(this.historyBody, wanted.length ? wanted : [this.emptyHistory]);
      const keep = new Set(cards.map(card => card.session_id));
      for (const key of this.historyRows.keys()) if (!keep.has(key)) this.historyRows.delete(key);
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
        const quota = ReportView.quotaView(primary.quota, primary);
        const used = primary.quota.unlimited ? 'Unlimited' : quota.percent === '—' ? 'Usage unavailable' : quota.percent + ' ' + quota.mode;
        const cost = primary.cost, amount = cost == null || (cost.observed_requests && !cost.priced_requests) ? '—' : display(cost, 'known_ccost');
        const stale = !['available', 'partial'].includes(obs.availability) || view.quota_stale;
        const warning = primary.restricted ? ' · provider restriction' : '';
        const period = quota.mode === 'remaining' ? amount === '—' ? '' : ` (CCost used: ${amount})` : ` (${amount})`;
        text(line.children[0], `${obs.label} · ${used}${period}${warning}`);
        const basis = primary.note || (amount === '—' ? 'Period cost unavailable until verified history and boundaries are available.' :
          'Observed reference spending within this native quota period.');
        line.title = `${primary.quota.label} ${quota.mode}; ${quota.native}. ${quota.note || ''} Same native-period observed CCost, independent of native usage, not remaining CCost or billed spending. ${basis}${primary.estimated ? ' Estimated account attribution.' : ''}${cost && !cost.complete ? ' ? indicates partial pricing.' : ''}`;
        if (quota.mode === 'remaining' && quota.money !== 'N/A') line.title += ` Native money remaining ${quota.money} / ${display(primary.quota, 'limit_money')}.`;
        line.title += ` Last quota observation: ${observedAt(obs.observed_at_ms)}.${stale ? ' Retained quota; not current.' : ''}${obs.availability === 'partial' ? ' Partial quota data.' : ''}`;
        line.setAttribute('aria-description', line.title);
        line.className = quota.exhausted && quota.mode === 'remaining' ? 'mini-exhausted' : primary.restricted ? 'mini-warning' : '';
        const bar = line.children[1]; bar.hidden = primary.quota.unlimited || primary.used_fraction == null;
        bar.max = 1; bar.value = quota.fraction ?? 0;
        bar.className = quota.exhausted && !bar.hidden ? 'mini-exhausted' : '';
        bar.setAttribute('aria-label', obs.label + ' · ' + primary.quota.label + ' ' + quota.mode); bar.setAttribute('aria-valuetext', used + warning + (quota.exhausted ? ' · exhausted' : ''));
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
      this.observations = new Observations();
      this.placement = null; this.opened = false; this.instance = null;
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
      this.button.disabled = Boolean(this.reason) || !this.placement;
      if (this.reason) this.feedback.textContent = this.reason;
      else if (!this.placement) this.feedback.textContent = 'Mini Watch placement unavailable. Open Settings to retry.';
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
      if (this.reason || this.ended || !this.placement) return;
      if (this.window) { this.close(); return; }
      if (this.pending) {
        this.pending.cancelled = true; this.feedback.textContent = 'Opening cancelled.'; return;
      }
      const request = {cancelled: false}; this.pending = request;
      this.feedback.textContent = 'Opening Mini Watch…';
      let win = null;
      try {
        // Called synchronously inside the explicit click's user activation.
        // Chromium requests screen DIPs, independent of page zoom. Measured on
        // Windows at 150%: 450 DIPs produced a 729-physical-pixel visible frame.
        // 250 leaves room for native chrome below the 470px target on that setup.
        // Do not resize after opening: Chrome requires a NEW PiP user activation.
        const instance = this.instance;
        win = await this.owner.documentPictureInPicture.requestWindow({width: 560, height: 250,
          preferInitialWindowPlacement: !this.opened || this.placement === 'standard'});
        if (instance === this.instance) this.opened = true;
        if (request.cancelled || this.ended || win.closed || this.owner.documentPictureInPicture.window !== win) {
          win.close(); return;
        }
        this.window = win;
        win.addEventListener('pagehide', () => { this.release(win); this.sync(); }, {once: true});
        const doc = win.document; doc.title = 'Mini Watch · Cost Guard'; doc.documentElement.lang = 'en';
        const icon = doc.createElement('link'); icon.rel = 'icon'; icon.type = 'image/x-icon';
        icon.href = new URL('/favicon-cg1.ico', this.owner.location.href).href; doc.head.append(icon);
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
      const epoch = JSON.stringify([value?.view?.now_ms, value?.source_observed_at_ms]);
      if (epoch !== this.epoch) { this.epoch = epoch; this.receivedAt = Date.now(); }
      this.observations.update(value, Date.now());
      this.publication = value; this.sync(); this.render();
    }
    health(value) { this.healthState = value; this.sync(); this.render(); }
    settings(values, instance) {
      if (instance && instance !== this.instance) { this.instance = instance; this.opened = false; }
      if (values) {
        this.placement = values.miniWatchPlacement;
        this.feedback.textContent = '';
      }
      this.sync(); this.render();
    }
    render() {
      if (!this.view) return;
      this.view.doc.documentElement.dataset.theme = this.owner.document.documentElement.dataset.theme;
      const now = Date.now();
      this.view.update(this.publication, this.healthState, now - this.receivedAt > 15000, this.observations, now);
    }
  }
  return {Controller};
})();
