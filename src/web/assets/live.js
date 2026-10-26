'use strict';
// Exactly one authenticated EventSource per tab, independent of route changes.
// Complete publications are atomic; no browser-side totals or lifecycle inference.
const LiveConnection = (() => {
  function connect(api, update, status, sourceFactory = url => new EventSource(url)) {
    let source = null, instance = null, sequence = 0, syncing = null, stopped = false;
    let dirty = false, pending = [], values = {};
    function stop(message) {
      stopped = true;
      if (source) source.close();
      status(message);
    }
    function publish() {
      if (values.terminal) {
        stop(`${values.terminal.reason}: host stopped. Run the launcher again.`);
      } else update(values.live, values.progress);
    }
    async function sync() {
      if (stopped) return;
      if (syncing) { dirty = true; return syncing; }
      syncing = (async () => {
        try {
          const snapshot = await api('/api/live');
          if (stopped) return;
          if (instance && snapshot.instance_id !== instance) {
            stop('New host instance. Obtain a fresh authorized launcher link.'); return;
          }
          instance = snapshot.instance_id;
          if (snapshot.sequence >= sequence) {
            sequence = snapshot.sequence; values = snapshot.values; publish();
          }
        } catch (_) { status('Live offline. Last observation retained; reconnecting.'); }
      })();
      await syncing;
      syncing = null;
      const buffered = pending; pending = [];
      for (const [kind, event] of buffered) accept(kind, event);
      if (dirty && !stopped) { dirty = false; await sync(); }
    }
    function accept(kind, event) {
      if (stopped) return;
      if (syncing) {
        if (pending.length < 32) pending.push([kind, event]);
        else dirty = true;
        return;
      }
      const match = /^([^:]+):([0-9]+)$/.exec(event.lastEventId);
      if (!match || match[1] !== instance) {
        stop('Host identity changed. Obtain a fresh authorized launcher link.'); return;
      }
      const number = Number(match[2]);
      if (!Number.isSafeInteger(number) || number <= sequence) return;
      if (kind === 'terminal') {
        try { values.terminal = JSON.parse(event.data); sequence = number; publish(); }
        catch (_) { sync(); }
        return; // A received terminal notice must stop retry even across a replay gap.
      }
      if (number !== sequence + 1) { sync(); return; }
      try { values[kind] = JSON.parse(event.data); }
      catch (_) { sync(); return; }
      sequence = number; publish();
    }
    async function start() {
      await sync();
      if (stopped || !instance) return;
      source = sourceFactory('/api/events'); // No reusable secret or query string.
      for (const kind of ['live', 'progress', 'terminal']) source.addEventListener(kind, e => accept(kind, e));
      source.addEventListener('resync', sync);
      source.addEventListener('authorization_required', () => stop('Authorization expired. Obtain a fresh launcher link.'));
      source.onopen = () => { if (!stopped) { status('Live connected.'); sync(); } };
      source.onerror = () => { if (!stopped) status('Live offline. Last observation retained; reconnecting. No server will be started.'); };
    }
    start();
    return {close: () => stop('Live connection closed.'), resync: sync};
  }
  return {connect};
})();
