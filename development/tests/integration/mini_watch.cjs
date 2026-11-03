// Deterministic window/DOM seam. This does not claim browser-owned PiP or OS proof.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.dataset = {}; this.attributes = {}; this.events = {}; this.text = ''; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(child => child.textContent).join(''); }
  append(...children) { for (const child of children) { child.remove(); child.parentNode = this; this.children.push(child); } }
  replaceChildren(...children) { for (const child of this.children) child.parentNode = null; this.children = []; this.text = ''; this.append(...children); }
  remove() { if (this.parentNode) this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1); this.parentNode = null; }
  insertBefore(child, before) { child.remove(); child.parentNode = this; this.children.splice(before ? this.children.indexOf(before) : this.children.length, 0, child); }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(name, callback) { (this.events[name] ||= []).push(callback); }
  fire(name) { for (const callback of this.events[name] || []) callback(); }
}
function doc() { return {createElement: tag => new Node(tag), head: new Node('head'), body: new Node('body'), documentElement: new Node('html')}; }
function win() {
  const node = new Node('window'); node.document = doc(); node.closed = false; node.timers = new Set();
  node.setInterval = callback => {node.timers.add(callback); return callback;};
  node.clearInterval = callback => node.timers.delete(callback);
  node.close = () => {node.closed = true;}; // Deliberately defer pagehide to reproduce stale callbacks.
  return node;
}
let now = 1000;
const context = vm.createContext({document: doc(), window: {}, URL, Date: {now: () => now}, input});
for (const file of ['render', 'mini']) vm.runInContext(fs.readFileSync(`src/web/assets/${file}.js`, 'utf8'), context);
const Controller = vm.runInContext('MiniWatch.Controller', context);
function setup() {
  const owner = win(); owner.top = owner; owner.isSecureContext = true; owner.location = {href: 'http://127.0.0.1:1234/#/watch'};
  let resolve, reject, calls = 0, focused = 0, returned = 0;
  owner.focus = () => focused++;
  owner.document.documentElement.dataset.theme = 'classic';
  const api = owner.documentPictureInPicture = {window: null, requestWindow() {
    calls++; return new Promise((yes, no) => {resolve = yes; reject = no;});
  }};
  const button = new Node('button'), feedback = new Node('span');
  const controller = new Controller(owner, button, feedback, () => returned++);
  return {owner, api, button, feedback, controller, calls: () => calls, focused: () => focused, returned: () => returned,
    opened: value => {api.window = value; resolve(value);}, reject: () => reject(new Error('denied'))};
}
(async () => {
  const test = setup(), {controller, button, feedback, owner, api} = test;
  assert.equal(test.calls(), 0, 'no automatic opening or preference restore');
  controller.update(input); controller.health({kind: 'connected'});
  const first = controller.toggle();
  assert.equal(button.textContent, 'Mini Watch: Off', 'pending is not On');
  await controller.toggle(); await controller.toggle();
  assert.equal(test.calls(), 1, 'rapid clicks never duplicate in-flight windows');
  const cancelled = win(); test.opened(cancelled); await first;
  assert.equal(cancelled.closed, true); assert.equal(button.textContent, 'Mini Watch: Off');
  const failed = controller.toggle(); test.reject(); await failed;
  assert.match(feedback.textContent, /could not open/); assert.equal(button.textContent, 'Mini Watch: Off');
  const opening = controller.toggle(), child = win(); test.opened(child); await opening;
  assert.equal(button.textContent, 'Mini Watch: On'); assert.equal(button.attributes['aria-pressed'], 'true');
  let view = controller.view;
  assert.equal(view.doc.documentElement.dataset.theme, 'classic');
  assert.equal(view.values[0].textContent, '2'); assert.equal(view.values[1].textContent, '4'); assert.equal(view.values[2].textContent, '20m');
  assert.equal(view.health.textContent, 'Live');
  assert.equal(child.document.head.children.length, 2);
  assert.deepEqual(child.document.head.children.map(n => n.href), ['http://127.0.0.1:1234/app.css', 'http://127.0.0.1:1234/mini.css']);
  assert.equal(view.accounts.children.length, 6);
  assert.match(view.accounts.textContent, /GitHub Copilot Pro · 8.4% used \(1814\)/);
  assert.match(view.accounts.textContent, /Primary temporarily missing · Usage unavailable \(—\)/);
  assert.match(view.accounts.textContent, /OpenAI Pro Lite · 42% used \(—\)/);
  assert.ok(!/Reset|Weekly|Today|Provisional/.test(view.accounts.textContent));
  const retained = view.accounts.children[0]; controller.update(input);
  assert.equal(view.accounts.children[0], retained, 'independent keyed DOM survives refresh');
  const primary = input.view.accounts.accounts[0].primary, savedCost = primary.cost;
  primary.estimated = true; primary.cost = {...savedCost,complete:false,display:{known_ccost:'?1814'}};
  controller.update(input); assert.match(retained.textContent,/8.4% used \(~\?1814\)/);
  assert.match(retained.title,/estimated account attribution.*partial pricing/);
  primary.cost = {...savedCost,priced_requests:0};
  controller.update(input); assert.match(retained.textContent,/8.4% used \(—\)/,'known percentage survives unknown pricing');
  primary.estimated = false; primary.cost = savedCost; controller.update(input);
  vm.runInContext('ReportView.setUnit("usd")', context); owner.document.documentElement.dataset.theme = 'web'; controller.settings();
  assert.equal(view.values[1].textContent, '$0.04'); assert.match(retained.textContent, /\(\$18.14\)/);
  assert.equal(child.document.documentElement.dataset.theme, 'web');
  for (const kind of ['reconnecting', 'offline', 'source_unavailable', 'authorization_required', 'identity_changed', 'stopped']) {
    controller.health({kind}); assert.match(view.health.textContent, /not live/); assert.equal(view.values[2].textContent, '20m');
  }
  controller.health({kind: 'connected'}); now += 16000;
  [...child.timers][0](); assert.match(view.health.textContent, /Waiting for live update · not live/);
  controller.update(input); assert.match(view.health.textContent, /not live/, 'progress/repeated snapshot is not new Live evidence');
  input.view.now_ms++;
  controller.update(input); assert.equal(view.health.textContent, 'Live');
  controller.update({...input, state: 'recovering'}); assert.match(view.health.textContent, /not live/);
  controller.update(input);
  view.summary.fire('click'); assert.equal(test.returned(), 1); assert.equal(test.focused(), 1);
  assert.equal(child.closed, false, 'return selects existing tab without closing Mini');
  view.doc.body.children[0].children[0].children[1].fire('click');
  assert.equal(child.closed, true); assert.equal(test.focused(), 1, 'close does not also focus the owner');
  assert.equal(child.timers.size, 0); assert.equal(button.textContent, 'Mini Watch: Off');
  const reopen = controller.toggle(), second = win(); test.opened(second); await reopen;
  child.fire('pagehide'); assert.equal(button.textContent, 'Mini Watch: On', 'late old pagehide cannot retire a new window');
  second.close(); second.fire('pagehide'); assert.equal(button.textContent, 'Mini Watch: Off', 'native close');
  const replaceOpen = controller.toggle(), replaced = win(); test.opened(replaced); await replaceOpen;
  api.window = win(); controller.update(input); assert.equal(button.textContent, 'Mini Watch: Off', 'ownership replacement');
  assert.equal(replaced.timers.size, 0);
  const reloadOpen = controller.toggle(), reloadChild = win(); test.opened(reloadChild); await reloadOpen;
  owner.fire('pagehide'); assert.equal(reloadChild.closed, true); assert.equal(button.textContent, 'Mini Watch: Off');
  await controller.toggle(); assert.equal(test.calls(), 6, 'ended owner cannot reopen');
  const pendingClose = setup(); const promise = pendingClose.controller.toggle(); pendingClose.owner.fire('pagehide');
  const late = win(); pendingClose.opened(late); await promise; assert.equal(late.closed, true);
  for (const change of [owner => {owner.isSecureContext = false;}, owner => {delete owner.documentPictureInPicture;},
      owner => {owner.top = {};}, owner => {owner.document.permissionsPolicy = {allowsFeature: () => false};}]) {
    const item = setup(); change(item.owner);
    const disabled = new Controller(item.owner, item.button, item.feedback, () => {});
    assert.equal(item.button.disabled, true); assert.ok(item.feedback.textContent); await disabled.toggle(); assert.equal(item.calls(), 0);
  }
  console.log('Mini Watch VM: lifecycle/races, units/theme, native callbacks, fresh/retained states and independent DOM passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
