'use strict';
// Complete document-scrolling history, assembled from one pinned source revision.
const SessionDetail = (() => {
  const el = (...args) => ReportView.element(...args);
  const columns = [
    ['Prompt', 'Local start time, prompt number and preview. [RUNNING] requires observed ongoing work.'],
    ['Model', ReportView.headerHelp.model],
    ['Effort', 'Reasoning effort requested for the main prompt.'],
    ['CCost', 'Reference cost of this prompt, including linked work; not your bill.'],
    ['Calls', ReportView.headerHelp.calls],
    ['Duration', ReportView.headerHelp.duration],
    ['Ictx', 'Context on the first request of this prompt, not the next session context. N/A is unknown.'],
    ['Ictx CCost', 'Reference incoming-context cost component. Estimates and unavailable evidence retain their canonical meaning.'],
    ['Extra CCost', 'Other reference cost: output, later requests and linked subagents.'],
    ['Token Mix %', 'Token percentages in Input / Cached input / Cache write / Output order. Output includes reasoning. Not cost.']
  ];
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
        const valid = Array.isArray(row.token_mix_percent) && row.token_mix_percent.length === 4 &&
          row.token_mix_percent.every(value => Number.isFinite(value) && value >= 0);
        const state = authority?.rows?.[row.event_id];
        let value = this.select(row, 'token_mix_percent', state === 'known' && !valid ? 'unavailable' : state, cache);
        if (!Array.isArray(value.token_mix_percent) || value.token_mix_percent.length !== 4 ||
            state === 'pending' && !cache.has('token_mix_percent')) {
          const token = state !== 'invalidated' && (row.in_progress || state === 'pending') ? 'Loading…' :
            row.calls > 0 ? '?' : 'N/A';
          value = {...value, display: {...value.display, token_mix_percent: token},
            display_units: Object.fromEntries(['credits', 'usd'].map(unit =>
              [unit, {...value.display_units?.[unit], token_mix_percent: token}]))};
        }
        return value;
      });
      for (const key of this.mixes.keys()) if (!wanted.has(key)) this.mixes.delete(key);
      let result = {...block, rows};
      for (const key of ['total_calls', 'duration_ms', 'total_ccost', 'total_incoming_context_ccost',
        'total_extra_ccost', 'total_token_mix_percent']) {
        result = this.select(result, key, authority?.totals?.[key], this.totals);
        if (authority?.totals?.[key] === 'pending' && !this.totals.has(key) &&
            !['total_incoming_context_ccost', 'total_extra_ccost'].includes(key)) {
          result = {...result, [key]: 'Loading…', display: {...result.display, [key]: 'Loading…'},
            display_units: Object.fromEntries(['credits', 'usd'].map(unit =>
              [unit, {...result.display_units?.[unit], [key]: 'Loading…'}]))};
        }
      }
      return result;
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
  function cells(value, modelValue = () => value) {
    const label = el('span', undefined, 'session-prompt-label');
    const clock = ContextHelp.value(el('span', value.display?.clock || '—'), value.display?.date_time || 'Start time unavailable');
    const preview = el('span', value.preview || value.label || 'Prompt', 'session-preview');
    ContextHelp.value(preview, value.preview || value.label || 'Prompt');
    label.append(clock, el('span', `${value.execution_unverified ? '[UNVERIFIED] ' : value.in_progress ? '[RUNNING] ' : ''}#${value.prompt_number ?? '—'}`), preview);
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
    return [label, model, effort, cost,
      calls, ReportView.display(value, 'duration_ms'),
      firstContext(value), ReportView.costValue(value, 'incoming_context_ccost'),
       ReportView.costValue(value, 'extra_ccost'), ContextHelp.value(
         el('span', ReportView.display(value, 'token_mix_percent')),
         'Token percentages use recorded Input / Cached input / Cache write / Output counts. ' +
         'Loading…: acquisition pending. ?: recorded token breakdown unavailable or incomplete; ' +
         'CCost can reflect only the known priced portion. N/A: no nonzero token mix.')];
  }
  class View {
    constructor(api, id, live = () => null) {
      Object.assign(this, {api, id, live, token: null, data: null, busy: false, attached: false, generation: 0});
      this.root = el('div', undefined, 'session-detail'); this.root.setAttribute('aria-label', 'Session detail');
      const back = this.back = el('a', '↩ Back to Show All Sessions'); back.href = '#/sessions';
      back.setAttribute('aria-label', 'Back to Show All Sessions');
      this.heading = el('h1');
      this.exporter = typeof SessionExport === 'undefined' ? null : new SessionExport.Action(api, id);
      this.status = el('p', '', 'warning'); this.status.setAttribute('role', 'status'); this.status.hidden = true;
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
      });
      const scroll = el('div', undefined, 'sessions-table-pan');
      this.scroll = scroll;
      scroll.tabIndex = 0; scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', 'Session prompt history');
      const table = el('table', undefined, 'sessions-table session-history-table');
      const head = el('thead'), header = el('tr');
      columns.forEach(([name, help]) => { const th = el('th'); th.scope = 'col'; th.append(ContextHelp.button(name, help)); header.append(th); });
      head.append(header); this.body = el('tbody'); this.footer = el('tr');
      this.activityFeedback = el('tbody');
      this.activityAnnouncement = el('span', '', 'sr-only'); this.activityAnnouncement.setAttribute('role', 'status');
      const foot = el('tfoot'); foot.append(this.footer); table.append(head, this.body, this.activityFeedback, foot); scroll.append(table);
      this.values = new Values();
      this.quotaUsage = typeof AccountCards === 'undefined' ? null : new AccountCards.SessionUsage();
      this.root.append(back, this.heading, el('p', 'Session ID: ' + id), this.activityAnnouncement, this.status,
        this.retry, this.loader.root, scroll, this.context.root, this.invocations.root, this.activity.root);
      if (this.quotaUsage) this.root.append(this.quotaUsage.root);
      if (this.exporter) this.heading.after(this.exporter.root);
      this.loading(); this.freshness();
    }
    attach(parent) {
      this.freshness();
      if (this.root.parentNode !== parent) parent.replaceChildren(this.root);
      if (this.attached) return;
      this.attached = true; this.poll();
    }
    detach() {
      this.exporter?.close();
      this.attached = false; this.generation++; clearTimeout(this.timer);
      this.showActivityFeedback(null);
      this.activity.update(null); this.activityLimit = 25;
      this.invocations.update(null);
      if (this.data) this.data.activity = null;
      this.scroll.setAttribute('aria-busy', 'false'); this.loader.root.hidden = true;
      const token = this.token; this.token = null;
      if (token) this.api('/api/detail', {action: 'close', token}).catch(() => {});
    }
    wake(hints) {
      const hint = hints?.find(item => item.session_id === this.id)?.hint;
      if (!hint || hint === this.liveHint) return;
      this.liveHint = hint;
      if (!document.hidden) this.poll();
    }
    catchUp() {
      if (!this.attached || document.hidden) return;
      this.revalidate = true; this.poll();
    }
    updateInvocations(data = this.data) {
      this.invocations.update(this.attached ? this.live() : null, this.id, data?.activity?.invocation_scope);
    }
    async poll() {
      if (!this.attached) return;
      if (this.busy) { this.trailing = true; return; }
      clearTimeout(this.timer);
      if (document.hidden) { this.timer = setTimeout(() => this.poll(), 30000); return; }
      this.trailing = false;
      const generation = this.generation;
      this.pendingLoad = this.load();
      await this.pendingLoad;
      if (this.attached) this.timer = setTimeout(() => this.poll(),
        this.trailing || generation !== this.generation ? 0 : this.waiting ? 500 : 5000);
    }
    async retrySource() {
      if (this.retry.disabled || !this.token) return;
      const token = this.token;
      this.retry.disabled = true;
      try {
        // A click during a short status read must not be silently discarded.
        await this.pendingLoad;
        if (!this.attached || this.token !== token) return;
        await this.api('/api/detail', {action: 'retry', token});
        if (!this.attached || this.token !== token) return;
        if (!this.data) this.progress = {percent: 0, stage: 'Queued for session source…'};
        this.retry.hidden = true; this.waiting = true;
        await this.poll();
      } catch (error) {
        this.status.textContent = this.data ? '' : 'Could not load. Return to Sessions to try again.';
        this.status.hidden = !this.status.textContent;
      } finally { this.retry.disabled = false; }
    }
    async load() {
      if (this.busy) return;
      this.busy = true;
      const generation = this.generation;
      try {
        if (!this.token && !this.data) this.progress = {percent: 0, stage: 'Opening session…'};
        if (!this.token) this.loading('Opening session…');
        if (!this.token) {
          const opened = (await this.api('/api/detail', {action: 'open', session_id: this.id, mode: 'live'})).token;
          if (!this.attached || generation !== this.generation) { this.api('/api/detail', {action: 'close', token: opened}).catch(() => {}); return; }
          this.token = opened;
        }
        if (this.revalidate) {
          this.revalidate = false;
          await this.api('/api/detail', {action: 'wake', token: this.token});
          if (!this.attached || generation !== this.generation) return;
        }
        let data = await this.api('/api/detail', {action: 'begin', token: this.token, offset: 0});
        if (!this.attached || generation !== this.generation) return;
        if (data.values_invalidated) {
          this.invalidateValues(); this.sourceStatus(data); return;
        }
        if (data.result && this.values.scope && data.value_authority?.scope !== this.values.scope)
          this.invalidateValues();
        this.exporter?.update(this.token, data.export_available === true, data.result?.view?.prompt_blocks?.[0]?.title);
        if (!data.result) {
          this.showActivityFeedback(data.activity_refresh || (this.activityFeedbackState && data.acquisition?.reason
            ? 'unavailable' : null));
          this.sourceStatus(data);
          return;
        }
        this.sourceStatus(data);
        // Pending quota publication is not observed nonuse. Host/source
        // invalidation above still retires the entire retained projection.
        if (data.quota_usage) this.quotaUsage?.update(data.quota_usage);
        if (this.data?.activity?.scope && data.activity?.scope !== this.data.activity.scope) {
          this.activity.update(null); this.activityLimit = 25; this.data.activity = null;
        }
        // Qualification can recover without changing the immutable report.
        // Do not pin a pending footer merely because its raw rows are identical.
        const sameValues = JSON.stringify(this.data?.value_authority?.totals) ===
          JSON.stringify(data.value_authority?.totals) &&
          Object.entries(data.value_authority?.rows || {}).every(([id, state]) =>
            this.data?.value_authority?.rows?.[id] === state);
        if (this.data?.revision === data.revision && sameValues && (this.data.activity?.failures?.length || 0) >=
            Math.min(this.activityLimit, data.activity?.total || 0)) {
          this.showActivityFeedback(data.activity_refresh);
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
        const materialTransfer = this.data?.activity_revision && data.activity_revision &&
          this.data.activity_revision !== data.activity_revision &&
          (rows.length < data.total || (data.activity?.failures?.length || 0) <
            Math.min(this.activityLimit, data.activity?.total || 0));
        this.showActivityFeedback(data.activity_refresh || (materialTransfer ? 'pending' : null));
        this.historyProgress(rows.length, data.total);
        while (rows.length < data.total) {
          const chunk = await this.api('/api/detail', {action: 'chunk', token: this.token,
            offset: rows.length, revision: data.revision});
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
        const failureIds = new Set((data.activity?.failures || []).map(call => call.identity));
        while (data.activity && data.activity.failures.length < Math.min(this.activityLimit, data.activity.total)) {
          const offset = data.activity.failures.length;
          const page = await this.api('/api/detail', {action: 'activity', token: this.token,
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
        this.loading('Preparing session…');
        this.update(data);
        this.showActivityFeedback(data.activity_refresh);
        this.sourceStatus(data);
      } catch (error) {
        if (!this.attached || generation !== this.generation) return;
        this.waiting = false;
        if (this.activityFeedbackState) this.showActivityFeedback('unavailable');
        this.status.textContent = this.data ? '' : 'Could not load. Return to Sessions to try again.';
        this.retry.hidden = true;
        this.status.hidden = !this.status.textContent;
        this.loader.root.hidden = true; this.scroll.setAttribute('aria-busy', 'false');
        if (error.message === 'detail_expired') {
          this.token = null; this.exporter?.close(); this.activity.update(null);
          if (this.data) this.data.activity = null;
        }
        if (['instance_stopping', 'authentication_required', 'host_identity_changed', 'csrf_required',
            'permission_denied', 'http_auth_failure', 'source_identity_changed', 'session_missing'].includes(error.message)) {
          this.invalidateValues(); this.detach();
        }
      } finally { this.busy = false; this.activity.more.disabled = false; }
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
        this.waiting = false; this.retry.hidden = true;
        this.status.textContent = 'Could not load. Return to Sessions to try again.';
        this.status.hidden = false;
        return;
      }
      this.waiting = !this.data && !data.result && acquisition?.phase !== 'failed';
      this.retry.hidden = Boolean(this.data) || !acquisition?.retry_available;
      // Retained live history is never a foreground action. Silence includes
      // the live region, Retry tab stop, loader and its reserved geometry.
      if (this.data && !data.values_invalidated) {
        this.status.textContent = ''; this.status.hidden = true;
        this.retry.hidden = true; this.loader.root.hidden = true;
        this.scroll.setAttribute('aria-busy', 'false');
        return;
      }
      if (acquisition?.phase === 'failed') {
        if (['source_identity_changed', 'session_missing'].includes(acquisition.reason)) {
          this.activity.update(null); if (this.data) this.data.activity = null;
        }
        this.status.textContent = 'Could not load. Try again or return to Sessions.';
        this.status.hidden = false; this.loader.root.hidden = true; this.scroll.setAttribute('aria-busy', 'false');
        return;
      }
      if (!data.result && acquisition) {
        const phase = 'Loading session';
        const percent = Number.isFinite(acquisition.percent) && acquisition.percent >= 0 && acquisition.percent <= 70 ? acquisition.percent : this.progress.percent;
        this.loading(`${phase}…`, percent, phase);
        return;
      }
      if (data.state === 'loading' || data.pending && data.state === 'observed') {
        if (!this.data) this.loading('Loading session…');
        // Passive work is silent; a pending observation cannot clear a real fault.
        return;
      }
      this.status.textContent = data.result ? '' : 'Could not load. Return to Sessions to try again.';
      this.status.hidden = !this.status.textContent;
      if (!data.result && !this.data) { this.loader.root.hidden = true; this.scroll.setAttribute('aria-busy', 'false'); }
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
      this.scroll.hidden = !this.data;
      this.context.root.hidden = !this.data;
    }
    invalidateValues() {
      this.values.clear(); this.costs = null; this.costSource = null; this.data = null;
      this.showActivityFeedback(null);
      ContextHelp.dismiss(this.root);
      this.body.replaceChildren(); this.footer.replaceChildren(); this.footerBlock = null;
      this.context.contextObservation = null; this.context.update(null); this.activity.update(null);
      this.invocations.update(null);
      this.exporter?.close(); this.freshness();
      this.quotaUsage?.update(null);
    }
    update(data) {
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
      this.pendingRender = false;
      const protectedNode = protection();
      ReportView.text(this.heading, block.title || 'Untitled session'); this.context.update(block.session_context);
      this.activity.update(data.activity, data.result.view.timezone_id);
      this.updateInvocations(data);
      const old = new Map([...this.body.children].map(row => [row.dataset.id, row]));
      const wanted = new Set(block.rows.map(row => row.id));
      const anchor = [...this.body.children].find(row => row.getBoundingClientRect().bottom > 0);
      const top = anchor?.getBoundingClientRect().top;
      let deferOrder = false;
      for (const row of [...this.body.children]) if (!wanted.has(row.dataset.id)) {
        if (protectedNode(row)) { this.pendingRender = true; deferOrder = true; }
        else row.remove();
      }
      const initialLength = this.body.children.length, append = [];
      block.rows.forEach((value, index) => {
        value = this.costs.select(value, source && [...source, value.id]);
        const row = old.get(value.id) || el('tr'); row.dataset.id = value.id;
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
          const content = cells(value, () => row.modelValue);
          content.forEach((item, column) => {
            const td = row.children[column] || el('td');
            // A gesture owns its ancestor chain too: never detach/reparent Model.
            if (column !== 1 || !model)
              td.replaceChildren(typeof item === 'object' ? item : el('span', () => cellsText(value, column)));
            if (!td.parentNode) row.append(td);
          }); row.signature = signature;
        }
        if (deferOrder) { if (!row.parentNode) append.push(row); }
        else if (index >= initialLength) append.push(row);
        else if (this.body.children[index] !== row) this.body.insertBefore(row, this.body.children[index] || null);
      });
      for (let offset = 0; offset < append.length; offset += 200) this.body.append(...append.slice(offset, offset + 200));
      this.updateFooter(block, data.value_authority);
      if (anchor?.isConnected && top != null) {
        const delta = anchor.getBoundingClientRect().top - top;
        if (delta) window.scrollBy(0, delta);
      }
      if (!this.data) this.loader.update({percent: 100, stage: 'Session ready', stageLabel: 'Session ready'});
      this.data = data; this.loader.root.hidden = true; this.scroll.setAttribute('aria-busy', 'false');
      this.freshness();
    }
    updateFooter(block, authority) {
      this.footerBlock = block;
      const value = index => {
        const row = this.footerBlock;
        return ['Complete session', '', '', ReportView.display(row, 'total_ccost'),
          String(row.total_calls ?? 'N/A'), ReportView.display(row, 'duration_ms'), '—',
          ReportView.display(row, 'total_incoming_context_ccost'), ReportView.display(row, 'total_extra_ccost'),
          Array.isArray(row.total_token_mix_percent) ? row.total_token_mix_percent.join('/') :
             row.total_token_mix_percent === 'Loading…' ? 'Loading…' : row.total_calls > 0 ? '?' : 'N/A'][index];
      };
      for (let index = 0; index < 10; index++) {
        const cell = this.footer.children[index] || el('td'), node = cell.children[0] || el('span');
        ReportView.text(node, () => index === 3 && authority?.totals?.total_ccost === 'pending' &&
          !this.values.totals.has('total_ccost') ? 'Loading…' : value(index));
        if (index === 3) ContextHelp.value(node, () => ReportView.display(this.footerBlock, 'session_cost_help') +
          (Number.isFinite(this.footerBlock.duration_ms) ?
             '\n\nDuration: ' + ReportView.display(this.footerBlock, 'duration_ms') : ''));
        if (index === 9) ContextHelp.value(node,
          'Complete-session token mix uses raw recorded counts, not an average of prompt percentages. ' +
          '?: the recorded breakdown is incomplete or has no positive denominator. Loading…: acquisition pending.');
        if (!node.parentNode) cell.append(node);
        if (!cell.parentNode) this.footer.append(cell);
      }
      ContextHelp.refresh(this.footer);
    }
  }
  class CachedView {
    constructor(api, id, hint) {
      Object.assign(this, {api, id, hint, offset: 0, data: null, attached: false, dirty: true});
      this.root = el('section', undefined, 'session-detail session-detail-cache');
      this.root.setAttribute('aria-label', 'Session detail');
      this.back = el('a', '↩ Back to Show All Sessions'); this.back.href = '#/sessions';
      this.heading = el('h1', 'Session detail');
      this.exporter = typeof SessionExport === 'undefined' ? null : new SessionExport.Action(api, id, true);
      this.summary = el('p'); this.status = el('p');
      this.status.setAttribute('role', 'status');
      const table = el('table'), head = el('thead'), header = el('tr');
      for (const [label, help] of columns) {
        const cell = el('th', label);
        cell.scope = 'col'; ContextHelp.attach(cell, help); header.append(cell);
      }
      this.body = el('tbody'); head.append(header); table.append(head, this.body);
      this.table = el('div', undefined, 'session-scroll'); this.table.append(table);
      this.pager = el('div', undefined, 'page-navigation');
      this.previous = this.pageButton('Previous', -1); this.next = this.pageButton('Next', 1);
      this.range = el('span'); this.pager.append(this.previous, this.range, this.next);
      this.root.append(this.back, this.heading, this.summary, this.status, this.table, this.pager);
      if (this.exporter) this.heading.after(this.exporter.root);
      this.resumePaint = () => queueMicrotask(() => {
        if (this.attached && this.pendingRender && this.data) this.paint(this.data);
      });
      this.root.addEventListener('focusout', this.resumePaint);
      this.reset('No cached detail yet.');
    }
    pageButton(label, delta) {
      const button = el('button', label);
      button.type = 'button';
      button.addEventListener('click', () => {
        if (!this.data || button.disabled) return;
        this.offset = Math.max(0, this.offset + this.data.size * delta);
        this.retire(); this.catchUp();
      });
      return button;
    }
    attach(parent) {
      if (this.root.parentNode !== parent) parent.replaceChildren(this.root);
      if (!this.attached) {
        this.attached = true; document.addEventListener('selectionchange', this.resumePaint); this.catchUp();
      }
    }
    detach() {
      this.attached = false; this.retire(); this.exporter?.close(); this.demanded = null;
      document.removeEventListener('selectionchange', this.resumePaint);
    }
    retire() {
      this.flight?.abort(); this.flight = null;
      clearTimeout(this.timer); this.timer = null;
    }
    reset(message) {
      this.data = null; this.pendingRender = false; this.heading.textContent = 'Session detail';
      this.exporter?.close();
      ReportView.text(this.summary, ''); ReportView.text(this.status, message); this.range.textContent = '';
      ContextHelp.dismiss(this.body); this.body.replaceChildren();
      this.previous.disabled = this.next.disabled = true;
    }
    invalidateValues() { this.retire(); this.hint = null; this.demanded = null; this.reset('Session cache unavailable.'); }
    updateInvocations() {} // Committed history cannot assert active invocation state.
    wake() {} // Source signals never supply facts to the cache-only view.
    cacheHint(hint, resync = false) {
      if (hint?.view !== 'sessions') return;
      const bindingChanged = hint.binding !== this.hint?.binding;
      if (!bindingChanged && !resync && this.hint.generation >= hint.generation) return;
      this.hint = hint;
      if (!hint.binding || bindingChanged && this.data && this.data.binding !== hint.binding) this.invalidateValues();
      if (hint.binding) { this.hint = hint; this.dirty = true; this.schedule(); }
    }
    schedule() {
      if (this.attached && !document.hidden && !this.flight && !this.timer) {
        this.timer = setTimeout(() => { this.timer = null; if (this.dirty) this.read(); }, 50);
      }
    }
    catchUp() { this.dirty = true; this.read(); }
    async read() {
      if (!this.attached || document.hidden || this.flight) return;
      this.dirty = false;
      const hint = this.hint, flight = new AbortController();
      this.flight = flight;
      try {
        const data = await this.api('/api/cache/session-detail', {session_id: this.id, offset: this.offset}, flight.signal);
        if (this.flight !== flight) return;
        if (this.hint !== hint && this.hint?.binding !== data.binding) return;
        if (this.hint?.binding === data.binding && this.hint?.generation > data.generation) {
          this.dirty = true;
          return;
        }
        this.paint(data);
      } catch (_) {
        if (this.flight === flight) this.reset('Session cache unavailable.');
      } finally {
        if (this.flight === flight) {
          this.flight = null;
          if (this.dirty) this.schedule();
        }
      }
    }
    paint(data) {
      const summary = data.summary, previous = this.data;
      this.data = data;
      this.exporter?.update(data.binding, data.export_supported === true, summary?.title);
      if (['pending', 'retained'].includes(data.history_coverage) && summary?.source_present !== false &&
          data.binding && this.demanded !== data.binding) {
        this.demanded = data.binding;
        this.api('/api/cache/session-detail/demand', {binding: data.binding, session_id: this.id}).catch(() => {});
      }
      if (!this.pendingRender && previous?.binding === data.binding && previous.generation === data.generation &&
          previous.offset === data.offset) return;
      this.pendingRender = false;
      ReportView.text(this.heading, summary?.title || 'Session detail');
      ReportView.text(this.summary, () => summary ?
        `Total CCost: ${ReportView.display(summary, 'ccost')} · Ctx: ${ReportView.display(summary, 'context_tokens')}` : '');
      if (summary?.context_detail) ContextHelp.value(this.summary, summary.context_detail);
      else ContextHelp.clearValue(this.summary);
      const archived = summary?.source_present === false;
      this.status.textContent = archived ? 'Saved history; the original source session is unavailable.' :
        !data.cached_total ? (data.history_coverage === 'as-of' ? 'No cached prompts for this session.' : 'No cached detail yet.') : '';
      const old = new Map([...this.body.children].map(row => [row.dataset.id, row]));
      const wanted = new Set(data.rows.map(row => row.event_id));
      const protectedNode = protection();
      let deferOrder = false;
      for (const [id, row] of old) if (!wanted.has(id)) {
        if (protectedNode(row)) { this.pendingRender = true; deferOrder = true; }
        else { ContextHelp.dismiss(row); row.remove(); }
      }
      data.rows.forEach((value, index) => {
        const row = old.get(value.event_id) || el('tr');
        row.dataset.id = value.event_id;
        const signature = JSON.stringify(value);
        if (row.signature !== signature && protectedNode(row)) this.pendingRender = true;
        else if (row.signature !== signature) {
          const detail = {...value, prompt_number: value.number, watch_model: value.model, watch_effort: value.effort,
            label: value.kind === 'compaction' ? 'Compaction' : value.kind === 'subtask' ? 'Subtask' : 'Prompt',
            in_progress: false, execution_unverified: value.outcome === 'unverified'};
          row.replaceChildren(...cells(detail).map(item => {
            const cell = el('td'); cell.append(typeof item === 'object' ? item : el('span', item)); return cell;
          }));
          row.signature = signature;
        }
        if (deferOrder) {
          if (!row.parentNode) this.body.append(row);
        } else if (this.body.children[index] !== row) {
          const before = this.body.children[index] || null;
          if (row.parentNode && this.body.moveBefore) this.body.moveBefore(row, before);
          else if (!protectedNode(row)) this.body.insertBefore(row, before);
          else this.pendingRender = true;
        }
      });
      this.range.textContent = data.rows.length ? `${data.offset + 1}–${data.offset + data.rows.length} of ${data.cached_total} cached events` : '';
      this.previous.disabled = data.offset === 0;
      this.next.disabled = data.offset + data.size >= data.cached_total;
    }
  }
  // Unit bindings must not manufacture new tooltip DOM for unchanged text cells.
  function firstContext(row) {
    return row.display?.first_incoming_context_tokens ?? ReportView.display(row, 'incoming_context_tokens');
  }
  function cellsText(row, index) {
    return [null, row.watch_model || 'N/A', row.watch_effort || 'N/A', null,
      row.display?.calls ?? String(row.calls ?? 'N/A'), ReportView.display(row, 'duration_ms'), firstContext(row),
      ...['incoming_context_ccost', 'extra_ccost', 'token_mix_percent'].map(key => ReportView.display(row, key))][index];
  }
  return {View, CachedView};
})();
