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
    const grid = element('table', undefined, key === 'models' ? 'models-table' : '');
    grid.append(element('caption', title));
    const head = element('thead'), header = element('tr');
    const headers = [];
    columns.forEach((column, index) => {
      const th = element('th'), button = element('button', column); th.scope = 'col';
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
      for (const value of totals) row.append(element('td', value));
      foot.append(row); grid.append(foot);
    }
    scroll.append(grid); section.append(scroll); parent.append(section);
    const pager = element('div', undefined, 'pager');
     const previous = element(remote ? 'a' : 'button', 'Previous'), next = element(remote ? 'a' : 'button', 'Next');
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
    if (key === 'models') {
      const reset = element('button', 'CLI default order');
      reset.addEventListener('click', () => { delete state.sorts[key]; state.pages[key] = 0; draw(); });
      pager.append(reset);
    }
    draw();
  }
  function overviewConcepts(parent, view) {
    const concepts = element('div', undefined, 'report-concepts');
    function concept(label, value, explanation) {
      const card = element('div');
      card.append(element('h3', label), element('p', value, 'metric-value'));
      const help = element('details');
      help.append(element('summary', 'About ' + label), element('p', explanation));
      card.append(help); concepts.append(card);
      return card;
    }
    const costCard = concept('CCost', '1 CCost = 1 Copilot AI credit',
      'Reference token valuation, not actual billing. Flat-rate accounts use Copilot’s published token rates. Unlabeled cost figures are CCost; unknown pricing is not zero.');
    costCard.append(element('p', 'CCost = reference valuation, not provider billing. Unknown pricing is not zero.', 'detail'));
    const mix = view.token_mix;
    const mixCard = concept('Token Mix %', mix ? display(mix, 'percentages') + ' · I/C/W/O' : 'N/A',
      'Observed input/cache-read/cache-write/output token shares. Output includes reasoning. The report sample is independent of account-period usage.');
    if (mix) mixCard.append(element('p',
      `${mix.sample_size} priced prompts · ${display(mix, 'totals')} tokens · CCost ${display(mix, 'costs')}`,
      mix.cost_complete ? 'detail' : 'detail partial'));
    concept('Relative CCost', view.model_comparison_sample_size ? `${view.model_comparison_sample_size} completed ${view.model_comparison_sample_size === 1 ? 'prompt' : 'prompts'}` : 'No completed priced prompts',
      view.model_comparison_sample_size ? 'Applies the completed-prompt Token Mix % to every model and tier, with the same cheapest comparable base as 1.0x. Arrows show context-tier prices; > or ≥ marks the published input-token boundary.' :
        'Relative CCost stays blank; a hidden 2/96/1/1 mix orders published prices. No synthetic multipliers are shown.');
    parent.append(concepts);
  }
  function modelRelative(row, sampled) {
    const cell = element('span', undefined, 'model-relative' + (row.promotional ? ' promotion' : ''));
    cell.append(element('span', row.promotion_marker != null ? `*${row.promotion_marker} ` : '', 'model-marker'));
    const [base, ...tiers] = sampled ? display(row, 'relative_cost').split(' → ') : [''];
    cell.append(element('span', base, 'model-ratio'));
    const levels = element('span', undefined, 'model-tiers');
    for (const tier of tiers) levels.append(element('span', ' → ' + tier, 'model-tier'));
    cell.append(levels);
    return cell;
  }
  function modelPrices(row) {
    const cell = element('span', undefined, 'model-prices' + (row.promotional ? ' promotion' : ''));
    display(row, 'price_summary').split('→').forEach((tier, index) =>
      cell.append(element('span', (index ? '→' : '') + tier.trim(), 'model-tier')));
    return cell;
  }
  function modelPriceKey(row) {
    // Published exact rate strings only; no Number coercion or price calculation.
    if (!row.price_summary || row.price_summary === 'N/A') return null;
    return row.price_summary.replaceAll(' -> ', '→').split('→').flatMap(tier => {
      const [rates, boundary = ''] = tier.trim().split(' ');
      return [...rates.split('/').map(rate => rate === '-' ? null : rate), boundary.replace(/[^0-9]/g, '') || '0'];
    });
  }
  function accountQuota(card, quota) {
    const row = element('div', undefined, 'quota-summary ' + (quota.display_roles || []).join(' ') +
      (quota.status === 'blocked' ? ' error' : ''));
    const status = quota.status === 'blocked' ? ' · BLOCKED' : ' · ' + quota.status;
    row.append(element('strong', quota.label + status));
    const remaining = quota.unlimited ? 'Unlimited' : quota.remaining_fraction == null ? 'Remaining unavailable' : display(quota, 'remaining_fraction') + ' remaining';
    row.append(element('span', remaining, 'metric-value'));
    // Only a known server-formatted fraction creates a determinate bar. Never coerce null to zero.
    if (!quota.unlimited && quota.remaining_fraction != null) {
      const bar = element('progress'); bar.max = 100;
      bar.value = display(quota, 'remaining_fraction').replace('%', '');
      bar.setAttribute('aria-label', quota.label + ' remaining');
      bar.setAttribute('aria-valuetext', remaining); row.append(bar);
    }
    const unit = quota.unit || 'units';
    if (quota.remaining != null) row.append(element('span', `${display(quota, 'remaining')} ${unit} remaining` +
      (quota.limit == null || quota.unlimited ? '' : ` / ${display(quota, 'limit')} ${unit}`)));
    else if (quota.used != null || quota.limit != null) row.append(element('span',
      `Used ${display(quota, 'used')} / ${quota.unlimited ? 'Unlimited' : display(quota, 'limit')} ${unit}`));
    if (quota.remaining_money != null || quota.limit_money != null) row.append(element('span',
      `Native money ${display(quota, 'remaining_money')} / ${display(quota, 'limit_money')}`, 'detail'));
    row.append(element('span', display(quota, 'reset'), 'detail'));
    const window = [quota.period !== 'unknown' && quota.period,
      quota.duration_seconds && display(quota, 'window') + ' window',
      quota.scope && quota.scope !== 'account' && quota.scope, quota.model_id].filter(Boolean);
    if (window.length) row.append(element('span', window.join(' · '), 'detail'));
    card.append(row);
  }
  function accountStatus(obs) {
    const cause = {auth_failure: 'Authentication unavailable', unsupported_auth_method: 'Unsupported authentication method',
      transport_failure: 'Connection failed', format_changed: 'Provider format changed',
      software_failure: 'Account refresh failed internally', discovery_failure: 'Account metadata unavailable',
      rate_limited: 'Rate limited', account_unavailable: 'Account unavailable'}[obs.error_code];
    const availability = {available: 'Available', partial: 'Partial quota data', stale: 'Stale — last observation, not current',
      unavailable: 'Unavailable', error: 'Refresh failed'}[obs.availability] || 'Availability unknown';
    const status = obs.status === 'available' ? '' : obs.status === 'blocked' ? 'BLOCKED' : 'Usage status unknown';
    return [availability, status, cause, obs.has_warning && 'Provider warning'].filter(Boolean).join(' · ');
  }
  function overviewAccounts(parent, accounts, title = 'Accounts Overview', detailed = false) {
    parent.append(element('h3', title));
    if (!accounts?.accounts.length) { parent.append(element('p', 'No configured accounts detected.')); return; }
    const group = element('div', undefined, 'account-grid');
    for (const account of accounts.accounts) {
      const obs = account.observation, card = element('section', undefined, 'account-card');
      if (detailed) card.setAttribute('data-availability', obs.availability);
      card.append(element('h4', obs.label), element('p', [obs.provider_label, obs.plan].filter(Boolean).join(' · '), 'detail'));
      if (detailed) card.append(element('p', accountStatus(obs),
        obs.has_error || obs.status === 'blocked' ? 'error account-status' : obs.has_warning || obs.availability !== 'available' ? 'warning account-status' : 'account-status'));
      for (const scope of account.ccost_scopes) card.append(element('p', `CCost ${scope.name}: ${scope.cost == null ? '—' : display(scope.cost, 'account_ccost')}`, 'metric-value'));
      if (detailed || account.billed_today != null) card.append(element('p', 'Billed today: ' + display(account, 'billed_today')));
      if (detailed || account.billed_month != null) card.append(element('p', 'Billed month: ' + display(account, 'billed_month')));
      for (const quota of obs.quotas) {
        if (detailed) { accountQuota(card, quota); continue; }
        const row = element('div', undefined, 'quota-summary ' + (quota.display_roles || []).join(' '));
        row.append(element('strong', quota.label), element('span',
          `${display(quota, 'remaining')} ${quota.unit} remaining / ${quota.unlimited ? 'Unlimited' : display(quota, 'limit')} · ${display(quota, 'remaining_fraction')}`));
        row.append(element('span', `Used ${display(quota, 'used')} · Reset ${display(quota, 'reset_at_ms')} · ${quota.status}${quota.window_active === false ? ' · Inactive window' : ''}`, 'detail'));
        card.append(row);
      }
      for (const pace of account.pace) card.append(element('p', `${pace.label} Pace: ${display(pace, 'per_day')} ${pace.unit}/day · ${pace.days} days · ${pace.per_workday == null ? 'no workdays left' : display(pace, 'per_workday') + ' per workday'}`, 'detail'));
      if (['github-copilot', 'github-copilot-enterprise'].includes(obs.provider_id) || account.unaccounted_usage != null) card.append(element('p', 'Unaccounted usage (estimate): ' + display(account, 'unaccounted_usage')));
      if (!detailed && (obs.has_error || obs.has_warning || ['stale', 'unavailable', 'error', 'paused', 'blocked'].includes(obs.status))) card.append(element('p', `${obs.availability} · ${obs.status} · ${obs.error_code || 'Account warning'}`, 'warning'));
      if (detailed && !obs.quotas.length) card.append(element('p', 'Quota unavailable; not zero or unlimited.', 'detail'));
      if (account.ccost_account_unknown) card.append(element('p', 'CCost account attribution unknown.', 'warning'));
      for (const note of account.ccost_notes || []) card.append(element('p', note, 'warning'));
      const details = element('details');
      details.append(element('summary', 'Observation details'), element('p', `${obs.availability} · ${obs.status} · Observed ${display(obs, 'observed_at_ms')}`));
      for (const bill of obs.billing || []) (detailed ? card : details).append(element('p', `${bill.label} · ${bill.period} · ${bill.kind} · ${display(bill, 'amount')} ${bill.currency} · ${bill.status}`));
      for (const quota of obs.quotas) details.append(element('p', detailed ?
        `${quota.label} · Used ${display(quota, 'used')} ${quota.unit || 'units'} · ${quota.status}` :
        `${quota.label} · ${quota.period} · ${known(quota.duration_seconds)} s · ${quota.scope || ''} · Native money remaining/limit ${display(quota, 'remaining_money')}/${display(quota, 'limit_money')}`));
      card.append(details); group.append(card);
    }
    parent.append(group);
  }
  function promptLabel(row, live = false) {
    const node = element('span', `${row.label || 'Prompt'} ${row.prompt_number == null ? '' : '#' + row.prompt_number} ${row.preview || ''}`.trim());
    const flags = [row.model_effort, row.is_compaction && 'Compaction',
      row.in_progress && (live ? 'Running · provisional' : 'Running at snapshot · provisional'), row.aborted && 'Aborted',
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
    const overview = section === 'overview' && view.kind === 'normal';
    parent.append(element('p', `Snapshot: ${new Date(result.observed_at_ms).toLocaleString()} · ${view.source_label} · ${result.source.status} · ${result.source.atomicity}. Frozen; Refresh explicitly to reacquire.`, 'snapshot'));
    if (result.source.status === 'partial') parent.append(element('p', `Partial source data (${view.source_warning_count} warnings). Values may be incomplete.`, 'warning'));
    if (view.model_availability_unverified) parent.append(element('p', 'Model availability unverified: showing the full catalog or all historically used models, not a verified selectable list.', 'warning'));
    if (view.model_availability_empty) parent.append(element('p', 'No available OpenCode models match the pricing catalog.', 'warning'));
    if (view.kind === 'date') parent.append(element('p', `Inclusive local range ${result.scope.date_text} · ${result.scope.timezone_id} · [${result.scope.start_ms}, ${result.scope.end_ms}) milliseconds. Prompt links open complete sessions; use Back to return to this frozen range.`));
    const definitions = element('details');
    definitions.append(element('summary', 'Reading this report'), element('p', 'CCost = reference valuation, not provider billing. Unknown pricing is not zero. I/C/W/O = input/cache read/cache write/output. Durations are report execution durations, frozen at observation time.'));
    if (!overview) parent.append(definitions);
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
    if (['overview', 'models'].includes(section) && view.model_comparison.length) {
      if (view.token_mix && !overview) mixSummary(parent, view.token_mix);
      if (!overview) parent.append(element('p', view.model_comparison_sample_size ?
        `Relative CCost · ${view.model_comparison_sample_size} priced completed prompts · cheapest comparable base = 1.0x. Arrows show input-context tiers (> or ≥). Reference valuation, not billed USD.` :
        'No completed priced prompts: relative cells stay blank. A hidden 2/96/1/1 mix orders published prices; no synthetic multipliers are shown.', 'detail'));
      parent.append(element('p', `Pricing/cache metadata: ${display(view, 'pricing_retrieved_at_ms')}`, 'detail'));
      const all = view.kind === 'all-models';
      table(parent, overview ? 'Reference models' : 'Reference models · shared CLI sample · default exact server ranking',
        ['Publisher', 'Model', 'Relative CCost', ...(all ? ['GitHub USD/M I/C/W/O'] : []), 'Release date'], view.model_comparison,
        row => [row.publisher || 'N/A', element('span', row.model + (row.recent ? ' · recent' : '') + (row.superseded ? ' · older stable variant' : ''), row.recent ? 'new' : ''),
          modelRelative(row, view.model_comparison_sample_size),
          ...(all ? [modelPrices(row)] : []), element('span', row.release_date || 'N/A', row.recent ? 'new' : '')], null, state, 'models',
        row => [row.publisher, row.model, row.relative_cost, ...(all ? [modelPriceKey(row)] : []), row.release_date]);
      if (!overview && all) parent.append(element('p', 'GitHub USD/M I/C/W/O: exact published reference rates per million input/cache-read/cache-write/output tokens, not billed spend.', 'detail'));
      if (!overview && view.model_comparison.some(row => row.superseded)) parent.append(element('p', 'Older stable variants are muted, not hidden. Promotions use numbered * markers; recent releases are highlighted.', 'detail'));
      for (const note of view.model_comparison_promotion_notes || []) parent.append(element('p', note, 'promotion'));
      if (view.recent_model_notice) parent.append(element('p', view.recent_model_notice, 'new'));
    }
    if (section === 'models' && !view.model_comparison.length) parent.append(element('p', 'No matching reference models. Availability warnings, if any, are shown above.'));
    const accounts = view.accounts_quotas;
    if (overview) overviewAccounts(parent, accounts);
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
  return {render, renderLive, element, detailCells, detailTotals, compare, overviewAccounts};
})();
