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
    const help = monthly => {
      if (!current()) return '';
      if (quota().unlimited && !monthly) return '';
      if (ReportView.capacityKnown(quota(), monthly)) {
        // Basis is source-qualified by the projection, not inferred from provider or text.
        if (!monthly && quota().ccost_reference.basis === 'native') return '';
        if (monthly || quota().ccost_reference.basis === 'ratio')
          return ReportView.quotaCapacityHelp(quota(), monthly).split('\n')[0];
      }
      return ReportView.quotaCapacityHelp(quota(), monthly);
    };
    function capacityLine(monthly) {
      const line = el('div', undefined, monthly ? 'watch-monthly-capacity metric-value' : 'watch-quota-capacity metric-value');
      const text = () => {
        const label = monthly ? 'Monthly Capacity' : display(quota(), 'capacity_label');
        return (label === 'N/A' ? 'Capacity' : label) + ': ' + amount(monthly);
      };
      let available;
      ReportView.bind(line, () => {
        const needed = Boolean(help(monthly));
        if (available === needed) return;
        // Replace only the help owner when eligibility changes. Detached owners
        // cannot leave a popup, ARIA reference or inert keyboard stop behind.
        if (line.firstChild) ContextHelp.dismiss(line.firstChild);
        const value = el('span', text);
        if (needed) ContextHelp.value(value, () => help(monthly));
        line.replaceChildren(value);
        available = needed;
      });
      return line;
    }
    const summary = () => quota().unlimited ? 'Unlimited' : view().percent === '—' ? '—' : view().percent + ' ' + view().mode;
    const label = el('div'); label.append(el('span', () => `${ReportView.quotaLabel(quota())} · ${summary()}`));
    ReportView.bind(label, () => label.className = 'watch-quota-summary metric-value' + (view().exhausted ? ' watch-quota-exhausted' : ''));
    label.append(el('span', () => ` (${display(quota(), 'ccost_' + view().mode)})`, 'watch-period-cost'));
    const capacity = capacityLine(false), monthly = capacityLine(true);
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
    } else track.append(el('span', () => quota().unlimited ? 'No usage limit' : 'N/A', 'detail'));
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
    return [[obs.status === 'blocked' && ![item.primary, ...item.secondary].some(q => q.exhausted || q.restricted) ?
      'Provider restriction reported' : '', 'warning']].filter(([text]) => text);
  }
  class Subscription {
    constructor() {
      this.root = el('section', undefined, 'account-card account-subscription watch-subscription');
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
        return `CCost Today: ${display(today?.cost, 'account_ccost')}`;
      }), "This account's reference cost for the local calendar day."));
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
      if (!this.heading) { this.heading = ReportView.accountHeading(() => item().observation); this.root.append(this.heading); }
      // Track-shape redraws must not detach the focused heading link.
      for (const child of [...this.root.children]) if (child !== this.heading) child.remove();
      this.root.append(cost, ...track.nodes, primary);
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
        // Retain native figures only: independently published accounting (including
        // midnight/unknown Today) must not freeze with a failed quota observation.
        const observed = q => ({...q, quota:{...q.quota, ccost_pace:null}});
        value = {...value, primary:observed(this.value.primary), secondary:this.value.secondary.map(observed)};
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
      this.costs ||= new ReportView.CostDisplay();
      const failed = view.quota_stale || view.quota_recovering_count > 0;
      // Missing publication is pending, not an observed empty population. A
      // failed empty read must not erase the last usable common observation.
      if (view.accounts && (view.accounts.accounts.length || !failed)) {
        const wanted = [], keep = new Set();
        const day = ReportView.formatDateTime(view.now_ms ?? view.accounts.now_ms,
          ReportView.DateTimeMode.DATE, view.timezone_id ?? ReportView.configuredTimezone());
        for (let item of view.accounts.accounts) {
          const key = JSON.stringify([item.observation.provider_id, item.observation.id]); keep.add(key);
          item = {...item, ccost_scopes: item.ccost_scopes.map(scope => ({...scope,
            cost: this.costs.select(scope.cost, /^\d{4}-\d{2}-\d{2}$/.test(day) ? [view.source_label, key, scope.name,
              scope.name === 'today' ? day : scope.name === 'this month' ? day.slice(0, 7) :
                [item.primary, ...item.secondary].map(value => value.quota.reset_at_ms)] : null, 'known_ccost')}))};
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
      const message = this.observed && !this.cards.size ? 'No configured accounts detected.' :
        !this.observed && this.showLoading ? 'Loading…' : '';
      ReportView.text(this.message, message);
      // Keep the healthy view grid-only and preserve its DOM through health updates.
      if (this.cards.size && this.grid.parentNode !== this.root) this.root.append(this.grid);
      if (!this.cards.size) this.grid.remove();
      if (message && this.message.parentNode !== this.root) this.root.append(this.message);
      if (!message) this.message.remove();
      this.align();
    }
  }
  function compactQuotaHelp(primary) {
    const capacity = display(primary.quota, 'capacity_amount');
    const summary = `Capacity: ${capacity === '?' ? 'N/A' : capacity}\nNext reset: ${display(primary, 'mini_reset')}`;
    const pace = primary.quota.ccost_pace;
    if (!pace) return summary;
    const lines = [];
    const day = display(pace, 'ccost_per_day');
    if (day && day !== 'N/A') lines.push(`CCost Remaining/day: ${day}`);
    if (pace.workdays === 0) lines.push('No workdays left');
    else {
      const workday = display(pace, 'ccost_per_workday');
      if (workday && workday !== 'N/A') lines.push(`CCost Remaining/workday: ${workday}`);
    }
    return lines.length ? `${summary}\n\n${lines.join('\n')}` : summary;
  }
  // Shared compact subscription presenter; owns neither acquisition nor PiP.
  class CompactView {
    constructor(doc = document) {
      this.doc = doc;
      this.el = (tag, value, name) => {
        const node = doc.createElement(tag);
        if (value !== undefined) node.textContent = value;
        if (name) node.className = name;
        return node;
      };
      this.root = this.el('ul', undefined, 'mini-accounts');
      this.root.tabIndex = 0;
      this.root.setAttribute('aria-label', 'Primary subscription usage and same-period observed CCost');
      this.lines = new Map();
    }
    update(view) {
      const text = ReportView.text, display = ReportView.display;
      const accounts = view?.accounts?.accounts, wanted = [];
      for (const item of accounts || []) {
        const obs = item.observation, primary = item.primary;
        const key = JSON.stringify([obs.provider_id, obs.id]);
        let line = this.lines.get(key);
        if (!line) {
          line = this.el('li');
          const label = this.el('div'); label.append(this.el('span'));
          ContextHelp.value(label.children[0], () => line.helpText || '');
          line.append(label, this.el('progress')); this.lines.set(key, line);
        }
        const warning = primary.restricted ? ' · provider restriction' : '';
        ReportView.bind(line, () => {
          const quota = ReportView.quotaView(primary.quota, primary);
          const used = primary.quota.unlimited ? 'Unlimited' : quota.percent === '—' ? 'Usage unavailable' : quota.percent + ' ' + quota.mode;
          line.helpText = compactQuotaHelp(primary);
          text(line.children[0].children[0], `${obs.label} · ${used} (${display(primary.quota, 'ccost_' + quota.mode)})${warning}`);
          ContextHelp.refresh(line);
          line.className = quota.exhausted && quota.mode === 'remaining' ? 'mini-exhausted' : primary.restricted ? 'mini-warning' : '';
          const bar = line.children[1]; bar.hidden = primary.quota.unlimited || primary.used_fraction == null;
          bar.max = 1; bar.value = quota.fraction ?? 0;
          bar.className = quota.exhausted && !bar.hidden ? 'mini-exhausted' : '';
          bar.setAttribute('aria-label', obs.label + ' · ' + primary.quota.label + ' ' + quota.mode);
          bar.setAttribute('aria-valuetext', used + warning + (quota.exhausted ? ' · exhausted' : ''));
        });
        wanted.push(line);
      }
      if (!wanted.length) {
        this.empty ||= this.el('li');
        text(this.empty, accounts ? 'No configured subscriptions' : 'Acquiring subscriptions…'); wanted.push(this.empty);
      }
      const keep = new Set(wanted);
      for (const node of [...this.root.children]) if (!keep.has(node)) node.remove();
      wanted.forEach((node, index) => {
        if (this.root.children[index] !== node) this.root.insertBefore(node, this.root.children[index] || null);
      });
      for (const [key, line] of this.lines) if (!keep.has(line)) this.lines.delete(key);
    }
  }
  // Detail-only, compact session equivalents. Never renders live account totals.
  class SessionUsage {
    constructor() {
      this.root = el('section', undefined, 'session-quota-usage');
      this.root.setAttribute('aria-label', 'Session Quota Usage');
      this.grid = el('div', undefined, 'account-grid watch-account-grid session-quota-grid');
      this.root.append(el('h2', 'Session Quota Usage'), this.grid);
      this.cards = new Map(); this.root.hidden = true;
      physicalWidth(this.root, () => {});
    }
    update(value) {
      if (!value || this.scope !== value.scope) {
        this.cards.clear(); this.grid.replaceChildren();
      }
      this.scope = value?.scope;
      const accounts = (value?.accounts || []).map(item => ({...item,
        quotas: item.quotas.filter(quota => quota.contribution !== 'zero')})).filter(item => item.quotas.length);
      this.root.hidden = !accounts.length;
      const wanted = new Set();
      for (const item of accounts) {
        const key = JSON.stringify([item.observation.provider_id, item.observation.id]);
        wanted.add(key);
        let card = this.cards.get(key);
        if (!card) {
          card = {root: el('section', undefined, 'account-card account-subscription'), rows: new Map(), value: item};
          card.heading = ReportView.accountHeading(() => card.value.observation, 'h3');
          card.root.append(card.heading); this.cards.set(key, card);
        }
        card.value = item;
        const rows = new Set(item.quotas.map(row => row.id));
        for (const [id, node] of card.rows) if (!rows.has(id)) { node.remove(); card.rows.delete(id); }
        item.quotas.forEach((quota, index) => {
          let line = card.rows.get(quota.id);
          if (!line) {
            line = el('p', undefined, 'metric-value session-quota-row');
            line.append(el('span'), el('span')); card.rows.set(quota.id, line);
          }
          const suffix = quota.scope === 'model' && quota.model_id &&
            !quota.label.toLowerCase().includes(quota.model_id.toLowerCase()) ? ` · ${quota.model_id}` : '';
          const label = quota.label.replace(/(^|\s)(\p{Ll})/gu, (_, space, letter) => space + letter.toUpperCase());
          ReportView.text(line.children[0], `${label}${suffix}`);
          ReportView.text(line.children[1], quota.percent);
          ContextHelp.value(line.children[1], quota.reason || 'Session-equivalent consumption, not account total Used.');
          ContextHelp.refresh(line.children[1]);
          if (card.root.children[index + 1] !== line)
            card.root.insertBefore(line, card.root.children[index + 1] || null);
        });
        ReportView.syncUnits(card.heading);
      }
      for (const [key, card] of this.cards) if (!wanted.has(key)) { card.root.remove(); this.cards.delete(key); }
      accounts.forEach((item, index) => {
        const node = this.cards.get(JSON.stringify([item.observation.provider_id, item.observation.id])).root;
        if (this.grid.children[index] !== node) this.grid.insertBefore(node, this.grid.children[index] || null);
      });
    }
  }
  return {View, CompactView, SessionUsage};
})();
