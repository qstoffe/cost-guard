'use strict';
// Keyed prompt cards over server-owned membership, metrics and lifecycle.
const WatchView = (() => {
  const el = (...args) => ReportView.element(...args);
  const display = (row, key) => ReportView.display(row, key);
  const text = (node, value) => ReportView.text(node, value);
  function historyNotice(view, retained) {
    if (retained) return '';
    if (view?.history_state === 'observed' || view?.history_epoch > 0) return 'No earlier sessions';
    if (view?.history_state === 'unavailable') return 'Unable to load earlier sessions';
    return 'Loading earlier sessions…';
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
  function invocationDisclosure() {
    const target = disclosure(); target.node.className = 'watch-running-tool';
    target.note = el('p', undefined, 'detail'); target.input = el('pre', undefined, 'watch-invocation');
    target.list.append(target.note, target.input);
    return target;
  }
  function drawInvocation(target, label, detail) {
    const identity = label ? JSON.stringify([detail?.identity, detail?.revision]) : '';
    const changed = identity !== target.identity;
    // A changed/ended call invalidates old content even while it has focus.
    if (changed) {
      target.node.open = false; target.identity = identity;
      text(target.input, detail?.text || '');
      text(target.note, label ? detail?.qualification || 'Invocation details unavailable from the current source.' : '');
    }
    if (changed || !protectedNode(target.summary) || !label) text(target.summary, label);
    target.node.hidden = !label;
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
  function daily(parent, value, state) {
    if (!parent.children.length) parent.append(el('strong', 'CCost Today'), el('span', '', 'metric-value'), el('span'));
    text(parent.children[1], value ? () => display(value, 'daily_ccost') : state === 'unavailable' ? 'Unavailable' : '—');
    text(parent.children[2], value ? `${value.prompt_count} prompts` : '');
  }
  function promptCostHelp(prompt) {
    if (!display(prompt, 'ccost')) return '';
    const split = `Incoming Context CCost (I): ${display(prompt, 'incoming_context_ccost')}\n` +
      `Extra CCost (E): ${display(prompt, 'extra_ccost')}\n\n` +
      'I — Incoming context on the first attributed request.\nE — Output, later requests and linked subagents.\n' +
      'N/A means unavailable, not zero. ? marks partial pricing or source data.';
    return [split, ReportView.costHelp(prompt), display(prompt, 'cost_detail_help')]
      .filter(value => value && value !== 'N/A').join('\n\n');
  }
  function promptRole(prompt) {
    return !prompt ? '' : prompt.in_progress ? 'running' : prompt.aborted || prompt.has_error ? 'error' :
      prompt.completed_successfully ? 'success' : '';
  }
  const columns = [
    ['Started', 'When this prompt started, in local time. Hover or focus the clock for the full date.'],
    ['Duration', 'Time spent on this prompt.\nStops advancing when work ends or updates are unavailable.'],
    ['Prompt', 'The prompt’s number within its session and a short preview of your message.'],
    ['Model', '• Main prompt — The model shown in this column.\n• Linked subagents — If marked *, hover, focus or tap the Model value to see their recorded models and effort.'],
    ['Effort', 'How much reasoning the model was asked to do.'],
    ['CCost', 'Estimated reference cost of this prompt, not your bill.\nHover, focus or tap the value for Incoming/Extra CCost and model/subagent details.'],
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
  function metricValue(row, column, value, help) {
    const content = typeof help === 'function' ? help() : help;
    const enabled = Boolean(content && content !== 'N/A');
    const old = row.children[column]?.children[0];
    const reusable = old && Boolean(old.className?.includes('help-value')) === enabled;
    const node = reusable ? old : el('span');
    text(node, value);
    if (enabled) {
      if (reusable) ContextHelp.attach(node, help, true);
      else ContextHelp.value(node, help);
    }
    return node;
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
  function contextParts(target) {
    const icon = contextWarningIcon(); target.warningIcon = icon.node; target.warningOutline = icon.outline;
    target.contextValue = el('span', undefined, 'watch-session-context');
    target.contextLabel = el('span', 'Context: ');
    const line = el('div'), help = ContextHelp.value(el('span'), 'Estimated context for the next request in this session.\nPrice warnings concern its price tier, not a session spending limit.');
    help.append(target.contextLabel, target.contextValue);
    target.warningText = el('span'); target.warningLead = el('span');
    target.warningImpact = el('span'); target.warningEnd = el('span');
    target.warningText.append(target.warningLead, target.warningImpact, target.warningEnd);
    line.append(target.warningIcon, help, target.warningText);
    return line;
  }
  function drawContext(target, context) {
    const warning = context?.warning;
    target.summary.dataset.guidance = warning?.guidance_state || 'ready';
    const visible = context?.watch_next_context_tokens != null && ['approaching', 'exceeded'].includes(warning?.severity);
    target.summary.dataset.severity = visible ? warning.severity : 'none';
    text(target.contextValue, context ? display(context, 'watch_next_context_tokens') : 'N/A');
    target.warningIcon.hidden = !visible;
    target.warningOutline.setAttribute('points', warning?.severity === 'exceeded' ?
      '7,2 17,2 22,7 22,17 17,22 7,22 2,17 2,7' : '12,2 23,22 1,22');
    target.warningIcon.setAttribute('aria-label', visible ? warning.severity === 'exceeded' ?
      'Stop: higher context pricing' : 'Caution: nearing higher context pricing' : '');
    target.warningIcon.tabIndex = visible ? 0 : -1;
    const wording = visible ? warning.text.replace(/^\[|\]$/g, '').trim() : '';
    const impact = () => visible ? display(warning, 'warning_cost').replace(/^\(|\)$/g, '').trim() : '';
    text(target.warningLead, () => visible ? ` (${wording}${impact() ? '; ' : ''}` : '');
    text(target.warningImpact, impact);
    target.warningImpact.className = warning?.multiplier != null ? 'watch-price-multiplier' : '';
    text(target.warningEnd, visible ? ')' : '');
  }
  class ContextLine {
    constructor() {
      this.root = this.summary = el('div', undefined, 'watch-session-summary');
      this.root.append(contextParts(this));
    }
    update(value) { drawContext(this, value); }
  }
  class Card {
    constructor(historical) {
      this.root = el('article', undefined, 'watch-card');
      this.title = el('a'); const heading = el('h3'); heading.append(this.title);
      this.message = el('p', undefined, 'detail'); this.message.setAttribute('role', 'status');
      this.sourceStatus = new ReportView.LiveStatus();
      const scroll = el('div', undefined, 'watch-table-scroll');
      scroll.tabIndex = 0; scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', 'Session prompts');
      const table = el('table', undefined, 'watch-prompt-table');
      const head = el('thead'), header = el('tr');
      for (const [index, [name, explanation]] of columns.entries()) header.append(columnHeader(
        historical && index === 0 ? 'Finished' : name,
        historical && index === 0 ? 'When this prompt ended, including stopped or failed work.\nHover or focus the clock for the full local date and UTC offset.\n— means the finish time is unknown.' : explanation));
      head.append(header); this.body = el('tbody'); table.append(head, this.body); scroll.append(table);
      this.activity = el('div', undefined, 'watch-activity');
      this.tools = disclosure(); this.skills = disclosure();
      this.runningDetail = invocationDisclosure(); this.backgroundDetail = invocationDisclosure();
      this.running = this.runningDetail.node; this.background = this.backgroundDetail.node;
      ContextHelp.attach(this.tools.summary, '• Counts include failures and cancellations; red outcomes are a subset, not extra calls.\n• Only recorded errors or cancellations count; missing evidence is not success.');
      ContextHelp.attach(this.skills.summary, 'Confirmed custom skill loads only.\nFailure counts require direct skill attribution.');
      this.activity.append(this.tools.node, this.skills.node, this.running, this.background);
      this.summary = el('div', undefined, 'watch-session-summary');
      const contextLine = contextParts(this);
      this.costLabel = el('span'); this.costStatus = el('span');
      this.costHelp = ContextHelp.value(this.costLabel, () => (ReportView.costHelp(this.summaryValue?.cost ||
        (this.summaryValue?.state === 'unavailable' ? {} : null), 'known_ccost') ||
        'Reference cost of the entire session, including earlier prompts, linked subagents and provisional work.') +
        (this.summaryValue?.cost && !this.summaryValue.cost.complete ? '\n? — Partial pricing or source data.' : ''));
      const costLine = el('div'); costLine.append(el('span', 'Total CCost: '), this.costHelp, this.costStatus);
      this.summary.append(contextLine, costLine);
      this.root.append(heading, this.message, scroll, this.summary, this.activity);
    }
    update(value, historical, sourceNotice = false) {
      this.value = value;
      this.root.dataset.session = value.session_id;
      text(this.title, value.title || value.session_id);
      if (/^[A-Za-z0-9_-]{1,200}$/.test(value.session_id)) this.title.href = '#/sessions/' + value.session_id;
      const focalRole = historical ? '' : promptRole(value.rows.find(item => item.prompt.event_id === value.focal_id)?.prompt);
      this.title.className = ['running', 'success'].includes(focalRole) ? `watch-${focalRole}-title` : '';
      const hasRows = value.rows.length > 0;
      const retryDelayed = this.sourceStatus.update(value.state === 'observed', value.observed_at_ms,
        Date.now(), hasRows ? 60000 : 30000);
      text(this.message, sourceNotice || hasRows ? '' : value.state === 'unavailable' ? 'Prompt source unavailable.' :
        retryDelayed ? 'Prompt updates delayed; check source availability.' : '');
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
            const outcome = prompt.execution_unverified ? 'Unverified' : prompt.in_progress ? 'Running' : prompt.aborted ? 'Aborted' : prompt.has_error ? 'Error' : prompt.completed_successfully ? 'Completed' : 'Ended';
            const reason = !prompt.in_progress && {quota_limit: 'quota limit', rate_limit: 'rate limit',
              tool_call_limit: 'tool-call limit', step_limit: 'step limit', user: 'by user'}[prompt.abort_reason];
            row.setAttribute('aria-label', `Prompt ${prompt.prompt_number} · ${outcome}${reason ? ' · ' + reason : ''}`);
            const label = el('span', undefined, 'watch-prompt-label');
            const preview = el('span', prompt.preview || '', 'watch-prompt-preview');
            label.append(el('span', '#' + prompt.prompt_number + (prompt.execution_unverified ? ' · Unverified' : ''), 'watch-prompt-number'), preview);
            if (prompt.execution_unverified) ContextHelp.value(label, 'Unfinished request; this OpenCode process reports no active execution. Another server may own it. End time and execution duration are unknown.');
            const started = el('span', display(prompt, historical ? 'finished_clock' : 'clock'));
            if (!historical || prompt.completed_at_ms != null) ContextHelp.value(started, display(prompt, historical ? 'finished_date_time' : 'date_time'));
             const model = metricValue(row, 3, item.model + (prompt.linked_agent_count ? '*' : ''), display(prompt, 'model_detail_help'));
             if (prompt.linked_agent_count) model.setAttribute('aria-label', `${item.model} · Linked subagents participated (${prompt.linked_agent_count})`);
             else model.removeAttribute('aria-label');
              const cost = metricValue(row, 5, () => display(prompt, 'ccost'), () => promptCostHelp(prompt));
             const calls = metricValue(row, 6, String(prompt.calls), display(prompt, 'calls_help'));
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
      if (!historical) {
        const row = value.rows.find(row => row.prompt.event_id === value.focal_id);
        this.drawActivity(row?.tool, !sourceNotice && value.state === 'observed' &&
          row?.prompt.in_progress && !row.prompt.execution_unverified);
      }
      this.drawSummary(value.session_summary);
    }
    drawSummary(value) {
      const pending = !value || ['loading', 'refreshing', 'retrying'].includes(value.state);
      // Keep the last coherent footer through ordinary reacquisition, not through
      // an observed correction or a confirmed unavailable/partial result.
      if (pending) value = {...value, cost: value?.cost ?? this.summaryValue?.cost};
      this.summaryValue = value;
      drawContext(this, value?.context);
      text(this.costLabel, () => value?.cost ?
        value.cost.observed_requests && !value.cost.priced_requests ? 'N/A' : display(value.cost, 'known_ccost') :
        value?.state === 'unavailable' ? 'N/A' : 'Loading…');
      text(this.costStatus, !value?.cost && value?.state === 'unavailable' ? ' (unavailable)' : '');
      ContextHelp.refresh(this.costHelp);
    }
    drawActivity(tool, verified) {
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
      drawInvocation(this.runningDetail, tool?.running_tool ? `Running: ${tool.running_tool} ${display(tool, 'running_ms')}` : '',
        verified ? tool?.running_invocation : null);
      const kinds = tool?.background_kinds || [];
      const background = kinds.length === 1 ? kinds[0] : new Set(kinds).size === 1 ? `${kinds.length}× ${kinds[0]}` : `${kinds.length} jobs`;
      drawInvocation(this.backgroundDetail, kinds.length ? `Running: ${background} ${display(tool, 'background_ms')}` : '',
        verified && kinds.length === 1 ? tool?.background_invocation : null);
    }
  }
  class View {
    constructor(state) {
      this.state = state;
      this.root = el('div', undefined, 'watch-view');
      this.earlier = el('details', undefined, 'watch-earlier');
      this.earlier.append(el('summary', 'Earlier Sessions'));
      this.history = el('div', undefined, 'watch-history'); this.earlier.append(this.history);
      this.active = el('div', undefined, 'watch-active');
      this.empty = el('p'); this.empty.setAttribute('role', 'status');
      this.accountCards = new AccountCards.View();
      this.accounts = this.accountCards.root; this.cards = new Map();
      this.daily = el('section', undefined, 'watch-daily');
      this.daily.setAttribute('aria-label', 'CCost Today');
      this.root.append(this.earlier, this.empty, this.active, this.daily, this.accounts);
    }
    attach(parent) {
      ReportView.syncUnits(this.root);
      if (this.root.parentNode !== parent) parent.replaceChildren(this.root);
    }
    update(result) {
      const view = result.view, active = view.active_cards || [];
      const history = view.history_state === 'observed' || view.history_epoch > 0 ? view.history_cards || [] : [];
      this.earlier.dataset.hasHistory = String(history.length > 0);
      // A healthy host/stream retrying its source is not a disconnected stream.
      // Host health owns actionable failures; never duplicate them as table prose
      // or falsely announce a connection loss during ordinary source retry.
      const connected = this.state.connection === 'Live connected.' || this.state.connectionKind === 'source_retrying';
      const hostOwnsRetry = this.state.connectionKind === 'source_retrying';
      // Only observed prompt membership establishes empty success. Independent
      // history/accounts/daily acquisition and elapsed time say nothing about it.
      const noRunning = result.state === 'running' && this.state.connection === 'Live connected.' && view.cards_state === 'observed' &&
        !active.some(card => card.rows.some(row => row.prompt.in_progress));
      const unverified = active.some(card => card.rows.some(row => row.prompt.execution_unverified));
      text(this.empty, view.cards_state === 'unavailable' && !active.length ? 'Some prompt sources are unavailable.' : unverified ? 'Some prompt execution is unverified' : noRunning ? 'No running prompts' : '');
      this.empty.hidden = !this.empty.textContent;
      const keep = new Set();
      for (const [parent, values, historical] of [[this.active, active, false], [this.history, history, true]]) {
        const wanted = values.map(value => {
          const key = JSON.stringify([value.session_id, value.focal_id || 'history']); keep.add(key);
          if (!this.cards.has(key)) this.cards.set(key, new Card(historical));
          const card = this.cards.get(key); card.update(value, historical, hostOwnsRetry || !connected); return card.root;
        });
        if (historical) {
          const notice = historyNotice(view, wanted.length > 0);
          if (notice) {
            this.historyNotice ||= el('p'); this.historyNotice.setAttribute('role', 'status');
            text(this.historyNotice, notice); wanted.push(this.historyNotice);
          }
        }
        reconcile(parent, wanted);
      }
      for (const key of this.cards.keys()) if (!keep.has(key)) this.cards.delete(key);
      const dailyValue = view.daily_usage ?? (this.dailyValue &&
        (this.dailyValue.day_end_ms == null || this.dailyValue.day_end_ms > Date.now()) ? this.dailyValue : null);
      this.dailyValue = dailyValue;
      const dailyState = view.daily_state;
      const dailySignature = JSON.stringify([dailyValue, dailyValue ? null : dailyState]);
      if (this.dailySignature !== dailySignature && !protectedNode(this.daily)) {
        daily(this.daily, dailyValue, dailyState); this.dailySignature = dailySignature;
      }
      this.accountCards.update(view);
    }
  }
  return {View, ContextLine, historyNotice};
})();
