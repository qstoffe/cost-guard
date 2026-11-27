'use strict';
// Complete history in its own viewport, assembled from one pinned source revision.
const SessionDetail = (() => {
  const el = (...args) => ReportView.element(...args);
  const columns = [
    ['Prompt', 'Local start time, prompt number and preview. [RUNNING] requires observed ongoing work. [ABORTED] means the prompt was aborted.'],
    ['Model', ReportView.headerHelp.model],
    ['Effort', 'Reasoning effort requested for the main prompt.'],
    ['CCost', ReportView.headerHelp.promptCost],
    ['Calls', ReportView.headerHelp.calls],
    ['Duration', ReportView.headerHelp.duration],
    ['Ictx', 'Context on the first request of this prompt, not the next session context. N/A is unknown.'],
    ['Ictx CCost', ReportView.headerHelp.incomingContextCost],
    ['Extra CCost', ReportView.headerHelp.extraCost],
    ['Token Mix %', 'Token percentages in Input / Cached input / Cache write / Output order. Output includes reasoning. Not cost.']
  ];
  const footerMetrics = {
    3: ['total_ccost', 'session total CCost'],
    4: ['total_calls', 'session total calls'],
    5: ['duration_ms', 'session total duration'],
    7: ['total_incoming_context_ccost', 'session incoming context CCost'],
    8: ['total_extra_ccost', 'session extra CCost'],
    9: ['total_token_mix_percent', 'session total token mix']
  };
  const validMix = values => Array.isArray(values) && values.length === 4 &&
    values.every(value => Number.isFinite(value) && value >= 0);
  const tokenCount = new Intl.NumberFormat('en-US');
  const initialReadRetries = 3;
  const restartableReads = new Set(['detail_expired', 'detail_busy', 'detail_read_stale',
    'inconsistent_history', 'inconsistent_activity']);
  const invalidatingFailures = new Set(['instance_stopping', 'authentication_required', 'host_identity_changed',
    'csrf_required', 'permission_denied', 'http_auth_failure', 'source_identity_changed', 'session_missing']);
  class Values {
    constructor() { this.clear(); }
    clear() { this.scope = null; this.retained = false; this.mixes = new Map(); this.totals = new Map(); }
    select(row, key, state, cache) {
      const names = key === 'total_ccost' ? ['total_ccost', 'session_cost_help'] : [key];
      const extract = tokens => Object.fromEntries(names.filter(name => Object.hasOwn(tokens || {}, name))
        .map(name => [name, tokens[name]]));
      if (state === 'known') cache.set(key, {display: extract(row.display),
        units: Object.fromEntries(['credits', 'usd'].map(unit => [unit, extract(row.display_units?.[unit])])),
        value: row[key]});
      else if (state !== 'pending') cache.delete(key);
      const old = cache.get(key);
      if (!old) return row;
      if (state === 'pending') this.retained = true;
      // Display-only observations; raw billing/accounting and source DTOs stay untouched.
      return {...row, [key]: old.value, display: {...row.display, ...old.display},
        display_units: Object.fromEntries(['credits', 'usd'].map(unit =>
          [unit, {...row.display_units?.[unit], ...old.units[unit]}]))};
    }
    project(block, authority) {
      if (!authority?.scope || authority.scope !== this.scope) this.clear();
      this.scope = authority?.scope; this.retained = false;
      const wanted = new Set();
      const rows = block.rows.map(row => {
        const key = JSON.stringify([row.id, row.event_id, row.at_ms]); wanted.add(key);
        const cache = this.mixes.get(key) || new Map(); this.mixes.set(key, cache);
        const state = authority?.rows?.[row.event_id];
        const value = this.select(row, 'token_mix_percent',
          state === 'known' && !validMix(row.token_mix_percent) ? 'unavailable' : state, cache);
        const pending = state === 'pending' ? !cache.has('token_mix_percent') :
          state == null && row.in_progress && !validMix(value.token_mix_percent);
        return {...value, tokenMixPending: pending === true,
          tokenMixAvailable: state !== 'invalidated' && !pending && validMix(value.token_mix_percent)};
      });
      for (const key of this.mixes.keys()) if (!wanted.has(key)) this.mixes.delete(key);
      let result = {...block, rows};
      const pendingTotals = [];
      for (const key of ['total_calls', 'duration_ms', 'total_ccost', 'total_incoming_context_ccost',
        'total_extra_ccost', 'total_token_mix_percent']) {
        const state = authority?.totals?.[key];
        result = this.select(result, key, state, this.totals);
        if (state === 'pending' && !this.totals.has(key)) pendingTotals.push(key);
      }
      return {...result, pendingTotals};
    }
  }
  function protection() {
    const selection = window.getSelection?.();
    const targets = [document.activeElement, ...(selection && !selection.isCollapsed ? [selection.anchorNode, selection.focusNode] : [])].filter(Boolean);
    return node => targets.some(target => node.contains(target));
  }
  function updateModel(node, value) {
    const name = value.watch_model || value.model_effort || 'N/A';
    ReportView.text(node, name + (value.has_model_details ? '*' : ''));
    if (value.linked_agent_count) node.setAttribute('aria-label',
      `${name} · Linked subagents participated (${value.linked_agent_count})`);
    else if (value.has_model_details) node.setAttribute('aria-label',
      `${name} · Multiple models or different effort levels`);
    else node.removeAttribute('aria-label');
  }
  function promptLabel(value) {
    let status = '';
    if (value.execution_unverified) status = '[UNVERIFIED] ';
    else if (value.in_progress) status = '[RUNNING] ';
    else if (value.aborted) status = '[ABORTED] ';
    return `${status}#${value.prompt_number ?? '—'}`;
  }
  function contextChangeHelp(data, index, running) {
    const block = data?.result.view.prompt_blocks[0];
    const current = block?.rows[index];
    if (!current) return 'Context change unavailable.';
    const next = block.rows[index + 1];
    let nextTokens = next?.incoming_context_tokens;
    if (!next) {
      if (block.rows.length !== data.total) return 'Context change pending.';
      const context = block.session_context;
      if (running || current.in_progress || context?.context_state === 'pending') return 'Context change pending.';
      // Older archived detail has the owning prompt but predates the status field.
      if (!context || context.warning?.owner_id !== current.event_id ||
          (context.context_state !== undefined && context.context_state !== 'ready-current'))
        return 'Context change unavailable.';
      nextTokens = context.watch_next_context_tokens;
    }
    if (!Number.isFinite(current.incoming_context_tokens) || !Number.isFinite(nextTokens))
      return 'Context change unavailable.';
    const delta = nextTokens - current.incoming_context_tokens;
    const sign = delta > 0 ? '+' : delta < 0 ? '−' : '';
    return `Estimated context change: ${sign}${tokenCount.format(Math.abs(delta))} tokens`;
  }
  function cells(value, modelValue, mixNode, contextHelp) {
    const label = el('span', undefined, 'session-prompt-label');
    const clock = ContextHelp.value(el('span', value.display?.clock || '—'), value.display?.date_time || 'Start time unavailable');
    const preview = el('span', value.preview || value.label || 'Prompt', 'session-preview');
    ContextHelp.value(preview, value.preview || value.label || 'Prompt');
    label.append(clock, el('span', promptLabel(value), 'session-prompt-state'), preview);
    const cost = ContextHelp.value(el('span', () => ReportView.display(value, 'ccost')),
      () => (value.prompt_number == null ? '' : `Prompt #${value.prompt_number}\n`) +
        ReportView.costGroups(value) + (Number.isFinite(value.duration_ms) ?
          '\n\nDuration: ' + ReportView.display(value, 'duration_ms') : ''));
    const model = ContextHelp.value(el('span'),
       () => ReportView.display(modelValue(), 'model_detail_help'));
    updateModel(model, value);
    const calls = ContextHelp.value(el('span', value.display?.calls ?? String(value.calls ?? 'N/A')),
      () => value.watch_calls_help || 'Model/effort request details unavailable.');
    const effort = el('span', value.watch_effort || 'N/A');
    const mix = mixNode || ContextHelp.value(el('span'),
      'Token percentages use recorded Input / Cached input / Cache write / Output counts. ' +
      'Spinner: acquisition pending. ?: recorded token breakdown unavailable or incomplete; ' +
      'CCost can reflect only the known priced portion. N/A: no nonzero token mix.');
    ReportView.valueSlot(mix, value.tokenMixAvailable ? ReportView.display(value, 'token_mix_percent') :
      value.calls > 0 ? '?' : 'N/A', {pending: value.tokenMixPending, field: 'prompt token mix'});
    const duration = el('span', () => ReportView.display(value, 'duration_ms'));
    const incomingContext = ContextHelp.value(el('span', () =>
      value.display?.first_incoming_context_tokens ?? ReportView.display(value, 'incoming_context_tokens')), contextHelp);
    return [label, model, effort, cost,
       calls, duration,
       incomingContext, ReportView.costValue(value, 'incoming_context_ccost'),
       ReportView.costValue(value, 'extra_ccost'), mix];
  }
  function section(title, className) {
    const root = el('section', undefined, `session-detail-card ${className}`);
    const heading = el('h2', title, 'session-indicator-heading');
    const feedback = el('span');
    heading.append(feedback); root.append(heading);
    return {root, feedback};
  }

  class HistoryViewport {
    constructor(scroll, table) {
      this.scroll = scroll;
      this.table = table;
      this.recordScroll = () => {
        const {scrollTop, scrollHeight, clientHeight} = scroll;
        if (!clientHeight || scrollTop === this.lastTop) return;
        this.lastTop = scrollTop;
        // CSSOM rounds the scroll extent but may report a fractional scrollTop.
        this.followBottom = scrollHeight - clientHeight - scrollTop <= 1;
      };
      this.resize = new ResizeObserver(() => this.layout());
    }
    attach() {
      this.followBottom = true;
      this.layout();
      this.scroll.addEventListener('scroll', this.recordScroll, {passive: true});
      this.resize.observe(this.table);
      this.resize.observe(this.scroll);
    }
    detach() {
      this.resize.disconnect();
      this.scroll.removeEventListener('scroll', this.recordScroll);
    }
    layout() {
      const {scroll, table} = this;
      if (!scroll.clientHeight) return;
      const rows = table.tBodies[0].rows;
      let limit = '';
      if (rows.length > 10) {
        const tenRowsAndHeader = rows[9].getBoundingClientRect().bottom - table.getBoundingClientRect().top;
        const totals = table.tFoot.getBoundingClientRect().height;
        const horizontalScrollbar = scroll.offsetHeight - scroll.clientHeight;
        limit = `${tenRowsAndHeader + totals + horizontalScrollbar}px`;
      }
      if (scroll.style.getPropertyValue('--session-history-max') !== limit)
        scroll.style.setProperty('--session-history-max', limit);
      if (this.followBottom) scroll.scrollTop = scroll.scrollHeight;
      this.lastTop = scroll.scrollTop;
    }
  }

  class View {
    constructor(api, id, live = () => null) {
      Object.assign(this, {api, id, live, token: null, data: null, busy: false, attached: false, generation: 0});
      this.root = el('div', undefined, 'session-detail'); this.root.setAttribute('aria-label', 'Session detail');
      const back = this.back = el('a', '↩ Back to Show All Sessions');
      back.setAttribute('aria-label', 'Back to Show All Sessions');
      this.closeLink = el('a', '×', 'session-close');
      this.closeLink.setAttribute('aria-label', 'Close session detail and return to Sessions');
      this.returnTo('#/sessions');
      const nav = el('div', undefined, 'session-detail-navigation'); nav.append(back, this.closeLink);
      const title = el('h1', undefined, 'session-indicator-heading');
      this.heading = el('span'); this.titleFeedback = el('span');
      title.append(this.heading, this.titleFeedback);
      this.initialSettled = new Set();
      this.exporter = typeof SessionExport === 'undefined' ? null : new SessionExport.Action(api, id);
      this.status = el('p', '', 'warning'); this.status.setAttribute('role', 'status'); this.status.hidden = true;
      this.liveActivityStatus = el('p'); this.liveActivityStatus.setAttribute('role', 'status');
      this.liveActivityStatus.hidden = true;
      this.retry = el('button', 'Try again'); this.retry.type = 'button'; this.retry.hidden = true;
      this.retry.addEventListener('click', () => this.retrySource());
      this.loader = new ReportLoading.View();
      this.loader.bar.setAttribute('aria-label', 'Session loading progress');
      this.loader.status.setAttribute('aria-live', 'polite');
      this.progress = {percent: 0, stage: 'Opening session…', stageLabel: 'Opening session…'};
      this.context = new WatchView.ContextLine();
      this.invocations = new WatchView.LiveInvocations();
      this.activityLimit = 25;
      this.activity = new WatchView.HistoryActivity(() => {
        if (this.busy) return;
        this.activityLimit += 25; this.activity.more.disabled = true;
        this.poll();
      }, {expanded: true});
      this.overview = section('Session overview', 'session-detail-overview');
      const totals = el('dl');
      this.totalNodes = new Map([[3, 'CCost'], [4, 'Calls'], [5, 'Duration'], [9, 'Token Mix %']].map(([index, label]) => {
        const pair = el('div'), value = el('dd');
        pair.append(el('dt', label), value); totals.append(pair);
        return [index, value];
      }));
      this.overview.root.append(totals, this.context.root);
      this.activitySection = section('Tools and Skills', 'session-detail-activity');
      this.activityEmpty = el('p', '', 'detail');
      this.activitySection.root.append(this.invocations.root, this.activity.root, this.activityEmpty);
      this.historySection = section('Prompt history', 'session-detail-history');
      const scroll = el('div', undefined, 'sessions-table-pan session-history-pan');
      this.scroll = scroll;
      scroll.tabIndex = 0; scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', 'Session prompt history');
      const table = el('table', undefined, 'sessions-table session-history-table');
      const head = el('thead'), header = el('tr');
      columns.forEach(([name, help]) => { const th = el('th'); th.scope = 'col'; th.append(ContextHelp.button(name, help)); header.append(th); });
      head.append(header); this.body = el('tbody'); this.footer = el('tr');
      this.activityFeedback = el('tbody');
      this.activityAnnouncement = el('span', '', 'sr-only'); this.activityAnnouncement.setAttribute('role', 'status');
      const foot = el('tfoot'); foot.append(this.footer); table.append(head, this.body, this.activityFeedback, foot); scroll.append(table);
      this.historyViewport = new HistoryViewport(scroll, table);
      this.historySection.root.append(scroll);
      this.values = new Values();
      this.rowIndexes = new Map();
      this.quotaUsage = typeof AccountCards === 'undefined' ? null : new AccountCards.SessionUsage();
      this.root.append(nav, title, el('p', 'Session ID: ' + id), this.activityAnnouncement, this.status,
        this.retry, this.liveActivityStatus, this.loader.root, this.overview.root, this.activitySection.root,
        this.historySection.root);
      if (this.quotaUsage) this.root.append(this.quotaUsage.root);
      if (this.exporter) title.after(this.exporter.root);
      this.loading(); this.freshness();
    }
    returnTo(destination) {
      this.back.href = this.closeLink.href = destination;
    }
    attach(parent) {
      this.freshness();
      if (this.root.parentNode !== parent) parent.replaceChildren(this.root);
      if (this.attached) return;
      this.initialFailed = false; this.readFailures = 0;
      if (!this.data) this.progress = {percent: 0, stage: 'Opening session…'};
      this.historyViewport.attach();
      this.attached = true; this.poll();
    }
    detach() {
      this.exporter?.close();
      this.historyViewport.detach();
      this.attached = false; this.generation++; clearTimeout(this.timer);
      this.flight?.controller.abort(); this.flight = null; this.busy = false;
      this.showActivityFeedback(null);
      this.activity.update(null); this.activityLimit = 25;
      this.invocations.reset();
      if (this.data) this.data.activity = null;
      this.scroll.setAttribute('aria-busy', 'false'); this.loader.root.hidden = true;
      const token = this.token; this.token = null;
      if (token) this.api('/api/detail', {action: 'close', token}).catch(() => {});
    }
    wake(hints) {
      const hint = hints?.find(item => item.session_id === this.id)?.hint;
      if (!hint || hint === this.liveHint || document.hidden) return;
      this.liveHint = hint;
      this.poll();
    }
    catchUp(since = performance.now(), hiddenOrRecovery = true) {
      if (!this.attached || document.hidden) return;
      if (this.retry.disabled) { this.trailing = true; return; }
      if (this.flight) {
        // A provisional open (including the legacy path) keeps its owner.
        // Warm cached readers pin by revision and may supersede a stale flight.
        if (!this.data?.cache_first || !this.token || this.flight.started > since ||
            this.flight.foreground && !hiddenOrRecovery) { this.trailing = true; return; }
        this.generation++;
        this.flight.controller.abort(); this.flight = null; this.busy = false;
      }
      this.initialFailed = false; this.readFailures = 0;
      this.poll(true);
    }
    updateInvocations(data) {
      if (!this.attached) return;
      if (data) this.invocations.observeDetail(data.activity, data.live_activity);
      this.invocations.update(this.live(), this.id);
    }
    async poll(foreground = false) {
      if (!this.attached || this.initialFailed) return;
      if (this.busy) { this.trailing = true; return; }
      clearTimeout(this.timer);
      if (document.hidden) { this.timer = setTimeout(() => this.poll(), 30000); return; }
      this.trailing = false;
      const generation = this.generation;
      this.pendingLoad = this.load(foreground);
      await this.pendingLoad;
      if (generation === this.generation && this.attached && !this.initialFailed) this.timer = setTimeout(() => this.poll(),
        this.trailing ? 0 : this.waiting ? 500 : 5000);
    }
    async retrySource() {
      if (this.retry.disabled || !this.token) return;
      const token = this.token;
      const generation = this.generation;
      this.retry.disabled = true;
      this.readFailures = 0;
      try {
        // A click during a short status read must not be silently discarded.
        await this.pendingLoad;
        if (!this.attached || this.token !== token) return;
        await this.api('/api/detail', {action: 'retry', token});
        if (!this.attached || this.token !== token) return;
        this.initialFailed = false;
        if (!this.data) {
          this.progress = {percent: 0};
          this.loading('Loading session…');
        }
        this.retry.hidden = true; this.waiting = true;
        await this.poll();
      } catch (error) {
        if (this.attached && generation === this.generation) {
          this.readFailed(error);
          if (this.waiting) await this.poll();
        }
      } finally { this.retry.disabled = false; }
    }
    async load(foreground) {
      if (this.busy) return;
      this.busy = true;
      const generation = this.generation;
      const flight = this.flight = {controller: new AbortController(), started: performance.now(), foreground};
      const read = value => this.api('/api/detail', value, flight.controller.signal);
      const current = () => this.attached && generation === this.generation;
      const begin = async () => {
        if (!this.token) {
          this.loading('Opening session…');
          // An issued token belongs to this flight, even if navigation retired it.
          const {token, export_state, export_scope} = await this.api('/api/detail',
            {action: 'open', session_id: this.id, mode: 'live'});
          if (!current()) { this.api('/api/detail', {action: 'close', token}).catch(() => {}); return; }
          this.token = token;
          this.exporter?.update(token, export_state || 'pending', export_scope);
        }
        return read({action: 'begin', token: this.token, offset: 0});
      };
      try {
        let data;
        try { data = await begin(); }
        catch (error) {
          if (!current() || error.message !== 'detail_expired') throw error;
          this.token = null;
          data = await begin();
        }
        if (!current()) return;
        if (data.values_invalidated) {
          this.invalidateValues(); this.sourceStatus(data); return;
        }
        if (data.result && this.values.scope && data.value_authority?.scope !== this.values.scope)
          this.invalidateValues();
        this.syncLiveActivity(data, this.data?.activity?.scope);
        this.updateInvocations(data);
        this.exporter?.update(this.token, data.export_state || 'pending', data.export_scope, data.export_name);
        if (data.result || this.data) this.quotaUsage?.update(data.quota_usage,
          data.quota_state || (data.quota_usage ? 'ready' : 'unavailable'));
        if (!data.result) {
          this.readFailures = 0;
          this.showActivityFeedback(data.activity_refresh || (this.activityFeedbackState && data.acquisition?.reason
            ? 'unavailable' : null));
          this.sourceStatus(data);
          this.loadingFeedback(this.data);
          return;
        }
        if (this.data?.activity?.scope && data.activity?.scope !== this.data.activity.scope) {
          this.activity.update(null); this.activityLimit = 25; this.data.activity = null;
        }
        // Qualification can recover without changing the immutable report.
        // Do not pin a pending footer merely because its raw rows are identical.
        const sameValues = JSON.stringify(this.data?.value_authority?.totals) ===
          JSON.stringify(data.value_authority?.totals) &&
          Object.entries(data.value_authority?.rows || {}).every(([id, state]) =>
            this.data?.value_authority?.rows?.[id] === state);
        if (this.data?.revision === data.revision && sameValues &&
            this.data.result.view.prompt_blocks[0].rows.length === data.total && (this.data.activity?.failures?.length || 0) >=
            Math.min(this.activityLimit, data.activity?.total || 0)) {
          this.showActivityFeedback(data.activity_refresh);
          this.loadingFeedback(data);
          if (this.pendingRender) this.update(this.data); return;
        }
        const initial = this.data?.revision === data.revision && sameValues ?
          this.data.result.view.prompt_blocks[0].rows : data.result.view?.prompt_blocks?.[0]?.rows;
        if (!data.revision || data.offset !== 0 || !Number.isSafeInteger(data.total) || data.total < 0 ||
            !Array.isArray(initial) || initial.length > data.total) throw new Error('inconsistent_history');
        const rows = [...initial], ids = new Set();
        const validate = next => {
          for (const row of next) {
            if (!row.id || ids.has(row.id)) throw new Error('inconsistent_history');
            ids.add(row.id);
          }
        };
        validate(rows);
        if (!this.data) {
          const block = data.result.view.prompt_blocks[0];
          this.update({...data, result: {...data.result, view: {...data.result.view,
             prompt_blocks: [{...block, rows: [...rows]}]}}});
        }
        this.loadingFeedback(data);
        const materialTransfer = this.data?.activity_revision && data.activity_revision &&
          this.data.activity_revision !== data.activity_revision &&
          (rows.length < data.total || (data.activity?.failures?.length || 0) <
            Math.min(this.activityLimit, data.activity?.total || 0));
        this.showActivityFeedback(data.activity_refresh || (materialTransfer ? 'pending' : null));
        this.historyProgress(rows.length, data.total);
        while (rows.length < data.total) {
          const chunk = await read({action: 'chunk', token: this.token,
            offset: rows.length, revision: data.revision, ...(data.cache_first ? {size: 200} : {})});
          if (!this.attached || generation !== this.generation) return;
          const next = chunk.result?.view?.prompt_blocks?.[0]?.rows;
          if (chunk.revision !== data.revision || chunk.total !== data.total || chunk.offset !== rows.length ||
              !Array.isArray(next) || !next.length || rows.length + next.length > data.total) throw new Error('inconsistent_history');
          validate(next);
          if (data.value_authority?.scope !== chunk.value_authority?.scope || chunk.values_invalidated)
            throw new Error('inconsistent_history');
          if (data.value_authority) Object.assign(data.value_authority.rows, chunk.value_authority.rows);
          rows.push(...next);
          this.historyProgress(rows.length, data.total);
          // Yield between bounded chunks without discarding a retained history.
          await new Promise(resolve => setTimeout(resolve, 0));
        }
        if (!this.attached || generation !== this.generation) return;
        data.result.view.prompt_blocks[0].rows = rows;
        this.update({...data, activity: data.activity && {...data.activity, failures: [...data.activity.failures]}});
        this.readFailures = 0;
        this.showActivityFeedback(data.activity_refresh);
        this.sourceStatus(data);
        const failureIds = new Set((data.activity?.failures || []).map(call => call.identity));
        while (data.activity && data.activity.failures.length < Math.min(this.activityLimit, data.activity.total)) {
          const offset = data.activity.failures.length;
          const page = await read({action: 'activity', token: this.token,
            revision: data.revision, offset});
          if (!this.attached || generation !== this.generation) return;
          if (page.revision !== data.revision || page.offset !== offset || page.total !== data.activity.total ||
              !Array.isArray(page.failures) || !page.failures.length ||
              offset + page.failures.length > page.total) throw new Error('inconsistent_activity');
          for (const call of page.failures) {
            if (!call.identity || failureIds.has(call.identity)) throw new Error('inconsistent_activity');
            failureIds.add(call.identity);
          }
          data.activity.failures.push(...page.failures);
        }
        if (data.activity?.failures.length !== this.data.activity?.failures.length) {
          this.data.activity = data.activity;
          this.activity.update(data.activity, data.result.view.timezone_id);
        }
        this.loadingFeedback(data);
      } catch (error) {
        if (this.attached && generation === this.generation) this.readFailed(error);
      } finally {
        if (this.flight === flight) {
          this.flight = null; this.busy = false; this.activity.more.disabled = false;
        }
      }
    }
    readFailed(error) {
      if (error.message === 'detail_expired') this.token = null;
      if (invalidatingFailures.has(error.message)) {
        this.invalidateValues(); this.detach();
      } else if ((restartableReads.has(error.message) || !this.data && error.retryable === true) &&
                 ++this.readFailures <= initialReadRetries) {
        this.initialFailed = false; this.waiting = true; this.retry.hidden = true;
        this.loading('Loading session…');
        return;
      }
      if (this.activityFeedbackState) this.showActivityFeedback('unavailable');
      this.loadingFeedback(this.data, true);
      if (this.data && !this.quotaUsage?.settled) this.quotaUsage?.update(null, 'unavailable');
      this.finishLoading(!this.data);
    }
    finishLoading(failed, retryAvailable = false) {
      this.initialFailed = failed; this.waiting = false; this.retry.hidden = !retryAvailable;
      this.status.textContent = !failed ? '' : retryAvailable
        ? 'Could not load. Try again or return to Sessions.' : 'Could not load. Return to Sessions to try again.';
      this.status.hidden = !failed;
      this.loader.root.hidden = true; this.scroll.setAttribute('aria-busy', 'false');
    }
    showActivityFeedback(state) {
      state = this.data && ['pending', 'unavailable'].includes(state) ? state : null;
      if (state === this.activityFeedbackState) return;
      this.activityFeedbackState = state;
      if (!state) {
        this.activityFeedback.replaceChildren(); this.activityAnnouncement.textContent = '';
        return;
      }
      const text = state === 'pending'
        ? 'Updating session activity… Checking any running prompts.'
        : 'Could not update session activity. Running status may be out of date.';
      if (!this.activityFeedback.firstChild) {
        const row = el('tr', undefined, 'session-activity-feedback');
        const cell = el('td'); cell.colSpan = columns.length; row.append(cell); this.activityFeedback.append(row);
      }
      this.activityFeedback.firstChild.firstChild.textContent = text;
      this.activityAnnouncement.textContent = text;
    }
    sourceStatus(data) {
      this.freshness();
      const acquisition = data.acquisition;
      if (data.values_invalidated) {
        this.invalidateValues(); this.detach();
        this.finishLoading(true);
        return;
      }
      // Retained live history is never a foreground action. Silence includes
      // the live region, Retry tab stop, loader and its reserved geometry.
      if (this.data) {
        this.finishLoading(false);
        return;
      }
      if (acquisition?.phase === 'failed' && !acquisition.retry_scheduled) {
        this.finishLoading(true, acquisition.retry_available);
        return;
      }
      this.retry.hidden = true;
      if (acquisition) {
        this.waiting = true;
        const phase = 'Loading session';
        const percent = Number.isFinite(acquisition.percent) && acquisition.percent >= 0 && acquisition.percent <= 70 ? acquisition.percent : this.progress.percent;
        this.loading(`${phase}…`, percent, phase);
        return;
      }
      if (data.state === 'loading' || data.pending && data.state === 'observed') {
        this.waiting = true;
        this.loading('Loading session…');
        return;
      }
      this.finishLoading(true);
    }
    historyProgress(completed, total) {
      // Source-owned milestones 0–70%; pinned rows 70–95%; applied DOM 100%.
      // Scalar work/time never invent a fraction. Retries retain the proven watermark.
      this.loading(`Loading session history (${completed} of ${total})…`, total ? 70 + 25 * completed / total : 95,
        'Loading session history');
    }
    loading(stage = this.progress.stage, percent = this.progress.percent, stageLabel = stage) {
      if (this.data) return;
      Object.assign(this.progress, {stage, stageLabel, percent: Math.max(this.progress.percent, Math.min(95, Math.floor(percent)))});
      this.loader.update(this.progress);
      this.loader.root.hidden = false; this.status.hidden = true;
      // Busy history must not suppress the sibling loader's polite stage announcements.
      this.scroll.setAttribute('aria-busy', 'true');
    }
    freshness() {
      if (!this.scroll) return;
      for (const part of [this.historySection, this.overview, this.activitySection]) part.root.hidden = !this.data;
      if (this.quotaUsage) this.quotaUsage.root.hidden = !this.data;
    }
    loadingFeedback(data, failed = false) {
      const block = data?.result.view.prompt_blocks[0];
      if (!block) { ReportView.valueSlot(this.titleFeedback, ''); return; }
      const pending = (name, active) => {
        if (!active || failed) this.initialSettled.add(name);
        return !this.initialSettled.has(name);
      };
      const historyIncomplete = block.rows.length < data.total;
      const history = pending('history', historyIncomplete);
      const promptValues = pending('prompt values', historyIncomplete || this.pendingPromptValues);
      const activity = pending('activity', data.activity_refresh === 'pending' ||
        data.activity?.failures.length < Math.min(this.activityLimit, data.activity?.total || 0));
      const metrics = pending('metrics', this.footerBlock?.pendingTotals.length);
      const context = pending('context', block.session_context?.context_state === 'pending');
      const exporting = pending('export', this.exporter?.state === 'pending');
      ReportView.valueSlot(this.historySection.feedback, '', {pending: history, field: 'prompt history'});
      ReportView.valueSlot(this.activitySection.feedback, '', {pending: activity, field: 'tools and skills'});
      ReportView.valueSlot(this.overview.feedback, '', {pending: context, field: 'session context'});
      ReportView.valueSlot(this.titleFeedback, '', {
        pending: history || promptValues || activity || metrics || context || exporting, field: 'session details'
      });
      ReportView.text(this.activityEmpty, data.activity || activity ? '' : 'No recorded tool or skill activity is available.');
    }
    invalidateValues() {
      this.values.clear(); this.costs = null; this.costSource = null; this.data = null;
      this.rowIndexes.clear();
      this.showActivityFeedback(null);
      ContextHelp.dismiss(this.root);
      this.body.replaceChildren(); this.footer.replaceChildren(); this.footerBlock = null;
      for (const total of this.totalNodes.values()) {
        ReportView.valueSlot(total, '');
        ContextHelp.clearValue(total);
      }
      this.initialSettled.clear();
      this.loadingFeedback(null);
      this.context.contextObservation = null; this.context.update(null); this.activity.update(null);
      this.invocations.reset();
      this.syncLiveActivity({});
      this.freshness();
      this.quotaUsage?.update(null);
    }
    update(data) {
      // Read the old scroll extent before new rows can turn a pinned position into an offset.
      this.historyViewport.recordScroll();
      ReportView.defaultUnit();
      const scope = data.value_authority?.scope;
      if (this.values.scope && scope !== this.values.scope) this.invalidateValues();
      if (Object.values(data.value_authority?.rows || {}).includes('invalidated')) this.costs = null;
      // Legacy DTOs have no detail authority, but still carry source provenance.
      // Without either identity, do not qualify cross-observation cost retention.
      const source = scope ? [scope, this.id] : data.result.source?.identity != null ?
        [data.result.source.identity, data.result.source.generation, this.id] : null;
      const costSource = JSON.stringify(source);
      if (!source || costSource !== this.costSource) this.costs = null;
      this.costSource = costSource;
      this.costs ||= new ReportView.CostDisplay();
      const block = this.values.project(data.result.view.prompt_blocks[0], data.value_authority);
      this.pendingPromptValues = block.rows.some(row => row.tokenMixPending);
      this.pendingRender = false;
      const protectedNode = protection();
      ReportView.text(this.heading, block.title || 'Untitled session'); this.context.update(block.session_context);
      this.activity.update(data.activity, data.result.view.timezone_id);
      const old = new Map([...this.body.children].map(row => [row.dataset.id, row]));
      this.rowIndexes = new Map(block.rows.map((row, index) => [row.id, index]));
      let deferOrder = false;
      for (const row of [...this.body.children]) if (!this.rowIndexes.has(row.dataset.id)) {
        if (protectedNode(row)) { this.pendingRender = true; deferOrder = true; }
        else row.remove();
      }
      const initialLength = this.body.children.length, append = [];
      block.rows.forEach((value, index) => {
        value = this.costs.select(value, source && [...source, value.id]);
        const row = old.get(value.id) || el('tr'); row.dataset.id = value.id;
        row.detailValue = value;
        row.className = value.in_progress ? 'session-running' : value.has_error || value.aborted ? 'error' : '';
        const signature = JSON.stringify(value);
        const withdrawn = ['invalidated', 'unavailable'].includes(data.value_authority?.rows?.[value.event_id]);
        const protectedRow = !withdrawn && protectedNode(row);
        row.modelValue = value;
        const model = row.children[1]?.firstChild;
        const selection = window.getSelection?.();
        const selectedModel = selection && !selection.isCollapsed &&
          [selection.anchorNode, selection.focusNode].some(target => target && model?.contains(target));
        if (model && !selectedModel) {
          updateModel(model, value);
          ContextHelp.refresh(model);
        }
        // Unavailable Token Mix is not withdrawn Model identity. In particular,
        // zero-token/scripted requests remain valid stationary help targets.
        if (data.value_authority?.rows?.[value.event_id] === 'invalidated') ContextHelp.dismiss(row);
        if (row.signature !== signature && protectedRow) this.pendingRender = true;
        if (row.signature !== signature && !protectedRow) {
          const content = cells(value, () => row.modelValue, row.children[9]?.firstChild, () =>
            contextChangeHelp(this.data, this.rowIndexes.get(row.dataset.id), row.classList.contains('session-running')));
          content.forEach((item, column) => {
            const td = row.children[column] || el('td');
            // A gesture owns its ancestor chain too: never detach/reparent Model.
            if ((column !== 1 || !model) && td.firstChild !== item)
              td.replaceChildren(item);
            if (!td.parentNode) row.append(td);
          }); row.signature = signature;
        }
        if (deferOrder) { if (!row.parentNode) append.push(row); }
        else if (index >= initialLength) append.push(row);
        else if (this.body.children[index] !== row) this.body.insertBefore(row, this.body.children[index] || null);
      });
      for (let offset = 0; offset < append.length; offset += 200) this.body.append(...append.slice(offset, offset + 200));
      this.updateFooter(block);
      if (!this.data) this.loader.update({percent: 100, stage: 'Session ready', stageLabel: 'Session ready'});
      this.data = data; this.loader.root.hidden = true; this.scroll.setAttribute('aria-busy', 'false');
      this.syncLiveActivity(data);
      this.freshness();
      this.loadingFeedback(data);
      this.historyViewport.layout();
    }
    syncLiveActivity(data, rowScope = data.activity?.scope) {
      const proof = data.live_activity;
      const running = new Set(proof?.running);
      const ended = new Set(proof?.ended);
      for (const row of this.body.children) {
        const value = row.detailValue;
        if (!value) continue;
        const observedRunning = rowScope === proof?.scope && running.delete(value.event_id);
        const observedEnded = rowScope === proof?.scope && ended.has(value.event_id);
        const uncertain = !observedRunning && !observedEnded && value.in_progress &&
          (proof && rowScope === proof.scope || data.running_unverified);
        if (!value.in_progress && !observedRunning && !row.activityOverlaid) continue;
        row.activityOverlaid = observedRunning;
        const display = {...value, in_progress: observedRunning || value.in_progress && !observedEnded && !uncertain,
          execution_unverified: !observedRunning && !observedEnded && (value.execution_unverified || !!uncertain)};
        row.classList.toggle('session-running', !!display.in_progress);
        const label = row.querySelector('.session-prompt-state');
        if (label) ReportView.text(label, promptLabel(display));
      }
      const message = running.size ? 'A prompt is running. Its detail is not available yet.' : '';
      ReportView.text(this.liveActivityStatus, message);
      this.liveActivityStatus.hidden = !message;
      ContextHelp.refresh(this.body);
    }
    updateFooter(block) {
      this.footerBlock = block;
      const value = index => {
        const row = this.footerBlock;
        return ['Complete session', '', '', ReportView.display(row, 'total_ccost'),
          String(row.total_calls ?? 'N/A'), ReportView.display(row, 'duration_ms'), '—',
          ReportView.display(row, 'total_incoming_context_ccost'), ReportView.display(row, 'total_extra_ccost'),
           Array.isArray(row.total_token_mix_percent) ? row.total_token_mix_percent.join('/') :
              row.total_calls > 0 ? '?' : 'N/A'][index];
      };
      for (let index = 0; index < 10; index++) {
        const cell = this.footer.children[index] || el('td'), node = cell.children[0] || el('span');
        const [key, field] = footerMetrics[index] || [];
        ReportView.valueSlot(node, () => value(index), {pending: block.pendingTotals.includes(key), field});
        if (index === 3) ContextHelp.value(node, () => ReportView.display(this.footerBlock, 'session_cost_help') +
          (Number.isFinite(this.footerBlock.duration_ms) ?
             '\n\nDuration: ' + ReportView.display(this.footerBlock, 'duration_ms') : ''));
        if (index === 9) ContextHelp.value(node,
          'Complete-session token mix uses raw recorded counts, not an average of prompt percentages. ' +
          '?: the recorded breakdown is incomplete or has no positive denominator. Spinner: acquisition pending.');
        if (!node.parentNode) cell.append(node);
        if (!cell.parentNode) this.footer.append(cell);
        const total = this.totalNodes.get(index);
        if (total) {
          ReportView.valueSlot(total, () => value(index), {pending: block.pendingTotals.includes(key), field});
          if (index === 3) ContextHelp.value(total, () => ReportView.display(this.footerBlock, 'session_cost_help'));
        }
      }
      ContextHelp.refresh(this.footer);
    }
  }
  return {View};
})();
