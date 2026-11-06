'use strict';
// Historical report presentation only: exact source values, no pricing or acquisition.
const TokenMixView = (() => {
  const categories = ['input', 'cache', 'write', 'output'];
  const names = ['Input', 'Cached input', 'Cache write', 'Output'];
  const definitions = ['Uncached input tokens.', 'Previously cached input tokens read by a request.',
    'Input tokens written to the cache.', 'Output tokens, including reasoning once.'];
  const e = (...args) => ReportView.element(...args);
  const tokenKey = 'mix_total_tokens';
  function numeric(row, column) {
    if (column === 1) return row.prompts;
    if (column === 2) return row.calls;
    if (column === 3) return row.mix.known_total_tokens;
    if (column === 12) return row.mix.priced_requests || !row.mix.request_count ? row.mix.total_cost : null;
    const index = Math.floor((column - 4) / 2);
    if (column % 2) return row.mix.priced_requests || !row.mix.request_count ? row.mix.costs?.[index] : null;
    // Cross multiplication preserves shares even beyond Decimal/IEEE-754 precision.
    return row.mix.shares?.[index] == null ? null :
      [BigInt(row.mix.exact_totals[index]), BigInt(row.mix.exact_total_tokens)];
  }
  function compare(a, b, direction) {
    if (a == null || b == null) return a == null ? b == null ? 0 : 1 : -1;
    if (Array.isArray(a)) {
      const left = a[0] * b[1], right = b[0] * a[1];
      return (left < right ? -1 : left > right ? 1 : 0) * direction;
    }
    return ReportView.compare(a, b) * direction;
  }
  function costHelp(mix) {
    return mix.cost_complete ? 'Reference valuation, not billing.' :
      `Partial reference valuation: ${mix.priced_requests} of ${mix.request_count} calls priced. Unknown prices are not zero.`;
  }
  class Table {
    constructor(key) {
      this.key = key; this.sort = {column: 12, direction: -1}; this.nodes = new Map();
      this.root = e('section', undefined, 'token-mix-section');
      const title = `Token Mix % by ${key}`;
      this.root.append(e('h3', title));
      const pan = e('div', undefined, 'token-mix-pan');
      pan.tabIndex = 0; pan.setAttribute('role', 'region'); pan.setAttribute('aria-label', title);
      const table = e('table', undefined, 'token-mix-table');
      const caption = e('caption', title, 'sr-only'); table.append(caption);
      const head = e('thead'), tr = e('tr');
      const columns = [key === 'model' ? 'Model' : 'Publisher', 'Prompts', 'Calls', 'Tokens',
        ...names.flatMap(name => [name + ' %', name + ' CCost']), 'Total CCost'];
      const help = [key === 'model' ? 'Canonical historical model display name.' : 'Model manufacturer, not an account provider.',
        'Distinct contributing user prompts. Mixed-model prompts can appear in several rows; counts are not additive.',
        'Attributed model requests in available shown history.',
        'Known Input, Cached input, Cache write and Output token volume. Partial means incomplete telemetry.',
        ...definitions.flatMap(text => [text + ' Share of tokens, not cost.', text + ' Per-request reference valuation, not share of cost.']),
        'Sum of known category reference valuations at each request’s actual model and price tier; not billing.'];
      this.headers = columns.map((label, column) => {
        const th = e('th'), button = e('button', label); th.scope = 'col'; button.type = 'button';
        ContextHelp.heading(button, help[column] + '\nActivate to sort; activate again to reverse. Unknown values stay last.');
        const arrow = e('span', '', 'sort-arrow'); arrow.setAttribute('aria-hidden', 'true'); button.append(arrow);
        button.addEventListener('click', () => {
          this.sort = {column, direction: this.sort.column === column ? -this.sort.direction : 1}; this.draw();
        });
        th.append(button); tr.append(th); return {th, arrow};
      });
      head.append(tr); this.body = e('tbody'); table.append(head, this.body); pan.append(table); this.root.append(pan);
    }
    update(rows) { this.rows = rows; this.draw(); }
    draw() {
      const {column, direction} = this.sort;
      this.headers.forEach(({th, arrow}, index) => {
        th.setAttribute('aria-sort', index === column ? direction === 1 ? 'ascending' : 'descending' : 'none');
        arrow.textContent = index === column ? direction === 1 ? ' ↑' : ' ↓' : '';
      });
      const value = row => column === 0 ? row[this.key] : numeric(row, column);
      const ordered = this.rows.map((row, index) => ({row, index})).sort((a, b) =>
        compare(value(a.row), value(b.row), direction) || compare(a.row.calls, b.row.calls, -1) ||
        a.row[this.key].localeCompare(b.row[this.key], undefined, {numeric: true}) || a.index - b.index);
      const retained = new Set(), occurrences = new Map();
      ordered.forEach(({row}, index) => {
        const name = row[this.key], occurrence = occurrences.get(name) || 0;
        occurrences.set(name, occurrence + 1);
        const key = JSON.stringify([name, occurrence]); retained.add(key);
        let node = this.nodes.get(key);
        if (!node) {
          node = {root: e('tr'), cells: [], help: new Set()};
          for (let col = 0; col < 13; col++) {
            const td = e('td'), span = e('span'); td.append(span); node.root.append(td); node.cells.push(span);
          }
          this.nodes.set(key, node);
        }
        node.row = row;
        node.cells.forEach((span, col) => {
          const key = col === 3 ? tokenKey : col === 12 ? 'mix_total_cost' :
            col >= 4 ? 'mix_' + categories[Math.floor((col - 4) / 2)] + (col % 2 ? '_cost' : '_share') : null;
          ReportView.text(span, () => col === 0 ? node.row[this.key] : col === 1 ? node.row.prompts :
            col === 2 ? node.row.calls : ReportView.display(node.row.mix, key));
          const tokenHelp = col === 3 && (row.mix.exact_total_tokens == null ||
            ReportView.display(row.mix, tokenKey) !== row.mix.known_total_tokens);
          const partialCost = (col >= 4 && col % 2 || col === 12) && !row.mix.cost_complete;
          if ((tokenHelp || partialCost) && !node.help.has(col)) {
            node.help.add(col);
            ContextHelp.value(span, () => col === 3 ?
              `${node.row.mix.known_total_tokens ?? 'No known'} recorded tokens.${node.row.mix.exact_total_tokens == null ? ' Partial telemetry; a complete total and shares are unavailable.' : ''}` : costHelp(node.row.mix));
          }
          if (col >= 4 && col % 2 || col === 12) {
            span.classList.toggle('partial', !row.mix.cost_complete);
          }
          ContextHelp.refresh(span);
        });
        // Never remove/reinsert unchanged rows: preserve focus, selection and scroll anchors.
        if (this.body.children[index] !== node.root) this.body.insertBefore(node.root, this.body.children[index] || null);
      });
      for (const [key, node] of this.nodes) if (!retained.has(key)) { node.root.remove(); this.nodes.delete(key); }
    }
  }
  class View {
    constructor() {
      this.root = e('div', undefined, 'token-mix-view');
      this.title = e('h2');
      ContextHelp.value(this.title, () => `${this.result.view.token_mix.known_total_tokens ?? 'No known'} recorded tokens in the same available shown history as the CLI. Deleted history is not reconstructed.\nObserved ${new Date(this.result.observed_at_ms).toLocaleString()}.`);
      this.summary = e('div', undefined, 'token-mix-summary');
      this.metrics = categories.map((key, index) => {
        const group = e('div'), label = e('span', names[index]), value = e('strong');
        ContextHelp.value(label, definitions[index]);
        ReportView.text(value, () => this.result ? ReportView.display(this.result.view.token_mix, 'mix_' + key + '_share') +
          ' · ' + ReportView.display(this.result.view.token_mix, 'mix_' + key + '_cost') : 'N/A');
        group.append(label, value); this.summary.append(group); return value;
      });
      this.status = e('p', '', 'token-mix-status'); this.status.setAttribute('role', 'status');
      this.models = new Table('model'); this.publishers = new Table('publisher');
      this.root.append(this.title, this.summary, this.status, this.models.root, this.publishers.root);
    }
    update(result) {
      if (this.result === result) return;
      this.result = result;
      ReportView.text(this.title, () => `Total Token Mix % · ${ReportView.display(this.result.view.token_mix, tokenKey)} tokens`);
      this.metrics.forEach(value => ReportView.syncUnits(value));
      const view = result.view;
      const issues = [ReportView.historyWarning(result),
        view.historical_source_gap && 'Legacy history is missing from this source; sources are not merged.',
        view.model_availability_unverified && 'Selectable models unverified.',
        !view.token_mix.cost_complete && 'Partial pricing.',
        view.token_mix.exact_total_tokens == null && 'Incomplete token telemetry.',
        !view.model_token_mix.length && 'No available historical usage.'];
      this.status.textContent = issues.filter(Boolean).join(' '); this.status.hidden = !this.status.textContent;
      this.models.update(view.model_token_mix); this.publishers.update(view.publisher_token_mix);
    }
    attach(parent) { if (parent.firstChild !== this.root) parent.replaceChildren(this.root); }
  }
  function valid(result) {
    const view = result?.view;
    const integer = value => typeof value === 'string' && /^\d+$/.test(value);
    const decimal = value => typeof value === 'string' && /^\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(value);
    const count = value => Number.isSafeInteger(value) && value >= 0;
    const vector = (value, check) => Array.isArray(value) && value.length === 4 && value.every(check);
    const nullable = check => value => value === null || check(value);
    const mix = value => value && count(value.request_count) && count(value.priced_requests) &&
      value.priced_requests <= value.request_count && typeof value.cost_complete === 'boolean' &&
      nullable(integer)(value.known_total_tokens) && nullable(integer)(value.exact_total_tokens) &&
      nullable(decimal)(value.total_cost) && vector(value.shares, nullable(decimal)) &&
      vector(value.exact_totals, nullable(integer)) && (value.costs === null || vector(value.costs, decimal)) &&
      (value.exact_total_tokens === null ? value.shares.every(share => share === null) :
        value.exact_totals.every(integer) && value.shares.every(share => share === null || BigInt(value.exact_total_tokens) > 0n)) &&
      ['mix_total_tokens', 'mix_total_cost', ...categories.flatMap(key => ['mix_' + key + '_share', 'mix_' + key + '_cost'])]
        .every(key => typeof value.display?.[key] === 'string');
    return Number.isFinite(result?.observed_at_ms) && typeof result?.source?.status === 'string' &&
      view?.kind === 'token-mix' && mix(view.token_mix) && ['model', 'publisher'].every(key =>
        Array.isArray(view[key + '_token_mix']) && view[key + '_token_mix'].every(row =>
          typeof row[key] === 'string' && count(row.prompts) && count(row.calls) && mix(row.mix)));
  }
  return {View, compare, numeric, valid};
})();
