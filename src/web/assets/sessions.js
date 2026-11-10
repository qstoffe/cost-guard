'use strict';
// Server-owned full-catalog ordering; older-page epochs never shift under arrivals.
const SessionsCatalog = (() => {
  const el = (...args) => ReportView.element(...args);
  const columns = [
    ['activity', 'Last activity', 'Latest source-backed activity in this session tree, in local date and time.'],
    ['name', 'Session name', 'The session title. Open the name for its complete live prompt history.'],
    ['model', 'Model', 'One canonical model, or Multiple models when different models contributed.'],
    ['ccost', 'CCost', 'Whole-session reference cost, not billing. ? means incomplete pricing. Sort uses unrounded complete cost; partial values stay last.'],
    ['prompts', 'Prompts', 'Canonical number of prompts in the entire session.'],
    ['duration', 'Duration', 'Canonical execution duration, excluding idle gaps. Sort uses milliseconds.']
  ];
  function protectedNode(node) {
    const selected = window.getSelection?.();
    return node.contains(document.activeElement) || Boolean(selected && !selected.isCollapsed &&
      (node.contains(selected.anchorNode) || node.contains(selected.focusNode)));
  }
  function destination(offset, epoch, sort, direction) {
    const params = new URLSearchParams({sort, direction: String(direction)});
    if (offset) { params.set('offset', String(offset)); params.set('epoch', epoch); }
    return '#/sessions?' + params;
  }
  class View {
    constructor(api) {
      Object.assign(this, {api, token: null, data: null, attached: false, busy: false, generation: 0});
      this.root = el('div', undefined, 'sessions-catalog'); this.root.setAttribute('aria-label', 'Sessions catalog');
      this.status = el('p', 'Loading sessions…', 'warning'); this.status.setAttribute('role', 'status');
      const pan = el('div', undefined, 'sessions-table-pan'); pan.tabIndex = 0;
      pan.setAttribute('role', 'region'); pan.setAttribute('aria-label', 'Sessions');
      const table = el('table', undefined, 'sessions-table session-catalog-table');
      const head = el('thead'), header = el('tr'); this.headers = [];
      for (const [key, name, help] of columns) {
        const th = el('th'), button = el('button', name); th.scope = 'col';
        const label = ContextHelp.heading(button, help + '\nActivate to sort the full catalog; activate again to reverse. Unknowns stay last.');
        button.addEventListener('click', () => {
          const direction = this.sort === key ? -this.direction : key === 'activity' ? -1 : 1;
          location.hash = destination(0, null, key, direction);
        });
        th.append(button); header.append(th); this.headers.push({key, name, th, label});
      }
      head.append(header); this.body = el('tbody'); table.append(head, this.body); pan.append(table);
      const pager = el('div', undefined, 'pager page-navigation');
      this.pan = pan; this.pager = pager;
      this.previous = el('button', 'Previous'); this.next = el('button', 'Next'); this.label = el('span');
      for (const button of [this.previous, this.next]) {
        button.type = 'button'; button.disabled = true;
        button.addEventListener('click', () => { if (!button.disabled && button.destination) location.hash = button.destination; });
      }
      this.label.setAttribute('aria-live', 'polite'); pager.append(this.previous, this.label, this.next);
      for (const event of ['focusin', 'pointerdown']) document.addEventListener(event, event => {
        if (this.actionFocus && event.target !== this.actionFocus) this.actionFocus = null;
      });
      this.root.append(this.status, pan, pager);
      this.loader = new ReportLoading.View(); this.loader.root.hidden = true;
      this.loader.bar.setAttribute('aria-label', 'Sessions loading progress');
      this.cancel = el('button', 'Cancel'); this.retry = el('button', 'Retry');
      this.cancel.type = this.retry.type = 'button'; this.retry.hidden = true;
      ContextHelp.attach(this.cancel, () => this.operation?.kind === 'page' ?
        'Cancel loading this page and return to the previous page.' :
        'Cancel this sort and return to the previous sorting and page.');
      this.cancel.addEventListener('click', () => this.cancelNavigation());
      this.retry.addEventListener('click', () => {
        this.configure(new URLSearchParams(location.hash.split('?')[1])); this.poll();
      });
      const actions = el('div', undefined, 'sessions-loading-actions'); actions.append(this.cancel, this.retry);
      this.loader.root.append(actions); this.root.append(this.loader.root);
    }
    configure(params) {
      this.retire();
      const focus = this.operation?.focus || document.activeElement;
      const scroll = this.operation?.scroll || [window.scrollX || 0, window.scrollY || 0, this.pan.scrollLeft || 0];
      this.offset = Number(params?.get('offset') || 0);
      this.epoch = params?.get('epoch') || null;
      this.sort = columns.some(([key]) => key === params?.get('sort')) ? params.get('sort') : 'activity';
      this.direction = params?.get('direction') === '1' ? 1 : -1;
      const changed = this.data && (this.offset !== this.data.offset || this.sort !== this.data.sort ||
        this.direction !== this.data.direction || this.offset && this.epoch !== this.data.epoch);
      this.operation = changed || !this.data ? {kind: this.data && this.sort === this.data.sort &&
        this.direction === this.data.direction ? 'page' : 'sort', focus, scroll,
        advanced: Date.now(), percent: 0, completed: -1, source: null, rebases: 0, failed: false} : null;
      this.loader.root.hidden = true; this.pan.hidden = this.pager.hidden = false;
      this.rerun = true;
    }
    retire() {
      this.generation++; this.flight?.controller.abort(); this.flight = null; this.busy = false;
      clearTimeout(this.admission); clearTimeout(this.timer);
      clearTimeout(this.requestDeadline);
    }
    rememberedDestination() { return destination(this.offset || 0, this.epoch || this.data?.epoch, this.sort || 'activity', this.direction || -1); }
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
      if (!this.attached || this.busy || this.operation?.failed) return;
      clearTimeout(this.timer);
      if (document.hidden) { this.timer = setTimeout(() => this.poll(), 30000); return; }
      const generation = this.generation;
      await this.load();
      if (generation === this.generation && this.attached && !this.operation?.failed) this.timer = setTimeout(() => this.poll(), this.rerun ? 0 : this.operation ? 1000 : 5000);
    }
    async load() {
      if (this.busy) return;
      this.busy = true; this.rerun = false;
      this.pagerBusy();
      const generation = this.generation;
      const flight = {controller: new AbortController()}; this.flight = flight;
      if (this.operation) this.admission = setTimeout(() => {
        if (generation === this.generation && this.operation) this.showProgress('Checking cached sort keys…');
      }, 180);
      this.requestDeadline = setTimeout(() => {
        if (this.flight !== flight) return;
        this.retire();
        if (this.operation) this.failNavigation('request_timeout');
        else { this.status.textContent = 'Sessions source did not respond. Retaining the last observed page.'; this.status.hidden = false; }
      }, 15000);
      try {
        const request = () => this.api('/api/sessions', {token: this.token, offset: this.offset,
          epoch: this.epoch, sort: this.sort, direction: this.direction}, flight.controller.signal);
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
            epoch: this.epoch, sort: this.sort, direction: this.direction}).catch(() => {});
          return;
        }
        if (!data.pending_sort && (data.sort !== this.sort || data.direction !== this.direction || data.offset !== this.offset)) {
          throw new Error('catalog_response_mismatch');
        }
        const opened = this.token !== data.token;
        this.token = data.token; this.update(data);
        if (opened) this.interest();
      } catch (error) {
        if (!this.attached || generation !== this.generation) return;
        if (this.operation) this.failNavigation(error.message);
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
    showProgress(stage, stageLabel = stage) {
      if (!this.operation) return;
      this.loader.update({percent: this.operation.percent, stage, stageLabel});
      this.loader.root.hidden = false;
      this.retry.hidden = !this.operation.failed;
      this.status.hidden = true;
      if (this.pan.contains(document.activeElement) || this.pager.contains(document.activeElement) ||
        this.actionFocus && document.activeElement === document.body) this.cancel.focus?.({preventScroll: true});
      this.pan.hidden = this.pager.hidden = !this.operation.failed;
    }
    failNavigation(reason) {
      if (!this.operation) return;
      this.operation.failed = true;
      this.interest(false);
      this.showProgress(`Sessions ${this.operation.kind} could not finish (${reason}). Retry after the source recovers, or Cancel to return.`, 'Sessions navigation failed');
    }
    pendingNavigation(data) {
      if (!this.operation) return false;
      const progress = data.progress;
      const pagePending = this.operation.kind === 'page' && progress && progress.completed < progress.total;
      if (!data.pending_sort && !pagePending && data.state === 'observed') return false;
      const operation = this.operation;
      const completed = progress?.completed ?? data.indexed ?? 0;
      const total = progress?.total ?? data.available ?? 0;
      const source = `${progress?.generation ?? ''}:${progress?.phase ?? 'index'}:${total}`;
      const restarted = operation.source !== null && (source !== operation.source || completed < operation.completed);
      if (restarted) { operation.percent = 0; operation.completed = -1; operation.rebases++; }
      if (operation.rebases >= 8) { this.failNavigation('concurrent_source_change'); return true; }
      if (completed > operation.completed) { operation.completed = completed; operation.advanced = Date.now(); }
      operation.source = source;
      operation.percent = Math.max(operation.percent, Math.min(99, total ? Math.floor(99 * completed / total) : 0));
      if (progress?.status === 'failed' || data.state === 'source_unavailable') {
        this.failNavigation(progress?.reason || 'source_unavailable'); return true;
      }
      if (Date.now() - operation.advanced >= 45000) { this.failNavigation('no_source_progress'); return true; }
      const name = columns.find(([key]) => key === this.sort)[1];
      const label = data.pending_sort ? `Indexing ${name}` : `Preparing page ${Math.floor(this.offset / 50) + 1}`;
      this.showProgress(`${restarted ? 'Source changed; restarting. ' : ''}${label} (${completed} of ${total} sessions)…`, label);
      return true;
    }
    cancelNavigation() {
      const operation = this.operation;
      if (!operation) return;
      this.retire(); this.interest(false); this.operation = null;
      if (this.data) {
        this.offset = this.data.offset; this.epoch = this.data.epoch;
        this.sort = this.data.sort; this.direction = this.data.direction;
      } else { this.offset = 0; this.epoch = null; this.sort = 'activity'; this.direction = -1; }
      history.replaceState(null, '', this.rememberedDestination());
      this.loader.root.hidden = true; this.pan.hidden = this.pager.hidden = false; this.pagerBusy();
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
      // A requested global sort is not applied until every key is valid. Keep
      // the previous actual order, header and pager rather than relabeling it.
      if (this.pendingNavigation(data) || data.pending_sort) return;
      const completed = this.operation;
      const restoreFocus = completed && this.loader.root.contains(document.activeElement);
      this.operation = null; clearTimeout(this.admission);
      this.loader.root.hidden = true; this.pan.hidden = this.pager.hidden = false;
      this.data = data;
      this.usable = data.state === 'observed' || data.view.session_usage.length > 0;
      this.offset = data.offset;
      if (data.epoch) this.epoch = data.epoch;
      if (this.recovering) {
        history.replaceState(null, '', destination(data.offset, data.epoch, this.sort, this.direction));
        this.recovering = false; this.rebased = true;
      }
      this.status.textContent = this.rebased ? 'The previous catalog expired; showing the latest first page.' :
        data.state !== 'observed' && !data.view.session_usage.length ? 'Loading sessions…' : '';
      this.status.hidden = !this.status.textContent;
      for (const {key, name, th, label} of this.headers) {
        const active = key === data.sort;
        th.setAttribute('aria-sort', active ? data.direction === 1 ? 'ascending' : 'descending' : 'none');
        ReportView.text(label, name + (active ? data.direction === 1 ? ' ↑' : ' ↓' : ' ↕'));
      }
      const values = data.view.session_usage;
      // Lifecycle status must not remain falsely running while a title is selected.
      if (completed && protectedNode(this.body)) {
        window.getSelection?.()?.removeAllRanges?.();
        if (this.body.contains(document.activeElement)) document.activeElement.blur?.();
      }
      this.rows(values);
      if (completed && !restoreFocus) ContextHelp.refresh(this.root);
      if (restoreFocus) this.actionFocus = completed.focus;
      const pages = Math.max(1, Math.ceil(data.total / data.size));
      this.label.textContent = data.total ? `Showing ${data.offset + 1}–${Math.min(data.offset + 50, data.total)} of ${data.total} sessions · Page ${Math.floor(data.offset / 50) + 1} of ${pages}` :
        data.state === 'observed' ? 'No sessions · Page 1 of 1' : 'Session count unavailable';
      const link = (node, offset, enabled) => {
        node.destination = enabled ? destination(offset, data.epoch, data.sort, data.direction) : null;
      };
      link(this.previous, Math.max(0, data.offset - 50), data.offset > 0);
      link(this.next, data.offset + 50, data.offset + 50 < data.total);
      this.pagerBusy();
      if (completed) this.loader.update({percent: 100, stage: 'Page applied', stageLabel: 'Page applied'});
    }
    pagerBusy() {
      if (this.busy && [this.previous, this.next].includes(document.activeElement)) this.actionFocus = document.activeElement;
      for (const button of [this.previous, this.next]) button.disabled = this.busy || this.recovering || !button.destination;
      if (!this.busy && this.actionFocus) {
        if (document.activeElement === document.body || document.activeElement === this.actionFocus ||
          this.loader.root.contains(document.activeElement)) {
          (this.actionFocus.disabled ? this.actionFocus === this.next ? this.previous : this.next : this.actionFocus).focus({preventScroll: true});
        }
        this.actionFocus = null;
      }
    }
    rows(values) {
      const old = new Map([...this.body.children].map(row => [row.dataset.id, row]));
      const wanted = new Set(values.map(row => row.session_id));
      const keepOrder = protectedNode(this.body);
      for (const row of [...this.body.children]) if (!wanted.has(row.dataset.id) && !protectedNode(row)) row.remove();
      values.forEach((value, index) => {
        const row = old.get(value.session_id) || el('tr'); row.dataset.id = value.session_id;
        row.value = value;
        if (!row.name) {
          row.activity = el('span'); row.name = el('a', undefined, 'session-name');
          row.runningMarker = el('span'); row.titleNode = el('span');
          row.name.append(row.runningMarker, row.titleNode);
          if (/^[A-Za-z0-9_-]{1,200}$/.test(value.session_id)) row.name.href = '#/sessions/' + value.session_id;
          ContextHelp.value(row.name, () => row.value.title);
          row.metrics = ['model', 'ccost', 'prompts', 'duration'].map(key => {
            const node = el('span');
            ContextHelp.value(node, () => {
              const current = row.value, state = current.metric_states?.[key] || current.metric_state || 'ready';
              if (key === 'ccost' && ReportView.costHelp(current)) return ReportView.costHelp(current);
              if (key !== 'model' || !current.multiple_models) return 'Observed session ' + key + '.';
              const models = current.contributor_models || [];
              return ['Models used in this session' + (current.contributor_models_complete && state === 'ready' ? '' : ' (observed so far)'),
                models.length ? models.join('\n') : 'Contributing model identities are not available.'].filter(Boolean).join('\n');
            });
            return node;
          });
          const cells = [row.activity, row.name, ...row.metrics];
          row.replaceChildren(...cells.map(content => { const td = el('td'); td.append(typeof content === 'object' ? content : el('span', content)); return td; }));
        }
        row.className = value.running ? 'session-running' : '';
        ReportView.text(row.activity, ReportView.timestamp(value.last_activity_ms, this.data.view.timezone_id));
        ReportView.text(row.titleNode, value.title);
        ReportView.text(row.runningMarker, value.running ? '[RUNNING] ' : '');
        const texts = [value.multiple_models ? 'Multiple models' : value.model || 'N/A',
          () => ReportView.display(value, 'ccost'), value.prompt_count == null ? 'N/A' : String(value.prompt_count),
          () => ReportView.display(value, 'duration_ms')];
        row.metrics.forEach((node, index) => {
          const key = ['model', 'ccost', 'prompts', 'duration'][index];
          const state = value.metric_states?.[key] || value.metric_state || (value.indexed ? 'ready' : 'pending');
          const missing = (!value.has_summary && !value.indexed && state !== 'retained') ||
            (key === 'model' && state === 'pending' && (!value.model || value.model === 'N/A'));
          ReportView.text(node, missing ? state === 'pending' ? 'Loading…' : 'Unavailable' : texts[index]);
          node.className = 'help-value' + (missing ? ' session-metric-pending' : '');
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
