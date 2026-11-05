'use strict';
// Keyed prompt cards over server-owned membership, metrics and lifecycle.
const WatchView = (() => {
  const el = (...args) => ReportView.element(...args);
  const display = (row, key) => ReportView.display(row, key);
  const text = (node, value) => ReportView.text(node, value);
  // Presentation-only grace: retries are not observations or a lifecycle change.
  function delayed(owner, key, waiting) {
    if (!waiting) { owner[key] = null; return false; }
    owner[key] ??= Date.now();
    return Date.now() - owner[key] >= 30000;
  }
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
  function drawDisclosure(target, summary, lines, empty) {
    // Retain header and breakdown together while focus/selection protects either.
    if (protectedNode(target.node)) return;
    fragments(target.summary, summary);
    const signature = JSON.stringify(lines);
    if (target.list.signature === signature) return;
    target.list.replaceChildren(...(lines.length ? lines : [[[empty, '']]]).map(parts => {
      const line = el('div'); fragments(line, parts); return line;
    }));
    target.list.signature = signature;
  }
  function quotaTrack(value) {
    const quota = value.quota, view = () => ReportView.quotaView(quota, value);
    const summary = () => quota.unlimited ? 'Unlimited' : view().percent === '—' ? '—' : view().percent + ' ' + view().mode;
    const label = el('div'); label.append(el('span', () => `${quota.label} · ${summary()}`));
    ReportView.bind(label, () => label.className = 'watch-quota-summary metric-value' + (view().exhausted ? ' watch-quota-exhausted' : ''));
    label.append(el('span', () => ` (${display(quota, 'ccost_' + view().mode)})`, 'watch-period-cost'));
    const capacity = el('div', undefined, 'watch-quota-capacity metric-value');
    capacity.append(ContextHelp.value(el('span', () => 'Capacity: ' + display(quota, 'ccost_capacity')), () => ReportView.quotaHelp(quota)));
    if (view().note) label.append(el('span', ' · ' + view().note, 'warning'));
    const track = el('div', undefined, 'watch-quota-track');
    if (!quota.unlimited && value.used_fraction != null) {
      const bar = el('progress'); bar.max = 1;
      ReportView.bind(bar, () => {
        bar.value = view().fraction;
        bar.setAttribute('aria-label', quota.label + ' ' + view().mode);
        bar.setAttribute('aria-valuetext', summary() + (view().exhausted ? ' · exhausted' : ''));
        bar.className = view().exhausted ? 'watch-quota-exhausted' : '';
      });
      if (value.exhausted) bar.className = 'watch-quota-exhausted';
      track.append(bar);
    } else track.append(el('span', quota.unlimited ? 'No usage limit' : 'Usage unavailable', 'detail'));
    return [label, capacity, track];
  }
  function quotaDetails(parent, value) {
    const quota = value.quota;
    const reset = el('p', undefined, 'detail'), clock = el('span', display(value, 'watch_reset')); reset.append(clock);
    if (quota.reset_at_ms != null) ContextHelp.value(clock, display(quota, 'reset_at_ms'));
    parent.append(reset);
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
      ReportView.bind(card, () => card.dataset.exhausted = String([item.primary, ...item.secondary].some(value => ReportView.quotaView(value.quota, value).exhausted)));
      const today = item.ccost_scopes.find(scope => scope.name === 'today');
      const cost = el('p', undefined, 'metric-value');
      cost.append(ContextHelp.value(el('span', () => `CCost Today: ${today?.cost == null ? '—' : display(today.cost, 'account_ccost')}`),
        'This account’s reference cost in your configured local day.' + (item.today_note ? '\n' + item.today_note : '')));
      const [label, capacity, track] = quotaTrack(item.primary), primary = el('div', undefined, 'watch-primary-details');
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
      card.append(el('h4', obs.label), cost, label, capacity, track, primary);
      if (lower.children.length) card.append(lower);
      grid.append(card);
    }
    parent.append(grid);
  }
  function daily(parent, value, state, waiting) {
    parent.replaceChildren(ContextHelp.value(el('strong', 'CCost Today'), 'Reference cost of today’s model activity in your configured local day.'));
    if (!value) { parent.append(el('span', state === 'unavailable' ? 'Daily activity unavailable' : waiting ? 'Daily updates delayed; check source availability.' : '—')); return; }
    parent.append(ContextHelp.value(el('span', () => value.total.observed_requests && !value.total.priced_requests ? 'N/A' : display(value.total, 'known_ccost'), 'metric-value'),
      'Today’s reference CCost, including recorded activity before Watch opened.' + (!value.total.complete ? '\n? — Partial pricing.' : '')));
    const count = ContextHelp.value(el('span', `${value.prompt_count} prompts`), 'Prompts with model requests today, including activity before Watch opened.');
    parent.append(count, ContextHelp.value(el('span', 'Token Mix %'), 'Token shares, not cost: Input / Cached input / Cache write / Output (including reasoning).'));
    for (const [key, label] of Object.entries(value.mix.display.token_categories))
      parent.append(el('span', () => `${label}: ${display(value.mix, key)}`, 'watch-daily-category'));
    if (!value.total.complete || !value.mix.cost_complete || value.mix.totals.some(amount => amount == null) && value.mix.request_count)
      parent.append(el('span', 'Partial pricing / token data', 'warning'));
    if (!value.mix.request_count) parent.append(el('span', 'No recorded usage', 'detail'));
    if (state === 'unavailable') parent.append(el('span', 'Source unavailable · retained daily observation', 'warning'));
    if (waiting) parent.append(el('span', 'Daily updates delayed · retained observation, not current', 'detail'));
  }
  function promptCost(prompt) {
    const total = display(prompt, 'ccost');
    if (!total || total === 'N/A') return total;
    // Match only the selected unit's displayed zero, never missing/partial data
    // or a small positive Credits token such as <0.1. Canonical values stay intact.
    const zero = /^(\??)(\$?0(?:\.0+)?)$/.exec(total);
    if (zero) return `${total} (${zero[2]} + ${zero[2]})`;
    return `${total} (${display(prompt, 'incoming_context_ccost')} + ${display(prompt, 'extra_ccost')})`;
  }
  function promptRole(prompt) {
    return !prompt ? '' : prompt.in_progress ? 'running' : prompt.aborted || prompt.has_error ? 'error' :
      prompt.completed_successfully ? 'success' : '';
  }
  const columns = [
    ['Started', 'When this prompt started, in local time. Hover or focus the clock for the full date.'],
    ['Duration', 'Time spent on this prompt.\nStops advancing when work ends or updates are unavailable.'],
    ['Prompt', 'The prompt’s number within its session and a short preview of your message.'],
    ['Model', '• Main prompt — The model shown in this column.\n• Linked subagents — May use other models; their activity is included in prompt totals.'],
    ['Effort', 'How much reasoning the model was asked to do.'],
    ['CCost (I + E)', 'Estimated reference cost of this prompt, not your bill.\n\nI — Incoming context cost on the first model request.\nE — Other cost: output, later requests and linked subagents.\nTotal = I + E when fully priced, before display rounding.\nA displayed zero shows two zero components in this unit, even when component evidence is unavailable.\n\nN/A — Cost unavailable, not zero.\n? — Part of the cost cannot be priced.\nI is a cost here, not the Input token share.'],
    ['Calls', 'Model requests for this prompt, including linked subagents.\nNot tool calls.'],
    ['Token Mix %', 'Token percentages in I / C / W / O order, not cost.\n\nI — Input: new input.\nC — Cached input: reused input.\nW — Cache write: input saved for reuse.\nO — Output: generated tokens, including reasoning.\n\nN/A or running — No reliable breakdown yet. Requires recorded usage with all four categories.'],
    ['Ictx', 'Input context size on this prompt’s first request; may be estimated.\nN/A — First-request data unavailable, not zero.\nNot the next session context or a sum of requests.'],
    ['Δ Ctx', 'How much context changed since the preceding known context.\nA negative value means it shrank; this is not the total size.']
  ];
  function columnHeader(name, explanation) {
    const th = el('th'); th.scope = 'col';
    const button = ContextHelp.button(name, explanation); button.className += ' watch-column-help';
    th.append(button); return th;
  }
  function contextWarningIcon() {
    const node = el('span', undefined, 'watch-warning-icon');
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24'); svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    const outline = document.createElementNS(svg.namespaceURI, 'polygon');
    const mark = document.createElementNS(svg.namespaceURI, 'path');
    mark.setAttribute('d', 'M12 8v6 M12 17v.1');
    svg.append(outline, mark); node.append(svg);
    node.setAttribute('role', 'img');
    return {node, outline};
  }
  class Card {
    constructor(historical) {
      this.root = el('article', undefined, 'watch-card');
      this.title = el('a'); const heading = el('h3'); heading.append(this.title);
      this.message = el('p', undefined, 'detail'); this.message.setAttribute('role', 'status');
      const scroll = el('div', undefined, 'watch-table-scroll');
      scroll.tabIndex = 0; scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', 'Session prompts');
      const table = el('table', undefined, 'watch-prompt-table');
      const head = el('thead'), header = el('tr');
      for (const [index, [name, explanation]] of columns.entries()) header.append(columnHeader(
        historical && index === 0 ? 'Finished' : name,
        historical && index === 0 ? 'When this prompt ended, including stopped or failed work.\nHover or focus the clock for the full local date and UTC offset.\n— means the finish time is unknown.' : explanation));
      head.append(header); this.body = el('tbody'); table.append(head, this.body); scroll.append(table);
      this.activity = el('div', undefined, 'watch-activity');
      this.tools = disclosure(); this.skills = disclosure(); this.running = el('p', undefined, 'watch-running-tool'); this.background = el('p');
      ContextHelp.attach(this.tools.summary, '• Counts include failures and cancellations; red outcomes are a subset, not extra calls.\n• Only recorded errors or cancellations count; missing evidence is not success.');
      ContextHelp.attach(this.skills.summary, 'Confirmed custom skill loads only.\nFailure counts require direct skill attribution.');
      this.activity.append(this.tools.node, this.skills.node, this.running, this.background);
      this.summary = el('div', undefined, 'watch-session-summary');
      const icon = contextWarningIcon(); this.warningIcon = icon.node; this.warningOutline = icon.outline;
      this.contextLabel = el('span', 'Context: ');
      this.contextValue = el('span', undefined, 'watch-session-context');
      const contextLine = el('div'), contextTarget = ContextHelp.value(el('span'), 'Estimated context for the next request in this session.\nPrice warnings concern its price tier, not a session spending limit.');
      contextTarget.append(this.contextLabel, this.contextValue);
      this.costLabel = el('span'); this.costStatus = el('span');
      this.costHelp = ContextHelp.value(el('span'), () => 'Reference cost of the entire session, including earlier prompts, linked subagents and provisional work.' +
        (this.summaryValue?.cost && !this.summaryValue.cost.complete ? '\n? — Partial pricing or source data.' : ''));
      this.costHelp.append(el('span', 'Total CCost: '), this.costLabel);
      const costLine = el('div'); costLine.append(this.costHelp, this.costStatus);
      this.warningText = el('span'); this.warningLead = el('span');
      this.warningImpact = el('span'); this.warningEnd = el('span');
      this.warningText.append(this.warningLead, this.warningImpact, this.warningEnd);
      contextLine.append(this.warningIcon, contextTarget, this.warningText);
      this.summary.append(contextLine, costLine);
      this.root.append(heading, this.message, scroll, this.summary, this.activity);
    }
    update(value, historical) {
      this.value = value;
      this.root.dataset.session = value.session_id;
      text(this.title, value.title || value.session_id);
      if (/^[A-Za-z0-9_-]{1,200}$/.test(value.session_id)) this.title.href = '#/sessions/' + value.session_id;
      const focalRole = historical ? '' : promptRole(value.rows.find(item => item.prompt.event_id === value.focal_id)?.prompt);
      this.title.className = ['running', 'success'].includes(focalRole) ? `watch-${focalRole}-title` : '';
      const retryDelayed = delayed(this, 'retrySince', value.state === 'retrying' || value.state === 'loading' || !value.rows.length);
      text(this.message, value.state === 'unavailable' ? 'Source unavailable; retained contents are not current.' : value.state === 'partial' ? 'Partial / retained evidence' : retryDelayed ? 'Prompt updates delayed; check source availability. Retained contents are not current.' : '');
      this.message.hidden = !this.message.textContent;
      if (!protectedNode(this.body)) {
        const old = new Map([...this.body.children].map(node => [node.dataset.id, node]));
        reconcile(this.body, value.rows.map(item => {
          const prompt = item.prompt, row = old.get(prompt.event_id) || el('tr');
          row.dataset.id = prompt.event_id;
          const signature = JSON.stringify([item, historical]);
          if (row.signature !== signature) {
            const focal = !historical && prompt.event_id === value.focal_id;
            const role = focal ? promptRole(prompt) : '';
            row.className = role ? `watch-${role}` : '';
            const outcome = prompt.in_progress ? 'Running' : prompt.aborted ? 'Aborted' : prompt.has_error ? 'Error' : prompt.completed_successfully ? 'Completed' : 'Ended';
            const reason = !prompt.in_progress && {quota_limit: 'quota limit', rate_limit: 'rate limit',
              tool_call_limit: 'tool-call limit', step_limit: 'step limit', user: 'by user'}[prompt.abort_reason];
            row.setAttribute('aria-label', `Prompt ${prompt.prompt_number} · ${outcome}${reason ? ' · ' + reason : ''}`);
            const label = el('span', undefined, 'watch-prompt-label');
            const preview = el('span', prompt.preview || '', 'watch-prompt-preview');
            label.append(el('span', '#' + prompt.prompt_number, 'watch-prompt-number'), preview);
            const started = el('span', display(prompt, historical ? 'finished_clock' : 'clock'));
            if (!historical || prompt.completed_at_ms != null) ContextHelp.value(started, display(prompt, historical ? 'finished_date_time' : 'date_time'));
            const model = el('span', item.model + (prompt.linked_agent_count ? '*' : ''));
            const modelHelp = display(prompt, 'model_detail_help');
            if (modelHelp && modelHelp !== 'N/A') ContextHelp.value(model, modelHelp);
            const cost = el('span', () => promptCost(prompt)), costHelp = () => display(prompt, 'cost_detail_help');
            if (costHelp() && costHelp() !== 'N/A') ContextHelp.value(cost, costHelp);
            const calls = el('span', String(prompt.calls)), callsHelp = display(prompt, 'calls_help');
            if (callsHelp && callsHelp !== 'N/A') ContextHelp.value(calls, callsHelp);
            const cells = [started, display(item, 'watch_duration_ms'), label, model, item.effort,
              cost, calls, display(prompt, 'token_mix_percent'),
              display(prompt, 'incoming_context_tokens'), display(item.live_context, 'watch_delta_context_tokens')];
            row.replaceChildren(...cells.map(value => { const cell = el('td'); cell.append(typeof value === 'object' ? value : el('span', value)); return cell; }));
            row.signature = signature;
          }
          return row;
        }));
      }
      this.activity.hidden = historical || !value.focal_id;
      if (!historical) this.drawActivity(value.rows.find(row => row.prompt.event_id === value.focal_id)?.tool);
      this.drawSummary(value.session_summary);
    }
    drawSummary(value) {
      const pending = !value || ['loading', 'refreshing', 'retrying'].includes(value.state);
      const summaryDelayed = delayed(this, 'summarySince', pending);
      // Keep the last coherent footer through ordinary reacquisition, not through
      // an observed correction or a confirmed unavailable/partial result.
      if (pending) value = {...value, cost: value?.cost ?? this.summaryValue?.cost};
      this.summaryValue = value;
      const context = value?.context, warning = context?.warning;
      const visible = context?.watch_next_context_tokens != null && ['approaching', 'exceeded'].includes(warning?.severity);
      this.summary.dataset.severity = visible ? warning.severity : 'none';
      text(this.contextValue, context ? display(context, 'watch_next_context_tokens') : 'N/A');
      this.warningIcon.hidden = !visible;
      this.warningOutline.setAttribute('points', warning?.severity === 'exceeded' ?
        '7,2 17,2 22,7 22,17 17,22 7,22 2,17 2,7' : '12,2 23,22 1,22');
      this.warningIcon.setAttribute('aria-label', visible ? warning.severity === 'exceeded' ?
        'Stop: higher context pricing' : 'Caution: nearing higher context pricing' : '');
      this.warningIcon.tabIndex = visible ? 0 : -1;
      // Canonical wording already includes severity and the boundary. Remove only
      // its display delimiters; never derive severity or prices from formatted text.
      const wording = visible ? warning.text.replace(/^\[|\]$/g, '').trim() : '';
      const impact = () => visible ? display(warning, 'warning_cost').replace(/^\(|\)$/g, '').trim() : '';
      text(this.warningLead, () => visible ? ` (${wording}${impact() ? '; ' : ''}` : '');
      text(this.warningImpact, impact);
      this.warningImpact.className = warning?.multiplier != null ? 'watch-price-multiplier' : '';
      text(this.warningEnd, visible ? ')' : '');
      text(this.costLabel, () => value?.cost ?
        value.cost.observed_requests && !value.cost.priced_requests ? 'N/A' : display(value.cost, 'known_ccost') :
        value?.state === 'unavailable' ? 'N/A' : '—');
      text(this.costStatus, summaryDelayed ? ' (session total updates delayed; retained observation, not current)' :
        value?.state === 'unavailable' ? ' (unavailable; retained observation, not current)' :
        value?.state === 'partial' ? ' (partial source evidence)' : '');
      ContextHelp.refresh(this.costHelp);
    }
    drawActivity(tool) {
      const groups = [...(tool?.counts || [])].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
      const total = groups.reduce((sum, pair) => sum + pair[1], 0);
      const omitted = groups.slice(5).reduce((sum, pair) => sum + pair[1], 0);
      const toolParts = [[`${total} tool calls`, ''], ...groups.slice(0, 5).map(([name, count]) => [` · ${count} × ${name}`, ''])];
      if (omitted) toolParts.push([` · ${omitted} × other`, '']);
      const outcomeTotal = tool?.failed_or_cancelled_count ?? tool?.failed_count ?? 0;
      if (outcomeTotal) toolParts.push([` · ${outcomeTotal} failed / cancelled`, 'watch-activity-error']);
      const skills = tool?.skills || [];
      const skillParts = skill => [[skill.skill_id, ''], ...(skill.failed_count ? [[` (${skill.failed_count} failed)`, 'watch-activity-error']] : [])];
      const summary = [[`${skills.length} skills`, '']];
      for (const skill of skills.slice(0, 5)) summary.push([' · ', ''], ...skillParts(skill));
      if (skills.length > 5) summary.push([` · ${skills.length - 5} other`, '']);
      const toolLines = groups.map(([name, count]) => [[`${count} × ${name}`, '']]);
      const outcomes = tool?.outcomes || [];
      for (const item of outcomes) toolLines.push([[`${item.count} × ${item.tool_name} ${item.outcome}`, 'watch-activity-error']]);
      const unidentified = outcomeTotal - outcomes.reduce((sum, item) => sum + item.count, 0);
      if (unidentified > 0) toolLines.push([[`${unidentified} × unidentified tool/outcome`, 'watch-activity-error']]);
      drawDisclosure(this.tools, toolParts, toolLines, 'No tool calls');
      drawDisclosure(this.skills, summary, skills.map(skillParts), 'No confirmed custom skills');
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
      // DPR already includes desktop page zoom. Only pinch zoom adds a separate
      // visual-viewport factor. Keep text unscaled and reserve two raster pixels
      // for fractional border/layout rounding beneath the 450-pixel ceiling.
      let resolution;
      const updateWidth = () => {
        const ratio = window.devicePixelRatio || 1;
        const scale = ratio * (window.visualViewport?.scale || 1);
        this.root.style.setProperty('--watch-account-width', Math.floor(448 / scale) + 'px');
        resolution?.removeEventListener('change', updateWidth);
        resolution = window.matchMedia(`(resolution: ${ratio}dppx)`);
        resolution.addEventListener('change', updateWidth);
      };
      // One retained View per document; also works while Watch is detached.
      window.addEventListener('resize', updateWidth);
      window.visualViewport?.addEventListener('resize', updateWidth);
      updateWidth();
      this.earlier = el('details', undefined, 'watch-earlier');
      this.earlier.append(el('summary', 'Earlier Prompts'));
      this.history = el('div', undefined, 'watch-history'); this.earlier.append(this.history);
      this.active = el('div', undefined, 'watch-active');
      this.empty = el('p'); this.empty.setAttribute('role', 'status');
      this.accounts = el('div'); this.cards = new Map();
      this.daily = el('section', undefined, 'watch-daily');
      this.daily.setAttribute('aria-label', 'CCost Today');
      this.root.append(this.earlier, this.empty, this.active, this.daily, this.accounts);
    }
    attach(parent) {
      ReportView.syncUnits(this.root);
      if (this.root.parentNode !== parent) parent.replaceChildren(this.root);
    }
    update(result) {
      const view = result.view, active = view.active_cards || [], history = view.history_cards || [];
      this.earlier.dataset.hasHistory = String(history.length > 0);
      // A healthy host/stream retrying its source is not a disconnected stream.
      // Its global health warning remains visible; don't duplicate it as fleeting
      // table-level acquisition prose or falsely announce a connection loss.
      const connected = this.state.connection === 'Live connected.' || this.state.connectionKind === 'source_retrying';
      const retryDelayed = delayed(this, 'retrySince', result.state === 'retrying');
      const sourceState = result.state === 'retrying' ? retryDelayed ? 'Source updates delayed; last observation retained, not current.' : '' :
        result.state !== 'running' ? 'Source unavailable; last observation retained, not current.' : '';
      const loading = view.cards_state === 'loading' || view.cards_state == null;
      const historyLoading = view.history_state === 'loading' || view.history_state == null;
      const initialDelayed = delayed(this, 'initialSince', loading || historyLoading || !view.accounts);
      text(this.empty, sourceState || (!connected ? 'Live connection interrupted; last observation retained, not live.' : view.cards_state === 'unavailable' ? 'Some prompt sources are unavailable.' : initialDelayed ? 'Still loading Watch data; check source availability.' : !loading && !active.some(card => card.rows.some(row => row.prompt.in_progress)) ? 'No running prompts' : ''));
      this.empty.hidden = !this.empty.textContent;
      const keep = new Set();
      for (const [parent, values, historical] of [[this.active, active, false], [this.history, history, true]]) {
        const wanted = values.map(value => {
          const key = JSON.stringify([value.session_id, value.focal_id || 'history']); keep.add(key);
          if (!this.cards.has(key)) this.cards.set(key, new Card(historical));
          const card = this.cards.get(key); card.update(value, historical); return card.root;
        });
        if (historical && !wanted.length && !historyLoading) wanted.push(el('p', view.history_state === 'unavailable' ? 'Earlier prompts unavailable' : 'No earlier prompts'));
        reconcile(parent, wanted);
      }
      for (const key of this.cards.keys()) if (!keep.has(key)) this.cards.delete(key);
      const dailyPending = ['loading', 'refreshing', 'retrying'].includes(view.daily_state) || view.daily_state == null;
      const dailyDelayed = delayed(this, 'dailySince', dailyPending);
      const dailyValue = view.daily_usage ?? (dailyPending ? this.dailyValue : null);
      this.dailyValue = dailyValue;
      const dailyState = dailyValue && dailyPending && !dailyDelayed ? 'observed' : view.daily_state;
      const dailySignature = JSON.stringify([dailyValue, dailyState, dailyDelayed]);
      if (this.dailySignature !== dailySignature && !protectedNode(this.daily)) {
        daily(this.daily, dailyValue, dailyState, dailyDelayed); this.dailySignature = dailySignature;
      }
      const signature = JSON.stringify([view.accounts, view.quota_stale, view.quota_recovering_count]);
      if (view.accounts && this.accountSignature !== signature && !protectedNode(this.accounts)) {
        this.accounts.replaceChildren();
        accounts(this.accounts, view.accounts);
        this.accountSignature = signature;
      }
    }
  }
  return {View};
})();
