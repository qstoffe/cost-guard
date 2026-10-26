'use strict';
// Presentation only. Decimal strings and canonical totals are never recalculated.
const ReportView = (() => {
  const known = value => value === null || value === undefined ? 'Unknown' : String(value);
  const ccost = (value, incomplete = false, estimated = false) => value == null ? 'Unknown' :
    `${value}${incomplete ? ' (incomplete)' : ''}${estimated ? ' (estimated)' : ''}`;
  const money = value => value == null ? 'Unknown' : '$' + value;
  const duration = value => value == null ? 'Unknown' : `${(value / 1000).toFixed(1)} s`;
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
  function table(parent, title, columns, rows, cells, totals, state, key) {
    const section = element('section');
    const scroll = element('div', undefined, 'table-scroll');
    scroll.tabIndex = 0;
    scroll.setAttribute('role', 'region');
    scroll.setAttribute('aria-label', title);
    const grid = element('table');
    grid.append(element('caption', title));
    const head = element('thead'), header = element('tr');
    for (const column of columns) { const th = element('th', column); th.scope = 'col'; header.append(th); }
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
      const page = Math.max(0, Math.min(state.pages[key] || 0, Math.ceil(rows.length / size) - 1));
      state.pages[key] = page;
      body.replaceChildren();
      for (const item of rows.slice(page * size, (page + 1) * size)) {
        const row = element('tr');
        if (item.is_compaction) row.className = 'compaction';
        for (const value of cells(item)) {
          const td = element('td');
          td.append(value && typeof value === 'object' ? value : element('span', value));
          row.append(td);
        }
        body.append(row);
      }
      label.textContent = rows.length ? `${page * size + 1}–${Math.min((page + 1) * size, rows.length)} of ${rows.length}` : 'No rows';
      previous.disabled = page === 0;
      next.disabled = (page + 1) * size >= rows.length;
    }
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
    node.append(element('span', flags.join(' · '), 'detail'));
    if (row.has_cost_breakdown) node.append(element('span',
      `Main CCost ${ccost(row.main_ccost, false, row.main_estimated)} · Linked child CCost ${ccost(row.subagent_ccost, false, row.subagent_estimated)}`, 'detail'));
    return node;
  }
  function prompts(parent, block, state, index) {
    const title = element('h3', block.title || 'Session'); parent.append(title, link(block.session_id));
    parent.append(element('p', `Full-session CCost ${ccost(block.total_ccost, !block.comparison_cost_complete)} · Billing ${money(block.billed_cost)} · Duration ${duration(block.duration_ms)}`));
    if (block.total_has_cost_breakdown) parent.append(element('p',
      `Main CCost ${ccost(block.total_main_ccost, false, block.total_main_estimated)} · Linked child CCost ${ccost(block.total_subagent_ccost, false, block.total_subagent_estimated)}`));
    if (!block.rows.length) parent.append(element('p', 'This session exists but has no prompt rows.'));
    table(parent, 'Prompts · complete session totals, independent of page',
      ['Prompt', 'CCost', 'Calls', 'Duration', '~Ictx', '~Ictx CCost', '~Extra CCost', 'I/C/W/O %'], block.rows,
      row => [promptLabel(row), ccost(row.ccost, row.unresolved_cost, row.cost_estimated), known(row.calls),
        duration(row.duration_ms), known(row.incoming_context_tokens), ccost(row.incoming_context_ccost),
        ccost(row.extra_ccost), row.token_mix_percent == null ? 'Unknown' : row.token_mix_percent.join('/')],
      ['Complete session', ccost(block.total_ccost, !block.comparison_cost_complete), known(block.total_calls),
        duration(block.duration_ms), '—', known(block.total_ictx_cost_text), known(block.total_extra_cost_text), known(block.total_mix_text)],
      state, 'prompts-' + index);
  }
  function render(parent, result, state) {
    parent.replaceChildren();
    const view = result.view;
    parent.append(element('p', `Snapshot: ${new Date(result.observed_at_ms).toLocaleString()} · ${view.source_label} · ${result.source.status} · ${result.source.atomicity}. Frozen; Refresh explicitly to reacquire.`, 'snapshot'));
    if (result.source.status === 'partial') parent.append(element('p', `Partial source data (${view.source_warning_count} warnings). Values may be incomplete.`, 'warning'));
    parent.append(element('p', 'CCost = reference valuation, not provider billing. Unknown pricing is not zero. I/C/W/O = input/cache read/cache write/output. Durations are report execution durations, frozen at observation time.'));
    for (const note of [view.recent_model_notice, ...(view.notes || []), ...(view.model_comparison_promotion_notes || [])].filter(Boolean)) parent.append(element('p', note, 'warning'));
    if (view.session_usage.length || view.kind === 'sessions') {
      if (!view.session_usage.length) parent.append(element('p', 'Source acquired: no available sessions.'));
      table(parent, 'Sessions', ['Session / name', 'Model / effort', 'CCost', 'Prompts', 'Duration'], view.session_usage,
        row => { const name = element('span'); name.append(link(row.session_id), element('span', row.title, 'detail'));
          return [name, row.model + (row.multiple_models ? ' · multiple models' : ''), ccost(row.ccost, !row.complete), known(row.prompt_count), duration(row.duration_ms)]; },
        null, state, 'sessions');
    }
    view.prompt_blocks.forEach((block, index) => prompts(parent, block, state, index));
    if (view.model_comparison.length) {
      parent.append(element('p', `Model comparison sample: ${known(view.model_comparison_sample_size)} · Pricing retrieved ${view.pricing_retrieved_at_ms == null ? 'unknown' : new Date(view.pricing_retrieved_at_ms).toLocaleString()}`));
      table(parent, 'Reference models · shared CLI sample',
        ['Model', 'Publisher', 'Relative cost', 'Pricing', 'Released'], view.model_comparison,
        row => [row.model + (row.promotion_marker || '') + (row.recent ? ' · recent' : ''), row.publisher,
          known(row.relative_cost), known(row.price_summary), known(row.release_date)], null, state, 'models');
    }
    const accounts = view.accounts_quotas;
    if (view.kind === 'normal') {
      parent.append(element('h3', 'Accounts · independent observations'));
      if (!accounts || !accounts.accounts.length) parent.append(element('p', 'Account data unavailable or no accounts discovered. Session data remains independent.'));
      if (accounts) {
        for (const account of accounts.accounts) {
          const obs = account.observation;
          parent.append(element('h4', `${obs.label} · ${obs.provider_label} · ${obs.plan || 'Plan unknown'}`));
          parent.append(element('p', `${obs.availability} · ${obs.status} · ${obs.error_code || ''} · Observed ${obs.observed_at_ms == null ? 'unknown' : new Date(obs.observed_at_ms).toLocaleString()}`, obs.has_error || obs.has_warning ? 'warning' : ''));
          parent.append(element('p', `Billed today ${money(account.billed_today)} · Billed month ${money(account.billed_month)}`));
          for (const scope of account.ccost_scopes) parent.append(element('p', `${scope.name} CCost ${ccost(scope.cost?.known_ccost)}`));
          if (account.unaccounted_usage != null) parent.append(element('p', `Unaccounted usage (estimate): ${known(account.unaccounted_usage)}`));
          if (account.ccost_account_unknown) parent.append(element('p', 'CCost account attribution unknown.', 'warning'));
          for (const note of account.ccost_notes || []) parent.append(element('p', note, 'warning'));
          table(parent, 'Quota: ' + obs.label, ['Period', 'Used', 'Limit', 'Remaining', 'Status'], obs.quotas,
            q => [q.label, `${known(q.used)} ${q.unit}`, q.unlimited ? 'Unlimited' : known(q.limit), known(q.remaining), q.status], null, state, 'account-' + obs.id);
        }
      }
    }
    if (view.token_mix && view.token_mix.request_count) {
      parent.append(element('h3', 'Token Mix · report sample'));
      parent.append(element('p', `I/C/W/O tokens: ${view.token_mix.totals.join('/')} · Requests: ${view.token_mix.request_count}`));
    }
  }
  return {render, element};
})();
