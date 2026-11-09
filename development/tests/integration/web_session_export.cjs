// Deterministic picker ordering, cancellation, write commit and URL lifecycle.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const order = [], timers = new Map();
class Node {
  constructor(text) { this.textContent = text; this.children = []; this.events = {}; this.attributes = {}; }
  setAttribute(key, value) { this.attributes[key] = value; }
  append(...nodes) { this.children.push(...nodes); }
  addEventListener(event, callback) { this.events[event] = callback; }
  remove() {}
  click() { order.push('download'); }
}
const window = {};
const context = vm.createContext({window, AbortController, URL: {
  createObjectURL() { order.push('url'); return 'blob:owned'; },
  revokeObjectURL() { order.push('revoke'); }
}, ReportView: {element: (_, text) => new Node(text)}, ContextHelp: {
  attach(target, help, passive = false) { target.help = help; target.passive = passive; }, dismiss() {}
},
  setTimeout: callback => { timers.set(1, callback); return 1; }, clearTimeout: key => timers.delete(key)});
vm.runInContext(fs.readFileSync('src/web/assets/session-export.js', 'utf8') + '\nglobalThis.Action = SessionExport.Action;', context);
async function main() {
  let calls = 0;
  const action = new context.Action(async (path, body, signal, attachment) => {
    calls++; order.push('export'); assert.equal(path, '/api/detail/export'); assert.equal(body.token, 'selected');
    assert.equal(attachment, true); assert.equal(signal.aborted, false);
    return {blob: 'sanitized', filename: 'opencode-ses_test-sanitized.json'};
  }, 'ses_test');
  action.update('selected', true);
  assert.equal(action.button.textContent, 'Export Sanitized JSON');
  assert.deepEqual(action.root.children, [action.button, action.notice], 'one action and one quiet live region');
  assert.equal(action.notice.attributes.role, 'status'); assert.equal(action.notice.textContent, '');
  assert.equal(action.button.passive, false, 'the action itself owns non-pinning help');
  assert.match(action.button.help, /redacts sensitive transcript and file data/);
  assert.match(action.button.help, /Review the file before sharing/);
  assert.match(action.button.help, /point-in-time snapshot/);
  assert.match(action.button.help, /otherwise your browser handles/);
  action.update('refreshed', true); assert.equal(action.notice.textContent, '', 'refresh cannot restore passive advice');
  action.update('selected', true);
  window.showSaveFilePicker = async options => {
    order.push('picker'); assert.equal(calls, 0); assert.match(options.suggestedName, /sanitized.json$/);
    throw Object.assign(new Error(), {name: 'AbortError'});
  };
  await action.save();
  assert.deepEqual(order, ['picker']); assert.equal(calls, 0); assert.match(action.notice.textContent, /cancelled/);
  order.length = 0;
  window.showSaveFilePicker = async () => { order.push('picker'); return {createWritable: async () => ({
    async write(blob) { order.push('write'); assert.equal(blob, 'sanitized'); },
    async close() { order.push('commit'); }, async abort() { order.push('abort'); }
  })}; };
  await action.save();
  assert.deepEqual(order, ['picker', 'export', 'write', 'commit']);
  action.update('selected', true); assert.match(action.notice.textContent, /saved/, 'polling preserves action feedback');
  delete window.showSaveFilePicker; order.length = 0;
  await action.save();
  assert.deepEqual(order, ['export', 'url', 'download']);
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
  console.log('PASS picker order/cancel/commit/fallback/revoke/selection retirement');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
