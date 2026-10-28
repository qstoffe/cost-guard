// Deterministic transport clock: no browser, sockets, model calls or real waits.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const turns = async () => { for (let n = 0; n < 20; n++) await Promise.resolve(); };
async function main() {
  let now = 1000, failure = null, calls = 0;
  let held = false, releaseApi = null, inFlight = 0, maxInFlight = 0;
  const timers = new Map(), streams = [], states = [], updates = [];
  let next = 0;
  let snapshot = {instance_id: 'first', sequence: 1, values: {
    live: {state: 'running', source_observed_at_ms: 900, view: {retained: 'not zero'}}}};
  const context = vm.createContext({Date, api: async () => {
    calls++; inFlight++; maxInFlight = Math.max(maxInFlight, inFlight);
    try {
      if (held) await new Promise(resolve => { releaseApi = resolve; });
      if (failure) throw new Error(failure);
      return structuredClone(snapshot);
    } finally { inFlight--; }
  }, update: value => updates.push(value), status: (message, state) => states.push({message, ...state}),
  clock: {now: () => now, later: (fn, ms) => { assert.equal(ms, 10000); timers.set(++next, fn); return next; },
    cancel: id => timers.delete(id)}, sourceFactory: () => {
    const stream = {listeners: {}, close() { this.closed = true; },
      addEventListener(kind, fn) { this.listeners[kind] = fn; }};
    streams.push(stream); return stream;
  }});
  vm.runInContext(fs.readFileSync('src/web/assets/live.js', 'utf8'), context);
  const connect = async () => {
    vm.runInContext('globalThis.connection = LiveConnection.connect(api, update, status, sourceFactory, clock)', context);
    await turns();
    streams.at(-1)?.onopen(); await turns();
  };
  const tick = async () => {
    assert.equal(timers.size, 1, 'one bounded watchdog');
    const [id, fn] = [...timers][0]; timers.delete(id); now += 10000; fn(); await turns();
  };
  await connect();
  assert.equal(states.at(-1).kind, 'connected');
  assert.equal(states.at(-1).observedAt, 900);
  assert.equal(streams.length, 1);
  const retainedView = snapshot.values.live.view;
  snapshot.sequence++; snapshot.values.live.view = null;
  await tick();
  assert.equal(states.at(-1).kind, 'starting', 'HTTP without a source view is not connected acquisition');
  snapshot.sequence++; snapshot.values.live.view = retainedView;
  await tick();
  streams[0].onerror();
  assert.equal(states.at(-1).kind, 'reconnecting');
  assert.equal(states.at(-1).writable, false);
  const errorCalls = calls;
  for (let n = 0; n < 5; n++) streams[0].onerror();
  assert.equal(calls, errorCalls, 'transport retry notifications never start a busy HTTP loop');
  assert.equal(streams.length, 1, 'native EventSource owns retry; no duplicate stream');
  await tick();
  assert.equal(states.at(-1).kind, 'reconnecting', 'healthy HTTP must not mask an interrupted stream');
  assert.match(states.at(-1).message, /HTTP connected/);
  failure = 'network_error';
  await tick();
  assert.equal(states.at(-1).kind, 'offline');
  assert.match(states.at(-1).message, /OFFLINE — last observation/);
  assert.equal(states.at(-1).authenticatedAt, 31000, 'failed probes cannot freshen the timestamp');
  assert.equal(updates.at(-1).view.retained, 'not zero');
  streams[0].listeners.progress({lastEventId: 'first:4', data: '{"jobs":[]}'});
  assert.equal(states.at(-1).kind, 'offline', 'job progress cannot claim that a failed source/host check recovered');
  failure = null;
  snapshot.sequence++; snapshot.values.live.state = 'recovering';
  await tick();
  assert.equal(states.at(-1).kind, 'source_unavailable', 'working HTTP is not source readiness');
  snapshot.sequence++; snapshot.values.live.state = 'running';
  streams[0].onopen(); await turns();
  await tick();
  assert.equal(states.at(-1).kind, 'connected');
  assert.equal(streams.length, 1);
  vm.runInContext('connection.resync()', context);
  assert.equal(states.at(-1).kind, 'connected', 'recent healthy visibility return does not invent an outage');
  await turns();
  now += 20000;
  vm.runInContext('connection.resync()', context);
  assert.equal(states.at(-1).kind, 'reconnecting', 'stale idle resume invalidates retained DOM before fetching');
  await turns();
  const start = states.length;
  for (let n = 0; n < 120; n++) await tick();
  assert.ok(states.slice(start).every(s => s.kind === 'connected'), 'twenty healthy virtual minutes never flap');
  held = true;
  await tick();
  streams[0].onerror(); streams[0].onopen(); streams[0].onopen();
  vm.runInContext('connection.resync()', context);
  assert.equal(inFlight, 1, 'probe/open/resync race shares the in-flight authenticated snapshot');
  held = false; releaseApi(); await turns();
  assert.equal(maxInFlight, 1);
  assert.equal(states.at(-1).kind, 'connected');
  assert.equal(streams.length, 1);
  assert.equal(timers.size, 1);
  snapshot.instance_id = 'replacement';
  const count = updates.length;
  await tick();
  assert.equal(states.at(-1).kind, 'identity_changed');
  assert.equal(updates.length, count, 'different host values never enter the old page');
  assert.equal(timers.size, 0);
  assert.equal(streams[0].closed, true);
  streams[0].onopen(); streams[0].onerror();
  assert.equal(states.at(-1).kind, 'identity_changed', 'late transport callbacks cannot undo terminal state');
  snapshot.instance_id = 'first';
  await connect();
  failure = 'authentication_required';
  await tick();
  assert.equal(states.at(-1).kind, 'authorization_required');
  assert.equal(timers.size, 0);
  failure = null;
  await connect();
  streams.at(-1).listeners.terminal({lastEventId: 'first:99', data: '{"reason":"menu"}'});
  assert.match(states.at(-1).message, /STOPPED — NOT LIVE/);
  assert.equal(timers.size, 0);
  const terminalCalls = calls;
  vm.runInContext('connection.resync()', context); await turns();
  assert.equal(calls, terminalCalls, 'terminal pages never retry or restart');
  // Initial unreachable host recovers without reload or a duplicate EventSource.
  failure = 'network_error';
  await connect();
  assert.equal(states.at(-1).kind, 'offline');
  failure = null;
  await tick();
  streams.at(-1).onopen(); await turns();
  assert.equal(states.at(-1).kind, 'connected');
  vm.runInContext('connection.close()', context);
  assert.equal(timers.size, 0);
  console.log('web connection passed: bounded watchdog, idle, source loss, auth, identity, terminal, initial recovery');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
