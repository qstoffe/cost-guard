// Deterministic window/DOM seam. This does not claim browser-owned PiP or OS proof.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
class Node {
  constructor(tag) {
    this.tag = tag; this.children = []; this.dataset = {}; this.attributes = {}; this.events = {}; this.text = '';
    const properties = new Map(); this.style = {setProperty: (key,value) => properties.set(key,value),
      getPropertyValue: key => properties.get(key) || '', removeProperty: key => properties.delete(key)};
  }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(child => child.textContent).join(''); }
  append(...children) { for (const child of children) { child.remove(); child.parentNode = this; this.children.push(child); } }
  replaceChildren(...children) { for (const child of this.children) child.parentNode = null; this.children = []; this.text = ''; this.append(...children); }
  remove() { if (this.parentNode) this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1); this.parentNode = null; }
  insertBefore(child, before) { child.remove(); child.parentNode = this; this.children.splice(before ? this.children.indexOf(before) : this.children.length, 0, child); }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(name, callback) { (this.events[name] ||= []).push(callback); }
  removeEventListener(name, callback) { this.events[name] = (this.events[name] || []).filter(item => item !== callback); }
  fire(name) { for (const callback of this.events[name] || []) callback(); }
  contains(node) { return node === this || this.children.some(child => child.contains(node)); }
  querySelectorAll(tag) { return this.children.flatMap(child => [...(child.tag === tag ? [child] : []), ...child.querySelectorAll(tag)]); }
}
function doc() { const value = {createElement: tag => Object.assign(new Node(tag), {ownerDocument:value}),
  createElementNS: (namespaceURI, tag) => Object.assign(new Node(tag), {namespaceURI}),
   createTextNode: text => Object.assign(new Node('#text'), {textContent:text}),
   head: new Node('head'), body: new Node('body'), documentElement: new Node('html')}; return value; }
