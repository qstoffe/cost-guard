'use strict';
// The opener owns one SQLite subscription/read for Full Watch and Mini.
const CachedWatch = (() => {
  class Controller {
    constructor(api, update) {
      Object.assign(this, {api, update, hint: null, value: null, flight: null, blocked: false,
        liveUncertain: false, quotaUncertain: false, healthVersion: 0, dirty: false});
    }
    quotaView(accounts, now) {
      if (!accounts || this.quotaMark?.binding === this.value.binding &&
          this.quotaMark.revision > this.value.quota_revision) return null;
      return {...accounts, accounts: accounts.accounts.filter(item => now < item.discard_at_ms).map(item =>
        this.quotaUncertain || now >= item.fresh_until_ms ? {...item, stale: true} : item)};
    }
    quotaHint(hint) {
      if (this.blocked || !hint?.binding || !Number.isSafeInteger(hint.revision)) return;
      const mark = this.quotaMark;
      if (mark?.binding === hint.binding && mark.revision >= hint.revision) return;
      this.quotaMark = hint;
      this.changed(); // Withdraw superseded values before waiting for a new commit.
    }
    publication() {
      if (!this.value || this.blocked) return null;
      const {view: saved, freshness, observed_ms: at, expires_ms: expiry} = this.value;
      const now = Date.now();
      const day = saved.daily_usage?.day_end_ms <= now ? {daily_usage: null, daily_state: 'pending'} : {};
      const view = {...saved, ...day, accounts: this.quotaView(saved.accounts, now), cached_quota: true};
      if (!this.liveUncertain && !this.needsLiveRead && freshness === 'current' && now < expiry) {
        return {state: 'running', source_observed_at_ms: at, view, cached: true};
      }
      const earlier = freshness !== 'current' ? view.earlier_cards : [...view.earlier_cards,
        ...view.active_cards.map(card => ({...card, state: 'retained', rows: card.rows.map(row =>
          row.prompt.in_progress ? {...row, display: undefined, live_context: undefined, prompt: {...row.prompt,
            in_progress: false, execution_unverified: true}} : row)}))];
      return {state: freshness === 'empty' ? 'empty' : 'as-of', source_observed_at_ms: at, cached: true,
        view: {...view, active_cards: [], earlier_cards: earlier, cards_state: 'partial'}};
    }
    changed() {
      const publication = this.publication();
      const previous = this.presented;
      const daily = publication?.view.daily_usage;
      const quota = JSON.stringify(publication?.view.accounts?.accounts.map(item => [item.observation.id, item.stale]));
      if (previous?.value === this.value && previous.state === publication?.state && previous.daily === daily &&
          previous.quota === quota) return;
      this.presented = {value: this.value, state: publication?.state, daily, quota};
      this.update(publication);
    }
    clear() {
      this.flight?.abort(); this.flight = null; this.value = null;
      clearTimeout(this.timer); clearTimeout(this.expire); this.timer = null; this.dirty = false;
      this.changed();
    }
    health(blocked, liveUncertain, quotaUncertain = false) {
      const changed = this.blocked !== blocked || this.liveUncertain !== liveUncertain ||
        this.quotaUncertain !== quotaUncertain;
      this.blocked = blocked;
      this.liveUncertain = liveUncertain;
      this.quotaUncertain = quotaUncertain;
      if (!changed) return;
      this.healthVersion++;
      if (liveUncertain) this.needsLiveRead = true;
      if (blocked) { this.hint = null; this.clear(); }
      else { this.changed(); this.catchUp(); }
    }
    cacheHint(hint, resync = false) {
      if (this.blocked) return;
      const previous = this.hint;
      this.hint = hint || null;
      if (hint && ((this.value && hint.binding !== this.value.binding) ||
          hint.archive_epoch > this.value?.archive_epoch ||
          (previous && previous.binding !== hint.binding))) this.clear();
      const behind = !this.value || this.value.binding !== hint?.binding ||
        this.value.archive_epoch < hint?.archive_epoch || this.value.generation < hint?.generation;
      if (hint?.binding && (resync && behind || previous?.generation !== hint.generation ||
          previous?.archive_epoch !== hint.archive_epoch || previous?.binding !== hint.binding)) this.catchUp();
      else if (!hint && resync && !this.value) this.catchUp();
    }
    catchUp() {
      this.dirty = true;
      if (this.blocked || this.flight || this.timer) return;
      this.timer = setTimeout(() => { this.timer = null; void this.read(); }, 30);
    }
    async read() {
      if (this.blocked || this.flight || !this.dirty) return;
      this.dirty = false;
      const flight = new AbortController(), hint = this.hint;
      const healthVersion = this.healthVersion;
      this.flight = flight;
      try {
        const value = await this.api('/api/cache/watch', undefined, flight.signal);
        if (this.flight !== flight) return;
        const latest = this.hint;
        if ((latest && latest.binding !== value.binding) ||
            latest?.archive_epoch > value.archive_epoch ||
            latest?.archive_epoch === value.archive_epoch && latest.generation > value.generation) {
          // Wait for the current in-flight binding's hint instead of painting it
          // under a retired incarnation. A raced newer event already set dirty.
          if (latest !== hint) this.dirty = true;
          return;
        }
        const previous = this.value;
        if (!previous || ['binding', 'archive_epoch', 'generation', 'freshness', 'expires_ms', 'quota_revision']
          .some(key => previous[key] !== value[key]) || !!previous.daily !== !!value.daily) this.value = value;
        if (!this.liveUncertain && healthVersion === this.healthVersion) this.needsLiveRead = false;
        this.changed();
        this.scheduleExpiry();
      } catch (error) {
        if (this.flight === flight && ['cache_source_unbound', 'authentication_required', 'host_identity_changed'].includes(error.message)) {
          const newerBinding = this.hint !== hint && this.hint?.binding;
          this.clear();
          if (newerBinding && error.message === 'cache_source_unbound') this.catchUp();
        }
      } finally {
        if (this.flight === flight) {
          this.flight = null;
          if (this.dirty) this.catchUp();
        }
      }
    }
    scheduleExpiry() {
      clearTimeout(this.expire);
      const now = Date.now(), expiry = this.value?.expires_ms;
      const quotaDeadlines = this.value?.view.accounts?.accounts.flatMap(item =>
        [item.fresh_until_ms, item.discard_at_ms]) || [];
      const next = Math.min(...[expiry, this.value?.view.daily_usage?.day_end_ms, ...quotaDeadlines].filter(at => at > now));
      if (Number.isFinite(next)) this.expire = setTimeout(() => {
        this.changed();
        if (expiry && expiry <= Date.now() && next === expiry) this.catchUp();
        this.scheduleExpiry();
      }, next - now + 1);
    }
  }
  return {Controller};
})();
