'use strict';
// Shared Watch/Accounts presentation over the one application-owned Live observation.
const AccountCards = (() => {
  const el = (...args) => ReportView.element(...args);
  const display = (row, key) => ReportView.display(row, key);
  function physicalWidth(root) {
    let resolution;
    const update = () => {
      const ratio = window.devicePixelRatio || 1;
      const scale = ratio * (window.visualViewport?.scale || 1);
      root.style.setProperty('--watch-account-width', Math.floor(448 / scale) + 'px');
      resolution?.removeEventListener('change', update);
      resolution = window.matchMedia(`(resolution: ${ratio}dppx)`);
      resolution.addEventListener('change', update);
    };
    window.addEventListener('resize', update);
    window.visualViewport?.addEventListener('resize', update);
    update();
  }
  function quotaTrack(value) {
    const quota = () => value().quota, view = () => ReportView.quotaView(quota(), value());
    const summary = () => quota().unlimited ? 'Unlimited' : view().percent === '—' ? '—' : view().percent + ' ' + view().mode;
    const label = el('div'); label.append(el('span', () => `${quota().label} · ${summary()}`));
    ReportView.bind(label, () => label.className = 'watch-quota-summary metric-value' + (view().exhausted ? ' watch-quota-exhausted' : ''));
    label.append(el('span', () => ` (${display(quota(), 'ccost_' + view().mode)})`, 'watch-period-cost'));
    const capacity = el('div', undefined, 'watch-quota-capacity metric-value');
    capacity.append(ContextHelp.value(el('span', () => display(quota(), 'capacity_label') + ': ' + display(quota(), 'ccost_capacity')), () => ReportView.quotaHelp(quota())));
    const monthly = display(quota(), 'monthly_capacity') ? el('div',
      () => 'Monthly Capacity: ' + display(quota(), 'monthly_capacity'), 'watch-monthly-capacity metric-value') : null;
    if (quota().quota_display?.used.note || quota().quota_display?.remaining.note)
      label.append(el('span', () => view().note ? ' · ' + view().note : '', 'warning'));
    const track = el('div', undefined, 'watch-quota-track');
    if (!quota().unlimited && value().used_fraction != null) {
      const bar = el('progress'); bar.max = 1;
      ReportView.bind(bar, () => {
        bar.value = view().fraction;
        bar.setAttribute('aria-label', quota().label + ' ' + view().mode);
        bar.setAttribute('aria-valuetext', summary() + (view().exhausted ? ' · exhausted' : ''));
        bar.className = view().exhausted ? 'watch-quota-exhausted' : '';
      });
      track.append(bar);
    } else track.append(el('span', () => quota().unlimited ? 'No usage limit' : 'Usage unavailable', 'detail'));
    return [label, capacity, ...(monthly ? [monthly] : []), track];
  }
  function quotaDetails(parent, value) {
    const reset = el('p', undefined, 'detail'), clock = el('span', () => display(value(), 'watch_reset')); reset.append(clock);
    if (value().quota.reset_at_ms != null) ContextHelp.value(clock, () => display(value().quota, 'reset_at_ms'));
    parent.append(reset);
    if (value().pace) {
      parent.append(el('p', () => `Remaining: ${display(value().pace, 'per_day')}/day`, 'detail'));
      parent.append(el('p', () => value().pace.workdays === 0 ? 'Remaining: no workdays left' :
        `Remaining: ${display(value().pace, 'per_workday')}/workday`, 'detail'));
    }
    if (value().restricted) parent.append(el('p', () => value().quota.label + ' · Provider restriction reported', 'warning'));
  }
  function warnings(item, quiet, late) {
    const obs = item.observation;
    const cause = {auth_failure: 'Authentication unavailable', transport_failure: 'Connection failed',
      unsupported_auth_method: 'Unsupported authentication method', format_changed: 'Provider format changed',
      software_failure: 'Account refresh failed', discovery_failure: 'Account metadata unavailable',
      rate_limited: 'Rate limited', account_unavailable: 'Account unavailable'}[obs.error_code];
    const state = {partial: 'Partial quota data', stale: 'Stale · last observation, not current',
      unavailable: 'Quota unavailable', error: 'Refresh failed'}[obs.availability];
    const actionable = ['auth_failure', 'unsupported_auth_method', 'format_changed', 'rate_limited', 'account_unavailable'].includes(obs.error_code);
    const status = actionable || !quiet ? [state, cause].filter(Boolean).join(' · ') : late ? 'Updates delayed · showing last values' : '';
    return [[status, 'warning'],
      [obs.status === 'blocked' && ![item.primary, ...item.secondary].some(q => q.exhausted || q.restricted) ?
        'Provider restriction reported; utilization not established' : '', 'warning'],
      [obs.has_warning ? 'Provider warning' : '', 'warning'],
      [item.ccost_account_unknown ? 'CCost account attribution unavailable' : '', 'detail']].filter(([text]) => text);
  }
  class Subscription {
    constructor() {
      this.root = el('section', undefined, 'account-card watch-subscription');
      this.status = new ReportView.LiveStatus();
      this.spacer = el('div', undefined, 'watch-capacity-spacer'); this.spacer.setAttribute('aria-hidden', 'true');
    }
    align(extra) {
      const monthly = !display(this.value.primary.quota, 'monthly_capacity');
      if (extra && monthly && this.spacer.parentNode !== this.root) this.root.insertBefore(this.spacer, this.primaryTrack);
      if ((!extra || !monthly) && this.spacer.parentNode) this.spacer.remove();
      this.root.style.setProperty('--watch-card-rows', extra ? '8' : '7');
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
      this.lower = el('div', undefined, 'watch-account-footer');
      const secondary = el('div', undefined, 'watch-account-details');
      item().secondary.forEach((_, index) => {
        const value = () => item().secondary[index], group = el('div', undefined, 'watch-secondary-quota');
        group.append(...quotaTrack(value)); quotaDetails(group, value); secondary.append(group);
      });
      if (item().secondary.length) this.lower.append(secondary);
      const track = quotaTrack(() => item().primary); this.primaryTrack = track.at(-1);
      this.root.replaceChildren(el('h4', () => item().observation.label), cost, ...track, primary);
      this.warningSignature = null;
    }
    update(value, stale) {
      const obs = value.observation;
      if (obs.observed_at_ms != null && obs.observed_at_ms !== this.lastObserved)
        this.partialObservation = obs.availability === 'partial' && !stale;
      const usable = !stale && (obs.availability === 'available' || this.partialObservation);
      const late = this.status.update(usable, obs.observed_at_ms);
      const quiet = this.verified && !this.partialObservation &&
        (value.primary.used_fraction != null || value.primary.quota.unlimited);
      const lines = warnings(value, quiet, late);
      this.sourceNotice = late || (!quiet && obs.availability !== 'available');
      if (usable) { this.lastObserved = obs.observed_at_ms; if (obs.availability === 'available') this.verified = true; }
      const signature = JSON.stringify([value, lines]);
      if (signature === this.signature) return;
      this.value = value;
      this.root.setAttribute('aria-description', `Quota: ${stale ? 'retained / not current' : obs.availability}; observed: ${obs.observed_at_ms ?? 'unknown'}`);
      // Only actual track/slot changes rebuild card contents. Ordinary values,
      // reset clocks, warnings and settings update bound nodes and active help.
      const shape = JSON.stringify([value.primary, ...value.secondary].map(q => [q.quota.label,
        q.quota.period, q.quota.scope, q.quota.model_id, q.quota.unlimited, q.used_fraction != null,
        q.quota.reset_at_ms != null, Boolean(q.pace), q.restricted,
        Boolean(q.quota.quota_display?.used.note || q.quota.quota_display?.remaining.note),
        Boolean(display(q.quota, 'monthly_capacity'))]));
      if (shape !== this.shape) { this.draw(); this.shape = shape; }
      const warningSignature = JSON.stringify(lines);
      if (warningSignature !== this.warningSignature) {
        for (const node of [...this.lower.children]) if (node.className !== 'watch-account-details') node.remove();
        for (const [text, role] of lines) this.lower.append(el('p', text, role));
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
      this.status = new ReportView.LiveStatus();
      this.message = el('p'); this.message.setAttribute('role', 'status');
      this.grid = el('div', undefined, 'account-grid watch-account-grid');
      if (typeof ResizeObserver !== 'undefined') new ResizeObserver(() => this.align()).observe(this.grid);
      physicalWidth(this.root);
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
      // Only comparison peers on the same responsive grid row need a blank slot.
      const template = typeof getComputedStyle === 'function' ? getComputedStyle(this.grid).gridTemplateColumns : '';
      const columns = template && template !== 'none' ? template.trim().split(/\s+/).length : this.cards.size || 1;
      const cards = [...this.cards.values()];
      for (let index = 0; index < cards.length; index += columns) {
        const peers = cards.slice(index, index + columns);
        const extra = peers.some(card => Boolean(display(card.value.primary.quota, 'monthly_capacity')));
        for (const card of peers) card.align(extra);
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
      const late = this.status.update(!failed && Boolean(view.accounts), view.accounts && JSON.stringify(
        view.accounts.accounts.map(item => [item.observation.provider_id, item.observation.id, item.observation.observed_at_ms])));
      const missing = failed && !view.accounts?.accounts.length;
      const sourceNotice = [...this.cards.values()].some(card => card.sourceNotice);
      const message = missing && (!this.cards.size || late && !sourceNotice) ? (this.cards.size ? 'Updates delayed · showing last values' : 'Accounts unavailable; retrying.') :
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
