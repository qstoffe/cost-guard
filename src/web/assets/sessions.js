'use strict';
// Server-owned period ordering; older-page epochs never shift under arrivals.
const SessionsCatalog = (() => {
  const el = (...args) => ReportView.element(...args);
  const columns = [
    ['activity', 'Last activity', 'The most recent recorded activity in this session.'],
    ['name', 'Session name', 'The session title. Open the name for its complete live prompt history.'],
    ['model', 'Model', ReportView.headerHelp.model],
    ['ccost', 'CCost', ReportView.headerHelp.sessionCost],
    ['prompts', 'Prompts', 'Number of prompts in the entire session.'],
    ['duration', 'Duration', 'Execution duration, excluding idle gaps. Sort uses milliseconds.'],
    ['ctx', 'Ctx', ReportView.headerHelp.context]
  ];
  const periods = [['today', 'Today'], ['7-days', '7 days'], ['30-days', '30 days'], ['month', 'This month'], ['all', 'All time']];
  function protectedNode(node) {
    const selected = window.getSelection?.();
    return node.contains(document.activeElement) || Boolean(selected && !selected.isCollapsed &&
      (node.contains(selected.anchorNode) || node.contains(selected.focusNode)));
  }
  function destination(offset, epoch, sort, direction, period) {
    const params = new URLSearchParams({period, sort, direction: String(direction)});
    if (offset) { params.set('offset', String(offset)); params.set('epoch', epoch); }
    return '#/sessions?' + params;
  }
  class View {
    constructor(api) {
      Object.assign(this, {api, token: null, data: null, attached: false, busy: false, generation: 0});
      this.root = el('div', undefined, 'sessions-catalog'); this.root.setAttribute('aria-label', 'Sessions catalog');
      this.status = el('p', 'Loading sessions…', 'warning'); this.status.setAttribute('role', 'status');
      this.periods = el('div', undefined, 'ai-stats-periods sessions-periods');
      this.periods.setAttribute('role', 'group'); this.periods.setAttribute('aria-label', 'Sessions period');
      this.periodButtons = periods.map(([key, label]) => {
        const button = el('button', label); button.type = 'button';
        button.addEventListener('click', () => { location.hash = destination(0, null, this.sort, this.direction, key); });
        this.periods.append(button); return {key, button};
      });
      const pan = el('div', undefined, 'sessions-table-pan'); pan.tabIndex = 0;
      pan.setAttribute('role', 'region'); pan.setAttribute('aria-label', 'Sessions');
      const table = el('table', undefined, 'sessions-table session-catalog-table');
      const head = el('thead'), header = el('tr'); this.headers = [];
      for (const [key, name, help] of columns) {
        const th = el('th'), button = el('button', name); th.scope = 'col';
        const label = ContextHelp.heading(button, help, key === 'ctx');
        button.addEventListener('click', () => {
          const direction = this.sort === key ? -this.direction : key === 'activity' ? -1 : 1;
          location.hash = destination(0, null, key, direction, this.period);
        });
        th.append(button); header.append(th); this.headers.push({key, name, th, label});
      }
      head.append(header); this.body = el('tbody'); table.append(head, this.body); pan.append(table);
      const pager = el('div', undefined, 'pager page-navigation');
      this.pan = pan; this.pager = pager;
      this.previous = el('button', 'Previous'); this.next = el('button', 'Next'); this.label = el('span');
      this.numbers = el('div', undefined, 'sessions-page-numbers');
      this.numbers.setAttribute('role', 'group'); this.numbers.setAttribute('aria-label', 'Session pages');
      this.pageButtons = new Map();
      for (const button of [this.previous, this.next]) {
        button.type = 'button'; button.disabled = true;
        button.addEventListener('click', () => { if (!button.disabled && button.destination) location.hash = button.destination; });
      }
      this.label.setAttribute('aria-live', 'polite'); pager.append(this.previous, this.label, this.numbers, this.next);
      for (const event of ['focusin', 'pointerdown']) document.addEventListener(event, event => {
        if (this.actionFocus && event.target !== this.actionFocus) this.actionFocus = null;
      });
      this.root.append(this.periods, this.status, pan, pager);
      this.loader = new ReportLoading.View(); this.loader.root.hidden = true;
      this.loader.bar.setAttribute('aria-label', 'Sessions loading progress');
      this.task = el('p', '', 'sessions-loading-task');
      this.count = el('p', '', 'sessions-loading-count');
      this.loader.root.insertBefore(this.task, this.loader.bar);
      const track = el('div', undefined, 'sessions-loading-track');
      track.append(this.loader.bar, this.loader.percent);
      this.loader.root.insertBefore(track, this.loader.stage);
      this.loader.root.insertBefore(this.count, this.loader.stage);
      this.cancel = el('button', 'Cancel');
      this.cancel.type = 'button';
      ContextHelp.attach(this.cancel, () => this.operation?.kind === 'page' ?
        'Cancel loading this page and return to the previous page.' :
        this.operation?.kind === 'period' ? 'Cancel loading this period and return to the previous period.' :
        'Cancel this sort and return to the previous sorting and page.');
      this.cancel.addEventListener('click', () => this.cancelNavigation());
      const actions = el('div', undefined, 'sessions-loading-actions'); actions.append(this.cancel);
      this.loader.root.append(actions); this.root.append(this.loader.root);
    }
    configure(params) {
      const offset = Number(params?.get('offset') || 0), epoch = params?.get('epoch') || null;
      const sort = columns.some(([key]) => key === params?.get('sort')) ? params.get('sort') : 'activity';
      const direction = params?.get('direction') === '1' ? 1 : -1;
      const period = params?.has('period') ? params.get('period') : 'today';
      // Repeated route notifications cannot impersonate Cancel or erase a failure.
      if (this.operation && offset === this.offset && epoch === this.epoch &&
        sort === this.sort && direction === this.direction && period === this.period) return;
      this.retire();
      const focus = this.operation?.focus || document.activeElement;
      const scroll = this.operation?.scroll || [window.scrollX || 0, window.scrollY || 0, this.pan.scrollLeft || 0];
      Object.assign(this, {offset, epoch, sort, direction, period});
      this.canonicalPeriod = !params?.has('period');
      this.periodSelection();
      const changedPeriod = this.data && period !== this.data.period;
      const changed = this.data && (this.offset !== this.data.offset || this.sort !== this.data.sort ||
        changedPeriod || this.direction !== this.data.direction || this.offset && this.epoch !== this.data.epoch);
      this.operation = changed || !this.data ? {kind: changedPeriod ? 'period' : this.data && this.sort === this.data.sort &&
        this.direction === this.data.direction ? 'page' : 'sort', focus, scroll,
        advanced: Date.now(), percent: 0, completed: -1, highWater: -1, source: null, rebases: 0, failed: false} : null;
      this.loader.root.hidden = true; this.pan.hidden = this.pager.hidden = false;
      this.retryDelay = 0;
      this.rerun = true;
      if (this.terminal) this.failNavigation(this.terminalReason);
    }
    retire() {
      this.generation++; this.flight?.controller.abort(); this.flight = null; this.busy = false;
      clearTimeout(this.admission); clearTimeout(this.timer);
      clearTimeout(this.requestDeadline);
    }
    periodSelection() {
      for (const {key, button} of this.periodButtons) button.setAttribute('aria-pressed', String(key === this.period));
    }
    rememberedDestination() { return destination(this.offset || 0, this.epoch || this.data?.epoch, this.sort || 'activity', this.direction || -1, this.period || 'today'); }
    attach(parent) {
      if (this.root.parentNode !== parent) parent.replaceChildren(this.root);
      if (this.attached) return;
      this.attached = true; this.poll();
    }
    interest(visible = this.attached && !document.hidden, token = this.token) {
      if (token) this.api('/api/sessions', {action: 'interest', token, visible}).catch(() => {});
    }
    detach() { this.attached = false; this.interest(false); this.retire(); }
    async poll() {
      if (!this.attached || this.busy || this.terminal || this.operation?.failed) return;
      clearTimeout(this.timer);
      if (document.hidden) { this.timer = setTimeout(() => this.poll(), 30000); return; }
      const generation = this.generation;
      await this.load();
      if (generation === this.generation && this.attached && !this.terminal && !this.operation?.failed)
        this.timer = setTimeout(() => this.poll(), this.retryDelay || (this.rerun ? 0 : this.operation ? 1000 : 5000));
    }
    async load() {
      if (this.busy || this.terminal) return;
      this.busy = true; this.rerun = false;
      this.pagerBusy();
      const generation = this.generation;
      const flight = {controller: new AbortController()}; this.flight = flight;
      if (this.operation) this.admission = setTimeout(() => {
        if (generation === this.generation && this.operation && this.loader.root.hidden)
          this.showProgress('Waiting for Sessions source…');
      }, 180);
      const deadline = new Promise((_, reject) => {
        this.requestDeadline = setTimeout(() => {
          if (this.flight !== flight) return;
          flight.timedOut = true; flight.controller.abort(); reject(new Error('request_timeout'));
        }, 15000);
      });
      try {
        const request = () => Promise.race([this.api('/api/sessions', {token: this.token, offset: this.offset,
          epoch: this.epoch, sort: this.sort, direction: this.direction, period: this.period}, flight.controller.signal), deadline]);
        let data;
        try { data = await request(); }
        catch (error) {
          if (error.message !== 'catalog_expired' || !this.attached || generation !== this.generation) throw error;
          // No proof that a new lease has the old membership: safely return to
          // latest, preserving sort intent. One reopen per poll, never a loop.
          this.interest(false);
          this.token = null; this.epoch = null; this.offset = 0; this.recovering = true;
          data = await request();
        }
        if (!this.attached || generation !== this.generation) {
          if (data.token !== this.token || !this.attached || this.operation?.failed) this.interest(false, data.token);
          else if (!document.hidden) this.api('/api/sessions', {token: this.token, offset: this.offset,
            epoch: this.epoch, sort: this.sort, direction: this.direction, period: this.period}).catch(() => {});
          return;
        }
        if (data.period !== this.period || !data.pending_sort &&
          (data.sort !== this.sort || data.direction !== this.direction || data.offset !== this.offset)) {
          throw new Error('catalog_response_mismatch');
        }
        const opened = this.token !== data.token;
        this.token = data.token;
        if (data.state === 'observed' && !data.progress?.reason) this.retryDelay = 0;
        this.update(data);
        if (opened) this.interest();
      } catch (error) {
        if (!this.attached || generation !== this.generation) return;
        const terminal = ['authentication_required', 'csrf_required', 'host_identity_changed', 'instance_stopping',
          'permission_denied', 'invalid_request', 'catalog_response_mismatch', 'unsupported_schema',
          'http_auth_failure', 'invalid_data'].includes(error.message) ||
          error.retryable === false && !['catalog_busy', 'request_unavailable', 'source_unavailable'].includes(error.message);
        if (terminal) {
          this.terminal = true; this.terminalReason = error.message; this.interest(false);
        }
        if (this.operation) {
          if (terminal) this.failNavigation(error.message);
          else this.waitNavigation(flight.timedOut ? 'request_timeout' : error.message);
        }
        else this.status.textContent = `Sessions unavailable (${error.message}). Retaining the last observed page.`;
        if (error.message === 'catalog_expired') {
          this.token = null; this.epoch = null; this.offset = 0; this.recovering = true;
        }
        this.status.hidden = !this.status.textContent;
      } finally {
        if (this.flight === flight) {
          clearTimeout(this.admission); clearTimeout(this.requestDeadline);
          this.flight = null; this.busy = false; this.pagerBusy();
        }
      }
    }
    showProgress(stage, stageLabel = 'Loading Sessions') {
      if (!this.operation) return;
      const operation = this.operation;
      const name = columns.find(([key]) => key === this.sort)[1];
      const task = operation.kind === 'period' ? `Loading sessions in ${periods.find(([key]) => key === this.period)?.[1] || this.period}` :
        operation.kind === 'page' ? `Loading Sessions page ${Math.floor(this.offset / 25) + 1}` : `Sorting sessions by ${name}`;
      ReportView.text(this.task, task);
      this.task.setAttribute('aria-label', task + (operation.kind === 'sort' ? this.direction === 1 ? ', ascending' : ', descending' : ''));
      ReportView.text(this.count, operation.completed < 0 ? 'Waiting for source counts…' :
        `${operation.phase === 'index' ? 'Indexed' : 'Prepared'} ${operation.completed.toLocaleString('en-US')} of ${operation.total.toLocaleString('en-US')} sessions`);
      this.loader.update({percent: this.operation.percent, stage, stageLabel});
      this.loader.root.hidden = false;
      ReportView.text(this.status, `${task}. ${this.count.textContent} ${stage}`);
      this.status.hidden = false;
      if (this.pan.contains(document.activeElement) || this.pager.contains(document.activeElement) ||
        this.actionFocus && document.activeElement === document.body) this.cancel.focus?.({preventScroll: true});
      this.pagerBusy();
    }
    failNavigation(reason) {
      if (!this.operation) return;
      this.terminal = true; this.terminalReason = reason;
      this.operation.failed = true;
      this.interest(false);
      this.showProgress(`Could not finish (${reason}). Reopen Cost Guard after resolving the error, or Cancel to return to the previous view.`, `Sessions navigation failed: ${reason}`);
    }
    waitNavigation(reason) {
      this.retryDelay = Math.min(30000, (this.retryDelay || 500) * 2);
      this.showProgress(`Source temporarily unavailable (${reason}). Recovering automatically…`, 'Waiting for Sessions source');
    }
    pendingNavigation(data) {
      if (!this.operation) return false;
      const progress = data.progress;
      const pagePending = this.operation.kind !== 'sort' && progress && progress.completed < progress.total;
      if (!data.pending_sort && !pagePending && data.state === 'observed' &&
        progress?.status !== 'failed' && !progress?.reason) return false;
      const operation = this.operation;
      const completed = progress?.completed ?? data.indexed ?? 0;
      const total = progress?.total ?? data.available ?? 0;
      const phase = progress?.phase ?? (data.pending_sort ? 'index' : 'page');
      const scope = `${phase}:${total}`;
      const restarted = operation.source !== null && (scope !== operation.scope || completed < operation.completed);
      if (restarted) operation.rebases++;
      // Source generations include unrelated metadata/activity updates. Coverage
      // already excludes changed keys; neither those ticks nor a lower count prove
      // forward work or justify abandoning valid unchanged keys.
      if (operation.scope !== scope) operation.highWater = -1;
      if (completed > operation.highWater) { operation.highWater = completed; operation.advanced = Date.now(); }
      Object.assign(operation, {completed, total, phase, scope, source: progress?.generation ?? ''});
      operation.percent = Math.min(99, total ? Math.floor(99 * completed / total) : 0);
      if (progress?.status === 'failed' && progress.retryable !== true) {
        this.failNavigation(progress?.reason || 'source_unavailable'); return true;
      }
      if (data.state === 'source_unavailable' || progress?.reason) {
        this.waitNavigation(progress?.reason || 'source_unavailable'); return true;
      }
      // A currently owned single-root read retains the source's transport bounds.
      // Do not label it an idle stall merely because no whole root has finished yet.
      if (Date.now() - operation.advanced >= 45000 && !progress?.work?.active) {
        this.waitNavigation('no_source_progress'); return true;
      }
      const stages = {checking_cache: 'Checking cached session summaries…', reading_summary: 'Reading session summary…',
        projecting_summary: 'Preparing session summary…', waiting_retry: 'Waiting to retry a session summary…',
        queued: 'Waiting for the session index worker…', ready: 'Applying requested view…'};
      const revalidating = restarted || progress?.revalidating > 0;
      const stage = stages[progress?.work?.stage] || 'Waiting for session sort keys…';
      this.showProgress(`${revalidating ? 'Source changed; revalidating keys. ' : ''}${progress?.work?.retrying ? 'Retrying. ' : ''}${stage}`,
        revalidating ? 'Revalidating Sessions keys' : progress?.waiting ? 'Waiting for Sessions source' :
          phase === 'index' ? 'Indexing Sessions' : 'Preparing Sessions page');
      return true;
    }
    cancelNavigation() {
      const operation = this.operation;
      if (!operation) return;
      this.retire(); this.interest(false); this.operation = null;
      if (this.data) {
        this.offset = this.data.offset; this.epoch = this.data.epoch;
        this.sort = this.data.sort; this.direction = this.data.direction;
        this.period = this.data.period;
        this.rows(this.data.view.session_usage);
      } else { this.offset = 0; this.epoch = null; this.sort = 'activity'; this.direction = -1; }
      this.periodSelection();
      history.replaceState(null, '', this.rememberedDestination());
      this.loader.root.hidden = true; this.pan.hidden = this.pager.hidden = false; this.pagerBusy();
      this.renderTimezone = this.data?.view.timezone_id;
      operation.focus?.focus?.({preventScroll: true});
      if (operation.scroll) { window.scrollTo?.(operation.scroll[0], operation.scroll[1]); this.pan.scrollLeft = operation.scroll[2]; }
      // Reassert only the restored lease demand. Shared caches/index work survive.
      this.poll();
    }
    update(data) {
      // Even a deferred sort/outage must retire unsupported running indicators.
      const observed = new Map(data.view.session_usage.map(value => [value.session_id, value]));
      for (const row of this.body.children) {
        const running = data.state === 'observed' && Boolean(observed.get(row.dataset.id)?.running);
        row.className = running ? 'session-running' : '';
        if (row.runningMarker) ReportView.text(row.runningMarker, running ? '[RUNNING] ' : '');
      }
      // A requested scoped sort is not applied until every eligible key is valid. Keep
      // the previous actual order, header and pager rather than relabeling it.
      if (this.pendingNavigation(data) || data.pending_sort) {
        if (data.pending_sort && !this.operation) {
          this.status.textContent = 'Provisional Last activity order; requested global sort is still indexing.';
          this.status.hidden = false;
        }
        // Qualified metadata may render while independent scalars are acquired.
        // An expensive pending sort keeps the last valid order explicitly visible.
        if (data.state === 'observed' && (!data.pending_sort && this.operation?.kind === 'page' || !this.data)) {
          this.renderTimezone = data.view.timezone_id; this.rows(data.view.session_usage);
        }
        return;
      }
      const values = data.view.session_usage;
      const changedPage = this.recovering && (this.body.children.length !== values.length ||
        values.some((value, index) => this.body.children[index].dataset.id !== value.session_id));
      const completed = this.operation;
      const restoreFocus = completed && this.loader.root.contains(document.activeElement);
      this.operation = null; clearTimeout(this.admission);
      this.loader.root.hidden = true; this.pan.hidden = this.pager.hidden = false;
      this.data = data;
      this.renderTimezone = data.view.timezone_id;
      this.usable = data.state === 'observed' || data.view.session_usage.length > 0;
      this.offset = data.offset;
      if (data.epoch) this.epoch = data.epoch;
      if (this.recovering || this.canonicalPeriod) {
        history.replaceState(null, '', destination(data.offset, data.epoch, this.sort, this.direction, this.period));
        this.recovering = false;
        this.canonicalPeriod = false;
      }
      // A safely applied replacement completes recovery, not a lasting warning.
      this.status.textContent = data.state !== 'observed' && !data.view.session_usage.length ? 'Loading sessions…' : '';
      this.status.hidden = !this.status.textContent;
      for (const {key, name, th, label} of this.headers) {
        const active = key === data.sort;
        th.setAttribute('aria-sort', active ? data.direction === 1 ? 'ascending' : 'descending' : 'none');
        ReportView.text(label, name + (active ? data.direction === 1 ? ' ↑' : ' ↓' : ''));
      }
      // Lifecycle status must not remain falsely running while a title is selected.
      // A recovered epoch cannot keep protected old rows under a new page label.
      if ((completed || changedPage) && protectedNode(this.body)) {
        window.getSelection?.()?.removeAllRanges?.();
        if (this.body.contains(document.activeElement)) document.activeElement.blur?.();
      }
      this.rows(values);
      if (completed && !restoreFocus) ContextHelp.refresh(this.root);
      if (restoreFocus) this.actionFocus = completed.focus;
      const pages = Math.max(1, Math.ceil(data.total / data.size));
      this.label.textContent = data.total ? `Showing ${data.offset + 1}–${Math.min(data.offset + data.size, data.total)} of ${data.total} sessions · Page ${Math.floor(data.offset / data.size) + 1} of ${pages}` :
        data.state === 'observed' ? `No sessions in ${periods.find(([key]) => key === data.period)?.[1] || data.period} · Page 1 of 1` : 'Session count unavailable';
      const link = (node, offset, enabled) => {
        node.destination = enabled ? destination(offset, data.epoch, data.sort, data.direction, data.period) : null;
      };
      link(this.previous, Math.max(0, data.offset - data.size), data.offset > 0);
      link(this.next, data.offset + data.size, data.offset + data.size < data.total);
      this.numberedPages(data);
      this.pagerBusy();
      if (completed) this.loader.update({percent: 100, stage: 'Page applied', stageLabel: 'Page applied'});
    }
    numberedPages(data) {
      const pages = Math.max(1, Math.ceil(data.total / data.size)), current = Math.floor(data.offset / data.size) + 1;
      const wanted = [...new Set([1, 2, current - 1, current, current + 1, pages])]
        .filter(page => page >= 1 && page <= pages).sort((a, b) => a - b);
      const nodes = [];
      for (const page of wanted) {
        let button = this.pageButtons.get(page);
        if (!button) {
          button = el('button', String(page)); button.type = 'button';
          button.setAttribute('aria-label', `Page ${page}`);
          button.addEventListener('click', () => { if (!button.disabled && button.destination) location.hash = button.destination; });
          this.pageButtons.set(page, button);
        }
        button.destination = data.state === 'observed' || data.total > 0 ?
          destination((page - 1) * data.size, data.epoch, data.sort, data.direction, data.period) : null;
        if (page === current) button.setAttribute('aria-current', 'page');
        else button.removeAttribute('aria-current');
        if (nodes.length && page > Number(nodes.at(-1).textContent) + 1) nodes.push(el('span', '…', 'page-gap'));
        nodes.push(button);
      }
      for (const node of [...this.numbers.children]) if (!nodes.includes(node)) node.remove();
      nodes.forEach((node, index) => {
        if (this.numbers.children[index] !== node) this.numbers.insertBefore(node, this.numbers.children[index] || null);
      });
      for (const [page, button] of this.pageButtons) if (!nodes.includes(button)) this.pageButtons.delete(page);
    }
    pagerBusy() {
      const navigating = Boolean(this.operation && !this.loader.root.hidden);
      const buttons = [this.previous, this.next, ...this.pageButtons.values()];
      if (navigating && buttons.includes(document.activeElement)) this.actionFocus = document.activeElement;
      for (const button of buttons) {
        const disabled = navigating || this.recovering || !button.destination;
        if (disabled && document.activeElement === button) this.actionFocus = button;
        if (button.disabled !== Boolean(disabled)) button.disabled = Boolean(disabled);
      }
      if (!navigating && !this.busy && this.actionFocus) {
        if (document.activeElement === document.body || document.activeElement === this.actionFocus ||
          this.loader.root.contains(document.activeElement)) {
          (this.actionFocus.disabled ? this.actionFocus === this.next ? this.previous : this.next : this.actionFocus).focus({preventScroll: true});
        }
        this.actionFocus = null;
      }
    }
    rows(values) {
      this.costs ||= new ReportView.CostDisplay();
      const old = new Map([...this.body.children].map(row => [row.dataset.id, row]));
      const wanted = new Set(values.map(row => row.session_id));
      const keepOrder = protectedNode(this.body);
      for (const row of [...this.body.children]) if (!wanted.has(row.dataset.id) && !protectedNode(row)) row.remove();
      values.forEach((value, index) => {
        value = this.costs.select(value, [this.data?.source?.identity, this.data?.source?.generation, value.session_id]);
        const row = old.get(value.session_id) || el('tr'); row.dataset.id = value.session_id;
        row.value = value;
        if (!row.name) {
          row.activity = el('span'); row.name = el('a', undefined, 'session-name');
          row.runningMarker = el('span'); row.titleNode = el('span');
          row.name.append(row.runningMarker, row.titleNode);
          if (/^[A-Za-z0-9_-]{1,200}$/.test(value.session_id)) row.name.href = '#/sessions/' + value.session_id;
          ContextHelp.value(row.name, () => row.value.title);
          ContextHelp.value(row.activity, () => ReportView.activityHelp(row.value.last_activity_ms, this.renderTimezone));
          row.metrics = ['model', 'ccost', 'prompts', 'duration', 'ctx'].map(key => {
            const node = el('span');
            ContextHelp.value(node, () => {
              const current = row.value, state = current.metric_states?.[key] || current.metric_state || 'ready';
              if (key === 'ccost' && !current.has_summary && !current.indexed && state !== 'retained')
                return state === 'pending' ? 'Session cost is awaiting source observation.' : 'Session cost unavailable.';
              if (key === 'ccost') return ReportView.sessionCostHelp(current, current) +
                (state === 'retained' ? '\nRetained source observation; refresh pending.' : '');
              if (key === 'ctx') return [current.context_tokens == null ? '' : `${current.context_tokens.toLocaleString()} estimated tokens.`,
                current.context_detail, state === 'retained' ? 'Retained from an earlier source observation; refresh pending.' :
                  state === 'pending' ? 'Source work is pending.' : state === 'unavailable' ? 'Source context unavailable.' : ''].filter(Boolean).join('\n');
              if (key !== 'model') return state === 'ready' ? '' : 'Session metric is retained or pending source observation.';
              return [ReportView.display(current, 'model_help'), state === 'ready' ? '' :
                'Retained or pending source observation; contributing model coverage may be incomplete.'].filter(Boolean).join('\n');
            });
            return node;
          });
          const cells = [row.activity, row.name, ...row.metrics];
          row.replaceChildren(...cells.map(content => { const td = el('td'); td.append(typeof content === 'object' ? content : el('span', content)); return td; }));
        }
        row.className = value.running ? 'session-running' : '';
        ReportView.text(row.activity, ReportView.timestamp(value.last_activity_ms, this.renderTimezone));
        ReportView.text(row.titleNode, value.title);
        ReportView.text(row.runningMarker, value.running ? '[RUNNING] ' : '');
        const texts = [(value.model || 'N/A') + (value.multiple_models && value.model && value.model !== 'N/A' ? '*' : ''),
          () => ReportView.display(value, 'ccost'), value.prompt_count == null ? 'N/A' : String(value.prompt_count),
          () => ReportView.display(value, 'duration_ms'), () => ReportView.display(value, 'context_tokens')];
        row.metrics.forEach((node, index) => {
          const key = ['model', 'ccost', 'prompts', 'duration', 'ctx'][index];
          const state = value.metric_states?.[key] || value.metric_state || (value.indexed ? 'ready' : 'pending');
          const missing = ((!value.has_summary && !value.indexed && state !== 'retained') ||
            (key === 'model' && state === 'pending' && (!value.model || value.model === 'N/A')) ||
            (key === 'ctx' && state === 'pending' && value.context_tokens == null));
          ReportView.text(node, missing ? state === 'pending' ? 'Loading…' : 'Unavailable' : texts[index]);
          node.className = 'help-value' + (missing || key === 'ctx' && state !== 'ready' ? ' session-metric-pending' : '');
          if (key === 'ctx' && state === 'retained') node.setAttribute('aria-label', `Retained context: ${node.textContent}`);
          else node.removeAttribute('aria-label');
          if (missing && state === 'pending') node.setAttribute('aria-busy', 'true');
          else node.removeAttribute('aria-busy');
        });
        ContextHelp.refresh(row);
        if (!keepOrder && this.body.children[index] !== row) this.body.insertBefore(row, this.body.children[index] || null);
        else if (!row.parentNode) this.body.append(row);
      });
    }
  }
  return {View};
})();
