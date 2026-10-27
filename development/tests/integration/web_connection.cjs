// Deterministic transport clock: no browser, sockets, model calls or real waits.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const turns = async () => { for (let n = 0; n < 20; n++) await Promise.resolve(); };
async function main() {
  let now = 1000, failure = null, calls = 0;
  const timers = new Map(), streams = [], states = [], updates = [];
  let next = 0;
  let snapshot = {instance_id: 'first', sequence: 1, values: {
    live: {state: 'running', source_observed_at_ms: 900, view: {retained: 'not zero'}}}};
  const context = vm.createContext({Date, api: async () => {
    calls++; if (failure) throw new Error(failure); return structuredClone(snapshot);
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
  failure = 'network_error';
  await tick();
  assert.equal(states.at(-1).kind, 'offline');
  assert.match(states.at(-1).message, /OFFLINE — last observation/);
  assert.equal(states.at(-1).authenticatedAt, 21000, 'failed probes cannot freshen the timestamp');
  assert.equal(updates.at(-1).view.retained, 'not zero');
  streams[0].listeners.progress({lastEventId: 'first:4', data: '{"jobs":[]}'});
  assert.equal(states.at(-1).kind, 'offline', 'job progress cannot claim that a failed source/host check recovered');
  failure = null;
  snapshot.sequence++; snapshot.values.live.state = 'recovering';
  await tick();
  assert.equal(states.at(-1).kind, 'source_unavailable', 'working HTTP is not source readiness');
  snapshot.sequence++; snapshot.values.live.state = 'running';
  await tick();
  assert.equal(states.at(-1).kind, 'connected');
  assert.equal(streams.length, 1);
  vm.runInContext('connection.resync()', context);
  assert.equal(states.at(-1).kind, 'reconnecting', 'idle resume invalidates stale DOM before fetching');
  await turns();
  snapshot.instance_id = 'replacement';
  const count = updates.length;
  await tick();
  assert.equal(states.at(-1).kind, 'identity_changed');
  assert.equal(updates.length, count, 'different host values never enter the old page');
  assert.equal(timers.size, 0);
  assert.equal(streams[0].closed, true);
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
  assert.equal(states.at(-1).kind, 'connected');
  vm.runInContext('connection.close()', context);
  assert.equal(timers.size, 0);
  console.log('web connection passed: bounded watchdog, idle, source loss, auth, identity, terminal, initial recovery');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
