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
      const old = this.clocks.get(key)?.token;
      const fresh = typeof token === 'number' && typeof old === 'number' ? token > old : token !== old;
      if (token != null && fresh) this.clocks.set(key, {token, at: now});
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
        if (!this.clocks.has('prompt:' + key)) this.clocks.set('prompt:' + key, {token: null, at: now});
        if (card.state === 'observed') this.observed('prompt:' + key, card.observed_at_ms, now);
        const old = oldCards.get(key);
        const value = card.state === 'observed' ? card :
          old ? {...old, state: card.state, session_summary: card.session_summary} : card;
        oldCards.set(key, value); return value;
      });
      if (prompts) {
        const stamps = cards.map(card => [card.session_id, card.focal_id, card.observed_at_ms]);
        if (!cards.length || cards.every(card => card.observed_at_ms != null))
          this.observed('prompts', JSON.stringify([stamps, publication.source_observed_at_ms]), now);
      }
      const promptKeys = new Set(cards.map(card => 'prompt:' + JSON.stringify([card.session_id, card.focal_id])));
      if (prompts) for (const key of this.clocks.keys())
        if (key.startsWith('prompt:') && !promptKeys.has(key)) this.clocks.delete(key);
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
          {...old, observation: {...obs, observed_at_ms: old.observation.observed_at_ms}};
      });
      const activeKeys = new Set((view.accounts?.accounts || previous?.accounts?.accounts || []).map(item =>
        'quota:' + JSON.stringify([item.observation.provider_id, item.observation.id])));
      for (const key of this.clocks.keys()) if (key.startsWith('quota:') && !activeKeys.has(key)) this.clocks.delete(key);
      this.view = {...view,
        active_cards: prompts ? cards : [...oldCards.values()],
        // The producer owns atomic history retention, invalidation and source scope.
        history_cards: view.history_cards || [],
        // Missing refresh data retains this day's usable summary only. The
        // configured boundary below still clears yesterday, even disconnected.
        daily_usage: daily ? dailyUsable || !previous?.daily_usage ||
          daily.day_start_ms !== previous.daily_usage.day_start_ms ? daily : previous.daily_usage :
          previous?.daily_usage?.day_end_ms > now ? previous.daily_usage : null,
        accounts: accounts ? {...view.accounts, accounts} : previous?.accounts};
    }
    snapshot(now) {
      const view = this.view;
      return view?.daily_usage?.day_end_ms <= now ? {...view, daily_usage: null} : view;
    }
    delayed(now) {
      const keys = ['prompts', 'daily', ...[...this.clocks.keys()].filter(key => key.startsWith('quota:') || key.startsWith('prompt:'))];
      return keys.some(key => now - (this.clocks.get(key)?.at ?? this.started) >= 600000);
    }
  }
  // Natural layout, including all accounts/warnings and a height-only two-row reserve.
  // Clones are invisible, inert measurement artifacts, never published prompt data.
  function contentHeight(view, width) {
    const {doc, root} = view, win = doc.defaultView;
    const copy = root.cloneNode(true); copy.classList.add('mini-measuring');
    copy.inert = true; copy.setAttribute('aria-hidden', 'true'); copy.style.width = width + 'px';
    root.parentNode.append(copy);
    try {
      const body = copy.querySelector('.mini-prompts > table > tbody');
      const rows = [...body.children].filter(row => !row.querySelector('.mini-empty'));
      const emptyHeight = rows.length ? 0 : body.getBoundingClientRect().height;
      const sample = view.sessionRow();
      ['Session', 'N/A (N/A)', '0s', 'N/A'].forEach((text, index) => { sample.children[index].textContent = text; });
      body.append(sample);
      const rowHeight = Math.max(sample.getBoundingClientRect().height,
        ...rows.map(row => row.getBoundingClientRect().height));
      sample.remove();
      return Math.ceil(copy.getBoundingClientRect().height + Math.max(0, (2 - rows.length) * rowHeight - emptyHeight));
    } finally { copy.remove(); }
  }
  function heightCap(win) {
    return Math.min(1000, win.screen?.availHeight > 0 ? win.screen.availHeight : 1000);
  }
  function headerWidth(view, reserve = false) {
    // Only inert header clones: never change real totals/disclosure or size to tables.
    const copy = view.root.firstElementChild.cloneNode(true);
    copy.classList.add('mini-header-measuring'); copy.inert = true;
    copy.setAttribute('aria-hidden', 'true'); view.root.append(copy);
    try {
      const toggle = copy.querySelector('.mini-earlier-toggle');
      const daily = copy.querySelector('.mini-daily > span');
      let width = 0;
      for (const text of reserve ? [daily.textContent, 'CCost Today 90 000 · 999 prompts'] : [daily.textContent]) {
        daily.textContent = text;
        for (const expanded of ['false', 'true']) {
          toggle.setAttribute('aria-expanded', expanded);
          toggle.setAttribute('aria-pressed', expanded);
          width = Math.max(width, copy.getBoundingClientRect().width);
        }
      }
      return width;
    }
    finally { copy.remove(); }
  }
  function scrollbarWidth(view) {
    const copy = view.doc.createElement('div'); copy.className = 'mini-scrollbar-measuring';
    copy.inert = true; copy.setAttribute('aria-hidden', 'true'); view.root.append(copy);
    try { return copy.offsetWidth - copy.clientWidth; }
    finally { copy.remove(); }
  }
  function geometry(win, frameWidth = 0) {
    // CSS document pixels and screen DIPs differ with browser zoom. The opener's
    // outer/inner ratio is an estimate before the first PiP exists, not OS proof.
    const scale = win.outerWidth > frameWidth && win.innerWidth > 0 ? (win.outerWidth - frameWidth) / win.innerWidth : 1;
    return {scale, frame: Math.max(0, win.outerHeight - win.innerHeight * scale)};
  }
  function targetHeight(view) {
    const win = view.doc.defaultView, {scale, frame} = geometry(win);
    const style = win.getComputedStyle(view.doc.body);
    const padding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
    return Math.min(heightCap(win), Math.ceil((contentHeight(view, view.root.getBoundingClientRect().width) + padding + 4) * scale + frame));
  }
  // One bounded native adjustment per user disclosure, never per publication.
  class DisclosureSize {
    constructor(view, mode) {
      this.view = view; this.win = view.doc.defaultView; this.mode = mode;
      this.restore = null; this.pending = null; this.widthCorrection = 0;
      this.win.addEventListener('resize', () => {
        if (this.pending) this.confirm(this.pending);
        else if (this.restore && !this.same(this.bounds(), this.restore.after)) {
          this.restore = null; this.widthCorrection = 0;
        }
      });
    }
    bounds() { return {width: this.win.outerWidth, height: this.win.outerHeight}; }
    same(a, b) { return Math.abs(a.width - b.width) <= 1 && Math.abs(a.height - b.height) <= 1; }
    resize(width, height) {
      // Start vertical-only. Some real page-zoom/native-DPI combinations still
      // round width upward; compensate that observed single DIP on the NEXT
      // eligible click, never by a second call, loop or passive correction.
      if (typeof this.win.resizeBy === 'function') this.win.resizeBy(this.widthCorrection, height - this.win.outerHeight);
      else this.win.resizeTo(width + this.widthCorrection, height);
    }
    confirm(request) {
      const after = this.bounds();
      if (request.after && !this.same(after, request.after)) { this.restore = null; this.widthCorrection = 0; return; }
      if (!request.after) {
        if (Math.abs(after.width - request.before.width) <= 1)
          this.widthCorrection = Math.max(-1, Math.min(1, this.widthCorrection + request.before.width - after.width));
        else this.widthCorrection = 0; // Native clamp, not rounding; no width repair.
        request.after = after;
      }
      if (request.expanded && Math.abs(after.width - request.before.width) <= 1 && after.height > request.before.height) {
        this.restore = {before: request.before, after};
      }
    }
    toggle(earlier) {
      const {win, view} = this;
      const before = this.bounds();
      earlier.hidden = !earlier.hidden;
      view.prompts.dataset.expanded = String(!earlier.hidden);
      view.earlierToggle.setAttribute('aria-expanded', String(!earlier.hidden));
      view.earlierToggle.setAttribute('aria-pressed', String(!earlier.hidden));
      if (this.pending) this.confirm(this.pending);
      this.pending = null;
      const restore = this.restore; this.restore = null;
      // Remembered mode must not restore stale bounds after an intervening resize.
      if (earlier.hidden && this.mode === 'remember-last' &&
          (!restore || !this.same(before, restore.after))) return;
      if (win.navigator?.userActivation && !win.navigator.userActivation.isActive) return;
      if (!(typeof win.resizeBy === 'function' || typeof win.resizeTo === 'function') || !win.innerWidth) return;
      const compact = view.fitHeight();
      const height = earlier.hidden ? this.mode === 'remember-last' ?
        Math.min(heightCap(win), restore.before.height) : compact : Math.max(before.height, compact);
      if (Math.abs(height - before.height) <= 1) return;
      const request = {before, expanded:!earlier.hidden}; this.pending = request;
      try { this.resize(before.width, height); }
      catch (_) { this.pending = null; return; }
      // Observe achieved bounds, not API return success. No later resize/retry.
      win.requestAnimationFrame(() => win.requestAnimationFrame(() => {
        if (this.pending !== request) return;
        this.confirm(request); this.pending = null;
      }));
    }
  }
  class View {
    constructor(doc, returnToWatch, mount = doc.body, mode = 'fit-on-open') {
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
      ContextHelp.attach(this.summary, 'Return to Watch in the existing tab.\nIf the window stays minimized, use the browser’s return-to-tab control.');
      this.summary.addEventListener('click', returnToWatch);
      this.summary.append(el('span', 'Cost Guard · Watch', 'mini-brand'));
      this.daily = el('p', undefined, 'mini-daily'); this.dailyText = el('span');
      this.dailyLead = el('span'); this.dailyAmount = el('span');
      this.dailyTail = el('span'); this.dailyText.append(this.dailyLead, this.dailyAmount, this.dailyTail);
      this.daily.append(this.dailyText);
      this.dailyNote = el('span', '', 'mini-daily-note'); this.daily.append(this.dailyNote);
      this.earlierToggle = el('button', 'Earlier Sessions', 'mini-earlier-toggle'); this.earlierToggle.type = 'button';
      this.earlierToggle.id = 'mini-earlier-toggle';
      this.earlierToggle.setAttribute('aria-expanded', 'false');
      this.earlierToggle.setAttribute('aria-pressed', 'false');
      this.earlierToggle.setAttribute('aria-controls', 'mini-earlier-sessions');
      this.earlierToggle.addEventListener('click', () => {
        this.disclosureSize.toggle(this.earlier);
        this.historyChanged?.();
      });
      const actions = el('div', undefined, 'mini-actions'); actions.append(this.summary, this.earlierToggle);
      const top = el('header', undefined, 'mini-header'); top.append(actions, this.daily);
      this.health = el('p', '', 'mini-health'); this.health.setAttribute('role', 'status');
      this.prompts = el('div', undefined, 'mini-prompts'); this.prompts.tabIndex = 0;
      this.prompts.dataset.expanded = 'false';
      this.prompts.setAttribute('role', 'region'); this.prompts.setAttribute('aria-label', 'Earlier sessions and active or recently ended prompts');
      this.earlier = el('section'); this.earlier.id = 'mini-earlier-sessions'; this.earlier.hidden = true;
      this.earlier.setAttribute('role', 'region'); this.earlier.setAttribute('aria-labelledby', this.earlierToggle.id);
      this.historyBody = this.table(this.earlier, true); this.historyRows = new Map();
      this.body = this.table(this.prompts, false); this.prompts.insertBefore(this.earlier, this.prompts.children[0]);
      this.promptRows = new Map(); this.emptyPrompts = this.emptyRow(4); this.emptyHistory = this.emptyRow(4);
      this.accounts = el('ul', undefined, 'mini-accounts'); this.lines = new Map();
      this.accounts.tabIndex = 0; this.accounts.setAttribute('aria-label', 'Primary subscription usage and same-period observed CCost');
      this.disclosureSize = mount === doc.body ? new DisclosureSize(this, mode) : null;
      this.root.append(top, this.health, this.prompts, this.accounts); mount.replaceChildren(this.root);
    }
    table(parent, historical) {
      const table = this.el('table', undefined, 'mini-prompt-table'), head = this.el('thead'), header = this.el('tr');
      table.setAttribute('aria-label', historical ? 'Earlier sessions: latest supported finish, latest-prompt CCost (whole-session CCost) and latest valid session context (Ctx)' :
        'Active prompts: prompt CCost (whole-session CCost), Duration and estimated next incoming context (Ctx)');
      for (const name of historical ? ['Finished', 'Session', 'CCost (Total)', 'Ctx'] : ['Session', 'CCost (Total)', 'Duration', 'Ctx']) {
        const cell = this.el('th'); cell.scope = 'col';
        const explanation = {Finished: 'The session’s latest supported finish, in configured local time.\nFocus or hover the time for the full local date and offset.', Session: 'The name of the session.',
          'CCost (Total)': `First: ${historical ? 'the latest prompt’s' : 'this prompt’s'} reference CCost.\nIn parentheses: the entire session’s reference CCost, including linked subagents.\nNot provider billing. N/A means unavailable, not zero; ? means partial pricing.`,
          Duration: 'Time spent on this prompt; freezes when updates are unavailable.', Ctx: historical ?
            'Last valid estimate of the next request’s context in this session.\nNot historical prompt context or a sum. N/A means unavailable.' :
            'Estimated context for this prompt’s next request.\nN/A means unavailable, not zero.'}[name];
        const button = ContextHelp.button(name, explanation, this.doc);
        if (name === 'Session') cell.className = 'mini-session-cell';
        cell.append(button);
        header.append(cell);
      }
      head.append(header); const body = this.el('tbody'); table.append(head, body); parent.append(table); return body;
    }
    fitHeight() { return targetHeight(this); }
    emptyRow(columns) {
      const row = this.el('tr'), cell = this.el('td'); cell.colSpan = columns;
      cell.append(this.el('span', '', 'mini-empty')); row.append(cell); return row;
    }
    sessionRow(historical = false) {
      const row = this.el('tr');
      for (let index = 0; index < 4; index++) row.append(this.el('td'));
      const cell = row.children[historical ? 1 : 0], value = this.el('span', undefined, 'mini-session-value');
      cell.className = 'mini-session-cell';
      const title = this.el('span', '', 'mini-session');
      ContextHelp.value(title, () => row.sessionHelp);
      value.append(title);
      cell.append(value);
      const cost = this.el('span', '', 'mini-cost-value');
      const promptCost = this.el('span'), sessionCost = this.el('span');
      ContextHelp.value(promptCost, () => row.costHelp);
      ContextHelp.value(sessionCost, () => row.totalCostHelp);
      cost.append(promptCost, this.el('span', ' ('), sessionCost, this.el('span', ')'));
      row.children[historical ? 2 : 1].append(cost);
      ContextHelp.value(row.children[3], () => row.contextHelp || 'Context estimate unavailable');
      return row;
    }
    drawSession(cell, card) {
      const title = card.title || card.session_id;
      ReportView.text(cell.children[0].children[0], title);
      return title;
    }
    rowHelp(row, session, item, card) {
      const number = item?.prompt?.prompt_number;
      row.sessionHelp = `${session}\n${number == null ? 'Prompt number unavailable' : 'Prompt #' + number + ' in this session'}`;
      row.costHelp = [ReportView.costHelp(item?.prompt), this.promptDetails(item)].filter(Boolean).join('\n\n');
      row.totalCostHelp = ['Whole-session reference CCost, including linked subagents.',
        ReportView.costHelp(card.session_summary?.cost || (card.session_summary?.state === 'unavailable' ? {} : null), 'known_ccost'),
        this.promptDetails(item)].filter(Boolean).join('\n\n');
      const warning = card.session_summary?.context?.warning;
      row.children[3].dataset.guidance = warning?.guidance_state || 'ready';
      row.contextHelp = ['Estimated context for the next request. Not remaining model capacity.',
        warning?.text?.replace(/^\[|\]$/g, ''),
        warning && ReportView.display(warning, 'warning_cost').replace(/^\(|\)$/g, '')].filter(Boolean).join('\n');
      ContextHelp.refresh(row.children[3]);
    }
    drawCost(cell, card, prompt) {
      const summary = card.session_summary, cost = summary?.cost;
      const total = cost ? cost.observed_requests && !cost.priced_requests ? 'N/A' : ReportView.display(cost, 'known_ccost') :
        summary?.state === 'unavailable' ? 'N/A' : 'Loading…';
      const amount = ReportView.display(prompt, 'ccost');
      ReportView.text(cell.children[0].children[0], amount);
      ReportView.text(cell.children[0].children[2], total);
      cell.children[0].setAttribute('aria-label', `Prompt reference CCost: ${amount}; whole-session reference CCost: ${total}`);
    }
    promptDetails(item) {
      const prompt = item?.prompt, detail = prompt?.cost_detail;
      if (!prompt) return 'Latest prompt details unavailable';
      const main = [...new Set((detail?.parts || []).filter(part => part.role === 'main' && part.provider_id && part.model_id)
        .map(part => part.provider_id + '/' + part.model_id))];
      const model = item.model && item.model !== 'N/A' ? item.model : 'N/A';
      const lines = [prompt.prompt_number == null ? 'Prompt number unavailable' : `Prompt #${prompt.prompt_number}`,
        `Main model: ${model}${main.length === 1 && !model.includes(main[0]) ? ' [' + main[0] + ']' : ''}`,
        `Effort: ${item.effort || 'N/A'}`, `Duration: ${ReportView.display(item, 'watch_duration_ms')}`];
      if (prompt.calls != null) lines.push(`Calls: ${prompt.calls}`);
      if (prompt.linked_agent_count) lines.push(`Linked subagents: ${prompt.linked_agent_count} (included in prompt cost)`);
      if (prompt.has_additional_model || detail?.model_count > 1) lines.push('Multiple models contributed to prompt cost');
      if (prompt.unresolved_cost) lines.push('Partial pricing / attribution');
      if (prompt.cost_estimated) lines.push('Estimated attribution');
      if (detail?.agents_without_usage || prompt.calls && !detail?.calls_complete) lines.push('Detailed request attribution incomplete');
      if (prompt.aborted || prompt.has_error) lines.push((prompt.aborted ? 'Aborted' : 'Failed') +
        (prompt.abort_reason ? ' · ' + prompt.abort_reason.replaceAll('_', ' ') : ''));
      return lines.join('\n');
    }
    update(publication, health, overdue, observations, now) {
      const view = observations.snapshot(now);
      const fresh = health.kind === 'connected' && publication?.state === 'running' && !overdue;
      const text = ReportView.text;
      const state = {authorization_required: 'Authorization expired · return to Cost Guard',
        identity_changed: 'Host changed · reopen Cost Guard', stopped: 'Host stopped · restart Cost Guard'}[health.kind];
      text(this.health, state || (health.kind === 'offline' ? 'Host unavailable · return to Cost Guard' : ''));
      this.health.hidden = !this.health.textContent;
      this.root.dataset.live = fresh && publication?.view?.cards_state === 'observed' ? 'true' : 'false';
      this.drawDaily(view);
      this.drawPrompts(view);
      this.drawHistory(view);
      this.drawAccounts(view);
      ContextHelp.refresh(this.root);
    }
    drawDaily(view) {
      const value = view?.daily_usage, state = view?.daily_state;
      let label = 'CCost Today · Loading…';
      if (!value && state === 'unavailable') label = 'CCost Today · Unavailable';
      this.dailyValue = value;
      const cost = value && ReportView.display(value, 'daily_ccost');
      ReportView.text(this.dailyLead, value ? 'CCost Today ' : label);
      ReportView.text(this.dailyAmount, value ? cost : '');
      ReportView.text(this.dailyTail, value ? ` · ${value.prompt_count} prompts` : '');
      ReportView.text(this.dailyNote, '');
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
          row = this.sessionRow(); row.dataset.id = key;
          this.promptRows.set(key, row);
        }
        const outcome = prompt.execution_unverified ? 'Unverified' : prompt.in_progress ? 'Running' : prompt.aborted ? 'Aborted' : prompt.has_error ? 'Error' : prompt.completed_successfully ? 'Completed' : 'Ended';
        const reason = !prompt.in_progress && prompt.abort_reason ? ' · ' + prompt.abort_reason.replaceAll('_', ' ') : '';
        const session = this.drawSession(row.children[0], card);
        this.rowHelp(row, session, item, card);
        row.setAttribute('aria-label', `${session} · Prompt ${prompt.prompt_number} · ${outcome}${reason}`);
        row.className = prompt.in_progress ? 'mini-running' : prompt.aborted || prompt.has_error ? 'mini-error' : prompt.completed_successfully ? 'mini-success' : '';
        const context = display(item.live_context, 'watch_next_context_tokens');
        this.drawCost(row.children[1], card, prompt);
        text(row.children[2], prompt.execution_unverified ? 'Unverified' : display(item, 'watch_duration_ms'));
        text(row.children[3], context); wanted.push(row);
      }
      text(this.emptyPrompts.children[0].children[0], view?.cards_state === 'observed' ? 'No running or recently ended prompts' : 'Loading…');
      reconcile(this.body, wanted.length ? wanted : [this.emptyPrompts]);
      for (const key of this.promptRows.keys()) if (!seen.has(key)) this.promptRows.delete(key);
    }
    drawHistory(view) {
      const seen = new Set((view?.active_cards || []).map(card => card.session_id));
      // Shared history is already eligible, session-distinct and oldest-to-newest.
      // No clock/ranking/valuation or new acquisition belongs in this view.
      const usable = view?.history_state === 'observed' || view?.history_epoch > 0;
      const cards = (usable ? view?.history_cards || [] : []).filter(card => {
        if (seen.has(card.session_id)) return false;
        seen.add(card.session_id); return true;
      }).slice(-3);
      const wanted = cards.map(card => {
        let row = this.historyRows.get(card.session_id);
        if (!row) {
          row = this.sessionRow(true); row.dataset.id = card.session_id;
          const time = this.el('span', '', 'mini-activity');
          ContextHelp.value(time, () => row.finishHelp || 'Unknown finish time'); row.children[0].append(time);
          this.historyRows.set(card.session_id, row);
        }
        // History exports one canonical representative; never rank or reformat it here.
        const item = card.rows?.[0], prompt = item?.prompt;
        const known = prompt?.completed_at_ms != null && prompt.display?.finished_clock && prompt.display?.finished_date_time;
        row.finishHelp = known ? prompt.display.finished_date_time : 'Unknown finish time';
        ReportView.text(row.children[0].children[0], known ? prompt.display.finished_clock : '—');
        const session = this.drawSession(row.children[1], card);
        this.rowHelp(row, session, item, card);
        const context = ReportView.display(card.session_summary?.context, 'watch_next_context_tokens');
        this.drawCost(row.children[2], card, prompt);
        const cell = row.children[3];
        ReportView.text(cell, context);
        row.setAttribute('aria-label', `Earlier session · ${session}`);
        return row;
      });
      const notice = WatchView.historyNotice(view, cards.length > 0);
      ReportView.text(this.emptyHistory.children[0].children[0], notice);
      this.emptyHistory.setAttribute('role', 'status');
      reconcile(this.historyBody, wanted.length ? [...wanted, ...(notice ? [this.emptyHistory] : [])] : [this.emptyHistory]);
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
          line = this.el('li');
          const label = this.el('div'); label.append(this.el('span'));
          ContextHelp.value(label.children[0], () => line.helpText || '');
          line.append(label, this.el('progress')); this.lines.set(key, line);
        }
        const quota = ReportView.quotaView(primary.quota, primary);
        const used = primary.quota.unlimited ? 'Unlimited' : quota.percent === '—' ? 'Usage unavailable' : quota.percent + ' ' + quota.mode;
        const amount = display(primary.quota, 'ccost_' + quota.mode);
        const stale = !['available', 'partial'].includes(obs.availability) || view.quota_stale;
        const warning = primary.restricted ? ' · provider restriction' : '';
        const period = ` (${amount})`;
        line.helpText = `Capacity: ${display(primary.quota, 'ccost_capacity')}\nNext reset: ${display(primary, 'watch_reset')}`;
        const notes = [obs.has_warning && 'Provider warning',
          ['auth_failure', 'unsupported_auth_method'].includes(obs.error_code) && 'Quota authentication unavailable'];
        const note = notes.filter(Boolean).join(' · ');
        text(line.children[0].children[0], `${obs.label} · ${used}${period}${warning}${note ? ' · ' + note : ''}`);
        ContextHelp.refresh(line);
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
    constructor(owner, button, feedback, returnToWatch, measureFactory = () => new OpeningMeasure(owner)) {
      this.owner = owner; this.button = button; this.feedback = feedback; this.returnToWatch = returnToWatch;
      this.window = null; this.view = null; this.pending = null; this.ended = false;
      this.publication = null; this.healthState = {kind: 'starting'}; this.receivedAt = 0;
      this.observations = new Observations();
      this.placement = null; this.opened = false; this.instance = null;
      this.appearance = owner.matchMedia('(prefers-color-scheme: dark)');
      this.themeChanged = () => this.syncTheme(); this.themeProperties = [];
      this.reason = unavailable(owner);
      this.measure = this.reason ? null : measureFactory();
      this.measure?.loaded?.then(() => this.sync());
      button.addEventListener('click', () => this.toggle());
      owner.addEventListener('pagehide', () => { this.ended = true; this.close(); this.measure?.close(); });
      this.sync();
    }
    sync() {
      const win = this.window;
      if (win && (win.closed || this.owner.documentPictureInPicture.window !== win)) this.release(win);
      this.button.textContent = `Mini Watch: ${this.window ? 'On' : 'Off'}`;
      this.button.setAttribute('aria-pressed', this.window ? 'true' : 'false');
      this.button.disabled = Boolean(this.reason) || !this.placement || !this.measure?.ready;
      if (this.reason) this.feedback.textContent = this.reason;
      else if (!this.placement) this.feedback.textContent = 'Mini Watch settings unavailable. Open Settings to retry.';
      else if (!this.measure?.ready) this.feedback.textContent = 'Preparing Mini Watch layout…';
    }
    release(win) {
      if (this.window !== win) return;
      win.clearInterval(this.timer);
      this.demand?.close(); this.demand = null;
      this.appearance.removeEventListener('change', this.themeChanged);
      this.window = this.view = null;
    }
    setDemandFactory(factory) {
      this.demand?.close(false); this.demand = null;
      this.demandFactory = factory;
      if (this.window && this.view && !this.ended) {
        this.demand = factory(this.window);
        this.demand.update();
      }
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
      if (this.reason || this.ended || !this.placement || !this.measure?.ready) return;
      if (this.window) { this.close(); return; }
      if (this.pending) {
        this.pending.cancelled = true; this.feedback.textContent = 'Opening cancelled.'; return;
      }
      const request = {cancelled: false}; this.pending = request;
      this.feedback.textContent = 'Opening Mini Watch…';
      let win = null;
      try {
        // Synchronous real-layout measurement BEFORE requestWindow consumes activation.
        // Native placement couples size/position. Fit wins over remembered position;
        // Standard wins over remembered size. Never emulate native coordinates.
        const instance = this.instance;
        const size = this.size;
        const dimensions = this.measure.read(this);
        win = await this.owner.documentPictureInPicture.requestWindow({...dimensions,
          preferInitialWindowPlacement: !this.opened || this.placement === 'standard' || size === 'fit-on-open'});
        if (instance === this.instance) this.opened = true;
        if (request.cancelled || this.ended || win.closed || this.owner.documentPictureInPicture.window !== win) {
          win.close(); return;
        }
        this.window = win;
        win.addEventListener('pagehide', () => { this.release(win); this.sync(); }, {once: true});
        const doc = win.document; doc.title = 'Mini Watch · Cost Guard'; doc.documentElement.lang = 'en';
        doc.documentElement.dataset.miniSize = size;
        this.syncTheme();
        this.appearance.addEventListener('change', this.themeChanged);
        const icon = doc.createElement('link'); icon.rel = 'icon'; icon.type = 'image/x-icon';
        icon.href = new URL('/favicon-cg1.ico', this.owner.location.href).href; doc.head.append(icon);
        const styles = [];
        for (const name of ['app.css', 'mini.css']) {
          const link = doc.createElement('link'); link.rel = 'stylesheet';
          link.href = new URL('/' + name, this.owner.location.href).href;
          styles.push(new Promise((resolve, reject) => {
            link.addEventListener('load', resolve, {once:true});
            link.addEventListener('error', reject, {once:true});
          }));
          doc.head.append(link);
        }
        // Avoid an unstyled first layout creating a vertical scrollbar which then
        // steals the measured header width and keeps itself alive through wrapping.
        await Promise.all(styles);
        if (request.cancelled || this.ended || win.closed || this.window !== win) { this.release(win); win.close(); return; }
        this.view = new View(doc, () => {
          this.returnToWatch();
          try { this.owner.focus(); }
          catch (_) { this.view.health.textContent = 'Use the browser’s native return-to-tab control.'; }
        }, doc.body, size);
        this.view.historyChanged = () => { if (this.window === win) this.demand?.update(); };
        if (this.demandFactory) { this.demand = this.demandFactory(win); this.demand.update(); }
        // A visible PiP document owns this freshness timer, not a hidden main rAF.
        this.timer = win.setInterval(() => { this.sync(); this.render(); }, 5000);
        this.render(); this.feedback.textContent = '';
        win.requestAnimationFrame(() => {
          if (this.window !== win || win.closed) return;
          this.openingBounds = {outerWidth:win.outerWidth, outerHeight:win.outerHeight,
            innerWidth:win.innerWidth, innerHeight:win.innerHeight, requested:dimensions};
          if (size === 'fit-on-open' && (this.view.fitHeight() > win.outerHeight + 2 ||
              headerWidth(this.view, true) > this.view.root.getBoundingClientRect().width + 1))
            this.feedback.textContent = 'Browser size limits prevented the full opening fit. Scroll Mini Watch to reach all content.';
        });
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
    health(value) {
      const wasWritable = this.healthState.writable;
      this.healthState = value;
      if (value.terminal) { this.demand?.close(false); this.demand = null; this.demandFactory = null; }
      else if (wasWritable !== value.writable) this.demand?.update();
      this.sync(); this.render();
    }
    settings(values, instance) {
      if (instance && instance !== this.instance) {
        if (this.instance) { this.demand?.close(false); this.demand = null; this.demandFactory = null; }
        this.instance = instance; this.opened = false;
      }
      if (values) {
        this.placement = values.miniWatchPlacement;
        this.size = values.miniWatchSize || 'fit-on-open';
        this.feedback.textContent = '';
      }
      this.syncTheme(); this.sync(); this.render();
    }
    syncTheme() {
      if (!this.window) return;
      const source = this.owner.document.documentElement, root = this.window.document.documentElement;
      root.dataset.theme = source.dataset.theme;
      for (const name of this.themeProperties) root.style.removeProperty(name);
      this.themeProperties = []; root.style.removeProperty('color-scheme');
      if (source.dataset.theme !== 'web') return; // Classic keeps its exact shared CSS.
      // Document PiP can report dark while its opener is light. Inherit resolved
      // semantic roles, not a second palette or the PiP document's media result.
      const style = this.owner.getComputedStyle(source);
      this.themeProperties = [...style].filter(name => name.startsWith('--'));
      for (const name of this.themeProperties) root.style.setProperty(name, style.getPropertyValue(name));
      root.style.setProperty('color-scheme', this.appearance.matches ? 'dark' : 'light');
    }
    render() {
      if (!this.view) return;
      const now = Date.now();
      this.view.update(this.publication, this.healthState, now - this.receivedAt > 15000, this.observations, now);
    }
  }
  // Styles are loaded before enabling the opener button; no await or forbidden
  // post-open resize is needed in the activation handler. Shadow isolation leaves
  // the main document/CSP intact. It contains no acquisition, timer or live owner.
  class OpeningMeasure {
    constructor(owner) {
      this.owner = owner;
      const doc = owner.document;
      this.host = doc.createElement('div'); this.host.inert = true;
      this.host.setAttribute('aria-hidden', 'true');
      this.host.style.cssText = 'position:fixed;left:0;top:0;visibility:hidden;pointer-events:none';
      const shadow = this.host.attachShadow({mode:'closed'});
      this.body = doc.createElement('body'); shadow.append(this.body); doc.body.append(this.host);
      this.view = new View(doc, () => {}, this.body);
      this.loaded = Promise.all(['app.css', 'mini.css'].map(name => new Promise(resolve => {
        const link = doc.createElement('link'); link.rel = 'stylesheet';
        link.href = new URL('/' + name, owner.location.href).href;
        link.addEventListener('load', () => resolve(true), {once:true});
        link.addEventListener('error', () => resolve(false), {once:true}); shadow.append(link);
      }))).then(values => { this.ready = values.every(Boolean); });
    }
    read(controller) {
      const owner = this.owner, view = this.view, now = Date.now();
      view.update(controller.publication, controller.healthState, now - controller.receivedAt > 15000, controller.observations, now);
      // First-open native frame estimate is intentionally conservative; the API has
      // no pre-open frame/zoom query. Screen clamps remain browser-owned and scrollable.
      const frameWidth = 16, frameHeight = 48;
      // Do not misinterpret the opener's native side frame as page zoom.
      const scale = geometry(owner, controller.size === 'remember-last' ? 0 : frameWidth).scale;
      const style = owner.getComputedStyle(this.body);
      const padding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
      const horizontal = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight);
      // A stable, measured scrollbar gutter prevents capped disclosure from stealing
      // header space. Eight CSS pixels cover focus/rounding, not a fixed window target.
      // Remember keeps its first request and browser-owned bounds, without this reserve.
      const gutter = controller.size === 'remember-last' ? 0 : scrollbarWidth(view);
      const requested = controller.size === 'remember-last' ? 650 - frameWidth :
        Math.ceil((headerWidth(view, true) + horizontal + gutter + 8) * scale);
      const width = Math.max(1, Math.min(requested, owner.screen?.availWidth > 0 ? owner.screen.availWidth - frameWidth : requested));
      const contentWidth = width / scale - horizontal - gutter;
      const height = Math.ceil((contentHeight(view, contentWidth) + padding + 6) * scale);
      return {width, height: Math.max(1, Math.min(heightCap(owner) - frameHeight, height))};
    }
    close() { this.host.remove(); }
  }
  return {Controller};
})();
