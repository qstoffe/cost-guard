'use strict';
// A bounded DOM page over shared Python report truth, not a browser billing engine.
const SessionDetail = (() => {
  const el = (...args) => ReportView.element(...args);
  class View {
    constructor(api, id, mode) {
      Object.assign(this, {api, id, mode, offset: 0, revision: null, anchor: null,
        token: null, data: null, follow: mode === 'live', busy: false, attached: false});
      this.root = el('section');
      this.controls = el('div', undefined, 'pager');
      this.toggle = el('button', mode === 'live' ? 'Snapshot' : 'Live');
      this.latest = el('button', 'Jump to latest');
      this.first = el('button', 'First'); this.previous = el('button', 'Previous');
      this.next = el('button', 'Next'); this.label = el('span');
      this.label.setAttribute('aria-live', 'polite');
      this.controls.append(this.toggle, this.first, this.previous, this.next, this.latest, this.label);
      this.rowNumber = el('input'); this.rowNumber.type = 'number';
      this.rowNumber.min = '1'; this.rowNumber.value = '1';
      this.rowNumber.setAttribute('aria-label', 'Go to session history row');
      const go = el('button', 'Go to row'); this.controls.append(this.rowNumber, go);
      go.addEventListener('click', () => {
        const row = Number(this.rowNumber.value);
        if (Number.isSafeInteger(row) && row > 0) this.page(row - 1);
      });
      this.status = el('p'); this.status.setAttribute('role', 'status');
      this.summary = el('p'); this.warning = el('p', undefined, 'warning');
      const scroll = el('div', undefined, 'table-scroll'); scroll.tabIndex = 0;
      scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', 'Session prompt history');
      const table = el('table'); table.append(el('caption', 'Complete session history — 50 rows per page'));
      const head = el('thead'), header = el('tr');
      for (const name of ['Prompt', 'CCost', 'Calls', 'Duration', '~Ictx', '~Ictx CCost', '~Extra CCost', 'I/C/W/O %']) {
        const th = el('th', name); th.scope = 'col'; header.append(th);
      }
      head.append(header); this.body = el('tbody'); this.footer = el('tr');
      const foot = el('tfoot'); foot.append(this.footer); table.append(head, this.body, foot); scroll.append(table);
      this.root.append(this.controls, this.status, this.summary, this.warning, scroll,
        el('p', 'CCost is reference valuation, not billing. Unknown is not zero. Durations are report execution durations at observation. Copy and selection cover this page; use First/Next for other history.'));
      this.first.addEventListener('click', () => this.page(0));
      this.previous.addEventListener('click', () => this.page(Math.max(0, this.offset - 50)));
      this.next.addEventListener('click', () => this.page(this.offset + 50));
      this.latest.addEventListener('click', () => { this.follow = this.mode === 'live'; this.page(2 ** 52, true); });
      this.toggle.addEventListener('click', () => this.switchMode());
      this.onScroll = () => {
        if (window.innerHeight + window.scrollY < document.documentElement.scrollHeight - 24) this.follow = false;
      };
      this.root.addEventListener('focusin', () => { this.follow = false; });
    }
    attach(parent) {
      parent.replaceChildren(this.root);
      if (this.attached) return;
      this.attached = true;
      window.addEventListener('scroll', this.onScroll, {passive: true});
      if (this.mode === 'live' && this.token) {
        this.api('/api/detail', {action: 'close', token: this.token}).catch(() => {});
        this.token = null;
      }
      this.poll();
    }
    detach() {
      this.attached = false; clearTimeout(this.timer);
      window.removeEventListener('scroll', this.onScroll);
    }
    async open() {
      this.token = (await this.api('/api/detail', {action: 'open', session_id: this.id, mode: this.mode})).token;
    }
    protectedSelection() {
      const selection = window.getSelection?.();
      return Boolean(selection && !selection.isCollapsed && this.root.contains(selection.anchorNode));
    }
    async poll() {
      if (!this.attached || this.busy) return;
      await this.load();
      if (this.attached) this.timer = setTimeout(() => this.poll(), 1000);
    }
    async page(offset, latest = false) {
      this.follow = latest && this.mode === 'live';
      this.anchor = null; this.offset = offset;
      await this.load(true, latest);
    }
    async switchMode() {
      if (this.busy) return;
      try {
        if (this.mode === 'live') {
          await this.api('/api/detail', {action: 'freeze', token: this.token});
          this.mode = 'snapshot'; this.follow = false;
        } else {
          await this.api('/api/detail', {action: 'close', token: this.token});
          this.mode = 'live'; this.token = null;
        }
        this.toggle.textContent = this.mode === 'live' ? 'Snapshot' : 'Live';
        await this.load();
      } catch (_) { this.status.textContent = 'Mode switch unavailable; last known result retained.'; }
    }
    async refresh() {
      if (this.busy) return;
      if (this.token) {
        try { await this.api('/api/detail', {action: 'close', token: this.token}); }
        catch (_) { /* A lost/expired lease still permits a fresh capture. */ }
      }
      this.token = null; await this.load();
    }
    async load(navigation = false, latest = false) {
      if (this.busy) return;
      this.busy = true;
      const oldAnchor = this.body.firstElementChild;
      const top = oldAnchor?.getBoundingClientRect().top;
      try {
        if (this.protectedSelection()) this.follow = false;
        if (!this.token) await this.open();
        const data = await this.api('/api/detail', {action: 'page', token: this.token,
          offset: latest || this.follow ? 2 ** 52 : this.offset,
          revision: this.revision, anchor: this.follow ? null : this.anchor});
        if (!this.attached) return;
        this.status.textContent = `${this.mode === 'live' ? 'Live' : 'Snapshot'} — ${data.state}${data.result ?
          ' — observed ' + new Date(data.result.observed_at_ms).toLocaleString() : ' — waiting for authoritative observation'}`;
        if (!data.result) return;
        if (this.mode === 'live' && data.revision !== this.revision && !this.follow) {
          this.latest.textContent = 'New/changed activity — Jump to latest';
        }
        if (!navigation && (this.protectedSelection() || this.body.contains(document.activeElement))) return;
        if (data.revision === this.revision && data.offset === this.offset && !navigation) return;
        this.update(data);
      } catch (error) {
        this.status.textContent = `Unavailable (${error.message}). Last known result retained; Refresh to retry. Return via Sessions.`;
        if (error.message === 'detail_expired') this.token = null;
        if (['instance_stopping', 'authentication_required'].includes(error.message)) {
          this.status.textContent = 'Host stopped or authorization expired. Last known report retained; use a fresh launcher link.';
          this.detach();
        }
      } finally {
        if (!navigation && !this.follow && oldAnchor?.isConnected && top !== undefined) {
          const delta = oldAnchor.getBoundingClientRect().top - top;
          if (delta) window.scrollBy(0, delta);
        }
        this.busy = false;
      }
    }
    update(data) {
      const block = data.result.view.prompt_blocks[0];
      const existing = new Map([...this.body.children].map(row => [row.dataset.id, row]));
      const desired = new Set(block.rows.map(row => row.id));
      for (const row of [...this.body.children]) if (!desired.has(row.dataset.id)) row.remove();
      block.rows.forEach((value, index) => {
        let row = existing.get(value.id);
        if (!row) { row = el('tr'); row.dataset.id = value.id; }
        row.className = value.is_compaction ? 'compaction' : '';
        const signature = JSON.stringify(value);
        if (row.dataset.value !== signature) {
          row.replaceChildren(...ReportView.detailCells(value).map(value => {
            const cell = el('td'); cell.append(typeof value === 'object' ? value : el('span', value)); return cell;
          })); row.dataset.value = signature;
        }
        if (this.body.children[index] !== row) this.body.insertBefore(row, this.body.children[index] || null);
      });
      this.footer.replaceChildren(...ReportView.detailTotals(block).map(value => el('td', value)));
      this.summary.textContent = `Whole session: ${data.total} rows; CCost ${block.total_ccost}${!block.comparison_cost_complete ? ' (incomplete)' : ''}; billed ${block.billed_cost ?? 'Unknown'}. Totals are not page subtotals.`;
      this.warning.textContent = (data.state === 'history_retained' ?
        'Source history omitted previously observed evidence. Retained last observations are included, not newly completed. Deleted-before-observation history cannot be reconstructed. ' : '') +
        (data.state === 'session_missing' || data.state === 'archived' ? 'Session missing or archived; last known report retained. Return via Sessions. ' : '') +
        data.result.view.notes.join(' ');
      if (!this.follow && data.revision !== this.revision) this.latest.textContent = 'New/changed activity — Jump to latest';
      else this.latest.textContent = 'Jump to latest';
      Object.assign(this, {data, offset: data.offset, revision: data.revision, anchor: block.rows[0]?.id || null});
      this.label.textContent = data.total ? `${data.offset + 1}–${data.offset + block.rows.length} of ${data.total}` : 'No rows';
      this.first.disabled = this.previous.disabled = data.offset === 0;
      this.next.disabled = data.offset + block.rows.length >= data.total;
      this.rowNumber.max = String(data.total);
    }
  }
  return {View};
})();
