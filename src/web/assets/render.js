'use strict';
// Presentation only. Decimal strings and canonical totals are never recalculated.
const ReportView = (() => {
  const known = value => value === null || value === undefined ? 'Unknown' : String(value);
  // Missing tokens are not a license to expose raw Decimal strings or calculate in JS.
  let unit = null;
  let quotaMode = 'used';
  const bindings = new WeakMap();
  const effects = new WeakMap();
  function bind(node, update) { effects.set(node, update); update(); }
  function setQuotaMode(value) { if (['used', 'remaining'].includes(value)) quotaMode = value; }
  function quotaView(quota, watch) {
    return quota.quota_display?.[quotaMode] || {mode: 'used', native: display(quota, 'quota_used'),
      money: display(quota, 'used_money'), account_percent: display(quota, 'used_fraction'),
      fraction: watch?.used_fraction, percent: watch?.used_percent, exhausted: watch?.exhausted, note: ''};
  }
  const display = (row, key) => row?.display_units?.[unit]?.[key] ?? row?.display?.[key] ?? 'N/A';
  function quotaHelp(quota) {
    const view = quotaView(quota), native = quota.quota_display;
    return `${display(quota, 'ccost_help')}\nCapacity: ${display(quota, 'ccost_capacity')}\n` +
      `${quota.label} · ${quota.period} · ${quota.scope}${quota.model_id ? ' · ' + quota.model_id : ''}\n` +
      `Native Used: ${native?.used.native || view.native}\nNative Remaining: ${native?.remaining.mode === 'remaining' ? native.remaining.native : 'unknown / inapplicable'}\n` +
      `Native money ${view.mode}: ${view.money} / ${display(quota, 'limit_money')}\n` +
      `${display(quota, 'reset')} · Source: ${quota.origin}\nAvailability: ${quota.availability}` + (view.note ? '\n' + view.note : '');
  }
  const mixLabels = row => Object.values(row?.display?.token_categories || {});
  const mixText = row => Object.entries(row?.display?.token_categories || {})
    .map(([key, label]) => label + ': ' + display(row, key)).join(' · ');
  const mixLegend = row => display(row, 'token_category_legend') + '. Output includes reasoning.';
  function text(node, value) {
    if (typeof value === 'function') { bindings.set(node, value); value = value(); }
    else bindings.delete(node);
    const content = String(value);
    if (node.textContent === content) return;
    // Keep text-node identity (and browser selection/anchors) when switching.
    if (node.childNodes?.length === 1 && node.firstChild.nodeType === 3) {
      const leaf = node.firstChild, oldLength = leaf.length;
      const selection = typeof window !== 'undefined' ? window.getSelection?.() : null;
      const anchor = selection?.anchorNode, focus = selection?.focusNode;
      const start = selection?.anchorOffset, end = selection?.focusOffset;
      leaf.data = content;
      if (anchor === leaf || focus === leaf) {
        const offset = value => value && value === oldLength ? content.length : Math.min(value, content.length);
        selection.setBaseAndExtent(anchor, anchor === leaf ? offset(start) : start,
          focus, focus === leaf ? offset(end) : end);
      }
    } else node.textContent = content;
  }
  function syncUnits(root, nested = false) {
    effects.get(root)?.();
    const binding = bindings.get(root);
    if (binding) text(root, binding);
    for (const child of root.children) syncUnits(child, true);
    if (!nested) ContextHelp.refresh(root);
  }
  function setUnit(value, root) {
    if (!['credits', 'usd'].includes(value)) return;
    unit = value;
    if (root) syncUnits(root);
  }
  function defaultUnit() {
    if (unit !== null) return;
    // The CLI/report default must never override an independent Web preference.
    // Startup reads file-backed Settings before connecting to report publications.
    setUnit('credits');
  }
  const ccost = (row, key = 'ccost') => display(row, key) +
    (row?.cost_estimated && key === 'ccost' ? ' (estimated)' : '');
  function element(tag, content, className) {
    const node = document.createElement(tag);
    if (content !== undefined) text(node, content);
    if (className) node.className = className;
    return node;
  }
  function link(id) {
    const node = element('a', id);
    // Match the API locator allowlist; never turn arbitrary source text into a URL.
    if (/^[A-Za-z0-9_-]{1,200}$/.test(id)) node.href = '#/sessions/' + id;
    return node;
  }
  // Compare decimal strings exactly (including exponent notation), without Number coercion.
  function compare(a, b) {
    if (Array.isArray(a) && Array.isArray(b)) {
      for (let i = 0; i < Math.max(a.length, b.length); i++) {
        if (a[i] == null || b[i] == null) { if (a[i] !== b[i]) return a[i] == null ? 1 : -1; }
        else { const order = compare(a[i], b[i]); if (order) return order; }
      }
      return 0;
    }
    const parse = value => {
      const m = /^([+-]?)(\d+)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/.exec(String(value));
      if (!m) return null;
      const digits = (m[2] + (m[3] || '')).replace(/^0+/, '').replace(/0+$/, '');
      const original = (m[2] + (m[3] || '')).replace(/^0+/, '');
      return {sign: digits ? m[1] === '-' ? -1 : 1 : 0, digits,
        magnitude: BigInt(original.length) + BigInt(m[4] || '0') - BigInt((m[3] || '').length)};
    };
    const x = parse(a), y = parse(b);
    if (x && y) {
      if (x.sign !== y.sign) return x.sign < y.sign ? -1 : 1;
      if (!x.sign) return 0;
      if (x.magnitude !== y.magnitude) return (x.magnitude < y.magnitude ? -1 : 1) * x.sign;
      const size = Math.max(x.digits.length, y.digits.length);
      const left = x.digits.padEnd(size, '0'), right = y.digits.padEnd(size, '0');
      return (left < right ? -1 : left > right ? 1 : 0) * x.sign;
    }
    return String(a).localeCompare(String(b));
  }
  function sortedCompare(a, b, direction) {
    if (a == null || b == null) return a == null ? b == null ? 0 : 1 : -1;
    if (Array.isArray(a) && Array.isArray(b)) {
      for (let i = 0; i < Math.max(a.length, b.length); i++) {
        const order = sortedCompare(a[i], b[i], direction);
        if (order) return order;
      }
      return 0;
    }
    return compare(a, b) * direction;
  }
  function table(parent, title, columns, rows, cells, totals, state, key, values = cells) {
    const section = element('section');
    const remote = key === 'sessions' ? state.result?.view?.session_page : null;
    state.filters ||= {}; state.sorts ||= {};
    const filterLabel = element('label', 'Filter ' + title + (remote ? ' (this page only) ' : ' ')), filter = element('input');
    filter.type = 'search'; filter.value = state.filters[key] || ''; filterLabel.append(filter); section.append(filterLabel);
    const scroll = element('div', undefined, 'table-scroll');
    scroll.tabIndex = 0;
    scroll.setAttribute('role', 'region');
    scroll.setAttribute('aria-label', title);
    const grid = element('table');
    grid.append(element('caption', title));
    const head = element('thead'), header = element('tr');
    const headers = [];
    columns.forEach((column, index) => {
      const th = element('th'), button = element('button', column); th.scope = 'col';
      ContextHelp.attach(button, 'Sort this column; activate again to reverse or clear sorting.\nUnknown values stay last. Sorting does not change totals.');
      button.addEventListener('click', () => {
        const old = state.sorts[key];
        if (old?.index === index && old.direction === -1) delete state.sorts[key];
        else state.sorts[key] = {index, direction: old?.index === index ? -old.direction : 1};
        state.pages[key] = 0; draw();
      });
      th.append(button); header.append(th); headers.push(th);
    });
    head.append(header); grid.append(head);
    const body = element('tbody'); grid.append(body);
    if (totals) {
      const foot = element('tfoot'), row = element('tr');
      for (let index = 0; index < totals().length; index++) row.append(element('td', () => totals()[index]));
      foot.append(row); grid.append(foot);
    }
    scroll.append(grid); section.append(scroll); parent.append(section);
    const pager = element('div', undefined, 'pager');
     const previous = element(remote ? 'a' : 'button', 'Previous'), next = element(remote ? 'a' : 'button', 'Next');
    const label = element('span'); label.setAttribute('aria-live', 'polite');
    previous.setAttribute('aria-label', 'Previous page: ' + title);
    next.setAttribute('aria-label', 'Next page: ' + title);
    pager.append(previous);
    pager.append(label);
    pager.append(next);
    section.append(pager);
    const size = 50;
    function draw() {
      const text = value => value && typeof value === 'object' ? value.textContent : known(value);
      const queries = [state.search, state.filters[key]].filter(Boolean).map(q => q.toLocaleLowerCase());
      const shown = rows.filter(row => queries.every(q => cells(row).map(text).join(' ').toLocaleLowerCase().includes(q)));
      const sort = state.sorts[key];
      headers.forEach((th, index) => th.setAttribute('aria-sort', sort?.index === index ? sort.direction === 1 ? 'ascending' : 'descending' : 'none'));
      if (sort) shown.sort((a, b) => {
        const x = values(a)[sort.index], y = values(b)[sort.index];
        if (x == null || y == null) return x == null ? y == null ? 0 : 1 : -1;
        return sortedCompare(x && typeof x === 'object' && !Array.isArray(x) ? text(x) : x,
          y && typeof y === 'object' && !Array.isArray(y) ? text(y) : y, sort.direction);
      });
      const page = Math.max(0, Math.min(state.pages[key] || 0, Math.ceil(shown.length / size) - 1));
      state.pages[key] = page;
      body.replaceChildren();
      for (const item of shown.slice(page * size, (page + 1) * size)) {
        const row = element('tr');
        row.className = [...(item.display_roles || item.prompt?.display_roles || []),
          ...(item.is_compaction ? ['compaction'] : [])].join(' ');
        cells(item).forEach((value, index) => {
          const td = element('td');
          td.append(value && typeof value === 'object' ? value : element('span', () => cells(item)[index]));
          row.append(td);
        });
        body.append(row);
      }
      label.textContent = (shown.length ? `${page * size + 1}–${Math.min((page + 1) * size, shown.length)} of ${shown.length}` : 'No rows') + ` · ${rows.length} full-report rows; filters/pages do not change totals`;
      previous.disabled = page === 0;
      next.disabled = (page + 1) * size >= shown.length;
      if (remote) {
        label.textContent = (rows.length ? `${remote.offset + 1}–${remote.offset + rows.length} of ${remote.total}` : 'No rows') +
          ` · Page ${Math.floor(remote.offset / remote.size) + 1} · ${shown.length} matches on this page only · catalog order frozen; row values observed per page`;
        function destination(node, offset, enabled) {
          node.setAttribute('aria-disabled', enabled ? 'false' : 'true');
          if (enabled) {
            const params = new URLSearchParams({offset: String(offset), revision: remote.catalog_revision});
            if (state.request.session_limit != null) params.set('limit', state.request.session_limit);
            node.href = '#/sessions?' + params;
          } else node.removeAttribute('href');
        }
        destination(previous, Math.max(0, remote.offset - remote.size), remote.offset > 0);
        destination(next, remote.offset + remote.size, remote.offset + rows.length < remote.total);
      }
    }
    filter.addEventListener('input', () => { state.filters[key] = filter.value; state.pages[key] = 0; draw(); });
    if (!remote) {
      previous.addEventListener('click', () => { state.pages[key]--; draw(); });
      next.addEventListener('click', () => { state.pages[key]++; draw(); });
    }
    draw();
  }
  function overviewConcepts(parent, view) {
    const help = element('details', undefined, 'overview-explanations');
    help.append(element('summary', 'More information'));
    const concepts = element('div', undefined, 'report-concepts');
    function concept(label, value, explanation) {
      const card = element('div');
      card.append(element('h3', label), element('p', value, 'metric-value'));
      card.append(element('p', explanation, 'help-copy')); concepts.append(card);
      return card;
    }
    const costCard = concept('CCost', '1 CCost = 1 Copilot AI credit',
      'Estimated reference cost, not your bill.\nFlat-rate plans use Copilot’s published token prices. Unlabelled costs are CCost.\nUnknown prices are not zero.');
    const mix = view.token_mix;
    const mixCard = concept('Token Mix %', () => mix ? mixText(mix) : 'N/A',
      'Percentages of tokens, not cost: ' + mixLegend(view) + '\nInput — New input. Cached input — Reused input. Cache write — Input saved for reuse.\nThis report’s sample is separate from account quota periods.');
    if (mix) mixCard.append(element('p',
      () => `${mix.sample_size} priced prompts · ${display(mix, 'totals')} tokens · CCost ${display(mix, 'costs')}`,
      mix.cost_complete ? 'detail' : 'detail partial'));
    mixCard.append(element('p', mix?.request_count ? `Your mix uses the latest ${mix.sample_size} priced prompts, totaling ${display(mix, 'total_tokens')} tokens.` : 'No priced prompts are available yet.', 'detail'));
    concept('Relative CCost', view.model_comparison_sample_size ? `${view.model_comparison_sample_size} completed ${view.model_comparison_sample_size === 1 ? 'prompt' : 'prompts'}` : 'No completed priced prompts',
      view.model_comparison_sample_size ? 'Price comparison using the same token mix for every model and price tier. The mix comes from up to 100 recent completed, priceable prompts across sessions.\n1.0x — The cheapest comparable positive price in the full catalog. Filters do not change it.\nArrows — Prices at larger input sizes; > or ≥ marks the boundary.\nNot a model-quality test, bill or forecast. Token Mix % uses a separate sample.' :
        'No comparable prompt sample yet, so Relative CCost is blank.\nA fixed I/C/W/O mix of 2/96/1/1 orders prices only; it does not produce displayed multipliers.');
    help.append(concepts, element('p', 'Local, read-only. This report is frozen at capture; navigation and live heartbeats never refresh it. Reload to acquire again. Closing this tab does not stop Cost Guard.', 'detail'));
    if (view.model_catalog) help.append(element('p', 'Available models come from OpenCode’s global list, not a check of your subscription’s entitlements.\nUnknown comparison prices are not zero.', 'detail help-copy'));
    parent.append(help);
  }
  function overviewModels(parent, view, state) {
    const catalog = view.model_catalog;
    const models = catalog?.rows || view.model_comparison;
    state.models ||= {all: false, latest: true, sorts: [{index: 2, direction: -1}]};
    const choice = state.models;
    const tools = element('div', undefined, 'model-tools'), notices = element('div', undefined, 'model-notices');
    const filters = element('div', undefined, 'model-filters');
    function checkbox(label, key, help) {
      const wrap = element('label'), input = element('input');
      input.type = 'checkbox'; input.checked = choice[key]; ContextHelp.attach(input, help);
      input.addEventListener('change', () => { choice[key] = input.checked; draw(); });
      wrap.append(input, element('span', label)); filters.append(wrap);
    }
    checkbox('Show all Copilot-priced models', 'all', 'Off — Show models in OpenCode’s available list, not verified subscription entitlements.\nIf availability cannot be checked, show the catalog with a warning.');
    checkbox('Latest versions only', 'latest', 'Hide recognized older stable versions among the models selected by the other filter.');
    tools.append(notices, filters); parent.append(tools);
    const scroll = element('div', undefined, 'overview-models');
    scroll.tabIndex = 0;
    scroll.setAttribute('role', 'region');
    scroll.setAttribute('aria-label', 'Reference models — scroll horizontally on narrow screens');
    const grid = element('table', undefined, 'overview-model-table');
    // Layout widths come from prepared text, never price arithmetic. Share each
    // marker/ratio/boundary track across rows, including long or multi-tier text.
    const levels = models.flatMap(row => view.model_comparison_sample_size ? display(row, 'relative_cost').split(' → ') : []);
    const width = parts => Math.max(0, ...parts.map(value => value.length)) + 'ch';
    grid.style?.setProperty('--ratio-width', width(levels.map(value => value.split(' ')[0])));
    grid.style?.setProperty('--boundary-width', width(levels.map(value => value.includes(' ') ? value.slice(value.indexOf(' ')) : '')));
    grid.style?.setProperty('--marker-width', width(models.map(row => row.promotion_marker == null ? '' : '*' + row.promotion_marker)));
    grid.setAttribute('role', 'table');
    grid.setAttribute('aria-label', 'Reference models');
    const head = element('thead'), header = element('tr'), body = element('tbody');
    head.setAttribute('role', 'rowgroup'); body.setAttribute('role', 'rowgroup');
    header.setAttribute('role', 'row');
    const names = ['Publisher', 'Model', 'Relative CCost', 'Release date'], headers = [];
    names.forEach((name, index) => {
      const cell = element('th'), button = element('button', name); cell.scope = 'col';
      function activate(event) {
        const existing = choice.sorts.find(sort => sort.index === index);
        const sort = {index, direction: existing ? -existing.direction : index === 2 ? -1 : 1};
        if (event.shiftKey) {
          if (existing) choice.sorts[choice.sorts.indexOf(existing)] = sort;
          else choice.sorts.push(sort);
        } else choice.sorts = [sort];
        draw();
      }
      button.addEventListener('click', activate);
      button.addEventListener('keydown', event => {
        if (event.shiftKey && ['Enter', ' '].includes(event.key)) { event.preventDefault(); activate(event); }
      });
      cell.setAttribute('role', 'columnheader'); cell.append(button); header.append(cell); headers.push([cell, button]);
    });
    head.append(header);
    const promotion = element('div'), empty = element('p', undefined, 'warning');
    const collator = new Intl.Collator(undefined, {sensitivity: 'base'});
    function dateKey(value) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return null;
      const timestamp = Date.parse(value + 'T00:00:00Z');
      return Number.isFinite(timestamp) && new Date(timestamp).toISOString().slice(0, 10) === value ? timestamp : null;
    }
    function key(row, index) {
      return [row.publisher || null, row.model || null,
        row.relative_levels?.length ? row.relative_levels.map(level => level.relative_cost) : [row.relative_cost],
        dateKey(row.release_date)][index];
    }
    function draw() {
      const candidates = models.filter(row => choice.all || row.selectable !== false);
      const shown = candidates.filter(row => !choice.latest || !(choice.all ? row.superseded : catalog ? row.superseded_selectable : row.superseded));
      shown.sort((a, b) => {
        for (const sort of choice.sorts) {
          const x = key(a, sort.index), y = key(b, sort.index);
          const order = sort.index < 2 && x != null && y != null ? collator.compare(x, y) * sort.direction : sortedCompare(x, y, sort.direction);
          if (order) return order;
        }
        return models.indexOf(a) - models.indexOf(b);
      });
      headers.forEach(([cell, button], index) => {
        const priority = choice.sorts.findIndex(sort => sort.index === index), sort = choice.sorts[priority];
        cell.setAttribute('aria-sort', priority === 0 ? sort.direction === 1 ? 'ascending' : 'descending' : 'none');
        text(button, names[index] + (sort ? (sort.direction === 1 ? ' ↑' : ' ↓') + (choice.sorts.length > 1 ? ' ' + (priority + 1) : '') : ' ↕'));
        button.setAttribute('aria-label', names[index] + (sort ? `, ${sort.direction === 1 ? 'ascending' : 'descending'}, priority ${priority + 1}` : ', not sorted') + '. Activate to sort; Shift adds a key.');
        ContextHelp.attach(button, 'Activate to sort or reverse direction.\nHold Shift to keep earlier sort columns (click, Enter or Space).\nUnknown values stay last.');
      });
      body.replaceChildren();
      for (const model of shown) {
      const row = element('tr', undefined, (model.display_roles || []).filter(role => role !== 'superseded').join(' '));
      row.setAttribute('role', 'row');
      for (const value of [model.publisher || 'N/A', element('span', model.model, model.recent ? 'new' : ''),
        modelRelative(model, view.model_comparison_sample_size, false), element('span', model.release_date || 'N/A', model.recent ? 'new' : '')]) {
        const cell = element('td'); cell.setAttribute('role', 'cell');
        cell.append(typeof value === 'object' ? value : element('span', value)); row.append(cell);
      }
      body.append(row);
      }
      notices.replaceChildren();
      const visible = new Set(shown.map(row => row.model));
      const recent = catalog?.recent_notices.filter(note => visible.has(note.model)) || [];
      if (recent.length) notices.append(element('p', '✦ New Models: ' + recent.map(note => note.text.replace(/^✦ New Models: /, '')).join('; '), 'new'));
      if (!catalog && view.recent_model_notice && shown.some(row => row.recent)) notices.append(element('p', view.recent_model_notice, 'new'));
      const markers = new Set(shown.map(row => row.promotion_marker).filter(marker => marker != null));
      promotion.replaceChildren();
      for (const note of catalog?.promotion_notes || view.model_comparison_promotion_notes || []) {
        const marker = /^\*(\d+)\b/.exec(note);
        if (!marker || markers.has(Number(marker[1]))) promotion.append(element('p', note, 'promotion'));
      }
      text(empty, shown.length ? '' : 'No matching reference models. Availability warnings, if any, are shown below.');
    }
    grid.append(head, body); scroll.append(grid); parent.append(scroll);
    overviewConcepts(parent, view);
    parent.append(promotion, empty); draw();
  }
  function modelRelative(row, sampled, evidence = true) {
    const cell = element('span', undefined, 'model-relative' + (row.promotional ? ' promotion' : ''));
    cell.append(element('span', row.promotion_marker != null ? `*${row.promotion_marker} ` : '', 'model-marker'));
    const [base, ...tiers] = sampled ? display(row, 'relative_cost').split(' → ') : [''];
    cell.append(element('span', base, 'model-ratio'));
    const levels = element('span', undefined, 'model-tiers');
    for (const tier of tiers) {
      const level = element('span', undefined, 'model-tier');
      const space = tier.indexOf(' '), ratio = space < 0 ? tier : tier.slice(0, space), boundary = space < 0 ? '' : tier.slice(space);
      level.append(element('span', ' → '), element('span', ratio, 'tier-ratio'), element('span', boundary, 'tier-boundary'));
      levels.append(level);
    }
    cell.append(levels);
    if (evidence) ContextHelp.beside(cell, display(row, 'evidence'), 'Model price sources and coverage');
    return cell;
  }
  function accountQuota(card, quota, compact = false) {
    const row = element('div', undefined, 'quota-summary ' + (quota.display_roles || []).join(' ') +
      (quota.status === 'blocked' ? ' error' : ''));
    const status = quota.status === 'blocked' ? ' · BLOCKED' : compact && quota.status === 'available' ? '' : ' · ' + quota.status;
    row.append(element('strong', quota.label + status));
    const view = () => quotaView(quota);
    const summary = () => quota.unlimited ? 'Unlimited' : view().account_percent === 'N/A' ? 'Used percentage unavailable' :
      view().account_percent + ' ' + view().mode;
    const hasCost = quota.period_ccost?.cost != null;
    const label = element('span', () => summary() + (hasCost ? ` (${display(quota, 'ccost_' + view().mode)})` : ''), 'metric-value'); row.append(label);
    if (hasCost) {
      const capacity = element('span', () => 'Capacity: ' + display(quota, 'ccost_capacity'), 'metric-value');
      ContextHelp.beside(capacity, () => quotaHelp(quota), 'About quota Capacity and period CCost');
      row.append(capacity);
    }
    bind(label, () => label.className = 'metric-value' + (view().mode === 'remaining' && view().exhausted ? ' quota-exhausted' : ''));
    // Only a known server-formatted fraction creates a determinate bar. Never coerce null to zero.
    if (!compact && !quota.unlimited && view().account_percent !== 'N/A') {
      const bar = element('progress');
      bind(bar, () => {
        bar.max = view().mode === 'remaining' ? 1 : 100;
        bar.value = view().mode === 'remaining' ? view().fraction : display(quota, 'used_fraction').replace('%', '');
        bar.setAttribute('aria-label', quota.label + ' ' + view().mode);
        bar.setAttribute('aria-valuetext', summary() + (view().exhausted ? ' · exhausted' : ''));
        bar.className = view().mode === 'remaining' && view().exhausted ? 'quota-exhausted' : '';
      }); row.append(bar);
    }
    const unit = quota.unit || 'units';
    const native = element('span', () => !view().native.startsWith('N/A') ?
      (view().mode === 'remaining' ? 'Remaining ' : 'Used ') + view().native :
      !quota.unlimited && quota.remaining != null ? `${display(quota, 'remaining')} ${unit} remaining` :
      !quota.unlimited && quota.limit != null ? `Limit ${display(quota, 'limit')} ${unit}` : '');
    bind(native, () => native.hidden = view().native.startsWith('N/A') && (quota.unlimited || quota.remaining == null && quota.limit == null));
    row.append(native);
    if (quota.remaining_money != null || quota.limit_money != null) row.append(element('span',
      () => view().money !== 'N/A' ? `Native money ${view().mode} ${view().money} / ${display(quota, 'limit_money')}` :
        `Native money remaining ${display(quota, 'remaining_money')} / ${display(quota, 'limit_money')}`, 'detail'));
    if (view().note) row.append(element('span', view().note, 'warning'));
    row.append(element('span', display(quota, 'reset'), 'detail'));
    const window = [quota.period !== 'unknown' && quota.period,
      quota.duration_seconds && display(quota, 'window') + ' window',
      quota.scope && quota.scope !== 'account' && quota.scope, quota.model_id].filter(Boolean);
    if (!compact && window.length) row.append(element('span', window.join(' · '), 'detail'));
    card.append(row);
  }
  function accountStatus(obs, compact = false) {
    const cause = {auth_failure: 'Authentication unavailable', unsupported_auth_method: 'Unsupported authentication method',
      transport_failure: 'Connection failed', format_changed: 'Provider format changed',
      software_failure: 'Account refresh failed internally', discovery_failure: 'Account metadata unavailable',
      rate_limited: 'Rate limited', account_unavailable: 'Account unavailable'}[obs.error_code];
    const availability = {available: 'Available', partial: 'Partial quota data', stale: 'Stale — last observation, not current',
      unavailable: 'Unavailable', error: 'Refresh failed'}[obs.availability] || 'Availability unknown';
    const status = obs.status === 'available' ? '' : obs.status === 'blocked' ? 'BLOCKED' : compact ? '' : 'Usage status unknown';
    return [compact && obs.availability === 'available' ? '' : availability, status, cause, obs.has_warning && 'Provider warning'].filter(Boolean).join(' · ');
  }
  function overviewAccounts(parent, accounts, title = 'Accounts Overview', detailed = false, compact = false, watch = false) {
    if (!compact && !watch) parent.append(element('h3', title));
    if (!accounts?.accounts.length) { parent.append(element('p', 'No configured accounts detected.')); return; }
    const group = element('div', undefined, compact ? 'account-grid compact-accounts' : 'account-grid');
    for (const account of accounts.accounts) {
      const obs = account.observation, card = element('section', undefined, 'account-card');
      if (detailed) card.setAttribute('data-availability', obs.availability);
      const details = element('details');
      details.append(element('summary', compact ? 'Details' : 'Observation details'));
      card.append(element('h4', obs.label));
      (compact ? details : card).append(element('p', [obs.provider_label, obs.plan].filter(Boolean).join(' · '), 'detail'));
      if (detailed && (!compact || obs.has_error || obs.has_warning || obs.status === 'blocked' || obs.availability !== 'available')) card.append(element('p', accountStatus(obs, compact),
        obs.has_error || obs.status === 'blocked' ? 'error account-status' : obs.has_warning || obs.availability !== 'available' ? 'warning account-status' : 'account-status'));
      for (const scope of account.ccost_scopes) card.append(element('p', () => `CCost ${scope.name}: ${scope.cost == null ? '—' : display(scope.cost, 'account_ccost')}`, 'metric-value'));
      if ((!compact && detailed && !watch) || account.billed_today != null) card.append(element('p', 'Billed today: ' + display(account, 'billed_today')));
      if ((!compact && detailed && !watch) || account.billed_month != null) card.append(element('p', 'Billed month: ' + display(account, 'billed_month')));
      for (const quota of obs.quotas) {
        accountQuota(card, quota, compact);
      }
      for (const pace of account.pace) card.append(element('p', `${pace.label} Remaining: ${display(pace, 'per_day')} ${pace.unit}/day · ${pace.days} days · ${pace.per_workday == null ? 'no workdays left' : display(pace, 'per_workday') + ' per workday'}`, 'detail'));
      if (!watch && (['github-copilot', 'github-copilot-enterprise'].includes(obs.provider_id) || account.unaccounted_usage != null)) card.append(element('p', 'Unaccounted usage (estimate): ' + display(account, 'unaccounted_usage')));
      if (!detailed && (obs.has_error || obs.has_warning || ['stale', 'unavailable', 'error', 'paused', 'blocked'].includes(obs.status))) card.append(element('p', `${obs.availability} · ${obs.status} · ${obs.error_code || 'Account warning'}`, 'warning'));
      if (detailed && !obs.quotas.length) card.append(element('p', 'Quota unavailable; not zero or unlimited.', 'detail'));
      if (account.ccost_account_unknown) card.append(element('p', 'CCost account attribution unknown.', 'warning'));
      (watch ? [] : account.ccost_notes || []).forEach((note, index) => {
        const provider = account.provider_ccost_notes?.find(item => item.index === index);
        (compact ? details : card).append(element('p', provider ? () => `Provider-only CCost ${provider.name}: ${display(provider.cost, 'known_ccost')}${!provider.cost.complete ? ' (partial pricing)' : ''}; not allocated to accounts.` : note, 'warning'));
      });
      details.append(element('p', `${obs.availability} · ${obs.status} · Observed ${display(obs, 'observed_at_ms')}`));
      for (const bill of obs.billing || []) (detailed && !compact ? card : details).append(element('p', `${bill.label} · ${bill.period} · ${bill.kind} · ${display(bill, 'amount')} ${bill.currency} · ${bill.status}`));
      if (compact) for (const quota of obs.quotas) accountQuota(details, quota);
      for (const quota of obs.quotas) details.append(element('p', detailed ?
        () => quotaView(quota).mode === 'remaining' ? `${quota.label} · Remaining ${quotaView(quota).native} · ${quota.status}` :
          `${quota.label} · Used ${display(quota, 'used')} ${quota.unit || 'units'} · ${quota.status}` :
        `${quota.label} · ${quota.period} · ${display(quota, 'window') || 'N/A'} window · ${quota.scope || ''} · Native money remaining/limit ${display(quota, 'remaining_money')}/${display(quota, 'limit_money')}`));
      if (!watch) card.append(details);
      group.append(card);
    }
    parent.append(group);
  }
  function promptLabel(row, live = false) {
    const text = [row.is_compaction && row.label, row.preview || (!row.is_compaction && row.label)].filter(Boolean);
    const node = element('span', `${row.display?.clock || ''} ${row.prompt_number == null ? '' : '#' + row.prompt_number} ${[...new Set(text)].join(' ') || 'Prompt'}`.trim());
    const flags = [row.model_effort, row.is_compaction && 'Compaction',
      row.in_progress && (live ? 'Running · provisional' : 'Running at snapshot · provisional'), row.aborted && 'Aborted',
      row.has_error && 'Error', row.background_only && 'Background activity',
      row.has_additional_model && 'Additional model contribution',
      row.completed_successfully && 'Completed', row.aborted && row.display?.abort_clock, row.abort_reason,
      row.ended_after_tool_calls && 'Ended after tool calls', row.running_cost_warning,
      row.next_context_warning].filter(Boolean);
    node.append(element('span', flags.join(' · '), 'detail ' + (row.display_roles || []).join(' ')));
    if (row.has_cost_breakdown && row.breakdown_known) node.append(element('span',
      () => `Main CCost ${ccost(row, 'main_ccost')} · Linked child CCost ${ccost(row, 'subagent_ccost')}`, 'detail'));
    return node;
  }
  function prompts(parent, block, state, index, ranged = false) {
    const title = element('h3', block.title || 'Session'); parent.append(title, link(block.session_id));
    parent.append(element('p', () => `${ranged ? 'Selected-range' : 'Full-session'} CCost ${ccost(block, 'total_ccost')} · Billing ${display(block, 'billed_cost')} · Duration ${display(block, 'duration_ms')}`));
    if (!ranged && block.active_hour) parent.append(element('p', () => hourlySummary(block.active_hour), 'detail'));
    if (block.total_has_cost_breakdown) parent.append(element('p',
      () => block.total_breakdown_known ? `Main CCost ${ccost(block, 'total_main_ccost')} · Linked child CCost ${ccost(block, 'total_subagent_ccost')}` : 'Linked child breakdown unavailable.'));
    contextSummary(parent, block);
    if (!block.rows.length) parent.append(element('p', 'This session exists but has no prompt rows.'));
    table(parent, `Prompts · ${ranged ? 'selected range' : 'complete session'} totals, independent of page`,
      ['Prompt', 'CCost', 'Calls', 'Duration', '~Ictx', '~Ictx CCost', '~Extra CCost', 'Token Mix %'], block.rows,
      row => detailCells(row),
       () => [ranged ? 'Selected range' : 'Complete session', ccost(block, 'total_ccost'), known(block.total_calls),
         display(block, 'duration_ms'), '—', known(block.total_ictx_cost_text), known(block.total_extra_cost_text), known(block.total_mix_text)],
      state, 'prompts-' + index,
      row => [row.prompt_number, row.ccost, row.calls, row.duration_ms, row.incoming_context_tokens,
        row.incoming_context_ccost, row.extra_ccost, row.token_mix_percent?.join('/')]);
  }
  function hourlySummary(value) {
    return `Reference cost per active hour: ${display(value, 'rate')} · ${value.status} · CCost ${display(value, 'known_ccost')} · Active execution ${display(value, 'duration_ms')}`;
  }
  function hourlyPeriods(parent, view, scope) {
    parent.append(element('p', 'Reference spending per hour of observed concurrent execution, not agent-worker-hours, actual billing, a consultant invoice or human time saved. Unknown pricing/time is not zero.'));
    parent.append(element('p', `Timezone: ${scope.timezone_id}. Today and month-to-date use local calendar boundaries (including DST). Rolling 30 days is exactly 30 × 24 hours before this observation.`, 'detail'));
    const grid = element('div', undefined, 'report-concepts');
    for (const value of view.active_hours || []) {
      const card = element('div');
      card.append(element('h3', value.scope), element('p', () => hourlySummary(value)),
        element('p', `${display(value, 'start_ms')} → ${display(value, 'end_ms')} · ${value.observed_requests} observed requests`, 'detail'));
      grid.append(card);
    }
    parent.append(grid, element('p', 'Execution intervals are clipped before unioning, within and across sessions; idle gaps are excluded. CCost is deduplicated and allocated by each request’s canonical event/completion timestamp, even when execution crosses a boundary. Tokens are never prorated. Running work is provisional and frozen at capture. Complete means complete observed evidence, not recovered deleted/pruned history.', 'detail'));
    const sessions = element('a', 'Browse sessions and their Snapshot/Live rates'); sessions.href = '#/sessions'; parent.append(sessions);
  }
  function render(parent, result, state) {
    defaultUnit(result.view);
    parent.replaceChildren();
    const view = result.view;
    const section = state.section || 'models';
    const overview = ['models', 'overview'].includes(section) && ['normal', 'all-models'].includes(view.kind);
    if (overview) {
      overviewModels(parent, view, state);
      if (result.source.status !== 'acquired') parent.append(element('p', 'Partial source data. Values may be incomplete. Check the local source and reload to retry.', 'warning'));
      if (view.model_availability_unverified) parent.append(element('p', 'Model availability unverified; catalog is not a verified selectable list.', 'warning'));
      if (view.model_availability_empty) parent.append(element('p', 'No available OpenCode models match the pricing catalog.', 'warning'));
      for (const note of view.notes || []) parent.append(element('p', note, 'warning'));
      return;
    }
    parent.append(element('p', `Snapshot: ${new Date(result.observed_at_ms).toLocaleString()} · ${view.source_label} · ${result.source.status} · ${result.source.atomicity}. Frozen; Refresh explicitly to reacquire.`, 'snapshot'));
    if (result.source.status === 'partial') parent.append(element('p', `Partial source data (${view.source_warning_count} warnings). Values may be incomplete.`, 'warning'));
    if (view.model_availability_unverified) parent.append(element('p', 'Model availability unverified: showing the full catalog or all historically used models, not a verified selectable list.', 'warning'));
    if (view.model_availability_empty) parent.append(element('p', 'No available OpenCode models match the pricing catalog.', 'warning'));
    if (view.kind === 'date') parent.append(element('p', `Inclusive local range ${result.scope.date_text} · ${result.scope.timezone_id} · inclusive local calendar dates. Session links open complete history; Back returns to this frozen range.`, 'snapshot'));
    const definitions = element('details');
    definitions.append(element('summary', 'Reading this report'), element('p', 'CCost — Estimated reference cost, not your bill. Unknown prices are not zero.\nDuration — Recorded execution time, frozen with this snapshot.\nSearch, sorting and pages change what you see, not the totals or report scope.\nRefresh acquires a new snapshot. Navigation and live updates do not refresh reports.\nClosing this tab does not stop Cost Guard; the CLI runs separately.', 'help-copy'));
    if (!overview) parent.append(definitions);
    if (view.kind === 'cost-per-hour') {
      hourlyPeriods(parent, view, result.scope);
      for (const note of view.notes || []) parent.append(element('p', note, 'warning'));
      return;
    }
    parent.append(element('p', 'Token category order: ' + mixLegend(view), 'detail'));
    if (overview) overviewConcepts(parent, view);
    if (view.session_usage.length || view.kind === 'sessions') {
      if (!view.session_usage.length) parent.append(element('p', result.source.status === 'partial' ? 'Partial source: no sessions returned; unavailable history is not empty success.' : 'Source acquired: no available sessions.'));
      table(parent, 'Sessions', ['Session / name', 'Model / effort', 'CCost', 'Prompts', 'Duration'], view.session_usage,
        row => { const name = element('span'); name.append(link(row.session_id), element('span', row.title, 'detail'),
            element('span', [!row.complete && 'Incomplete pricing', row.archived && 'Archived', row.running && 'Running at snapshot'].filter(Boolean).join(' · '), 'detail'));
          return [name, row.model + (row.multiple_models ? ' · multiple models' : ''), ccost(row), known(row.prompt_count), display(row, 'duration_ms')]; },
        null, state, 'sessions', row => [row.title + ' ' + row.session_id, row.model, row.ccost, row.prompt_count, row.duration_ms]);
    }
    view.prompt_blocks.forEach((block, index) => prompts(parent, block, state, index, view.kind === 'date'));
    if (view.kind === 'date' && !view.prompt_blocks.length) parent.append(element('p', 'No prompt rows in this local date range.'));
    const accounts = view.accounts_quotas;
    if (overview) overviewAccounts(parent, accounts, 'Accounts Overview', true);
    if (view.kind === 'normal' && section === 'accounts') {
      parent.append(element('p', 'Normal report · local-month / Today CCost and account-native windows. Independent frozen observations; not Watch rolling usage.', 'detail'));
      overviewAccounts(parent, accounts, 'Accounts · independent observations', true);
    }
    if (view.token_mix && view.kind === 'token-mix') {
      const mix = view.token_mix;
      parent.append(element('h3', view.kind === 'token-mix' ? 'Token Mix · available deep history' : 'Token Mix · independent report sample'));
      mixSummary(parent, mix);
      if (view.kind === 'token-mix') {
        if (!view.model_token_mix.length) parent.append(element('p', 'No available historical model rows. Missing history is not reconstructed.'));
        table(parent, 'Historical models · canonical totals above, independent of filters',
          ['Model', 'Prompts', 'Calls', 'Tokens', ...mixLabels(view), 'CCost'], view.model_token_mix,
          row => [row.model, known(row.prompts), known(row.calls), display(row.mix, 'total_tokens'), ...['input', 'cache', 'write', 'output', 'total_cost'].map(key => display(row.mix, key))], null, state, 'history',
          row => [row.model, row.prompts, row.calls, row.mix.known_total_tokens ?? row.mix.total_tokens, ...row.mix.shares, row.mix.total_cost]);
        table(parent, 'Historical publishers · same shown usage, not the comparison prior',
          ['Publisher', 'Prompts', 'Calls', 'Tokens', ...mixLabels(view), 'CCost'], view.publisher_token_mix || [],
          row => [row.publisher, known(row.prompts), known(row.calls), display(row.mix, 'total_tokens'), ...['input', 'cache', 'write', 'output', 'total_cost'].map(key => display(row.mix, key))], null, state, 'publishers',
          row => [row.publisher, row.prompts, row.calls, row.mix.known_total_tokens ?? row.mix.total_tokens, ...row.mix.shares, row.mix.total_cost]);
      }
    }
    if (view.range_comparison) parent.append(element('p', () => `CCost for range: ${display(view.range_comparison, 'known_ccost')}; reference valuation, not billing.`, 'warning'));
    for (const note of (view.notes || []).slice(view.range_comparison ? 1 : 0)) parent.append(element('p', note, 'warning'));
  }
  function mixSummary(parent, mix) {
    parent.append(element('p', () => `Total Token Mix % · ${display(mix, 'total_tokens')} tokens · ` +
      mixText(mix), mix.cost_complete ? 'metric-value' : 'metric-value partial'));
    parent.append(element('p', mixLegend(mix), 'detail'));
    const details = element('details'); details.append(element('summary', 'Sample and price coverage'), element('p',
      `Full-report I/C/W/O tokens: ${display(mix, 'totals')}\nRequests: ${mix.request_count} · Prompts: ${mix.sample_size} · Priced requests: ${mix.priced_requests}\n${mix.cost_complete ? 'Complete prices' : 'Incomplete prices'}\n? — Incomplete token data. N/A — No known token categories.\nTotals add the known categories. K/M/B are rounded; sorting uses exact amounts.\nOutput includes reasoning. One prompt can use several models.`, 'help-copy')); parent.append(details);
  }
  function contextSummary(parent, block) {
    parent.append(element('p', () => display(block, 'next_context'), block.next_context_warning ? 'threshold' : 'detail'));
    if (block.next_context_warning) parent.append(element('p', 'Context: ' + block.next_context_warning.replace(/^\[|\]$/g, ''), 'warning'));
  }
  function renderLive(parent, result, state) {
    defaultUnit(result.view);
    state.watch ||= new WatchView.View(state);
    state.watch.attach(parent);
    state.watch.update(result);
  }
  function detailCells(row, live = false) {
    const label = promptLabel(row, live);
    if (row.retained) label.append(element('span', `Last observed ${new Date(row.last_observed_at_ms).toLocaleString()}; source history omitted this row`, 'detail'));
    return [label, ccost(row), row.display?.calls ?? known(row.calls),
      display(row, 'duration_ms'), display(row, 'incoming_context_tokens'), ccost(row, 'incoming_context_ccost'),
      ccost(row, 'extra_ccost'), display(row, 'token_mix_percent')];
  }
  function detailTotals(block) {
    return ['Complete session', ccost(block, 'total_ccost'), known(block.total_calls),
      display(block, 'duration_ms'), '—', known(block.total_ictx_cost_text), known(block.total_extra_cost_text), known(block.total_mix_text)];
  }
  return {render, renderLive, element, detailCells, detailTotals, compare, overviewAccounts, display, contextSummary, text, setUnit, syncUnits, defaultUnit, mixLegend, hourlySummary, bind, setQuotaMode, quotaView, quotaHelp};
})();
