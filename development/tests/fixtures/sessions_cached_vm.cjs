const assert = require('node:assert/strict');

module.exports = async ({vm, context, Node}) => {
  const {document} = context;
  const calls = [];
  // Nothing paints in this VM, so post-paint demand hints stay queued and cancellable.
  const frames = new Map(); let frameId = 0;
  context.requestAnimationFrame = callback => { frames.set(++frameId, callback); return frameId; };
  context.cancelAnimationFrame = id => frames.delete(id);
  context.cachedApi = (path, request, signal) => new Promise(resolve => {
    calls.push({path, request, signal, resolve});
  });
  vm.runInContext('globalThis.cached = new SessionsCatalog.CachedView(cachedApi)', context);
  const view = context.cached;
  const query = new URLSearchParams('period=all&sort=prompts&direction=-1&offset=25');
  view.configure(query);
  view.attach(new Node('main'));
  const row = {session_id: 's-26', title: 'Saved 26', activity_ms: 1000000,
    prompts: 16, context_tokens: null, fields: {prompts: 'as-of', ctx: 'source-history-missing'}};
  const page = {size: 25, offset: 25, cached_total: 36, period: 'all', sort: 'prompts', direction: -1,
    start_ms: null, end_ms: null, timezone_id: 'UTC', binding: 'first', generation: 4, rows: [row]};
  calls[0].resolve(page);
  await new Promise(setImmediate);
  assert.match(view.label.textContent, /Showing 26–26 of 36 cached sessions/);
  assert.equal(view.body.children[0].metrics[4].textContent, '?');
  assert.equal(view.status.hidden, true);

  const same = view.poll();
  assert.equal(calls[1].request.known.generation, 4);
  const savedRow = view.body.children[0];
  document.activeElement = savedRow.name;
  calls[1].resolve({unchanged: true, binding: 'first', generation: 5});
  await same;
  assert.ok(view.body.children[0] === savedRow, 'unchanged pages keep their existing keyed DOM');
  assert.ok(document.activeElement === savedRow.name, 'unchanged pages preserve keyboard focus');

  const pending = view.poll();
  const pendingCall = calls[2];
  view.configure(new URLSearchParams('period=today&sort=ccost&direction=1'));
  const activeCall = calls[3];
  assert.equal(pendingCall.signal.aborted, true);
  activeCall.resolve({...page, offset: 0, period: 'today', sort: 'ccost', direction: 1, rows: [], cached_total: 0});
  pendingCall.resolve(page);
  await pending;
  await new Promise(setImmediate);
  assert.match(view.label.textContent, /No cached sessions yet/);
  assert.equal(view.headers.find(header => header.key === 'ccost').th.attributes['aria-sort'], 'ascending');
  assert.equal(view.next.disabled, true);
  assert.ok(calls.every(call => call.path === '/api/cache/sessions'));

  view.cacheHint({view: 'sessions', binding: null});
  assert.equal(view.data, null);
  assert.equal(view.label.textContent, 'Session cache unavailable.');
  view.detach();
};
