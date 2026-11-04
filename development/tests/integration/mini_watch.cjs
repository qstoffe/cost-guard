// Deterministic window/DOM seam. This does not claim browser-owned PiP or OS proof.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.dataset = {}; this.attributes = {}; this.events = {}; this.text = ''; this.style = {setProperty() {}}; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(child => child.textContent).join(''); }
  append(...children) { for (const child of children) { child.remove(); child.parentNode = this; this.children.push(child); } }
  replaceChildren(...children) { for (const child of this.children) child.parentNode = null; this.children = []; this.text = ''; this.append(...children); }
  remove() { if (this.parentNode) this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1); this.parentNode = null; }
  insertBefore(child, before) { child.remove(); child.parentNode = this; this.children.splice(before ? this.children.indexOf(before) : this.children.length, 0, child); }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(name, callback) { (this.events[name] ||= []).push(callback); }
  fire(name) { for (const callback of this.events[name] || []) callback(); }
  contains(node) { return node === this || this.children.some(child => child.contains(node)); }
  querySelectorAll(tag) { return this.children.flatMap(child => [...(child.tag === tag ? [child] : []), ...child.querySelectorAll(tag)]); }
}
function doc() { return {createElement: tag => new Node(tag), head: new Node('head'), body: new Node('body'), documentElement: new Node('html')}; }
function win() {
  const node = new Node('window'); node.document = doc(); node.closed = false; node.timers = new Set();
  node.setInterval = callback => {node.timers.add(callback); return callback;};
  node.clearInterval = callback => node.timers.delete(callback);
  node.close = () => {node.closed = true;}; // Deliberately defer pagehide to reproduce stale callbacks.
  node.resizeTo = () => {throw new Error('Opening consumes activation; resizeTo requires a new PiP gesture');};
  node.matchMedia = () => ({addEventListener() {},removeEventListener() {}});
  return node;
}
let now = 1000;
class Clock extends Date { static now() { return now; } }
const context = vm.createContext({document: doc(), window: win(), URL, Date: Clock, input});
for (const file of ['render', 'watch', 'mini']) vm.runInContext(fs.readFileSync(`src/web/assets/${file}.js`, 'utf8'), context);
const Controller = vm.runInContext('MiniWatch.Controller', context);
function setup() {
  const owner = win(); owner.top = owner; owner.isSecureContext = true; owner.location = {href: 'http://127.0.0.1:1234/#/watch'};
  let resolve, reject, calls = 0, focused = 0, returned = 0;
  owner.focus = () => focused++;
  owner.document.documentElement.dataset.theme = 'classic';
  const api = owner.documentPictureInPicture = {window: null, requests: [], requestWindow(options) {
    api.requests.push(options); calls++; return new Promise((yes, no) => {resolve = yes; reject = no;});
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
  assert.equal(view.body.children.length, 2);
  assert.equal(view.body.children[0].children[1].textContent, '#23');
  assert.equal(view.body.children[0].children[2].textContent, '2');
  assert.equal(view.body.children[1].children[2].textContent, '3');
  assert.equal(view.body.children[1].children[3].textContent, '20m');
  assert.equal(view.health.textContent, ''); assert.equal(view.health.hidden, true);
  const table = view.prompts.querySelectorAll('table')[0], headers = table.querySelectorAll('th');
  assert.equal(headers[4].textContent, 'CTX');
  assert.equal(headers[4].title, 'Estimated next incoming context for this prompt; N/A means unavailable');
  assert.match(table.attributes['aria-label'], /estimated next incoming context \(CTX\)/);
  const contextItem = input.view.active_cards[0].rows[0], originalContext = contextItem.live_context;
  for (const formatted of ['123 456', '234 567', '0', 'N/A', '~source-format']) {
    contextItem.live_context = {display:{watch_next_context_tokens:formatted}};
    controller.update(input);
    assert.equal(view.body.children[0].children[4].textContent, formatted, 'CTX uses the source format without adding or stripping characters');
  }
  contextItem.live_context = null; controller.update(input);
  assert.equal(view.body.children[0].children[4].textContent, 'N/A');
  contextItem.live_context = originalContext; controller.update(input);
  assert.equal(view.daily.textContent, 'CCost Today 34 · 37 prompts', 'prior activity is not the two prompt rows or account-period costs');
  assert.match(view.daily.attributes['aria-label'], /^CCost Today 34 · 37 prompts\. Global configured local-day CCost/);
  assert.notEqual(view.daily.parentNode, view.summary, 'daily metric is outside the navigation target');
  view.daily.fire('click'); view.daily.fire('keydown'); assert.equal(test.returned(),0);
  assert.equal(api.requests[0].height,250); assert.equal(api.requests[0].width,560);
  assert.equal(api.requests[0].preferInitialWindowPlacement,true);
  context.fullParent = new Node('div'); context.fullState = {connection:'Live connected.'};
  const daily = input.view.daily_usage;
  function parity() {
    controller.update(input);
    const full = vm.runInContext('ReportView.renderLive(fullParent, input, fullState); fullState.watch.daily',context);
    assert.equal(full.children[0].textContent, 'CCost Today');
    assert.equal(full.attributes['aria-label'], 'CCost Today');
    assert.ok(view.daily.textContent.startsWith(`CCost Today ${full.children[1].textContent} · ${full.children[2].textContent}`));
  }
  parity();
  for (const [value,count,credit,usd] of [['6152',106,'6 152','$61.52'],['0',0,'0','$0.00']]) {
    input.view.daily_usage = {...daily,prompt_count:count,total:{...daily.total,known_ccost:value,observed_requests:count,priced_requests:count,
      display:{known_ccost:credit},display_units:{credits:{known_ccost:credit},usd:{known_ccost:usd}}}};
    parity(); assert.equal(view.daily.textContent,`CCost Today ${credit} · ${count} prompts`);
    vm.runInContext('ReportView.setUnit("usd")', context); controller.settings(); parity();
    assert.equal(view.daily.textContent,`CCost Today ${usd} · ${count} prompts`);
    vm.runInContext('ReportView.setUnit("credits")', context);
  }
  input.view.daily_usage = {...daily,total:{...daily.total,priced_requests:0,complete:false}};
  parity(); assert.equal(view.daily.textContent,'CCost Today N/A · 37 prompts');
  assert.match(view.daily.title,/Partial pricing/);
  input.view.daily_usage = {...daily,total:{...daily.total,complete:false}};
  parity(); assert.equal(view.daily.textContent,'CCost Today 34 · 37 prompts');
  for (const state of ['retrying','unavailable','loading','partial']) {
    input.view.daily_state=state; parity(); assert.equal(view.daily.textContent,'CCost Today 34 · 37 prompts');
    assert.equal(view.daily.className,'mini-daily'); assert.equal(view.health.hidden,true);
  }
  input.view.daily_usage=null; input.view.daily_state='unavailable'; controller.update(input); assert.equal(view.daily.textContent,'CCost Today · Loading…');
  input.view.daily_state='loading'; controller.update(input); assert.equal(view.daily.textContent,'CCost Today · Loading…');
  input.view.daily_usage={...daily,day_start_ms:daily.day_start_ms+86400000,day_end_ms:daily.day_end_ms+86400000,prompt_count:0,total:{...daily.total,observed_requests:0,priced_requests:0,display:{known_ccost:'0'},display_units:{credits:{known_ccost:'0'}}}};
  input.view.daily_state='observed'; parity(); assert.equal(view.daily.textContent,'CCost Today 0 · 0 prompts','new canonical local day replaces the old daily observation');
  input.view.daily_usage=daily; parity(); assert.equal(view.daily.textContent,'CCost Today 34 · 37 prompts','later source corrections replace, never accumulate');
  assert.ok(!/Running prompts|Running CCost|Longest running|×/.test(view.root.textContent));
   assert.equal(child.document.head.children.length, 3);
   assert.deepEqual(child.document.head.children.map(n => [n.rel, n.type, n.href]), [
     ['icon', 'image/x-icon', 'http://127.0.0.1:1234/favicon-cg1.ico'],
     ['stylesheet', undefined, 'http://127.0.0.1:1234/app.css'], ['stylesheet', undefined, 'http://127.0.0.1:1234/mini.css']]);
   assert.equal(owner.document.head.children.length, 0, 'Mini never changes the owning tab head');
  assert.equal(view.accounts.children.length, 6);
  assert.match(view.accounts.textContent, /GitHub Copilot Pro · 8.4% used \(1814\)/);
  assert.match(view.accounts.textContent, /Primary temporarily missing · Usage unavailable \(—\)/);
  assert.match(view.accounts.textContent, /OpenAI Pro Lite · 42% used \(—\)/);
  assert.ok(!/Reset|Weekly|Today|Provisional/.test(view.accounts.textContent));
  const retained = view.accounts.children[0]; controller.update(input);
  assert.equal(view.accounts.children[0], retained, 'independent keyed DOM survives refresh');
  const firstRow = view.body.children[0], firstCell = firstRow.children[0], originals = input.view.active_cards;
  const prompt = originals[1].rows[0].prompt;
  input.view.active_cards = [originals[1], originals[0], originals[0], {session_id:'pending',focal_id:'',rows:[]}];
  controller.update(input);
  assert.equal(view.body.children.length, 2, 'deduplicated by source session and event, not aggregate count');
  assert.equal(view.body.children[0], firstRow, 'canonical ascending start order and keyed row');
  assert.equal(firstRow.children[0], firstCell, 'focusable title cell survives updates');
  for (const [outcome, className, label] of [
    [{in_progress:false,completed_successfully:true},'mini-success','Completed'],
    [{in_progress:false,completed_successfully:false,aborted:true,abort_reason:'quota_limit'},'mini-error','Aborted · quota limit'],
    [{in_progress:false,completed_successfully:false,aborted:false,has_error:true},'mini-error','Error'],
    [{in_progress:false,completed_successfully:false,aborted:false,has_error:false},'','Ended']]) {
    const saved = {...prompt}; Object.assign(prompt, outcome); controller.update(input);
    const terminal = view.body.children[1];
    assert.equal(terminal.className,className); assert.ok(terminal.title.startsWith(label));
    assert.equal(terminal.children[3].textContent,'20m'); Object.assign(prompt,saved);
  }
  input.view.active_cards = []; controller.update(input);
  assert.match(view.body.textContent,/No running or recently ended prompts/);
  input.view.active_cards = originals; controller.update(input);
  const accountItems = input.view.accounts.accounts;
  input.view.accounts.accounts = [...accountItems].reverse(); controller.update(input);
  assert.equal(view.accounts.children.at(-1),retained,'provider-aware account key survives reorder');
  input.view.accounts.accounts = accountItems; controller.update(input);
  const primary = input.view.accounts.accounts[0].primary, savedCost = primary.cost;
  primary.estimated = true; primary.cost = {...savedCost,complete:false,display:{known_ccost:'?1814'},display_units:{credits:{known_ccost:'?1814'}}};
  controller.update(input); assert.match(retained.textContent,/8.4% used \(\?1814\)/);
  assert.match(retained.title,/Estimated account attribution.*partial pricing/);
  assert.ok(!retained.textContent.includes('~'));
  assert.equal(retained.children[1].value, primary.used_fraction);
  const quota = {...primary.quota}, saved = {...primary};
  for (const [fraction, exhausted] of [['0',false],['0.5',false],['0.99999',false],['1',true],[null,false]]) {
    primary.used_fraction = fraction; primary.exhausted = exhausted; controller.update(input);
    assert.equal(retained.children[1].hidden,fraction == null);
    assert.equal(retained.children[1].className,exhausted ? 'mini-exhausted' : '');
  }
  primary.quota.unlimited = true; controller.update(input);
  assert.equal(retained.children[1].hidden,true); assert.match(retained.textContent,/Unlimited/);
  Object.assign(primary,saved); Object.assign(primary.quota,quota);
  primary.cost = {...savedCost,priced_requests:0};
  controller.update(input); assert.match(retained.textContent,/8.4% used \(—\)/,'known percentage survives unknown pricing');
  primary.estimated = false; primary.cost = savedCost; controller.update(input);
  vm.runInContext('ReportView.setUnit("usd")', context); owner.document.documentElement.dataset.theme = 'web'; controller.settings();
  assert.equal(view.body.children[0].children[2].textContent, '$0.01'); assert.match(retained.textContent, /\(\$18.14\)/);
  assert.equal(child.document.documentElement.dataset.theme, 'web');
  assert.equal(view.daily.textContent,'CCost Today $0.34 · 37 prompts');
  for (const kind of ['reconnecting', 'offline', 'source_unavailable', 'authorization_required', 'identity_changed', 'stopped']) {
    controller.health({kind});
    assert.equal(view.health.hidden, ['reconnecting','offline','source_unavailable'].includes(kind));
    if (!view.health.hidden) assert.match(view.health.textContent,/return to|reopen|restart/);
    assert.equal(view.body.children[1].children[3].textContent, '20m');
    assert.equal(view.daily.textContent,'CCost Today $0.34 · 37 prompts'); assert.match(view.daily.title,/retained observation/);
  }
  controller.health({kind: 'connected'}); now += 16000;
  [...child.timers][0](); assert.equal(view.health.hidden,true); assert.equal(view.root.dataset.live,'false');
  assert.equal(view.daily.textContent,'CCost Today $0.34 · 37 prompts');
  controller.update(input); assert.equal(view.root.dataset.live,'false', 'progress/repeated snapshot is not new Live evidence');
  input.view.now_ms++;
  controller.update(input); assert.equal(view.health.textContent, '');
  controller.update({...input, state: 'recovering'}); assert.equal(view.health.hidden,true); assert.equal(view.root.dataset.live,'false');
  controller.update(input);
  // A failed/partial read cannot erase rows or advance the independent clocks.
  const retainedText = view.body.textContent, beforeDaily = view.daily.textContent;
  const healthy = JSON.parse(JSON.stringify(input));
  input.view = {...input.view,active_cards:[],cards_state:'unavailable',daily_state:'retrying',quota_stale:true,
    daily_usage:{...daily,total:{...daily.total,display_units:{usd:{known_ccost:'$999'}}}}};
  controller.update(input); assert.equal(view.body.textContent,retainedText); assert.equal(view.daily.textContent,beforeDaily);
  assert.ok(!/quota stale|Partial|Not current/.test(view.root.textContent));
  now = 600999; controller.health({kind:'reconnecting'}); assert.equal(view.health.hidden,true);
  now = 601000; controller.update(input); assert.equal(view.health.textContent,'Updates unavailable · showing last values');
  const warning = view.health.textContent; now += 5000; controller.health({kind:'connected'});
  input.view.now_ms++; controller.update(input); assert.equal(view.health.textContent,warning,'retry publications cannot fake recovery');
  assert.equal(view.body.textContent,retainedText); assert.match(view.prompts.title,/Retained values are not new live observations/);
  input.view = {...healthy.view,now_ms:healthy.view.now_ms+2,
    daily_usage:{...daily,observed_at_ms:daily.observed_at_ms+1},accounts:{...healthy.view.accounts,accounts:healthy.view.accounts.accounts.map(item =>
      ({...item,observation:{...item.observation,observed_at_ms:item.observation.observed_at_ms+1}}))}};
  controller.update(input); assert.equal(view.health.hidden,true,'genuinely usable recovery clears the one status');
  input.view = {...input.view,active_cards:[],cards_state:'observed',now_ms:input.view.now_ms+1};
  controller.update(input); assert.match(view.body.textContent,/No running or recently ended prompts/,'valid empty evicts retained rows');
  input.view = {...input.view,active_cards:originals,daily_usage:{...daily,day_end_ms:now+1}};
  controller.update(input); assert.equal(view.daily.textContent,beforeDaily);
  now++; [...child.timers][0](); assert.equal(view.daily.textContent,'CCost Today · Loading…','no yesterday total after configured midnight, even disconnected');
  input.view = {...healthy.view,now_ms:healthy.view.now_ms+3}; controller.update(input);
  view.summary.fire('click'); assert.equal(test.returned(), 1); assert.equal(test.focused(), 1);
  assert.equal(child.closed, false, 'return selects existing tab without closing Mini');
  await controller.toggle();
  assert.equal(child.closed, true); assert.equal(test.focused(), 1, 'close does not also focus the owner');
  assert.equal(child.timers.size, 0); assert.equal(button.textContent, 'Mini Watch: Off');
   const reopen = controller.toggle(), second = win(); test.opened(second); await reopen;
   assert.equal(api.requests.at(-1).height,250,'reopening requests the compact size again');
   assert.equal(second.document.head.children.filter(n => n.rel === 'icon').length, 1);
   assert.equal(second.document.head.children[0].href, 'http://127.0.0.1:1234/favicon-cg1.ico');
   assert.notEqual(second.document.head.children[0], child.document.head.children[0], 'each PiP document owns its link');
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
  // Independent acquisition lanes: prompt progress cannot hide a stuck Daily read.
  const lane = setup().controller, start = now, value = JSON.parse(JSON.stringify(healthy));
  lane.update(value);
  const before = lane.observations.view.accounts.accounts[0];
  value.view = {...value.view,daily_state:'retrying',accounts:{...value.view.accounts,accounts:value.view.accounts.accounts.map((item,index)=>
    index ? item : {...item,observation:{...item.observation,availability:'unavailable'},primary:{...item.primary,used_percent:'—',used_fraction:null}})}};
  lane.update(value);
  assert.equal(lane.observations.view.accounts.accounts[0].primary.used_percent,before.primary.used_percent,'failed quota reads keep real percentages');
  assert.equal(lane.observations.view.accounts.accounts[0].observation.availability,'unavailable','retention does not invent quota freshness');
  now = start+599999; value.view = {...healthy.view,now_ms:healthy.view.now_ms+5,daily_state:'retrying',
    accounts:{...healthy.view.accounts,accounts:healthy.view.accounts.accounts.map(item=>
      ({...item,observation:{...item.observation,observed_at_ms:item.observation.observed_at_ms+1}}))}};
  lane.update(value); assert.equal(lane.observations.delayed(now),false);
  now++; value.view.now_ms++; lane.update(value);
  assert.equal(lane.observations.delayed(now),true,'healthy prompt publications do not reset the daily failure clock');
  value.view = {...value.view,daily_state:'observed',daily_usage:{...daily,observed_at_ms:daily.observed_at_ms+1}};
  lane.update(value); assert.equal(lane.observations.delayed(now),false);
  const priorCards = lane.observations.view.active_cards;
  const changed = {...priorCards[0],title:'Fresh correction in a partial publication',state:'observed'};
  value.view = {...value.view,cards_state:'partial',active_cards:[changed]};
  lane.update(value);
  assert.equal(lane.observations.view.active_cards.length,2,'partial reads do not erase other retained prompt rows');
  assert.equal(lane.observations.view.active_cards[0].title,changed.title,'valid per-card corrections still apply');
  const initialTest = setup(), initial = initialTest.controller;
  initial.update({state:'recovering',view:null});
  assert.equal(initial.observations.snapshot(now),null,'no fabricated first values');
  const initialOpening = initial.toggle(); initialTest.opened(win()); await initialOpening;
  assert.equal(initial.view.daily.textContent, 'CCost Today · Loading…');
  assert.match(initial.view.daily.attributes['aria-label'], /^CCost Today · Loading…/);
  initial.close();
  now += 599999; assert.equal(initial.observations.delayed(now),false);
  now++; assert.equal(initial.observations.delayed(now),true);
  for (const change of [owner => {owner.isSecureContext = false;}, owner => {delete owner.documentPictureInPicture;},
      owner => {owner.top = {};}, owner => {owner.document.permissionsPolicy = {allowsFeature: () => false};}]) {
    const item = setup(); change(item.owner);
    const disabled = new Controller(item.owner, item.button, item.feedback, () => {});
    assert.equal(item.button.disabled, true); assert.ok(item.feedback.textContent); await disabled.toggle(); assert.equal(item.calls(), 0);
  }
  console.log('Mini Watch VM: lifecycle/races, units/theme, native callbacks, fresh/retained states and independent DOM passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
