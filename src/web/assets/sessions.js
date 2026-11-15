'use strict';
// Server-owned period ordering; older-page epochs never shift under arrivals.
const SessionsCatalog = (() => {
  const el = (...args) => ReportView.element(...args);
  const columns = [
    ['activity', 'Last activity', 'When this session last worked on a prompt.'],
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
      Object.assign(this, {api, token: null, data: null, attached: false, busy: false, generation: 0, navigationSequence: Date.now()});
      this.root = el('div', undefined, 'sessions-catalog'); this.root.setAttribute('aria-label', 'Sessions catalog');
      this.status = el('p', undefined, 'warning'); this.status.setAttribute('role', 'status');
      this.status.setAttribute('aria-atomic', 'false'); this.status.hidden = true;
      this.statusTask = el('span'); this.statusCount = el('span'); this.statusStage = el('span');
      // Counts remain readable in the accessibility tree, without speaking every
      // increment. Only changed task/stage/error text uses the polite live region.
      this.statusCount.setAttribute('aria-live', 'off');
      this.status.append(this.statusTask, this.statusCount, this.statusStage);
      this.periods = el('div', undefined, 'ai-stats-periods sessions-periods');
      this.periods.setAttribute('role', 'group'); this.periods.setAttribute('aria-label', 'Sessions period');
      this.periodButtons = periods.map(([key, label]) => {
        const button = el('button', label); button.type = 'button';
        button.addEventListener('click', () => this.navigateTo(destination(0, null, this.sort, this.direction, key), null, 'period'));
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
          this.navigateTo(destination(0, null, key, direction, this.period), null, 'sort');
        });
        th.append(button); header.append(th); this.headers.push({key, name, th, label});
      }
      head.append(header); this.body = el('tbody'); table.append(head, this.body); pan.append(table);
      const pager = el('div', undefined, 'pager page-navigation');
      this.pan = pan; this.pager = pager;
      this.previous = this.pageButton('Previous'); this.next = this.pageButton('Next'); this.label = el('span');
      this.numbers = el('div', undefined, 'sessions-page-numbers');
      this.numbers.setAttribute('role', 'group'); this.numbers.setAttribute('aria-label', 'Session pages');
      this.pageButtons = new Map();
      for (const button of [this.previous, this.next]) {
        button.disabled = true;
      }
      this.label.setAttribute('aria-live', 'polite'); pager.append(this.previous, this.label, this.numbers, this.next);
      for (const event of ['focusin', 'pointerdown']) document.addEventListener(event, event => {
        if (this.actionFocus && event.target !== this.actionFocus) this.actionFocus = null;
      });
      this.root.append(this.periods, this.status, pan, pager);
    }
    pageButton(label) {
      const button = el('button', label); button.type = 'button';
      button.addEventListener('click', () => {
        if (button.disabled || button.navigationDisabled || !button.destination) return;
        this.navigateTo(button.destination, button, 'page');
      });
      return button;
    }
    navigateTo(target, button = null, kind = null) {
      if (target === location.hash) return;
      this.userAction = {destination: target, button, kind};
      location.hash = target;
    }
    setStatus(message = '') {
      ReportView.text(this.statusTask, message);
      ReportView.text(this.statusCount, ''); ReportView.text(this.statusStage, '');
      this.status.hidden = !message;
    }
    configure(params) {
      const offset = Number(params?.get('offset') || 0), epoch = params?.get('epoch') || null;
      const sort = columns.some(([key]) => key === params?.get('sort')) ? params.get('sort') : 'activity';
      const direction = params?.get('direction') === '1' ? 1 : -1;
      const period = params?.has('period') ? params.get('period') : 'today';
      // Repeated route notifications cannot erase pending intent or a failure.
      if (this.operation && offset === this.offset && epoch === this.epoch &&
        sort === this.sort && direction === this.direction && period === this.period) return;
      const action = this.userAction?.destination === location.hash ? this.userAction : null;
      this.userAction = null;
      if (this.operation?.navigation) this.cancelledNavigation = this.operation.navigation;
      this.actionFocus = null; this.retire();
      this.setStatus();
      Object.assign(this, {offset, epoch, sort, direction, period});
      this.canonicalPeriod = !params?.has('period');
      this.periodSelection();
      const changedPeriod = this.data && period !== this.data.period;
      const changed = this.data && (this.offset !== this.data.offset || this.sort !== this.data.sort ||
        changedPeriod || this.direction !== this.data.direction || this.offset && this.epoch !== this.data.epoch);
      this.operation = changed || !this.data ? {kind: action?.kind || (changedPeriod ? 'period' : this.data && this.sort === this.data.sort &&
        this.direction === this.data.direction ? 'page' : 'sort'),
        userInitiated: Boolean(action), button: action?.button, navigation: action ? ++this.navigationSequence : null,
        restarts: 0,
        pending: false,
        advanced: Date.now(), percent: 0, completed: -1, highWater: -1, source: null, rebases: 0, failed: false} : null;
      this.pan.hidden = this.pager.hidden = false;
      this.retryDelay = 0;
      this.rerun = true;
      if (this.terminal) this.failNavigation(this.terminalReason);
    }
    retire() {
      this.generation++; this.flight?.controller.abort(); this.flight = null; this.busy = false;
      clearTimeout(this.admission); clearTimeout(this.timer);
      clearTimeout(this.requestDeadline);
      if (this.operation) this.operation.pending = false;
      this.pagerBusy(false);
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
    detach() {
      this.attached = false; this.actionFocus = null;
      // The router detaches even for another page in this same catalog.
      if (this.userAction?.destination !== location.hash) this.userAction = null;
      this.interest(false); this.retire();
    }
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
        if (generation === this.generation && this.operation && !this.operation.pending)
          this.showProgress();
      }, 180);
      const deadline = new Promise((_, reject) => {
        this.requestDeadline = setTimeout(() => {
          if (this.flight !== flight) return;
          flight.timedOut = true; flight.controller.abort(); reject(new Error('request_timeout'));
        }, 15000);
      });
      try {
        const request = () => Promise.race([this.api('/api/sessions', {token: this.token, offset: this.offset,
          epoch: this.epoch, sort: this.sort, direction: this.direction, period: this.period,
          navigation: this.operation?.navigation || null, applied: this.appliedNavigation || null,
          cancelled: this.cancelledNavigation || null}, flight.controller.signal), deadline]);
        let data;
        try { data = await request(); }
        catch (error) {
          if (error.message !== 'catalog_expired' || !this.attached || generation !== this.generation) throw error;
          if (this.operation && this.operation.restarts++ >= 1) {
            this.failNavigation('navigation_invalidated'); return;
          }
          // No proof that a new lease has the old membership: safely return to
          // latest, preserving sort intent. One reopen per poll, never a loop.
          this.interest(false);
          this.token = null; this.appliedNavigation = null; this.epoch = null; this.offset = 0; this.recovering = true;
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
        else this.setStatus();
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
    showProgress(message = '') {
      if (!this.operation) return;
      const operation = this.operation;
      operation.pending = !operation.failed;
      if (!operation.userInitiated) { this.setStatus(); this.pagerBusy(); return; }
      const name = columns.find(([key]) => key === this.sort)[1];
      const task = operation.kind === 'period' ? `Loading sessions in ${periods.find(([key]) => key === this.period)?.[1] || this.period}` :
        operation.kind === 'page' ? `Loading Sessions page ${Math.floor(this.offset / 25) + 1}` : `Sorting sessions by ${name}`;
      ReportView.text(this.statusTask, task);
      const count = operation.count;
      ReportView.text(this.statusCount, !operation.failed && !message && count ?
        ` · ${count.completed.toLocaleString('en-US')} of ${count.total.toLocaleString('en-US')} sessions` : '');
      ReportView.text(this.statusStage, message ? `. ${message}` : count ? '' : '…');
      this.status.hidden = false;
      this.pagerBusy();
    }
    failNavigation(reason) {
      if (!this.operation) return;
      this.terminal = true; this.terminalReason = reason;
      this.operation.failed = true;
      this.operation.pending = false;
      this.interest(false);
      const message = ['authentication_required', 'http_auth_failure', 'permission_denied', 'csrf_required'].includes(reason) ?
        'Check your access, then reopen Sessions.' :
        'Could not load. Reopen Sessions to try again.';
      if (this.operation.userInitiated) this.showProgress(message);
      else { this.setStatus(); this.pagerBusy(); }
    }
    waitNavigation(reason) {
      this.retryDelay = Math.min(30000, (this.retryDelay || 500) * 2);
      if (this.operation?.userInitiated && Date.now() - this.operation.advanced >= 90000)
        this.failNavigation(reason);
      else if (this.operation?.userInitiated) this.showProgress();
      else this.setStatus();
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
      operation.count = Number.isSafeInteger(progress?.completed) && Number.isSafeInteger(progress?.total) &&
        progress.completed >= 0 && progress.total > 0 && progress.completed <= progress.total &&
        ['index', 'page'].includes(progress.phase) ?
        {completed: progress.completed, total: progress.total, phase: progress.phase} : null;
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
      this.showProgress();
      return true;
    }
    update(data) {
      if (data.navigation != null && data.navigation !== this.operation?.navigation) return;
      if (!this.operation && data.progress?.status === 'failed' && data.progress.retryable !== true) {
        this.terminal = true; this.terminalReason = data.progress.reason || 'source_unavailable';
        this.interest(false);
        this.setStatus();
        return;
      }
      // Even a deferred sort/outage must retire unsupported running indicators.
      const observed = new Map(data.view.session_usage.map(value => [value.session_id, value]));
      for (const row of this.body.children) {
        const running = data.state === 'observed' && Boolean(observed.get(row.dataset.id)?.running);
        row.className = running ? 'session-running' : '';
        if (row.runningMarker) ReportView.text(row.runningMarker, running ? '[RUNNING] ' : '');
      }
      // A requested candidate-scope sort is not applied until every eligible key is valid. Keep
      // the previous actual order, header and pager rather than relabeling it.
      if (this.pendingNavigation(data) || data.pending_sort) {
        if (!this.operation) this.setStatus();
        // A pending page is not applied: keep the last qualified rows with their
        // actual pager/order. Only cold entry has no valid page to retain.
        if (data.state === 'observed' && !this.data) {
          this.renderTimezone = data.view.timezone_id; this.rows(data.view.session_usage);
        }
        return;
      }
      const values = data.view.session_usage;
      const changedPage = this.recovering && (this.body.children.length !== values.length ||
        values.some((value, index) => this.body.children[index].dataset.id !== value.session_id));
      const completed = this.operation;
      this.pan.hidden = this.pager.hidden = false;
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
      this.setStatus();
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
      if (completed) ContextHelp.refresh(this.root);
      const pages = Math.max(1, Math.ceil(data.total / data.size));
      this.label.textContent = data.total ? `Showing ${data.offset + 1}–${Math.min(data.offset + data.size, data.total)} of ${data.total} sessions · Page ${Math.floor(data.offset / data.size) + 1} of ${pages}` :
        data.state === 'observed' ? `No confirmed matches among catalog candidates in ${periods.find(([key]) => key === data.period)?.[1] || data.period} · Page 1 of 1` : 'Session count unavailable';
      const link = (node, offset, enabled) => {
        node.destination = enabled ? destination(offset, data.epoch, data.sort, data.direction, data.period) : null;
      };
      link(this.previous, Math.max(0, data.offset - data.size), data.offset > 0);
      link(this.next, data.offset + data.size, data.offset + data.size < data.total);
      this.numberedPages(data);
      // Release the cohort only after its matching table and pager were applied.
      // The next existing poll acknowledges it; no extra timer or acquisition lane.
      if (completed?.navigation) this.appliedNavigation = completed.navigation;
      this.operation = null; clearTimeout(this.admission);
      this.pagerBusy();
    }
    numberedPages(data) {
      const pages = Math.max(1, Math.ceil(data.total / data.size)), current = Math.floor(data.offset / data.size) + 1;
      const wanted = [...new Set([1, 2, current - 1, current, current + 1, pages])]
        .filter(page => page >= 1 && page <= pages).sort((a, b) => a - b);
      const nodes = [];
      for (const page of wanted) {
        let button = this.pageButtons.get(page);
        if (!button) {
          button = this.pageButton(String(page));
          button.setAttribute('aria-label', `Page ${page}`);
          this.pageButtons.set(page, button);
        }
        button.destination = page !== current && (data.state === 'observed' || data.total > 0) ?
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
    pagerBusy(restoreFocus = true) {
      const navigating = Boolean(this.operation?.userInitiated && this.operation.pending && !this.operation.failed);
      const buttons = [this.previous, this.next, ...this.pageButtons.values()];
      if (navigating && buttons.includes(document.activeElement)) this.actionFocus = document.activeElement;
      for (const button of buttons) {
        const disabled = navigating || this.recovering || !button.destination;
        if (disabled && document.activeElement === button) this.actionFocus = button;
        // Keep the initiating button focusable but inert while its target loads.
        // Other unavailable controls use native disabled semantics.
        const initiating = navigating && this.operation.kind === 'page' && this.operation.button === button;
        button.navigationDisabled = Boolean(disabled);
        if (initiating) {
          button.setAttribute('aria-disabled', 'true');
        } else {
          button.removeAttribute('aria-disabled');
        }
        const nativeDisabled = Boolean(disabled && !initiating);
        if (button.disabled !== nativeDisabled) button.disabled = nativeDisabled;
      }
      this.pan.setAttribute('aria-busy', String(navigating));
      if (restoreFocus && !navigating && !this.busy && this.actionFocus) {
        if (document.activeElement === document.body || document.activeElement === this.actionFocus) {
          const target = !this.actionFocus.disabled && this.pager.contains(this.actionFocus) ? this.actionFocus :
            buttons.find(button => !button.disabled);
          (target || this.pan).focus?.({preventScroll: true});
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
            if (key === 'duration') return node;
            ContextHelp.value(node, () => {
               const current = row.value;
              if (key === 'ccost') return ReportView.sessionCostHelp(current, current);
               if (key === 'ctx') return current.context_tokens == null ? '' : `~${current.context_tokens.toLocaleString()} tokens`;
               if (key !== 'model') return '';
                return ReportView.display(current, 'model_help');
            });
            return node;
          });
          const cells = [row.activity, row.name, ...row.metrics];
          row.replaceChildren(...cells.map(content => { const td = el('td'); td.append(typeof content === 'object' ? content : el('span', content)); return td; }));
        }
        row.className = value.running ? 'session-running' : '';
        ReportView.text(row.activity, value.last_activity_ms == null && value.activity_state === 'pending' ?
          'Loading…' : ReportView.timestamp(value.last_activity_ms, this.renderTimezone));
        ReportView.text(row.titleNode, value.title);
        ReportView.text(row.runningMarker, value.running ? '[RUNNING] ' : '');
        const texts = [(value.model || 'N/A') + (value.has_model_details ? '*' : ''),
          () => ReportView.display(value, 'ccost'), value.prompt_count == null ? 'N/A' : String(value.prompt_count),
          () => ReportView.display(value, 'duration_ms'), () => ReportView.display(value, 'context_tokens')];
        row.metrics.forEach((node, index) => {
          const key = ['model', 'ccost', 'prompts', 'duration', 'ctx'][index];
          const state = value.metric_states?.[key] || value.metric_state || (value.indexed ? 'ready' : 'pending');
          const missing = ((!value.has_summary && !value.indexed && state !== 'retained') ||
            (key === 'model' && state === 'pending' && (!value.model || value.model === 'N/A')) ||
            (key === 'ctx' && state === 'pending' && value.context_tokens == null));
          ReportView.text(node, missing ? state === 'pending' ? 'Loading…' : 'Unavailable' : texts[index]);
          node.className = (key === 'duration' ? '' : 'help-value') +
            (missing || key === 'ctx' && state !== 'ready' ? ' session-metric-pending' : '');
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
