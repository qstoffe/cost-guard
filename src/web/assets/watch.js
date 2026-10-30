'use strict';
// One persistent, paged Watch table over shared server truth. No acquisition or valuation.
const WatchView = (() => {
  const el = (...args) => ReportView.element(...args);
  const display = (row, key) => ReportView.display(row, key);
  const text = (node, value) => ReportView.text(node, value);
  class View {
    constructor(state) {
      this.state = state;
      this.page = 0;
      this.root = el('div', undefined, 'watch-view');
      this.status = el('p', undefined, 'snapshot'); this.status.setAttribute('role', 'status');
      this.totals = el('p', undefined, 'metric-value');
      this.legend = el('p', undefined, 'detail');
      this.origin = el('details'); this.origin.append(el('summary', 'Run scope / valuation'), el('p', 'Watch shares one host-owned engine across tabs; its run begins at engine start. Closing this tab does not stop Cost Guard. Search/sort/page controls never change report scope or totals. CLI remains independent.'));
      this.scope = el('p'); this.origin.append(this.scope);
      this.notices = el('p', undefined, 'warning');
      const section = el('section');
      const label = el('label', 'Filter Watch prompts '); this.filter = el('input');
      this.filter.type = 'search'; label.append(this.filter);
      this.scroll = el('div', undefined, 'table-scroll'); this.scroll.tabIndex = 0;
      this.scroll.setAttribute('role', 'region'); this.scroll.setAttribute('aria-label', 'Watch prompts');
      const table = el('table'); table.append(el('caption', 'Watch prompts · canonical CLI order'));
      const head = el('thead'), header = el('tr');
      for (const name of ['Session / prompt', 'Model / effort', 'CCost', 'Calls', 'Duration', 'Δctx → Next Ictx', 'Activity / context details']) {
        const th = el('th', name); th.scope = 'col'; header.append(th);
      }
      head.append(header); this.body = el('tbody'); table.append(head, this.body); this.scroll.append(table);
      this.previous = el('button', 'Previous'); this.next = el('button', 'Next');
      this.previous.setAttribute('aria-label', 'Previous Watch page'); this.next.setAttribute('aria-label', 'Next Watch page');
      this.pageLabel = el('span'); const pager = el('div', undefined, 'pager');
      pager.append(this.previous, this.pageLabel, this.next);
      section.append(label, this.scroll, pager);
      this.accounts = el('div');
      this.root.append(this.status, this.totals, this.legend, this.origin, this.notices, section, this.accounts);
      this.filter.addEventListener('input', () => { this.page = 0; this.draw(); });
      this.previous.addEventListener('click', () => { this.page--; this.draw(); });
      this.next.addEventListener('click', () => { this.page++; this.draw(); });
    }
    attach(parent) {
      ReportView.syncUnits(this.root);
      if (this.root.parentNode !== parent) parent.replaceChildren(this.root);
    }
    protected(node) {
      const selection = window.getSelection?.();
      return node.contains(document.activeElement) || Boolean(selection && !selection.isCollapsed &&
        (node.contains(selection.anchorNode) || node.contains(selection.focusNode)));
    }
    update(result) {
      this.result = result;
      const view = result.view;
      const fresh = result.state === 'running' && this.state.connection === 'Live connected.';
      const lifecycle = fresh ? view.active_count ? 'Updating · active prompts' : 'Idle · no active prompts' : 'Stale / retained activity; not current lifecycle proof';
      const observed = result.source_observed_at_ms == null ? 'not yet observed' : new Date(result.source_observed_at_ms).toLocaleString();
      text(this.status, `${this.state.connection || 'Connecting'} · ${result.state}${result.error_code ? ' · ' + result.error_code : ''} · ${lifecycle} · ${view.source_label} · ${view.status} · Source observation ${observed} · Published ${new Date(view.now_ms).toLocaleString()}${view.source_warning_count ? ' · Source warnings ' + view.source_warning_count : ''}`);
      text(this.totals, () => `Run CCost ${display(view, 'run_ccost')} · Requests ${view.run_total.request_count} · ${view.today_label} CCost ${display(view.today_total, 'known_ccost')}${view.today_pending ? ' · History pending' : ''}`);
      text(this.legend, 'Token Mix % order: ' + ReportView.mixLegend(view));
      text(this.scope, () => `Run origin: ${view.run_origin}, ${new Date(view.started_at_ms).toLocaleString()}. CCost is reference valuation, not billing. Run I/C/W/O tokens ${display(view.run_total, 'totals')} · CCost ${display(view.run_total, 'costs')} · Token Mix % ${display(view.token_mix, 'percentages')}. Session subtotals cover all retained rows, independent of filters/pages, not full historical sessions.`);
      text(this.notices, [view.recent_model_notice, ...view.recent_promotion_notices].filter(Boolean).join(' · '));
      if (!this.protected(this.body)) this.draw();
      if (!this.protected(this.accounts)) this.drawAccounts(view);
    }
    draw() {
      if (!this.result) return;
      const view = this.result.view;
      const queries = [this.state.search, this.filter.value].filter(Boolean).map(q => q.toLocaleLowerCase());
      const shown = view.rows.filter(row => queries.every(q => this.cells(row).map(c => c.textContent ?? c).join(' ').toLocaleLowerCase().includes(q) || row.session_title.toLocaleLowerCase().includes(q) || row.session_id.toLocaleLowerCase().includes(q)));
      this.page = Math.max(0, Math.min(this.page, Math.ceil(shown.length / 50) - 1));
      const edge = this.scroll.getBoundingClientRect().top;
      const first = [...this.body.children].find(row => row.getBoundingClientRect().bottom > edge) || this.body.firstElementChild;
      const top = first?.getBoundingClientRect().top;
      const old = new Map([...this.body.children].map(row => [row.dataset.id, row]));
      const wanted = [];
      let session = null;
      for (const item of shown.slice(this.page * 50, (this.page + 1) * 50)) {
        if (session !== item.session_id) {
          session = item.session_id;
          const subtotal = view.session_subtotals.find(s => s.session_id === session);
          const title = `${item.session_title} · ${item.session_active ? 'Active / recent' : item.earlier ? 'Earlier' : 'Retained'} · Displayed rows CCost ${display(subtotal, 'ccost')} (not full session)`;
          const group = old.get('session:' + session) || el('tr');
          group.dataset.id = 'session:' + session; group.className = 'watch-session';
          if (group.signature !== title) {
            const th = el('th'); th.colSpan = 7; th.scope = 'rowgroup';
             const link = el('a', () => `${item.session_title} · ${item.session_active ? 'Active / recent' : item.earlier ? 'Earlier' : 'Retained'} · Displayed rows CCost ${display(subtotal, 'ccost')} (not full session)`);
            if (/^[A-Za-z0-9_-]{1,200}$/.test(session)) link.href = '#/sessions/' + session;
            th.append(link); group.replaceChildren(th); group.signature = title;
          }
          wanted.push(group);
        }
        const key = JSON.stringify([item.session_id, item.prompt.event_id]);
        const row = old.get(key) || el('tr'); row.dataset.id = key;
        const signature = JSON.stringify(item);
        if (row.signature !== signature) {
          const open = [...row.querySelectorAll('details')].map(node => node.open);
          row.className = [...(item.prompt.display_roles || []), ...(item.display_roles || []),
            ...(item.prompt.is_compaction ? ['compaction'] : [])].join(' ');
          row.replaceChildren(...this.cells(item).map((value, index) => {
            const cell = el('td'); cell.append(typeof value === 'object' ? value : el('span', () => this.cells(item)[index])); return cell;
          }));
          [...row.querySelectorAll('details')].forEach((node, index) => { node.open = open[index] || false; });
          row.signature = signature;
        }
        wanted.push(row);
      }
      if (!wanted.length) {
        const row = el('tr'), cell = el('td', view.rows.length ? 'No matching rows.' : 'No retained prompt rows. Idle is not evidence of completion.');
        cell.colSpan = 7; row.append(cell); wanted.push(row);
      }
      const keep = new Set(wanted);
      for (const row of [...this.body.children]) if (!keep.has(row)) row.remove();
      wanted.forEach((row, index) => { if (this.body.children[index] !== row) this.body.insertBefore(row, this.body.children[index] || null); });
      if (first?.isConnected && top !== undefined) this.scroll.scrollTop += first.getBoundingClientRect().top - top;
      text(this.pageLabel, `${shown.length ? this.page * 50 + 1 : 0}–${Math.min((this.page + 1) * 50, shown.length)} of ${shown.length} · ${view.rows.length} retained rows; totals independent of filters/pages`);
      this.previous.disabled = this.page === 0; this.next.disabled = (this.page + 1) * 50 >= shown.length;
    }
    cells(row) {
      const cells = ReportView.detailCells({...row.prompt, model_effort: null, next_context_warning: row.next_context_warning}, true);
      cells[0].append(el('span', `${row.marker} · ${row.is_latest_session_event ? 'Newest' : row.earlier ? 'Earlier' : 'Retained'}`, 'detail'));
      const detail = el('span', row.next_context_warning || '', row.next_context_warning ? 'threshold' : '');
      const extra = el('details'); extra.append(el('summary', 'Context / token detail'), el('span', () => `Incoming context ${cells[4]} · ~Ictx CCost ${display(row.prompt, 'incoming_context_ccost')} · ~Extra CCost ${display(row.prompt, 'extra_ccost')} · Token Mix % ${cells[7]} · ${ReportView.mixLegend(row.prompt)} · Next context cached/fresh CCost ${display(row.live_context, 'watch_next_context_cached_ccost')}/${display(row.live_context, 'watch_next_context_fresh_ccost')}`, 'detail'));
      const tool = row.tool;
      if (tool) detail.append(el('span', `${tool.running_tool || ''} ${display(tool, 'running_ms')} · Calls ${tool.counts.map(pair => pair.join(': ')).join(', ')} · Failed ${tool.failed_count} · TODO ${tool.todo_completed}/${tool.todo_total} ${tool.active_todo || ''} · Background ${tool.background_kinds.join(', ')} ${display(tool, 'background_ms')} · Skills ${tool.skills.map(s => s.skill_id + (s.failed_count ? ' (failed ' + s.failed_count + ')' : '')).join(', ')}`, 'detail ' + (tool.failed_count ? 'warning' : '')));
      detail.append(extra);
      const next = display(row.live_context, 'watch_next_context_tokens');
      const context = `${display(row.live_context, 'watch_delta_context_tokens')} → ${next === 'N/A' ? next : '~' + next}`;
      const sparse = row.watch_sparse_compaction;
      return [cells[0], sparse && row.watch_model_effort === 'N/A' && !row.next_context_warning ? '' : row.watch_model_effort,
        sparse ? '' : cells[1], sparse ? '' : cells[2], sparse && !row.prompt.in_progress ? '' : display(row, 'watch_duration_ms'), context, detail];
    }
    drawAccounts(view) {
      const signature = JSON.stringify([view.accounts, view.quota_stale, view.quota_recovering_count]);
      if (this.accountSignature === signature) return;
      // Preserve open observation disclosures when independent account observations change.
      const open = [...this.accounts.querySelectorAll('details')].map(node => node.open);
      this.accounts.replaceChildren();
      ReportView.overviewAccounts(this.accounts, view.accounts,
        `Watch accounts · ${view.quota_stale ? 'stale' : 'independent observations'} · recovering ${view.quota_recovering_count}`);
      [...this.accounts.querySelectorAll('details')].forEach((node, index) => { node.open = open[index] || false; });
      this.accountSignature = signature;
    }
  }
  return {View};
})();
