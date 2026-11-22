'use strict';
// Scoped local reads. A notification never carries values to render.
const CachedStats = (() => {
  const periods = [['today', 'Today'], ['7-days', '7 days'], ['30-days', '30 days'],
    ['month', 'This month'], ['all', 'All time']];
  const fields = [['tokens', 'Observed tokens'], ['working', 'Working time'], ['longest', 'Longest session'], ['busiest', 'Busiest day'],
    ['overnight', 'Overnight work'], ['streak', 'Longest streak (days)'], ['parallel', 'Peak parallel sessions']];
  const revoked = new Set(['cache_source_unbound', 'authentication_required', 'host_identity_changed', 'instance_stopping']);
  const mark = (hint, period) => JSON.stringify(hint?.marks?.[period] ?? null);
  const clock = {now: () => Date.now(), set: (run, wait) => setTimeout(run, wait), cancel: id => clearTimeout(id)};

  class Controller {
    constructor(api, changed, timing = clock) {
      Object.assign(this, {api, changed, timing, period: null, hint: null, flight: null,
        value: null, error: null, blocked: false, expiry: null});
    }

    abort() {
      this.flight?.abort();
      this.flight = null;
      this.timing.cancel(this.expiry);
      this.expiry = null;
    }

    withdraw(error = null) {
      this.abort();
      this.value = null;
      this.error = error;
    }

    activate(period) {
      if (this.period === period) return;
      this.period = period;
      this.abort();
      if (period && (this.value?.period !== period || this.expired())) this.withdraw();
      this.read();
    }

    health(blocked) {
      if (this.blocked === blocked) return;
      this.blocked = blocked;
      if (blocked) { this.hint = null; this.withdraw(); this.changed(); }
      else this.read();
    }

    committed(hint, resync = false) {
      if (!hint || this.blocked) return;
      const prior = this.hint;
      const bindingChanged = (prior && prior.binding !== hint.binding) ||
        (this.value && this.value.binding !== hint.binding);
      const epochChanged = hint.archive_epoch != null && (
        prior?.archive_epoch != null && prior.archive_epoch !== hint.archive_epoch ||
        this.value && this.value.archive_epoch !== hint.archive_epoch);
      const cleared = hint.cleared === true && (!prior?.cleared || bindingChanged || epochChanged);
      this.hint = hint;
      if (!hint.binding) {
        if (this.value || this.flight || this.error !== 'cache_source_unbound') {
          this.withdraw('cache_source_unbound'); this.changed();
        }
        return;
      }
      if (bindingChanged || epochChanged || cleared) { this.withdraw(); this.changed(); }
      if (bindingChanged || epochChanged || cleared || mark(prior, this.period) !== mark(hint, this.period) ||
          !prior && !this.value && !this.flight || resync && this.error) {
        if (this.flight) this.dirty = true;
        else this.read();
      }
    }

    expired() {
      const end = this.value?.valid_until_ms;
      return end != null && end <= this.timing.now();
    }

    async read() {
      if (!this.period || this.blocked || this.flight || this.hint && !this.hint.binding) return;
      const period = this.period, flight = this.flight = new AbortController();
      this.dirty = false;
      try {
        const value = await this.api('/api/cache/ai-stats', {period}, flight.signal);
        if (this.flight !== flight || this.dirty) return;
        if (value?.period !== period || !/^[a-f0-9]{32}$/.test(value.binding) ||
            !Number.isSafeInteger(value.archive_epoch) || value.coverage !== 'unknown' ||
            !value.display || typeof value.display !== 'object') throw new Error('cache_unavailable');
        if (this.hint && (this.hint.binding !== value.binding ||
            this.hint.archive_epoch != null && value.archive_epoch !== this.hint.archive_epoch)) return;
        this.value = value;
        this.error = null;
        const end = value.valid_until_ms;
        this.timing.cancel(this.expiry);
        if (end != null && Number.isSafeInteger(end) && end > this.timing.now()) {
          // Cap the delay on very long months to avoid a 32-bit timeout overflow.
          this.expiry = this.timing.set(() => {
            if (this.expired()) { this.withdraw(); this.changed(); }
            this.read();
          }, Math.min(2147483647, end - this.timing.now()));
        }
      } catch (error) {
        if (this.flight !== flight) return;
        this.error = error.message;
        if (revoked.has(this.error)) this.value = null;
      } finally {
        if (this.flight === flight) {
          this.flight = null;
          if (this.dirty) this.read();
          else this.changed();
        }
      }
    }

    snapshot() { return {value: this.expired() ? null : this.value, error: this.error, blocked: this.blocked}; }
  }

  class View {
    constructor(select) {
      const element = ReportView.element;
      this.root = element('section', undefined, 'ai-stats-section cached-stats');
      this.root.append(element('h2', 'AI Stats'));
      const filters = element('div', undefined, 'ai-stats-periods');
      filters.setAttribute('role', 'group');
      filters.setAttribute('aria-label', 'AI Stats period');
      this.buttons = new Map(periods.map(([period, name]) => {
        const button = element('button', name);
        button.type = 'button'; button.dataset.period = period;
        button.addEventListener('click', () => select(period));
        filters.append(button);
        return [period, button];
      }));
      this.caption = element('p');
      const values = element('dl');
      this.values = new Map(fields.map(([field, label]) => {
        const value = element('dd', '—');
        value.dataset.metric = field;
        values.append(element('dt', label), value);
        return [field, value];
      }));
      this.root.append(filters, this.caption, values);
    }

    attach(host, period, {value, error, blocked}) {
      for (const [name, button] of this.buttons) button.setAttribute('aria-pressed', String(name === period));
      const display = value?.period === period ? value.display : {};
      ReportView.text(this.caption, blocked || error ? 'Cached AI Stats are unavailable for this source.' :
        display.working || display.tokens ? 'Observed cache only. Unobserved and estimated activity is not included.' :
        'No measured work is cached for this period yet.');
      for (const [field, node] of this.values)
        ReportView.text(node, typeof display[field] === 'string' ? display[field] : '—');
      if (this.root.parentNode !== host) host.replaceChildren(this.root);
    }
  }

  return {Controller, View};
})();
