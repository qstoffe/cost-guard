'use strict';
// One local read for the visible scope; events are hints, never display facts.
const CachedMix = (() => {
  const defaultOrder = ['ccost', 'desc'];
  const sameOrder = (left, right) => left?.[0] === right?.[0] && left?.[1] === right?.[1];
  const revoked = ['cache_source_unbound', 'authentication_required', 'host_identity_changed'];

  class Controller {
    constructor(api, changed) {
      Object.assign(this, {api, changed, period: null, hint: null, stamp: null, flight: null,
        value: null, error: null, blocked: false, orders: {}});
    }
    activate(period) {
      if (period === this.period) return;
      this.period = period;
      if (period === null || this.value?.scope === period) {
        // Leave a compatible table's page anchor intact while hidden. The
        // binding/clear/auth fences still withdraw snapshots immediately.
        this.abortRead();
      } else this.withdraw();
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
    abortRead() {
      this.flight?.abort();
      this.flight = null;
    }
    withdraw(error = null) {
      this.abortRead();
      this.value = null;
      this.error = error;
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
      if (hint.binding == null) {
        this.withdraw('cache_source_unbound');
        return;
      }
      if (bindingChanged || cleared) this.withdraw();
      if (bindingChanged || cleared || missed || resync && this.error ||
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
        const value = await this.api('/api/cache/token-mix', {period, orders: {...this.orders}}, flight.signal);
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
        if (revoked.includes(this.error)) this.value = null;
      } finally {
        if (this.flight === flight) {
          this.flight = null;
          if (this.refresh) this.read();
          else this.changed();
        }
      }
    }
    snapshot() { return {value: this.value, error: this.error, blocked: this.blocked}; }
    async page(kind, after, order, signal) {
      const {binding, scope: period, groups} = this.value || {};
      if (!groups || this.blocked || period !== this.period) return null;
      const [sort, direction] = order || defaultOrder;
      const current = () => !signal.aborted && this.value?.binding === binding && period === this.period &&
        this.value?.groups?.revision === groups.revision;
      let page;
      try {
        page = await this.api('/api/cache/token-mix/groups',
          {period, kind, after, sort, direction, known: groups.revision}, signal);
      } catch (error) {
        if (current() && revoked.includes(error.message)) this.withdraw(error.message);
        return null;
      }
      if (!current() || page?.binding !== binding ||
          page.scope !== period || page.kind !== kind) return null;
      if (page.revision !== groups.revision) {
        this.read(); // The local commit may precede its scoped event.
        return null;
      }
      return sameOrder(page.order, order) && Array.isArray(page.rows) ? page : null;
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
    constructor(kind, read, selectOrder) {
      const e = (...args) => ReportView.element(...args);
      Object.assign(this, {kind, read, selectOrder, cursors: [''], revision: null, order: defaultOrder, nodes: new Map()});
      this.root = e('section', undefined, 'token-mix-section');
      const title = `Cached Token Mix by ${kind}`;
      const table = e('table', undefined, 'token-mix-table');
      const pan = e('div', undefined, 'token-mix-pan');
      pan.tabIndex = 0; pan.setAttribute('role', 'region'); pan.setAttribute('aria-label', title);
      const thead = e('thead'), tr = e('tr');
      const labels = [['publisher', 'Publisher']];
      if (kind === 'model') labels.push(['model', 'Model']);
      const metrics = [['prompts', 'Prompts'], ['calls', 'Calls'], ['tokens', 'Tokens'],
        ['input', 'Input %'], ['cache', 'Cached %'], ['write', 'Write %'], ['output', 'Output %'], ['ccost', 'CCost']];
      this.headers = new Map([...labels, ...metrics].map(([key, label]) => {
        const th = e('th'), button = e('button', label), arrow = e('span', '', 'sort-arrow');
        th.scope = 'col';
        button.type = 'button';
        arrow.setAttribute('aria-hidden', 'true');
        button.append(arrow);
        button.addEventListener('click', () => this.sort(key));
        th.append(button); tr.append(th);
        return [key, {th, arrow}];
      }));
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
      this.draw({rows: []}, this.order);
    }
    update(revision, first, scope) {
      if (this.revision === revision && this.scope === scope) return;
      this.flight?.abort();
      this.flight = null;
      const preserve = revision && this.scope === scope && sameOrder(this.applied, this.order);
      this.revision = revision;
      this.scope = scope;
      this.canSort = !first || !!first.order;
      if (!preserve) this.cursors = [''];
      if (!first) this.draw({rows: []}, this.order);
      else if (this.cursors.length === 1 && (!this.canSort || sameOrder(this.order, first.order))) {
        this.draw(first, first.order);
      } else {
        // Keep the compatible displayed page through refresh, but never keep
        // old source/period rows while fetching the new selection's sort.
        if (!preserve) this.draw({rows: []}, this.order);
        this.fetch(this.cursors, this.canSort ? this.order : null, true);
      }
    }
    sort(key) {
      this.order = [key, this.order[0] === key && this.order[1] === 'asc' ? 'desc' : 'asc'];
      this.selectOrder(this.kind, this.order);
      if (this.revision && this.canSort) this.fetch([''], this.order);
      else if (!this.revision) this.draw({rows: []}, this.order);
    }
    move(delta) {
      const after = delta === 1 ? this.page?.next : this.cursors.at(-2);
      if (after == null || this.flight) return;
      this.fetch(delta === 1 ? [...this.cursors, after] : this.cursors.slice(0, -1), this.applied);
    }
    async fetch(cursors, order, refresh = false) {
      this.flight?.abort();
      const flight = this.flight = new AbortController();
      this.navigation();
      try {
        const page = await this.read(this.kind, cursors.at(-1), order, flight.signal);
        if (!page || this.flight !== flight) return;
        if (refresh && !page.rows.length && cursors.length > 1) {
          // A correction may remove the last cached destination.
          this.fetch(cursors.slice(0, -1), order, true);
          return;
        }
        this.cursors = cursors;
        this.draw(page, order);
      } catch (_) { /* Preserve the last authorized page on a failed local read. */ }
      finally {
        if (this.flight === flight) {
          this.flight = null;
          this.navigation();
        }
      }
    }
    draw(page, order) {
      const e = (...args) => ReportView.element(...args);
      this.page = page;
      this.applied = order;
      for (const [key, {th, arrow}] of this.headers) {
        const selected = key === order?.[0];
        th.setAttribute('aria-sort', selected ? order[1] === 'asc' ? 'ascending' : 'descending' : 'none');
        ReportView.text(arrow, selected ? order[1] === 'asc' ? ' ↑' : ' ↓' : '');
      }
      const retained = new Set();
      page.rows.forEach((row, index) => {
        const labels = [row.publisher];
        if (this.kind === 'model') labels.push(row.model);
        const keys = ['mix_total_tokens', 'mix_input_share', 'mix_cache_share', 'mix_write_share',
          'mix_output_share', 'mix_total_cost'];
        const values = [...labels, row.prompts, row.calls, ...keys.map(key =>
          key === 'mix_total_cost' && row.mix?.total_cost == null ? 'N/A' : ReportView.display(row.mix, key))];
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
      this.navigation();
    }
    navigation() {
      this.prev.setAttribute('aria-disabled', String(!!this.flight || this.cursors.length < 2));
      this.next.setAttribute('aria-disabled', String(!!this.flight || !this.page?.next));
    }
  }
  class View {
    constructor(select, read, selectOrder) {
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
      this.groups = ['publisher', 'model'].map(kind => new GroupTable(kind, read, selectOrder));
      this.root.append(controls, this.summary, this.status, ...this.groups.map(table => table.root));
    }
    attach(parent, period, {value, error, blocked}) {
      for (const [key, button] of this.buttons) button.setAttribute('aria-pressed', String(key === period));
      const mix = value?.token_mix;
      const groups = value?.groups;
      for (const table of this.groups) table.update(groups?.revision ?? null, groups?.[table.kind],
        value && value.binding + ':' + value.scope + ':' + value.start_ms);
      this.summary.hidden = !mix;
      if (mix) {
        ReportView.text(this.title, `Cached Token Mix · ${ReportView.display(mix, 'mix_total_tokens')} tokens`);
        ['input', 'cache', 'write', 'output'].forEach((key, index) =>
          ReportView.text(this.metrics[index], ReportView.display(mix, 'mix_' + key + '_share')));
      }
      const message = blocked ? 'Cached usage is unavailable.' : mix ?
        !groups ? 'Partial cached usage. Model and publisher breakdowns are still pending.' :
          !groups.model?.order ? 'Partial cached usage. Model and publisher sort indexes are being prepared.' :
          'Partial cached usage.' :
        error && error !== 'cache_source_unbound' ? 'Cached usage is unavailable.' : 'No cached usage yet.';
      ReportView.text(this.status, message);
      if (parent.firstChild !== this.root) parent.replaceChildren(this.root);
    }
  }
  return {Controller, View};
})();
