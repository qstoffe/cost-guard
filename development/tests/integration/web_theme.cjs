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
  querySelector(selector) {
    for (const child of this.children) {
      if (selector === '#' + child.id || selector === child.tag) return child;
      const found = child.querySelector(selector); if (found) return found;
    }
    return null;
  }
}
async function main() {
  const html = new Node('html'); html.dataset.theme = 'classic';
  documentState = {documentElement: html, body: new Node('body')};
  documentState.activeElement = documentState.body;
  const help = new Map();
  const context = vm.createContext({document: documentState, ContextHelp: {
    value(target, text) { help.set(target, text); }, attach(target, text) { help.set(target, text); }, dismiss() {}
  }, ReportView: {
   element(tag, text, className) { const node = new Node(tag); node.textContent = text; node.className = className; return node; },
    setUnit(unit) { documentState.unit = unit; },
    setQuotaMode(mode) { documentState.quotaMode = mode; }
  }});
  vm.runInContext(fs.readFileSync('src/web/assets/settings.js', 'utf8'), context);
  const Settings = vm.runInContext('WebSettings', context);
   const defaults = {theme: 'classic', ccostDisplayUnit: 'usd', miniWatchPlacement: 'remember-last', miniWatchSize: 'fit-on-open', quotaDisplayMode: 'used'};
   const inherited = {theme: 'default', ccostDisplayUnit: 'default', miniWatchPlacement: 'default', miniWatchSize: 'default', quotaDisplayMode: 'default'};
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
   const quota = view.controls.get('quotaDisplayMode');
   assert.equal(view.controls.size, 5);
   const size = view.controls.get('miniWatchSize');
  assert.equal(view.root['aria-label'], 'Settings');
  assert.equal(view.root.querySelector('h3'), null);
  assert.equal(view.root.querySelector('label').htmlFor, theme.id);
  assert.match(help.get(view.root.querySelector('label')), /Appearance.*Terminal colors/);
  assert.equal(view.enhanced, false, 'unsupported browsers retain native selects and a choice-help disclosure');
  assert.ok(view.root.querySelector('summary'));
  const save = select => select.events.change();
  view.attach(output); const root = output.firstChild;
  await view.read();
  assert.equal(theme.value, 'default'); assert.equal(ccost.value, 'default'); assert.equal(placement.value, 'default');
  assert.deepEqual(theme.children.map(option => [option.value,option.textContent]),
    [['default','Default (Classic)'],['classic','Classic'],['web','Web']]);
  assert.deepEqual(ccost.children.map(option => [option.value,option.textContent]),
    [['default','Default (USD)'],['credits','Credits'],['usd','USD']]);
   assert.match(help.get(ccost)(), /Follow the shipped default, currently USD.*US dollars, not actual charges/);
   assert.match(view.root.querySelector('#ccost-unit-default-help').textContent, /currently USD/);
   assert.equal(documentState.unit, 'usd');
   assert.deepEqual(placement.children.map(option => [option.value,option.textContent]),
     [['default','Default (Remember last)'],['remember-last','Remember last'],['standard','Standard position']]);
   assert.deepEqual(size.children.map(option => [option.value,option.textContent]),
     [['default','Default (Fit on open)'],['fit-on-open','Fit on open'],['remember-last','Remember last size']]);
   assert.deepEqual(quota.children.map(option => [option.value,option.textContent]),
      [['default','Default (Used)'],['used','Used'],['remaining','Remaining']]);
  assert.match(help.get(theme)(), /Follow the shipped default, currently Classic; do not pin/);
  assert.match(view.root.querySelector('#mini-size-fit-on-open-help').textContent, /two running prompts.*Live updates never resize/);
  assert.match(view.root.querySelector('#mini-size-fit-on-open-help').textContent, /both Earlier Sessions states.*CCost Today 90 000 · 999 prompts or wider real text/);
  assert.match(view.root.querySelector('#mini-size-fit-on-open-help').textContent, /rounding allowance and scrollbar space.*Real totals are unchanged/);
  assert.doesNotMatch(view.root.querySelector('#mini-size-fit-on-open-help').textContent, /650/);
  assert.match(view.root.querySelector('#mini-size-remember-last-help').textContent, /without forcing the minimal Fit opening width/);
  theme.focus(); theme.value = 'web'; const pending = save(theme);
  assert.equal(theme.disabled, true); assert.equal(ccost.disabled, true);
  assert.equal(html.dataset.theme, 'classic', 'never optimistically claim saved theme');
  assert.match(view.feedback.textContent, /Saving/);
  release(); await pending;
  assert.equal(html.dataset.theme, 'web');
  assert.equal(documentState.activeElement, theme, 'save restores keyboard focus after native disabled blur');
   assert.equal(view.feedback.textContent, 'Theme saved.');
  assert.match(help.get(theme)(), /system’s light or dark/);
  const count = calls.length; await save(theme);
  assert.equal(calls.length, count, 'unchanged selection never writes');
  view.attach(output); assert.equal(output.firstChild, root, 'heartbeat retains native focus owner');
  for (const code of ['settings_conflict','settings_invalid_config','settings_not_writable','instance_stopping',
      'authentication_required','csrf_required','host_identity_changed','offline','AbortError']) {
    failure = code; theme.value = 'classic'; await save(theme);
    assert.equal(theme.value, 'web'); assert.equal(html.dataset.theme, 'web');
    assert.equal(view.feedback.className, 'error'); assert.doesNotMatch(view.feedback.textContent, /Theme saved/);
    assert.equal(theme.disabled, false);
    ccost.value = 'credits'; await save(ccost);
    assert.equal(ccost.value, 'default'); assert.equal(documentState.unit, 'usd');
      placement.value = 'standard'; await save(placement); assert.equal(placement.value, 'default');
      size.value = 'remember-last'; await save(size); assert.equal(size.value, 'default');
     quota.value = 'remaining'; await save(quota); assert.equal(quota.value, 'default');
     assert.equal(documentState.quotaMode, 'used');
  }
  failure = null;
  ccost.focus(); ccost.value = 'credits'; const ccostPending = save(ccost);
  assert.equal(documentState.unit, 'usd', 'CCost applies only after confirmed success');
  release(); await ccostPending;
  assert.equal(documentState.unit, 'credits'); assert.equal(html.dataset.theme, 'web');
  assert.equal(documentState.activeElement, ccost);
  assert.equal(view.feedback.textContent, 'CCost display saved.');
  for (const choice of ['usd', 'default', 'credits']) {
    ccost.value = choice; const changed = save(ccost); release(); await changed;
    assert.equal(ccost.value, choice);
    assert.equal(documentState.unit, choice === 'default' ? 'usd' : choice);
  }
  // Default does not pin today's value; an equal explicit choice stays explicit.
  theme.value = 'default'; const inheritTheme = save(theme); release(); await inheritTheme;
  assert.equal(theme.value, 'default'); assert.equal(html.dataset.theme, 'classic');
  theme.value = 'classic'; const pinTheme = save(theme); release(); await pinTheme;
  assert.equal(theme.value, 'classic');
  defaults.theme = 'web'; await view.read();
  assert.equal(theme.value, 'classic'); assert.equal(theme.firstChild.textContent, 'Default (Web)');
  assert.match(view.root.querySelector('#web-theme-default-help').textContent, /currently Web.*system’s light or dark/);
  assert.match(help.get(theme)(), /dark, CLI-inspired/, 'explicit choice help does not follow a changed default');
  assert.equal(html.dataset.theme, 'classic');
  placement.value = 'remember-last'; const pinPlacement = save(placement); release(); await pinPlacement;
   assert.equal(placement.value, 'remember-last');
   quota.focus(); quota.value = 'remaining'; const remaining = save(quota);
   assert.equal(documentState.quotaMode, 'used'); release(); await remaining;
   assert.equal(documentState.quotaMode, 'remaining'); assert.equal(documentState.activeElement, quota);
   quota.value = 'used'; const pinUsed = save(quota); release(); await pinUsed;
   defaults.quotaDisplayMode = 'remaining'; await view.read();
   assert.equal(quota.value, 'used'); assert.equal(documentState.quotaMode, 'used');
   assert.equal(quota.firstChild.textContent, 'Default (Remaining)');
   quota.value = 'default'; const inheritQuota = save(quota); release(); await inheritQuota;
   assert.equal(documentState.quotaMode, 'remaining'); defaults.quotaDisplayMode = 'used';
  saved = {...inherited}; defaults.theme = 'classic'; await view.read();
  assert.equal(html.dataset.theme, 'classic', 'external file edits apply on next read');
  const fresh = new Settings.View(api); await fresh.read();
  assert.equal(fresh.controls.get('theme').value, 'default', 'new view reads file rather than browser storage');
  assert.equal(fresh.controls.get('ccostDisplayUnit').value, 'default');
  failure = 'offline'; const unread = new Settings.View(api); await unread.read();
  assert.equal(unread.controls.get('theme').disabled, true, 'unconfirmed initial read cannot claim or write a choice');
  assert.throws(() => Settings.apply({webSettings: defaults}), /settings_unavailable/);
   assert.ok(calls.every(call => ['/api/settings', '/api/settings/theme', '/api/settings/ccost', '/api/settings/mini-placement', '/api/settings/mini-size', '/api/settings/quota-display'].includes(call.path)));
  assert.ok(calls.filter(call => call.value).every(call => Object.keys(call.value).length === 1));
  console.log('Web settings state machine passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
