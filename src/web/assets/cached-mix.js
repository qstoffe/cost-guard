'use strict';
// One local read for the visible scope; events are hints, never display facts.
const CachedMix = (() => {
  class Controller {
    constructor(api, changed) {
      Object.assign(this, {api, changed, period: null, hint: null, stamp: null, flight: null,
        value: null, error: null, blocked: false});
    }
    activate(period) {
      if (period === this.period) return;
      this.period = period;
      this.withdraw();
      this.read();
    }
    health(blocked) {
      if (this.blocked === blocked) return;
      this.blocked = blocked;
      if (blocked) {
        this.hint = this.stamp = null;
        this.withdraw();
      } else this.read();
    }
    withdraw() {
      this.flight?.abort();
      this.flight = null;
      this.value = this.error = null;
      this.changed();
    }
    committed(hint, resync = false) {
      if (!hint || this.blocked) return;
      const stamp = JSON.stringify([hint.binding, hint.archive_epoch, hint.usage_revision, hint.end_ms, hint.cleared]);
      if (stamp === this.stamp && (!resync || !this.error)) return;
      const bindingChanged = this.value && this.value.binding !== hint.binding ||
        this.hint && this.hint.binding !== hint.binding;
      const cleared = hint.cleared || this.hint?.archive_epoch != null &&
        hint.archive_epoch != null && hint.archive_epoch !== this.hint.archive_epoch;
      const missed = resync && JSON.stringify(hint.marks?.[this.period]) !==
        JSON.stringify(this.hint?.marks?.[this.period]);
      this.stamp = stamp;
      this.hint = hint;
      if (bindingChanged || cleared) this.withdraw();
      if (hint.binding == null) {
        if (!bindingChanged) this.withdraw();
        this.error = 'cache_source_unbound';
        this.changed();
      } else if (bindingChanged || cleared || missed || resync && this.error ||
          !hint.periods || hint.periods.includes(this.period)) {
        if (this.flight) this.refresh = true;
        else this.read();
      }
    }
    async read() {
      if (!this.period || this.blocked || this.flight) return;
      const period = this.period, flight = this.flight = new AbortController();
      this.refresh = false;
      try {
        const value = await this.api('/api/cache/token-mix', {period}, flight.signal);
        if (this.flight !== flight || this.period !== period) return;
        if (this.refresh) return; // A relevant commit arrived after this read began.
        if (!valid(value, period)) throw new Error('cache_unavailable');
        if (this.hint && value.binding !== this.hint.binding) {
          // A committed rebind can reach HTTP before its event. Never paint
          // across the known fence; the new binding's hint schedules a read.
          this.value = null;
          return;
        }
        this.value = value;
        this.error = null;
      } catch (error) {
        if (this.flight !== flight) return;
        this.error = error.message;
        if (['cache_source_unbound', 'authentication_required', 'host_identity_changed'].includes(this.error))
          this.value = null;
      } finally {
        if (this.flight === flight) {
          this.flight = null;
          if (this.refresh) this.read();
          else this.changed();
        }
      }
    }
    snapshot() { return {value: this.value, error: this.error, blocked: this.blocked}; }
    async page(kind, after, signal) {
      const {binding, scope: period, groups} = this.value || {};
      if (!groups || this.blocked || period !== this.period) return null;
      const page = await this.api('/api/cache/token-mix/groups', {period, kind, after, known: groups.run}, signal);
      return this.value?.groups?.run === groups.run && page?.run === groups.run &&
        page.binding === binding && page.scope === this.period && page.kind === kind &&
        Array.isArray(page.rows) ? page : null;
    }
  }
  function valid(value, period) {
    const time = item => item === null || Number.isSafeInteger(item);
    return value?.scope === period && /^[a-f0-9]{32}$/.test(value.binding) &&
      time(value.start_ms) && time(value.end_ms) && ['unknown', 'partial'].includes(value.coverage) &&
      (value.token_mix === null || Number.isSafeInteger(value.token_mix?.request_count) &&
        value.token_mix.request_count > 0 && typeof value.token_mix.display?.mix_total_tokens === 'string');
  }
  class GroupTable {
    constructor(kind, read) {
      const e = (...args) => ReportView.element(...args);
      Object.assign(this, {kind, read, cursors: [''], run: null, nodes: new Map()});
      this.root = e('section', undefined, 'token-mix-section');
      this.root.hidden = true;
      const title = `Cached Token Mix by ${kind}`;
      const table = e('table', undefined, 'token-mix-table');
      const pan = e('div', undefined, 'token-mix-pan');
      pan.tabIndex = 0; pan.setAttribute('role', 'region'); pan.setAttribute('aria-label', title);
      const thead = e('thead'), tr = e('tr');
      const labels = kind === 'model' ? ['Publisher', 'Model'] : ['Publisher'];
      for (const label of [...labels, 'Prompts', 'Calls', 'Tokens', 'Input %', 'Cached %', 'Write %', 'Output %', 'CCost']) {
        const th = e('th', label);
        th.scope = 'col';
        tr.append(th);
      }
      thead.append(tr);
      this.body = e('tbody');
      table.append(thead, this.body);
      pan.append(table);
      this.prev = e('button', 'Previous'); this.next = e('button', 'Next');
      for (const [button, delta] of [[this.prev, -1], [this.next, 1]]) {
        button.type = 'button';
        button.addEventListener('click', () => this.move(delta));
      }
      this.root.append(e('h3', title), pan, this.prev, this.next);
    }
    update(run, page, scope) {
      if (this.run === run) return;
      this.flight?.abort();
      this.flight = null;
      const preserve = run && this.scope === scope && this.cursors.length > 1;
      this.run = run;
      this.scope = scope;
      this.root.hidden = run == null;
      if (preserve) this.reload(page);
      else {
        this.cursors = [''];
        if (page) this.draw(page);
        else { this.body.replaceChildren(); this.nodes.clear(); this.page = null; }
      }
    }
    async reload(first) {
      const flight = this.flight = new AbortController();
      const after = this.cursors.at(-1);
      try {
        const page = await this.read(this.kind, after, flight.signal);
        if (!page || this.flight !== flight) return;
        if (page.rows.length) this.draw(page);
        else {
          // No cached successor at the retained anchor. Return to the first page.
          this.cursors = [''];
          this.draw(first);
        }
      } catch (_) { /* Preserve the visible rows through a local read failure. */ }
      finally { if (this.flight === flight) this.flight = null; }
    }
    async move(delta) {
      const after = delta === 1 ? this.page?.next : this.cursors.at(-2);
      if (after == null || this.flight) return;
      const flight = this.flight = new AbortController();
      try {
        const page = await this.read(this.kind, after, flight.signal);
        if (!page || this.flight !== flight) return;
        if (delta === 1) this.cursors.push(after);
        else this.cursors.pop();
        this.draw(page);
      } catch (_) { /* Preserve the last authorized page on a failed local read. */ }
      finally { if (this.flight === flight) this.flight = null; }
    }
    draw(page) {
      const e = (...args) => ReportView.element(...args);
      this.page = page;
      const retained = new Set();
      page.rows.forEach((row, index) => {
        const labels = [row.publisher];
        if (this.kind === 'model') labels.push(row.model);
        const keys = ['mix_total_tokens', 'mix_input_share', 'mix_cache_share', 'mix_write_share',
          'mix_output_share', 'mix_total_cost'];
        const values = [...labels, row.prompts, row.calls, ...keys.map(key => ReportView.display(row.mix, key))];
        retained.add(row.identity);
        let tr = this.nodes.get(row.identity);
        if (!tr) {
          tr = e('tr');
          tr.append(...values.map(() => e('td')));
          this.nodes.set(row.identity, tr);
        }
        values.forEach((value, col) => ReportView.text(tr.cells[col], String(value)));
        if (this.body.children[index] !== tr) {
          const anchor = this.body.children[index] || null;
          if (tr.parentNode === this.body && this.body.moveBefore) this.body.moveBefore(tr, anchor);
          else this.body.insertBefore(tr, anchor);
        }
      });
      for (const [id, row] of this.nodes) if (!retained.has(id)) { row.remove(); this.nodes.delete(id); }
      this.prev.setAttribute('aria-disabled', String(this.cursors.length < 2));
      this.next.setAttribute('aria-disabled', String(!page.next));
    }
  }
  class View {
    constructor(select, read) {
      const e = (...args) => ReportView.element(...args);
      this.root = e('section', undefined, 'token-mix-view');
      const controls = e('div', undefined, 'ai-stats-periods');
      controls.setAttribute('role', 'group');
      controls.setAttribute('aria-label', 'Token Mix period');
      this.buttons = new Map([['today', 'Today'], ['7-days', '7 days'], ['30-days', '30 days'],
        ['month', 'This month'], ['all', 'All time']].map(([period, label]) => {
        const button = e('button', label);
        button.type = 'button';
        button.addEventListener('click', () => select(period));
        controls.append(button);
        return [period, button];
      }));
      this.title = e('h2');
      const metrics = e('div', undefined, 'token-mix-summary');
      this.metrics = ['Input', 'Cached input', 'Cache write', 'Output'].map(label => {
        const cell = e('div'), text = e('strong');
        cell.append(e('span', label), text);
        metrics.append(cell);
        return text;
      });
      this.summary = e('div');
      this.summary.append(this.title, metrics);
      this.status = e('p', '', 'token-mix-status');
      this.groups = [new GroupTable('publisher', read), new GroupTable('model', read)];
      this.root.append(controls, this.summary, this.status, ...this.groups.map(table => table.root));
    }
    attach(parent, period, {value, error, blocked}) {
      for (const [key, button] of this.buttons) button.setAttribute('aria-pressed', String(key === period));
      const mix = value?.token_mix;
      const groups = value?.groups;
      for (const table of this.groups) table.update(groups?.run ?? null, groups?.[table.kind],
        value && value.binding + ':' + value.scope);
      this.summary.hidden = !mix;
      if (mix) {
        ReportView.text(this.title, `Cached Token Mix · ${ReportView.display(mix, 'mix_total_tokens')} tokens`);
        ['input', 'cache', 'write', 'output'].forEach((key, index) =>
          ReportView.text(this.metrics[index], ReportView.display(mix, 'mix_' + key + '_share')));
      }
      const message = blocked ? 'Cached usage is unavailable.' : mix ?
        groups ? 'Partial cached usage.' : 'Partial cached usage. Model and publisher breakdowns are still pending.' :
        error && error !== 'cache_source_unbound' ? 'Cached usage is unavailable.' : 'No cached usage yet.';
      ReportView.text(this.status, message);
      if (parent.firstChild !== this.root) parent.replaceChildren(this.root);
    }
  }
  return {Controller, View};
})();
