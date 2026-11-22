'use strict';
// Server-owned order, membership, price qualification and paging.
const CachedModels = (() => {
  const columns = ['publisher', 'model', 'cost', 'release'];
  const day = 86400000;
  const clock = {now: () => Date.now(), set: (run, wait) => setTimeout(run, wait), cancel: id => clearTimeout(id)};
  const revoked = new Set(['authentication_required', 'csrf_required', 'cache_source_unbound',
    'host_identity_changed', 'instance_stopping']);

  class Controller {
    constructor(api, changed, timing = clock) {
      Object.assign(this, {api, changed, timing, owner: null, hint: null, value: null, flight: null,
        timer: null, error: null, blocked: false, offset: 0});
    }

    abort() {
      this.flight?.abort();
      this.flight = null;
      this.timing.cancel(this.timer);
      this.timer = null;
    }

    drop(error = null) {
      this.abort();
      this.value = null;
      this.error = error;
    }

    activate(owner) {
      if (owner === this.owner) return;
      this.drop();
      this.owner = owner;
      this.offset = 0;
      this.read();
    }

    health(blocked) {
      if (blocked === this.blocked) return;
      this.blocked = blocked;
      if (blocked) { this.hint = null; this.drop(); this.changed(true); }
      else this.read();
    }

    select(offset) {
      this.offset = offset;
      this.drop();
      this.changed(true);
      this.read();
    }

    committed(hint, resync) {
      if (!hint || this.blocked) return;
      const prior = this.hint, value = this.value;
      this.hint = hint;
      const replaced = prior && hint.binding !== prior.binding || value && hint.binding !== value.binding ||
        hint.archive_epoch != null && (
          prior?.archive_epoch != null && hint.archive_epoch !== prior.archive_epoch ||
          value && hint.archive_epoch !== value.archive_epoch);
      const repriced = hint.price_floor_ms > (prior?.price_floor_ms ?? value?.price_floor_ms ?? -1);
      if (!hint.binding || replaced || repriced) {
        if (!hint.binding && !this.flight && !this.value && this.error === 'cache_source_unbound') return;
        this.drop(hint.binding ? null : 'cache_source_unbound');
        this.changed(true);
      }
      if (hint.binding && (replaced || repriced || hint.mark !== prior?.mark ||
          !prior && !this.value && !this.flight || resync && this.error)) {
        this.abort();
        this.read();
      }
    }

    async read() {
      if (!this.owner || this.blocked || this.flight || this.hint && !this.hint.binding) return;
      const {all, latest, sorts} = this.owner.models;
      const orders = sorts.map(sort => [columns[sort.index], sort.direction === 1 ? 'asc' : 'desc']);
      const flight = this.flight = new AbortController();
      let urgent = false;
      try {
        const value = await this.api('/api/cache/models', {show_all: all, latest, orders, offset: this.offset}, flight.signal);
        if (this.flight !== flight) return;
        if (!/^[a-f0-9]{32}$/.test(value?.binding) || !Number.isSafeInteger(value.archive_epoch) ||
            !Number.isSafeInteger(value.price_floor_ms) || !Number.isSafeInteger(value.offset) ||
            value.size !== 50 || !Array.isArray(value.rows) || value.rows.length > value.size ||
            value.count !== null && (!Number.isSafeInteger(value.count) || value.count < value.rows.length))
          throw new Error('cache_unavailable');
        if (this.hint && (this.hint.binding !== value.binding ||
            this.hint.archive_epoch != null && value.archive_epoch !== this.hint.archive_epoch ||
            value.price_floor_ms < this.hint.price_floor_ms ||
            this.hint.mark != null && (value.observed_ms == null || value.observed_ms < this.hint.mark))) return;
        this.value = value;
        this.offset = value.offset;
        this.error = null;
        const now = this.timing.now(), end = value.price_boundary_ms;
        const next = value.prices_valid && Number.isSafeInteger(end) && end > now ?
          Math.min(end, (Math.floor(now / day) + 1) * day) : (Math.floor(now / day) + 1) * day;
        this.timing.cancel(this.timer);
        if (value.observed_ms != null) this.timer = this.timing.set(() => {
          const expired = this.expired();
          if (expired) this.changed(true);
          this.read();
        }, next - now);
      } catch (error) {
        if (this.flight !== flight) return;
        this.error = error.message;
        if (revoked.has(this.error)) { this.value = null; urgent = true; }
      } finally {
        if (this.flight === flight) {
          this.flight = null;
          this.changed(urgent || this.expired());
        }
      }
    }

    expired() {
      return this.value?.prices_valid && this.value.price_boundary_ms != null &&
        this.timing.now() >= this.value.price_boundary_ms;
    }

    snapshot() {
      const value = this.value;
      if (!this.expired()) return {value, error: this.error, blocked: this.blocked};
      const rows = value.rows.map(row => ({...row, display: {relative_cost: 'N/A'}, promotional: false,
        promotion: null, price_help: 'Cached rates are no longer current.'}));
      return {value: {...value, rows, prices_valid: false}, error: this.error, blocked: this.blocked};
    }
  }

  return {Controller};
})();
