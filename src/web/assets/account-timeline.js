'use strict';
const AccountTimelineView = (() => {
  const periods = [['today', 'Today'], ['7-days', '7 days'], ['30-days', '30 days'],
    ['month', 'This month']];
  const e = (...args) => ReportView.element(...args);
  const ns = 'http://www.w3.org/2000/svg';
  const plotHeight = 240, top = 12, bottom = 206, inset = 10;
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
  function visibleScale(series) {
    const largest = series.reduce((peak, item) => !peak || Number(item.peak) > Number(peak.peak) ? item : peak, null);
    return largest?.ticks || [];
  }
  function clock(zone, options) {
    return new Intl.DateTimeFormat('en-GB', {timeZone: zone, ...options});
  }
  function tickLabels(view, width, group) {
    const day = {month: 'short', day: 'numeric'};
    const year = clock(view.timezone_id, {year: '2-digit'});
    const rollsYear = year.format(view.start_ms) !== year.format(view.buckets.at(-1)[0]);
    const hourly = view.period === 'today';
    const format = clock(view.timezone_id, hourly ? {hour: '2-digit', hourCycle: 'h23'} :
      rollsYear ? {...day, year: '2-digit'} : day);
    const count = view.buckets.length;
    const spacing = hourly ? 36 : rollsYear ? 100 : 66;
    const step = Math.max(1, Math.ceil(spacing / group));
    return view.buckets.flatMap(([start], index) => {
      const last = index === count - 1;
      if (!last && index !== 0 && (index % step || count - 1 - index < step)) return [];
      const x = Math.max(inset, Math.min(width - inset, inset + group * (index + .5)));
      const anchor = last && count > 1 ? 'end' : index === 0 ? 'start' : 'middle';
      return [svg('text', {x, y: 230, 'text-anchor': anchor}, format.format(start))];
    });
  }

  class View {
    constructor(api, changeDemand) {
      this.api = api;
      this.changeDemand = changeDemand;
      this.period = 'month';
      this.cache = new Map();
      this.entries = new Map();
      this.selected = new Map();
      this.colors = new Map();
      this.generation = 0;
      this.width = 0;
      this.root = e('section', undefined, 'account-timeline');
      const title = e('h2', 'CCost'), id = 'account-timeline-title';
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
      const layout = e('div', undefined, 'account-timeline-layout');
      const graph = e('div', undefined, 'account-timeline-graph');
      this.frame = e('div', undefined, 'account-timeline-frame');
      this.axis = e('div', undefined, 'account-timeline-axis');
      this.axis.setAttribute('aria-hidden', 'true');
      this.scroller = e('div', undefined, 'account-timeline-scroll');
      this.plot = svg('svg', {role: 'group', 'aria-label': 'Usage by time. Use Left and Right arrows for bucket values.',
        tabindex: '0', class: 'account-timeline-plot'});
      this.shades = svg('g', {'aria-hidden': 'true'});
      this.highlight = svg('rect', {class: 'account-timeline-highlight', y: top, height: bottom - top,
        rx: 4, visibility: 'hidden', 'aria-hidden': 'true'});
      this.layers = svg('g', {'aria-hidden': 'true'});
      this.plot.append(this.shades, this.highlight, this.layers);
      this.scroller.append(this.plot);
      this.message = e('p', '', 'account-timeline-message');
      this.tooltip = e('div', undefined, 'account-timeline-tip');
      this.tooltip.hidden = true;
      this.announce = e('span', '', 'sr-only');
      this.announce.setAttribute('role', 'status');
      this.frame.append(this.axis, this.scroller, this.tooltip);
      graph.append(this.message, this.frame, this.announce);
      this.legend = e('fieldset', undefined, 'account-timeline-legend');
      this.legend.append(e('legend', 'Accounts and quotas'));
      this.legendRows = e('div');
      this.legend.append(this.legendRows);
      layout.append(graph, this.legend);
      this.root.append(title, filters, layout);
      this.plot.addEventListener('keydown', event => this.key(event));
      this.plot.addEventListener('focus', () => this.inspect(this.focusBucket ?? 0, true));
      this.plot.addEventListener('blur', () => this.inspect(null));
      this.plot.addEventListener('pointermove', event => this.pointer(event));
      this.plot.addEventListener('pointerdown', event => this.pointer(event));
      this.plot.addEventListener('pointerleave', () => {
        this.inspect(document.activeElement === this.plot ? this.focusBucket : null);
      });
      this.scroller.addEventListener('scroll', () => this.positionTip());
      if (typeof ResizeObserver !== 'undefined') new ResizeObserver(records => {
        const width = Math.floor(records[0].contentRect.width);
        if (width > 0 && width !== this.width) {
          this.width = width;
          this.draw();
        }
      }).observe(this.scroller);
      this.draw();
    }

    setScope(scope) {
      if (this.scope === scope) return;
      this.scope = scope;
      this.generation++;
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
      this.colors.clear();
      this.setScope(null);
      this.active(false);
    }

    select(period) {
      if (this.period === period) return;
      this.period = period;
      this.generation++;
      this.focusBucket = null;
      const cached = this.cache.get(period)?.view;
      this.initial = !cached || !!cached.pending_buckets.length;
      this.inspect(null);
      this.draw();
      this.scroller.scrollLeft = 0;
      this.changeDemand();
      this.schedule(0);
    }

    active(value) {
      if (value === this.visible) return;
      this.visible = value;
      this.generation++;
      if (value) {
        const view = this.cache.get(this.period)?.view;
        this.initial = !view || !!view.pending_buckets.length;
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
      const generation = this.generation;
      this.pending = true;
      try {
        const value = await this.api('/api/accounts/timeline', {period, revision});
        if (generation !== this.generation || value.scope !== this.scope) return;
        if (value.view) {
          if (!value.view.pending_buckets.length) this.initial = false;
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
        this.schedule(generation !== this.generation ? 0 : this.initial ? 2000 : 6000);
      }
    }

    legendFor(series) {
      const wanted = new Set(series.map(item => item.id));
      for (const [id, entry] of this.entries)
        if (!wanted.has(id)) { entry.root.remove(); this.entries.delete(id); }
      this.legend.hidden = !wanted.size;
      const occupied = new Set(series.flatMap(item => this.colors.has(item.id) ? [this.colors.get(item.id)] : []));
      series.forEach((item, index) => {
        if (!this.colors.has(item.id)) {
          const preferred = (parseInt(item.id.slice(0, 8), 16) >>> 0) % 8;
          let color = preferred;
          for (let offset = 0; offset < 8; offset++) {
            const candidate = (preferred + offset) % 8;
            if (!occupied.has(candidate)) { color = candidate; break; }
          }
          this.colors.set(item.id, color);
          occupied.add(color);
        }
        let entry = this.entries.get(item.id);
        if (!entry) {
          const input = e('input'), name = e('span'), wrapper = e('label');
          input.type = 'checkbox';
          const swatch = e('span', undefined, 'account-timeline-swatch');
          swatch.setAttribute('data-ink', this.colors.get(item.id));
          swatch.setAttribute('aria-hidden', 'true');
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
      this.series = view?.series.filter(item => this.selected.get(item.id) ?? item.primary) || [];
      this.view = view;
      this.acquiring = new Set(view?.pending_buckets);
      this.partial = new Set(view?.partial_buckets);
      const scale = visibleScale(this.series.filter(item => item.points.some(point => point !== null)));
      const unselected = roster.length && !roster.some(item => this.selected.get(item.id) ?? item.primary);
      const exploring = this.initial && this.visible;
      const message = unselected ? 'Select a series to show its usage.' :
        exploring && (!view || this.acquiring.size) ? 'Loading usage…' :
        !scale.length && !this.acquiring.size ? 'No usage history to show.' : '';
      ReportView.text(this.message, message);
      this.message.hidden = !message;
      this.frame.hidden = !view?.buckets.length || !!unselected;
      this.plot.setAttribute('tabindex', this.frame.hidden ? '-1' : '0');
      if (this.frame.hidden) return this.inspect(null);

      const axis = [];
      let lastLabel;
      scale.forEach((tick, index) => {
        const text = shown(tick);
        if (text === lastLabel) return;
        const node = e('span', text, 'account-timeline-tick');
        node.style.top = `${bottom - index * (bottom - top) / (scale.length - 1)}px`;
        axis.push(node);
        lastLabel = text;
      });
      this.axis.replaceChildren(...axis);
      const available = this.scroller.clientWidth || this.width;
      const count = view.buckets.length, seriesCount = this.series.length;
      const width = Math.max(available, 2 * inset + count * Math.max(24, seriesCount * 8 + 10));
      const group = this.group = (width - 2 * inset) / count;
      this.plot.setAttribute('width', width);
      this.plot.setAttribute('height', plotHeight);
      this.x = index => inset + index * group;
      this.fullDate = clock(view.timezone_id, {month: 'short', day: 'numeric', year: 'numeric',
        hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZoneName: 'shortOffset'});

      const shades = [];
      for (let index = 0; index < count; index++) {
        if (!this.acquiring.has(index)) continue;
        const first = index;
        while (this.acquiring.has(index + 1)) index++;
        shades.push(svg('rect', {class: 'account-timeline-loading', x: this.x(first) + 1, y: top,
          width: (index - first + 1) * group - 2, height: bottom - top, rx: 4}));
      }
      this.shades.replaceChildren(...shades);
      const nodes = tickLabels(view, width, group);
      const bar = Math.min(28, (group - 8) / Math.max(1, seriesCount) - 2);
      const max = Number(scale.at(-1)?.amount);
      if (max > 0) for (const [slot, item] of this.series.entries()) {
        item.points.forEach((point, index) => {
          const amount = Number(point?.amount);
          if (!(amount > 0)) return;
          const height = Math.max(1, (bottom - top) * (amount / max));
          const x = this.x(index) + (group - seriesCount * (bar + 2) + 2) / 2 + slot * (bar + 2);
          // Clip the bottom corner of the rounded column at the value origin.
          const radius = Math.min(3, height, bar / 2);
          const y = bottom - height, right = x + bar;
          const shape = `M${x},${bottom}V${y + radius}Q${x},${y} ${x + radius},${y}` +
            `H${right - radius}Q${right},${y} ${right},${y + radius}V${bottom}Z`;
          nodes.push(svg('path', {d: shape, class: 'account-timeline-bar', 'data-ink': this.colors.get(item.id),
            'data-bucket': index}));
        });
      }
      for (const index of this.partial) {
        nodes.push(svg('circle', {cx: this.x(index) + group / 2, cy: 214, r: 2,
          class: 'account-timeline-partial'}));
      }
      this.layers.replaceChildren(...nodes);
      this.highlight.setAttribute('width', group - 2);
      this.inspect(this.bucket);
    }

    key(event) {
      if (event.key === 'Escape') return this.inspect(null);
      const steps = {ArrowLeft: -1, ArrowRight: 1, Home: -Infinity, End: Infinity};
      if (this.frame.hidden || !Object.hasOwn(steps, event.key)) return;
      event.preventDefault();
      const value = (this.focusBucket ?? 0) + steps[event.key];
      this.focusBucket = Math.max(0, Math.min(this.view.buckets.length - 1, value));
      this.inspect(this.focusBucket, true);
    }

    pointer(event) {
      if (this.frame.hidden) return;
      const box = this.plot.getBoundingClientRect();
      const index = Math.floor((event.clientX - box.left - inset) / this.group);
      if (event.type === 'pointerdown' && index >= 0 && index < this.view.buckets.length) this.focusBucket = index;
      if (index !== this.bucket || this.tooltip.hidden) this.inspect(index);
    }

    inspect(index, announce = false) {
      this.bucket = index;
      const bucket = this.view?.buckets[index];
      if (!bucket || this.frame.hidden) {
        this.tooltip.hidden = true;
        this.highlight.setAttribute('visibility', 'hidden');
        return;
      }
      const [start, end] = bucket;
      const x = this.x(index);
      this.highlight.setAttribute('x', x + 1);
      this.highlight.setAttribute('visibility', 'visible');
      if (announce) {
        this.focusBucket = index;
        if (x < this.scroller.scrollLeft) this.scroller.scrollLeft = x - inset;
        else if (x + this.group > this.scroller.scrollLeft + this.scroller.clientWidth)
          this.scroller.scrollLeft = x + this.group + inset - this.scroller.clientWidth;
      }
      const partial = this.partial.has(index) ? ' · Partial' : '';
      const pending = this.acquiring.has(index);
      const time = `${this.fullDate.format(start)} – ${this.fullDate.format(end)}${partial}`;
      const values = this.series.map(item => {
        const point = item.points[index];
        return `${label(item)}: ${point ? shown(point) + (pending ? ' (so far)' : '') : pending ? '—' : 'Unavailable'}`;
      });
      const heading = pending && this.initial ? `${time} · Loading` : time;
      this.tooltip.replaceChildren(e('strong', heading), ...values.map(value => e('div', value)));
      this.positionTip();
      if (announce) ReportView.text(this.announce, [heading, ...values].join('. '));
    }

    positionTip() {
      if (!this.view?.buckets[this.bucket] || this.frame.hidden) return;
      const center = this.x(this.bucket) + this.group / 2 - this.scroller.scrollLeft;
      this.tooltip.hidden = center < 0 || center > this.scroller.clientWidth;
      if (this.tooltip.hidden) return;
      const offset = this.scroller.offsetLeft + center;
      this.tooltip.style.left = `${Math.max(0, Math.min(this.frame.clientWidth - this.tooltip.offsetWidth,
        offset - this.tooltip.offsetWidth / 2))}px`;
      this.tooltip.classList.toggle('below', this.frame.getBoundingClientRect().top < this.tooltip.offsetHeight + 12);
    }
  }
  return {View, visibleScale};
})();