function win() {
  const node = new Node('window'); node.document = doc(); node.closed = false; node.timers = new Set();
  node.document.defaultView = node; node.clearTimeout = clearTimeout; node.setTimeout = setTimeout;
  node.requestAnimationFrame = () => {}; // Native layout is exercised by the browser probe.
  const append = node.document.head.append.bind(node.document.head);
  node.document.head.append = (...nodes) => {
    append(...nodes);
    for (const item of nodes) if (item.rel === 'stylesheet' && !node.deferStyles) Promise.resolve().then(() => item.fire('load'));
  };
  node.setInterval = callback => {node.timers.add(callback); return callback;};
  node.clearInterval = callback => node.timers.delete(callback);
  node.close = () => {node.closed = true;}; // Deliberately defer pagehide to reproduce stale callbacks.
  node.resizeTo = () => {throw new Error('Opening consumes activation; resizeTo requires a new PiP gesture');};
  node.media = new Node('media'); node.media.matches = false; node.matchMedia = () => node.media;
  node.getComputedStyle = root => {
    assert.equal(root,node.document.documentElement);
    const values = {'--bg': node.media.matches ? '#0c1422' : '#eef2f8', '--ink': node.media.matches ? '#e6edf8' : '#17253b',
      '--surface': node.media.matches ? '#19263b' : '#f6f8fc'};
    const names = Object.keys(values); names.getPropertyValue = key => values[key]; return names;
  };
  return node;
}
let now = 1000;
class Clock extends Date { static now() { return now; } }
const context = vm.createContext({document: doc(), window: win(), URL, Date: Clock, input});
const helpText = require('../fixtures/web_help_vm.cjs')(vm, context);
for (const file of ['render', 'account-cards', 'watch', 'mini']) vm.runInContext(fs.readFileSync(
  file==='mini' && process.argv[2] ? process.argv[2] : `src/web/assets/${file}.js`, 'utf8'), context);
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
  const controller = new Controller(owner, button, feedback, () => returned++, () => ({ready:true,
    read: () => ({width:628,height:500}), close: () => {}}));
  assert.equal(button.disabled,true,'no placement assumption before confirmed settings');
  controller.settings({miniWatchPlacement:'remember-last'},'fixture-host');
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
  if(input.replay) {
    const values=[];
    for(const publication of input.replay) {
      controller.update(publication);controller.render();
      values.push(view.promptRows.get('root')?.children[4].textContent);
    }
    console.log(JSON.stringify(values));return;
  }
  assert.equal(view.doc.documentElement.dataset.theme, 'classic');
  assert.equal(view.body.children.length, 2);
    assert.equal(view.body.children[0].children[2].textContent, '2');
    assert.equal(view.body.children[1].children[2].textContent, '3');
    assert.equal(view.body.children[1].children[3].textContent, '4583');
    assert.match(helpText(view.body.children[1].children[2].children[0]), /Duration: 20m/);
  assert.equal(view.health.textContent, ''); assert.equal(view.health.hidden, true);
  const table = view.body.parentNode, headers = table.querySelectorAll('th');
    assert.equal(headers[4].textContent, 'Ctx');
    assert.equal(helpText(headers[4].children[0]), 'Estimated context for this session, in tokens.');
  assert.match(table.attributes['aria-label'], /estimated next incoming context \(Ctx\)/);
  assert.equal(view.body.querySelectorAll('button').length,0,'ordinary values have no duplicate help controls');
   assert.equal(view.earlierToggle,undefined,'obsolete disclosure removed');
    assert.equal(view.fitButton.textContent,'↕');assert.equal(view.fitButton.attributes['aria-label'],'Fit Mini Watch Height');
    assert.equal(helpText(view.fitButton),'Fit Mini Watch Height');
    assert.equal(helpText(view.summary),'Return to Watch in the Existing Parent Tab');
  assert.equal(view.daily.querySelectorAll('button').length,0,'daily has no help cue');
  assert.match(view.body.children[0].attributes['aria-label'], /Prompt 23 · Running/);
  assert.match(view.body.children[0].children[0].textContent, /^▶ /);
  const contextItem = input.view.active_cards[0].rows[0], originalContext = contextItem.live_context;
  for (const formatted of ['123 456', '234 567', '0', 'N/A', '~source-format']) {
    contextItem.live_context = {display:{watch_next_context_tokens:formatted}};
    controller.update(input);
     assert.equal(view.body.children[0].children[4].textContent, formatted, 'Ctx uses the source format without adding or stripping characters');
  }
  contextItem.live_context = null; controller.update(input);
    assert.equal(view.body.children[0].children[4].textContent, 'N/A');
  contextItem.live_context = originalContext; controller.update(input);
  const guidanceWarning=input.view.active_cards[0].session_summary.context.warning;
  const originalWarning=structuredClone(guidanceWarning);
  for(const [state,wording] of [['pending','Price comparison pending'],['unavailable','Price comparison unavailable; retrying'],['ready','2.4x more expensive']]) {
    guidanceWarning.guidance_state=state;
    guidanceWarning.multiplier=state==='ready'?'2.4':null;
    guidanceWarning.display.warning_cost='('+wording+')';controller.update(input);
    assert.equal(view.body.children[0].children[4].dataset.guidance,state);
    assert.equal(view.body.children[0].contextHelp,state==='ready'
      ? guidanceWarning.text.replace(/^\[|\]$/g,'')+' · 2.4x more expensive' : '');
    assert.equal(view.body.children[0].children[4].textContent,originalContext.display.watch_next_context_tokens);
  }
  Object.assign(guidanceWarning,originalWarning);controller.update(input);
  assert.equal(view.daily.textContent, 'CCost Today 34 · 37 prompts', 'prior activity is not the two prompt rows or account-period costs');
  assert.equal(view.dailyNote.textContent,'');
  assert.notEqual(view.daily.parentNode, view.summary, 'daily metric is outside the navigation target');
  view.daily.fire('click'); view.daily.fire('keydown'); assert.equal(test.returned(),0);
   assert.equal(api.requests[0].height,500); assert.equal(api.requests[0].width,628);
  assert.equal(api.requests[0].preferInitialWindowPlacement,true);
    require('../fixtures/mini_sessions.cjs')(vm,context,controller,view,input,helpText);
    require('../fixtures/mini_activity.cjs')(vm,context,controller,view,input,helpText,{get:()=>now,set:value=>{now=value;}});
     require('../fixtures/mini_help.cjs')(controller,view,input,helpText);
     require('../fixtures/mini_context.cjs')(controller,view,input,helpText);
   const demandCalls = [];
   controller.setDemandFactory(win => {
     assert.equal(win, child, 'Mini demand belongs to the actual PiP document');
     return {update: () => demandCalls.push(controller.view.needsHistory), close: () => demandCalls.push('closed')};
   });
   assert.equal(demandCalls.at(-1),true,'open Mini requests historical fillers automatically');
   controller.setDemandFactory(() => ({update() {}, close() {}}));
   assert.equal(demandCalls.at(-1), 'closed');
  require('../fixtures/mini_fit.cjs')(view,child,controller,input);
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
    input.view.daily_usage = {...daily,prompt_count:count,display:{daily_ccost:credit},
      display_units:{credits:{daily_ccost:credit},usd:{daily_ccost:usd}},total:{...daily.total,known_ccost:value,observed_requests:count,priced_requests:count,
      display:{known_ccost:credit},display_units:{credits:{known_ccost:credit},usd:{known_ccost:usd}}}};
    parity(); assert.equal(view.daily.textContent,`CCost Today ${credit} · ${count} prompts`);
    vm.runInContext('ReportView.setUnit("usd")', context); controller.settings(); parity();
    assert.equal(view.daily.textContent,`CCost Today ${usd} · ${count} prompts`);
    vm.runInContext('ReportView.setUnit("credits")', context);
  }
  input.view.daily_usage = {...daily,display:{daily_ccost:'N/A'},display_units:{},
    total:{...daily.total,known_ccost:'0',priced_requests:0,complete:false}};
  parity(); assert.equal(view.dailyText.textContent,'CCost Today N/A · 37 prompts');
  assert.equal(view.dailyNote.textContent,'');
  for (const changes of [{}, {total:{...daily.total,priced_requests:99,complete:false,
      display:{known_ccost:'?34'},display_units:{usd:{known_ccost:'?$0.34'}}},mix:{...daily.mix,cost_complete:false}},
      {mix:{...daily.mix,totals:[5000,null,1000,1000]}}, {prompt_count_complete:false}]) {
    input.view.daily_usage = {...daily,...changes};
    const canonical = JSON.stringify(input.view.daily_usage);
    for (const [unit,amount] of [['credits','34'],['usd','$0.34']]) {
      vm.runInContext(`ReportView.setUnit('${unit}')`, context); controller.settings(); parity();
      assert.equal(view.dailyText.textContent,`CCost Today ${amount} · 37 prompts`);
      assert.equal(view.dailyNote.textContent,'');
      assert.equal(view.daily.querySelectorAll('button').length,0);
      assert.equal(JSON.stringify(input.view.daily_usage),canonical,'daily presentation preserves all backing evidence');
    }
  }
  vm.runInContext('ReportView.setUnit("credits")', context);
  input.view.daily_usage = {...daily,total:{...daily.total,priced_requests:99,complete:false}};
  for (const state of ['retrying','unavailable','loading','partial']) {
    input.view.daily_state=state; parity(); assert.equal(view.dailyText.textContent,'CCost Today 34 · 37 prompts');
    assert.equal(view.daily.className,'mini-daily'); assert.equal(view.health.hidden,true);
  }
  input.view.daily_usage=null;
  for (const state of ['unavailable','loading','retrying']) {
    input.view.daily_state=state; controller.update(input);
    assert.equal(view.daily.textContent,'CCost Today 34 · 37 prompts','same-day null refresh retains usable daily data');
  }
  input.view.daily_usage={...daily,day_start_ms:daily.day_start_ms+86400000,day_end_ms:daily.day_end_ms+86400000,prompt_count:0,
    display:{daily_ccost:'0'},display_units:{credits:{daily_ccost:'0'},usd:{daily_ccost:'$0.00'}},
    total:{...daily.total,known_ccost:'0',observed_requests:0,priced_requests:0,display:{known_ccost:'0'},display_units:{credits:{known_ccost:'0'}}}};
  input.view.daily_state='observed'; parity(); assert.equal(view.daily.textContent,'CCost Today 0 · 0 prompts','new canonical local day replaces the old daily observation');
  input.view.daily_usage=daily; parity(); assert.equal(view.daily.textContent,'CCost Today 34 · 37 prompts','later source corrections replace, never accumulate');
  assert.ok(!/Running prompts|Running CCost|Longest running|×/.test(view.root.textContent));
   assert.equal(child.document.head.children.length, 3);
   assert.deepEqual(child.document.head.children.map(n => [n.rel, n.type, n.href]), [
     ['icon', 'image/x-icon', 'http://127.0.0.1:1234/favicon-cg1.ico'],
     ['stylesheet', undefined, 'http://127.0.0.1:1234/app.css'], ['stylesheet', undefined, 'http://127.0.0.1:1234/mini.css']]);
   assert.equal(owner.document.head.children.length, 0, 'Mini never changes the owning tab head');
  assert.equal(view.accounts.children.length, 6);
  assert.match(view.accounts.textContent, /GitHub Copilot Pro · 8.4% used \(2088\)/);
  assert.match(view.accounts.textContent, /Primary temporarily missing · Usage unavailable \(\?\)/);
  assert.match(view.accounts.textContent, /OpenAI Pro Lite · 42% used \(\?\)/);
  assert.ok(!/Reset|Weekly|Today|Provisional/.test(view.accounts.textContent));
  const retained = view.accounts.children[0]; controller.update(input);
  assert.equal(view.accounts.children[0], retained, 'independent keyed DOM survives refresh');
  const beforeSwitch = JSON.stringify(input), retainedBar = retained.children[1];
  vm.runInContext('ReportView.setQuotaMode("remaining")', context); controller.settings();
  assert.match(retained.textContent, /91.6% remaining \(22912\)/);
  assert.equal(retainedBar.value, '0.91648'); assert.match(retainedBar.attributes['aria-label'], /remaining/);
  for (const [index, line] of [...view.accounts.children].entries()) {
    const primary = input.view.accounts.accounts[index].primary;
    assert.equal(line.helpText, `Capacity: ${primary.quota.display.capacity_amount}\nNext reset: ${primary.display.mini_reset}`);
    assert.doesNotMatch(line.helpText, /Unrounded|Guesstimate|estimate|Observed same-window|Provider-reported fraction|÷/);
  }
  assert.equal(retained.querySelectorAll('button').length,0,'subscription text owns help without a cue');
  assert.equal(retained.children[0].children[0].tabIndex,0);
  assert.equal(helpText(retained.children[0].children[0]), retained.helpText);
  assert.doesNotMatch(retained.helpText,/Last quota update|Source:|Availability:/);
  assert.doesNotMatch(retained.helpText, /Period CCost unavailable/);
  assert.equal(view.accounts.children[0], retained); assert.equal(retained.children[1], retainedBar);
  vm.runInContext('ReportView.setQuotaMode("used")', context); controller.settings();
  assert.match(retained.textContent, /8.4% used \(2088\)/);
  assert.equal(JSON.stringify(input), beforeSwitch, 'presentation never changes canonical source fields');
  const scopedPrimary = input.view.accounts.accounts[0].primary, scopedQuota = scopedPrimary.quota;
  const scopedDisplay = scopedPrimary.display;
  for (const [capacity, usd, reset] of [['3066 Credits', '$30.66', 'Reset in 1h, 12:00 today'],
      ['~3066 Credits', '~$30.66', 'Reset in 23h, 10:00 Saturday'], ['?', '?', 'Reset unknown']]) {
    scopedPrimary.quota = {...scopedQuota, display:{...scopedQuota.display,capacity_amount:capacity},
      display_units:{credits:{capacity_amount:capacity},usd:{capacity_amount:usd}}};
    scopedPrimary.display = {...scopedDisplay,mini_reset:reset};
    for (const unit of ['credits','usd']) {
      vm.runInContext(`ReportView.setUnit('${unit}')`, context); controller.settings();
      assert.equal(helpText(retained.children[0].children[0]), `Capacity: ${unit === 'usd' ? usd : capacity}\nNext reset: ${reset}`);
    }
  }
  scopedPrimary.quota = scopedQuota; scopedPrimary.display = scopedDisplay;
  vm.runInContext('ReportView.setUnit("credits")', context); controller.settings();
  const firstRow = view.body.children[0], firstCell = firstRow.children[0], originals = input.view.active_cards;
  const prompt = originals[1].rows[0].prompt;
  input.view.active_cards = [originals[1], originals[0], originals[0], {session_id:'pending',focal_id:'',rows:[]}];
  controller.update(input);
  assert.equal(view.body.children.length, 2, 'deduplicated by source session and event, not aggregate count');
  assert.equal(view.body.children[0], firstRow, 'canonical ascending start order and keyed row');
  assert.equal(firstRow.children[0], firstCell, 'focusable title cell survives updates');
   assert.match(view.body.children[1].attributes['aria-label'], /Prompt 24 · Running/);
  for (const [outcome, className, label] of [
    [{in_progress:false,completed_successfully:true},'mini-success','Completed'],
    [{in_progress:false,completed_successfully:false,aborted:true,abort_reason:'quota_limit'},'mini-error','Aborted · quota limit'],
    [{in_progress:false,completed_successfully:false,aborted:false,has_error:true},'mini-error','Error'],
    [{in_progress:false,completed_successfully:false,aborted:false,has_error:false},'','Ended']]) {
    const saved = {...prompt}, savedView = input.view;
    Object.assign(prompt, outcome, {completed_at_ms:10000}); controller.update(input);
    const terminal = view.promptRows.get(originals[1].session_id);
     assert.equal(terminal.className,className); assert.ok(terminal.attributes['aria-label'].includes(label));
     assert.doesNotMatch(terminal.children[0].textContent,/▶/,'terminal publication clears the cue in the same update');
    assert.equal(terminal.querySelectorAll('button').length,0,'status has no popover');
     assert.match(helpText(terminal.children[2].children[0]),/Duration: 20m/);
    input.view = {...savedView, active_cards:[originals[0]], history_state:'observed', history_epoch:1,
      history_cards:[{...structuredClone(originals[1]),focal_id:''}]};
    controller.update(input);
    assert.equal(view.promptRows.get(originals[1].session_id),terminal,'source handoff reuses the row');
    assert.equal(terminal.className,'','historical outcome does not retain terminal emphasis');
    assert.ok(terminal.attributes['aria-label'].includes(label));
    input.view = {...input.view,cards_state:'unavailable',active_cards:[],history_state:'refreshing'};
    for (const state of ['running','recovering','running']) {
      controller.update({...input,state}); controller.render();
       assert.equal(terminal.className,'','retention/retry does not restart completion');
       assert.doesNotMatch(terminal.children[0].textContent,/▶/);
    }
     input.view = savedView; Object.assign(prompt,saved); controller.update(input);
     assert.match(terminal.children[0].textContent,/^▶ /,'the next verified running publication restores its own cue');
  }
  input.view.active_cards = []; controller.update(input);
  assert.match(view.body.textContent,/No earlier sessions/);
  input.view.active_cards = originals; controller.update(input);
  const accountItems = input.view.accounts.accounts;
  input.view.accounts.accounts = [...accountItems].reverse(); controller.update(input);
  assert.equal(view.accounts.children.at(-1),retained,'provider-aware account key survives reorder');
  input.view.accounts.accounts = accountItems; controller.update(input);
  const primary = input.view.accounts.accounts[0].primary, savedCost = primary.cost;
  const savedQuota = primary.quota;
  primary.estimated = true; primary.cost = {...savedCost,complete:false,display:{known_ccost:'?1814'},display_units:{credits:{known_ccost:'?1814'}}};
  primary.quota = {...savedQuota,display_units:{},display:{...savedQuota.display,ccost_brief:'Used CCost has partial attribution / pricing.\nUsed CCost has estimated attribution.'}};
  controller.update(input); assert.match(retained.textContent,/8.4% used \(2088\)/,'provider Used does not depend on partial OpenCode pricing');
  assert.equal(retained.helpText.split('\n').length, 2, 'attribution prose is not repeated in Mini help');
  assert.ok(!retained.textContent.includes('~'));
  assert.equal(retained.children[1].value, primary.used_fraction);
  const quota = {...primary.quota}, saved = {...primary};
  // Exercise the supported legacy DTO fallback separately from computed variants.
  primary.quota = {...primary.quota, quota_display: undefined};
  for (const [fraction, exhausted] of [['0',false],['0.5',false],['0.99999',false],['1',true],[null,false]]) {
    primary.used_fraction = fraction; primary.exhausted = exhausted; controller.update(input);
    assert.equal(retained.children[1].hidden,fraction == null);
    assert.equal(retained.children[1].className,exhausted ? 'mini-exhausted' : '');
  }
  primary.quota.unlimited = true; controller.update(input);
  assert.equal(retained.children[1].hidden,true); assert.match(retained.textContent,/Unlimited/);
  Object.assign(primary,saved); Object.assign(primary.quota,quota);
  primary.cost = {...savedCost,priced_requests:0};
  primary.quota = {...savedQuota,display:{...savedQuota.display,ccost_used:'?'},display_units:{}};
  controller.update(input); assert.match(retained.textContent,/8.4% used \(\?\)/,'known percentage survives unknown pricing');
  primary.estimated = false; primary.cost = savedCost; primary.quota = savedQuota; controller.update(input);
  vm.runInContext('ReportView.setUnit("usd")', context); owner.document.documentElement.dataset.theme = 'web'; controller.settings();
    assert.equal(view.body.children[0].children[2].textContent, '$0.01');
    assert.equal(view.body.children[0].children[3].textContent, '$45.82'); assert.match(retained.textContent, /\(\$20.88\)/);
  assert.equal(child.document.documentElement.dataset.theme, 'web');
  const themeStyle = child.document.documentElement.style;
  assert.equal(themeStyle.getPropertyValue('--bg'),'#eef2f8','PiP uses owner-resolved Web tokens');
  assert.equal(themeStyle.getPropertyValue('--ink'),'#17253b');
  assert.equal(themeStyle.getPropertyValue('color-scheme'),'light');
  owner.media.matches = true; owner.media.fire('change');
  assert.equal(themeStyle.getPropertyValue('--bg'),'#0c1422','OS change applies without settings, data or timer');
  assert.equal(themeStyle.getPropertyValue('color-scheme'),'dark');
  owner.document.documentElement.dataset.theme = 'classic'; controller.settings();
  assert.equal(themeStyle.getPropertyValue('--bg'),'','Classic retains its original CSS without Web overrides');
  assert.equal(themeStyle.getPropertyValue('--surface'),'');
  assert.equal(themeStyle.getPropertyValue('color-scheme'),'');
  owner.media.matches = false; owner.document.documentElement.dataset.theme = 'web'; controller.settings();
  assert.equal(themeStyle.getPropertyValue('--bg'),'#eef2f8','Web → Classic → Web restores the entire palette');
  assert.equal(view.daily.textContent,'CCost Today $0.34 · 37 prompts');
  for (const kind of ['reconnecting', 'offline', 'source_unavailable', 'authorization_required', 'identity_changed', 'stopped']) {
    controller.health({kind});
    assert.equal(view.health.hidden, ['reconnecting','source_unavailable'].includes(kind));
    if (!view.health.hidden) assert.match(view.health.textContent,/return to|reopen|restart/);
     assert.match(helpText(view.body.children[1].children[2].children[0]), /Duration: 20m/);
    assert.equal(view.daily.textContent,'CCost Today $0.34 · 37 prompts');
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
  assert.doesNotMatch(view.accounts.textContent,/Retained quota|not current/i,'short retries remain visually quiet');
  assert.equal(retained.attributes['aria-description'], undefined);
  now = 600999; controller.health({kind:'reconnecting'}); assert.equal(view.health.hidden,true);
  now = 601000; controller.update(input); assert.equal(view.health.textContent,'');
  const warning = view.health.textContent; now += 5000; controller.health({kind:'connected'});
  input.view.now_ms++; controller.update(input); assert.equal(view.health.textContent,warning,'retry publications cannot fake recovery');
  assert.equal(view.body.textContent,retainedText); assert.equal(view.observationHelp,undefined);
  input.view = {...healthy.view,now_ms:healthy.view.now_ms+2,
    active_cards:healthy.view.active_cards.map(card=>({...card,observed_at_ms:card.observed_at_ms+1})),
    daily_usage:{...daily,observed_at_ms:daily.observed_at_ms+1},accounts:{...healthy.view.accounts,accounts:healthy.view.accounts.accounts.map(item =>
      ({...item,observation:{...item.observation,observed_at_ms:item.observation.observed_at_ms+1}}))}};
  controller.update(input); assert.equal(view.health.hidden,true,'genuinely usable recovery clears the one status');
  input.view = {...input.view,active_cards:[],cards_state:'observed',now_ms:input.view.now_ms+1};
  controller.update(input); assert.match(view.body.textContent,/No earlier sessions/,'valid empty evicts retained rows');
  input.view = {...input.view,active_cards:originals,daily_usage:{...daily,day_end_ms:now+1}};
  controller.update(input); assert.equal(view.daily.textContent,beforeDaily);
  now++; [...child.timers][0](); assert.equal(view.daily.textContent,'CCost Today · Loading…','no yesterday total after configured midnight, even disconnected');
  input.view = {...healthy.view,now_ms:healthy.view.now_ms+3}; controller.update(input);
  view.summary.fire('click'); assert.equal(test.returned(), 1); assert.equal(test.focused(), 1);
  assert.equal(child.closed, false, 'return selects existing tab without closing Mini');
  await controller.toggle();
  assert.equal(child.closed, true); assert.equal(test.focused(), 1, 'close does not also focus the owner');
  assert.equal(child.timers.size, 0); assert.equal(button.textContent, 'Mini Watch: Off');
  assert.equal(owner.media.events.change.length,0,'native close releases the appearance listener');
  owner.media.matches = true; owner.media.fire('change');
  assert.equal(themeStyle.getPropertyValue('--bg'),'#eef2f8','retired document no longer follows the owner');
   const reopen = controller.toggle(), second = win(); test.opened(second); await reopen;
   assert.equal(api.requests.at(-1).height,500,'reopening forwards measured layout');
   assert.equal(api.requests.at(-1).preferInitialWindowPlacement,true,'Fit on open prioritizes measured size over remembered position');
   assert.equal(second.document.head.children.filter(n => n.rel === 'icon').length, 1);
   assert.equal(second.document.documentElement.style.getPropertyValue('--bg'),'#0c1422','fresh Web opens in current owner appearance');
   assert.equal(owner.media.events.change.length,1,'reopen has exactly one appearance listener');
   assert.equal(second.document.head.children[0].href, 'http://127.0.0.1:1234/favicon-cg1.ico');
    assert.notEqual(second.document.head.children[0], child.document.head.children[0], 'each PiP document owns its link');
   assert.equal(controller.view.earlier,undefined,'fresh Mini has one always-visible table');
  child.fire('pagehide'); assert.equal(button.textContent, 'Mini Watch: On', 'late old pagehide cannot retire a new window');
  second.close(); second.fire('pagehide'); assert.equal(button.textContent, 'Mini Watch: Off', 'native close');
  controller.settings({miniWatchPlacement:'standard'},'same-host');
  const replaceOpen = controller.toggle(), replaced = win(); test.opened(replaced); await replaceOpen;
  assert.equal(api.requests.at(-1).preferInitialWindowPlacement,true);
   controller.settings({miniWatchPlacement:'remember-last',miniWatchSize:'remember-last'},'same-host');
  assert.equal(controller.window,replaced,'mode changes never move or close existing PiP');
  api.window = win(); controller.update(input); assert.equal(button.textContent, 'Mini Watch: Off', 'ownership replacement');
  assert.equal(replaced.timers.size, 0);
  const reloadOpen = controller.toggle(), reloadChild = win(); test.opened(reloadChild); await reloadOpen;
  assert.equal(api.requests.at(-1).preferInitialWindowPlacement,false);
  owner.fire('pagehide'); assert.equal(reloadChild.closed, true); assert.equal(button.textContent, 'Mini Watch: Off');
  await controller.toggle(); assert.equal(test.calls(), 6, 'ended owner cannot reopen');
  const pendingClose = setup(); const promise = pendingClose.controller.toggle(); pendingClose.owner.fire('pagehide');
  const late = win(); pendingClose.opened(late); await promise; assert.equal(late.closed, true);
  for (const outcome of ['load','error','close']) {
    const waiting=setup(), child=win();child.deferStyles=true;
    const opening=waiting.controller.toggle();waiting.opened(child);await Promise.resolve();
    assert.equal(waiting.controller.view,null,'never render unstyled content into the narrow viewport');
    if(outcome==='close')waiting.controller.close();
    child.document.head.children.filter(n=>n.rel==='stylesheet').forEach(n=>n.fire(outcome==='error'?'error':'load'));
    await opening;
    if(outcome==='load')assert.ok(waiting.controller.view);
    else {assert.equal(child.closed,true);assert.equal(waiting.controller.view,null);}
    waiting.controller.close();
  }
  const boundary = setup(); boundary.controller.settings({miniWatchPlacement:'remember-last'},'host-1');
  for (const [identity,initial] of [['host-1',true],['host-1',false],['host-2',true],['host-2',false]]) {
     boundary.controller.settings({miniWatchPlacement:'remember-last',miniWatchSize:'remember-last'},identity);
    const opening = boundary.controller.toggle(); boundary.opened(win()); await opening;
    assert.equal(boundary.api.requests.at(-1).preferInitialWindowPlacement,initial,'host identity resets first opening only');
    boundary.controller.close();
  }
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
    active_cards:healthy.view.active_cards.map(card=>({...card,observed_at_ms:card.observed_at_ms+2})),
    accounts:{...healthy.view.accounts,accounts:healthy.view.accounts.accounts.map(item=>
      ({...item,observation:{...item.observation,observed_at_ms:item.observation.observed_at_ms+1}}))}};
  lane.update(value); assert.equal(lane.observations.delayed(now),false);
  value.view.accounts.accounts[0].observation = {...value.view.accounts.accounts[0].observation,
    availability:'stale',error_code:'auth_failure'};
  lane.update(value);
  assert.equal(lane.observations.view.accounts.accounts[0].observation.error_code,'auth_failure','retention cannot hide a new authentication failure');
  now += 600000;
  value.view = {...value.view,now_ms:value.view.now_ms+1,
    daily_usage:{...value.view.daily_usage,observed_at_ms:value.view.daily_usage.observed_at_ms+1},
    accounts:healthy.view.accounts,
    active_cards:value.view.active_cards.map((card,index)=>index ? card : {...card,observed_at_ms:card.observed_at_ms+1})};
  lane.update(value);
  assert.equal(lane.observations.delayed(now),true,'another focal prompt cannot hide an unobserved retained card');
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
  assert.equal(initial.view.daily.textContent, 'CCost Today · Loading…');
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
