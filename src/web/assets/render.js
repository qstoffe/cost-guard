'use strict';
// Presentation only. Decimal strings and canonical totals are never recalculated.
const ReportView = (() => {
  const known = value => value === null || value === undefined ? 'Unknown' : String(value);
  // Missing tokens are not a license to expose raw Decimal strings or calculate in JS.
  let unit = null;
  let quotaMode = 'used';
  let timezone = null;
  function setTimezone(value) { timezone = value; }
  function configuredTimezone() { return timezone; }
  const ccostDefinition = 'Comparative Cost Based on GitHub Reference Price List';
  const ccostHelp = context => context ? `${ccostDefinition}\n${context}` : ccostDefinition;
  const headerHelp = {
    model: '• Main model — The model shown in this column.\n• Linked subagents, multiple models or different effort levels — If marked *, hover, focus or tap the Model value for details.',
    calls: 'Model requests for this prompt, including linked subagents.\nNot tool calls.',
    duration: 'Time spent on this prompt.',
    sessionCost: ccostHelp('The entire session’s reference cost, including attributed linked subagents.'),
    promptCost: ccostHelp('Reference cost of this prompt, including attributed linked subagent calls.'),
    incomingContextCost: ccostHelp('Reference cost of the incoming context on the first request.'),
    extraCost: ccostHelp('Other reference cost: output, later requests and linked subagents.'),
    todayCost: ccostHelp('Reference cost for the local calendar day.'),
    context: 'Estimated context for this session, in tokens.'
  };
  function activityHelp(value, zone, running = false, started = null) {
    const label = Number.isSafeInteger(value) && value > 0 ? timestamp(value, zone) : 'N/A';
    if (label === 'N/A') return Number.isSafeInteger(started) && started > 0 ?
      timestamp(started, zone) + '\nCompletion unverified. Showing recorded prompt start, not finish.' :
      'Activity time unavailable.';
    return label + (running === true ? '\n* Running sessions appear first, regardless of sorting.' : '');
  }
  function costGroups(value, session = false) {
    const models = display(value, 'mini_cost_models'), amounts = display(value, 'mini_cost_amounts');
    if (!Array.isArray(models) || !Array.isArray(amounts)) {
      return 'No model usage recorded';
    }
    const groups = ['Session Models', 'Sub Agents'].map(label => {
      const bullets = models.flatMap(([kind, model], index) => kind === label ?
        [`• ${model} — (${amounts[index] ?? 'N/A'})`] : []);
      return bullets.length ? label + ':\n' + bullets.join('\n') : '';
    }).filter(Boolean).join('\n\n') || 'No model usage recorded';
    const coverage = display(value, 'mini_cost_coverage_help');
    return groups + (coverage && coverage !== 'N/A' ? '\n\n' + coverage : '');
  }
  function sessionCostHelp(cost, summary) {
    return costGroups(cost, true) + (Number.isFinite(summary?.duration_ms) ?
      '\n\nDuration: ' + display(summary, 'duration_ms') : '');
  }
  const DateTimeMode = Object.freeze({DATE: 'DATE', TIME: 'TIME', DATE_TIME: 'DATE_TIME',
    DATE_TIME_SECONDS: 'DATE_TIME_SECONDS'});
  let timestampZone, timestampFormatter;
  function calendarDateKey(value) {
    if (typeof value !== 'string' || !/^(?!0000)\d{4}-\d{2}-\d{2}$/.test(value)) return null;
    const instant = Date.parse(`${value}T00:00:00Z`);
    return Number.isFinite(instant) && new Date(instant).toISOString().slice(0, 10) === value ? instant : null;
  }
  function formatDateTime(instant, mode, configuredZone) {
    if (mode === DateTimeMode.DATE && typeof instant === 'string')
      return calendarDateKey(instant) === null ? 'N/A' : instant;
    if (mode !== DateTimeMode.DATE && mode !== DateTimeMode.TIME &&
        mode !== DateTimeMode.DATE_TIME && mode !== DateTimeMode.DATE_TIME_SECONDS) return 'N/A';
    if (!Number.isFinite(instant) || typeof configuredZone !== 'string') return 'N/A';
    const zone = configuredZone.trim();
    // Do not accept the fixed-offset syntax supported by newer Intl engines.
    if (!/^[A-Za-z][A-Za-z0-9_+/-]*$/.test(zone)) return 'N/A';
    try {
      if (zone !== timestampZone) {
        timestampFormatter = new Intl.DateTimeFormat('en-US', {timeZone: zone, calendar: 'gregory', numberingSystem: 'latn',
          year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
          second: '2-digit', era: 'short', hourCycle: 'h23'});
        timestampZone = zone;
      }
      const parts = timestampFormatter.formatToParts(Math.floor(instant / 1000) * 1000);
      const fields = Object.fromEntries(parts.map(part => [part.type, part.value]));
      if (fields.era !== 'AD' || fields.year.length > 4) return 'N/A';
      const day = `${fields.year.padStart(4, '0')}-${fields.month}-${fields.day}`;
      const clock = `${fields.hour}:${fields.minute}`;
      if (mode === DateTimeMode.DATE) return day;
      if (mode === DateTimeMode.TIME) return clock;
      return `${day} ${clock}${mode === DateTimeMode.DATE_TIME_SECONDS ? `:${fields.second}` : ''}`;
    } catch (_) { return 'N/A'; } // Never substitute the browser's timezone for missing configuration.
  }
  function timestamp(value, zone = timezone) {
    return Number.isSafeInteger(value) && value >= 0 ? formatDateTime(value, DateTimeMode.DATE_TIME, zone) : 'N/A';
  }
  const calendarWeekday = new Intl.DateTimeFormat('en', {weekday: 'long', timeZone: 'UTC'});
  let monthLanguage, calendarMonths;
  function calendarCaption(day, kind, language = 'en') {
    // Axis captions describe a calendar day, not an absolute UTC timestamp.
    const key = calendarDateKey(day);
    if (key === null) return 'N/A';
    if (kind === 'weekday') return calendarWeekday.format(key);
    if (kind !== 'month-short' && kind !== 'month-long') return 'N/A';
    try {
      if (language !== monthLanguage) {
        calendarMonths = ['short', 'long'].map(month => new Intl.DateTimeFormat(language, {
          month, timeZone: 'UTC', calendar: 'gregory'
        }));
        monthLanguage = language;
      }
      return calendarMonths[kind === 'month-short' ? 0 : 1].format(key);
    } catch (_) { return 'N/A'; }
  }
  const bindings = new WeakMap();
  const effects = new WeakMap();
  // Live presentation grace only: a repeated snapshot or another lane's progress
  // cannot clear an ongoing failure. Callers supply their own successful evidence.
  class LiveStatus {
    update(usable, token, now = Date.now(), threshold = 60000) {
      const fresh = typeof token === 'number' && typeof this.token === 'number' ? token > this.token : token !== this.token;
      if (usable && token != null && fresh) {
        this.token = token; this.since = null;
      } else if (!usable) this.since ??= now;
      return this.since != null && now - this.since >= threshold;
    }
  }
  function bind(node, update) { effects.set(node, update); update(); }
  function setQuotaMode(value) { if (['used', 'remaining'].includes(value)) quotaMode = value; }
  function quotaView(quota, watch) {
    return quota.quota_display?.[quotaMode] || {mode: 'used', native: display(quota, 'quota_used'),
      money: display(quota, 'used_money'), account_percent: display(quota, 'used_fraction'),
      fraction: watch?.used_fraction, percent: watch?.used_percent, exhausted: watch?.exhausted, note: ''};
  }
  const costKeys = new Set(['ccost', 'known_ccost', 'account_ccost', 'daily_ccost', 'total_ccost',
    'run_ccost', 'main_ccost', 'subagent_ccost', 'total_main_ccost', 'total_subagent_ccost',
    'incoming_context_ccost', 'extra_ccost', 'next_context_cached_ccost', 'next_context_fresh_ccost',
    'total_incoming_context_ccost', 'total_extra_ccost',
    'watch_next_context_cached_ccost', 'watch_next_context_fresh_ccost']);
  const display = (row, key) => {
    // Identity and cost-group help have independent evidence and ownership.
    if (['model_help', 'model_detail_help'].includes(key)) {
      return row?.model_display_help || row?.display_units?.[unit]?.[key] || row?.display?.[key] || row?.[key] ||
        (row?.contributor_models?.length ? row.contributor_models.join('\n') :
        row?.watch_model || row?.model_effort || row?.model || row?.label || 'N/A');
    }
    const value = row?.display_units?.[unit]?.[key] ?? row?.display?.[key];
    return costKeys.has(key) && (value == null || ['', 'N/A', 'Not Applicable', '—', '-', 'Loading…', 'Unavailable'].includes(value)) ?
      'N/A' : value ?? 'N/A';
  };
  const metricLabels = {activity: 'last activity', model: 'model', ccost: 'CCost',
    prompts: 'prompt count', duration: 'duration', ctx: 'context', prompt_ccost: 'prompt CCost', total: 'total CCost'};
  const emptyHistoryHelp = {
    activity: 'No prompt activity is recorded for this session.',
    model: 'No model is recorded for this session.',
    ctx: 'No recorded context is available for this session.',
    prompt_ccost: 'No prompt is recorded for this session.'
  };
  const metricIndicators = new WeakMap();
  function paintValue(node, value, pending, field) {
    let spinner = metricIndicators.get(node);
    if (!pending) {
      if (spinner?.parentNode === node) spinner.remove();
      text(node, value);
      return;
    }
    bindings.delete(node);
    if (!spinner) {
      spinner = node.ownerDocument.createElement('span');
      spinner.className = 'metric-spinner';
      spinner.setAttribute('role', 'img');
      metricIndicators.set(node, spinner);
    }
    const label = 'Loading ' + field;
    if (spinner.getAttribute('aria-label') !== label) spinner.setAttribute('aria-label', label);
    if (spinner.parentNode !== node) {
      text(node, '');
      node.append(spinner);
    }
  }
  // The caller decides whether evidence is pending; display text is never a state signal.
  function valueSlot(node, value, {pending = false, field} = {}) {
    effects.delete(node);
    paintValue(node, value, pending, field);
  }
  const metricToken = (row, key) => {
    const token = display(row, key);
    return token === 'N/A' || token === '' ? null : token;
  };
  function metric(node, field, {value, reason, help, label, onHelpLost} = {}) {
    const render = () => {
      const shown = typeof value === 'function' ? value() : value;
      const absence = shown == null && reason === 'complete_empty_history' ? emptyHistoryHelp[field] : '';
      const pending = shown == null && !absence;
      const hint = absence || (shown != null && help);
      if (hint) ContextHelp.value(node, hint);
      else {
        ContextHelp.clearValue(node);
        if (node.ownerDocument.activeElement === node) onHelpLost?.();
      }
      if (shown != null && label) node.setAttribute('aria-label', label(shown));
      else node.removeAttribute('aria-label');
      paintValue(node, absence ? '?' : shown, pending, metricLabels[field]);
    };
    if (typeof value === 'function') bind(node, render);
    else { effects.delete(node); render(); }
  }
  // AI Stats prepares concise provider/model + By Effort help. Do not route it
  // through the generic prompt identity shortener above or lose the effort rows.
  const aiStatsModelHelp = row => row?.display_units?.[unit]?.model_help ??
    row?.display?.model_help ?? row?.model_help ?? '';
  class CostDisplay {
    constructor() { this.values = new Map(); }
    select(row, scope, key = 'ccost', complete = row?.complete === true || row?.unresolved_cost === false, raw = row?.[key], extra = []) {
      if (scope == null) return row;
      const original = row;
      row = this.observe(row, scope, key, complete, raw, name => extra.includes(name) || costKeys.has(name) ||
        /^mix_.*_cost(?:_help)?$/.test(name) ||
        ['costs', 'total_cost', 'cost_detail_help', 'session_cost_help', 'mini_cost_models', 'mini_cost_amounts'].includes(name));
      // A priced aggregate is not evidence that each component is priceable.
      // Independently qualified amounts survive a partial replacement too.
      for (const name of costKeys) {
        if (name === key || !Object.hasOwn(original || {}, name)) continue;
        const available = original[name + '_known'] !== false && !original[name + '_usage_missing'];
        const covered = available && complete && !original[name.replace('_ccost', '_estimated')];
        row = this.observe(row, scope, ['component', name], covered, available ? original[name] : null,
          token => token === name, original);
      }
      if (key === 'total_cost') {
        for (const [index, name] of ['input', 'cache', 'write', 'output'].entries()) {
          row = this.observe(row, scope, ['category', name], complete, original?.costs?.[index],
            token => token === 'mix_' + name + '_cost' || token === 'mix_' + name + '_cost_help', original);
        }
      }
      if (original?.display?.mini_cost_ready) {
        const models = original.display.mini_cost_models;
        const amounts = {credits: [], usd: []};
        original.display.mini_cost_ready.forEach((ready, index) => {
          const source = {display: {amount: original.display.mini_cost_amounts[index]},
            display_units: Object.fromEntries(['credits', 'usd'].map(unit =>
              [unit, {amount: original.display_units?.[unit]?.mini_cost_amounts?.[index] ??
                original.display.mini_cost_amounts[index]}]))};
          const identity = ['mini', models[index][0].startsWith('Sub Agent'), models[index][1]];
          // Unknown model/effort is not a stable group identity.
          const shown = models[index][1] === 'N/A — N/A' ? source :
            this.observe(source, scope, identity, false, null, name => name === 'amount', source, ready);
          for (const unit of ['credits', 'usd']) amounts[unit].push(shown.display_units[unit].amount);
        });
        row = {...row, display: {...row.display, mini_cost_models: models},
          display_units: Object.fromEntries(['credits', 'usd'].map(unit =>
            [unit, {...row.display_units?.[unit], mini_cost_amounts: amounts[unit]}]))};
      }
      return row;
    }
    observe(row, scope, key, complete, raw, includes, source = row, ready) {
      const identity = JSON.stringify([scope, key]);
      const numeric = typeof raw !== 'boolean' && raw != null && /^[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?$/.test(String(raw));
      const order = numeric ? compare(raw, '0') : -1;
      const qualified = ready ?? (numeric && (order > 0 || order === 0 && complete));
      const extract = tokens => Object.fromEntries(Object.entries(tokens || {}).filter(([name]) => includes(name)));
      if (qualified) {
        const units = Object.fromEntries(['credits', 'usd'].map(unit =>
          [unit, extract({...source.display, ...source.display_units?.[unit]})]));
        this.values.delete(identity);
        this.values.set(identity, {display: extract(source.display), units});
        // View-owned display observations only, never another persistent ledger.
        if (this.values.size > 5000) this.values.delete(this.values.keys().next().value);
      }
      const old = this.values.get(identity);
      if (!old) return row;
      return {...row, display: {...row?.display, ...old.display},
        display_units: Object.fromEntries(['credits', 'usd'].map(unit =>
          [unit, {...row?.display_units?.[unit], ...old.units[unit]}]))};
    }
  }
  function estimateValue(target, row, key) {
    const help = () => { const text = display(row(), key() + '_help'); return text === 'N/A' ? '' : text; };
    ContextHelp.value(target, help);
    bind(target, () => {
      const available = Boolean(help());
      target.tabIndex = available ? 0 : -1;
      target.className = target.className.replace(/\s?help-value/g, '') + (available ? ' help-value' : '');
    });
    return target;
  }
  const quotaLabel = quota => quota.label.replace(/^\p{L}/u, letter => letter.toUpperCase());
  const capacityKnown = (quota, monthly = false) => quota.ccost_reference?.[monthly ? 'monthly_capacity' : 'capacity'] != null;
  function quotaCapacityHelp(quota, monthly = false) {
    if (quota.unlimited && !monthly) return 'Capacity: Unlimited';
    if (!capacityKnown(quota, monthly)) return 'N/A';
    if (quota.ccost_reference.retained_capacity)
      return display(quota, monthly ? 'monthly_capacity_help' : 'capacity_help');
    return 'Estimated reference-cost capacity for this quota.';
  }
  function quotaUsageHelp(quota) {
    const view = quotaView(quota), native = quota.quota_display;
    return (quota.unlimited ? 'Unlimited\n' : '') +
      `Used: ${native?.used.native || view.native}\nRemaining: ${native?.remaining.mode === 'remaining' ? native.remaining.native : 'N/A'}\n` +
      (quota.limit_money != null || quota.remaining_money != null ? `Native money ${view.mode}: ${view.money} / ${display(quota, 'limit_money')}\n` : '') +
      display(quota, 'web_reset') +
      (quota.status === 'blocked' ? '\nProvider restriction reported.' : '') +
      (view.note ? '\n' + view.note : '');
  }
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
    for (const child of [...root.children]) syncUnits(child, true);
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
  function costHelp(row, key = 'ccost') {
    if (['total_ccost', 'known_ccost'].includes(key) && display(row, 'session_cost_help') !== 'N/A') return display(row, 'session_cost_help');
    if (!row) return '';
    if (row?.[key + '_known'] === false || row?.[key + '_usage_missing']) return '';
    if (row[key] != null && !row.unresolved_cost && row.complete !== false) return '';
    return '';
  }
  function costValue(row, key = 'ccost') {
    const node = element('span', () => ccost(row, key));
    if (costHelp(row, key)) ContextHelp.value(node, () => costHelp(row, key));
    return node;
  }
  function element(tag, content, className) {
    const node = document.createElement(tag);
    if (content !== undefined) text(node, content);
    if (className) node.className = className;
    return node;
  }
  // Reviewed official destinations; never derive a host/path from account text.
  const accountDestinations = new Map(Object.entries({
    'github-copilot': 'https://github.com/settings/copilot/features',
    'github-copilot-enterprise': 'https://github.com/settings/copilot/features',
    'claude-code': 'https://claude.ai/settings/usage',
    openai: 'https://chatgpt.com/settings/usage',
    anthropic: 'https://console.anthropic.com/',
    openrouter: 'https://openrouter.ai/activity',
    deepseek: 'https://platform.deepseek.com/',
    minimax: 'https://platform.minimax.io/user-center/payment/balance',
    'minimax-cn': 'https://platform.minimax.cn/user-center/payment/balance',
    'minimax-coding-plan': 'https://platform.minimax.io/user-center/payment/token-plan',
    'minimax-cn-coding-plan': 'https://platform.minimax.cn/user-center/payment/token-plan',
  }));
  function accountDestination(obs) {
    const plan = typeof obs.plan === 'string' ? obs.plan.toLowerCase() : '';
    const api = ['api pay as you go', 'pay as you go'].includes(plan);
    if (obs.provider_id === 'openai' && api) return 'https://platform.openai.com/usage';
    if (obs.provider_id === 'claude-code' && api) return accountDestinations.get('anthropic');
    if (obs.provider_id === 'anthropic' && obs.capacity_kind !== 'credit' && ['pro', 'max', 'team', 'enterprise'].includes(plan))
      return accountDestinations.get('claude-code');
    return accountDestinations.get(obs.provider_id);
  }
  function accountHeading(observation, level = 'h4') {
    const heading = element(level); let label, name, linked;
    bind(heading, () => {
      const obs = observation(), href = accountDestination(obs);
      if (!label || linked !== Boolean(href)) {
        linked = Boolean(href); label = element(linked ? 'a' : 'span', undefined, linked ? 'account-provider-link' : undefined);
        name = linked ? element('span') : label;
        if (linked) {
          label.target = '_blank'; label.rel = 'noopener noreferrer';
          const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
          icon.setAttribute('class', 'account-link-icon'); icon.setAttribute('viewBox', '0 0 24 24');
          icon.setAttribute('aria-hidden', 'true'); icon.setAttribute('focusable', 'false');
          const chain = document.createElementNS('http://www.w3.org/2000/svg', 'path');
          chain.setAttribute('d', 'M10 13a5 5 0 0 0 7 .2l3-3a5 5 0 0 0-7-7l-1.7 1.7M14 11a5 5 0 0 0-7-.2l-3 3a5 5 0 0 0 7 7l1.7-1.7');
          icon.append(chain); label.append(icon, name);
        }
        heading.replaceChildren(label);
      }
      text(name, obs.label);
      if (linked) {
        label.href = href;
        label.setAttribute('aria-label', `${obs.label} — provider usage or settings (opens in a new tab)`);
      }
    });
    return heading;
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
  function table(parent, title, columns, rows, cells, totals, state, key, values = cells, columnHelp = {}) {
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
    const headers = [], headerLabels = [];
    columns.forEach((column, index) => {
      const th = element('th'), button = element('button', column); th.scope = 'col';
      const sortHelp = 'Sort this column; activate again to reverse or clear sorting.\nUnknown values stay last. Sorting does not change totals.';
      const context = columnHelp[column];
      headerLabels.push(ContextHelp.heading(button, context ? `${context}\n${sortHelp}` : sortHelp));
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
      totals().forEach((value, index) => {
        const cell = element('td'); cell.append(typeof value === 'object' ? value : element('span', () => totals()[index])); row.append(cell);
      });
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
      headers.forEach((th, index) => {
        const active = sort?.index === index, order = sort?.direction === 1 ? 'ascending' : 'descending';
        th.setAttribute('aria-sort', active ? order : 'none');
        headerLabels[index].textContent = columns[index] + (active ? sort.direction === 1 ? ' ↑' : ' ↓' : '');
        th.children[0].setAttribute('aria-label', columns[index] + (active ? ', ' + order : ', not sorted') + '. Activate to sort.');
      });
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
  function modelHeadingHelp(view) {
    return ['The model’s developer/manufacturer.',
      'The model identity in the published catalog.',
      'Reference-price ratio to the cheapest comparable model (1.0x); not task performance.\n\nToken Mix is the percentage split of Input, Cached input, Cache write and Output tokens. This comparison uses a fixed statistical average: Input 3%, Cached input 95%, Cache write 1%, Output 1%.',
      'The published/verified model release date.'];
  }
  function modelHeading(title, source, href) {
    const heading = element('h2', undefined, 'model-section-heading');
    const reference = element('span', undefined, 'model-source'), link = element('a', 'View source');
    link.href = href; link.target = '_blank'; link.rel = 'noopener noreferrer';
    reference.append(element('span', '(' + source + ' · '), link, element('span', ')'));
    heading.append(typeof title === 'string' ? element('span', title) : title, reference);
    return heading;
  }
  const latestModelsHelp = 'Hide recognized older numeric versions. Also hide reviewed predecessors when their successor is in the selected list.';
  function latestModels(candidates, enabled, isNumericallySuperseded) {
    if (!enabled) return candidates;
    const reviewedKeys = new Set(candidates.map(row => row.reviewed_key).filter(Boolean));
    return candidates.filter(row => !isNumericallySuperseded(row) && !reviewedKeys.has(row.reviewed_successor_key));
  }
  function overviewModels(parent, view, state) {
    if (state.modelView && state.modelView.choice === state.models) { state.modelView.update(view); state.modelView.attach(parent); return; }
    const root = element('div', undefined, 'models-view');
    let catalog = view.model_catalog;
    let models = catalog?.rows || view.model_comparison;
    let sortKeys = new Map();
    state.models ||= {all: false, latest: true, sorts: [{index: 2, direction: -1}]};
    const choice = state.models;
    root.append(modelHeading('GitHub Reference Pricing', 'GitHub Copilot',
      'https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing'));
    const tools = element('div', undefined, 'model-tools');
    const prices = element('div', undefined, 'model-price-controls'), refresh = element('button', 'Refresh price list');
    refresh.setAttribute('data-model-control', 'refresh');
    const fetched = element('span', 'Last fetched: ' + (view.pricing_retrieved_at_ms > 0 ? display(view, 'pricing_retrieved_at_ms') : 'Unavailable'));
    const progress = element('span'); progress.setAttribute('role', 'status');
    state.priceControls = writable => {
      refresh.disabled = !writable || !!state.priceRefreshing;
      refresh.setAttribute('aria-disabled', String(refresh.disabled));
      text(progress, state.priceRefreshing ? 'Refreshing…' : state.priceMessage || '');
    };
    refresh.addEventListener('click', () => state.refreshPrices?.());
    prices.append(refresh, fetched, progress);
    const filters = element('div', undefined, 'model-filters');
    function checkbox(label, key, help) {
      const wrap = element('label'), input = element('input');
      input.type = 'checkbox'; input.checked = choice[key]; ContextHelp.attach(input, help);
      input.setAttribute('data-model-control', key);
      input.addEventListener('change', () => { choice[key] = input.checked; draw(); });
      wrap.append(input, element('span', label)); filters.append(wrap);
    }
    checkbox('Show all Copilot-priced models', 'all', 'Show the full priced catalog instead of the available-model list.');
    checkbox('Latest versions only', 'latest', latestModelsHelp);
    tools.append(prices, filters); root.append(tools);
    const scroll = element('div', undefined, 'overview-models');
    scroll.tabIndex = 0;
    scroll.setAttribute('role', 'region');
    scroll.setAttribute('aria-label', 'Reference models — scroll horizontally on narrow screens');
    const grid = element('table', undefined, 'overview-model-table');
    // Layout widths come from prepared text, never price arithmetic. Share each
    // marker/ratio/boundary track across rows, including long or multi-tier text.
    const width = parts => parts.reduce((max, value) => Math.max(max, value.length), 0) + 'ch';
    grid.setAttribute('role', 'table');
    grid.setAttribute('aria-label', 'Reference models');
    const head = element('thead'), header = element('tr'), body = element('tbody');
    head.setAttribute('role', 'rowgroup'); body.setAttribute('role', 'rowgroup');
    header.setAttribute('role', 'row');
    const names = ['Publisher', 'Model', 'Relative Price List Cost', 'Release date'], headers = [];
    const help = modelHeadingHelp(view);
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
      button.setAttribute('data-model-control', 'column-' + index);
      const label = ContextHelp.heading(button, help[index]);
      cell.setAttribute('role', 'columnheader'); cell.append(button); header.append(cell); headers.push([cell, button, label]);
    });
    head.append(header);
    const empty = element('p', undefined, 'warning');
    const collator = new Intl.Collator(undefined, {sensitivity: 'base'});
    function keys(row) {
      return [row.publisher || null, row.model || null,
        row.relative_levels?.length ? row.relative_levels.map(level => level.relative_cost) : [row.relative_cost],
        calendarDateKey(row.release_date)];
    }
    const rows = new Map();
    function draw() {
      const candidates = models.filter(row => choice.all || row.selectable !== false);
      const shown = latestModels(candidates, choice.latest,
        row => choice.all || !catalog ? row.superseded : row.superseded_selectable);
      shown.sort((a, b) => {
        for (const sort of choice.sorts) {
          const x = sortKeys.get(a)[sort.index], y = sortKeys.get(b)[sort.index];
          const order = sort.index < 2 && x != null && y != null ? collator.compare(x, y) * sort.direction : sortedCompare(x, y, sort.direction);
          if (order) return order;
        }
        return 0; // Stable sort preserves the original publication order for ties.
      });
      headers.forEach(([cell, button, label], index) => {
        const priority = choice.sorts.findIndex(sort => sort.index === index), sort = choice.sorts[priority];
        cell.setAttribute('aria-sort', priority === 0 ? sort.direction === 1 ? 'ascending' : 'descending' : 'none');
        text(label, names[index] + (sort ? (sort.direction === 1 ? ' ↑' : ' ↓') + (choice.sorts.length > 1 ? ' ' + (priority + 1) : '') : ''));
        button.setAttribute('aria-label', names[index] + (sort ? `, ${sort.direction === 1 ? 'ascending' : 'descending'}, priority ${priority + 1}` : ', not sorted') + '. Activate to sort; Shift adds a key.');
      });
      const wanted = [];
      for (const model of shown) {
        const identity = JSON.stringify([model.publisher, model.model]);
        const {category = null, ...rowData} = model;
        const signature = JSON.stringify(rowData);
        let entry = rows.get(identity);
        if (!entry || entry.signature !== signature) {
          const row = element('tr', undefined, (model.display_roles || []).filter(role => role !== 'superseded').join(' '));
          row.setAttribute('role', 'row');
          const name = element('span', model.model, model.recent ? 'new' : '');
          for (const value of [model.publisher || 'N/A', name, modelRelative(model),
            element('span', formatDateTime(model.release_date, DateTimeMode.DATE), model.recent ? 'new' : '')]) {
            const cell = element('td'); cell.setAttribute('role', 'cell');
            cell.append(typeof value === 'object' ? value : element('span', value)); row.append(cell);
          }
          entry = {row, name, signature, category: null}; rows.set(identity, entry);
        }
        if (entry.category !== category) {
          if (category) {
            ContextHelp.value(entry.name, 'GitHub category: ' + category);
          } else if (entry.category) {
            ContextHelp.dismiss(entry.name);
            const plainName = element('span', model.model, model.recent ? 'new' : '');
            entry.name.parentNode.replaceChildren(plainName);
            entry.name = plainName;
          }
          entry.category = category;
        }
        wanted.push(entry.row);
      }
      const keep = new Set(wanted);
      for (const row of [...body.children]) if (!keep.has(row)) row.remove();
      let next = body.firstElementChild;
      for (const row of wanted) {
        if (row === next) next = row.nextElementSibling;
        else body.insertBefore(row, next);
      }
      for (const [identity, entry] of rows) if (!keep.has(entry.row)) rows.delete(identity);
      text(empty, shown.length ? '' : 'No matching models.');
    }
    grid.append(head, body); scroll.append(grid); root.append(scroll);
    root.append(empty);
    if (typeof BenchmarkView !== 'undefined') {
      state.benchmark ||= new BenchmarkView.View(); state.benchmark.attach(root);
    }
    const more = element('div', undefined, 'more-benchmarks'), links = element('ul');
    for (const [label, href] of [
      ['Artificial Analysis — Coding Agent Index', 'https://artificialanalysis.ai/agents/coding-agents/'],
      ['Slopalytics — Cost per task / Cost vs intelligence', 'https://slopalytics.com/']]) {
      const item = element('li'), link = element('a', label);
      link.href = href; link.target = '_blank'; link.rel = 'noopener noreferrer';
      item.append(link); links.append(item);
    }
    more.append(element('h2', 'More Coding Benchmarks'), links);
    const availability = element('p', undefined, 'warning');
    root.append(availability, more);
    state.modelView = {
      root, choice,
      attach(target) { if (root.parentNode !== target) target.replaceChildren(root); },
      update(value) {
        view = value; catalog = view.model_catalog; models = catalog?.rows || view.model_comparison;
        sortKeys = new Map(models.map(row => [row, keys(row)]));
        const levels = models.flatMap(row => display(row, 'relative_cost').split(' → '));
        grid.style?.setProperty('--ratio-width', width(levels.map(value => value.split(' ')[0])));
        grid.style?.setProperty('--boundary-width', width(levels.map(value => value.includes(' ') ? value.slice(value.indexOf(' ')) : '')));
        text(fetched, 'Last fetched: ' + (view.pricing_retrieved_at_ms > 0 ? display(view, 'pricing_retrieved_at_ms') : 'Unavailable'));
        text(availability, view.model_availability_empty ? 'No available OpenCode models match the pricing catalog.' : '');
        availability.hidden = !view.model_availability_empty; draw();
      }
    };
    state.modelView.update(view); state.modelView.attach(parent);
  }
  function modelRelative(row) {
    const cell = element('span', undefined, 'model-relative' + (row.promotional ? ' promotion' : ''));
    const [base, ...tiers] = display(row, 'relative_cost').split(' → ');
    cell.append(element('span', base, 'model-ratio'));
    const levels = element('span', undefined, 'model-tiers');
    for (const tier of tiers) {
      const level = element('span', undefined, 'model-tier');
      const space = tier.indexOf(' '), ratio = space < 0 ? tier : tier.slice(0, space), boundary = space < 0 ? '' : tier.slice(space);
      level.append(element('span', ' → '), element('span', ratio, 'tier-ratio'), element('span', boundary, 'tier-boundary'));
      levels.append(level);
    }
    cell.append(levels);
    let prices = row.price_help || 'GitHub Copilot · USD / 1M tokens';
    if (row.promotional) {
      cell.append(element('span', ' *', 'model-marker'));
      const offer = row.promotion;
      if (offer) prices = ContextHelp.warningParagraph(prices, ['Price Promotion', offer.price_comparison,
        'Temporary GitHub Copilot promotional pricing',
        offer.description !== 'Temporary GitHub Copilot promotional pricing' && offer.description,
        offer.through && 'Promotion ends: ' + offer.through,
        offer.resumes && 'Standard prices resume: ' + offer.resumes].filter(Boolean).join('\n'));
    }
    ContextHelp.value(cell, prices);
    return cell;
  }
  function accountQuota(card, quota, compact = false) {
    const row = element('div', undefined, 'quota-summary ' + (quota.display_roles || []).join(' ') +
      (quota.status === 'blocked' ? ' error' : ''));
    const status = quota.status === 'blocked' ? ' · BLOCKED' : '';
    row.append(element('strong', quota.label + status));
    const view = () => quotaView(quota);
    const summary = () => quota.unlimited ? 'Unlimited' : view().account_percent === 'N/A' ? 'N/A' :
      view().account_percent + ' ' + view().mode;
    const hasCost = quota.period_ccost?.cost != null;
    const label = element('span', undefined, 'metric-value');
    label.append(element('span', summary));
    if (hasCost) label.append(estimateValue(element('span', () => ` (${display(quota, 'ccost_' + view().mode)})`),
      () => quota, () => 'ccost_' + view().mode));
    row.append(label);
    if (hasCost) {
      const capacity = element('span', () => 'Capacity: ' + display(quota, 'ccost_capacity'), 'metric-value');
      ContextHelp.value(capacity, () => quotaCapacityHelp(quota));
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
    row.append(element('span', display(quota, 'web_reset'), 'detail'));
    const window = [quota.period !== 'unknown' && quota.period,
      quota.duration_seconds && display(quota, 'window') + ' window',
      quota.scope && quota.scope !== 'account' && quota.scope, quota.model_id].filter(Boolean);
    if (!compact && window.length) row.append(element('span', window.join(' · '), 'detail'));
    card.append(row);
  }
  function accountStatus(obs, compact = false) {
    return obs.status === 'blocked' ? 'Provider restriction reported' : '';
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
      card.append(accountHeading(() => obs));
      (compact ? details : card).append(element('p', [obs.provider_label, obs.plan].filter(Boolean).join(' · '), 'detail'));
      if (obs.status === 'blocked') card.append(element('p', accountStatus(obs, compact), 'account-status'));
      for (const scope of account.ccost_scopes) {
        const line = element('p', undefined, 'metric-value');
        const context = `This account’s reference cost for ${scope.name}.`;
        line.append(ContextHelp.value(element('span', `CCost ${scope.name}:`), ccostHelp(context)), ' ',
          ContextHelp.value(element('span', () => display(scope.cost, 'account_ccost')), context));
        card.append(line);
      }
      if ((!compact && detailed && !watch) || account.billed_today != null) card.append(element('p', 'Billed today: ' + display(account, 'billed_today')));
      if ((!compact && detailed && !watch) || account.billed_month != null) card.append(element('p', 'Billed month: ' + display(account, 'billed_month')));
      for (const quota of obs.quotas) {
        accountQuota(card, quota, compact);
        const pace = quota.ccost_pace;
        if (pace) {
          const line = element('p', undefined, 'detail');
          line.append(estimateValue(element('span', () => `${quota.label} Remaining: ${display(pace, 'ccost_per_day')}/day`),
            () => pace, () => 'ccost_per_day'), element('span', ` · ${pace.days} days · `),
            estimateValue(element('span', () => pace.workdays === 0 ? 'no workdays left' : display(pace, 'ccost_per_workday') + '/workday'),
              () => pace, () => 'ccost_per_workday'));
          card.append(line);
        }
      }
      if (!watch && (['github-copilot', 'github-copilot-enterprise'].includes(obs.provider_id) || account.unaccounted_usage != null)) card.append(element('p', 'Unaccounted usage (estimate): ' + display(account, 'unaccounted_usage')));
      details.append(element('p', `Observed ${display(obs, 'observed_at_ms')}`));
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
      row.has_error && 'Error', row.subagent_active && 'Subagent activity',
      row.parent_outcome && row.subagent_active && `Parent attempt: ${row.parent_outcome}`,
      row.background_only && 'Background activity',
      row.has_additional_model && 'Additional model contribution',
      row.completed_successfully && 'Completed', row.aborted && row.display?.abort_clock, row.abort_reason,
      row.ended_after_tool_calls && 'Ended after tool calls', row.running_cost_warning,
      row.next_context_warning].filter(Boolean);
    node.append(element('span', flags.join(' · '), 'detail ' + (row.display_roles || []).join(' ')));
    if (row.has_cost_breakdown && row.breakdown_known) node.append(element('span',
      () => `Main CCost ${ccost(row, 'main_ccost')} · Linked child CCost ${ccost(row, 'subagent_ccost')}`, 'detail'));
    return node;
  }
  function prompts(parent, block, state, index, zone) {
    const title = element('h3', block.title || 'Session'); parent.append(title, link(block.session_id));
    const totals = element('p');
    totals.append(ContextHelp.value(element('span', 'Full-session CCost'), headerHelp.sessionCost), ' ',
      costValue(block, 'total_ccost'), element('span', () => ` · Billing ${display(block, 'billed_cost')} · Duration ${display(block, 'duration_ms')}`));
    parent.append(totals);
    if (block.active_hour) parent.append(element('p', () => hourlySummary(block.active_hour), 'detail'));
    if (block.total_has_cost_breakdown) parent.append(element('p',
      () => block.total_breakdown_known ? `Main CCost ${ccost(block, 'total_main_ccost')} · Linked child CCost ${ccost(block, 'total_subagent_ccost')}` : 'N/A'));
    contextSummary(parent, block);
    if (!block.rows.length) parent.append(element('p', 'This session exists but has no prompt rows.'));
    table(parent, 'Prompts · complete session totals, independent of page',
      ['Prompt', 'CCost', 'Calls', 'Duration', '~Ictx', '~Ictx CCost', '~Extra CCost', 'Token Mix %'], block.rows,
       row => detailCells(row, false, zone),
        () => ['Complete session', costValue(block, 'total_ccost'), known(block.total_calls),
         display(block, 'duration_ms'), '—', known(block.total_ictx_cost_text), known(block.total_extra_cost_text), known(block.total_mix_text)],
      state, 'prompts-' + index,
      row => [row.prompt_number, row.ccost, row.calls, row.duration_ms, row.incoming_context_tokens,
         row.incoming_context_ccost, row.extra_ccost, row.token_mix_percent?.join('/')],
       {'CCost': headerHelp.promptCost, '~Ictx CCost': headerHelp.incomingContextCost, '~Extra CCost': headerHelp.extraCost});
  }
  function hourlySummary(value) {
    return `Reference cost per active hour: ${display(value, 'rate')} · Active execution ${display(value, 'duration_ms')}`;
  }
  function historyWarning(result) {
    if (result?.source?.status !== 'partial') return '';
    const count = result.source.omitted_roots;
    return Number.isSafeInteger(count) && count > 0 ?
      `Partial history: ${count} changing root session${count === 1 ? '' : 's'} could not be verified and were omitted. Totals and groups do not cover the full source.` :
      'Partial source history. Values may be incomplete.';
  }
  function render(parent, result, state) {
    defaultUnit(result.view);
    const view = result.view;
    const section = state.section || 'models';
    if (view.kind === 'token-mix') {
      state.tokenMix ||= new TokenMixView.View();
      state.tokenMix.update(result); state.tokenMix.attach(parent); return;
    }
    const overview = ['models', 'overview'].includes(section) && ['normal', 'all-models'].includes(view.kind);
    if (overview) {
      overviewModels(parent, view, state);
      return;
    }
    parent.replaceChildren();
    parent.append(element('p', `Snapshot: ${timestamp(result.observed_at_ms, view.timezone_id)}`, 'snapshot'));
    const definitions = element('details');
    const costExplanation = 'Estimated reference cost, not your bill. Unknown prices are not zero.';
    const explanation = element('p', undefined, 'help-copy');
    explanation.append(ContextHelp.value(element('span', 'CCost'), ccostHelp(costExplanation)),
      ` — ${costExplanation}\nDuration — Recorded execution time, frozen with this snapshot.\nSearch, sorting and pages change what you see, not the totals or report scope.\nRefresh acquires a new snapshot. Navigation and live updates do not refresh reports.\nClosing this tab does not stop Cost Guard; the CLI runs separately.`);
    definitions.append(element('summary', 'Reading this report'), explanation);
    if (!overview) parent.append(definitions);
    parent.append(element('p', 'Token category order: ' + mixLegend(view), 'detail'));
    if (view.session_usage.length || view.kind === 'sessions') {
      if (!view.session_usage.length) parent.append(element('p', result.source.status === 'partial' ? 'N/A' : 'No sessions yet.'));
      table(parent, 'Sessions', ['Session / name', 'Model / effort', 'CCost', 'Prompts', 'Duration'], view.session_usage,
        row => { const name = element('span'); name.append(link(row.session_id), element('span', row.title, 'detail'),
            element('span', [row.archived && 'Archived', row.running && 'Running at snapshot'].filter(Boolean).join(' · '), 'detail'));
          return [name, row.model + (row.multiple_models ? ' · multiple models' : ''), costValue(row), known(row.prompt_count), display(row, 'duration_ms')]; },
         null, state, 'sessions', row => [row.title + ' ' + row.session_id, row.model, row.ccost, row.prompt_count, row.duration_ms],
         {CCost: headerHelp.sessionCost});
    }
    view.prompt_blocks.forEach((block, index) => prompts(parent, block, state, index, view.timezone_id));
    const accounts = view.accounts_quotas;
    if (overview) overviewAccounts(parent, accounts, 'Accounts Overview', true);
    if (view.kind === 'normal' && section === 'accounts') {
      parent.append(element('p', 'Normal report · local-month / Today CCost and account-native windows. Independent frozen observations; not Watch rolling usage.', 'detail'));
      overviewAccounts(parent, accounts, 'Accounts · independent observations', true);
    }
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
  function detailCells(row, live = false, zone = timezone) {
    const label = promptLabel(row, live);
    return [label, costValue(row), row.display?.calls ?? known(row.calls),
      display(row, 'duration_ms'), display(row, 'incoming_context_tokens'), costValue(row, 'incoming_context_ccost'),
      costValue(row, 'extra_ccost'), display(row, 'token_mix_percent')];
  }
  function detailTotals(block) {
    return ['Complete session', costValue(block, 'total_ccost'), known(block.total_calls),
      display(block, 'duration_ms'), '—', known(block.total_ictx_cost_text), known(block.total_extra_cost_text), known(block.total_mix_text)];
  }
  return {render, renderLive, element, modelHeading, latestModels, latestModelsHelp, detailCells, detailTotals, compare, sortedCompare, overviewAccounts, display, metric, metricToken, valueSlot, aiStatsModelHelp, contextSummary, text, setUnit, syncUnits, defaultUnit, mixLegend, hourlySummary, historyWarning, bind, setQuotaMode, quotaView, quotaUsageHelp, quotaCapacityHelp, quotaLabel, capacityKnown, estimateValue, LiveStatus, costHelp, costValue, accountHeading, formatDateTime, DateTimeMode, calendarCaption, timestamp, setTimezone, configuredTimezone, CostDisplay, ccostHelp, headerHelp, activityHelp, costGroups, sessionCostHelp};
})();
