'use strict';
const AccountTimelineView = (() => {
  const periods = [['today', 'Today'], ['7-days', '7 days'], ['30-days', '30 days'],
    ['month', 'This month']];
  const e = (...args) => ReportView.element(...args);
  const ns = 'http://www.w3.org/2000/svg';
  const top = 27, bottom = 194, inset = 3, paletteSize = 12;
  const labelBaseline = 214, weekdayLineHeight = 14, shadeTop = 4;
  const {DATE, TIME} = ReportView.DateTimeMode;
  const shown = item => ReportView.display({
    display: {amount: item.display.credits},
    display_units: {usd: {amount: item.display.usd}}
  }, 'amount');
  function discrepancyHelp(item) {
    if (!item.discrepancy_comparable) return '';
    const provider = shown(item.month_total), observed = shown(item.observed_total);
    if (provider === observed) return '';
    return `Provider-reported monthly usage: ${provider}\nOpenCode-observed CCost: ${observed}\n\n` +
      'OpenCode counts only the usage it observes, valued at reference prices. ' +
      'Provider coverage, attribution, pricing or reporting windows can differ.';
  }
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
    const minimum = view.period === 'today' ? 33 : view.period === '7-days' ? 76 : 25;
    return 2 * inset + view.buckets.length * minimum;
  }
  function overlayWidth(base, rank, count) {
    if (rank === 0) return base;
    // Leave clear edges for small groups, then share the width above the floor.
    const floor = 2;
    const step = Math.min(4, (base - floor) / (count - 1));
    return Math.max(floor, base - rank * step);
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
    const crossYear = years.size > 1;
    const extraLabelSpace = shortDates ? weekdayLineHeight : 0;
    const axis = {
      monthBaseline: 236 + extraLabelSpace,
      yearBaseline: 250 + extraLabelSpace,
      dividerHeight: (crossYear ? 51 : 38) + extraLabelSpace,
      highlightHeight: 221 - shadeTop + extraLabelSpace,
      targetHeight: bottom + 25 + extraLabelSpace,
      plotHeight: (hourly ? 230 : crossYear ? 258 : 244) + extraLabelSpace
    };
    return {slots, width, group, hourly, shortDates, months, crossYear, axis};
  }
  function equalSlots(a, b) {
    return a && b && a.period === b.period && a.timezone_id === b.timezone_id &&
      a.buckets.length === b.buckets.length && b.buckets.every(([start], i) => a.buckets[i][0] === start);
  }
  function rangeLabel(view, layout) {
    const mode = layout.hourly ? ReportView.DateTimeMode.DATE_TIME : DATE;
    const start = ReportView.formatDateTime(view.start_ms, mode, view.timezone_id);
    const end = ReportView.formatDateTime(view.end_ms, layout.hourly ? TIME : ReportView.DateTimeMode.DATE_TIME,
      view.timezone_id);
    if (start === 'N/A' || end === 'N/A') return '—';
    if (layout.hourly) {
      const occurrence = view.end_occurrence ? ` (${view.end_occurrence === 1 ? 'first' : 'second'})` : '';
      return `${start}–${end}${occurrence}`;
    }
    return `${start} – ${end}`;
  }
  function axisLabels(layout, future, nonWorking) {
    const {slots, hourly, shortDates, months, group, crossYear, axis} = layout;
    const labels = [];
    for (const slot of slots) {
      const tick = hourly ? slot.time?.slice(0, 2) : Number(slot.day.slice(8));
      const attrs = {x: slot.center, 'data-bucket': slot.index, 'data-future': future.has(slot.index),
        'text-anchor': 'middle'};
      const node = svg('text', {...attrs, y: labelBaseline, class: 'account-timeline-slot-label'},
        slot.day === 'N/A' ? '—' : undefined);
      if (slot.day !== 'N/A') {
        if (nonWorking.has(slot.index)) node.append(svg('tspan', {class: 'account-timeline-non-working'}, tick));
        else node.textContent = tick;
        if (shortDates) node.append(`/${Number(slot.day.slice(5, 7))}`);
      }
      if (slot.occurrence) node.append(svg('tspan', {class: 'account-timeline-fold'}, slot.occurrence === 1 ? '¹' : '²'));
      labels.push(node);
      if (shortDates && slot.day !== 'N/A') {
        labels.push(svg('text', {...attrs, y: labelBaseline + weekdayLineHeight, class: 'account-timeline-weekday'},
          ReportView.calendarCaption(slot.day, 'weekday')));
      }
    }
    months.forEach(({month, x, count}, index) => {
      const width = group * count;
      const [year, number] = month.split('-').map(Number);
      if (!year || !number) return;
      const caption = ReportView.calendarCaption(`${month}-01`, width < 85 ? 'month-short' : 'month-long',
        document.documentElement.lang || 'en');
      if (index) labels.push(svg('rect', {x: x - .5, y: bottom + 6, width: 1, height: axis.dividerHeight,
        class: 'account-timeline-month-divider'}));
      const attrs = {x: x + width / 2, 'text-anchor': 'middle', class: 'account-timeline-month-label'};
      labels.push(svg('text', {...attrs, y: axis.monthBaseline}, caption));
      if (crossYear) labels.push(svg('text', {...attrs, y: axis.yearBaseline}, year));
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
      this.legendEntries = new Map();
      this.selected = new Map();
      this.colors = new Map();
      this.generation = 0;
      this.readFailed = false;
      this.selectionRead = null;
      this.width = 0;
      this.root = e('section', undefined, 'account-timeline');
      const title = e('h2'), id = 'account-timeline-title';
      title.append(ContextHelp.button('CCost',
        ReportView.ccostHelp('Observed reference cost by account and period. Provider-native totals are separate.')));
      title.id = id;
      this.root.setAttribute('aria-labelledby', id);
      const filters = e('div', undefined, 'ai-stats-periods');
      filters.setAttribute('role', 'group');
      filters.setAttribute('aria-label', 'Usage period');
      this.buttons = periods.map(([period, text]) => {
        const button = e('button', text);
        button.type = 'button';
        if (typeof PeriodHelp !== 'undefined') PeriodHelp.attach(button, period);
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
      this.highlight = svg('rect', {class: 'account-timeline-highlight', y: shadeTop,
        rx: 4, visibility: 'hidden', 'aria-hidden': 'true'});
      this.layers = svg('g', {'aria-hidden': 'true'});
      this.labels = svg('g', {'aria-hidden': 'true'});
      this.targets = svg('g', {'aria-hidden': 'true'});
      this.plot.append(this.shades, this.highlight, this.layers, this.labels, this.targets);
      this.scroller.append(this.plot);
      this.range = e('p', undefined, 'account-timeline-range');
      this.savedView = e('p', 'Saved view', 'account-timeline-saved');
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
      this.frame.append(this.axis, this.scroller, this.range, this.savedView, this.selectedLegend, this.tooltip);
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
      this.readFailed = false;
      this.selectionRead = null;
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
      if (this.period === period && !this.readFailed) return;
      ReportLoading.beginHistorySelection(this, this.buttons.find(([id]) => id === period)?.[1]);
      this.retireRead();
      this.period = period;
      this.generation++;
      this.working = false;
      this.readFailed = false;
      this.selectionRead = {retried: false};
      this.focusKey = null;
      const cached = this.cache.get(period)?.view;
      this.initial = !cached || !!cached.initial_pending_buckets?.length;
      this.inspect(null);
      this.draw();
      this.scroller.scrollLeft = 0;
      this.refresh();
      this.changeDemand();
    }

    active(value) {
      if (value === this.visible) return;
      this.visible = value;
      this.generation++;
      this.working = false;
      this.readFailed = false;
      this.selectionRead = null;
      if (value) {
        const view = this.cache.get(this.period)?.view;
        this.initial = !view || !!view.initial_pending_buckets?.length;
        this.draw();
      } else {
        ReportLoading.endHistorySelection(this);
        this.retireRead();
        this.panel.hidePopover();
        this.inspect(null);
        for (const {amount} of this.legendEntries.values()) ContextHelp.dismiss(amount);
        this.draw();
      }
      this.schedule(0);
    }

    retireRead() {
      this.pending?.abort();
      this.pending = null;
      this.cachePending = false;
      clearTimeout(this.timer);
    }

    schedule(delay) {
      clearTimeout(this.timer);
      if (this.visible && !this.pending) this.timer = setTimeout(() => this.refresh(), delay);
    }

  wake(hint, reconnected) {
      if (!this.cacheEvents || !this.visible || hint === this.cacheHint && !reconnected) return;
      this.cacheHint = hint;
      if (this.pending) this.cachePending = true;
      else this.schedule(0);
    }

    catchUp() {
      if (!this.visible) return;
      if (this.selectionRead) {
        this.cachePending = true;
        this.schedule(0);
        return;
      }
      this.retireRead();
      this.refresh();
    }

    async refresh() {
      if (!this.visible || this.pending) return;
      const period = this.period, revision = this.cache.get(period)?.revision ?? null;
      const generation = this.generation, selection = this.selectionRead;
      const request = new AbortController();
      this.pending = request;
      let retry = false;
      try {
        let value;
        try {
          value = await this.api('/api/accounts/timeline', {period, revision}, request.signal);
        } catch (error) {
          if (this.pending !== request || generation !== this.generation || request.signal.aborted) return;
          const working = this.working;
          this.working = false;
          if (selection) {
            // The API's own timeout aborts the fetch, not this selection's signal.
            const recoverable = error?.retryable === true || ['TypeError', 'AbortError'].includes(error?.name) ||
              ['busy', 'source_starting'].includes(error?.message);
            retry = recoverable && !selection.retried;
            if (retry) selection.retried = true;
            else {
              this.selectionRead = null;
              this.readFailed = true;
              ReportLoading.endHistorySelection(this);
            }
          }
          // Host health owns unattended read failures; don't turn them into selection errors.
          if (working || this.readFailed && selection) this.draw();
          return;
        }
        if (this.pending !== request || request.signal.aborted || generation !== this.generation) return;
        const terminalChanged = this.terminal !== (value.terminal === true);
        this.terminal = value.terminal === true;
        if (value.scope !== this.scope) {
          if (!this.sharedHistory) return;
          this.setScope(value.scope);
        }
        const recovered = this.readFailed;
        this.readFailed = false;
        this.selectionRead = null;
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
          this.cache.set(period, {revision: value.revision, view, shown, restored: value.restored === true});
          this.roster = value.view.series;
          this.draw();
        } else if (!value.unchanged) {
          const prior = this.cache.delete(period);
          const empty = value.ready && !value.series.length;
          if (empty || prior) this.initial = !empty;
          if (prior || empty || activityChanged || terminalChanged || recovered || this.rosterRevision !== value.revision) {
            this.rosterRevision = value.revision;
            this.roster = value.series;
            this.draw();
          }
        } else if (activityChanged || terminalChanged || recovered) this.draw();
      } finally {
        if (this.pending === request) {
          this.pending = null;
          if (generation !== this.generation || this.cachePending) this.schedule(0);
          // One error-driven retry, not a new poll when cache events are enabled.
          else if (retry) this.schedule(350);
          else if (!this.cacheEvents) this.schedule(this.initial ? 350 : 1500);
          this.cachePending = false;
        }
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

    drawLegend() {
      const selected = new Set(this.series.map(item => item.id));
      for (const [id, {row, amount}] of this.legendEntries) {
        if (selected.has(id)) continue;
        ContextHelp.dismiss(amount);
        row.remove();
        this.legendEntries.delete(id);
      }
      this.series.forEach((item, index) => {
        let entry = this.legendEntries.get(item.id);
        if (!entry) {
          const row = e('li'), name = e('span');
          const amount = e('span', undefined, 'account-timeline-legend-value');
          row.append(swatch(this.colors.get(item.id)), name, amount);
          entry = {row, name, amount};
          this.legendEntries.set(item.id, entry);
        }
        const {row, name, amount} = entry;
        ReportView.text(name, item.account);
        ReportView.text(amount, item.total ? shown(item.total) : '—');
        const help = discrepancyHelp(item);
        if (entry.help !== help) {
          if (help) ContextHelp.value(amount, help);
          else ContextHelp.clearValue(amount);
          entry.help = help;
        }
        if (this.selectedLegend.children[index] !== row)
          this.selectedLegend.insertBefore(row, this.selectedLegend.children[index] || null);
      });
    }

    draw() {
      const cached = this.cache.get(this.period);
      const view = cached?.view;
      const previous = this.view;
      const roster = view?.series || this.roster || [];
      this.buttons.forEach(([id, button]) => button.setAttribute('aria-pressed', String(id === this.period)));
      if (typeof ReportLoading !== 'undefined')
        ReportLoading.historyProgress(this, this.buttons.find(([id]) => id === this.period)?.[1],
           !this.visible ? undefined : this.terminal ? {terminal: true} :
              this.readFailed ? {terminal: true, error: 'Could not load CCost for this period. Select it again to retry.'} :
                view?.history_progress ?? (this.sharedHistory && !view ? {complete: false} : undefined));
      this.legendFor(roster);
      const selectedSeries = roster.filter(item => this.selected.get(item.id) ?? true);
      this.series = view ? selectedSeries : [];
      this.selectedLegend.hidden = !view || !selectedSeries.length;
      this.drawLegend();
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
      this.savedView.hidden = !!unselected || !cached?.restored;
      ReportView.text(this.range, `Range: ${rangeLabel(view, layout)}`);
      if (!sameGeometry) {
        const {plotHeight, targetHeight, highlightHeight} = layout.axis;
        this.plot.style.setProperty('--timeline-min-width', `${minimum}px`);
        this.plot.setAttribute('viewBox', `0 0 ${layout.width} ${plotHeight}`);
        this.plot.setAttribute('height', plotHeight);
        // Native hit testing is already in actual SVG coordinates, including
        // scroll, CSS zoom and transforms. Bars cannot be hit targets.
        this.targets.replaceChildren(...slots.map(({index, x}) => svg('rect', {
          class: 'account-timeline-target', x, y: 0, width: group, height: targetHeight, 'data-slot': index
        })));
        this.highlight.setAttribute('width', group - 2);
        this.highlight.setAttribute('height', highlightHeight);
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
        for (const [rank, item] of overlays.entries()) {
          const width = overlayWidth(bar, rank, overlays.length);
          const height = Math.max(1, (bottom - top) * Number(item.points[index].amount) / max);
          nodes.push(svg('rect', {x: center - width / 2, y: bottom - height, width, height,
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
