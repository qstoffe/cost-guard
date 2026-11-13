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
    label.append(clock, el('span', `${value.execution_unverified ? '[UNVERIFIED] ' : value.in_progress ? '[RUNNING] ' : ''}#${value.prompt_number ?? '—'}`), preview);
    const cost = ContextHelp.value(el('span', () => ReportView.display(value, 'ccost')),
      () => [ReportView.costHelp(value), ReportView.display(value, 'cost_detail_help')].filter(text => text && text !== 'N/A').join('\n\n'));
    const model = ContextHelp.value(el('span', value.watch_model || value.model_effort || 'N/A'),
      () => ReportView.display(value, 'model_detail_help'));
    const calls = ContextHelp.value(el('span', value.display?.calls ?? String(value.calls ?? 'N/A')),
      () => ReportView.display(value, 'calls_help'));
    const effort = ContextHelp.value(el('span', value.watch_effort || 'N/A'),
      () => ReportView.display(value, 'effort_help'));
    return [label, model, effort, cost,
      calls, ReportView.display(value, 'duration_ms'),
      firstContext(value), ReportView.costValue(value, 'incoming_context_ccost'),
      ReportView.costValue(value, 'extra_ccost'), ReportView.display(value, 'token_mix_percent')];
  }
  class View {
    constructor(api, id) {
      Object.assign(this, {api, id, token: null, data: null, busy: false, attached: false, generation: 0});
      this.root = el('div', undefined, 'session-detail'); this.root.setAttribute('aria-label', 'Session detail');
      const back = el('a', 'Show all sessions'); back.href = '#/sessions';
      this.heading = el('h1');
      this.exporter = typeof SessionExport === 'undefined' ? null : new SessionExport.Action(api, id);
      this.status = el('p', '', 'warning'); this.status.setAttribute('role', 'status'); this.status.hidden = true;
      this.retry = el('button', 'Retry session loading'); this.retry.type = 'button'; this.retry.hidden = true;
      this.retry.addEventListener('click', () => this.retrySource());
      this.loader = new ReportLoading.View();
      this.loader.bar.setAttribute('aria-label', 'Session loading progress');
      this.loader.status.setAttribute('aria-live', 'polite');
      this.progress = {percent: 0, stage: 'Opening session…', stageLabel: 'Opening session…'};
      this.context = new WatchView.ContextLine();
      const scroll = el('div', undefined, 'sessions-table-pan');
      this.scroll = scroll;
      scroll.tabIndex = 0; scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', 'Session prompt history');
      const table = el('table', undefined, 'sessions-table session-history-table');
      const head = el('thead'), header = el('tr');
      columns.forEach(([name, help]) => { const th = el('th'); th.scope = 'col'; th.append(ContextHelp.button(name, help)); header.append(th); });
      head.append(header); this.body = el('tbody'); this.footer = el('tr');
      const foot = el('tfoot'); foot.append(this.footer); table.append(head, this.body, foot); scroll.append(table);
      this.root.append(back, this.heading, el('p', 'Session ID: ' + id), this.context.root, this.status, this.retry, this.loader.root, scroll);
      if (this.exporter) this.heading.after(this.exporter.root);
      this.loading(); this.freshness();
    }
    attach(parent) {
      this.freshness();
      if (this.root.parentNode !== parent) parent.replaceChildren(this.root);
      if (this.attached) return;
      this.attached = true; this.poll();
    }
    detach() {
      this.exporter?.close();
      this.attached = false; this.generation++; clearTimeout(this.timer);
      this.scroll.setAttribute('aria-busy', 'false'); this.loader.root.hidden = true;
      const token = this.token; this.token = null;
      if (token) this.api('/api/detail', {action: 'close', token}).catch(() => {});
    }
    async poll() {
      if (!this.attached || this.busy) return;
      clearTimeout(this.timer);
      if (document.hidden) { this.timer = setTimeout(() => this.poll(), 30000); return; }
      const generation = this.generation;
      this.pendingLoad = this.load();
      await this.pendingLoad;
      if (this.attached) this.timer = setTimeout(() => this.poll(), generation === this.generation ? (this.waiting ? 500 : 5000) : 0);
    }
    async retrySource() {
      if (this.retry.disabled || !this.token) return;
      const token = this.token;
      this.retry.disabled = true;
      try {
        // A click during a short status read must not be silently discarded.
        await this.pendingLoad;
        if (!this.attached || this.token !== token) return;
        await this.api('/api/detail', {action: 'retry', token});
        if (!this.attached || this.token !== token) return;
        if (!this.data) this.progress = {percent: 0, stage: 'Queued for session source…'};
        this.retry.hidden = true; this.waiting = true;
        await this.poll();
      } catch (error) {
        this.status.textContent = `Retry unavailable (${error.message}). Return to Sessions and reopen this session.`;
        this.status.hidden = false;
      } finally { this.retry.disabled = false; }
    }
    async load() {
      if (this.busy) return;
      this.busy = true;
      const generation = this.generation;
      try {
        if (!this.token && !this.data) this.progress = {percent: 0, stage: 'Opening session…'};
        if (!this.token) this.loading('Opening session…');
        if (!this.token) {
          const opened = (await this.api('/api/detail', {action: 'open', session_id: this.id, mode: 'live'})).token;
          if (!this.attached || generation !== this.generation) { this.api('/api/detail', {action: 'close', token: opened}).catch(() => {}); return; }
          this.token = opened;
        }
        let data = await this.api('/api/detail', {action: 'begin', token: this.token, offset: 0});
        if (!this.attached || generation !== this.generation) return;
        this.exporter?.update(this.token, data.export_available === true);
        if (!data.result) {
          this.sourceStatus(data);
          return;
        }
        this.sourceStatus(data);
        if (this.data?.revision === data.revision) { if (this.pendingRender) this.update(this.data); return; }
        const initial = data.result.view?.prompt_blocks?.[0]?.rows;
        if (!data.revision || data.offset !== 0 || !Number.isSafeInteger(data.total) || data.total < 0 ||
            !Array.isArray(initial) || initial.length > data.total) throw new Error('inconsistent_history');
        const rows = [...initial], ids = new Set();
        const validate = next => {
          for (const row of next) {
            if (!row.id || ids.has(row.id)) throw new Error('inconsistent_history');
            ids.add(row.id);
          }
        };
        validate(rows);
        this.historyProgress(rows.length, data.total);
        while (rows.length < data.total) {
          const chunk = await this.api('/api/detail', {action: 'chunk', token: this.token,
            offset: rows.length, revision: data.revision});
          if (!this.attached || generation !== this.generation) return;
          const next = chunk.result?.view?.prompt_blocks?.[0]?.rows;
          if (chunk.revision !== data.revision || chunk.total !== data.total || chunk.offset !== rows.length ||
              !Array.isArray(next) || !next.length || rows.length + next.length > data.total) throw new Error('inconsistent_history');
          validate(next);
          rows.push(...next);
          this.historyProgress(rows.length, data.total);
          // Yield between bounded chunks without discarding a retained history.
          await new Promise(resolve => setTimeout(resolve, 0));
        }
        if (!this.attached || generation !== this.generation) return;
        data.result.view.prompt_blocks[0].rows = rows;
        this.loading('Preparing session…');
        this.update(data);
        this.sourceStatus(data);
      } catch (error) {
        if (!this.attached || generation !== this.generation) return;
        this.status.textContent = this.data ? '' : `Session unavailable (${error.message}).`;
        this.status.hidden = !this.status.textContent;
        this.loader.root.hidden = true; this.scroll.setAttribute('aria-busy', 'false');
        if (error.message === 'detail_expired') this.token = null;
        if (['instance_stopping', 'authentication_required', 'host_identity_changed'].includes(error.message)) this.detach();
      } finally { this.busy = false; }
    }
    sourceStatus(data) {
      this.freshness();
      const acquisition = data.acquisition;
      this.waiting = !data.result && acquisition?.phase !== 'failed';
      this.retry.hidden = !acquisition?.retry_available;
      if (acquisition?.phase === 'failed') {
        const reasons = {
          detail_no_progress: 'No forward progress was observed during source acquisition.',
          detail_not_admitted: 'The session acquisition worker did not start. Check the source connection.',
          session_missing: 'This session is no longer present in the selected source.',
          concurrent_source_change: 'The session changed repeatedly while it was being verified.',
          source_identity_changed: 'The source changed. Return to Sessions to select it again.',
          http_auth_failure: 'The source rejected authentication. Restore source access before retrying.',
          unsupported_schema: 'This source data format is unsupported.',
          unsupported_version: 'This source version is unsupported.'
        };
        this.status.textContent = `${reasons[acquisition.reason] || 'Session acquisition failed.'} (${acquisition.reason || 'detail_unavailable'}). Retry or return to Sessions.${this.data ? ' Previously verified history is retained.' : ''}`;
        this.status.hidden = false; this.loader.root.hidden = true; this.scroll.setAttribute('aria-busy', 'false');
        return;
      }
      if (!data.result && acquisition) {
        const phase = ({queued: 'Queued for session source', selecting: 'Selecting session source', reading: 'Reading session source',
          verifying: 'Verifying session revision', analyzing: 'Analyzing session history',
          projecting: 'Building session table', publishing: 'Preparing verified session history',
          retrying: 'Waiting to retry session source'})[acquisition.phase] || 'Waiting for session source';
        const percent = Number.isFinite(acquisition.percent) && acquisition.percent >= 0 && acquisition.percent <= 70 ? acquisition.percent : this.progress.percent;
        const work = Number.isSafeInteger(acquisition.phase_total) && acquisition.phase_total > 0 &&
          Number.isSafeInteger(acquisition.phase_completed) && acquisition.phase_completed >= 0 && acquisition.phase_completed <= acquisition.phase_total ?
          `${acquisition.phase_completed} of ${acquisition.phase_total} stage units; ` : '';
        this.loading(`${phase}… ${work}${acquisition.completed || 0} completed work units; attempt ${acquisition.attempts || 0}; last progress ${acquisition.progress_age_seconds || 0}s ago${acquisition.reason ? ` (${acquisition.reason})` : ''}`, percent, phase);
        return;
      }
      if (data.state === 'loading' || data.pending && data.state === 'observed') {
        if (!this.data) this.loading('Waiting for session source…');
        else { this.status.textContent = ''; this.status.hidden = true; }
        return;
      }
      this.status.textContent = data.state === 'observed' || this.data && ['history_retained', 'source_unavailable'].includes(data.state) ? '' :
        ({history_retained: 'Session data unavailable.', source_unavailable: 'Source unavailable.',
          session_missing: 'Session unavailable; retained observations shown.', archived: 'Archived session; last observed history.'}[data.state] || 'Session data unavailable.');
      this.status.hidden = !this.status.textContent;
      if (!data.result && !this.data) { this.loader.root.hidden = true; this.scroll.setAttribute('aria-busy', 'false'); }
    }
    historyProgress(completed, total) {
      // Source-owned milestones 0–70%; pinned rows 70–95%; applied DOM 100%.
      // Scalar work/time never invent a fraction. Retries retain the proven watermark.
      this.loading(`Loading session history (${completed} of ${total})…`, total ? 70 + 25 * completed / total : 95,
        'Loading session history');
    }
    loading(stage = this.progress.stage, percent = this.progress.percent, stageLabel = stage) {
      if (this.data) return;
      Object.assign(this.progress, {stage, stageLabel, percent: Math.max(this.progress.percent, Math.min(95, Math.floor(percent)))});
      this.loader.update(this.progress);
      this.loader.root.hidden = false; this.status.hidden = true;
      // Busy history must not suppress the sibling loader's polite stage announcements.
      this.scroll.setAttribute('aria-busy', 'true');
    }
    freshness() {
      if (!this.scroll) return;
      this.scroll.hidden = !this.data;
      this.context.root.hidden = !this.data;
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
      if (!protectedNode(this.footer)) this.footer.replaceChildren(...totals().map(value => {
        const cell = el('td'); cell.append(typeof value === 'object' ? value : el('span', value)); return cell;
      }));
      else this.pendingRender = true;
      if (anchor?.isConnected && top != null) {
        const delta = anchor.getBoundingClientRect().top - top;
        if (delta) window.scrollBy(0, delta);
      }
      if (!this.data) this.loader.update({percent: 100, stage: 'Session ready', stageLabel: 'Session ready'});
      this.data = data; this.loader.root.hidden = true; this.scroll.setAttribute('aria-busy', 'false');
      this.freshness();
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
