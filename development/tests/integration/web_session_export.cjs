// Deterministic picker ordering, cancellation, write commit and URL lifecycle.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const order = [], downloads = [], timers = new Map();
class Node {
  constructor(text) { this.textContent = text; this.children = []; this.events = {}; this.attributes = {}; }
  setAttribute(key, value) { this.attributes[key] = value; }
  append(...nodes) { this.children.push(...nodes); }
  addEventListener(event, callback) { this.events[event] = callback; }
  remove() {}
  click() { order.push('download'); downloads.push(this.download); }
}
const window = {};
const context = vm.createContext({window, AbortController, TextEncoder, URL: {
  createObjectURL() { order.push('url'); return 'blob:owned'; },
  revokeObjectURL() { order.push('revoke'); }
}, ReportView: {element: (_, text) => new Node(text)}, ContextHelp: {
  attach(target, help, passive = false) { target.help = help; target.passive = passive; }, dismiss() {}
},
  setTimeout: callback => { timers.set(1, callback); return 1; }, clearTimeout: key => timers.delete(key)});
vm.runInContext(fs.readFileSync('src/web/assets/session-export.js', 'utf8') + '\nglobalThis.Action = SessionExport.Action;', context);
async function main() {
  const names = new context.Action(async () => {}, 'ses_test');
  names.update('selected', true, 'Ångström.zip');
  assert.equal(names.filename, 'Ångström.zip');
  names.update('new-selection', true);
  assert.equal(names.filename, 'session-ses_test.zip', 'new selection never inherits a title');
  names.update('new-selection', false, 'Unverified source');
  assert.equal(names.filename, 'session-ses_test.zip');
  let calls = 0;
  const action = new context.Action(async (path, body, signal, attachment) => {
    calls++; order.push('export'); assert.equal(path, '/api/detail/export'); assert.equal(body.token, 'selected');
    assert.equal(attachment, true); assert.equal(signal.aborted, false);
    return {blob: 'archive', filename: 'opencode-ses_test-analysis.zip'};
  }, 'ses_test');
  action.update('selected', true, 'FixAuthTests.zip');
  assert.equal(action.button.textContent, 'Export Session Analysis ZIP');
  assert.deepEqual(action.root.children, [action.button, action.spinner, action.notice]);
  assert.equal(action.notice.attributes.role, 'status'); assert.equal(action.notice.textContent, '');
  assert.equal(action.button.passive, false, 'the action itself owns non-pinning help');
  action.update('refreshed', true); assert.equal(action.notice.textContent, '', 'refresh cannot restore passive advice');
  action.update('selected', true, 'FixAuthTests.zip');
  window.showSaveFilePicker = async options => {
    order.push('picker'); assert.equal(options.suggestedName, 'FixAuthTests.zip');
    assert.deepEqual(Array.from(options.types[0].accept['application/zip']), ['.zip']);
    throw Object.assign(new Error(), {name: 'AbortError'});
  };
  const preparing = action.button.events.click();
  assert.equal(action.button.disabled, true); assert.equal(action.spinner.hidden, false);
  await action.button.events.click();
  await preparing;
  assert.deepEqual(order, ['export']); assert.equal(action.button.textContent, 'Save ZIP');
  assert.equal(action.spinner.hidden, true); assert.equal(action.button.disabled, false);
  const cancelled = action.button.events.click();
  assert.deepEqual(order, ['export', 'picker'], 'second click invokes the picker synchronously');
  await cancelled;
  assert.equal(calls, 1); assert.match(action.notice.textContent, /cancelled/);
  assert.equal(action.button.textContent, 'Export Session Analysis ZIP'); assert.equal(timers.size, 0);
  order.length = 0;
  window.showSaveFilePicker = async () => { order.push('picker'); return {createWritable: async () => ({
    async write(blob) { order.push('write'); assert.equal(blob, 'archive'); },
    async close() { order.push('commit'); }, async abort() { order.push('abort'); }
  })}; };
  await action.button.events.click(); await action.button.events.click();
  assert.deepEqual(order, ['export', 'picker', 'write', 'commit']);
  action.update('selected', true, 'Renamed å.zip'); assert.match(action.notice.textContent, /saved/, 'polling preserves action feedback');
  delete window.showSaveFilePicker; order.length = 0;
  await action.button.events.click(); await action.button.events.click();
  assert.deepEqual(order, ['export', 'url', 'download']);
  assert.deepEqual(downloads, ['Renamed å.zip'], 'fallback ignores trusted transport filename for its display name');
  assert.match(action.notice.textContent, /browser controls/);
  action.close(); assert.equal(order.at(-1), 'revoke'); assert.equal(timers.size, 0);
  for (const [available, token] of [[false, 'selected'], [true, null]]) {
    action.update(token, available); assert.equal(action.button.disabled, true);
    assert.equal(action.notice.textContent, '', 'passive export availability is silent');
  }
  for (const code of ['detail_expired', 'export_too_large', 'export_source_unavailable']) {
    const failed = new context.Action(async () => { throw new Error(code); }, 'ses_test');
    failed.update('selected', true); await failed.button.events.click();
    assert.equal(failed.spinner.hidden, true);
    assert.equal(failed.button.textContent, 'Export Session Analysis ZIP');
    assert.match(failed.notice.textContent, /expired|size limit|unavailable/); assert.equal(failed.button.disabled, false);
  }
  let finish;
  window.showSaveFilePicker = () => new Promise(resolve => { finish = resolve; });
  action.update('selected', true);
  await action.button.events.click();
  const pending = action.button.events.click(); action.close(); finish({}); await pending;
  assert.equal(action.notice.textContent, '', 'late picker result after navigation is silent');
  assert.equal(action.filename, 'session-ses_test.zip');
  action.update('selected', true, 'Old title');
  await action.button.events.click();
  action.update('other-token', true, 'New title');
  assert.equal(action.button.textContent, 'Export Session Analysis ZIP');
  assert.equal(timers.size, 0, 'new token retires the ready payload and expiry timer');
  action.update('selected', true);
  await action.button.events.click();
  const [expire] = timers.values(); expire();
  assert.equal(action.button.textContent, 'Export Session Analysis ZIP'); assert.match(action.notice.textContent, /expired/);
  window.showSaveFilePicker = async () => ({createWritable: async () => ({
    write: async () => {throw new Error('synthetic write failure');}, abort: async () => order.push('abort')
  })});
  await action.button.events.click(); await action.button.events.click();
  assert.equal(order.at(-1), 'abort'); assert.match(action.notice.textContent, /no completed export/);
  delete window.showSaveFilePicker;
  let complete;
  const late = new context.Action(() => new Promise(resolve => { complete = resolve; }), 'ses_other');
  late.update('old-token', true, 'Old session');
  const response = late.button.events.click();
  late.update('new-token', true, 'New session');
  complete({blob:'late', filename:'opencode-ses_other-analysis.zip'}); await response;
  assert.equal(late.button.textContent, 'Export Session Analysis ZIP'); assert.equal(late.notice.textContent, '');
  const wrong = new context.Action(async () => ({blob: 'other', filename:'opencode-ses_other-analysis.zip'}), 'ses_test');
  wrong.update('selected', true); await wrong.button.events.click();
  assert.match(wrong.notice.textContent,/invalid or incomplete/);
  assert.deepEqual(downloads, ['Renamed å.zip'], 'a stale or foreign export never saves');
  // Run the shipped attachment parser unchanged: a display name must not relax transport trust.
  const app = fs.readFileSync('src/web/assets/app.js','utf8');
  Object.assign(context,{hostState:{terminal:false},hostInstance:'owned-host',csrf:'owned-csrf',current:null,
    document:{hidden:false},connectionStatus(){},Response,fetch:async()=>context.response});
  vm.runInContext(app.slice(app.indexOf('async function api('),app.indexOf('\nfunction show('))+'\nglobalThis.request = api;',context);
  const headers = {'X-CG-Instance':'owned-host','Content-Type':'application/zip',
    'Content-Length':'2','Content-Disposition':'attachment; filename="opencode-ses_test-analysis.zip"'};
  context.response = new Response('PK',{headers});
  assert.equal((await context.request('/api/detail/export',{token:'selected'},undefined,true)).filename,'opencode-ses_test-analysis.zip');
  for (const invalid of [
    {'Content-Disposition':'attachment; filename="Title.zip"'},
    {'Content-Disposition':'attachment; filename="../opencode-ses_test-analysis.zip"'},
    {'Content-Length':'67108865'},{'Content-Length':'3'},{'Content-Type':'application/json'},
    {'X-CG-Instance':''}
  ]) {
    context.response = new Response('PK',{headers:{...headers,...invalid}});
    await assert.rejects(context.request('/api/detail/export',{token:'selected'},undefined,true),/export_invalid_response/);
  }
  console.log('PASS ZIP attachment validation, picker order/cancel/commit, fallback/revoke, selection retirement');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
