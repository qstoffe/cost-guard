// Deterministic DOM state, not visual/native browser evidence.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let documentState;
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.dataset = {}; this.events = {}; this.isConnected = true; }
  set disabled(value) { this._disabled = value; if (value && documentState?.activeElement === this) documentState.activeElement = documentState.body; }
  get disabled() { return this._disabled; }
  focus() { documentState.activeElement = this; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  get firstChild() { return this.children[0]; }
  setAttribute(key, value) { this[key] = value; }
  addEventListener(key, fn) { this.events[key] = fn; }
}
async function main() {
  const html = new Node('html'); html.dataset.theme = 'classic';
  documentState = {documentElement: html, body: new Node('body')};
  documentState.activeElement = documentState.body;
  const context = vm.createContext({document: documentState, ReportView: {
    element(tag, text) { const node = new Node(tag); node.textContent = text; return node; }
  }});
  vm.runInContext(fs.readFileSync('src/web/assets/settings.js', 'utf8'), context);
  const Theme = vm.runInContext('ThemeSettings', context);
  const calls = []; let saved = 'classic', failure = null, release;
  const api = async (path, value) => {
    calls.push({path, value});
    if (failure) throw new Error(failure);
    if (value) { await new Promise(resolve => { release = resolve; }); saved = value.webTheme; }
    return {webTheme: saved};
  };
  const view = new Theme.View(api), output = new Node('div');
  view.attach(output); const root = output.firstChild;
  await view.read();
  assert.equal(view.select.value, 'classic');
  view.select.focus(); view.select.value = 'web'; const pending = view.save();
  assert.equal(view.select.disabled, true);
  assert.equal(html.dataset.theme, 'classic', 'never optimistically claim saved theme');
  assert.match(view.feedback.textContent, /Saving/);
  release(); await pending;
  assert.equal(html.dataset.theme, 'web');
  assert.equal(documentState.activeElement, view.select, 'save restores keyboard focus after native disabled blur');
  assert.equal(view.feedback.textContent, 'Theme saved.');
  const count = calls.length; await view.save();
  assert.equal(calls.length, count, 'unchanged selection never writes');
  view.attach(output); assert.equal(output.firstChild, root, 'heartbeat retains native focus owner');
  for (const code of ['settings_conflict','settings_invalid_config','settings_not_writable','instance_stopping',
      'authentication_required','csrf_required','host_identity_changed','offline','AbortError']) {
    failure = code; view.select.value = 'classic'; await view.save();
    assert.equal(view.select.value, 'web'); assert.equal(html.dataset.theme, 'web');
    assert.equal(view.feedback.className, 'error'); assert.doesNotMatch(view.feedback.textContent, /Theme saved/);
    assert.equal(view.select.disabled, false);
  }
  failure = null; saved = 'classic'; await view.read();
  assert.equal(html.dataset.theme, 'classic', 'external file edits apply on next read');
  const fresh = new Theme.View(api); await fresh.read();
  assert.equal(fresh.select.value, 'classic', 'new view reads file rather than browser storage');
  assert.ok(calls.every(call => call.path === '/api/settings/theme'));
  assert.ok(calls.filter(call => call.value).every(call => Object.keys(call.value).join() === 'webTheme'));
  console.log('theme state machine passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
