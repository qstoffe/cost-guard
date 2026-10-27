'use strict';
// Exactly one authenticated EventSource per tab, independent of route changes.
// Complete publications are atomic; no browser-side totals or lifecycle inference.
const LiveConnection = (() => {
  function connect(api, update, status, sourceFactory = url => new EventSource(url),
      clock = {now: () => Date.now(), later: (fn, ms) => setTimeout(fn, ms), cancel: id => clearTimeout(id)}) {
    let source = null, instance = null, sequence = 0, syncing = null, stopped = false;
    let dirty = false, pending = [], values = {}, timer = null, authenticatedAt = null;
    function report(kind, message) {
      status(message, {kind, authenticatedAt, observedAt: values.live?.source_observed_at_ms ?? null,
        terminal: stopped, writable: !stopped && ['connected', 'starting', 'source_unavailable'].includes(kind)});
    }
    function stop(message, kind = 'stopped') {
      stopped = true;
      if (source) source.close();
      clock.cancel(timer);
      report(kind, message);
    }
    function health() {
      const live = values.live;
      if (!live || live.state === 'starting' || (live.state === 'running' && !live.view)) report('starting', 'STARTING — source observation pending. HTTP is not source readiness.');
      else if (live.state !== 'running') report('source_unavailable', 'SOURCE UNAVAILABLE — HTTP connected; last source observation retained, not live.');
      else report('connected', 'Live connected.');
    }
    function publish(validate = false) {
      if (values.terminal) {
        stop(`STOPPED — NOT LIVE · ${values.terminal.reason}: host stopped. Run the launcher again using the OS launcher.`);
      } else { if (validate) health(); update(values.live, values.progress); }
    }
    async function sync() {
      if (stopped) return;
      if (syncing) { dirty = true; return syncing; }
      syncing = (async () => {
        try {
          const snapshot = await api('/api/live');
          if (stopped) return;
          if (instance && snapshot.instance_id !== instance) {
            stop('Host identity changed. Obtain a fresh authorized launcher link.', 'identity_changed'); return;
          }
          instance = snapshot.instance_id;
          authenticatedAt = clock.now();
          if (snapshot.sequence >= sequence) {
            sequence = snapshot.sequence; values = snapshot.values; publish(true);
          }
          openStream();
        } catch (error) {
          if (stopped) return;
          if (['authentication_required', 'bootstrap_expired_or_used', 'csrf_required'].includes(error.message)) {
            stop('AUTHENTICATION EXPIRED — NOT LIVE. Obtain a fresh launcher link.', 'authorization_required');
          } else if (error.message === 'host_identity_changed') {
            stop('HOST IDENTITY CHANGED — NOT LIVE. Obtain a fresh authorized launcher link.', 'identity_changed');
          } else if (error.message === 'instance_stopping') {
            stop('STOPPED — NOT LIVE. Run the launcher again using the OS launcher.');
          } else report('offline', 'OFFLINE — last observation retained; Live offline. Host unreachable. Retrying this host only; no server will be started.');
        }
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
        stop('Host identity changed. Obtain a fresh authorized launcher link.', 'identity_changed'); return;
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
      sequence = number; publish(kind === 'live');
    }
    function openStream() {
      if (stopped || source || !instance) return;
      source = sourceFactory('/api/events'); // No reusable secret or query string.
      for (const kind of ['live', 'progress', 'terminal']) source.addEventListener(kind, e => accept(kind, e));
      source.addEventListener('resync', sync);
      source.addEventListener('authorization_required', () => stop('AUTHENTICATION EXPIRED — NOT LIVE. Obtain a fresh launcher link.', 'authorization_required'));
      source.onopen = () => { if (!stopped) sync(); };
      source.onerror = () => { if (!stopped) report('reconnecting', 'RECONNECTING — Live offline; last observation retained, not live. Checking the same authorized host.'); };
    }
    async function probe() {
      await sync();
      if (!stopped) timer = clock.later(probe, 10000);
    }
    function revalidate() {
      if (stopped) return;
      report('reconnecting', 'RECONNECTING — revalidating after idle; last observation retained, not live.');
      sync();
    }
    report('starting', 'STARTING — connecting to the authorized host.');
    probe();
    return {close: () => stop('Live connection closed.'), resync: revalidate};
  }
  return {connect};
})();
