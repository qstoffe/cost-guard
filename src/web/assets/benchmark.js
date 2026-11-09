'use strict';
// Independent retained table. Only same-origin prepared aggregates reach this view.
const BenchmarkView = (() => {
  const source = 'https://hub.harborframework.com/datasets/terminal-bench/terminal-bench/4';
  const names = ['Publisher', 'Model', 'Effort', 'Relative Task Cost', 'Solved'];
  const keys = ['publisher', 'model', 'effort', 'relative_cost', 'solved'];
  const helps = ['The matched GitHub catalog’s model developer/manufacturer.',
    'The matched GitHub model. The name reveals this configuration’s coding client.',
    'The tested reasoning effort. Missing effort is not guessed.',
    'Cost per attempt relative to the cheapest comparable benchmark run (1.0x).',
    'Percentage of benchmark attempts solved successfully.'];
  class View {
    constructor() {
      const el = ReportView.element;
      this.root = el('section', undefined, 'benchmark-section');
      const heading = el('h2');
      heading.append(ContextHelp.value(el('span', 'Coding Benchmark – Cost per Task'),
        'Terminal-Bench 4.0 results depend on model, coding client and effort.\n\nThese are benchmark tasks, not your bills or predicted OpenCode costs.'));
      const provenance = el('div', undefined, 'model-price-controls');
      this.fetched = el('span');
      const link = el('a', 'View source'); link.href = source; link.target = '_blank'; link.rel = 'noopener noreferrer';
      this.refresh = el('button', 'Refresh benchmark');
      this.refresh.setAttribute('data-benchmark-control', 'refresh');
      this.refresh.addEventListener('click', () => this.refreshSource());
      this.status = el('span'); this.status.setAttribute('role', 'status');
      provenance.append(el('span', 'Terminal-Bench 4.0 · Harbor Hub'), link, this.refresh, this.fetched, this.status);
      this.choice = {all: false, latest: true, efforts: null};
      const filters = el('div', undefined, 'model-filters benchmark-filters');
      this.picker = el('details', undefined, 'effort-picker'); this.summary = el('summary');
      this.options = el('div', undefined, 'effort-options'); this.picker.append(this.summary, this.options);
      filters.append(this.picker);
      for (const [key, text] of [['all', 'Show all Copilot-priced models'], ['latest', 'Latest versions only']]) {
        const label = el('label'), input = el('input'); input.type = 'checkbox'; input.checked = this.choice[key];
        input.setAttribute('data-benchmark-control', key);
        input.addEventListener('change', () => { this.choice[key] = input.checked; this.draw(); });
        label.append(input, el('span', text)); filters.append(label);
      }
      document.addEventListener?.('click', event => { if (!this.picker.contains(event.target)) this.picker.open = false; });
      this.picker.addEventListener('keydown', event => {
        if (event.key === 'Escape') { this.picker.open = false; this.summary.focus(); event.preventDefault(); }
      });
      const tools = el('div', undefined, 'model-tools benchmark-tools'); tools.append(provenance, filters);
      this.scroll = el('div', undefined, 'benchmark-scroll'); this.scroll.tabIndex = 0;
      this.scroll.setAttribute('role', 'region'); this.scroll.setAttribute('aria-label', 'Coding benchmark — scroll horizontally on narrow screens');
      this.table = el('table', undefined, 'benchmark-table'); this.table.setAttribute('aria-label', 'Coding Benchmark – Cost per Task');
      const head = el('thead'), row = el('tr'); this.body = el('tbody'); this.headers = [];
      this.sort = {index: 3, direction: -1}; this.data = {rows: [], efforts: []}; this.effortSignature = '';
      names.forEach((name, index) => {
        const th = el('th'), button = el('button', name); th.scope = 'col';
        button.setAttribute('data-benchmark-control', String(index));
        const label = ContextHelp.heading(button, helps[index]);
        button.addEventListener('click', () => {
          this.sort = {index, direction: this.sort.index === index ? -this.sort.direction : index < 3 ? 1 : -1};
          this.draw();
        });
        th.append(button); row.append(th); this.headers.push([th, button, label]);
      });
      head.append(row); this.table.append(head, this.body); this.scroll.append(this.table);
      this.empty = el('p', 'Benchmark unavailable / no benchmark data yet', 'benchmark-empty');
      this.root.append(heading, tools, this.scroll, this.empty);
      this.checked = 0; this.loading = false; this.signature = '';
      this.draw();
    }
    attach(parent) { parent.append(this.root); }
    controls(writable, api = this.api) {
      this.writable = writable; this.api = api;
      this.refresh.disabled = !writable || this.loading || this.manual || !!this.data.refreshing;
      this.refresh.setAttribute('aria-disabled', String(this.refresh.disabled));
    }
    async refreshSource() {
      if (!this.api || this.refresh.disabled) return;
      this.manual = true; this.status.textContent = 'Refreshing…'; this.controls(this.writable);
      try {
        await this.api('/api/models/benchmark/refresh', {});
        await this.load(this.api, true);
      } catch (_) {
        this.manual = false; this.status.textContent = 'Refresh failed; previous benchmark retained.';
      } finally { this.controls(this.writable); }
    }
    async load(api, force = false) {
      if (this.loading || !force && Date.now() - this.checked < 5000) return;
      this.loading = true; this.checked = Date.now();
      this.controls(this.writable, api);
      try {
        const data = await api('/api/models/benchmark');
        const signature = JSON.stringify(data);
        if (signature !== this.signature) { this.data = data; this.signature = signature; this.draw(); }
        if (!data.refreshing && this.manual) {
          this.manual = false;
          this.status.textContent = data.unavailable ? 'Refresh failed; previous benchmark retained.' : 'Benchmark refreshed.';
        } else if (data.refreshing) this.status.textContent = 'Refreshing…';
        else if (!this.manual) this.status.textContent = data.unavailable ? 'Benchmark unavailable; previous data retained.' : '';
      } catch (_) { /* Last-good rows/date survive network/host failure. */ }
      finally { this.loading = false; this.controls(this.writable); }
    }
    efforts() {
      const el = ReportView.element, available = this.data.efforts || [], selected = this.choice.efforts;
      if (selected) for (const key of selected) if (!available.includes(key)) selected.delete(key);
      const signature = JSON.stringify(available);
      if (signature !== this.effortSignature) {
        const focused = (this.effortInputs || []).find(([, input]) => input === document.activeElement);
        this.options.replaceChildren(); this.effortInputs = [];
        for (const key of available) {
          const label = el('label'), input = el('input'); input.type = 'checkbox';
          input.addEventListener('change', () => {
            this.choice.efforts ||= new Set(available);
            if (input.checked) this.choice.efforts.add(key); else this.choice.efforts.delete(key);
            if (available.every(value => this.choice.efforts.has(value))) this.choice.efforts = null;
            this.draw();
          });
          label.append(input, el('span', key ? key[0].toUpperCase() + key.slice(1) : 'Not specified'));
          this.options.append(label); this.effortInputs.push([key, input]);
        }
        this.effortSignature = signature;
        if (focused) (this.effortInputs.find(([key]) => key === focused[0])?.[1] || this.summary).focus();
      }
      for (const [key, input] of this.effortInputs || []) input.checked = !selected || selected.has(key);
      this.summary.textContent = 'Effort levels · ' + (!selected ? 'All' : !selected.size ? 'None' :
        selected.size === 1 ? [...selected][0] || 'Not specified' : selected.size + ' of ' + available.length);
    }
    draw() {
      const el = ReportView.element, {index, direction} = this.sort;
      this.efforts();
      this.headers.forEach(([th, button, label], column) => {
        const active = column === index, order = direction === 1 ? 'ascending' : 'descending';
        th.setAttribute('aria-sort', active ? order : 'none');
        label.textContent = names[column] + (active ? direction === 1 ? ' ↑' : ' ↓' : ' ↕');
        button.setAttribute('aria-label', names[column] + (active ? ', ' + order : ', not sorted') + '. Activate to sort.');
      });
      const compare = (a, b, key, dir) => {
        if (a[key] == null || b[key] == null) return a[key] == null ? b[key] == null ? 0 : 1 : -1;
        return ReportView.sortedCompare(a[key], b[key], dir);
      };
      const rows = this.data.rows.filter(row => (this.choice.all || row.selectable !== false) &&
        (!this.choice.latest || !(this.choice.all ? row.superseded : row.superseded_selectable)) &&
        (!this.choice.efforts || this.choice.efforts.has(row.effort || ''))).sort((a, b) => compare(a, b, keys[index], direction) ||
        a.model.localeCompare(b.model) || a.client.localeCompare(b.client) ||
        (a.effort || '').localeCompare(b.effort || '') || a.id.localeCompare(b.id));
      this.body.replaceChildren();
      for (const item of rows) {
        const row = el('tr');
        const model = ContextHelp.value(el('span', item.model, item.recent ? 'new' : ''), item.configuration_help);
        const cost = ContextHelp.value(el('span', item.relative_text), item.task_help);
        for (const value of [item.publisher, model, item.effort || 'N/A', cost, item.solved_text]) {
          const cell = el('td'); cell.append(typeof value === 'object' ? value : el('span', value)); row.append(cell);
        }
        this.body.append(row);
      }
      this.fetched.textContent = 'Last fetched: ' + (this.data.fetched_text || 'Unavailable');
      this.empty.textContent = this.data.fetched_at_ms ? 'No matching benchmark rows' : 'Benchmark unavailable / no benchmark data yet';
      this.empty.hidden = rows.length > 0;
      this.scroll.hidden = rows.length === 0;
    }
  }
  return {View};
})();
