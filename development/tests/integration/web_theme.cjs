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
   element(tag, text) { const node = new Node(tag); node.textContent = text; return node; },
   setUnit(unit) { documentState.unit = unit; }
  }});
  vm.runInContext(fs.readFileSync('src/web/assets/settings.js', 'utf8'), context);
  const Settings = vm.runInContext('WebSettings', context);
  const defaults = {theme: 'classic', ccostDisplayUnit: 'credits', miniWatchPlacement: 'remember-last'};
  const inherited = {theme: 'default', ccostDisplayUnit: 'default', miniWatchPlacement: 'default'};
  const calls = []; let saved = {...inherited}, failure = null, release;
  const api = async (path, value) => {
    calls.push({path, value});
    if (failure) throw new Error(failure);
    if (value) { await new Promise(resolve => { release = resolve; }); saved = {...saved, ...value}; }
    return {webSettings: Object.fromEntries(Object.entries(saved).map(([key,value]) => [key,value === 'default' ? defaults[key] : value])),
      webSettingsChoices: {...saved}, webSettingsDefaults: {...defaults}};
  };
  const view = new Settings.View(api), output = new Node('div');
  const theme = view.controls.get('theme'), ccost = view.controls.get('ccostDisplayUnit'), placement = view.controls.get('miniWatchPlacement');
  assert.equal(view.controls.size, 3);
  assert.equal(view.root.children[0].textContent, 'Web settings');
  const save = select => select.events.change();
  view.attach(output); const root = output.firstChild;
  await view.read();
  assert.equal(theme.value, 'default'); assert.equal(ccost.value, 'default'); assert.equal(placement.value, 'default');
  assert.deepEqual(theme.children.map(option => [option.value,option.textContent]),
    [['default','Default (Classic)'],['classic','Classic'],['web','Web']]);
  assert.deepEqual(ccost.children.map(option => [option.value,option.textContent]),
    [['default','Default (Credits)'],['credits','Credits'],['usd','USD']]);
  assert.deepEqual(placement.children.map(option => [option.value,option.textContent]),
    [['default','Default (Remember last)'],['remember-last','Remember last'],['standard','Standard placement']]);
  theme.focus(); theme.value = 'web'; const pending = save(theme);
  assert.equal(theme.disabled, true); assert.equal(ccost.disabled, true);
  assert.equal(html.dataset.theme, 'classic', 'never optimistically claim saved theme');
  assert.match(view.feedback.textContent, /Saving/);
  release(); await pending;
  assert.equal(html.dataset.theme, 'web');
  assert.equal(documentState.activeElement, theme, 'save restores keyboard focus after native disabled blur');
  assert.equal(view.feedback.textContent, 'Theme saved.');
  const count = calls.length; await save(theme);
  assert.equal(calls.length, count, 'unchanged selection never writes');
  view.attach(output); assert.equal(output.firstChild, root, 'heartbeat retains native focus owner');
  for (const code of ['settings_conflict','settings_invalid_config','settings_not_writable','instance_stopping',
      'authentication_required','csrf_required','host_identity_changed','offline','AbortError']) {
    failure = code; theme.value = 'classic'; await save(theme);
    assert.equal(theme.value, 'web'); assert.equal(html.dataset.theme, 'web');
    assert.equal(view.feedback.className, 'error'); assert.doesNotMatch(view.feedback.textContent, /Theme saved/);
    assert.equal(theme.disabled, false);
    ccost.value = 'usd'; await save(ccost);
    assert.equal(ccost.value, 'default'); assert.equal(documentState.unit, 'credits');
    placement.value = 'standard'; await save(placement); assert.equal(placement.value, 'default');
  }
  failure = null;
  ccost.focus(); ccost.value = 'usd'; const ccostPending = save(ccost);
  assert.equal(documentState.unit, 'credits', 'CCost applies only after confirmed success');
  release(); await ccostPending;
  assert.equal(documentState.unit, 'usd'); assert.equal(html.dataset.theme, 'web');
  assert.equal(documentState.activeElement, ccost);
  assert.equal(view.feedback.textContent, 'CCost display saved.');
  // Default does not pin today's value; an equal explicit choice stays explicit.
  theme.value = 'default'; const inheritTheme = save(theme); release(); await inheritTheme;
  assert.equal(theme.value, 'default'); assert.equal(html.dataset.theme, 'classic');
  theme.value = 'classic'; const pinTheme = save(theme); release(); await pinTheme;
  assert.equal(theme.value, 'classic');
  defaults.theme = 'web'; await view.read();
  assert.equal(theme.value, 'classic'); assert.equal(theme.firstChild.textContent, 'Default (Web)');
  assert.equal(html.dataset.theme, 'classic');
  placement.value = 'remember-last'; const pinPlacement = save(placement); release(); await pinPlacement;
  assert.equal(placement.value, 'remember-last');
  saved = {...inherited}; defaults.theme = 'classic'; await view.read();
  assert.equal(html.dataset.theme, 'classic', 'external file edits apply on next read');
  const fresh = new Settings.View(api); await fresh.read();
  assert.equal(fresh.controls.get('theme').value, 'default', 'new view reads file rather than browser storage');
  assert.equal(fresh.controls.get('ccostDisplayUnit').value, 'default');
  failure = 'offline'; const unread = new Settings.View(api); await unread.read();
  assert.equal(unread.controls.get('theme').disabled, true, 'unconfirmed initial read cannot claim or write a choice');
  assert.throws(() => Settings.apply({webSettings: defaults}), /settings_unavailable/);
  assert.ok(calls.every(call => ['/api/settings', '/api/settings/theme', '/api/settings/ccost', '/api/settings/mini-placement'].includes(call.path)));
  assert.ok(calls.filter(call => call.value).every(call => Object.keys(call.value).length === 1));
  console.log('Web settings state machine passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
