'use strict';
// App-owned PiP presentation. No auth, source calls, totals or lifecycle inference.
const MiniWatch = (() => {
  const defaultNonRunningRows = 5;
  const nonRunningScrollback = 15; // Same bounded window as the shared catalog publication.
  const openingWidthRatio = 0.75;
  const graphemes = typeof Intl.Segmenter === 'function' ? new Intl.Segmenter(undefined, {granularity: 'grapheme'}) : null;
  function promptPreview(prompt) {
    if (!graphemes || !prompt?.event_id || prompt.is_compaction || typeof prompt.preview !== 'string') return '';
    const text = prompt.preview.replace(/[\s\p{Cc}]+/gu, ' ').trim();
    const parts = [...graphemes.segment(text)];
    if (parts.length <= 25) return text;
    return parts.slice(0, 25).map(part => part.segment).join('').trimEnd().replace(/(?:…|\.{3})+$/u, '').trimEnd() + '…';
  }
  function reconcile(parent, wanted) {
    const keep = new Set(wanted);
    for (const node of [...parent.children]) if (!keep.has(node)) node.remove();
    wanted.forEach((node, index) => {
      if (parent.children[index] === node) return;
      const before = parent.children[index] || null;
      if (parent.moveBefore && node.parentNode === parent) parent.moveBefore(node, before);
      else {
        const focus = parent.ownerDocument?.activeElement;
        const restore = focus && node.contains(focus);
        parent.insertBefore(node, before);
        if (restore) focus.focus({preventScroll: true});
      }
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
      this.started = Date.now(); this.clocks = new Map(); this.view = null; this.summaries = new Map();
    }
    observed(key, token, now) {
      const old = this.clocks.get(key)?.token;
      const fresh = typeof token === 'number' && typeof old === 'number' ? token > old : token !== old;
      if (token != null && fresh) this.clocks.set(key, {token, at: now});
    }
    context(card) {
      const summary = WatchView.retainSummary(card.session_summary, this.summaries.get(card.session_id));
      this.summaries.set(card.session_id, summary);
      return {...card, session_summary: summary};
    }
    update(publication, now) {
      if (!publication?.view || publication.state !== 'running') return;
      this.costs ||= new ReportView.CostDisplay();
      const view = WatchView.costProjection(publication.view, this.costs, publication.source_generation);
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
        const qualified = this.context(value);
        oldCards.set(key, qualified); return qualified;
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
        history_cards: (view.history_cards || []).map(card => this.context(card)),
        recent_finished_cards: (view.recent_finished_cards || []).map(card => this.context(card)),
        earlier_cards: (view.earlier_cards || []).map(card => this.context(card)),
        // Missing refresh data retains this day's usable summary only. The
        // configured boundary below still clears yesterday, even disconnected.
        daily_usage: daily ? dailyUsable || !previous?.daily_usage ||
          daily.day_start_ms !== previous.daily_usage.day_start_ms ? daily : previous.daily_usage :
          previous?.daily_usage?.day_end_ms > now ? previous.daily_usage : null,
        accounts: accounts ? {...view.accounts, accounts} : previous?.accounts};
      if (prompts && view.history_state === 'observed') {
        const present = new Set([...cards, ...(view.history_cards || []), ...(view.recent_finished_cards || [])].map(card => card.session_id));
        for (const key of this.summaries.keys()) if (!present.has(key)) this.summaries.delete(key);
      }
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
  // Select presentation representatives from canonical, already-acquired facts.
  // Never infer completion, revalue costs or resolve identity from display names.
  function sessions(view, nonRunningRows) {
    const active = new Map(), finished = new Map();
    const catalog = new Map((view?.earlier_previews || []).map(value => [value.session_id, value]));
    const start = value => [value.item?.prompt?.at_ms ?? 0, value.item?.prompt?.event_id || ''];
    const activity = value => value.preview ? value.card.activity_ms :
      value.running ? value.item.prompt.at_ms :
        value.item?.prompt?.completed_at_ms ?? catalog.get(value.card.session_id)?.activity_ms;
    const compare = (a, b) => (activity(a) ?? -Infinity) - (activity(b) ?? -Infinity) ||
      a.card.session_id.localeCompare(b.card.session_id) || start(a)[1].localeCompare(start(b)[1]);
    const add = (pool, value, newer) => {
      const old = pool.get(value.card.session_id);
      if (!old || newer(value, old)) pool.set(value.card.session_id, value);
    };
    for (const card of view?.active_cards || []) for (const item of card.rows || []) {
      const prompt = item.prompt;
      if (!card.focal_id || prompt.event_id !== card.focal_id || prompt.is_compaction) continue;
      const running = Boolean(prompt.in_progress || prompt.execution_unverified);
      const value = {card, item, running, historical: false};
      if (running) add(active, value, (a, b) => {
        const verified = p => Boolean(p.in_progress && !p.execution_unverified);
        const pa = a.item.prompt, pb = b.item.prompt;
        return verified(pa) !== verified(pb) ? verified(pa) :
          pa.at_ms !== pb.at_ms ? pa.at_ms > pb.at_ms : pa.event_id.localeCompare(pb.event_id) > 0;
      });
      else add(finished, value, (a, b) => compare(a, b) > 0);
    }
    for (const card of [...(view?.earlier_cards || []), ...WatchView.finishedCards(view)]) {
      const value = {card, item: card.rows?.[0], running: false, historical: true};
      add(finished, value, (a, b) => compare(a, b) >= 0);
    }
    for (const card of view?.earlier_previews || []) if (!finished.has(card.session_id))
      finished.set(card.session_id, {card, preview: true, running: false, historical: true});
    for (const id of active.keys()) finished.delete(id);
    const fillers = [...finished.values()].sort(compare).slice(-nonRunningScrollback);
    const split = Math.max(0, fillers.length - nonRunningRows);
    // Older finished rows form scrollback. Preserve activity order within
    // each band: even a long-running session belongs in the opening band.
    const latest = [...active.values(), ...fillers.slice(split)].sort(compare);
    return [...fillers.slice(0, split), ...latest]
      .map(value => ({...value, catalog: catalog.get(value.card.session_id)}));
  }
  function activityLabel(prompt, running, now, today) {
    const at = running ? prompt?.at_ms : prompt?.completed_at_ms;
    if (!Number.isSafeInteger(at) || at < 0) return '—';
    const clock = (running ? prompt.display?.clock : prompt.display?.finished_clock) || '—';
    const full = running ? prompt.display?.start_date_time : prompt.display?.finished_date_time;
    const hour = 3600000, day = 24 * hour, age = now - at;
    // Future times keep their supported clock, never a negative "ago". Without
    // configured-local day evidence, conservatively retain the prepared clock.
    if (age < 12 * hour || !today || !/^\d{4}-\d{2}-\d{2} /.test(full || '') || full.startsWith(today + ' ')) return clock;
    if (age < day) return Math.floor(age / hour) + 'h ago';
    if (age < 30 * day) return Math.floor(age / day) + 'd ago';
    if (age < 365 * day) return Math.floor(age / (30 * day)) + 'm ago';
    return Math.floor(age / (365 * day)) + 'y ago';
  }
  const hydrationHelp = {
    reading: 'Reading this session’s prompt history.',
    waiting: 'This source read is taking longer than usual.',
    retrying: 'Source evidence is incomplete or delayed; another read will be attempted.',
    unknown: 'No representative prompt could be confirmed.',
    unavailable: 'Session details are currently unavailable from the source.'
  };
  const hydrationDetail = value => hydrationHelp[value?.hydration_state] || 'Waiting for an available history slot.';
  function measurementRow(view) {
    const row = view.sessionRow(); row.inert = true; row.setAttribute('aria-hidden', 'true');
    row.children[0].children[0].textContent = '23:59';
    row.children[1].children[0].children[0].textContent = 'Session';
    row.children[2].children[0].textContent = '90 000';
    row.children[3].children[0].textContent = '90 000';
    row.children[4].textContent = '120k';
    return row;
  }
  // Budget the opening band's real heights independently:
  // every running row, plus the newest configured number of non-running rows.
  function boundTable(view, root, {reserve = false, viewport = false} = {}) {
    const region = root.querySelector('.mini-prompts'), table = region.firstElementChild;
    const body = table.tBodies[0], rows = [...body.rows];
    // DOM attributes, rather than class names, also cover unverified running
    // representatives and survive cloning for opening/explicit-fit measurement.
    const nonRunning = rows.filter(row => row.dataset.running === 'false');
    const capacity = view.nonRunningRows;
    const visible = [...rows.filter(row => row.dataset.running !== 'false'), ...nonRunning.slice(-capacity)];
    const zoom = region.currentCSSZoom || 1;
    const header = table.tHead.getBoundingClientRect().height;
    const height = row => row.getBoundingClientRect().height;
    let content = header + visible.reduce((total, row) => total + height(row), 0);
    if (reserve && nonRunning.length < capacity) {
      const sample = measurementRow(view);
      body.append(sample);
      try {
        const missing = capacity - nonRunning.length;
        const notice = rows.find(row => row.dataset.running === undefined);
        content += Math.max(0, missing * height(sample) - (notice ? height(notice) : 0));
      } finally { sample.remove(); }
    }
    let available = Infinity, minimum = 0;
    if (viewport) {
      const win = view.doc.defaultView;
      const inset = region.getBoundingClientRect().top + win.scrollY;
      const padding = parseFloat(win.getComputedStyle(view.doc.body).paddingBottom) * zoom;
      // Keep at least a header and one row reachable even in a very short
      // viewport; the document can still scroll past the header or to accounts.
      minimum = (header + (rows.length ? height(rows.at(-1)) : 0)) / zoom;
      available = (win.innerHeight - inset - padding) / zoom;
    }
    const gutter = () => region.offsetHeight - region.clientHeight;
    const apply = horizontal => {
      const desired = Math.ceil(content / zoom + horizontal);
      const limit = Math.max(Math.ceil(minimum + horizontal), Math.floor(available));
      region.style.maxHeight = Math.min(desired, limit) + 'px';
      if (reserve) region.style.minHeight = desired + 'px';
    };
    apply(gutter());
    // Some scrollbar modes report their horizontal gutter only after layout.
    apply(gutter());
  }
  // Clones are invisible, inert measurement artifacts, never published prompt data.
  function contentHeight(view, width, reserve = true) {
    const {doc, root} = view, win = doc.defaultView;
    const copy = root.cloneNode(true); copy.classList.add('mini-measuring');
    copy.inert = true; copy.setAttribute('aria-hidden', 'true'); copy.style.width = width + 'px';
    root.parentNode.append(copy);
    try {
      boundTable(view, copy, {reserve});
      return Math.ceil(copy.getBoundingClientRect().height);
    } finally { copy.remove(); }
  }
  function heightCap(win) {
    return Math.min(1000, win.screen?.availHeight > 0 ? win.screen.availHeight : 1000);
  }
  function headerWidth(view, reserve = false) {
    // Only inert header clones: never change real totals.
    const copy = view.root.firstElementChild.cloneNode(true);
    copy.classList.add('mini-header-measuring'); copy.inert = true;
    copy.setAttribute('aria-hidden', 'true'); view.root.append(copy);
    try {
      const daily = copy.querySelector('.mini-daily > span');
      let width = 0;
      for (const text of reserve ? [daily.textContent, 'CCost Today 90 000 · 999 prompts'] : [daily.textContent]) {
        daily.textContent = text;
        width = Math.max(width, copy.getBoundingClientRect().width);
      }
      return width;
    }
    finally { copy.remove(); }
  }
  function tableWidth(view) {
    const table = view.body.parentNode.cloneNode(true);
    table.classList.add('mini-table-measuring'); table.inert = true; table.setAttribute('aria-hidden', 'true');
    const sample = measurementRow(view);
    table.tBodies[0].replaceChildren(sample); view.root.append(table);
    try { return 2.6 * [0, 2, 3, 4].reduce((sum, index) => sum + sample.children[index].getBoundingClientRect().width, 0); }
    finally { table.remove(); }
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
  function targetHeight(view, reserve = true) {
    // Exclude the same conservative side frame as opening for explicit shrink.
    // Treating it as zoom makes the inferred top frame depend on the OLD height.
    const win = view.doc.defaultView, {scale, frame} = geometry(win, reserve ? 0 : 16);
    const style = win.getComputedStyle(view.doc.body);
    const padding = (parseFloat(style.paddingTop) + parseFloat(style.paddingBottom)) * (view.doc.body.currentCSSZoom || 1);
    const width = view.root.getBoundingClientRect().width / (view.root.currentCSSZoom || 1);
    return Math.min(heightCap(win), Math.ceil((contentHeight(view, width, reserve) + padding + 4) * scale + frame));
  }
  // One height-only native request per explicit Fit, never per publication.
  class FitSize {
    constructor(view) {
      this.view = view; this.win = view.doc.defaultView;
    }
    bounds() { return {width: this.win.outerWidth, height: this.win.outerHeight}; }
    resize(width, height) {
      if (typeof this.win.resizeBy === 'function') this.win.resizeBy(0, height - this.win.outerHeight);
      else this.win.resizeTo(width, height);
    }
    available() {
      const win = this.win;
      return !win.closed && this.view.root.isConnected !== false && win.innerWidth > 0 &&
        (!win.navigator?.userActivation || win.navigator.userActivation.isActive) &&
        (typeof win.resizeBy === 'function' || typeof win.resizeTo === 'function');
    }
    fit() {
      if (!this.available()) return;
      const before = this.bounds(), height = this.view.fitHeight(false);
      const scroll = this.view.doc.scrollingElement;
      // Native zoom quantizes achieved CSS pixels. An already scroll-free fit
      // within the small rounding margin must not oscillate on identical clicks.
      if (scroll && scroll.scrollHeight <= scroll.clientHeight + 1 &&
          Math.abs(height - before.height) <= 4 * geometry(this.win, 16).scale) return;
      if (height === before.height) return;
      try { this.resize(before.width, height); }
      catch (_) { /* Native refusal leaves ordinary scrolling available. */ }
    }
  }
  class View {
    constructor(doc, returnToWatch, mount = doc.body) {
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
      this.summary.setAttribute('aria-label', 'Return to Watch in the Existing Parent Tab');
      ContextHelp.attach(this.summary, 'Return to Watch in the Existing Parent Tab');
      this.summary.addEventListener('click', returnToWatch);
      this.summary.append(el('span', 'Cost Guard · Watch', 'mini-brand'));
      this.daily = el('p', undefined, 'mini-daily'); this.dailyText = el('span');
      this.dailyLead = el('span'); this.dailyAmount = el('span');
      this.dailyTail = el('span'); this.dailyText.append(this.dailyLead, this.dailyAmount, this.dailyTail);
      this.daily.append(this.dailyText);
      this.dailyNote = el('span', '', 'mini-daily-note'); this.daily.append(this.dailyNote);
      this.fitButton = el('button', '↕', 'mini-fit-height'); this.fitButton.type = 'button';
      this.fitButton.setAttribute('aria-label', 'Fit Mini Watch Height');
      ContextHelp.attach(this.fitButton, 'Fit Mini Watch Height');
      this.fitButton.addEventListener('click', () => this.fitSize?.fit());
      const actions = el('div', undefined, 'mini-actions'); actions.append(this.summary, this.fitButton);
      const top = el('header', undefined, 'mini-header'); top.append(actions, this.daily);
      this.health = el('p', '', 'mini-health'); this.health.setAttribute('role', 'status');
      this.prompts = el('div', undefined, 'mini-prompts'); this.prompts.tabIndex = 0;
      this.prompts.setAttribute('role', 'region'); this.prompts.setAttribute('aria-label', 'Session activity');
      this.body = this.table(this.prompts);
      this.nonRunningRows = defaultNonRunningRows;
      this.promptRows = new Map(); this.emptyPrompts = this.emptyRow(5);
      this.compactAccounts = new AccountCards.CompactView(doc);
      this.accounts = this.compactAccounts.root;
      this.fitSize = mount === doc.body ? new FitSize(this) : null;
      this.root.append(top, this.health, this.prompts, this.accounts); mount.replaceChildren(this.root);
      if (mount === doc.body) doc.defaultView.addEventListener('resize', () => this.boundSessions());
    }
    table(parent) {
      const table = this.el('table', undefined, 'mini-prompt-table'), head = this.el('thead'), header = this.el('tr');
      table.setAttribute('aria-label', 'Session activity: representative prompt CCost, whole-session Total CCost and estimated next incoming context (Ctx)');
      for (const name of ['Activity', 'Session', 'CCost', 'Total', 'Ctx']) {
        const cell = this.el('th'); cell.scope = 'col';
        const explanation = {Activity: '• For a running prompt, shows when it started.\n• For a finished prompt, shows when it finished.\n• While prompt details load, shows session activity.', Session: 'The name of the session.',
          CCost: "Reference cost of this session's latest represented prompt, including attributed linked subagent calls.",
          Total: ReportView.headerHelp.sessionCost,
          Ctx: ReportView.headerHelp.context}[name];
        const button = ContextHelp.button(name, explanation, this.doc);
        if (name === 'Session') cell.className = 'mini-session-cell';
        cell.append(button);
        header.append(cell);
      }
      head.append(header); const body = this.el('tbody'); table.append(head, body); parent.append(table); return body;
    }
    fitHeight(reserve = true) { return targetHeight(this, reserve); }
    atLatest() {
      const region = this.prompts;
      return Boolean(this.body.rows) && region.scrollHeight - region.clientHeight - region.scrollTop <= 1 &&
        !region.contains(this.doc.activeElement);
    }
    boundSessions(followLatest = this.atLatest()) {
      if (!this.body.rows) return; // VM fixtures have no layout engine.
      boundTable(this, this.root, {viewport: true});
      if (followLatest) this.prompts.scrollTop = this.prompts.scrollHeight;
    }
    emptyRow(columns) {
      const row = this.el('tr'), cell = this.el('td'); cell.colSpan = columns;
      cell.append(this.el('span', '', 'mini-empty')); row.append(cell); return row;
    }
    sessionRow() {
      const row = this.el('tr');
      for (let index = 0; index < 5; index++) row.append(this.el('td'));
      const time = this.el('span', '', 'mini-activity');
      const indicator = this.el('span', '', 'mini-activity-running'); indicator.setAttribute('aria-hidden', 'true');
      time.append(indicator, this.el('span'));
      ContextHelp.value(time, () => row.activityHelp || 'Unknown finish time'); row.children[0].append(time);
      const cell = row.children[1], value = this.el('span', undefined, 'mini-session-value');
      cell.className = 'mini-session-cell';
      const title = this.el('span', '', 'mini-session');
      ContextHelp.value(title, () => row.sessionHelp);
      value.append(title);
      cell.append(value);
      const promptCost = this.el('span', '', 'mini-cost-value'), sessionCost = this.el('span', '', 'mini-cost-value');
      row.children[2].append(promptCost); row.children[3].append(sessionCost);
      row.children[4].className = 'mini-context';
      row.metricHelpLost = () => this.prompts.focus?.({preventScroll: true});
      return row;
    }
    drawSession(cell, card) {
      const title = card.title || card.session_id;
      ReportView.text(cell.children[0].children[0], title);
      return title;
    }
    rowHelp(row, session, item, card, historical) {
      const number = item?.prompt?.prompt_number;
      const preview = promptPreview(item?.prompt);
      const identity = number == null ? 'Prompt number unavailable' : 'Prompt #' + number;
      row.sessionHelp = `${session}\n${identity}${preview ? (number == null ? '\nPrompt: ' : ': ') + preview : ''}`;
      const prompt = item?.prompt;
      const highlight = !historical && prompt?.in_progress && !prompt.execution_unverified && !prompt.aborted && !prompt.has_error;
      row.costHelp = this.promptDetails(item, highlight);
      const source = card.session_summary?.context, warning = source?.warning;
      const exceeded = warning?.severity === 'exceeded' && source.context_state === 'ready-current' &&
        Number.isFinite(source.watch_next_context_tokens) && warning.guidance_state === 'ready';
      const cell = row.children[4];
      cell.dataset.guidance = warning?.guidance_state || 'ready';
      cell.classList.toggle('mini-context-exceeded', exceeded);
      row.contextHelp = exceeded ? [warning.text?.replace(/^\[|\]$/g, ''),
        warning.multiplier != null && ReportView.display(warning, 'warning_cost').replace(/^\(|\)$/g, '')]
        .filter(Boolean).join(' · ') : '';
    }
    drawMetrics(row, card, prompt, catalog, context) {
      const summary = card.session_summary, cost = summary?.cost;
      const useCatalog = catalog?.total_ccost != null && (summary?.state !== 'observed' || !cost?.complete);
      const retained = useCatalog ? catalog.total_state === 'retained' :
        cost?.known_ccost != null && ['checking', 'unavailable'].includes(summary?.state);
      const reasons = prompt ? null : catalog?.metric_absences;
      const totalHelp = () => (useCatalog ? 'Whole-session reference CCost from the shared Sessions index.' :
        ReportView.sessionCostHelp(cost, summary)) + (retained ? '\nLast qualified value; refresh pending.' : '');
      row.totalCostHelp = totalHelp();
      ReportView.metric(row.children[2].children[0], 'prompt_ccost', {
        value: () => ReportView.metricToken(prompt, 'ccost'), reason: reasons?.prompt_ccost,
        help: () => row.costHelp, label: shown => `Prompt reference CCost: ${shown}`, onHelpLost: row.metricHelpLost
      });
      ReportView.metric(row.children[3].children[0], 'total', {
        value: () => useCatalog ? ReportView.metricToken(catalog, 'total_ccost') : ReportView.metricToken(cost, 'account_ccost'),
        help: totalHelp,
        label: shown => `Whole-session reference CCost: ${shown}${retained ? ' (retained)' : ''}`,
        onHelpLost: row.metricHelpLost
      });
      ReportView.metric(row.children[4], 'ctx', {
        value: context?.context_state === 'invalidated' ? null : ReportView.metricToken(context, 'watch_next_context_tokens'),
        reason: reasons?.ctx, help: row.contextHelp,
        label: catalog && ['refreshing', 'retrying', 'unavailable', 'partial'].includes(card.state) ?
          shown => `Next incoming context: ${shown} (retained or partial)` : null,
        onHelpLost: row.metricHelpLost
      });
      if (!row.children[4].className.includes('help-value')) row.children[4].tabIndex = -1;
    }
    drawPreview(row, card, now, today) {
      const text = ReportView.text, session = this.drawSession(row.children[1], card);
      const help = hydrationDetail(card);
      const reason = card.hydration_reason === 'http_auth_failure' ? ' Source authorization is required.' : '';
      row.className = ''; row.setAttribute('aria-label', session + ' · Session activity');
      row.sessionHelp = `${session}\n${help}${reason}`;
      row.contextHelp = ''; row.children[4].classList.toggle('mini-context-exceeded', false);
      row.children[4].dataset.guidance = 'pending';
      const time = row.children[0].children[0], at = card.activity_ms;
      text(time.children[0], '');
      // Generic activity only; no synthetic prompt, event ID or finish outcome.
      const full = card.display?.activity_date_time;
      const label = card.display?.activity_clock || '—';
      const age = now - at, day = 86400000;
      text(time.children[1], at == null || age < 43200000 || !today || full?.startsWith(today + ' ') ? label :
        age < day ? Math.floor(age / 3600000) + 'h ago' : age < 30 * day ? Math.floor(age / day) + 'd ago' :
        age < 365 * day ? Math.floor(age / (30 * day)) + 'm ago' : Math.floor(age / (365 * day)) + 'y ago');
      row.activityHelp = 'Session activity' + (full ? ' · ' + full : '') +
        (card.activity_origin === 'catalog' ? '\nSource catalog activity, not a prompt finish.' : '');
      this.drawMetrics(row, card, null, card, null);
    }
    costGroups(value, session = false) {
      return WatchView.costGroups(value, session);
    }
    promptDetails(item, highlight) {
      return WatchView.promptDetails(item, highlight);
    }
    update(publication, health, overdue, observations, now) {
      const snapshot = observations.snapshot(now);
      const view = health.terminal ? {...snapshot, earlier_previews: [], earlier_cards: []} : snapshot;
      const fresh = health.kind === 'connected' && publication?.state === 'running' && !overdue;
      const text = ReportView.text;
      const state = {authorization_required: 'Authorization expired · return to Cost Guard',
        identity_changed: 'Host changed · reopen Cost Guard', stopped: 'Host stopped · restart Cost Guard'}[health.kind];
      text(this.health, state || '');
      this.health.hidden = !this.health.textContent;
      this.root.dataset.live = fresh && publication?.view?.cards_state === 'observed' ? 'true' : 'false';
      this.drawDaily(view);
      this.drawSessions(view, now);
      this.drawAccounts(view);
      ContextHelp.refresh(this.root);
    }
    drawDaily(view) {
      const value = view?.daily_usage, state = view?.daily_state;
      this.dailyValue = value;
      ReportView.text(this.dailyLead, 'CCost Today ');
      ReportView.text(this.dailyAmount, () => ReportView.display(value, 'daily_ccost'));
      ReportView.text(this.dailyTail, value ? ` · ${value.prompt_count} prompts` : '');
      ReportView.text(this.dailyNote, '');
      this.daily.className = 'mini-daily';
    }
    drawSessions(view, now = Date.now()) {
      const wanted = [], seen = new Set(), text = ReportView.text;
      const localNow = ReportView.formatDateTime(now, ReportView.DateTimeMode.DATE,
        view?.timezone_id ?? ReportView.configuredTimezone());
      const today = localNow === 'N/A' ? null : localNow;
      const values = sessions(view, this.nonRunningRows);
      const nonRunning = values.filter(value => !value.running);
      // A metadata preview can fill space before prompt history settles.
      const needsHistory = nonRunning.slice(-this.nonRunningRows)
        .filter(value => !value.preview || value.card.empty_history).length < this.nonRunningRows;
      if (this.needsHistory !== needsHistory) { this.needsHistory = needsHistory; this.historyChanged?.(); }
      for (const {card, item, running, historical, preview, catalog} of values) {
        const prompt = item?.prompt, key = card.session_id;
        if (seen.has(key)) continue;
        seen.add(key);
        let row = this.promptRows.get(key);
        if (!row) {
          row = this.sessionRow(); row.dataset.id = key;
          this.promptRows.set(key, row);
        }
        row.dataset.running = String(running);
        if (preview) { this.drawPreview(row, card, now, today); wanted.push(row); continue; }
        const outcome = prompt?.execution_unverified ? 'Unverified' : prompt?.in_progress ? prompt.subagent_active ? 'Running (subagent activity)' : 'Running' : prompt?.aborted ? 'Aborted' : prompt?.has_error ? 'Error' : prompt?.completed_successfully ? 'Completed' : 'Ended';
        const reason = !running && prompt?.abort_reason ? ' · ' + prompt.abort_reason.replaceAll('_', ' ') : '';
        const session = this.drawSession(row.children[1], card);
        const summaryContext = card.session_summary?.context;
        const source = historical || summaryContext?.context_scope ? summaryContext : item?.live_context;
        this.rowHelp(row, session, item, card, historical);
        row.setAttribute('aria-label', `${session} · Prompt ${prompt?.prompt_number ?? 'unknown'} · ${outcome}${reason}`);
        row.className = historical || prompt?.execution_unverified ? '' : prompt?.in_progress ? 'mini-running' : prompt?.aborted || prompt?.has_error ? 'mini-error' : prompt?.completed_successfully ? 'mini-success' : '';
        const at = running ? prompt?.at_ms : prompt?.completed_at_ms;
        const known = Number.isSafeInteger(at) && at >= 0;
        row.activityHelp = known ? (running ? prompt.display?.mini_start_date_time : prompt.display?.mini_finished_date_time) : null;
        const time = row.children[0].children[0];
        const verifiedRunning = !historical && prompt?.in_progress && !prompt.execution_unverified &&
          !prompt.aborted && !prompt.has_error && !prompt.completed_successfully;
        text(time.children[0], verifiedRunning ? '▶ ' : '');
        text(time.children[1], activityLabel(prompt, running, now, today));
        row.activityHelp ||= running ? 'Unknown start time' : 'Unknown finish time';
        if (!known && !running && Number.isSafeInteger(prompt?.at_ms) && prompt.at_ms > 0)
          row.activityHelp += '\nStarted: ' + (prompt.display?.date_time || 'N/A') + '\nCompletion unverified.';
        if (prompt?.model_display_help) row.activityHelp += '\n\n' + prompt.model_display_help;
        if (catalog && ['refreshing', 'retrying', 'unavailable', 'partial'].includes(card.state)) {
          row.sessionHelp += `\n${hydrationDetail(catalog)} Available prompt details may be retained.`;
          row.costHelp += '\nProvisional or retained while prompt details are rechecked.';
        }
        this.drawMetrics(row, card, prompt, catalog, source);
        wanted.push(row);
      }
      const certified = view?.history_state === 'observed' || view?.history_epoch > 0;
      const notice = !values.some(value => value.preview) && nonRunning.length < this.nonRunningRows &&
        (view?.recent_finished_cards?.length || !(certified && wanted.length)) ?
        WatchView.historyNotice(view, values.some(value => value.historical)) : '';
      text(this.emptyPrompts.children[0].children[0], notice || (view?.cards_state === 'observed' ? 'No sessions' : 'Loading…'));
      this.emptyPrompts.setAttribute('role', 'status');
      reconcile(this.body, [...wanted, ...(!wanted.length || notice ? [this.emptyPrompts] : [])]);
      for (const key of this.promptRows.keys()) if (!seen.has(key)) this.promptRows.delete(key);
    }
    drawAccounts(view) {
      this.compactAccounts.update(view);
    }
  }
  class Controller {
    constructor(owner, button, feedback, returnToWatch, measureFactory = () => new OpeningMeasure(owner)) {
      this.owner = owner; this.button = button; this.feedback = feedback; this.returnToWatch = returnToWatch;
      this.window = null; this.view = null; this.pending = null; this.ended = false;
      this.failure = '';
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
      // Keep unavailable controls keyboard-discoverable. Normal preparation is quiet.
      this.button.setAttribute('aria-disabled', String(Boolean(this.reason) || !this.placement ||
        !this.measure?.ready || Boolean(this.healthState.terminal)));
      ReportView.text(this.feedback, this.failure || '');
      this.button.title = '';
    }
    release(win) {
      if (this.window !== win) return;
      this.window = this.view = null;
      if (this.pending?.window === win) {
        const request = this.pending; this.pending = null;
        request.cancelled = true; request.cancelStyles?.();
      }
      win.clearInterval(this.timer);
      this.demand?.close(); this.demand = null;
      this.appearance.removeEventListener('change', this.themeChanged);
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
      this.failure = '';
      this.sync();
    }
    loadStyles(doc, request) {
      return new Promise((resolve, reject) => {
        const links = [], cleanup = () => {
          for (const [link, loaded, failed] of links) {
            link.removeEventListener('load', loaded); link.removeEventListener('error', failed);
          }
          request.cancelStyles = null;
        };
        request.cancelStyles = () => { cleanup(); resolve(false); };
        let remaining = 2;
        for (const name of ['app.css', 'mini.css']) {
          const link = doc.createElement('link'); link.rel = 'stylesheet';
          link.href = new URL('/' + name, this.owner.location.href).href;
          const loaded = () => { if (!--remaining) { cleanup(); resolve(true); } };
          const failed = () => { cleanup(); reject(new Error('Mini Watch stylesheet unavailable')); };
          links.push([link, loaded, failed]);
          link.addEventListener('load', loaded); link.addEventListener('error', failed);
          doc.head.append(link);
        }
      });
    }
    async toggle() {
      this.sync();
      if (this.reason || this.ended || !this.placement || !this.measure?.ready || this.healthState.terminal) {
        this.failure = 'Could not open Mini Watch. Try again.'; this.sync(); return;
      }
      if (this.window) { this.close(); return; }
      if (this.pending) {
        this.pending.cancelled = !this.pending.cancelled; return;
      }
      const request = {cancelled: false}; this.pending = request;
      this.failure = ''; this.sync();
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
        if (request.cancelled || this.ended || instance !== this.instance || win.closed ||
            this.owner.documentPictureInPicture.window !== win) {
          win.close(); return;
        }
        this.window = win; request.window = win;
        win.addEventListener('pagehide', () => { this.release(win); this.sync(); }, {once: true});
        const doc = win.document; doc.title = 'Mini Watch · Cost Guard'; doc.documentElement.lang = 'en';
        doc.documentElement.dataset.miniSize = size;
        this.syncTheme();
        this.appearance.addEventListener('change', this.themeChanged);
        const icon = doc.createElement('link'); icon.rel = 'icon'; icon.type = 'image/x-icon';
        icon.href = new URL('/favicon-cg1.ico', this.owner.location.href).href; doc.head.append(icon);
        const shell = doc.createElement('p'); shell.className = 'mini-opening';
        shell.setAttribute('role', 'status'); shell.textContent = 'Loading Mini Watch…';
        doc.body.replaceChildren(shell); this.sync();
        // The inert sizing document already loaded these exact same-origin rules.
        // Construct sheets in the new document's realm: no inline-style CSP bypass,
        // refetch, second Live owner, or unstyled sensitive first layout.
        const styled = this.measure.styleDocument?.(doc);
        // Avoid an unstyled first layout creating a vertical scrollbar which then
        // steals the measured header width and keeps itself alive through wrapping.
        if (!styled && !await this.loadStyles(doc, request)) return;
        if (typeof ControlFocus !== 'undefined') ControlFocus.install(doc);
        if (request.cancelled || this.ended || win.closed || this.window !== win) { this.release(win); win.close(); return; }
        this.view = new View(doc, () => {
          this.returnToWatch();
          try { this.owner.focus(); }
          catch (_) { this.view.health.textContent = 'Use the browser’s native return-to-tab control.'; }
        });
        this.view.historyChanged = () => { if (this.window === win) this.demand?.update(); };
        this.render();
        if (this.demandFactory) { this.demand = this.demandFactory(win); this.demand.update(); }
        // A visible PiP document owns this freshness timer, not a hidden main rAF.
        this.timer = win.setInterval(() => { this.sync(); this.render(); }, 5000);
        win.requestAnimationFrame(() => {
          if (this.window !== win || win.closed) return;
          this.openingBounds = {outerWidth:win.outerWidth, outerHeight:win.outerHeight,
            innerWidth:win.innerWidth, innerHeight:win.innerHeight, requested:dimensions};
          if (size === 'fit-on-open' && this.view.fitHeight() > win.outerHeight + 2) {
            this.failure = 'Browser size limits prevented the full opening fit. Scroll Mini Watch to reach all content.';
            this.sync();
          }
        });
      } catch (_) {
        const cancelled = request.cancelled;
        if (win) { this.release(win); win.close(); }
        if (!cancelled) this.failure = 'Could not open Mini Watch. Try again.';
      } finally { if (this.pending === request) this.pending = null; this.sync(); }
    }
    update(value) {
      // Progress events and repeated HTTP snapshots may contain the same retained
      // Live value. They are not fresh source/presentation publications.
      if (typeof value?.view?.now_ms === 'number' && value.view.now_ms < this.publication?.view?.now_ms) return;
      // A changed source cannot inherit prompt observations or displayed context.
      const scope = JSON.stringify([this.instance, value?.view?.source_label]);
      if (scope !== this.sourceScope) {
        this.sourceScope = scope; this.observations = new Observations();
      }
      const epoch = JSON.stringify([value?.view?.now_ms, value?.source_observed_at_ms]);
      if (epoch !== this.epoch) { this.epoch = epoch; this.receivedAt = Date.now(); }
      this.observations.update(value, Date.now());
      this.publication = value; this.sync(); this.render();
    }
    health(value) {
      const wasWritable = this.healthState.writable;
      this.healthState = value;
      if (value.terminal) {
        if (this.pending) this.close();
        this.demand?.close(false); this.demand = null; this.demandFactory = null;
      }
      else if (wasWritable !== value.writable) this.demand?.update();
      this.sync(); this.render();
    }
    settings(values, instance) {
      if (instance && instance !== this.instance) {
        if (this.pending) this.close();
        if (this.instance) { this.demand?.close(false); this.demand = null; this.demandFactory = null; }
        this.instance = instance; this.opened = false;
        this.publication = null; this.observations = new Observations();
        this.view?.drawSessions(null); this.measure?.view?.drawSessions(null);
      }
      if (values) {
        this.placement = values.miniWatchPlacement;
        this.size = values.miniWatchSize || 'fit-on-open';
        this.nonRunningRows = values.miniWatchNonRunningRows ?? defaultNonRunningRows;
        this.failure = '';
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
      const followLatest = this.view.atLatest();
      this.view.nonRunningRows = this.nonRunningRows ?? defaultNonRunningRows;
      this.view.update(this.publication, this.healthState, now - this.receivedAt > 15000, this.observations, now);
      this.view.boundSessions(followLatest);
    }
    defaultContentWidth() {
      return this.measure?.ready ? this.measure.defaultContentWidth?.() : null;
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
      }))).then(values => {
        this.ready = values.every(Boolean); this.failed = !this.ready;
        if (this.ready) {
          try { this.styles = [...shadow.querySelectorAll('link')].map(link =>
            [...link.sheet.cssRules].map(rule => rule.cssText).join('\n')); }
          catch (_) { /* Unavailable CSSOM uses ordinary same-origin links. */ }
        }
      });
    }
    styleDocument(doc) {
      if (!this.styles) return false;
      try {
        const sheets = this.styles.map(css => {
          const sheet = new doc.defaultView.CSSStyleSheet(); sheet.replaceSync(css); return sheet;
        });
        doc.adoptedStyleSheets = sheets; return true;
      } catch (_) { return false; } // Native support/refusal retains the link fallback.
    }
    defaultContentWidth() {
      return Math.max(headerWidth(this.view, true),
        tableWidth(this.view) + scrollbarWidth(this.view)) + 8;
    }
    read(controller) {
      const owner = this.owner, view = this.view, now = Date.now();
      view.nonRunningRows = controller.nonRunningRows ?? defaultNonRunningRows;
      view.update(controller.publication, controller.healthState, now - controller.receivedAt > 15000, controller.observations, now);
      // First-open native frame estimate is intentionally conservative; the API has
      // no pre-open frame/zoom query. Screen clamps remain browser-owned and scrollable.
      const frameWidth = 16, frameHeight = 48;
      // Do not misinterpret the opener's native side frame as page zoom.
      const scale = geometry(owner, controller.size === 'remember-last' ? 0 : frameWidth).scale;
      const style = owner.getComputedStyle(this.body);
      const padding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
      const horizontal = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight);
      // A stable, measured table scrollbar gutter prevents extra rows from stealing
      // header space. Eight CSS pixels cover focus/rounding, not a fixed window target.
      // Remembered placement/size is browser-owned. Only its first-open fallback
      // is compacted here, alongside the measured Fit request.
      const requested = controller.size === 'remember-last' ? 650 - frameWidth :
        Math.ceil((this.defaultContentWidth() + horizontal) * scale);
      const screenWidth = owner.screen?.availWidth > 0 ? owner.screen.availWidth - frameWidth : requested;
      const width = Math.max(1, Math.round(Math.min(requested, screenWidth) * openingWidthRatio));
      const contentWidth = Math.max(1, width / scale - horizontal);
      const height = Math.ceil((contentHeight(view, contentWidth) + padding + 6) * scale);
      return {width, height: Math.max(1, Math.min(heightCap(owner) - frameHeight, height))};
    }
    close() { this.host.remove(); }
  }
  return {Controller};
})();
