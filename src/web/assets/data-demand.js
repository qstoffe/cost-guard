'use strict';
// Lightweight route leases only. Due times and expensive work belong to the host.
const DataDemand = (() => {
  class Controller {
    constructor(api, state, writable) {
      Object.assign(this, {api, state, writable, tab: crypto.randomUUID()});
    }
    update() {
      clearTimeout(this.timer);
      if (!this.writable()) return;
      const state = this.state();
      if (!state) return;
      this.api('/api/interest', {tab: this.tab, section: state.detail ? 'session' : state.section,
        visible: !document.hidden, request: ['models', 'token-mix', 'ai-stats', 'comparisons'].includes(state.section) ? state.request : null})
        .catch(() => {}); // API owns authentication/identity failures; leases expire.
      if (!document.hidden) this.timer = setTimeout(() => this.update(), 30000);
    }
  }
  return {Controller};
})();
