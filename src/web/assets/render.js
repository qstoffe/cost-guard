'use strict';
// Presentation only. Decimal strings and canonical totals are never recalculated.
const ReportView = (() => {
  const known = value => value === null || value === undefined ? 'Unknown' : String(value);
  // Missing tokens are not a license to expose raw Decimal strings or calculate in JS.
  const display = (row, key) => row?.display?.[key] ?? 'N/A';
  const ccost = (row, key = 'ccost') => display(row, key) +
    (row?.cost_estimated && key === 'ccost' ? ' (estimated)' : '');
  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
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
  function table(parent, title, columns, rows, cells, totals, state, key, values = cells) {
    const section = element('section');
    state.filters ||= {}; state.sorts ||= {};
    const filterLabel = element('label', 'Filter ' + title + ' '), filter = element('input');
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
      button.addEventListener('click', () => {
        const old = state.sorts[key]; state.sorts[key] = {index, direction: old?.index === index ? -old.direction : 1};
        state.pages[key] = 0; draw();
      });
      th.append(button); header.append(th); headers.push(th);
    });
    head.append(header); grid.append(head);
    const body = element('tbody'); grid.append(body);
    if (totals) {
      const foot = element('tfoot'), row = element('tr');
      for (const value of totals) row.append(element('td', value));
      foot.append(row); grid.append(foot);
    }
    scroll.append(grid); section.append(scroll); parent.append(section);
    const pager = element('div', undefined, 'pager');
    const previous = element('button', 'Previous'), next = element('button', 'Next');
    const label = element('span'); label.setAttribute('aria-live', 'polite');
    previous.setAttribute('aria-label', 'Previous page: ' + title);
    next.setAttribute('aria-label', 'Next page: ' + title);
    pager.append(previous, label, next); section.append(pager);
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
        return compare(x && typeof x === 'object' && !Array.isArray(x) ? text(x) : x,
          y && typeof y === 'object' && !Array.isArray(y) ? text(y) : y) * sort.direction;
      });
      const page = Math.max(0, Math.min(state.pages[key] || 0, Math.ceil(shown.length / size) - 1));
      state.pages[key] = page;
      body.replaceChildren();
      for (const item of shown.slice(page * size, (page + 1) * size)) {
        const row = element('tr');
        row.className = [...(item.display_roles || item.prompt?.display_roles || []),
          ...(item.is_compaction ? ['compaction'] : [])].join(' ');
        for (const value of cells(item)) {
          const td = element('td');
          td.append(value && typeof value === 'object' ? value : element('span', value));
          row.append(td);
        }
        body.append(row);
      }
      label.textContent = (shown.length ? `${page * size + 1}–${Math.min((page + 1) * size, shown.length)} of ${shown.length}` : 'No rows') + ` · ${rows.length} full-report rows; filters/pages do not change totals`;
      previous.disabled = page === 0;
      next.disabled = (page + 1) * size >= shown.length;
    }
    filter.addEventListener('input', () => { state.filters[key] = filter.value; state.pages[key] = 0; draw(); });
    previous.addEventListener('click', () => { state.pages[key]--; draw(); });
    next.addEventListener('click', () => { state.pages[key]++; draw(); });
    draw();
  }
  function promptLabel(row) {
    const node = element('span', `${row.label || 'Prompt'} ${row.prompt_number == null ? '' : '#' + row.prompt_number} ${row.preview || ''}`.trim());
    const flags = [row.model_effort, row.is_compaction && 'Compaction',
      row.in_progress && 'Running at snapshot · provisional', row.aborted && 'Aborted',
      row.has_error && 'Error', row.background_only && 'Background activity',
      row.has_additional_model && 'Additional model contribution',
      row.completed_successfully && 'Completed', row.abort_reason,
      row.ended_after_tool_calls && 'Ended after tool calls', row.running_cost_warning,
      row.next_context_warning].filter(Boolean);
    node.append(element('span', flags.join(' · '), 'detail ' + (row.display_roles || []).join(' ')));
    if (row.has_cost_breakdown) node.append(element('span',
      `Main CCost ${ccost(row, 'main_ccost')} · Linked child CCost ${ccost(row, 'subagent_ccost')}`, 'detail'));
    return node;
  }
  function prompts(parent, block, state, index, ranged = false) {
    const title = element('h3', block.title || 'Session'); parent.append(title, link(block.session_id));
    parent.append(element('p', `${ranged ? 'Selected-range' : 'Full-session'} CCost ${ccost(block, 'total_ccost')} · Billing ${display(block, 'billed_cost')} · Duration ${display(block, 'duration_ms')}`));
    if (block.total_has_cost_breakdown) parent.append(element('p',
      `Main CCost ${ccost(block, 'total_main_ccost')} · Linked child CCost ${ccost(block, 'total_subagent_ccost')}`));
    if (!block.rows.length) parent.append(element('p', 'This session exists but has no prompt rows.'));
    table(parent, `Prompts · ${ranged ? 'selected range' : 'complete session'} totals, independent of page`,
      ['Prompt', 'CCost', 'Calls', 'Duration', '~Ictx', '~Ictx CCost', '~Extra CCost', 'I/C/W/O %'], block.rows,
      row => detailCells(row),
       [ranged ? 'Selected range' : 'Complete session', ccost(block, 'total_ccost'), known(block.total_calls),
         display(block, 'duration_ms'), '—', known(block.total_ictx_cost_text), known(block.total_extra_cost_text), known(block.total_mix_text)],
      state, 'prompts-' + index,
      row => [row.prompt_number, row.ccost, row.calls, row.duration_ms, row.incoming_context_tokens,
        row.incoming_context_ccost, row.extra_ccost, row.token_mix_percent?.join('/')]);
  }
  function render(parent, result, state) {
    parent.replaceChildren();
    const view = result.view;
    const section = state.section || 'overview';
    parent.append(element('p', `Snapshot: ${new Date(result.observed_at_ms).toLocaleString()} · ${view.source_label} · ${result.source.status} · ${result.source.atomicity}. Frozen; Refresh explicitly to reacquire.`, 'snapshot'));
    if (result.source.status === 'partial') parent.append(element('p', `Partial source data (${view.source_warning_count} warnings). Values may be incomplete.`, 'warning'));
    if (view.model_availability_unverified) parent.append(element('p', 'Model availability unverified: showing the full catalog or all historically used models, not a verified selectable list.', 'warning'));
    if (view.kind === 'date') parent.append(element('p', `Inclusive local range ${result.scope.date_text} · ${result.scope.timezone_id} · [${result.scope.start_ms}, ${result.scope.end_ms}) milliseconds. Prompt links open complete sessions; use Back to return to this frozen range.`));
    parent.append(element('p', 'CCost = reference valuation, not provider billing. Unknown pricing is not zero. I/C/W/O = input/cache read/cache write/output. Durations are report execution durations, frozen at observation time.'));
    if (view.session_usage.length || view.kind === 'sessions') {
      if (!view.session_usage.length) parent.append(element('p', 'Source acquired: no available sessions.'));
      table(parent, 'Sessions', ['Session / name', 'Model / effort', 'CCost', 'Prompts', 'Duration'], view.session_usage,
        row => { const name = element('span'); name.append(link(row.session_id), element('span', row.title, 'detail'));
          return [name, row.model + (row.multiple_models ? ' · multiple models' : ''), ccost(row), known(row.prompt_count), display(row, 'duration_ms')]; },
        null, state, 'sessions', row => [row.title + ' ' + row.session_id, row.model, row.ccost, row.prompt_count, row.duration_ms]);
    }
    view.prompt_blocks.forEach((block, index) => prompts(parent, block, state, index, view.kind === 'date'));
    if (view.kind === 'date' && !view.prompt_blocks.length) parent.append(element('p', 'No prompt rows in this local date range.'));
    if (['overview', 'models'].includes(section) && view.model_comparison.length) {
      if (view.token_mix) mixSummary(parent, view.token_mix);
      parent.append(element('p', `Model comparison sample: ${known(view.model_comparison_sample_size)} · Pricing retrieved ${display(view, 'pricing_retrieved_at_ms')}`));
      const all = view.kind === 'all-models';
      table(parent, 'Reference models · shared CLI sample · default exact server ranking',
        ['Publisher', 'Model', 'Relative CCost', ...(all ? ['GitHub USD/M I/C/W/O'] : []), 'Release date'], view.model_comparison,
        row => [row.publisher || 'N/A', element('span', row.model + (row.recent ? ' · recent' : '') + (row.superseded ? ' · older stable variant' : ''), row.recent ? 'new' : ''),
          element('span', (row.promotion_marker ? `*${row.promotion_marker} ` : '') + display(row, 'relative_cost'), row.promotional ? 'promotion' : ''),
          ...(all ? [display(row, 'price_summary')] : []), row.release_date || 'N/A'], null, state, 'models',
        row => [row.publisher, row.model, row.relative_cost, ...(all ? [row.price_summary] : []), row.release_date]);
      for (const note of view.model_comparison_promotion_notes || []) parent.append(element('p', note, 'promotion'));
      if (view.recent_model_notice) parent.append(element('p', view.recent_model_notice, 'new'));
    }
    if (section === 'models' && !view.model_comparison.length) parent.append(element('p', 'No matching reference models. Availability warnings, if any, are shown above.'));
    const accounts = view.accounts_quotas;
    if (view.kind === 'normal' && ['overview', 'accounts'].includes(section)) {
      parent.append(element('h3', 'Accounts · independent observations'));
      if (!accounts || !accounts.accounts.length) parent.append(element('p', 'Account data unavailable or no accounts discovered. Session data remains independent.'));
      if (accounts) {
        parent.append(element('p', `Report Today CCost ${ccost(accounts.comparison_today, 'known_ccost')} · Local-month CCost ${ccost(accounts.comparison_month, 'known_ccost')} · report scope, not Watch rolling usage`));
        for (const account of accounts.accounts) {
          const obs = account.observation;
          parent.append(element('h4', `${obs.label} · ${obs.provider_label} · ${obs.plan || 'Plan unknown'}`));
          parent.append(element('p', `${obs.availability} · ${obs.status} · ${obs.error_code || ''} · Observed ${display(obs, 'observed_at_ms')}`, obs.has_error || obs.has_warning ? 'warning' : ''));
          parent.append(element('p', `Billed today ${display(account, 'billed_today')} · Billed month ${display(account, 'billed_month')}`));
          for (const bill of obs.billing || []) parent.append(element('p', `${bill.label} · ${bill.period} · ${bill.kind} · ${display(bill, 'amount')} ${bill.currency} · ${bill.status}`));
           for (const scope of account.ccost_scopes) parent.append(element('p', `${scope.name} CCost ${display(scope.cost, 'account_ccost')} · account-only partial-display policy; attribution notes below`));
          if (obs.provider_id === 'github-copilot' || account.unaccounted_usage != null) parent.append(element('p', `Unaccounted usage (estimate): ${display(account, 'unaccounted_usage')}`));
          if (account.ccost_account_unknown) parent.append(element('p', 'CCost account attribution unknown.', 'warning'));
          for (const note of account.ccost_notes || []) parent.append(element('p', note, 'warning'));
          for (const pace of account.pace) parent.append(element('p', `${pace.label} Pace ${display(pace, 'per_day')} ${pace.unit}/day · ${known(pace.days)} days · ${pace.per_workday == null ? 'no workdays left' : display(pace, 'per_workday') + ' per workday'}`));
          for (const quota of obs.quotas) parent.append(element('p', `${quota.label} · Remaining ${display(quota, 'remaining_fraction')} · Native money remaining/limit ${display(quota, 'remaining_money')}/${display(quota, 'limit_money')} · ${quota.window_active === false ? 'Inactive window' : 'Window activity ' + known(quota.window_active)}`));
          table(parent, 'Quota: ' + obs.label, ['Period / window', 'Used', 'Limit', 'Remaining', 'Reset', 'Status'], obs.quotas,
            q => [q.label + ` · ${q.period} · ${known(q.duration_seconds)} s · ${q.scope || ''}`, `${display(q, 'used')} ${q.unit}`, q.unlimited ? 'Unlimited' : display(q, 'limit'), `${display(q, 'remaining')} ${q.unit}`, display(q, 'reset_at_ms'), q.status], null, state, 'account-' + obs.id,
            q => [q.label, q.used, q.limit, q.remaining, q.reset_at_ms, q.status]);
        }
      }
    }
    if (view.token_mix && view.kind === 'token-mix') {
      const mix = view.token_mix;
      parent.append(element('h3', view.kind === 'token-mix' ? 'Token Mix · available deep history' : 'Token Mix · independent report sample'));
      mixSummary(parent, mix);
      if (view.kind === 'token-mix') {
        if (!view.model_token_mix.length) parent.append(element('p', 'No available historical model rows. Missing history is not reconstructed.'));
        table(parent, 'Historical models · canonical totals above, independent of filters',
          ['Model', 'Prompts', 'Calls', 'I/C/W/O tokens', 'I/C/W/O CCost', 'I/C/W/O %', 'Price coverage'], view.model_token_mix,
          row => [row.model, known(row.prompts), known(row.calls), display(row.mix, 'totals'), display(row.mix, 'costs'), display(row.mix, 'percentages'), `${row.mix.priced_requests}/${row.mix.request_count} ${row.mix.cost_complete ? 'complete' : 'incomplete'}`], null, state, 'history',
          row => [row.model, row.prompts, row.calls, row.mix.totals, row.mix.costs, row.mix.percentages, row.mix.priced_requests]);
      }
    }
    for (const note of view.notes || []) parent.append(element('p', note, 'warning'));
  }
  function mixSummary(parent, mix) {
    parent.append(element('p', `Full-report I/C/W/O tokens: ${display(mix, 'totals')} · CCost ${display(mix, 'costs')} · Mix % ${display(mix, 'percentages')} · Requests ${mix.request_count} · Prompts ${mix.sample_size} · Priced requests ${mix.priced_requests} · ${mix.cost_complete ? 'Complete prices' : 'Incomplete prices'}`, mix.cost_complete ? '' : 'partial'));
  }
  function renderLive(parent, result, state) {
    parent.replaceChildren();
    const view = result.view;
    parent.append(element('p', `${result.state} · ${view.source_label} · ${view.status} · Source observation ${new Date(result.source_observed_at_ms ?? view.now_ms).toLocaleString()} · Published ${new Date(view.now_ms).toLocaleString()}`, 'snapshot'));
    parent.append(element('p', `Run origin: ${view.run_origin}, ${new Date(view.started_at_ms).toLocaleString()}. CCost is reference valuation, not billing.`));
    parent.append(element('p', `Run CCost ${ccost(view, 'run_ccost')} · Requests ${view.run_total.request_count} · I/C/W/O tokens ${display(view.run_total, 'totals')}`));
    parent.append(element('p', `Run I/C/W/O CCost ${display(view.run_total, 'costs')} · Token Mix % ${display(view.token_mix, 'percentages')}`));
    parent.append(element('p', `${view.today_label} CCost ${ccost(view.today_total, 'known_ccost')}${view.today_pending ? ' · History pending' : ''}`));
    for (const message of [view.recent_model_notice, ...view.recent_promotion_notices].filter(Boolean)) parent.append(element('p', message, 'warning'));
    const groups = new Map();
    for (const row of view.rows) {
      if (!groups.has(row.session_id)) groups.set(row.session_id, []);
      groups.get(row.session_id).push(row);
    }
    for (const [id, rows] of groups) {
      const first = rows[0];
      parent.append(element('h3', `${first.session_title} · ${rows.some(r => r.session_active) ? 'Active / recent' : first.earlier ? 'Earlier' : 'Retained'}`), link(id));
      const subtotal = view.session_subtotals.find(item => item.session_id === id);
      parent.append(element('p', `Displayed rows CCost ${ccost(subtotal)} (not full session)`));
      table(parent, 'Live prompts', ['Prompt / lifecycle', 'CCost', 'Calls', 'Duration', '~Ictx', '~Ictx CCost', '~Extra CCost', 'I/C/W/O %', 'Live context / tools'], rows,
        row => {
          const p = row.prompt, tool = row.tool;
          const label = promptLabel({...p, next_context_warning: row.next_context_warning}); label.append(element('span', row.marker, 'detail'));
          const detail = element('span', row.next_context_warning || '', row.next_context_warning ? 'threshold' : '');
          detail.append(element('span', `Next context ${display(row.live_context, 'watch_next_context_tokens')} · delta ${display(row.live_context, 'watch_delta_context_tokens')} · cached/fresh CCost ${ccost(row.live_context, 'watch_next_context_cached_ccost')}/${ccost(row.live_context, 'watch_next_context_fresh_ccost')}`, 'detail'));
          if (tool) detail.append(element('span', `${tool.running_tool} ${display(tool, 'running_ms')} · Calls ${tool.counts.map(pair => pair.join(': ')).join(', ')} · Failed ${tool.failed_count} · TODO ${tool.todo_completed}/${tool.todo_total} ${tool.active_todo} · Background ${tool.background_kinds.join(', ')} ${display(tool, 'background_ms')} · Skills ${tool.skills.map(s => s.skill_id + (s.failed_count ? ' (failed ' + s.failed_count + ')' : '')).join(', ')}`, 'detail'));
          return [label, ccost(p), known(p.calls), display(p, 'duration_ms'), display(p, 'incoming_context_tokens'), ccost(p, 'incoming_context_ccost'), ccost(p, 'extra_ccost'), display(p, 'token_mix_percent'), detail];
        }, null, state, 'live-' + id, row => [row.prompt.prompt_number, row.prompt.ccost, row.prompt.calls,
          row.prompt.duration_ms, row.prompt.incoming_context_tokens, row.prompt.incoming_context_ccost,
          row.prompt.extra_ccost, row.prompt.token_mix_percent, row.tool?.running_tool]);
    }
    if (!view.rows.length) parent.append(element('p', 'No retained prompt rows. Idle is not evidence of completion.'));
    parent.append(element('h3', `Watch accounts · ${view.quota_stale ? 'stale' : 'independent observations'} · recovering ${view.quota_recovering_count}`));
    for (const account of view.accounts?.accounts || []) {
      const obs = account.observation;
      parent.append(element('h4', `${obs.label} · ${obs.provider_label} · ${obs.plan || ''}`));
      parent.append(element('p', `${obs.availability} · ${obs.status} · ${obs.error_code || ''} · Observed ${display(obs, 'observed_at_ms')}`, obs.has_error || obs.has_warning ? 'warning' : ''));
      for (const scope of account.ccost_scopes) parent.append(element('p', `${scope.name} CCost ${display(scope.cost, 'account_ccost')}`));
      for (const pace of account.pace) parent.append(element('p', `${pace.label} Pace ${display(pace, 'per_day')} ${pace.unit}/day`));
      table(parent, 'Watch quota: ' + obs.label, ['Period', 'Used', 'Limit', 'Remaining', 'Reset', 'Status'], obs.quotas,
        q => [q.label, `${display(q, 'used')} ${q.unit}`, q.unlimited ? 'Unlimited' : display(q, 'limit'), display(q, 'remaining'), display(q, 'reset_at_ms'), q.status], null, state, 'live-account-' + obs.id,
        q => [q.label, q.used, q.limit, q.remaining, q.reset_at_ms, q.status]);
    }
  }
  function detailCells(row) {
    const label = promptLabel(row);
    if (row.retained) label.append(element('span', `Last observed ${new Date(row.last_observed_at_ms).toLocaleString()}; source history omitted this row`, 'detail'));
    return [label, ccost(row), row.display?.calls ?? known(row.calls),
      display(row, 'duration_ms'), display(row, 'incoming_context_tokens'), ccost(row, 'incoming_context_ccost'),
      ccost(row, 'extra_ccost'), display(row, 'token_mix_percent')];
  }
  function detailTotals(block) {
    return ['Complete session', ccost(block, 'total_ccost'), known(block.total_calls),
      display(block, 'duration_ms'), '—', known(block.total_ictx_cost_text), known(block.total_extra_cost_text), known(block.total_mix_text)];
  }
  return {render, renderLive, element, detailCells, detailTotals, compare};
})();
