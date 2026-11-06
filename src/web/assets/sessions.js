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
  function localTimestamp(milliseconds) {
    if (milliseconds == null) return 'N/A';
    const date = new Date(milliseconds), pad = value => String(value).padStart(2, '0');
    if (!Number.isFinite(date.getTime())) return 'N/A';
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
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
      const pager = el('div', undefined, 'pager sessions-pager');
      this.previous = el('button', 'Previous'); this.next = el('button', 'Next'); this.label = el('span');
      for (const button of [this.previous, this.next]) {
        button.type = 'button'; button.disabled = true;
        button.addEventListener('click', () => { if (!button.disabled && button.destination) location.hash = button.destination; });
      }
      this.label.setAttribute('aria-live', 'polite'); pager.append(this.previous, this.label, this.next);
      this.root.append(this.status, pan, pager);
    }
    configure(params) {
      this.offset = Number(params?.get('offset') || 0);
      this.epoch = params?.get('epoch') || null;
      this.sort = columns.some(([key]) => key === params?.get('sort')) ? params.get('sort') : 'activity';
      this.direction = params?.get('direction') === '1' ? 1 : -1;
      this.generation++; this.rerun = true;
    }
    attach(parent) {
      if (this.root.parentNode !== parent) parent.replaceChildren(this.root);
      if (this.attached) return;
      this.attached = true; this.poll();
    }
    detach() { this.attached = false; this.generation++; clearTimeout(this.timer); }
    async poll() {
      if (!this.attached || this.busy) return;
      clearTimeout(this.timer);
      await this.load();
      if (this.attached) this.timer = setTimeout(() => this.poll(), this.rerun ? 0 : 5000);
    }
    async load() {
      if (this.busy) return;
      this.busy = true; this.rerun = false;
      this.pagerBusy();
      const generation = this.generation;
      try {
        const data = await this.api('/api/sessions', {token: this.token, offset: this.offset,
          epoch: this.epoch, sort: this.sort, direction: this.direction});
        if (!this.attached || generation !== this.generation) return;
        this.token = data.token; this.update(data);
      } catch (error) {
        if (!this.attached || generation !== this.generation) return;
        this.status.replaceChildren(el('span', `Sessions unavailable (${error.message}); last observed rows retained. `));
        if (error.message === 'catalog_expired') {
          this.token = null;
          const first = el('a', 'Return to page 1'); first.href = destination(0, null, this.sort, this.direction); this.status.append(first);
        }
        this.status.hidden = false;
        if (['instance_stopping', 'authentication_required', 'host_identity_changed'].includes(error.message)) this.detach();
      } finally {
        this.busy = false;
        this.pagerBusy();
      }
    }
    update(data) {
      this.data = data;
      this.status.textContent = [data.state === 'source_unavailable' ? 'Source unavailable; retained rows are not current.' :
        data.state === 'loading' ? 'Waiting for the shared session source…' : '',
        data.pending_sort ? `Global sort unavailable: indexed ${data.indexed} of ${data.available} sessions. Showing Last activity, newest first until ready.` : ''].filter(Boolean).join(' ');
      this.status.hidden = !this.status.textContent;
      for (const {key, name, th, label} of this.headers) {
        const active = key === data.sort;
        th.setAttribute('aria-sort', active ? data.direction === 1 ? 'ascending' : 'descending' : 'none');
        ReportView.text(label, name + (active ? data.direction === 1 ? ' ↑' : ' ↓' : ' ↕'));
      }
      const values = data.view.session_usage;
      // Lifecycle status must not remain falsely running while a title is selected.
      const observed = new Map(values.map(value => [value.session_id, value]));
      for (const row of this.body.children) {
        const running = Boolean(observed.get(row.dataset.id)?.running);
        row.className = running ? 'session-running' : '';
        if (row.runningMarker) ReportView.text(row.runningMarker, running ? '[RUNNING] ' : '');
      }
      if (!protectedNode(this.body)) this.rows(values);
      const pages = Math.max(1, Math.ceil(data.total / data.size));
      this.label.textContent = data.total ? `Showing ${data.offset + 1}–${Math.min(data.offset + 50, data.total)} of ${data.total} sessions · Page ${Math.floor(data.offset / 50) + 1} of ${pages}` :
        data.state === 'observed' ? 'No sessions · Page 1 of 1' : 'Session count unavailable';
      const link = (node, offset, enabled) => {
        node.destination = enabled ? destination(offset, data.epoch, this.sort, this.direction) : null;
      };
      link(this.previous, Math.max(0, data.offset - 50), data.offset > 0);
      link(this.next, data.offset + 50, data.offset + 50 < data.total);
      this.pagerBusy();
    }
    pagerBusy() {
      for (const button of [this.previous, this.next]) button.disabled = this.busy || !button.destination;
    }
    rows(values) {
      const old = new Map([...this.body.children].map(row => [row.dataset.id, row]));
      const wanted = new Set(values.map(row => row.session_id));
      for (const row of [...this.body.children]) if (!wanted.has(row.dataset.id)) row.remove();
      values.forEach((value, index) => {
        const row = old.get(value.session_id) || el('tr'); row.dataset.id = value.session_id;
        const signature = JSON.stringify(value);
        if (row.signature !== signature) {
          row.className = value.running ? 'session-running' : '';
          const name = el('a', undefined, 'session-name');
          row.runningMarker = el('span', value.running ? '[RUNNING] ' : '');
          name.append(row.runningMarker, el('span', value.title));
          if (/^[A-Za-z0-9_-]{1,200}$/.test(value.session_id)) name.href = '#/sessions/' + value.session_id;
          ContextHelp.value(name, value.title);
          const metric = text => {
            const state = value.metric_state || (value.indexed ? 'ready' : 'pending');
            const missing = !value.has_summary && !value.indexed && state !== 'retained';
            const node = el('span', missing ? state === 'pending' ? 'Loading…' : 'Unavailable' : text,
              missing ? 'session-metric-pending' : '');
            if (missing && state === 'pending') node.setAttribute('aria-busy', 'true');
            if (state !== 'ready') ContextHelp.value(node, state === 'pending' ? 'Session summary acquisition is pending.' :
              state === 'retained' ? 'Last observed summary retained; awaiting a valid current source observation.' : 'Session summary unavailable after source acquisition trouble.');
            return node;
          };
          const cells = [localTimestamp(value.last_activity_ms), name,
            metric(value.multiple_models ? 'Multiple models' : value.model || 'N/A'), metric(() => ReportView.display(value, 'ccost')),
            metric(value.prompt_count == null ? 'N/A' : String(value.prompt_count)), metric(() => ReportView.display(value, 'duration_ms'))];
          row.replaceChildren(...cells.map(content => { const td = el('td'); td.append(typeof content === 'object' ? content : el('span', content)); return td; }));
          row.signature = signature;
        }
        if (this.body.children[index] !== row) this.body.insertBefore(row, this.body.children[index] || null);
      });
    }
  }
  return {View, localTimestamp};
})();
