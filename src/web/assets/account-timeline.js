'use strict';
const AccountTimelineView = (() => {
  const periods = [['today', 'Today'], ['7-days', '7 days'], ['30-days', '30 days'],
    ['month', 'This month'], ['all', 'All time']];
  const e = (...args) => ReportView.element(...args);
  const ns = 'http://www.w3.org/2000/svg';
  const lineStyles = ['none', '8 4', '2 4', '10 3 2 3', '5 3 1 3', '12 5 4 5'];
  const label = series => `${series.account} · ${ReportView.quotaLabel({label: series.quota})}`;
  const shown = item => ReportView.display({
    display: {amount: item.display.credits},
    display_units: {usd: {amount: item.display.usd}}
  }, 'amount');
  function svg(tag, attrs = {}, text) {
    const node = document.createElementNS(ns, tag);
    for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function seriesStyle(node, id) {
    const key = parseInt(id.slice(0, 8), 16) >>> 0;
    node.setAttribute('data-ink', key % 8);
    node.setAttribute('stroke-dasharray', lineStyles[Math.floor(key / 8) % lineStyles.length]);
    return node;
  }
  function visibleScale(series) {
    const top = series.reduce((peak, item) => !peak || Number(item.peak) > Number(peak.peak) ? item : peak, null);
    return top?.ticks || [];
  }
  function clock(zone, period, full) {
    const detail = {month: 'short', day: 'numeric'};
    const options = full ? {...detail, year: 'numeric', hour: '2-digit', minute: '2-digit',
      hourCycle: 'h23', timeZoneName: 'shortOffset'} :
      period === 'today' ? {hour: '2-digit', minute: '2-digit', hourCycle: 'h23'} :
      period === 'all' ? {month: 'short', year: '2-digit'} : detail;
    return new Intl.DateTimeFormat('en-GB', {timeZone: zone, ...options});
  }

  class View {
    constructor(api, changeDemand) {
      this.api = api;
      this.changeDemand = changeDemand;
      this.period = 'month';
      this.cache = new Map();
      this.entries = new Map();
      this.selected = new Map();
      this.width = 620;
      this.root = e('section', undefined, 'account-timeline');
      const title = e('h2', 'Used CCost'), id = 'account-timeline-title';
      title.id = id;
      this.root.setAttribute('aria-labelledby', id);
      const filters = e('div', undefined, 'ai-stats-periods');
      filters.setAttribute('role', 'group');
      filters.setAttribute('aria-label', 'Usage period');
      this.buttons = periods.map(([period, text]) => {
        const button = e('button', text);
        button.type = 'button';
        button.addEventListener('click', () => this.select(period));
        filters.append(button);
        return [period, button];
      });
      const body = e('div', undefined, 'account-timeline-body');
      const graph = e('div', undefined, 'account-timeline-graph');
      this.graph = graph;
      this.plot = svg('svg', {role: 'group', 'aria-label': 'Usage by time. Use Left and Right arrows for bucket values.',
        tabindex: '0', class: 'account-timeline-plot'});
      this.layers = svg('g', {'aria-hidden': 'true'});
      this.cursor = svg('line', {class: 'account-timeline-cursor', visibility: 'hidden', 'aria-hidden': 'true'});
      this.plot.append(this.layers, this.cursor);
      this.message = e('p', '', 'account-timeline-message');
      this.tooltip = e('div', undefined, 'account-timeline-tip');
      this.tooltip.hidden = true;
      this.announce = e('span', '', 'sr-only');
      this.announce.setAttribute('role', 'status');
      graph.append(this.plot, this.message, this.tooltip, this.announce);
      this.legend = e('fieldset', undefined, 'account-timeline-legend');
      this.legend.append(e('legend', 'Accounts and quotas'));
      this.legendRows = e('div');
      this.legend.append(this.legendRows);
      body.append(graph, this.legend);
      this.root.append(title, filters, body);
      this.plot.addEventListener('keydown', event => this.key(event));
      this.plot.addEventListener('focus', () => this.inspect(this.focusBucket ?? 0, true));
      this.plot.addEventListener('blur', () => this.inspect(null));
      this.plot.addEventListener('pointermove', event => this.pointer(event));
      this.plot.addEventListener('pointerdown', event => this.pointer(event));
      this.plot.addEventListener('pointerleave', () => {
        this.inspect(document.activeElement === this.plot ? this.focusBucket : null);
      });
      if (typeof ResizeObserver !== 'undefined') new ResizeObserver(records => {
        const width = Math.floor(records[0].contentRect.width);
        if (width > 0 && width !== this.width) {
          this.width = width;
          this.draw();
        }
      }).observe(graph);
      this.draw();
    }

    setScope(scope) {
      if (this.scope === scope) return;
      this.scope = scope;
      this.cache.clear();
      this.legendFor([]);
      // IDs include source/account/quota semantics; keep choices for still
      // compatible entries until the server publishes its new roster.
      this.roster = [];
      this.rosterRevision = null;
      this.focusBucket = null;
      this.inspect(null);
      ReportView.text(this.announce, '');
      this.draw();
      this.schedule(0);
    }

    invalidate() {
      this.selected.clear();
      this.setScope(null);
      this.active(false);
    }

    select(period) {
      if (this.period === period) return;
      this.period = period;
      this.focusBucket = null;
      this.initial = true;
      this.draw();
      this.changeDemand();
      this.schedule(0);
    }

    active(value) {
      if (value === this.visible) return;
      this.visible = value;
      if (value) {
        this.initial = !this.cache.has(this.period);
        this.draw();
      }
      this.schedule(0);
    }

    schedule(delay) {
      clearTimeout(this.timer);
      if (this.visible && !this.pending) this.timer = setTimeout(() => this.refresh(), delay);
    }

    async refresh() {
      if (!this.visible || this.pending) return;
      const period = this.period, revision = this.cache.get(period)?.revision ?? null;
      this.pending = true;
      try {
        const value = await this.api('/api/accounts/timeline', {period, revision});
        if (!this.visible || period !== this.period || value.scope !== this.scope) return;
        if (value.view) {
          this.initial = false;
          this.cache.set(period, {revision: value.revision, view: value.view});
          this.roster = value.view.series;
          this.draw();
        } else if (!value.unchanged) {
          const prior = this.cache.delete(period);
          const empty = value.ready && !value.series.length;
          if (empty) this.initial = false;
          if (prior || empty || this.rosterRevision !== value.revision) {
            this.rosterRevision = value.revision;
            this.roster = value.series;
            this.draw();
          }
        }
      } catch (_) {
        // Host health owns sign-in and connection UX. Never narrate retries.
      } finally {
        this.pending = false;
        this.schedule(period !== this.period ? 0 : this.initial ? 2000 : 6000);
      }
    }

    legendFor(series) {
      const wanted = new Set(series.map(item => item.id));
      for (const [id, entry] of this.entries)
        if (!wanted.has(id)) { entry.root.remove(); this.entries.delete(id); }
      this.legend.hidden = !wanted.size;
      series.forEach((item, index) => {
        let entry = this.entries.get(item.id);
        if (!entry) {
          const input = e('input'), name = e('span'), wrapper = e('label');
          input.type = 'checkbox';
          const swatch = svg('svg', {viewBox: '0 0 26 9', class: 'account-timeline-swatch', 'aria-hidden': 'true'});
          swatch.append(seriesStyle(svg('line', {x1: 0, x2: 26, y1: 4.5, y2: 4.5}), item.id));
          input.addEventListener('change', () => {
            this.selected.set(item.id, input.checked);
            this.draw();
          });
          entry = {input, name, root: wrapper};
          wrapper.append(input, swatch, name);
          this.entries.set(item.id, entry);
        }
        entry.input.checked = this.selected.get(item.id) ?? item.primary;
        ReportView.text(entry.name, label(item));
        if (this.legendRows.children[index] !== entry.root)
          this.legendRows.insertBefore(entry.root, this.legendRows.children[index] || null);
      });
    }

    draw() {
      const view = this.cache.get(this.period)?.view;
      const roster = view?.series || this.roster || [];
      this.buttons.forEach(([id, button]) => button.setAttribute('aria-pressed', String(id === this.period)));
      this.legendFor(roster);
      this.lines = view?.series.filter(item => this.selected.get(item.id) ?? item.primary) || [];
      this.view = view;
      const scale = visibleScale(this.lines.filter(item => item.points.some(point => point !== null)));
      const message = !view ? (this.initial && this.visible ? 'Loading usage…' : 'No usage history to show.') :
        roster.length && !this.lines.length ? 'Select a series to show its usage.' :
        !scale.length ? 'No usage history to show.' : '';
      ReportView.text(this.message, message);
      this.message.hidden = !message;
      this.plot.classList.toggle('account-timeline-blank', !!message);
      if (message) {
        this.plot.setAttribute('tabindex', '-1');
        this.layers.replaceChildren();
        this.inspect(null);
        return;
      }
      this.plot.setAttribute('tabindex', '0');
      this.plot.setAttribute('viewBox', `0 0 ${this.width} 270`);
      const width = this.width, max = Number(scale.at(-1).amount);
      const left = this.left = width < 320 ? 55 : 75, right = this.right = width - 10, end = 237, top = 15;
      const x = this.x = stamp => left + (right - left) * (stamp - view.start_ms) / (view.end_ms - view.start_ms);
      const y = value => end - (end - top) * Number(value) / max;
      const shortDate = clock(view.timezone_id, view.period, false);
      this.fullDate = clock(view.timezone_id, view.period, true);
      const nodes = [];
      let lastLabel;
      for (const tick of scale) {
        const height = y(tick.amount);
        nodes.push(svg('line', {x1: left, x2: right, y1: height, y2: height, class: 'account-timeline-gridline'}));
        const text = shown(tick);
        if (text !== lastLabel) nodes.push(svg('text', {x: left - 7, y: height + 4, 'text-anchor': 'end'}, text));
        lastLabel = text;
      }
      const count = Math.max(2, Math.min(6, Math.floor((right - left) / 86)));
      for (let i = 0; i < count; i++) {
        const time = Math.round(view.start_ms + i / (count - 1) * (view.end_ms - view.start_ms));
        nodes.push(svg('text', {x: x(time), y: 259,
          'text-anchor': i === 0 ? 'start' : i === count - 1 ? 'end' : 'middle'}, shortDate.format(time)));
      }
      for (const item of this.lines) {
        let path = '', run = [], dots = [];
        const flush = () => {
          if (run.length === 1) dots.push(run[0]);
          else if (run.length) path += `M${run.join('L')}`;
          run = [];
        };
        item.points.forEach((point, index) => {
          if (point === null) return flush();
          const [start, finish] = view.buckets[index];
          run.push([x((start + finish) / 2).toFixed(2), y(point.amount).toFixed(2)]);
        });
        flush();
        if (path) nodes.push(seriesStyle(svg('path', {d: path, class: 'account-timeline-line'}), item.id));
        for (const [cx, cy] of dots)
          nodes.push(seriesStyle(svg('circle', {cx, cy, r: 3, class: 'account-timeline-dot'}), item.id));
      }
      this.layers.replaceChildren(...nodes);
      this.cursor.setAttribute('y1', top);
      this.cursor.setAttribute('y2', end);
      this.inspect(this.bucket);
    }

    key(event) {
      const steps = {ArrowLeft: -1, ArrowRight: 1, Home: -Infinity, End: Infinity};
      if (!this.view?.buckets.length || !Object.hasOwn(steps, event.key)) return;
      event.preventDefault();
      const value = (this.focusBucket ?? 0) + steps[event.key];
      this.focusBucket = Math.max(0, Math.min(this.view.buckets.length - 1, value));
      this.inspect(this.focusBucket, true);
    }

    pointer(event) {
      if (!this.view?.buckets.length || this.plot.classList.contains('account-timeline-blank')) return;
      const box = this.plot.getBoundingClientRect(), px = (event.clientX - box.left) * this.width / box.width;
      const time = this.view.start_ms + (px - this.left) / (this.right - this.left) *
        (this.view.end_ms - this.view.start_ms);
      let lo = 0, hi = this.view.buckets.length - 1;
      while (lo < hi) {
        const middle = (lo + hi) >> 1;
        if (time < this.view.buckets[middle][1]) hi = middle;
        else lo = middle + 1;
      }
      this.inspect(lo);
    }

    inspect(index, announce = false) {
      this.bucket = index;
      const bucket = this.view?.buckets[index];
      if (!bucket || this.plot.classList.contains('account-timeline-blank')) {
        this.tooltip.hidden = true;
        this.cursor.setAttribute('visibility', 'hidden');
        return;
      }
      const [start, end] = bucket;
      const x = this.x((start + end) / 2);
      this.cursor.setAttribute('x1', x);
      this.cursor.setAttribute('x2', x);
      this.cursor.setAttribute('visibility', 'visible');
      const time = `${this.fullDate.format(start)} – ${this.fullDate.format(end)}`;
      const values = this.lines.map(item => `${label(item)}: ${item.points[index] ? shown(item.points[index]) : '—'}`);
      this.tooltip.replaceChildren(e('strong', time), ...values.map(value => e('div', value)));
      this.tooltip.classList.toggle('align-end', x < this.width / 2);
      this.tooltip.hidden = false;
      if (announce) ReportView.text(this.announce, [time, ...values].join('. '));
    }
  }
  return {View, visibleScale};
})();
