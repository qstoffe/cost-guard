'use strict';
// Observed individual runs, never browser-side valuation or a model leaderboard.
const ComparisonsView = (() => {
  const columns = [
    ['Session', 'Independent root session. Each repetition remains a separate run; follow the link for its actual session detail.'],
    ['Started', 'Configured-local first-prompt start (24-hour clock), not the session’s last activity. Groups and rows instead sort by newest session-tree activity.'],
    ['Model', 'Provider-qualified main model selected for this first prompt. Mixed work is marked; help lists contributing request models.'],
    ['Effort', 'Request-bound effort for the first prompt. Unavailable evidence is not an invented default. Mixed variants/models are explicitly marked.'],
    ['CCost', 'First-prompt reference token valuation including attributable children, not full-session cost or actual billing. N/A means unavailable.'],
    ['Duration', 'First-prompt start through its supported final execution boundary, including causal tool/child/background work. Not session age or time to first token.'],
    ['Context', 'Approximate next incoming context in tokens immediately after this first prompt. Historical estimate, not remaining model capacity or current context after later prompts. N/A means unsupported.'],
    ['Token Mix', 'I/C/W/O percentages: uncached Input / Cached input / Cache write / Output (including reasoning). Usage composition, not cost distribution.'],
    ['Calls', 'Unique attributable physical model requests for this first prompt. Not the number of tool invocations.']
  ];
  const e = (...args) => ReportView.element(...args), d = (...args) => ReportView.display(...args);
  function valid(result) {
    const page = result?.view?.comparisons;
    return result?.view?.kind === 'comparisons' && Array.isArray(page?.groups) && page.groups.length <= 10 &&
      Number.isInteger(page.total) && page.groups.every(group => group.runs?.length >= 2 &&
        group.runs.every(run => /^[A-Za-z0-9_-]{1,200}$/.test(run.session_id) && run.match_run));
  }
  function provenance(run, valueCell = false) {
    return run.contributors.map(item => `${item.model_help}\n${(valueCell ? item.effort_value_help : item.effort_help) || item.effort} · ${item.calls} calls · ${d(item, 'ccost')}${item.complete ? '' : ' (partial)'}`).join('\n\n') || 'No attributable request evidence.';
  }
  function help(run, column) {
    const state = `Run status: ${run.status}.`;
    if (column === 1) return `${d(run, 'precise_start')}\nFinal execution boundary: ${d(run, 'precise_end')}\n${state}`;
    if (column === 2 || column === 3) return `${run.mixed ? 'Mixed model/effort work.\n' : ''}${provenance(run, column === 3)}`;
    if (column === 4) return `First-prompt CCost: ${d(run, 'ccost')} (${run.cost_complete ? 'fully priced' : 'partial/unavailable'}). Not billing.\nMain: ${d(run, 'main_ccost')} · Linked children: ${d(run, 'subagent_ccost')}\nIncoming: ${d(run, 'incoming_context_ccost')} + Extra: ${d(run, 'extra_ccost')}\n${provenance(run)}\n${state}`;
    if (column === 5) return `${d(run, 'duration_ms')} · ${state}\n${columns[5][1]}\nUnfinished, failed and unknown-boundary runs never set time-gap records.`;
    if (column === 6) return `${d(run, 'context')} tokens.\n${columns[6][1]}\nValid only for this prompt’s completion; no later prompt is used as a replacement anchor.`;
    if (column === 7) return `${d(run, 'token_mix_percent')}% I/C/W/O\nObserved token totals: ${d(run, 'totals')}\n${columns[7][1]}\nMissing categories or zero total make the percentages unavailable.`;
    return `${run.calls} observed physical requests; ${run.linked_agents} linked child sessions; ${run.errors} request errors.\n${state}\n${run.status === 'complete' ? 'Final attributed work.' : 'Counts may be incomplete; no success is inferred.'}`;
  }
  class Row {
    constructor(run) {
      this.root = e('tr'); this.root.dataset.session = run.session_id; this.cells = [];
      columns.forEach((_column, index) => {
        const td = e('td'), target = index ? ContextHelp.button('', () => help(this.run, index)) : e('a');
        if (!index) target.href = '#/sessions/' + run.session_id;
        td.append(target); this.root.append(td); this.cells.push(target);
        if ([4, 5, 6, 7, 8].includes(index)) td.className = 'numeric';
      });
      this.update(run);
    }
    update(run) {
      this.run = run;
      const values = [run.title || 'Untitled session', () => d(this.run, 'started'),
        `${run.provider || '?'}/${run.model_label || 'Unknown'}${run.mixed ? ' *' : ''}`,
        `${run.effort || 'N/A'}${run.mixed ? ' *' : ''}`, () => d(this.run, 'ccost'),
        () => d(this.run, 'duration_ms'), () => d(this.run, 'context'),
        () => d(this.run, 'token_mix_percent'), `${run.calls}${run.status === 'complete' ? '' : '?'}`];
      values.forEach((value, index) => ReportView.text(this.cells[index], value));
      this.root.dataset.status = run.status;
      this.root.className = ['failed', 'aborted'].includes(run.status) ? 'error' : run.status === 'running' ? 'running' : '';
      if (run.status !== 'complete') {
        let badge = this.cells[0].parentNode.querySelector('.comparison-state');
        if (!badge) { badge = e('span', '', 'comparison-state'); this.cells[0].parentNode.append(badge); }
        ReportView.text(badge, ' · ' + run.status);
      } else this.cells[0].parentNode.querySelector('.comparison-state')?.remove();
    }
  }
  class Group {
    constructor() {
      this.root = e('section', undefined, 'comparison-group'); this.title = e('h3'); this.preview = e('p', '', 'comparison-preview');
      this.scroll = e('div', undefined, 'table-scroll'); this.scroll.tabIndex = 0;
      this.scroll.setAttribute('role', 'region');
      const table = e('table', undefined, 'comparison-table'), head = e('thead'), header = e('tr');
      this.caption = e('caption', '', 'sr-only'); table.append(this.caption);
      columns.forEach(([label, content]) => { const th = e('th'); th.scope = 'col'; th.append(ContextHelp.button(label, content)); header.append(th); });
      head.append(header); this.body = e('tbody'); table.append(head, this.body); this.scroll.append(table);
      this.facts = e('div', undefined, 'comparison-facts'); this.factNodes = [];
      this.root.append(this.title, this.preview, this.scroll, this.facts); this.rows = new Map();
    }
    update(group) {
      this.ids = new Set(group.runs.map(run => run.session_id));
      ReportView.text(this.title, `${group.runs[0].title || 'Matched first input'} · ${group.runs.length} sessions`);
      ReportView.text(this.caption, this.title.textContent); this.scroll.setAttribute('aria-label', this.title.textContent);
      ReportView.text(this.preview, `Prompt 1: ${group.preview || 'Input preview unavailable'}`);
      for (const [id, row] of this.rows) if (!this.ids.has(id)) { row.root.remove(); this.rows.delete(id); }
      group.runs.forEach((run, index) => {
        let row = this.rows.get(run.session_id);
        if (!row) { row = new Row(run); this.rows.set(run.session_id, row); } else row.update(run);
        if (this.body.children[index] !== row.root) this.body.insertBefore(row.root, this.body.children[index] || null);
      });
      group.facts.forEach((fact, index) => {
        let target = this.factNodes[index];
        if (!target) { target = ContextHelp.button('', () => target.help()); this.factNodes.push(target); this.facts.append(target); }
        const label = fact.kind.startsWith('same-') ? 'Same-model variation' : fact.kind === 'time' ? 'Largest time gap' : 'Largest CCost gap';
        ReportView.text(target, () => `${label}: ${d(fact, 'difference')} · ${d(fact, 'ratio')}`);
        target.help = () => `${fact.samples} qualifying finished runs. ${fact.low_label}: ${d(fact, 'minimum')} → ${fact.high_label}: ${d(fact, 'maximum')}.\nObserved repeated input, not controlled context, answer quality or intrinsic model superiority. Zero baselines have no ratio.`;
      });
      while (this.factNodes.length > group.facts.length) this.factNodes.pop().remove();
    }
  }
  class View {
    constructor(select) {
      this.root = e('div', undefined, 'comparisons-view'); this.status = e('p'); this.status.setAttribute('role', 'status');
      const disclaimer = ContextHelp.button('About observed runs', 'Exact first user input does not establish equal repository state, files, instructions, tools, environment or model service. These are individual observed runs, not controlled scientific benchmarks or answer-quality scores. Attachment references without recorded content are excluded.');
      this.content = e('div', undefined, 'comparison-groups'); this.groups = [];
      this.feedback = e('p', '', 'comparison-feedback'); this.feedback.setAttribute('role', 'status');
      this.pager = e('div', undefined, 'pager page-navigation'); this.previous = e('button', 'Previous'); this.next = e('button', 'Next'); this.label = e('span');
      this.label.setAttribute('aria-live', 'polite');
      for (const event of ['focusin', 'pointerdown']) document.addEventListener(event, event => {
        if (this.actionFocus && event.target !== this.actionFocus) this.actionFocus = null;
      });
      for (const [button, step] of [[this.previous, -10], [this.next, 10]]) {
        button.type = 'button';
        button.addEventListener('click', () => {
          if (button.disabled || !this.page) return;
          this.actionFocus = document.activeElement === button ? button : null;
          select(this.page.offset + step, this.page.revision);
        });
      }
      this.pager.append(this.previous, this.label, this.next); this.root.append(disclaimer, this.status, this.feedback, this.content, this.pager);
    }
    update(state) {
      const page = state.result?.view.comparisons;
      const feedback = state.orderReset ? 'Comparison history changed; restarting at page 1. ' : '';
      ReportView.text(this.feedback, feedback + (state.pageNavigation ? state.loading ? state.stage : state.failed ? state.message : '' : ''));
      this.feedback.hidden = !this.feedback.textContent;
      if (!page || state.withheld) {
        this.pager.hidden = true;
        ReportView.text(this.status, state.withheld ? 'Retained report is stale and withheld.' : '');
        ReportLoading.show(this.content, state);
        return;
      }
      ReportView.text(this.status, !page.total && page.complete ? 'No exact first-input matches in available history.' : '');
      this.status.hidden = !this.status.textContent;
      if (this.last !== state.result || this.content.querySelector('.report-loading')) {
        const focused = document.activeElement;
        const old = this.groups, next = [];
        page.groups.forEach((group, index) => {
          const view = old.find(view => !next.includes(view) && group.runs.some(run => view.ids.has(run.session_id))) || new Group();
          view.update(group); next.push(view);
          if (this.content.children[index] !== view.root) this.content.insertBefore(view.root, this.content.children[index] || null);
        });
        for (const view of old) if (!next.includes(view)) view.root.remove();
        this.content.querySelector('.report-loading')?.remove();
        this.groups = next; this.last = state.result;
        if (focused?.isConnected && document.activeElement !== focused && this.root.contains(focused)) focused.focus({preventScroll: true});
      }
      this.page = page; this.pager.hidden = !page.total;
      this.previous.disabled = state.loading || page.offset === 0; this.next.disabled = state.loading || page.offset + 10 >= page.total;
      for (const button of [this.previous, this.next]) button.setAttribute('aria-disabled', String(state.loading || button.disabled));
      ReportView.text(this.label, `Showing ${page.total ? page.offset + 1 : 0}–${Math.min(page.offset + 10, page.total)} of ${page.total.toLocaleString()} groups · Page ${page.offset / 10 + 1} of ${Math.max(1, Math.ceil(page.total / 10))}`);
      if (!state.loading && this.actionFocus) {
        if (document.activeElement === document.body || document.activeElement === this.actionFocus) {
          (this.actionFocus.disabled ? this.actionFocus === this.next ? this.previous : this.next : this.actionFocus).focus({preventScroll: true});
        }
        this.actionFocus = null;
      }
      ContextHelp.refresh(this.root);
    }
    attach(parent) { if (parent.firstChild !== this.root) parent.replaceChildren(this.root); }
  }
  return {View, valid};
})();
