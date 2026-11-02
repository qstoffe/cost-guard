'use strict';
// Keyed, unframed cards over server-owned membership, totals and lifecycle.
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
  class Card {
    constructor() {
      this.root = el('article', undefined, 'watch-card');
      this.title = el('a'); const heading = el('h3'); heading.append(this.title);
      this.totals = el('p', undefined, 'watch-card-totals');
      this.message = el('p', undefined, 'detail'); this.message.setAttribute('role', 'status');
      const scroll = el('div', undefined, 'watch-table-scroll');
      scroll.tabIndex = 0; scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', 'Session prompts');
      const table = el('table', undefined, 'watch-prompt-table');
      const head = el('thead'), header = el('tr');
      for (const name of ['Date / Time', 'Prompt', 'Model', 'Effort', 'CCost', 'Model Calls', 'Duration', 'Δ Context', 'Context']) {
        const th = el('th', name); th.scope = 'col';
        if (name === 'Context') th.title = 'Estimated next incoming context (CLI Watch)';
        header.append(th);
      }
      head.append(header); this.body = el('tbody'); table.append(head, this.body); scroll.append(table);
      this.activity = el('div', undefined, 'watch-activity');
      this.tools = disclosure(); this.skills = disclosure(); this.running = el('p');
      this.activity.append(this.tools.node, this.skills.node, this.running);
      this.root.append(heading, this.totals, this.message, scroll, this.activity);
    }
    update(value, historical) {
      this.value = value;
      this.root.dataset.session = value.session_id;
      text(this.title, value.title || value.session_id);
      if (/^[A-Za-z0-9_-]{1,200}$/.test(value.session_id)) this.title.href = '#/sessions/' + value.session_id;
      text(this.totals, () => `Session Total C Cost: ${value.totals ? display(value.totals, 'total_ccost') : value.state === 'unavailable' ? 'Unavailable' : 'Loading…'} · Session Total Duration: ${value.totals ? display(value.totals, 'duration_ms') : value.state === 'unavailable' ? 'Unavailable' : 'Loading…'}${value.provisional ? ' · provisional' : ''}${value.state === 'partial' ? ' · partial / retained evidence' : ''}`);
      text(this.message, value.state === 'unavailable' ? 'Source unavailable; retained contents are not current.' : !value.rows.length ? 'Loading prompts…' : '');
      if (!protectedNode(this.body)) {
        const old = new Map([...this.body.children].map(node => [node.dataset.id, node]));
        reconcile(this.body, value.rows.map(item => {
          const prompt = item.prompt, row = old.get(prompt.event_id) || el('tr');
          row.dataset.id = prompt.event_id;
          const signature = JSON.stringify([item, historical]);
          if (row.signature !== signature) {
            const focal = !historical && prompt.event_id === value.focal_id;
            row.className = focal ? prompt.in_progress ? 'watch-running' : prompt.aborted || prompt.has_error ? 'watch-error' : 'watch-success' : '';
            const outcome = prompt.in_progress ? 'Running · provisional' : prompt.aborted ? 'Aborted' : prompt.has_error ? 'Error' : prompt.completed_successfully ? 'Completed' : 'Ended';
            const label = el('span', `${item.marker || ''} #${prompt.prompt_number} ${prompt.preview || prompt.label || 'Prompt'}`.trim());
            label.append(el('span', ' · ' + outcome, 'watch-outcome'));
            if (prompt.has_additional_model) label.append(el('span', ' · Additional model contribution', 'detail'));
            if (item.context_warning) label.append(el('span', item.context_warning, 'detail threshold'));
            const context = display(item.live_context, 'watch_next_context_tokens');
            const cells = [display(prompt, 'date_time'), label, item.model, item.effort,
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
    }
    drawActivity(tool) {
      const groups = [...(tool?.counts || [])].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
      const total = groups.reduce((sum, pair) => sum + pair[1], 0);
      const omitted = groups.slice(5).reduce((sum, pair) => sum + pair[1], 0);
      text(this.tools.summary, [`${total} tool calls`, ...groups.slice(0, 5).map(([name, count]) => `${count} × ${name}`), omitted && `${omitted} × other`, tool?.failed_count && `${tool.failed_count} failed / cancelled`].filter(Boolean).join(' · '));
      const skills = tool?.skills || [];
      const skillText = skill => skill.skill_id + (skill.failed_count ? ` (${skill.failed_count} failed)` : '');
      text(this.skills.summary, [`${skills.length} skills`, ...skills.slice(0, 5).map(skillText), skills.length > 5 && `${skills.length - 5} other`].filter(Boolean).join(' · '));
      for (const [target, lines, empty] of [[this.tools.list, groups.map(([name, count]) => `${count} × ${name}`), 'No tool calls'], [this.skills.list, skills.map(skillText), 'No confirmed custom skills']]) {
        const signature = JSON.stringify(lines);
        if (target.signature !== signature && !protectedNode(target)) {
          target.replaceChildren(...(lines.length ? lines : [empty]).map(line => el('div', line)));
          target.signature = signature;
        }
      }
      text(this.running, tool?.running_tool ? `${tool.running_tool} · ${display(tool, 'running_ms')}` : '');
      this.running.hidden = !tool?.running_tool;
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
      this.root.append(this.earlier, this.empty, this.active, this.accounts);
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
        const scroll = parent.scrollTop;
        const wanted = values.map(value => {
          const key = JSON.stringify([value.session_id, value.focal_id || 'history']); keep.add(key);
          if (!this.cards.has(key)) this.cards.set(key, new Card());
          const card = this.cards.get(key); card.update(value, historical); return card.root;
        });
        if (historical && !wanted.length) wanted.push(el('p', view.history_state === 'loading' ? 'Loading earlier prompts…' : view.history_state === 'unavailable' ? 'Earlier prompts unavailable' : 'No earlier prompts'));
        reconcile(parent, wanted);
        if (historical) parent.scrollTop = scroll;
      }
      for (const key of this.cards.keys()) if (!keep.has(key)) this.cards.delete(key);
      const signature = JSON.stringify([view.accounts, view.quota_stale, view.quota_recovering_count]);
      if (this.accountSignature !== signature && !protectedNode(this.accounts)) {
        this.accounts.replaceChildren();
        ReportView.overviewAccounts(this.accounts, view.accounts, '', true, false, true);
        this.accountSignature = signature;
      }
    }
  }
  return {View};
})();
