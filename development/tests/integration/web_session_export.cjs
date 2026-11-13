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
  for (const [title, expected] of [
    ['Refactor authentication', 'Refactor authentication.json'],
    ['Fix:Auth|Tests?', 'FixAuthTests.json'],
    ['Översyn – åäö 🚀 👩‍💻', 'Översyn – åäö 🚀 👩‍💻.json'],
    ['  Internal  spaces! (v2)', '  Internal  spaces! (v2).json'],
    ['../a\\b/<c>"d*e', '..abcde.json'],
    ['title. . ', 'title.json'], ['a\u0000b\u007fc\u202ed\u2066e\ud800', 'abcde.json'],
    ...[null, '', '   ', '. .', '<>:|?*', 'CON', 'con.txt', 'COM1 .txt', 'LPT9.tar.gz', 'nul', 'aux.json', 'PRN']
      .map(title => [title, 'session-ses_test.json']),
    ['COM10', 'COM10.json'], ['a'.repeat(250), 'a'.repeat(200) + '.json'],
    ['🚀'.repeat(100), '🚀'.repeat(50) + '.json'],
    ['a'.repeat(199) + ' .tail', 'a'.repeat(199) + '.json']
  ]) {
    names.update('selected', true, title);
    assert.equal(names.filename, expected, String(title));
  }
  names.update('new-selection', true);
  assert.equal(names.filename, 'session-ses_test.json', 'new selection never inherits a title');
  names.update('new-selection', false, 'Unverified source');
  assert.equal(names.filename, 'session-ses_test.json');
  let calls = 0;
  const action = new context.Action(async (path, body, signal, attachment) => {
    calls++; order.push('export'); assert.equal(path, '/api/detail/export'); assert.equal(body.token, 'selected');
    assert.equal(attachment, true); assert.equal(signal.aborted, false);
    return {blob: 'sanitized', filename: 'opencode-ses_test-sanitized.json'};
  }, 'ses_test');
  action.update('selected', true, 'Fix:Auth|Tests?');
  assert.equal(action.button.textContent, 'Export Sanitized JSON');
  assert.deepEqual(action.root.children, [action.button, action.notice], 'one action and one quiet live region');
  assert.equal(action.notice.attributes.role, 'status'); assert.equal(action.notice.textContent, '');
  assert.equal(action.button.passive, false, 'the action itself owns non-pinning help');
  assert.match(action.button.help, /redacts sensitive transcript and file data/);
  assert.match(action.button.help, /Review the file before sharing/);
  assert.match(action.button.help, /point-in-time snapshot/);
  assert.match(action.button.help, /otherwise your browser handles/);
  action.update('refreshed', true); assert.equal(action.notice.textContent, '', 'refresh cannot restore passive advice');
  action.update('selected', true, 'Fix:Auth|Tests?');
  window.showSaveFilePicker = async options => {
    order.push('picker'); assert.equal(calls, 0); assert.equal(options.suggestedName, 'FixAuthTests.json');
    throw Object.assign(new Error(), {name: 'AbortError'});
  };
  const cancelled = action.save();
  assert.deepEqual(order, ['picker'], 'picker is invoked in the original click turn, not after an await');
  await cancelled;
  assert.deepEqual(order, ['picker']); assert.equal(calls, 0); assert.match(action.notice.textContent, /cancelled/);
  order.length = 0;
  window.showSaveFilePicker = async () => { order.push('picker'); return {createWritable: async () => ({
    async write(blob) { order.push('write'); assert.equal(blob, 'sanitized'); },
    async close() { order.push('commit'); }, async abort() { order.push('abort'); }
  })}; };
  await action.save();
  assert.deepEqual(order, ['picker', 'export', 'write', 'commit']);
  action.update('selected', true, 'Renamed å'); assert.match(action.notice.textContent, /saved/, 'polling preserves action feedback');
  delete window.showSaveFilePicker; order.length = 0;
  await action.save();
  assert.deepEqual(order, ['export', 'url', 'download']);
  assert.deepEqual(downloads, ['Renamed å.json'], 'fallback ignores trusted transport filename for its display name');
  assert.match(action.notice.textContent, /browser controls/);
  action.close(); assert.equal(order.at(-1), 'revoke'); assert.equal(timers.size, 0);
  for (const [available, token] of [[false, 'selected'], [true, null]]) {
    action.update(token, available); assert.equal(action.button.disabled, true);
    assert.match(action.notice.textContent, /Export unavailable/);
  }
  for (const code of ['detail_expired', 'export_too_large', 'export_source_unavailable']) {
    const failed = new context.Action(async () => { throw new Error(code); }, 'ses_test');
    failed.update('selected', true); await failed.save();
    assert.match(failed.notice.textContent, /expired|16 MiB|unavailable/); assert.equal(failed.button.disabled, false);
  }
  let finish;
  window.showSaveFilePicker = () => new Promise(resolve => { finish = resolve; });
  action.update('selected', true);
  const pending = action.save(); action.close(); finish({}); await pending;
  assert.equal(calls, 2, 'navigation while picker is open starts no native read');
  assert.equal(action.filename, 'session-ses_test.json');
  action.update('selected', true, 'Old title');
  const switched = action.save();
  action.update('other-token', true, 'New title'); finish({}); await switched;
  assert.equal(calls, 2, 'token replacement while picker is open starts no native read');
  delete window.showSaveFilePicker;
  let complete;
  const late = new context.Action(() => new Promise(resolve => { complete = resolve; }), 'ses_other');
  late.update('old-token', true, 'Old session');
  const response = late.save();
  late.update('new-token', true, 'New session');
  complete({blob:'late', filename:'opencode-ses_other-sanitized.json'}); await response;
  assert.deepEqual(downloads, ['Renamed å.json'], 'late export cannot save under another selection');
  // Run the shipped attachment parser unchanged: a display name must not relax transport trust.
  const app = fs.readFileSync('src/web/assets/app.js','utf8');
  Object.assign(context,{hostState:{terminal:false},hostInstance:'owned-host',csrf:'owned-csrf',current:null,
    document:{hidden:false},connectionStatus(){},Response,fetch:async()=>context.response});
  vm.runInContext(app.slice(app.indexOf('async function api('),app.indexOf('\nfunction show('))+'\nglobalThis.request = api;',context);
  const headers = {'X-CG-Instance':'owned-host','Content-Type':'application/json; charset=utf-8',
    'Content-Length':'2','Content-Disposition':'attachment; filename="opencode-ses_test-sanitized.json"'};
  context.response = new Response('{}',{headers});
  assert.equal((await context.request('/api/detail/export',{token:'selected'},undefined,true)).filename,'opencode-ses_test-sanitized.json');
  for (const invalid of [
    {'Content-Disposition':'attachment; filename="Title.json"'},
    {'Content-Disposition':'attachment; filename="../opencode-ses_test-sanitized.json"'},
    {'Content-Length':'16777217'},{'Content-Length':'3'},{'Content-Type':'text/plain'},
    {'X-CG-Instance':''}
  ]) {
    context.response = new Response('{}',{headers:{...headers,...invalid}});
    await assert.rejects(context.request('/api/detail/export',{token:'selected'},undefined,true),/export_invalid_response/);
  }
  console.log('PASS safe title names/Unicode/limits/picker order/cancel/commit/fallback/revoke/selection retirement');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
