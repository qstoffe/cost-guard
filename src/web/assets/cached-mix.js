'use strict';
// One local read for the visible scope; events are hints, never display facts.
const CachedMix = (() => {
  class Controller {
    constructor(api, changed) {
      Object.assign(this, {api, changed, period: null, hint: null, stamp: null, flight: null,
        value: null, error: null, blocked: false});
    }
    activate(period) {
      if (period === this.period) return;
      this.period = period;
      this.withdraw();
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
    withdraw() {
      this.flight?.abort();
      this.flight = null;
      this.value = this.error = null;
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
      if (bindingChanged || cleared) this.withdraw();
      if (hint.binding == null) {
        if (!bindingChanged) this.withdraw();
        this.error = 'cache_source_unbound';
        this.changed();
      } else if (bindingChanged || cleared || missed || resync && this.error ||
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
        const value = await this.api('/api/cache/token-mix', {period}, flight.signal);
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
        if (['cache_source_unbound', 'authentication_required', 'host_identity_changed'].includes(this.error))
          this.value = null;
      } finally {
        if (this.flight === flight) {
          this.flight = null;
          if (this.refresh) this.read();
          else this.changed();
        }
      }
    }
    snapshot() { return {value: this.value, error: this.error, blocked: this.blocked}; }
  }
  function valid(value, period) {
    const time = item => item === null || Number.isSafeInteger(item);
    return value?.scope === period && /^[a-f0-9]{32}$/.test(value.binding) &&
      time(value.start_ms) && time(value.end_ms) && ['unknown', 'partial'].includes(value.coverage) &&
      (value.token_mix === null || Number.isSafeInteger(value.token_mix?.request_count) &&
        value.token_mix.request_count > 0 && typeof value.token_mix.display?.mix_total_tokens === 'string');
  }
  class View {
    constructor(select) {
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
      this.root.append(controls, this.summary, this.status);
    }
    attach(parent, period, {value, error, blocked}) {
      for (const [key, button] of this.buttons) button.setAttribute('aria-pressed', String(key === period));
      const mix = value?.token_mix;
      this.summary.hidden = !mix;
      if (mix) {
        ReportView.text(this.title, `Cached Token Mix · ${ReportView.display(mix, 'mix_total_tokens')} tokens`);
        ['input', 'cache', 'write', 'output'].forEach((key, index) =>
          ReportView.text(this.metrics[index], ReportView.display(mix, 'mix_' + key + '_share')));
      }
      const message = blocked ? 'Cached usage is unavailable.' : mix ?
        'Partial cached usage. Model and publisher breakdowns are not available in this cache view.' :
        error && error !== 'cache_source_unbound' ? 'Cached usage is unavailable.' : 'No cached usage yet.';
      ReportView.text(this.status, message);
      if (parent.firstChild !== this.root) parent.replaceChildren(this.root);
    }
  }
  return {Controller, View};
})();
