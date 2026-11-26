'use strict';
// Server-owned period ordering; a pager destination names an issued slice.
const SessionsCatalog = (() => {
  const el = (...args) => ReportView.element(...args);
  const columns = [
    ['activity', 'Last activity', 'Prompt start while running; supported finish time afterward. A star offers details. Running sessions appear first, regardless of sorting.'],
    ['name', 'Session name', 'The session title. Open the name for its complete live prompt history.'],
    ['model', 'Model', ReportView.headerHelp.model],
    ['ccost', 'CCost', ReportView.headerHelp.sessionCost],
    ['prompts', 'Prompts', 'Number of prompts in the entire session.'],
    ['duration', 'Duration', 'Execution duration, excluding idle gaps. Sort uses milliseconds.'],
    ['ctx', 'Ctx', ReportView.headerHelp.context]
  ];
  const periods = [['today', 'Today'], ['7-days', '7 days'], ['30-days', '30 days'], ['month', 'This month'], ['all', 'All time']];
  const sharedRecovery = new Set(['authentication_required', 'csrf_required', 'host_identity_changed', 'instance_stopping']);
  function protectedNode(node) {
    const selected = window.getSelection?.();
    return node.contains(document.activeElement) || Boolean(selected && !selected.isCollapsed &&
      (node.contains(selected.anchorNode) || node.contains(selected.focusNode)));
  }
  function destination(offset, epoch, sort, direction, period) {
    const params = new URLSearchParams({period, sort, direction: String(direction)});
    if (offset) params.set('offset', String(offset));
    if (epoch) params.set('epoch', epoch);
    return '#/sessions?' + params;
  }
  class View {
    constructor(api, {archive = false} = {}) {
      Object.assign(this, {api, archive, token: null, data: null, attached: false, busy: false, generation: 0, navigationSequence: Date.now()});
      this.root = el('div', undefined, 'sessions-catalog'); this.root.setAttribute('aria-label', 'Sessions catalog');
      this.status = el('p', undefined, 'sessions-action-status'); this.status.setAttribute('role', 'status');
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
        if (typeof PeriodHelp !== 'undefined') PeriodHelp.attach(button, key);
        button.addEventListener('click', () => this.navigateTo(destination(0, null, this.sort, this.direction, key), null, 'period'));
        this.periods.append(button); return {key, button};
      });
      const pan = el('div', undefined, 'sessions-table-pan'); pan.tabIndex = 0;
      pan.setAttribute('role', 'region'); pan.setAttribute('aria-label', 'Sessions');
      const table = el('table', undefined, 'sessions-table session-catalog-table');
      const head = el('thead'), header = el('tr'); this.headers = [];
      for (const [key, name, help] of columns) {
        const th = el('th'), button = el('button', name); th.scope = 'col';
        const label = ContextHelp.heading(button, help + (key === 'activity' ? '' :
          '\nRunning sessions appear first, newest prompt start first.'), key === 'ctx');
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
      pager.append(this.previous, this.label, this.numbers, this.next);
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
      if (kind === 'page' && this.offset === 0 && this.data?.offset === 0 && !this.operation &&
          (this.data.order_state === 'verified' || this.data.candidate_navigation)) {
        // Back must name the actual page being left, not ask for a cold latest.
        history.replaceState(history.state, '', this.rememberedDestination());
      }
      this.userAction = {destination: target, button, kind, started: performance.now()};
      location.hash = target;
    }
    clearStatus() {
      ReportView.text(this.statusTask, '');
      ReportView.text(this.statusCount, ''); ReportView.text(this.statusStage, '');
      this.status.hidden = true;
    }
    configure(params) {
      const offset = Number(params?.get('offset') || 0), epoch = params?.get('epoch') || null;
      const sort = columns.some(([key]) => key === params?.get('sort')) ? params.get('sort') : 'activity';
      const direction = params?.get('direction') === '1' ? 1 : -1;
      const period = params?.has('period') ? params.get('period') : 'today';
      // Repeated route notifications cannot erase pending intent or a failure.
      if (offset === this.offset && epoch === this.epoch &&
        sort === this.sort && direction === this.direction && period === this.period) {
        if (!params?.has('period')) {
          if (this.operation) this.canonicalPeriod = true;
          else history.replaceState(history.state, '', destination(offset, epoch, sort, direction, period));
        }
        return;
      }
      const action = this.userAction?.destination === location.hash ? this.userAction : null;
      this.userAction = null;
      if (this.operation?.navigation) this.cancelledNavigation = this.operation.navigation;
      this.actionFocus = null; this.retire();
      this.clearStatus();
      if (this.period != null && period !== this.period)
        ReportLoading.beginHistorySelection(this, this.periodButton(period), action?.started);
      Object.assign(this, {offset, epoch, sort, direction, period});
      this.canonicalPeriod = !params?.has('period');
      this.periodSelection();
      const changedPeriod = this.data && period !== this.data.period;
      const changedOrder = this.data && (sort !== this.data.sort || direction !== this.data.direction || changedPeriod);
      this.operation = action || offset || epoch || changedOrder ? {kind: action?.kind || (changedPeriod ? 'period' : this.data && this.sort === this.data.sort &&
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
    periodButton(period = this.period) {
      return this.periodButtons.find(item => item.key === period)?.button;
    }
    periodSelection() {
      for (const {key, button} of this.periodButtons) button.setAttribute('aria-pressed', String(key === this.period));
      if (this.archive || this.data?.cache_first)
        ReportLoading.historyProgress(this, this.periodButton(),
          this.data?.period === this.period ? this.data.history_progress : {complete: false});
    }
    rememberedDestination() {
      const data = this.data;
      if (data) return this.pageDestination(data, data.offset);
      return this.firstPageDestination();
    }
    sectionDestination() { return this.data?.offset ? this.rememberedDestination() : this.firstPageDestination(); }
    firstPageDestination() { return destination(0, null, this.sort, this.direction, this.period); }
    attach(parent) {
      if (this.root.parentNode !== parent) parent.replaceChildren(this.root);
      if (!this.attached) {
        this.attached = true; this.rerun = true; this.periodSelection(); this.interest(); this.poll();
      } else if (this.rerun) this.poll();
    }
    interest(visible = this.attached && !document.hidden, token = this.token) {
      if (token) this.api('/api/sessions', {action: 'interest', token, visible}).catch(() => {});
    }
    detach() {
      this.attached = false; this.actionFocus = null;
      ReportLoading.endHistorySelection(this);
      if (this.userAction?.destination !== location.hash) this.userAction = null;
      this.interest(false); this.retire();
    }
    sourceHealth(unverified, blocked) {
      const becameUnverified = unverified && !this.sourceUnverified;
      this.sourceUnverified = unverified;
      if (blocked) {
        this.clearStatus();
        if (this.attached) this.detach();
      }
      if (!becameUnverified) return;
      for (const row of this.body.children) if (row.value.running) {
        row.value = {...row.value, running: false, last_activity_ms: null, activity_state: 'unverified'};
        this.activity(row);
      }
    }
    wake(hint) {
      if (typeof hint !== 'string' || !hint || hint === this.liveHint) return;
      if (!this.attached || document.hidden || this.offset !== 0 && !this.data?.cache_first ||
          this.terminal || this.operation?.failed) return;
      this.liveHint = hint;
      const pending = this.wakePending; this.wakePending = true;
      // Explicit navigation owns the request/cohort. Keep one trailing wake,
      // never cancel or restart an action or an in-flight passive request.
      if (pending || this.busy || this.operation || this.retryDelay) return;
      clearTimeout(this.timer);
      this.timer = setTimeout(() => this.poll(), 100);
    }
    catchUp(since = performance.now(), hiddenOrRecovery = true) {
      if (!this.attached || document.hidden || this.terminal || this.operation?.failed) return;
      // An authenticated host is usable again. Retire only a stale passive
      // request; keep the selected page, sort and any explicit navigation.
      this.retryDelay = 0;
      if (this.busy) {
        if (!this.operation && (this.archive || this.data?.cache_first) && this.flight?.started <= since &&
            (hiddenOrRecovery || !this.flight.foreground)) this.retire();
        else { this.wakePending = true; return; }
      }
      this.interest();
      this.poll(true);
    }
    async poll(foreground = false) {
      if (!this.attached || this.busy || this.terminal) return;
      clearTimeout(this.timer);
      if (document.hidden) {
        if (!this.data?.cache_events) this.timer = setTimeout(() => this.poll(), 30000);
        return;
      }
      if (this.operation?.failed) this.recoverNavigation();
      const generation = this.generation;
      await this.load(foreground);
      if (generation === this.generation && this.attached && !this.terminal) {
        const delay = this.retryDelay || (this.rerun ? 0 : this.operation ? 1000 :
          this.wakePending && (this.offset === 0 || this.data?.cache_first) ? 100 :
          this.data?.cache_events ? null : this.data?.cache_first ? 1500 : 5000);
        if (delay !== null) this.timer = setTimeout(() => this.poll(), delay);
      }
    }
    recoverNavigation() {
      if (this.operation.navigation) this.cancelledNavigation = this.operation.navigation;
      this.operation = null;
      const previous = this.data;
      this.offset = previous?.offset || 0;
      this.epoch = this.offset ? previous.epoch : null;
      if (previous) Object.assign(this, {period: previous.period, sort: previous.sort, direction: previous.direction});
      this.periodSelection(); this.canonicalPeriod = true;
    }
    async load(foreground) {
      if (this.busy || this.terminal) return;
      const entering = this.rerun;
      this.busy = true; this.rerun = false;
      if (!this.operation) this.wakePending = false;
      this.pagerBusy();
      const generation = this.generation;
      const flight = {controller: new AbortController(), started: performance.now(), foreground}; this.flight = flight;
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
        let requestedEpoch, passive;
        const request = () => {
          passive = !this.operation && this.offset === 0;
          requestedEpoch = this.epoch || (passive && !entering && !this.recovering ? this.data?.epoch : null) || null;
          return Promise.race([this.api('/api/sessions', {token: this.token, offset: this.offset,
            epoch: requestedEpoch, sort: this.sort, direction: this.direction, period: this.period, passive,
            navigation: this.operation?.navigation || null, applied: this.appliedNavigation || null,
            cancelled: this.cancelledNavigation || null}, flight.controller.signal), deadline]);
        };
        let data;
        try { data = await request(); }
        catch (error) {
          if (error.message !== 'catalog_expired' || !this.attached || generation !== this.generation) throw error;
          if (this.operation && this.operation.restarts++ >= 1) {
            this.failNavigation('navigation_invalidated', false); return;
          }
          // No proof that a new lease has the old membership: safely return to
          // latest, preserving sort intent. One reopen per poll, never a loop.
          this.interest(false);
          this.token = null; this.appliedNavigation = null; this.cancelledNavigation = null;
          this.epoch = null; this.offset = 0; this.recovering = true;
          if (!this.operation?.userInitiated || this.operation.kind === 'page') this.operation = null;
          // Old destinations belong to the rejected lease. Retire them before
          // awaiting the replacement, not only after that request settles.
          this.pagerBusy();
          data = await request();
        }
        if (!this.attached || generation !== this.generation) {
          if (data.token !== this.token || !this.attached || this.operation?.failed) this.interest(false, data.token);
          return;
        }
        if (data.period !== this.period || !data.cache_first && requestedEpoch && !passive && data.epoch !== requestedEpoch ||
          (!data.pending_sort || data.passive) &&
          (data.sort !== this.sort || data.direction !== this.direction || !data.cache_first && data.offset !== this.offset)) {
          throw new Error('catalog_response_mismatch');
        }
        const opened = this.token !== data.token;
        this.token = data.token;
        if (data.state === 'observed' && (!this.operation || !data.progress?.reason)) this.retryDelay = 0;
        this.update(data);
        if (opened) this.interest();
      } catch (error) {
        if (!this.attached || generation !== this.generation) return;
        const terminal = sharedRecovery.has(error.message) ||
          ['permission_denied', 'invalid_request', 'catalog_response_mismatch', 'unsupported_schema',
          'http_auth_failure', 'invalid_data'].includes(error.message) ||
          error.retryable === false && !['catalog_busy', 'request_unavailable', 'source_unavailable'].includes(error.message);
        if (terminal) {
          this.terminal = true; this.terminalReason = error.message; this.interest(false);
          ReportLoading.endHistorySelection(this);
        }
        if (this.operation) {
          if (terminal) this.failNavigation(error.message);
          else this.waitNavigation(flight.timedOut ? 'request_timeout' : error.message);
        }
        else {
          this.retryDelay = Math.min(30000, (this.retryDelay || 2500) * 2);
        }
        if (error.message === 'catalog_expired') {
          this.token = null; this.epoch = null; this.offset = 0; this.recovering = true;
        }
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
      if (!operation.userInitiated) { this.pagerBusy(); return; }
      if ((this.archive || this.data?.cache_first) && !operation.failed) { this.pagerBusy(); return; }
      const before = operation.kind === 'page' ? null : this.pan;
      if (this.status.nextSibling !== before) this.root.insertBefore(this.status, before);
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
    failNavigation(reason, terminal = true) {
      if (!this.operation) return;
      this.terminal = terminal; this.terminalReason = reason;
      this.operation.failed = true;
      this.operation.pending = false;
      ReportLoading.endHistorySelection(this);
      if (terminal) this.interest(false);
      const message = terminal ? 'Could not load. Reload Cost Guard to try again.' :
          'Could not complete this request. Returning to an available page.';
      if (this.operation.userInitiated && !sharedRecovery.has(reason)) this.showProgress(message);
      else { this.clearStatus(); this.pagerBusy(); }
    }
    waitNavigation(reason) {
      this.retryDelay = Math.min(30000, (this.retryDelay || 500) * 2);
      if (this.operation?.userInitiated && Date.now() - this.operation.advanced >= 90000)
        this.failNavigation(reason, false);
      else if (this.operation?.userInitiated) this.showProgress();
    }
    pendingNavigation(data) {
      if (!this.operation) return false;
      const progress = data.progress;
      if (data.page_reused && data.state === 'observed' && progress?.status !== 'failed') return false;
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
        // Explicit order may be unavailable even while the read-only live lane
        // is healthy. Retire that navigation, not the separate metadata feed.
        this.failNavigation(progress?.reason || 'source_unavailable', data.state !== 'observed');
        return true;
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
      if (data.state !== 'observed') {
        if (this.operation) this.pendingNavigation(data);
        return;
      }
      if (this.sourceUnverified && !data.cache_first) return; // A pre-outage HTTP reply cannot restore Live.
      // A requested candidate-scope sort is not applied until every eligible key is valid. Keep
      // the previous actual order, header and pager rather than relabeling it.
      const provisional = !this.operation && this.offset === 0 && data.offset === 0 && data.passive &&
        data.state === 'observed' && data.order_state === 'provisional' &&
        data.period === this.period && data.sort === this.sort && data.direction === this.direction;
      if (this.pendingNavigation(data) || data.pending_sort && !provisional) {
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
      if (this.data?.source?.identity !== data.source?.identity) {
        this.costs = null;
        this.body.replaceChildren();
      }
      this.data = data;
      this.renderTimezone = data.view.timezone_id;
      this.offset = data.offset;
      if (this.recovering || this.canonicalPeriod || data.cache_first && (this.epoch !== data.epoch && data.offset > 0) ||
          data.passive && this.epoch && data.epoch !== this.epoch) {
        this.epoch = data.offset || this.epoch && data.order_state === 'verified' ? data.epoch : null;
        history.replaceState(history.state, '', destination(data.offset, this.epoch, this.sort, this.direction, this.period));
        this.recovering = false;
        this.canonicalPeriod = false;
      }
      this.clearStatus();
      ReportLoading.historyProgress(this, this.periodButton(data.period), data.history_progress);
      for (const {key, name, th, label} of this.headers) {
        const active = key === data.sort;
        th.setAttribute('aria-sort', active ? data.direction === 1 ? 'ascending' : 'descending' : 'none');
        ReportView.text(label, name + (active ? data.direction === 1 ? ' ↑' : ' ↓' : ''));
      }
      // Lifecycle status must not remain falsely running while a title is selected.
      // A recovered epoch cannot keep protected old rows under a new page label.
      if ((completed && !data.page_reused || changedPage) && protectedNode(this.body)) {
        window.getSelection?.()?.removeAllRanges?.();
        if (this.body.contains(document.activeElement)) document.activeElement.blur?.();
      }
      this.rows(values);
      if (completed) ContextHelp.refresh(this.root);
      const pages = Math.max(1, Math.ceil(data.total / data.size));
      const retainedOrder = data.retained_order ? ' · Order as of snapshot' : '';
      const unit = data.membership_pending ? (data.cache_first ? 'currently available sessions' :
        'catalog candidates (preliminary)') : 'sessions';
      const empty = data.cache_first && data.membership_pending ? 'No cached matches yet' : 'No confirmed matches among catalog candidates';
      ReportView.text(this.label, data.total ? `Showing ${data.offset + 1}–${Math.min(data.offset + data.size, data.total)} of ${data.total} ${unit} · Page ${Math.floor(data.offset / data.size) + 1} of ${pages}${retainedOrder}` :
        data.state === 'observed' ? `${empty} in ${periods.find(([key]) => key === data.period)?.[1] || data.period} · Page 1 of 1` : 'Session count unavailable');
      const link = (node, offset, enabled) => {
        node.destination = enabled ? this.pageDestination(data, offset) : null;
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
    pageDestination(data, offset) {
      return destination(offset, offset || data.order_state === 'verified' || data.candidate_navigation ? data.epoch : null,
        data.sort, data.direction, data.period);
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
          this.pageDestination(data, (page - 1) * data.size) : null;
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
      if (this.pan.getAttribute('aria-busy') !== String(navigating)) this.pan.setAttribute('aria-busy', String(navigating));
      if (restoreFocus && !navigating && !this.busy && this.actionFocus) {
        if (document.activeElement === document.body || document.activeElement === this.actionFocus) {
          const target = !this.actionFocus.disabled && this.pager.contains(this.actionFocus) ? this.actionFocus :
            buttons.find(button => !button.disabled);
          (target || this.pan).focus?.({preventScroll: true});
        }
        this.actionFocus = null;
      }
    }
    activity(row) {
      const value = row.value;
      const render = at => ReportView.timestamp(at, this.renderTimezone);
      let label, help = '';
      if (value.running) {
        label = render(value.prompt_started_ms ?? value.last_activity_ms);
        help = ReportView.activityHelp(value.prompt_started_ms ?? value.last_activity_ms, this.renderTimezone, true);
      } else if (value.catalog_activity_ms != null) {
        label = render(value.catalog_activity_ms);
        help = '* Preliminary activity from the OpenCode session catalog. Prompt time is not yet verified.';
      } else if (value.last_activity_ms == null || value.activity_state === 'unverified') {
        label = render(value.prompt_started_ms);
        help = '* Showing the recorded prompt start. Finish time is not verified.';
      } else {
        label = render(value.last_activity_ms);
      }
      ReportView.metric(row.activity, 'activity', {
        value: label === 'N/A' ? null : label + (help ? '*' : ''), help,
        reason: value.metric_absences?.activity, onHelpLost: row.metricHelpLost
      });
      const status = value.running ? 'running' : value.terminal_status;
      row.className = status ? `session-${status}` : '';
      ReportView.text(row.statusMarker, status ? `[${status.toUpperCase()}] ` :
        value.activity_state === 'unverified' ? '[UNVERIFIED] ' : value.new_arrival ? '[NEW · Loading] ' : '');
      const finalizing = value.finalization_status === 'pending';
      const unavailable = value.finalization_status === 'unavailable';
      ReportView.text(row.finalizationMarker, finalizing ? ' *' : unavailable ? ' !' : '');
      if (finalizing || unavailable) {
        const hint = finalizing ? 'Final session history is still being prepared.' : 'Final session history is unavailable.';
        ContextHelp.value(row.finalizationMarker, hint);
      } else ContextHelp.clearValue(row.finalizationMarker);
    }
    rows(values) {
      this.costs ||= new ReportView.CostDisplay();
      const old = new Map([...this.body.children].map(row => [row.dataset.id, row]));
      const wanted = new Set(values.map(row => row.session_id));
      for (const row of [...this.body.children]) if (!wanted.has(row.dataset.id)) {
        // A genuine backend eviction is not a focus-pinned extra table row.
        const removedFocus = row.contains(document.activeElement);
        ContextHelp.dismiss?.(row); row.remove();
        if (removedFocus) this.pan.focus?.({preventScroll: true});
      }
      values.forEach((value, index) => {
        value = this.costs.select(value, [this.data?.source?.identity, this.data?.source?.generation, value.session_id],
          'ccost', value.unresolved_cost == null ? value.complete === true : !value.unresolved_cost);
        const row = old.get(value.session_id) || el('tr'); row.dataset.id = value.session_id;
        row.value = value;
        if (!row.name) {
          row.activity = el('span'); row.name = el('a', undefined, 'session-name');
          row.statusMarker = el('span'); row.titleNode = el('span');
          row.finalizationMarker = el('span');
          row.name.append(row.statusMarker, row.titleNode);
          if (/^[A-Za-z0-9_-]{1,200}$/.test(value.session_id)) row.name.href = '#/sessions/' + value.session_id;
          ContextHelp.value(row.name, () => row.value.title);
          row.metricHelpLost = () => {
            row.name.focus?.({preventScroll: true});
            ContextHelp.dismiss(row.name);
          };
          row.metrics = Array.from({length: 5}, () => el('span'));
          const cells = [row.activity, row.name, ...row.metrics];
          row.replaceChildren(...cells.map(content => { const td = el('td'); td.append(typeof content === 'object' ? content : el('span', content)); return td; }));
          row.activity.after(row.finalizationMarker);
        }
        this.activity(row);
        ReportView.text(row.titleNode, value.title);
        const model = (value.model !== 'N/A' && value.model) || value.selected_display_model;
        const amounts = [
          model ? model + (value.has_model_details ? '*' : '') : null,
          () => ReportView.metricToken(value, 'ccost') ?? (value.metric_states?.ccost === 'unavailable' ? '—' : null),
          value.prompt_count,
          ReportView.metricToken(value, 'duration_ms'),
          ReportView.metricToken(value, 'context_tokens')
        ];
        const current = value;
        const helps = [
          () => ReportView.metricToken(value, 'model_help'),
          () => value.metric_states?.ccost === 'unavailable' && ReportView.metricToken(value, 'ccost') == null ?
            ReportView.metricToken(value, 'ccost_unavailable_help') || 'Whole-session reference CCost unavailable.' :
             ReportView.sessionCostHelp(value, value) + (value.metric_states?.ccost === 'retained' ?
               '\nLast qualified value; refresh pending.' : ''), null, null,
          current.context_tokens == null ? null : `~${current.context_tokens.toLocaleString()} tokens`
        ];
        row.metrics.forEach((node, index) => {
          const key = ['model', 'ccost', 'prompts', 'duration', 'ctx'][index];
          const state = value.metric_states?.[key] || value.metric_state || (value.indexed ? 'ready' : 'pending');
          node.classList.toggle('session-metric-pending', state === 'retained' || key === 'ctx' && state !== 'ready');
          ReportView.metric(node, key, {value: amounts[index], reason: value.metric_absences?.[key],
            help: helps[index], label: state === 'retained' ? shown => `Retained value: ${shown}` : null,
            onHelpLost: row.metricHelpLost});
        });
        ContextHelp.refresh(row);
        if (this.body.children[index] !== row) {
          const before = this.body.children[index] || null;
          if (row.parentNode && this.body.moveBefore) this.body.moveBefore(row, before);
          else {
            // Older engines can preserve a protected target by moving the
            // intervening nodes around it rather than detaching that target.
            while (row.parentNode === this.body && protectedNode(row) &&
              this.body.children[index] !== row && !protectedNode(this.body.children[index])) {
              this.body.insertBefore(this.body.children[index], row.nextSibling);
            }
            if (this.body.children[index] !== row) {
              const active = document.activeElement, selection = window.getSelection?.();
              const range = selection && !selection.isCollapsed ?
                [selection.anchorNode, selection.anchorOffset, selection.focusNode, selection.focusOffset] : null;
              this.body.insertBefore(row, this.body.children[index] || null);
              if (active && this.body.contains(active) && document.activeElement !== active) active.focus?.({preventScroll: true});
              if (range && this.body.contains(range[0]) && this.body.contains(range[2])) selection.setBaseAndExtent?.(...range);
            }
          }
        }
      });
    }
  }
  return {View};
})();
