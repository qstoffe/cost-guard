'use strict';
// Independent retained table. Only same-origin prepared aggregates reach this view.
const BenchmarkView = (() => {
  const source = 'https://hub.harborframework.com/datasets/terminal-bench/terminal-bench/4';
  const names = ['Model', 'Coding Client', 'Effort', 'Relative Task Cost', 'USD/Task', 'Solved'];
  const keys = ['model', 'client', 'effort', 'relative_cost', 'usd_per_task', 'solved'];
  const helps = ['The model that ran this benchmark configuration.',
    'The coding agent application, such as Codex or Claude Code.',
    'The tested reasoning effort. Missing effort is not guessed.',
    'Cost per attempt relative to the cheapest comparable benchmark run (1.0x).',
    'Average US dollars spent per attempt, including failed attempts.',
    'Percentage of benchmark attempts solved successfully.'];
  class View {
    constructor() {
      const el = ReportView.element;
      this.root = el('section', undefined, 'benchmark-section');
      const heading = el('h2');
      heading.append(ContextHelp.value(el('span', 'Coding Benchmark – Cost per Task'),
        'Terminal-Bench 4.0 results depend on model, coding client and effort.\n\nThese are benchmark tasks, not your bills or predicted OpenCode costs.'));
      const provenance = el('div', undefined, 'benchmark-provenance');
      this.fetched = el('span');
      const link = el('a', 'View source'); link.href = source; link.target = '_blank'; link.rel = 'noopener noreferrer';
      provenance.append(el('span', 'Terminal-Bench 4.0 · Harbor Hub'), this.fetched, link);
      this.scroll = el('div', undefined, 'benchmark-scroll'); this.scroll.tabIndex = 0;
      this.scroll.setAttribute('role', 'region'); this.scroll.setAttribute('aria-label', 'Coding benchmark — scroll horizontally on narrow screens');
      this.table = el('table', undefined, 'benchmark-table'); this.table.setAttribute('aria-label', 'Coding Benchmark – Cost per Task');
      const head = el('thead'), row = el('tr'); this.body = el('tbody'); this.headers = [];
      this.sort = {index: 3, direction: -1}; this.data = {rows: []};
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
      this.root.append(heading, provenance, this.scroll, this.empty);
      this.checked = 0; this.loading = false; this.signature = '';
      this.draw();
    }
    attach(parent) { parent.append(this.root); }
    async load(api) {
      if (this.loading || Date.now() - this.checked < 5000) return;
      this.loading = true; this.checked = Date.now();
      try {
        const data = await api('/api/models/benchmark');
        const signature = JSON.stringify(data);
        if (signature !== this.signature) { this.data = data; this.signature = signature; this.draw(); }
      } catch (_) { /* Last-good rows/date survive network/host failure. */ }
      finally { this.loading = false; }
    }
    draw() {
      const el = ReportView.element, {index, direction} = this.sort;
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
      const rows = [...this.data.rows].sort((a, b) => compare(a, b, keys[index], direction) ||
        a.model.localeCompare(b.model) || a.client.localeCompare(b.client) ||
        (a.effort || '').localeCompare(b.effort || '') || a.id.localeCompare(b.id));
      this.body.replaceChildren();
      for (const item of rows) {
        const row = el('tr');
        const client = ContextHelp.value(el('span', item.client), item.configuration_help);
        for (const value of [el('span', item.model, item.recent ? 'new' : ''), client, item.effort || 'N/A',
          item.relative_text, item.usd_text, item.solved_text]) {
          const cell = el('td'); cell.append(typeof value === 'object' ? value : el('span', value)); row.append(cell);
        }
        this.body.append(row);
      }
      this.fetched.textContent = this.data.fetched_at_ms ? 'Last fetched: ' + new Date(this.data.fetched_at_ms).toLocaleString() : '';
      this.empty.hidden = rows.length > 0;
      this.scroll.hidden = rows.length === 0;
    }
  }
  return {View};
})();
