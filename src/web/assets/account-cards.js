'use strict';
// Shared Watch/Accounts presentation over the one application-owned Live observation.
const AccountCards = (() => {
  const el = (...args) => ReportView.element(...args);
  const display = (row, key) => ReportView.display(row, key);
  // This flag comes from the existing normalized native-period calculation.
  // Missing period evidence is unknown, not proof of a native monthly window.
  const monthlyApplicable = quota => quota.ccost_reference?.monthly_applicable !== false;
  const gridRow = (node, row) => node.style.setProperty('grid-row', String(row));
  function physicalWidth(root, resized) {
    let resolution;
    const update = () => {
      const ratio = window.devicePixelRatio || 1;
      const scale = ratio * (window.visualViewport?.scale || 1);
      root.style.setProperty('--watch-account-width', Math.floor(448 / scale) + 'px');
      resized(); // Row membership can change even if the grid's outer size does not.
      resolution?.removeEventListener('change', update);
      resolution = window.matchMedia(`(resolution: ${ratio}dppx)`);
      resolution.addEventListener('change', update);
    };
    window.addEventListener('resize', update);
    window.visualViewport?.addEventListener('resize', update);
    update();
  }
  function quotaTrack(value, current) {
    const quota = () => value().quota, view = () => ReportView.quotaView(quota(), value());
    const amount = monthly => !monthly && quota().unlimited ? 'Unlimited' :
      current() && ReportView.capacityKnown(quota(), monthly) ? display(quota(), monthly ? 'monthly_capacity' : 'ccost_capacity') : '?';
    const help = monthly => current() ? ReportView.quotaCapacityHelp(quota(), monthly) :
      'Reference CCost unavailable for a stale or unavailable observation.';
    const summary = () => quota().unlimited ? 'Unlimited' : view().percent === '—' ? '—' : view().percent + ' ' + view().mode;
    const label = el('div'); label.append(ContextHelp.value(el('span', () => `${ReportView.quotaLabel(quota())} · ${summary()}`),
      () => ReportView.quotaUsageHelp(quota()) + (current() ? '' : '\nQuota observation is stale or unavailable.')));
    ReportView.bind(label, () => label.className = 'watch-quota-summary metric-value' + (view().exhausted ? ' watch-quota-exhausted' : ''));
    label.append(ReportView.estimateValue(el('span', () => ` (${display(quota(), 'ccost_' + view().mode)})`, 'watch-period-cost'),
      quota, () => 'ccost_' + view().mode));
    const capacity = el('div', undefined, 'watch-quota-capacity metric-value');
    capacity.append(ContextHelp.value(el('span', () => {
      const label = display(quota(), 'capacity_label');
      return (label === 'N/A' ? 'Capacity' : label) + ': ' + amount(false);
    }), () => help(false)));
    const monthly = el('div', undefined, 'watch-monthly-capacity metric-value');
    monthly.append(ContextHelp.value(el('span', () => 'Monthly Capacity: ' + amount(true)), () => help(true)));
    const spacer = el('div', undefined, 'watch-capacity-spacer'); spacer.setAttribute('aria-hidden', 'true');
    if (quota().quota_display?.used.note || quota().quota_display?.remaining.note)
      label.append(el('span', () => view().note ? ' · ' + view().note : '', 'warning'));
    const track = el('div', undefined, 'watch-quota-track');
    if (!quota().unlimited && value().used_fraction != null) {
      const bar = el('progress'); bar.max = 1;
      ReportView.bind(bar, () => {
        bar.value = view().fraction;
        bar.setAttribute('aria-label', ReportView.quotaLabel(quota()) + ' ' + view().mode);
        bar.setAttribute('aria-valuetext', summary() + (view().exhausted ? ' · exhausted' : ''));
        bar.className = view().exhausted ? 'watch-quota-exhausted' : '';
      });
      track.append(bar);
    } else track.append(el('span', () => quota().unlimited ? 'No usage limit' : 'Usage unavailable', 'detail'));
    return {
      nodes: [label, capacity, ...(monthlyApplicable(quota()) ? [monthly] : []), track],
      align(row, extra) {
        gridRow(label, row++); gridRow(capacity, row++);
        const slot = monthlyApplicable(quota()) ? monthly : extra ? spacer : null;
        for (const node of [monthly, spacer]) {
          if (node === slot) {
            if (node.parentNode !== track.parentNode) track.parentNode.insertBefore(node, track);
            gridRow(node, row); ReportView.syncUnits(node);
          } else if (node.parentNode) node.remove();
        }
        if (extra) row++;
        gridRow(track, row++);
        return row;
      }
    };
  }
  function quotaDetails(parent, value) {
    const reset = el('p', undefined, 'detail'), clock = el('span', () => display(value(), 'watch_reset')); reset.append(clock);
    if (value().quota.reset_at_ms != null) ContextHelp.value(clock, () => display(value().quota, 'reset_at_ms'));
    parent.append(reset);
    const pace = () => value().quota.ccost_pace;
    const day = el('p', undefined, 'detail'), workday = el('p', undefined, 'detail');
    day.append(ReportView.estimateValue(el('span', () => `Remaining: ${display(pace(), 'ccost_per_day')}/day`),
      pace, () => 'ccost_per_day'));
    workday.append(ReportView.estimateValue(el('span', () => pace()?.workdays === 0 ? 'Remaining: no workdays left' :
      `Remaining: ${display(pace(), 'ccost_per_workday')}/workday`), pace, () => 'ccost_per_workday'));
    ReportView.bind(parent, () => {
      if (pace() && day.parentNode !== parent) {
        parent.insertBefore(day, parent.children[1] || null); parent.insertBefore(workday, parent.children[2] || null);
      } else if (!pace()) { day.remove(); workday.remove(); }
    });
    if (value().restricted) parent.append(el('p', () => ReportView.quotaLabel(value().quota) + ' · Provider restriction reported', 'warning'));
  }
  function warnings(item, quiet) {
    const obs = item.observation;
    const cause = {auth_failure: 'Authentication unavailable', transport_failure: 'Connection failed',
      unsupported_auth_method: 'Unsupported authentication method', format_changed: 'Provider format changed',
      software_failure: 'Account refresh failed', discovery_failure: 'Account metadata unavailable',
      rate_limited: 'Rate limited', account_unavailable: 'Account unavailable'}[obs.error_code];
    const state = {partial: 'Partial quota data', stale: 'Stale · last observation, not current',
      unavailable: 'Quota unavailable', error: 'Refresh failed'}[obs.availability];
    const actionable = ['auth_failure', 'unsupported_auth_method', 'format_changed', 'rate_limited', 'account_unavailable'].includes(obs.error_code);
    const status = actionable || !quiet ? [state, cause].filter(Boolean).join(' · ') : '';
    return [[status, 'warning'],
      [obs.status === 'blocked' && ![item.primary, ...item.secondary].some(q => q.exhausted || q.restricted) ?
        'Provider restriction reported; utilization not established' : '', 'warning'],
      [obs.has_warning ? 'Provider warning' : '', 'warning'],
      [item.ccost_account_unknown ? 'CCost account attribution unavailable' : '', 'detail']].filter(([text]) => text);
  }
  class Subscription {
    constructor() {
      this.root = el('section', undefined, 'account-card watch-subscription');
    }
    align(extras, rows) {
      let row = 3; // Account heading and Today precede the ordered quota slots.
      this.levels.forEach((level, index) => {
        if (level.divider) gridRow(level.divider, row++);
        row = level.track.align(row, extras[index]);
        gridRow(level.details, row++);
      });
      gridRow(this.warningLines, rows);
      this.root.style.setProperty('--watch-card-rows', String(rows));
    }
    draw() {
      const item = () => this.value;
      ReportView.bind(this.root, () => {
        this.root.dataset.availability = item().observation.availability;
        this.root.dataset.exhausted = String([item().primary, ...item().secondary].some(q => ReportView.quotaView(q.quota, q).exhausted));
      });
      const cost = el('p', undefined, 'metric-value');
      cost.append(ContextHelp.value(el('span', () => {
        const today = item().ccost_scopes.find(scope => scope.name === 'today');
        return `CCost Today: ${today?.cost == null ? '—' : display(today.cost, 'account_ccost')}`;
      }), () => 'This account’s reference cost in your configured local day.' + (item().today_note ? '\n' + item().today_note : '')));
      const primary = el('div', undefined, 'watch-primary-details');
      quotaDetails(primary, () => item().primary);
      const track = quotaTrack(() => item().primary, () => this.capacityCurrent);
      this.levels = [{track, details: primary}];
      this.lower = el('div', undefined, 'watch-account-footer');
      this.warningLines = el('div', undefined, 'watch-account-warnings');
      const secondary = el('div', undefined, 'watch-account-details');
      item().secondary.forEach((_, index) => {
        const value = () => item().secondary[index], group = el('div', undefined, 'watch-secondary-quota');
        const track = quotaTrack(value, () => this.capacityCurrent), divider = el('div', undefined, 'watch-quota-divider');
        divider.setAttribute('aria-hidden', 'true');
        const details = el('div', undefined, 'watch-secondary-details'); quotaDetails(details, value);
        group.append(divider, ...track.nodes, details); secondary.append(group);
        this.levels.push({track, divider, details});
      });
      if (item().secondary.length) this.lower.append(secondary);
      this.root.replaceChildren(ReportView.accountHeading(() => item().observation), cost, ...track.nodes, primary);
      this.warningSignature = null;
    }
    update(value, stale) {
      const obs = value.observation;
      if (obs.observed_at_ms != null && obs.observed_at_ms !== this.lastObserved)
        this.partialObservation = obs.availability === 'partial' && !stale;
      const usable = !stale && (obs.availability === 'available' || this.partialObservation);
      this.capacityCurrent = usable;
      const quiet = (this.verified || [value.primary, ...value.secondary].some(q =>
        q.used_fraction != null || q.quota.unlimited)) && !this.partialObservation;
      const lines = warnings(value, quiet);
      if (!usable && this.value && ![value.primary, ...value.secondary].some(q => q.restricted || q.exhausted)) {
        // Keep observed figures quietly, but never retain a stale forward budget.
        const observed = q => ({...q, quota:{...q.quota, ccost_pace:null}});
        value = {...this.value, observation: obs, primary:observed(this.value.primary), secondary:this.value.secondary.map(observed)};
      }
      if (usable) { this.lastObserved = obs.observed_at_ms; if (obs.availability === 'available') this.verified = true; }
      const signature = JSON.stringify([value, lines, usable]);
      if (signature === this.signature) return;
      this.value = value;
      // Only actual track/slot changes rebuild card contents. Ordinary values,
      // reset clocks, warnings and settings update bound nodes and active help.
      const shape = JSON.stringify([value.primary, ...value.secondary].map(q => [q.quota.unlimited, q.used_fraction != null,
        q.quota.reset_at_ms != null, q.restricted,
        Boolean(q.quota.quota_display?.used.note || q.quota.quota_display?.remaining.note)]));
      if (shape !== this.shape) { this.draw(); this.shape = shape; }
      const warningSignature = JSON.stringify(lines);
      if (warningSignature !== this.warningSignature) {
        this.warningLines.replaceChildren(...lines.map(([text, role]) => el('p', text, role)));
        if (lines.length) this.lower.append(this.warningLines);
        else this.warningLines.remove();
        if (this.lower.children.length) this.root.append(this.lower);
        else this.lower.remove();
        this.warningSignature = warningSignature;
      }
      ReportView.syncUnits(this.root);
      this.signature = signature;
    }
  }
  class View {
    constructor(showLoading = false) {
      this.showLoading = showLoading;
      this.root = el('div', undefined, 'live-account-cards');
      this.cards = new Map();
      this.message = el('p'); this.message.setAttribute('role', 'status');
      this.grid = el('div', undefined, 'account-grid watch-account-grid');
      if (typeof ResizeObserver !== 'undefined') new ResizeObserver(() => this.align()).observe(this.grid);
      physicalWidth(this.root, () => this.align());
      this.update({});
    }
    attach(parent) {
      if (this.root.parentNode !== parent) {
        ReportView.syncUnits(this.root);
        parent.replaceChildren(this.root);
        this.align();
      }
    }
    align() {
      // Share semantic slots at every ordinal, within this physical comparison row.
      const template = typeof getComputedStyle === 'function' ? getComputedStyle(this.grid).gridTemplateColumns : '';
      const columns = template && template !== 'none' ? template.trim().split(/\s+/).length : this.cards.size || 1;
      const cards = [...this.cards.values()];
      for (let index = 0; index < cards.length; index += columns) {
        const peers = cards.slice(index, index + columns);
        const quotas = peers.map(card => [card.value.primary, ...card.value.secondary]);
        const count = Math.max(...quotas.map(levels => levels.length));
        const extras = Array.from({length: count}, (_, level) => quotas.some(levels =>
          levels[level] && monthlyApplicable(levels[level].quota)));
        // Each real level: summary, Capacity, optional monthly, track, details;
        // each subsequent level also has a divider. Missing tails stay empty grid
        // cells, with no phantom DOM, semantics or maximum quota-count assumption.
        const rows = 2 + extras.reduce((sum, extra, level) => sum + 4 + Number(extra) + Number(level > 0), 0) + 1;
        for (const card of peers) card.align(extras, rows);
      }
    }
    update(view) {
      const failed = view.quota_stale || view.quota_recovering_count > 0;
      // Missing publication is pending, not an observed empty population. A
      // failed empty read must not erase the last usable common observation.
      if (view.accounts && (view.accounts.accounts.length || !failed)) {
        const wanted = [], keep = new Set();
        for (const item of view.accounts.accounts) {
          const key = JSON.stringify([item.observation.provider_id, item.observation.id]); keep.add(key);
          if (!this.cards.has(key)) this.cards.set(key, new Subscription());
          const card = this.cards.get(key); card.update(item, view.quota_stale); wanted.push(card.root);
        }
        for (const key of this.cards.keys()) if (!keep.has(key)) this.cards.delete(key);
        // Keep responsive row membership in publication order, including reorders.
        this.cards = new Map(view.accounts.accounts.map(item => {
          const key = JSON.stringify([item.observation.provider_id, item.observation.id]); return [key, this.cards.get(key)];
        }));
        for (const node of [...this.grid.children]) if (!wanted.includes(node)) node.remove();
        wanted.forEach((node, index) => {
          if (this.grid.children[index] !== node) this.grid.insertBefore(node, this.grid.children[index] || null);
        });
        this.observed = true;
      }
      const missing = failed && !view.accounts?.accounts.length;
      const message = missing && !this.observed ? 'Accounts unavailable; retrying.' :
        this.observed && !this.cards.size ? 'No configured accounts detected.' : !this.observed && this.showLoading ? 'Loading accounts…' : '';
      ReportView.text(this.message, message);
      // Keep the healthy view grid-only and preserve its DOM through health updates.
      if (this.cards.size && this.grid.parentNode !== this.root) this.root.append(this.grid);
      if (!this.cards.size) this.grid.remove();
      if (message && this.message.parentNode !== this.root) this.root.append(this.message);
      if (!message) this.message.remove();
      this.align();
    }
  }
  return {View};
})();
