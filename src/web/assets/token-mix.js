'use strict';
// Historical report presentation only: exact source values, no pricing or acquisition.
const TokenMixView = (() => {
  const categories = ['input', 'cache', 'write', 'output'];
  const names = ['Input', 'Cached input', 'Cache write', 'Output'];
  const definitions = ['Uncached input tokens.', 'Previously cached input tokens read by a request.',
    'Input tokens written to the cache.', 'Output tokens, including reasoning once.'];
  const e = (...args) => ReportView.element(...args);
  const tokenKey = 'mix_total_tokens';
  const periods = [['today', 'Today'], ['7-days', '7 days'], ['30-days', '30 days'], ['month', 'This month'], ['all', 'All time']];
  const display = (mix, key) => ReportView.display(mix, key);
  function compatible(result, selected) {
    const {token_mix_period: period, timezone_id: zone} = result.view;
    const configured = ReportView.configuredTimezone();
    if (period?.period !== selected || configured && result.scope?.timezone_id && zone !== configured) return false;
    if (selected === 'all') return true;
    const day = ms => ReportView.formatDateTime(ms, ReportView.DateTimeMode.DATE, zone);
    const now = day(Date.now()), observed = day(period.end_ms);
    return now !== 'N/A' && (selected === 'month' ? now.slice(0, 7) === observed.slice(0, 7) : now === observed);
  }
  function titleHelp(result) {
    const {token_mix: mix, token_mix_period: period, timezone_id: zone} = result.view;
    const quantity = BigInt(mix.observed_total_tokens).toLocaleString('en-US');
    const boundary = value => {
      if (!Number.isSafeInteger(value)) return null;
      return ReportView.timestamp(value, zone);
    };
    return [`${quantity} recorded tokens for the selected period`,
      [boundary(period?.start_ms), boundary(period?.end_ms)].filter(Boolean).join(' – ')].filter(Boolean).join('\n');
  }
  function numeric(row, column) {
    if (column === 1) return row.prompts;
    if (column === 2) return row.calls;
    if (column === 3) return row.mix.observed_total_tokens;
    if (column === 8) return row.mix.total_cost;
    const index = column - 4;
    // Cross multiplication preserves shares even beyond Decimal/IEEE-754 precision.
    const total = BigInt(row.mix.observed_total_tokens);
    return [BigInt(row.mix.observed_totals[index]), total || 1n];
  }
  function compare(a, b, direction) {
    if (a == null || b == null) return a == null ? b == null ? 0 : 1 : -1;
    if (Array.isArray(a)) {
      const left = a[0] * b[1], right = b[0] * a[1];
      return (left < right ? -1 : left > right ? 1 : 0) * direction;
    }
    return ReportView.compare(a, b) * direction;
  }
  class Table {
    constructor(key) {
      this.key = key; this.offset = key === 'model' ? 1 : 0;
      this.sort = {column: 8 + this.offset, direction: -1}; this.nodes = new Map();
      this.root = e('section', undefined, 'token-mix-section');
      const title = `Token Mix % by ${key}`;
      this.root.append(e('h3', title));
      const pan = e('div', undefined, 'token-mix-pan');
      pan.tabIndex = 0; pan.setAttribute('role', 'region'); pan.setAttribute('aria-label', title);
      const table = e('table', undefined, 'token-mix-table');
      const caption = e('caption', title, 'sr-only'); table.append(caption);
      const head = e('thead'), tr = e('tr');
      const columns = [...(this.offset ? ['Publisher', 'Model'] : ['Publisher']), 'Prompts', 'Calls', 'Tokens',
        ...names.map(name => name + ' %'), 'Total CCost'];
      const help = ['Model manufacturer, not an account provider.', ...(this.offset ? [null] : []),
        'Distinct logical prompts in each executing session, including recorded child prompts. Mixed-model prompts can appear in several rows; counts are not additive.',
        'Attributed model requests in available shown history.',
         'Recorded Input, Cached input, Cache write and Output token volume.',
        ...definitions.map(text => text + ' Share of tokens, not cost.'),
        'Sum of known category reference valuations at each request’s actual model and price tier; not billing.'];
      this.headers = columns.map((label, column) => {
        const th = e('th'), button = e('button', label); th.scope = 'col'; button.type = 'button';
        if (help[column]) ContextHelp.heading(button, help[column]);
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
      const value = row => column === 0 ? row.publisher : this.offset && column === 1 ? row.model :
        numeric(row, column - this.offset);
      const ordered = this.rows.map((row, index) => ({row, index})).sort((a, b) =>
        compare(value(a.row), value(b.row), direction) || compare(a.row.calls, b.row.calls, -1) ||
        a.row[this.key].localeCompare(b.row[this.key], undefined, {numeric: true}) || a.index - b.index);
      const retained = new Set();
      ordered.forEach(({row}, index) => {
        const key = row.identity || row.publisher; retained.add(key);
        let node = this.nodes.get(key);
        if (!node) {
          node = {root: e('tr'), cells: [], help: new Set()};
          for (let col = 0; col < 9 + this.offset; col++) {
            const td = e('td'), span = e('span'); td.append(span); node.root.append(td); node.cells.push(span);
          }
          this.nodes.set(key, node);
        }
        node.row = row;
        node.cells.forEach((span, col) => {
          const metric = col - this.offset;
          const key = metric === 3 ? tokenKey : metric === 8 ? 'mix_total_cost' :
            metric >= 4 ? 'mix_' + categories[metric - 4] + '_share' : null;
          ReportView.text(span, () => col === 0 ? node.row.publisher : this.offset && col === 1 ? node.row.model :
            metric === 1 ? node.row.prompts : metric === 2 ? node.row.calls : display(node.row.mix, key));
          const category = metric >= 4 && metric < 8;
          if (category && !node.help.has(col)) {
            node.help.add(col);
            ContextHelp.value(span, () => ReportView.display(node.row.mix, 'mix_' + categories[metric - 4] + '_cost_help'));
          }
          ContextHelp.refresh(span);
        });
        // Never remove/reinsert unchanged rows: preserve focus, selection and scroll anchors.
        if (this.body.children[index] !== node.root) {
          const before = this.body.children[index] || null;
          if (node.root.parentNode === this.body && this.body.moveBefore) this.body.moveBefore(node.root, before);
          else this.body.insertBefore(node.root, before);
        }
      });
      for (const [key, node] of this.nodes) if (!retained.has(key)) { node.root.remove(); this.nodes.delete(key); }
    }
  }
  class View {
    constructor(select = () => {}) {
      this.root = e('div', undefined, 'token-mix-view');
      this.selector = e('div', undefined, 'ai-stats-periods');
      this.selector.setAttribute('role', 'group'); this.selector.setAttribute('aria-label', 'Token Mix period');
      this.buttons = periods.map(([id, label]) => {
        const button = e('button', label); button.type = 'button';
        button.addEventListener('click', () => select(id)); this.selector.append(button); return {id, button};
      });
      this.content = e('div');
      this.title = e('h2');
      ContextHelp.value(this.title, () => this.result?.view.token_mix ? titleHelp(this.result) : '');
      this.summary = e('div', undefined, 'token-mix-summary');
      this.metrics = categories.map((key, index) => {
        const group = e('div'), label = e('span', names[index]), value = e('strong');
        ReportView.text(value, () => this.result?.view.token_mix ? display(this.result.view.token_mix, 'mix_' + key + '_share') : '');
        ContextHelp.value(value, () => this.result?.view.token_mix ? display(this.result.view.token_mix, 'mix_' + key + '_cost_value') : '');
        group.append(label, value); this.summary.append(group); return value;
      });
      this.status = e('p', '', 'token-mix-status');
      this.models = new Table('model'); this.publishers = new Table('publisher');
      this.content.append(this.status, this.title, this.summary, this.models.root, this.publishers.root);
      this.root.append(this.selector, this.content);
    }
    selection(period, ready) {
      this.buttons.forEach(({id, button}) => button.setAttribute('aria-pressed', String(id === period)));
      this.content.hidden = !ready;
    }
    update(result) {
      if (this.result === result) return;
      this.result = result;
      const view = result.view;
      const coverage = view.token_mix_period?.coverage;
      const hasUsage = !!view.model_token_mix.length || !!view.token_mix?.request_count;
      const unknown = coverage === 'unknown' || !hasUsage && result.source.status === 'partial';
      for (const node of [this.title, this.summary, this.models.root, this.publishers.root])
        node.hidden = unknown;
      ReportView.text(this.status, unknown ? 'Usage for this period could not be verified yet.' :
        coverage === 'partial' ? 'Showing verified usage only. Some history could not be checked.' :
          hasUsage ? '' : 'No usage yet.');
      this.status.hidden = !this.status.textContent;
      if (unknown) return;
      ReportView.text(this.title, () => this.result.view.token_mix ?
        `Total Token Mix % · ${display(this.result.view.token_mix, tokenKey)} tokens` : '');
      ContextHelp.refresh(this.title);
      this.metrics.forEach(value => ReportView.syncUnits(value));
      this.models.update(view.model_token_mix); this.publishers.update(view.publisher_token_mix);
    }
    attach(parent) { if (parent.firstChild !== this.root) parent.replaceChildren(this.root); }
  }
  function valid(result) {
    const view = result?.view;
    const period = view?.token_mix_period;
    if (period != null && (!periods.some(([id]) => id === period.period) ||
        ![period.start_ms, period.end_ms].every(value => value === null || Number.isSafeInteger(value)) ||
        (period.period !== 'all' && (period.start_ms === null || period.end_ms === null)) ||
         (period.start_ms !== null && period.end_ms !== null && period.start_ms > period.end_ms) ||
         (period.coverage !== undefined && !['unknown', 'partial'].includes(period.coverage)))) return false;
    if (!Number.isFinite(result?.observed_at_ms) || !['acquired', 'partial'].includes(result?.source?.status) ||
        view?.kind !== 'token-mix') return false;
    if (period?.coverage === 'unknown') return result.source.status === 'partial' && view.token_mix === null &&
      ['model', 'publisher'].every(key => Array.isArray(view[key + '_token_mix']) && !view[key + '_token_mix'].length);
    const integer = value => typeof value === 'string' && /^\d+$/.test(value);
    const decimal = value => typeof value === 'string' && /^\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(value);
    const count = value => Number.isSafeInteger(value) && value >= 0;
    const vector = (value, check) => Array.isArray(value) && value.length === 4 && value.every(check);
    const nullable = check => value => value === null || check(value);
    const mix = value => value && count(value.request_count) && count(value.priced_requests) &&
      value.priced_requests <= value.request_count && typeof value.cost_complete === 'boolean' &&
      nullable(integer)(value.known_total_tokens) && nullable(integer)(value.exact_total_tokens) &&
      nullable(decimal)(value.total_cost) && vector(value.shares, nullable(decimal)) &&
      vector(value.observed_totals, integer) && integer(value.observed_total_tokens) &&
      value.observed_totals.reduce((sum, item) => sum + BigInt(item), 0n) === BigInt(value.observed_total_tokens) &&
      vector(value.exact_totals, nullable(integer)) && (value.costs === null || vector(value.costs, decimal)) &&
      (value.exact_total_tokens === null ? value.shares.every(share => share === null) :
        value.exact_totals.every(integer) && value.shares.every(share => share === null || BigInt(value.exact_total_tokens) > 0n)) &&
      ['mix_total_tokens', 'mix_total_cost', ...categories.flatMap(key => ['mix_' + key + '_share', 'mix_' + key + '_cost'])]
        .every(key => typeof value.display?.[key] === 'string');
    return mix(view.token_mix) && ['model', 'publisher'].every(key =>
        Array.isArray(view[key + '_token_mix']) && view[key + '_token_mix'].every(row =>
          typeof row[key] === 'string' && (key !== 'model' || typeof row.publisher === 'string' && typeof row.identity === 'string') &&
          count(row.prompts) && count(row.calls) && mix(row.mix)));
  }
  return {View, compare, numeric, valid, compatible};
})();
