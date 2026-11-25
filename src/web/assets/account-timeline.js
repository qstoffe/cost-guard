'use strict';
const AccountTimelineView = (() => {
  const periods = [['today', 'Today'], ['7-days', '7 days'], ['30-days', '30 days'],
    ['month', 'This month']];
  const e = (...args) => ReportView.element(...args);
  const ns = 'http://www.w3.org/2000/svg';
  const top = 27, bottom = 194, inset = 3, paletteSize = 12;
  const labelBaseline = 214, highlightBottom = 221, shadeTop = 4;
  const {DATE, TIME} = ReportView.DateTimeMode;
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
  function swatch(ink) {
    const node = e('span', undefined, 'account-timeline-swatch');
    node.setAttribute('data-ink', ink);
    node.setAttribute('aria-hidden', 'true');
    return node;
  }
  function viewport() {
    const {offsetLeft = 0, offsetTop = 0, width = innerWidth, height = innerHeight} = globalThis.visualViewport || {};
    return {left: offsetLeft + 8, right: offsetLeft + width - 8, top: offsetTop + 8, bottom: offsetTop + height - 8};
  }
  const clamp = (value, min, max) => Math.max(min, Math.min(value, max));
  function visibleScale(series) {
    const largest = series.reduce((peak, item) => !peak || ReportView.compare(item.peak, peak.peak) > 0 ? item : peak, null);
    return largest?.ticks || [];
  }
  function minimumWidth(view) {
    const minimum = view.period === 'today' ? 33 : view.period === '7-days' ? 42 : 25;
    return 2 * inset + view.buckets.length * minimum;
  }
  function layoutSlots(view, width) {
    const hourly = view.period === 'today', shortDates = view.period === '7-days';
    const group = (width - 2 * inset) / view.buckets.length;
    const slots = view.buckets.map(([start], index) => {
      const date = view.slot_dates?.[index];
      const [day, time] = date ? [ReportView.formatDateTime(date, DATE)] :
        ReportView.timestamp(start, view.timezone_id).split(' ');
      const x = inset + index * group;
      return {index, key: hourly ? start : day, day, time, x, center: x + group / 2};
    });
    const hours = new Map(), months = [];
    for (const slot of slots) {
      if (hourly) {
        const hour = slot.time?.slice(0, 2);
        const group = hours.get(hour) || [];
        group.push(slot);
        hours.set(hour, group);
      } else {
        const month = slot.day.slice(0, 7);
        const last = months.at(-1);
        if (last?.month === month) last.count++;
        else months.push({month, x: slot.x, count: 1});
      }
    }
    for (const repeated of hours.values())
      if (repeated.length > 1) repeated.forEach((slot, index) => { slot.occurrence = index + 1; });
    const years = new Set(months.map(({month}) => month.slice(0, 4)));
    return {slots, width, group, hourly, shortDates, months, crossYear: years.size > 1};
  }
  function equalSlots(a, b) {
    return a && b && a.period === b.period && a.timezone_id === b.timezone_id &&
      a.buckets.length === b.buckets.length && b.buckets.every(([start], i) => a.buckets[i][0] === start);
  }
  function rangeLabel(view, layout, future) {
    const mode = layout.hourly ? ReportView.DateTimeMode.DATE_TIME : DATE;
    const start = ReportView.formatDateTime(view.start_ms, mode, view.timezone_id);
    const end = ReportView.formatDateTime(view.end_ms, layout.hourly ? TIME : DATE, view.timezone_id);
    if (start === 'N/A' || end === 'N/A') return '—';
    if (layout.hourly) {
      const occurrence = view.end_occurrence ? ` (${view.end_occurrence === 1 ? 'first' : 'second'})` : '';
      return `${start}–${end}${occurrence}`;
    }
    // Use the last represented date, not a reserved date or the next day's
    // midnight (the exclusive end of a rolling window on that boundary).
    const last = layout.slots.findLast(slot => !future.has(slot.index));
    return `${start} – ${last?.day ?? end}`;
  }
  function axisLabels(layout, future, nonWorking) {
    const {slots, hourly, shortDates, months, group, crossYear} = layout;
    const labels = slots.map(slot => {
      const tick = hourly ? slot.time?.slice(0, 2) : Number(slot.day.slice(8));
      const node = svg('text', {x: slot.center, y: labelBaseline, class: 'account-timeline-slot-label',
        'data-bucket': slot.index, 'data-future': future.has(slot.index), 'text-anchor': 'middle'},
        slot.day === 'N/A' ? '—' : undefined);
      if (slot.day !== 'N/A') {
        if (nonWorking.has(slot.index)) node.append(svg('tspan', {class: 'account-timeline-non-working'}, tick));
        else node.textContent = tick;
        if (shortDates) node.append(`/${Number(slot.day.slice(5, 7))}`);
      }
      if (slot.occurrence) node.append(svg('tspan', {class: 'account-timeline-fold'}, slot.occurrence === 1 ? '¹' : '²'));
      return node;
    });
    months.forEach(({month, x, count}, index) => {
      const width = group * count;
      const [year, number] = month.split('-').map(Number);
      if (!year || !number) return;
      const caption = ReportView.calendarCaption(`${month}-01`, width < 85 ? 'month-short' : 'month-long',
        document.documentElement.lang || 'en');
      if (index) labels.push(svg('rect', {x: x - .5, y: bottom + 6, width: 1, height: crossYear ? 51 : 38,
        class: 'account-timeline-month-divider'}));
      const attrs = {x: x + width / 2, y: 236, 'text-anchor': 'middle', class: 'account-timeline-month-label'};
      labels.push(svg('text', attrs, caption));
      if (crossYear) labels.push(svg('text', {...attrs, y: 250}, year));
    });
    return labels;
  }
  function loadingCue(index, x, active) {
    const y = (shadeTop + bottom) / 2;
    const d = active ? `M${x + 4},${y}a4,4 0 1 1 -4,-4` :
      `M${x - 3},${y - 4}h6l-6,8h6Z`;
    return svg('path', {class: active ? 'account-timeline-ring' : 'account-timeline-hourglass', 'data-bucket': index, d});
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
      const header = e('div', undefined, 'account-timeline-header');
      const graph = e('div', undefined, 'account-timeline-graph');
      this.frame = e('div', undefined, 'account-timeline-frame');
      this.axis = e('div', undefined, 'account-timeline-axis');
      this.axis.setAttribute('aria-hidden', 'true');
      this.scroller = e('div', undefined, 'account-timeline-scroll');
      this.plot = svg('svg', {role: 'group', 'aria-label': 'Usage by time. Use Left and Right arrows for bucket values.',
        tabindex: '0', class: 'account-timeline-plot', preserveAspectRatio: 'none'});
      this.shades = svg('g', {'aria-hidden': 'true'});
      this.highlight = svg('rect', {class: 'account-timeline-highlight', y: shadeTop, height: highlightBottom - shadeTop,
        rx: 4, visibility: 'hidden', 'aria-hidden': 'true'});
      this.layers = svg('g', {'aria-hidden': 'true'});
      this.labels = svg('g', {'aria-hidden': 'true'});
      this.targets = svg('g', {'aria-hidden': 'true'});
      this.plot.append(this.shades, this.highlight, this.layers, this.labels, this.targets);
      this.scroller.append(this.plot);
      this.range = e('p', undefined, 'account-timeline-range');
      this.selectedLegend = e('ul', undefined, 'account-timeline-selected');
      this.selectedLegend.setAttribute('role', 'list');
      this.selectedLegend.setAttribute('aria-label', 'Selected accounts');
      this.empty = e('div', undefined, 'account-timeline-empty');
      this.message = e('span');
      this.initialRing = e('span', undefined, 'account-timeline-ring');
      this.initialRing.setAttribute('aria-hidden', 'true');
      this.empty.append(this.initialRing, this.message);
      this.tooltip = e('div', undefined, 'account-timeline-tip');
      this.tooltip.hidden = true;
      this.tipTitle = e('strong');
      this.tipState = e('span', undefined, 'account-timeline-tip-state');
      const tipHeader = e('div', undefined, 'account-timeline-tip-header');
      tipHeader.append(this.tipTitle, this.tipState);
      this.tipValues = e('div', undefined, 'account-timeline-tip-values');
      this.tipValues.setAttribute('aria-label', 'Selected account values');
      this.tooltip.append(tipHeader, this.tipValues);
      this.announce = e('span', '', 'sr-only');
      this.announce.setAttribute('role', 'status');
      this.frame.append(this.axis, this.scroller, this.range, this.selectedLegend, this.tooltip);
      graph.append(this.frame, this.empty, this.announce);
      this.chooser = e('button', undefined, 'account-timeline-chooser');
      this.chooser.type = 'button';
      this.summary = e('span', undefined, 'account-timeline-summary');
      this.summary.setAttribute('aria-hidden', 'true');
      this.selectionCount = e('span', undefined, 'account-timeline-count');
      const caret = e('span', '⌄', 'account-timeline-caret');
      caret.setAttribute('aria-hidden', 'true');
      this.chooser.append(this.summary, e('span', 'Accounts'), this.selectionCount, caret);
      this.chooser.setAttribute('popovertarget', 'account-timeline-options');
      this.panel = e('div', undefined, 'account-timeline-options');
      this.panel.id = 'account-timeline-options';
      this.panel.setAttribute('popover', 'auto');
      this.legend = e('fieldset', undefined, 'account-timeline-legend');
      this.legend.append(e('legend', 'Accounts'));
      this.legendRows = e('div');
      this.legend.append(this.legendRows);
      this.panel.append(this.legend);
      header.append(title, this.chooser, filters, this.panel);
      this.root.append(header, graph);
      this.panel.addEventListener('toggle', () => this.positionOverlays());
      this.plot.addEventListener('keydown', event => this.key(event));
      this.plot.addEventListener('focus', () => this.choose(this.indexOf(this.focusKey) ?? 0));
      this.plot.addEventListener('blur', event => {
        if (!this.tooltip.contains(event.relatedTarget)) this.inspect(null);
      });
      this.tipValues.addEventListener('blur', event => {
        if (event.relatedTarget !== this.plot) this.inspect(null);
      });
      this.tipValues.addEventListener('keydown', event => {
        if (event.key === 'Escape') { this.plot.focus({preventScroll: true}); this.inspect(null); }
      });
      this.plot.addEventListener('pointermove', event => this.pointer(event));
      this.plot.addEventListener('pointerdown', event => this.pointer(event));
      this.plot.addEventListener('pointerup', event => this.pointer(event));
      this.plot.addEventListener('pointerleave', event => {
        if (event.pointerType === 'touch' || this.tooltip.contains(event.relatedTarget)) return;
        this.inspect(document.activeElement === this.plot ? this.indexOf(this.focusKey) : null,
          this.plot.matches(':focus-visible'));
      });
      this.scroller.addEventListener('scroll', () => this.positionTip());
      // One instance per Accounts view lifecycle; removing the root also stops
      // positioning work until the section is visible again.
      document.addEventListener('scroll', () => this.positionOverlays(), {capture: true, passive: true});
      globalThis.visualViewport?.addEventListener('resize', () => this.positionOverlays());
      globalThis.visualViewport?.addEventListener('scroll', () => this.positionOverlays());
      if (typeof ResizeObserver !== 'undefined') new ResizeObserver(records => {
        const width = Math.floor(records[0].contentRect.width);
        if (width > 0 && width !== this.width) {
          this.width = width;
          this.draw();
        }
      }).observe(this.frame);
      this.draw();
    }

    setScope(scope) {
      if (this.scope === scope) return;
      this.scope = scope;
      this.generation++;
      this.working = false;
      this.initial = scope != null;
      this.cache.clear();
      this.priceRevision = undefined;
      this.legendFor([]);
      // IDs include the source-qualified account identity; keep choices for still
      // compatible entries until the server publishes its new roster.
      this.roster = [];
      this.rosterRevision = null;
      this.focusKey = null;
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
      this.working = false;
      this.focusKey = null;
      const cached = this.cache.get(period)?.view;
      this.initial = !cached || !!cached.initial_pending_buckets?.length;
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
      this.working = false;
      if (value) {
        const view = this.cache.get(this.period)?.view;
        this.initial = !view || !!view.initial_pending_buckets?.length;
        this.draw();
      } else {
        this.panel.hidePopover();
        this.inspect(null);
        this.draw();
      }
      this.schedule(0);
    }

    schedule(delay) {
      clearTimeout(this.timer);
      if (this.visible && !this.pending) this.timer = setTimeout(() => this.refresh(), delay);
    }

    wake(hint, reconnected) {
      if (!this.cacheEvents || hint === this.cacheHint && !reconnected) return;
      this.cacheHint = hint;
      if (this.pending) this.cachePending = true;
      else this.schedule(0);
    }

    async refresh() {
      if (!this.visible || this.pending) return;
      const period = this.period, revision = this.cache.get(period)?.revision ?? null;
      const generation = this.generation;
      this.pending = true;
      try {
        const value = await this.api('/api/accounts/timeline', {period, revision});
        if (generation !== this.generation) return;
        const terminalChanged = this.terminal !== (value.terminal === true);
        this.terminal = value.terminal === true;
        if (value.scope !== this.scope) {
          if (!this.sharedHistory) return;
          this.setScope(value.scope);
        }
        const activityChanged = this.working !== (value.acquiring === true);
        this.working = value.acquiring === true;
        if (value.view) {
          this.initial = !!value.view.initial_pending_buckets?.length;
          if (value.view.price_revision !== this.priceRevision) {
            this.cache.clear();
            this.priceRevision = value.view.price_revision;
          }
          const {view} = value, previous = this.cache.get(period)?.shown;
          const shown = new Set();
          view.buckets.forEach(([start], index) => {
            if (previous?.has(start) || view.series.some(series => series.points[index] != null)) shown.add(start);
          });
          this.cache.set(period, {revision: value.revision, view, shown});
          this.roster = value.view.series;
          this.draw();
        } else if (!value.unchanged) {
          const prior = this.cache.delete(period);
          const empty = value.ready && !value.series.length;
          if (empty || prior) this.initial = !empty;
          if (prior || empty || activityChanged || terminalChanged || this.rosterRevision !== value.revision) {
            this.rosterRevision = value.revision;
            this.roster = value.series;
            this.draw();
          }
        } else if (activityChanged || terminalChanged) this.draw();
      } catch (_) {
        // Host health owns sign-in and connection UX. Never narrate retries.
        if (generation === this.generation && this.working) {
          this.working = false;
          this.draw();
        }
      } finally {
        this.pending = false;
        if (generation !== this.generation || this.cachePending) this.schedule(0);
        else if (!this.cacheEvents) this.schedule(this.initial ? 350 : 1500);
        this.cachePending = false;
      }
    }

    legendFor(series) {
      const wanted = new Set(series.map(item => item.id));
      for (const [id, entry] of this.entries)
        if (!wanted.has(id)) { entry.root.remove(); this.entries.delete(id); }
      this.chooser.hidden = !wanted.size;
      if (!wanted.size) this.panel.hidePopover();
      const occupied = new Set(series.flatMap(item => this.colors.has(item.id) ? [this.colors.get(item.id)] : []));
      const selectedInks = [];
      for (const id of [...wanted].sort()) {
        if (this.colors.has(id)) continue;
        const preferred = (parseInt(id.slice(0, 8), 16) >>> 0) % paletteSize;
        let color = preferred;
        for (let offset = 0; offset < paletteSize; offset++) {
          const candidate = (preferred + offset) % paletteSize;
          if (!occupied.has(candidate)) { color = candidate; break; }
        }
        this.colors.set(id, color);
        occupied.add(color);
      }
      series.forEach((item, index) => {
        let entry = this.entries.get(item.id);
        if (!entry) {
          const input = e('input'), name = e('span'), wrapper = e('label');
          input.type = 'checkbox';
          input.addEventListener('change', () => {
            this.selected.set(item.id, input.checked);
            this.draw();
          });
          entry = {input, name, root: wrapper};
          wrapper.append(input, swatch(this.colors.get(item.id)), name);
          this.entries.set(item.id, entry);
        }
        entry.input.checked = this.selected.get(item.id) ?? true;
        if (entry.input.checked) selectedInks.push(this.colors.get(item.id));
        ReportView.text(entry.name, item.account);
        if (this.legendRows.children[index] !== entry.root)
          this.legendRows.insertBefore(entry.root, this.legendRows.children[index] || null);
      });
      ReportView.text(this.selectionCount, `${selectedInks.length} selected`);
      this.summary.replaceChildren(...selectedInks.slice(0, 4).map(swatch));
    }

    draw() {
      const cached = this.cache.get(this.period);
      const view = cached?.view;
      const previous = this.view;
      const roster = view?.series || this.roster || [];
      this.buttons.forEach(([id, button]) => button.setAttribute('aria-pressed', String(id === this.period)));
      if (typeof ReportLoading !== 'undefined')
        ReportLoading.historyProgress(this, this.buttons.find(([id]) => id === this.period)?.[1],
           this.terminal ? {terminal: true} :
             view?.history_progress ?? (this.sharedHistory && !view ? {complete: false} : undefined));
      this.legendFor(roster);
      const selectedSeries = roster.filter(item => this.selected.get(item.id) ?? true);
      this.series = view ? selectedSeries : [];
      this.selectedLegend.hidden = !view || !selectedSeries.length;
      const totalText = value => value ? (view?.history_progress ? shown(value) :
        shown(value).replace(/^[~≈]/, '')) : '—';
      const legend = this.series.map(item => [
        this.colors.get(item.id), item.account,
        item.provider_monthly_total ? totalText(item.month_total) : totalText(item.total),
        item.provider_monthly_total ? totalText(item.observed_total) : null
      ]);
      const legendKey = JSON.stringify(legend);
      if (legendKey !== this.legendKey) {
        this.legendKey = legendKey;
        this.selectedLegend.replaceChildren(...legend.map(([ink, name, total, observed]) => {
          const row = e('li');
          const value = e('span', total === '—' ? undefined : total, 'account-timeline-legend-value');
          if (total === '—') {
            const dash = e('span', total);
            dash.setAttribute('aria-hidden', 'true');
            value.append(dash, e('span', 'Total unavailable', 'sr-only'));
          }
          row.append(swatch(ink), e('span', name));
          if (observed !== null) {
            row.append(e('span', 'Provider monthly total:'), value,
              e('span', `Observed OpenCode subtotal: ${observed}`));
          } else row.append(value);
          return row;
        }));
      }
      this.view = view;
      this.unread = new Set(view?.initial_pending_buckets);
      this.shown = cached?.shown;
      this.partial = new Set(view?.partial_buckets);
      this.future = new Set(view?.future_buckets);
      this.nonWorking = new Set(view?.non_working_buckets);
      const scale = visibleScale(this.series.filter(item => item.points.some(point => point !== null)));
      const unselected = roster.length && !selectedSeries.length;
      const loading = !view && !unselected && this.initial && this.visible;
      const message = unselected ? 'Select an account to show its usage.' :
        this.sharedHistory && !view ? '' : loading ? 'Preparing chart' : 'No usage history to show.';
      ReportView.text(this.message, message);
      this.initialRing.hidden = this.sharedHistory || !loading || !this.working;
      this.frame.hidden = !view?.buckets.length;
      this.empty.hidden = !this.frame.hidden && !unselected;
      this.empty.classList.toggle('over-plot', !this.frame.hidden);
      this.plot.setAttribute('tabindex', this.frame.hidden ? '-1' : '0');
      const nativeMonth = this.series.some(item => item.provider_monthly_total);
      this.plot.setAttribute('aria-label', (nativeMonth ? 'Observed OpenCode daily CCost.' : 'Usage by time.') +
        ' Use Left and Right arrows for bucket values.');
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
      // SVG coordinates stay stable when a newly qualified value needs a wider
      // tick label. CSS fits the shape to the scroller, not vice versa.
      const minimum = minimumWidth(view);
      const width = Math.max(this.frame.clientWidth || this.width, minimum);
      const sameGeometry = equalSlots(previous, view) && this.layout?.width === width;
      const layout = sameGeometry ? this.layout : this.layout = layoutSlots(view, width);
      const {slots, group} = layout;
      this.range.hidden = !!unselected;
      this.range.title = layout.shortDates ? 'A rolling seven-day window; dates at either end may be partial.' : '';
      ReportView.text(this.range, (nativeMonth ? 'Observed OpenCode daily CCost · ' : '') +
        `Range: ${rangeLabel(view, layout, this.future)}`);
      if (!sameGeometry) {
        const plotHeight = layout.hourly ? 230 : layout.crossYear ? 258 : 244;
        this.plot.style.setProperty('--timeline-min-width', `${minimum}px`);
        this.plot.setAttribute('viewBox', `0 0 ${layout.width} ${plotHeight}`);
        this.plot.setAttribute('height', plotHeight);
        // Native hit testing is already in actual SVG coordinates, including
        // scroll, CSS zoom and transforms. Bars cannot be hit targets.
        this.targets.replaceChildren(...slots.map(({index, x}) => svg('rect', {
          class: 'account-timeline-target', x, y: 0, width: group, height: bottom + 25, 'data-slot': index
        })));
        this.highlight.setAttribute('width', group - 2);
      }
      if (!sameGeometry || previous.future_buckets?.length !== view.future_buckets?.length)
        this.labels.replaceChildren(...axisLabels(layout, this.future, this.nonWorking));

      const shades = [], nodes = [];
      let cue = false;
      for (const {index, x, center} of slots) {
        const future = this.future.has(index);
        const waiting = this.unread.has(index) && !this.shown?.has(view.buckets[index][0]);
        if (future || waiting) shades.push(svg('rect', {
          class: future ? 'account-timeline-future' : 'account-timeline-loading',
          'data-bucket': index, x: x + 1, y: shadeTop, width: group - 2, height: bottom - shadeTop, rx: 4
        }));
        // This is a neutral cue in a backed unread region, not a claim that
        // the source is reading one specific day (a tree can span many).
        if (!future && waiting) {
          const active = !cue && this.visible && this.working;
          nodes.push(loadingCue(index, center, active));
          cue ||= active;
        }
      }
      const bar = Math.min(28, group - 6);
      const max = Number(scale.at(-1)?.amount);
      if (max > 0) for (const {index, center} of slots) {
        // SVG paints in document order. The hit layer remains a single full slot.
        const overlays = this.series.filter(item => Number(item.points[index]?.amount) > 0);
        overlays.sort((a, b) => ReportView.compare(b.points[index].amount, a.points[index].amount)
          || a.id.localeCompare(b.id));
        for (const item of overlays) {
          const height = Math.max(1, (bottom - top) * Number(item.points[index].amount) / max);
          nodes.push(svg('rect', {x: center - bar / 2, y: bottom - height, width: bar, height,
            class: 'account-timeline-bar', 'data-ink': this.colors.get(item.id), 'data-bucket': index}));
        }
      }
      this.shades.replaceChildren(...shades);
      this.layers.replaceChildren(...nodes);
      this.inspect(this.indexOf(this.shownKey), this.tipInteractive);
      this.positionOverlays();
    }

    indexOf(key) {
      return this.layout?.slots.find(slot => slot.key === key)?.index;
    }
    key(event) {
      if (event.key === 'Escape') return this.inspect(null);
      const steps = {ArrowLeft: -1, ArrowRight: 1, Home: -Infinity, End: Infinity};
      if (this.frame.hidden || !Object.hasOwn(steps, event.key)) return;
      event.preventDefault();
      const value = (this.indexOf(this.shownKey) ?? this.indexOf(this.focusKey) ?? 0) + steps[event.key];
      this.choose(clamp(value, 0, this.layout.slots.length - 1), true);
    }
    pointer(event) {
      if (this.frame.hidden || (event.pointerType === 'touch' ? event.type !== 'pointerup' : event.type === 'pointerup'))
        return;
      const target = event.target.getAttribute('data-slot');
      const index = target === null ? null : Number(target);
      if (index !== null && (event.pointerType === 'touch' || event.type === 'pointerdown'))
        return this.choose(index, false, event.pointerType === 'touch');
      if (index !== this.indexOf(this.shownKey) || this.tooltip.hidden) this.inspect(index);
    }
    choose(index, scroll = false, pinned = false) {
      const slot = this.layout?.slots[index];
      if (!slot || this.frame.hidden) return;
      this.focusKey = slot.key;
      if (scroll) {
        const clip = this.scroller.getBoundingClientRect();
        const cell = this.targets.children[index].getBoundingClientRect();
        const ratio = clip.width / this.scroller.offsetWidth || 1;
        if (cell.left < clip.left) this.scroller.scrollLeft += (cell.left - clip.left) / ratio - inset;
        else if (cell.right > clip.right) this.scroller.scrollLeft += (cell.right - clip.right) / ratio + inset;
      }
      this.inspect(index, true, true, pinned);
    }
    inspect(index, interactive = false, announce = false, pinned = this.tipPinned && !announce && interactive) {
      const slot = this.layout?.slots[index];
      this.shownKey = slot?.key;
      this.tipInteractive = interactive;
      this.tipPinned = pinned;
      this.tipValues.tabIndex = interactive ? 0 : -1;
      this.tooltip.classList.toggle('interactive', interactive);
      this.tooltip.classList.toggle('pinned', pinned);
      if (!slot || this.frame.hidden) {
        this.tooltip.hidden = true;
        this.highlight.setAttribute('visibility', 'hidden');
        return;
      }
      this.highlight.setAttribute('x', slot.x + 1);
      this.highlight.setAttribute('visibility', 'visible');
      const future = this.future.has(index), partial = this.partial.has(index);
      let heading = slot.day;
      if (this.layout.hourly && slot.time) {
        const end = ReportView.formatDateTime(this.view.buckets[index][1], TIME, this.view.timezone_id);
        const repeat = slot.occurrence ? ` (${slot.occurrence === 1 ? 'first' : 'second'})` : '';
        heading += ` ${slot.time}${partial ? '–Now' : end !== 'N/A' ? `–${end}` : ''}${repeat}`;
      } else if (!this.layout.hourly && slot.day !== 'N/A') {
        heading += ` ${ReportView.calendarCaption(slot.day, 'weekday')}`;
      }
      const state = [future && 'Upcoming', this.nonWorking.has(index) && 'Swedish non-working day'].filter(Boolean).join(' · ');
      const values = [], rows = [];
      for (const item of this.series) {
        const point = item.points[index];
        const value = point ? shown(point).replace(/^[~≈]/, '') : '—';
        if (future) continue;
        const name = item.account, row = e('div', undefined, 'account-timeline-tip-row');
        const text = e('span', name, 'account-timeline-tip-name');
        text.title = name;
        row.append(swatch(this.colors.get(item.id)), text, e('span', value));
        rows.push(row);
        values.push(`${name}: ${value}`);
      }
      ReportView.text(this.tipTitle, heading);
      ReportView.text(this.tipState, state);
      if (this.tipValues.hidden || !rows.length) this.tipValues.scrollTop = 0;
      this.tipValues.hidden = !rows.length;
      this.tipValues.replaceChildren(...rows);
      this.positionTip();
      if (announce) ReportView.text(this.announce, [heading, state, ...values].filter(Boolean).join('. '));
    }

    positionOverlays() {
      if (!this.visible) return;
      this.positionTip();
      if (!this.panel.matches(':popover-open')) return;
      const anchor = this.chooser.getBoundingClientRect(), screen = viewport();
      const belowTop = Math.max(screen.top, anchor.bottom + 6);
      const aboveBottom = Math.min(screen.bottom, anchor.top - 6);
      const below = screen.bottom - belowTop, above = aboveBottom - screen.top;
      const openBelow = below >= 140 || below >= above;
      this.panel.style.maxHeight = `${Math.max(0, Math.min(360, openBelow ? below : above))}px`;
      this.panel.style.maxWidth = `${screen.right - screen.left}px`;
      this.panel.style.left = `${clamp(anchor.right - this.panel.offsetWidth, screen.left, screen.right - this.panel.offsetWidth)}px`;
      this.panel.style.top = `${openBelow ? belowTop : aboveBottom - this.panel.offsetHeight}px`;
    }
    positionTip() {
      const index = this.indexOf(this.shownKey);
      if (index === undefined || this.frame.hidden) return;
      const cell = this.targets.children[index].getBoundingClientRect();
      const clip = this.scroller.getBoundingClientRect(), frame = this.frame.getBoundingClientRect(), screen = viewport();
      const left = Math.max(screen.left, clip.left, cell.left), right = Math.min(screen.right, clip.right, cell.right);
      this.tooltip.hidden = right <= left || cell.bottom <= screen.top || cell.top >= screen.bottom;
      if (this.tooltip.hidden) return;
      const low = Math.max(screen.left, clip.left), high = Math.min(screen.right, frame.right);
      this.tooltip.style.setProperty('--tip-room', `${high - low}px`);
      this.tipValues.style.maxHeight = `${Math.max(28, Math.min(140, screen.bottom - screen.top - 60))}px`;
      const width = this.tooltip.offsetWidth, height = this.tooltip.offsetHeight;
      // Keep the controls and ticks clear. Prefer the space beside the
      // inspected slot so that its bars and loading cue remain visible.
      const anchor = right + 6 + width <= high ? right + 6 : left - 6 - width;
      const x = clamp(anchor, low, high - width);
      const y = clamp(frame.top + 8, screen.top, Math.min(screen.bottom, cell.bottom - 23) - height);
      this.tooltip.style.left = `${x}px`;
      this.tooltip.style.top = `${y}px`;
    }
  }
  return {View, visibleScale};
})();
