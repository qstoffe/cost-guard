'use strict';
// Complete document-scrolling history, assembled from one pinned source revision.
const SessionDetail = (() => {
  const el = (...args) => ReportView.element(...args);
  const columns = [
    ['Prompt', 'Local start time, prompt number and preview. [RUNNING] requires observed ongoing work.'],
    ['Model', 'The canonical main prompt model. Linked subagents may use other models.'],
    ['Effort', 'Reasoning effort requested for the main prompt.'],
    ['CCost', 'Reference cost of this prompt, including linked work; not your bill. ? means partial pricing.'],
    ['Calls', 'Recorded model requests, including linked subagents. Not tool calls.'],
    ['Duration', 'Canonical execution time, excluding idle gaps. Retained observations do not advance.'],
    ['Ictx', 'Context on the first request of this prompt, not the next session context. N/A is unknown.'],
    ['Ictx CCost', 'Reference incoming-context cost component. Estimates and unavailable evidence retain their canonical meaning.'],
    ['Extra CCost', 'Other reference cost: output, later requests and linked subagents.'],
    ['Token Mix %', 'Token percentages in Input / Cached input / Cache write / Output order. Output includes reasoning. Not cost.']
  ];
  function protection() {
    const selection = window.getSelection?.();
    const targets = [document.activeElement, ...(selection && !selection.isCollapsed ? [selection.anchorNode, selection.focusNode] : [])].filter(Boolean);
    return node => targets.some(target => node.contains(target));
  }
  function cells(value) {
    const label = el('span', undefined, 'session-prompt-label');
    const clock = ContextHelp.value(el('span', value.display?.clock || '—'), value.display?.date_time || 'Start time unavailable');
    const preview = el('span', value.preview || value.label || 'Prompt', 'session-preview');
    ContextHelp.value(preview, value.preview || value.label || 'Prompt');
    label.append(clock, el('span', `${value.in_progress ? '[RUNNING] ' : ''}#${value.prompt_number ?? '—'}`), preview);
    const cost = ContextHelp.value(el('span', () => ReportView.display(value, 'ccost')),
      () => ReportView.display(value, 'cost_detail_help') + (value.retained ? '\nRetained source evidence.' : ''));
    return [label, value.watch_model || 'N/A', value.watch_effort || 'N/A', cost,
      value.display?.calls ?? String(value.calls ?? 'N/A'), ReportView.display(value, 'duration_ms'),
      firstContext(value), ReportView.display(value, 'incoming_context_ccost'),
      ReportView.display(value, 'extra_ccost'), ReportView.display(value, 'token_mix_percent')];
  }
  class View {
    constructor(api, id) {
      Object.assign(this, {api, id, token: null, data: null, busy: false, attached: false, generation: 0});
      this.root = el('div', undefined, 'session-detail'); this.root.setAttribute('aria-label', 'Session detail');
      const back = el('a', 'Show all sessions'); back.href = '#/sessions';
      this.heading = el('h1');
      this.status = el('p', 'Loading session…', 'warning'); this.status.setAttribute('role', 'status');
      this.loading();
      this.context = new WatchView.ContextLine();
      const scroll = el('div', undefined, 'sessions-table-pan');
      scroll.tabIndex = 0; scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', 'Session prompt history');
      const table = el('table', undefined, 'sessions-table session-history-table');
      const head = el('thead'), header = el('tr');
      columns.forEach(([name, help]) => { const th = el('th'); th.scope = 'col'; th.append(ContextHelp.button(name, help)); header.append(th); });
      head.append(header); this.body = el('tbody'); this.footer = el('tr');
      const foot = el('tfoot'); foot.append(this.footer); table.append(head, this.body, foot); scroll.append(table);
      this.root.append(back, this.heading, el('p', 'Session ID: ' + id), this.context.root, this.status, scroll);
    }
    attach(parent) {
      if (this.root.parentNode !== parent) parent.replaceChildren(this.root);
      if (this.attached) return;
      this.attached = true; this.poll();
    }
    detach() {
      this.attached = false; this.generation++; clearTimeout(this.timer);
      const token = this.token; this.token = null;
      if (token) this.api('/api/detail', {action: 'close', token}).catch(() => {});
    }
    async poll() {
      if (!this.attached || this.busy) return;
      clearTimeout(this.timer);
      const generation = this.generation;
      await this.load();
      if (this.attached) this.timer = setTimeout(() => this.poll(), generation === this.generation ? 5000 : 0);
    }
    async load() {
      if (this.busy) return;
      this.busy = true;
      const generation = this.generation;
      try {
        if (!this.token) {
          const opened = (await this.api('/api/detail', {action: 'open', session_id: this.id, mode: 'live'})).token;
          if (!this.attached || generation !== this.generation) { this.api('/api/detail', {action: 'close', token: opened}).catch(() => {}); return; }
          this.token = opened;
        }
        let data = await this.api('/api/detail', {action: 'begin', token: this.token, offset: 0});
        if (!this.attached || generation !== this.generation) return;
        if (!data.result) {
          this.sourceStatus(data);
          return;
        }
        this.sourceStatus(data);
        if (this.data?.revision === data.revision) { if (this.pendingRender) this.update(this.data); return; }
        const rows = [...data.result.view.prompt_blocks[0].rows];
        if (!this.data && data.state === 'observed') this.loading();
        while (rows.length < data.total) {
          const chunk = await this.api('/api/detail', {action: 'chunk', token: this.token,
            offset: rows.length, revision: data.revision});
          if (!this.attached || generation !== this.generation) return;
          const next = chunk.result?.view.prompt_blocks[0].rows;
          if (chunk.revision !== data.revision || chunk.total !== data.total || chunk.offset !== rows.length || !next?.length) throw new Error('inconsistent_history');
          rows.push(...next);
          // Yield between bounded chunks without discarding a retained history.
          await new Promise(resolve => setTimeout(resolve, 0));
        }
        data.result.view.prompt_blocks[0].rows = rows;
        this.update(data);
        this.sourceStatus(data);
      } catch (error) {
        if (!this.attached || generation !== this.generation) return;
        this.status.textContent = `Session unavailable (${error.message}); last observed rows retained.`;
        this.status.hidden = false;
        if (error.message === 'detail_expired') this.token = null;
        if (['instance_stopping', 'authentication_required', 'host_identity_changed'].includes(error.message)) this.detach();
      } finally { this.busy = false; }
    }
    sourceStatus(data) {
      if (data.state === 'loading' || data.pending && data.state === 'observed') {
        if (!this.data) this.loading();
        else { this.status.textContent = ''; this.status.hidden = true; }
        return;
      }
      this.status.textContent = data.state === 'observed' ? '' :
        ({history_retained: 'Partial history: retained observations included.', source_unavailable: 'Source unavailable; retained observations are not current.',
          session_missing: 'Session unavailable; retained observations shown.', archived: 'Archived session; last observed history.'}[data.state] || 'Session data unavailable.');
      this.status.hidden = !this.status.textContent;
    }
    loading() {
      const progress = el('progress'); progress.setAttribute('aria-label', 'Loading session');
      this.status.replaceChildren(el('span', 'Loading session… '), progress);
      this.status.hidden = false;
    }
    update(data) {
      ReportView.defaultUnit();
      const block = data.result.view.prompt_blocks[0];
      this.pendingRender = false;
      const protectedNode = protection();
      ReportView.text(this.heading, block.title || 'Untitled session'); this.context.update(block.session_context);
      const old = new Map([...this.body.children].map(row => [row.dataset.id, row]));
      const wanted = new Set(block.rows.map(row => row.id));
      const anchor = [...this.body.children].find(row => row.getBoundingClientRect().bottom > 0);
      const top = anchor?.getBoundingClientRect().top;
      let deferOrder = false;
      for (const row of [...this.body.children]) if (!wanted.has(row.dataset.id)) {
        if (protectedNode(row)) { this.pendingRender = true; deferOrder = true; }
        else row.remove();
      }
      const initialLength = this.body.children.length, append = [];
      block.rows.forEach((value, index) => {
        const row = old.get(value.id) || el('tr'); row.dataset.id = value.id;
        row.className = value.in_progress ? 'session-running' : value.has_error || value.aborted ? 'error' : '';
        const signature = JSON.stringify(value);
        if (row.signature !== signature && protectedNode(row)) this.pendingRender = true;
        if (row.signature !== signature && !protectedNode(row)) {
          const content = cells(value);
          row.replaceChildren(...content.map((item, column) => {
            const td = el('td'); td.append(typeof item === 'object' ? item : el('span', () => cellsText(value, column))); return td;
          })); row.signature = signature;
        }
        if (deferOrder) { if (!row.parentNode) append.push(row); }
        else if (index >= initialLength) append.push(row);
        else if (this.body.children[index] !== row) this.body.insertBefore(row, this.body.children[index] || null);
      });
      for (let offset = 0; offset < append.length; offset += 200) this.body.append(...append.slice(offset, offset + 200));
      const totals = () => { const values = ReportView.detailTotals(block); return [values[0], '', '', ...values.slice(1)]; };
      if (!protectedNode(this.footer)) this.footer.replaceChildren(...totals().map((_, index) => el('td', () => totals()[index])));
      else this.pendingRender = true;
      if (anchor?.isConnected && top != null) {
        const delta = anchor.getBoundingClientRect().top - top;
        if (delta) window.scrollBy(0, delta);
      }
      this.data = data;
    }
  }
  // Unit bindings must not manufacture new tooltip DOM for unchanged text cells.
  function firstContext(row) {
    return row.display?.first_incoming_context_tokens ?? ReportView.display(row, 'incoming_context_tokens');
  }
  function cellsText(row, index) {
    return [null, row.watch_model || 'N/A', row.watch_effort || 'N/A', null,
      row.display?.calls ?? String(row.calls ?? 'N/A'), ReportView.display(row, 'duration_ms'), firstContext(row),
      ...['incoming_context_ccost', 'extra_ccost', 'token_mix_percent'].map(key => ReportView.display(row, key))][index];
  }
  return {View};
})();
