'use strict';
// Lightweight route leases only. Due times and expensive work belong to the host.
const DataDemand = (() => {
  class Controller {
    constructor(api, state, writable, {owner = window, history = false} = {}) {
      Object.assign(this, {api, state, writable, owner, history, tab: crypto.randomUUID(), closed: false});
      this.visibility = () => this.update();
      this.pagehide = () => this.close();
      owner.document.addEventListener('visibilitychange', this.visibility);
      owner.addEventListener('pagehide', this.pagehide, {once: true});
    }
    payload(visible) {
      const state = this.state();
      if (!state) return null;
      const value = {tab: this.tab, section: state.detail ? 'session' : state.section,
        visible, request: ['models', 'token-mix', 'ai-stats', 'comparisons'].includes(state.section) ? state.request : null};
      if (this.history && value.section === 'watch') value.history = state.history === true;
      return value;
    }
    send(value) {
      this.api('/api/interest', value)
         .catch(() => {}); // API owns authentication/identity failures; leases expire.
    }
    update() {
      this.owner.clearTimeout(this.timer);
      if (this.closed || !this.writable()) return;
      const value = this.payload(!this.owner.document.hidden);
      if (!value) return;
      this.send(value);
      if (value.visible) this.timer = this.owner.setTimeout(() => this.update(), 30000);
    }
    close(withdraw = true) {
      if (this.closed) return;
      this.closed = true;
      this.owner.clearTimeout(this.timer);
      this.owner.document.removeEventListener('visibilitychange', this.visibility);
      this.owner.removeEventListener('pagehide', this.pagehide);
      const value = withdraw && this.writable() ? this.payload(false) : null;
      if (value) this.send(value);
    }
  }
  return {Controller};
})();
