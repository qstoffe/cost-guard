'use strict';
// Keyed prompt cards over server-owned membership, metrics and lifecycle.
const WatchView = (() => {
  const el = (...args) => ReportView.element(...args);
  const display = (row, key) => ReportView.display(row, key);
  const text = (node, value) => ReportView.text(node, value);
  function protectedNode(node) {
    const selection = window.getSelection?.();
    return node.contains(document.activeElement) || Boolean(selection && !selection.isCollapsed &&
      (node.contains(selection.anchorNode) || node.contains(selection.focusNode)));
  }
  function reconcile(parent, wanted) {
    const keep = new Set(wanted);
    for (const node of [...parent.children]) if (!keep.has(node)) node.remove();
    wanted.forEach((node, index) => {
      if (parent.children[index] !== node) parent.insertBefore(node, parent.children[index] || null);
    });
  }
  function disclosure() {
    const node = el('details'), summary = el('summary'), list = el('div');
    node.append(summary, list);
    return {node, summary, list};
  }
  function fragments(target, parts) {
    const signature = JSON.stringify(parts);
    if (target.signature === signature || protectedNode(target)) return;
    target.replaceChildren(...parts.map(([label, role]) => el('span', label, role)));
    target.signature = signature;
  }
  function quotaTrack(value) {
    const quota = value.quota, summary = quota.unlimited ? 'Unlimited' : value.used_percent === '—' ? '—' : value.used_percent + ' used';
    const label = el('div', () => `${quota.label} · ${summary} (${value.cost == null ? '—' : display(value.cost, 'account_ccost')})`,
      value.exhausted ? 'warning metric-value' : 'metric-value');
    const track = el('div', undefined, 'watch-quota-track');
    if (!quota.unlimited && value.used_fraction != null) {
      const bar = el('progress'); bar.max = 1; bar.value = value.used_fraction;
      bar.setAttribute('aria-label', quota.label + ' used'); bar.setAttribute('aria-valuetext', summary);
      if (value.exhausted) bar.className = 'watch-quota-exhausted';
      track.append(bar);
    } else track.append(el('span', quota.unlimited ? 'No usage limit' : 'Usage unavailable', 'detail'));
    return [label, track];
  }
  function quotaDetails(parent, value) {
    const quota = value.quota;
    parent.append(el('p', quota.window_active === false && quota.reset_at_ms == null ? 'Reset: not started' : display(quota, 'reset'), 'detail'));
    if (value.pace) {
      parent.append(el('p', `Remaining: ${display(value.pace, 'per_day')}/day`, 'detail'));
      parent.append(el('p', value.pace.workdays === 0 ? 'Remaining: no workdays left' :
        `Remaining: ${display(value.pace, 'per_workday')}/workday`, 'detail'));
    }
    if (value.restricted) parent.append(el('p', quota.label + ' · Provider restriction reported', 'warning'));
  }
  function accounts(parent, value) {
    if (!value?.accounts.length) { parent.append(el('p', 'No configured accounts detected.')); return; }
    const grid = el('div', undefined, 'account-grid watch-account-grid');
    for (const item of value.accounts) {
      const obs = item.observation, card = el('section', undefined, 'account-card watch-subscription');
      card.dataset.availability = obs.availability;
      const today = item.ccost_scopes.find(scope => scope.name === 'today');
      const cost = el('p', () => `CCost Today: ${today?.cost == null ? '—' : display(today.cost, 'account_ccost')}`, 'metric-value');
      cost.title = item.today_note;
      const [label, track] = quotaTrack(item.primary), primary = el('div', undefined, 'watch-primary-details');
      quotaDetails(primary, item.primary);
      const lower = el('div', undefined, 'watch-account-footer');
      const secondary = el('div', undefined, 'watch-account-details');
      for (const quota of item.secondary) {
        const group = el('div', undefined, 'watch-secondary-quota');
        group.append(...quotaTrack(quota)); quotaDetails(group, quota); secondary.append(group);
      }
      if (item.secondary.length) lower.append(secondary);
      const cause = {auth_failure: 'Authentication unavailable', transport_failure: 'Connection failed',
        unsupported_auth_method: 'Unsupported authentication method', format_changed: 'Provider format changed',
        software_failure: 'Account refresh failed', discovery_failure: 'Account metadata unavailable',
        rate_limited: 'Rate limited', account_unavailable: 'Account unavailable'}[obs.error_code];
      const state = {partial: 'Partial quota data', stale: 'Stale · last observation, not current',
        unavailable: 'Quota unavailable', error: 'Refresh failed'}[obs.availability];
      if (state || cause) lower.append(el('p', [state, cause].filter(Boolean).join(' · '), 'warning'));
      if (obs.status === 'blocked' && ![item.primary, ...item.secondary].some(quota => quota.exhausted || quota.restricted))
        lower.append(el('p', 'Provider restriction reported; utilization not established', 'warning'));
      if (obs.has_warning) lower.append(el('p', 'Provider warning', 'warning'));
      if (item.ccost_account_unknown) lower.append(el('p', 'CCost account attribution unavailable', 'detail'));
      card.append(el('h4', obs.label), cost, label, track, primary);
      if (lower.children.length) card.append(lower);
      grid.append(card);
    }
    parent.append(grid);
  }
  function daily(parent, value, state) {
    parent.replaceChildren(el('strong', 'Total Today'));
    if (!value) { parent.append(el('span', state === 'unavailable' ? 'Daily activity unavailable' : 'Loading daily activity…')); return; }
    parent.append(el('span', () => value.total.observed_requests && !value.total.priced_requests ? 'N/A' : display(value.total, 'known_ccost'), 'metric-value'));
    const count = el('span', `${value.prompt_count} prompts`);
    count.title = 'Distinct initiating user prompts with requests attributed to this local calendar day, including continuing prompts and pre-Watch activity.';
    parent.append(count, el('span', 'Token Mix %'));
    for (const [key, label] of Object.entries(value.mix.display.token_categories))
      parent.append(el('span', () => `${label}: ${display(value.mix, key)}`, 'watch-daily-category'));
    if (!value.total.complete || !value.mix.cost_complete || value.mix.totals.some(amount => amount == null) && value.mix.request_count)
      parent.append(el('span', 'Partial pricing / telemetry', 'warning'));
    if (!value.mix.request_count) parent.append(el('span', 'No recorded usage', 'detail'));
    if (state === 'unavailable') parent.append(el('span', 'Source unavailable · retained daily observation', 'warning'));
  }
  class Card {
    constructor() {
      this.root = el('article', undefined, 'watch-card');
      this.title = el('a'); const heading = el('h3'); heading.append(this.title);
      this.message = el('p', undefined, 'detail'); this.message.setAttribute('role', 'status');
      const scroll = el('div', undefined, 'watch-table-scroll');
      scroll.tabIndex = 0; scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', 'Session prompts');
      const table = el('table', undefined, 'watch-prompt-table');
      const head = el('thead'), header = el('tr');
      for (const name of ['Started', 'Prompt', 'Model', 'Effort', 'CCost', 'Model Calls', 'Duration', 'Δ Ctx', 'Context']) {
        const th = el('th', name); th.scope = 'col';
        if (name === 'Context') th.title = 'Estimated next incoming context (CLI Watch)';
        header.append(th);
      }
      head.append(header); this.body = el('tbody'); table.append(head, this.body); scroll.append(table);
      this.activity = el('div', undefined, 'watch-activity');
      this.tools = disclosure(); this.skills = disclosure(); this.running = el('p'); this.background = el('p');
      this.activity.append(this.tools.node, this.skills.node, this.running, this.background);
      this.warning = el('div', undefined, 'watch-context-warning');
      this.root.append(heading, this.message, scroll, this.warning, this.activity);
    }
    update(value, historical) {
      this.value = value;
      this.root.dataset.session = value.session_id;
      text(this.title, value.title || value.session_id);
      if (/^[A-Za-z0-9_-]{1,200}$/.test(value.session_id)) this.title.href = '#/sessions/' + value.session_id;
      this.title.className = !historical && value.rows.some(item => item.prompt.in_progress) ? 'watch-running-title' : '';
      text(this.message, value.state === 'unavailable' ? 'Source unavailable; retained contents are not current.' : value.state === 'partial' ? 'Partial / retained evidence' : !value.rows.length ? 'Loading prompts…' : '');
      if (!protectedNode(this.body)) {
        const old = new Map([...this.body.children].map(node => [node.dataset.id, node]));
        reconcile(this.body, value.rows.map(item => {
          const prompt = item.prompt, row = old.get(prompt.event_id) || el('tr');
          row.dataset.id = prompt.event_id;
          const signature = JSON.stringify([item, historical]);
          if (row.signature !== signature) {
            const focal = !historical && prompt.event_id === value.focal_id;
            row.className = focal ? prompt.in_progress ? 'watch-running' : prompt.aborted || prompt.has_error ? 'watch-error' : 'watch-success' : '';
            const outcome = prompt.in_progress ? 'Running' : prompt.aborted ? 'Aborted' : prompt.has_error ? 'Error' : prompt.completed_successfully ? 'Completed' : 'Ended';
            const reason = !prompt.in_progress && {quota_limit: 'quota limit', rate_limit: 'rate limit',
              tool_call_limit: 'tool-call limit', step_limit: 'step limit', user: 'by user'}[prompt.abort_reason];
            row.setAttribute('aria-label', `Prompt ${prompt.prompt_number} · ${outcome}${reason ? ' · ' + reason : ''}`);
            const label = el('span', prompt.preview || '');
            label.title = prompt.preview || '';
            const model = el('span', item.model);
            if (prompt.has_additional_model) model.title = 'Additional model contribution included in canonical cost and calls';
            const context = display(item.live_context, 'watch_next_context_tokens');
            const cells = [`Prompt ${prompt.prompt_number} ${display(prompt, historical ? 'date_time' : 'clock')}`, label, model, item.effort,
              () => display(prompt, 'ccost'), String(prompt.calls), display(item, 'watch_duration_ms'),
              display(item.live_context, 'watch_delta_context_tokens'), context === 'N/A' ? context : '~' + context];
            row.replaceChildren(...cells.map(value => { const cell = el('td'); cell.append(typeof value === 'object' ? value : el('span', value)); return cell; }));
            row.signature = signature;
          }
          return row;
        }));
      }
      this.activity.hidden = historical || !value.focal_id;
      if (!historical) this.drawActivity(value.rows.find(row => row.prompt.event_id === value.focal_id)?.tool);
      const warning = value.context_warning;
      this.warning.hidden = !warning || warning.severity === 'none';
      text(this.warning, () => this.warning.hidden ? '' : `⚠ ${warning.text.replace(/^\[|\]$/g, '')} ${display(warning, 'warning_cost')}`.trim());
      this.warning.dataset.severity = warning?.severity || 'none';
    }
    drawActivity(tool) {
      const groups = [...(tool?.counts || [])].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
      const total = groups.reduce((sum, pair) => sum + pair[1], 0);
      const omitted = groups.slice(5).reduce((sum, pair) => sum + pair[1], 0);
      const toolParts = [[`${total} tool calls`, ''], ...groups.slice(0, 5).map(([name, count]) => [` · ${count} × ${name}`, ''])];
      if (omitted) toolParts.push([` · ${omitted} × other`, '']);
      if (tool?.failed_count) toolParts.push([` · ${tool.failed_count} failed / cancelled`, 'watch-activity-error']);
      fragments(this.tools.summary, toolParts);
      const skills = tool?.skills || [];
      const skillParts = skill => [[skill.skill_id, ''], ...(skill.failed_count ? [[` (${skill.failed_count} failed)`, 'watch-activity-error']] : [])];
      const summary = [[`${skills.length} skills`, '']];
      for (const skill of skills.slice(0, 5)) summary.push([' · ', ''], ...skillParts(skill));
      if (skills.length > 5) summary.push([` · ${skills.length - 5} other`, '']);
      fragments(this.skills.summary, summary);
      const toolLines = groups.map(([name, count]) => [[`${count} × ${name}`, '']]);
      if (tool?.failed_count) toolLines.push([[`${tool.failed_count} failed / cancelled`, 'watch-activity-error']]);
      for (const [target, lines, empty] of [[this.tools.list, toolLines, 'No tool calls'], [this.skills.list, skills.map(skillParts), 'No confirmed custom skills']]) {
        const signature = JSON.stringify(lines);
        if (target.signature !== signature && !protectedNode(target)) {
          target.replaceChildren(...(lines.length ? lines : [[[empty, '']]]).map(parts => {
            const line = el('div'); fragments(line, parts); return line;
          }));
          target.signature = signature;
        }
      }
      text(this.running, tool?.running_tool ? `Running: ${tool.running_tool} ${display(tool, 'running_ms')}` : '');
      this.running.hidden = !tool?.running_tool;
      const kinds = tool?.background_kinds || [];
      const background = kinds.length === 1 ? kinds[0] : new Set(kinds).size === 1 ? `${kinds.length}× ${kinds[0]}` : `${kinds.length} jobs`;
      text(this.background, kinds.length ? `Running: ${background} ${display(tool, 'background_ms')}` : '');
      this.background.hidden = !kinds.length;
    }
  }
  class View {
    constructor(state) {
      this.state = state;
      this.root = el('div', undefined, 'watch-view');
      this.earlier = el('details', undefined, 'watch-earlier');
      this.earlier.append(el('summary', 'Earlier Prompts'));
      this.history = el('div', undefined, 'watch-history'); this.earlier.append(this.history);
      this.active = el('div', undefined, 'watch-active');
      this.empty = el('p'); this.empty.setAttribute('role', 'status');
      this.accounts = el('div'); this.cards = new Map();
      this.daily = el('section', undefined, 'watch-daily');
      this.daily.setAttribute('aria-label', 'Total Today');
      this.root.append(this.earlier, this.empty, this.active, this.daily, this.accounts);
    }
    attach(parent) {
      ReportView.syncUnits(this.root);
      if (this.root.parentNode !== parent) parent.replaceChildren(this.root);
    }
    update(result) {
      const view = result.view, active = view.active_cards || [], history = view.history_cards || [];
      const fresh = result.state === 'running' && this.state.connection === 'Live connected.';
      text(this.empty, !fresh ? 'Source / connection unavailable; last observation retained.' : view.cards_state === 'loading' || view.cards_state == null ? 'Loading active prompts…' : view.cards_state === 'unavailable' ? 'Some prompt sources are unavailable.' : !active.some(card => card.rows.some(row => row.prompt.in_progress)) ? 'No running prompts' : '');
      const keep = new Set();
      for (const [parent, values, historical] of [[this.active, active, false], [this.history, history, true]]) {
        const wanted = values.map(value => {
          const key = JSON.stringify([value.session_id, value.focal_id || 'history']); keep.add(key);
          if (!this.cards.has(key)) this.cards.set(key, new Card());
          const card = this.cards.get(key); card.update(value, historical); return card.root;
        });
        if (historical && !wanted.length) wanted.push(el('p', view.history_state === 'loading' ? 'Loading earlier prompts…' : view.history_state === 'unavailable' ? 'Earlier prompts unavailable' : 'No earlier prompts'));
        reconcile(parent, wanted);
      }
      for (const key of this.cards.keys()) if (!keep.has(key)) this.cards.delete(key);
      const dailyState = view.daily_usage && view.daily_state !== 'unavailable' ? 'observed' : view.daily_state;
      const dailySignature = JSON.stringify([view.daily_usage, dailyState]);
      if (this.dailySignature !== dailySignature && !protectedNode(this.daily)) {
        daily(this.daily, view.daily_usage, view.daily_state); this.dailySignature = dailySignature;
      }
      const signature = JSON.stringify([view.accounts, view.quota_stale, view.quota_recovering_count]);
      if (this.accountSignature !== signature && !protectedNode(this.accounts)) {
        this.accounts.replaceChildren();
        accounts(this.accounts, view.accounts);
        this.accountSignature = signature;
      }
    }
  }
  return {View};
})();
