// Actual shipped complete-history assets in a deterministic VM/DOM.
const assert = require('node:assert/strict'), vm = require('node:vm'), fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.dataset = {}; this.events = {}; this.text = ''; this.attributes = {}; }
  set textContent(value) { this.replaceChildren(); this.text = String(value); }
  get textContent() { return this.text + this.children.map(c => c.textContent).join(''); }
  get parentNode() { return this.parent; }
  get firstChild() { return this.children[0]; }
  get isConnected() { return Boolean(this.parent); }
  append(...children) { for (const child of children) { child.remove(); this.children.push(child); child.parent = this; } }
  replaceChildren(...children) { for (const child of this.children) child.parent = null; this.children = []; this.text = ''; this.append(...children); }
  insertBefore(child, before) { child.remove(); const index = before ? this.children.indexOf(before) : this.children.length; this.children.splice(index, 0, child); child.parent = this; }
  after(child) { if (this.parent) this.parent.insertBefore(child, this.parent.children[this.parent.children.indexOf(this) + 1]); }
  remove() { if (this.parent) { this.parent.children.splice(this.parent.children.indexOf(this), 1); this.parent = null; } }
  contains(child) { return child === this || this.children.some(c => c.contains(child)); }
  querySelector(selector) { return this.children.find(child => selector[0] === '.' ? child.className === selector.slice(1) : child.tag === selector) || this.children.map(child => child.querySelector(selector)).find(Boolean); }
  setAttribute(key, value) { this.attributes[key] = value; }
  removeAttribute(key) { delete this.attributes[key]; }
  addEventListener(key, fn) { this.events[key] = fn; }
  getBoundingClientRect() { return {top: 100, bottom: 120}; }
}
async function main() {
  let selected = null, offline = false, page = input.first;
  const calls = [], scrolls = [], delays = [], timers = new Map(); let timerId = 0;
  const document = {createElement: tag => new Node(tag), createElementNS: (_, tag) => new Node(tag),
    createTextNode: text => Object.assign(new Node('#text'),{textContent:text}), activeElement: null, addEventListener(){}};
     const context = vm.createContext({document, console, Date, performance, URLSearchParams, AbortController, TextEncoder, location: {},
     history: {replaceState: (_, __, url) => { context.location.hash = url; }},
    setTimeout: (fn, delay) => { const id = ++timerId; if (!delay) fn(); else { timers.set(id, fn); delays.push(delay); } return id; },
    clearTimeout: id => timers.delete(id),
    window: {getSelection: () => ({isCollapsed: !selected, anchorNode: selected}), scrollBy: (...args) => scrolls.push(args)},
    api: async (path, value) => {
      assert.equal(path, '/api/detail'); calls.push(value);
      if (offline) throw new Error('offline');
      if (value.action === 'open') return {token: 'owned'};
      if (value.action === 'close') return {};
      const result = JSON.parse(JSON.stringify(page));
      result.offset = value.offset;
      result.result.view.prompt_blocks[0].rows = result.result.view.prompt_blocks[0].rows.slice(value.offset, value.offset + 25);
      return result;
    }});
  require('../fixtures/web_help_vm.cjs')(vm, context);
  for (const file of ['render', 'account-cards', 'watch', 'report-loading', 'session-export', 'session', 'sessions']) vm.runInContext(fs.readFileSync(`src/web/assets/${file}.js`, 'utf8'), context);
  vm.runInContext("globalThis.view = new SessionDetail.View(api, 'root-0000')", context);
  const view = context.view; view.attached = true;
  page.quota_usage={scope:'same-source',accounts:[{observation:{id:'safe',provider_id:'synthetic',label:'Synthetic Plan'},
    quotas:[{id:'five',label:'5-hour',contribution:'positive',percent:'~235%'},
      {id:'model',label:'Special',scope:'model',model_id:'special',contribution:'zero',percent:'0%'}]},
    {observation:{id:'unused',provider_id:'openai',label:'Unused'},quotas:[
       {id:'weekly',label:'weekly',contribution:'unknown',percent:'?',reason:'Account allocation unavailable'}]}]};
  new Node('main').append(view.root);
  await view.load();
  assert.equal(view.root.children.at(-1),view.quotaUsage.root,'summary follows all existing activity');
  assert.ok(view.activitySection.root.contains(view.activity.root));
  const quotaCard=view.quotaUsage.grid.children[0],quotaRow=quotaCard.children[1];
  assert.match(quotaRow.textContent,/~235%/);
   assert.equal(view.quotaUsage.grid.children.length,2,'unallocatable accounts explain their unknown share');
  assert.equal(quotaCard.children.length,2,'zero model quota has no DOM slot');
  assert.equal(quotaCard.children[0].tag,'h3','account is subordinate to the section h2');
  page.quota_usage.accounts[0].quotas[0].percent='~117.5%';
  await view.load();
  assert.equal(view.quotaUsage.grid.children[0],quotaCard);
  assert.equal(quotaCard.children[1],quotaRow);
  assert.equal(quotaRow.textContent,'5-hour~117.5%','same-revision capacity update must not be skipped');
  // Unit switching exercises the bound production heading and ordinary rows.
  vm.runInContext("ReportView.setUnit('usd');ReportView.syncUnits(view.root)",context);
  assert.equal(quotaRow.textContent,'5-hour~117.5%');
  vm.runInContext("ReportView.setUnit('credits');ReportView.syncUnits(view.root)",context);
  const quotaValue=page.quota_usage; page.quota_usage=null; page.quota_state='pending'; await view.load();
  assert.equal(view.quotaUsage.grid.children[0],quotaCard,'pending quota refresh retains the last usable card');
  page.quota_usage=quotaValue; page.quota_state='ready';
  const tiny={id:'tiny',label:'weekly GPT-6',contribution:'positive',percent:'~0%'};
  quotaValue.accounts[0].quotas.push(tiny); await view.load();
  assert.equal(quotaCard.children[2].children[0].textContent,'Weekly GPT-6');
  assert.equal(quotaCard.children[2].children[1].textContent,'~0%','typed positive wins over rounded text');
   tiny.percent='?'; await view.load();
   assert.equal(quotaCard.children[2].children[1].textContent,'?','positive membership survives unknown capacity');
  tiny.contribution='zero'; await view.load();
  assert.equal(quotaCard.children.length,2);
  assert.equal(view.body.children.length, 100);
  assert.equal(view.body.children[0].children.length, 10);
  assert.equal(view.back.textContent, '↩ Back to Show All Sessions');
  assert.equal(view.back.getAttribute('aria-label'), 'Back to Show All Sessions');
  assert.equal(view.back.href, '#/sessions');
  assert.match(view.root.textContent, /Session ID: root-0000/);
  assert.match(view.footer.textContent, /Complete session/);
  assert.equal(view.footer.children.length, 10);
  // Metric availability is not Model invalidation: zero-token/scripted rows
  // must not close an actively read Model surface on an ordinary refresh.
  const modelNode = view.body.children[0].children[1].firstChild;
  modelNode.events.focus();
  const modelPanel = document.body.children.at(-1);
  assert.equal(modelPanel.hidden, false);
  const unavailable = JSON.parse(JSON.stringify(page));
  const eventId = unavailable.result.view.prompt_blocks[0].rows[0].event_id;
  unavailable.value_authority = {...unavailable.value_authority,
    rows: {...unavailable.value_authority?.rows, [eventId]: 'unavailable'}};
  view.update(unavailable);
  assert.equal(view.body.children[0].children[1].firstChild, modelNode);
  assert.equal(modelPanel.hidden, false, 'unavailable Token Mix does not dismiss Model help');
  modelNode.events.blur();
  view.update(page);
  assert.ok(!/Freeze|Snapshot|Go to row|Refresh|Token Mix order/.test(view.root.textContent));
  const row = view.body.children[10], cell = row.children[0];
  page = input.changed;
  page.quota_usage={scope:'same-source',accounts:[]}; page.quota_state='ready';
  await view.load();
  assert.equal(view.quotaUsage.grid.children.length,0,'observed removal clears old-account cards');
  assert.match(view.quotaUsage.empty.textContent,/No applicable quota/);
  assert.equal(view.body.children.length, 101);
  assert.equal(view.body.children[10], row);
  assert.equal(row.children[0], cell, 'unchanged rows keep their text and help DOM');
  selected = cell;
  page = JSON.parse(JSON.stringify(page)); page.revision = 'corrected';
  page.result.view.prompt_blocks[0].rows[10].watch_model = 'Late model correction';
  await view.load();
  assert.equal(row.children[0], selected, 'selection survives a corrected live revision');
  selected = null; await view.load();
  assert.match(row.textContent, /Late model correction/);
  selected = row.children[0];
  page.result.view.prompt_blocks[0].rows.splice(10, 1); page.revision = 'row-reclassified';
  page.total = page.result.view.prompt_blocks[0].rows.length;
  await view.load();
  assert.ok(view.body.contains(selected), 'reclassified selected row remains until selection is released');
  selected = null; await view.load();
  assert.equal(view.body.children.length, 100, 'same-revision retry removes the deferred obsolete row');
  assert.deepEqual(view.body.children.map(item => item.dataset.id), page.result.view.prompt_blocks[0].rows.map(item => item.id));
  const promptRows = page.result.view.prompt_blocks[0].rows;
  const latest = promptRows.at(-1);
  promptRows.at(-2).has_error = true;
  latest.in_progress = true; page.revision = 'running';
  await view.load();
  const state = offset => view.body.children.at(offset).querySelector('.session-prompt-state').textContent;
  assert.equal(state(-1), `[RUNNING] #${latest.prompt_number}`);
  assert.equal(view.body.children.at(-1).className, 'session-running');
  latest.in_progress = false; latest.aborted = true; page.revision = 'aborted';
  for (let poll = 0; poll < 2; poll++) {
    await view.load();
    assert.equal(state(-1), `[ABORTED] #${latest.prompt_number}`);
    assert.equal(view.body.children.at(-1).className, 'error');
    assert.ok(view.body.children.at(-1).children[0].textContent.endsWith(latest.preview));
    assert.equal(state(-2), `#${promptRows.at(-2).prompt_number}`, 'an ordinary red error is not an abort');
    assert.equal(view.body.children.at(-2).className, 'error');
    assert.equal(state(-3), `#${promptRows.at(-3).prompt_number}`);
    assert.equal(view.body.children.at(-3).className, '');
  }
  const retained = view.body.textContent; offline = true; await view.load();
   assert.equal(view.body.textContent, retained); assert.equal(view.status.textContent, '');
   assert.equal(view.retry.hidden, true);
  assert.ok(calls.some(call => call.action === 'chunk' && call.offset === 100));
  assert.equal(scrolls.length, 0, 'stable document geometry never scrolls');
  offline = false; page.export_state = 'ready'; page.export_scope = 'scope';
  page.export_name = 'Observed title å.zip';
  page.result.view.prompt_blocks[0].title = 'Observed: title å';
  page.revision = 'renamed-session'; await view.load();
  assert.equal(view.heading.textContent,'Observed: title å');
  assert.equal(view.exporter.filename,'Observed title å.zip');
  view.heading.textContent = 'Editable DOM is not authority';
  await view.load();
  assert.equal(view.exporter.filename,'Observed title å.zip');
  page.export_state = 'unavailable'; await view.load();
  assert.match(view.exporter.notice.textContent,/unavailable/);
  assert.equal(view.exporter.button.disabled,true);
  view.detach();
  assert.ok(calls.some(call => call.action === 'close' && call.token === 'owned'));
  offline = false;
  let pending = true, pendingState = 'observed', acquisition, retryCalls = 0;
  context.pendingApi = async (path, value) => {
    if (value.action === 'open') return {token:'pending-lease'};
    if (value.action === 'close') return {};
    if (value.action === 'retry') {retryCalls++;acquisition={phase:'queued',attempts:0,completed:0};return {};}
    if (pending) return {state:pendingState,pending:true,result:null,acquisition};
    const result = JSON.parse(JSON.stringify(input.first));
    result.offset = value.offset;
    result.result.view.prompt_blocks[0].rows = result.result.view.prompt_blocks[0].rows.slice(value.offset, value.offset + 25);
    return result;
  };
  vm.runInContext("globalThis.pendingView = new SessionDetail.View(pendingApi, 'root-0000')", context);
  const pendingView = context.pendingView;
  pendingView.attach(new Node('main')); await new Promise(setImmediate);
  assert.equal(pendingView.body.children.length, 0);
  const pendingBar = pendingView.loader.bar;
  assert.equal(pendingBar.max, 100); assert.equal(pendingBar.value, 0);
  assert.equal(pendingBar.attributes['aria-valuetext'], '0 percent');
   assert.match(pendingView.loader.stage.textContent, /Loading session/);
  assert.equal(pendingView.status.hidden, true);
  await pendingView.load(); pendingView.freshness();
  assert.equal(pendingView.loader.bar, pendingBar, 'polls preserve the determinate DOM instance');
  assert.equal(pendingBar.value, 0, 'unmeasured source waits cannot advance');
  assert.equal(delays.at(-1), 500, 'bounded short pending status polls do not acquire source history');
  assert.equal(timers.size, 1);
  pendingState = 'source_unavailable'; await pendingView.load();
    assert.match(pendingView.status.textContent, /Could not load/);
   assert.ok(!pendingView.status.children.some(node => node.tag === 'progress'));
   assert.equal(pendingView.loader.root.hidden, true);
   assert.equal(pendingView.scroll.attributes['aria-busy'], 'false');
  assert.ok(!pendingView.status.textContent.includes('Waiting'), 'a pending lease cannot hide explicit source failure');
   acquisition = {phase:'analyzing',attempts:2,completed:73,percent:40,progress_age_seconds:1};
  await pendingView.load();
   assert.equal(pendingView.loader.stage.textContent,'Loading session…');
   assert.equal(pendingBar.value,40,'source phase milestone advances without inventing a scalar denominator');
   acquisition.completed=73000; await pendingView.load();
   assert.equal(pendingBar.value,40,'arbitrary unknown units never advance the milestone');
   acquisition={phase:'reading',percent:27,phase_completed:1,phase_total:2,attempts:2};
   await pendingView.load(); assert.equal(pendingBar.value,40,'late lower watermark cannot regress');
    assert.equal(pendingView.loader.stage.textContent,'Loading session…');
   acquisition={phase:'retrying',percent:40,attempts:2}; await pendingView.load();
   acquisition={phase:'selecting',percent:3,attempts:3}; await pendingView.load();
   assert.equal(pendingBar.value,40,'automatic retry retains watermark, not claimed current-attempt fraction');
  acquisition = {phase:'failed',reason:'detail_no_progress',attempts:3,retry_available:true};
  await pendingView.load();
  assert.equal(pendingView.retry.hidden,false);
   assert.equal(pendingView.status.textContent,'Could not load. Try again or return to Sessions.');
  assert.equal(pendingView.loader.root.hidden,true);
  await pendingView.retrySource();
  assert.equal(retryCalls,1);
  assert.equal(pendingView.retry.hidden,true);
   assert.equal(pendingView.loader.stage.textContent,'Loading session…');
  let finishStatus;
  pendingView.pendingLoad = new Promise(resolve => {finishStatus=resolve;});
  pendingView.busy = true;
  const queuedRetry = pendingView.retrySource();
  await pendingView.retrySource();
  assert.equal(retryCalls,1,'a pending status read serializes Retry and duplicate clicks');
  pendingView.busy = false; finishStatus();
  await queuedRetry;
  assert.equal(retryCalls,2,'the original click is not discarded after the status read');
  pending = false;
  const [pendingTimer, resume] = timers.entries().next().value;
  timers.delete(pendingTimer); resume(); await new Promise(setImmediate);
  assert.equal(pendingView.body.children.length, 100);
  assert.equal(pendingView.status.hidden, true);
  pendingView.detach(); assert.equal(timers.size, 0);
  // Exact counts, independent phase expectations and completion after applied rows.
   for (const total of [0, 1, 25, 50, 220, 1001]) {
    const full = JSON.parse(JSON.stringify(input.first)); full.total = total; full.revision = 'count-' + total;
    full.result.view.prompt_blocks[0].rows = Array.from({length: total}, (_, index) => ({...input.first.result.view.prompt_blocks[0].rows[0], id:'row-' + index}));
    const offsets = [];
    context.countApi = async (_, request) => {
      if (request.action === 'open') return {token:'counts'};
      if (request.action === 'close') return {};
      offsets.push(request.offset);
      const response = JSON.parse(JSON.stringify(full)); response.offset = request.offset;
      response.result.view.prompt_blocks[0].rows = response.result.view.prompt_blocks[0].rows.slice(request.offset, request.offset + 50);
      return response;
    };
    vm.runInContext("globalThis.countView = new SessionDetail.View(countApi, 'counts')", context);
    const counted = context.countView, updates = [], original = counted.loader.update.bind(counted.loader);
    counted.loader.update = state => { updates.push({percent:state.percent,stage:state.stage,label:state.stageLabel,rows:counted.body.children.length}); original(state); };
    counted.attached = true; await counted.load();
    assert.equal(counted.body.children.length, total);
    assert.equal(counted.loader.root.hidden,true,'usable rows do not wait for later chunks behind the loader');
    if (total === 220) {
      assert.deepEqual(offsets, [0,50,100,150,200]);
    }
    const body = counted.body.children[0], bar = counted.loader.bar;
    counted.api = async () => ({state:'loading',pending:true,result:null}); await counted.load();
    assert.equal(counted.body.children[0], body); assert.equal(counted.loader.root.hidden, true);
    assert.equal(counted.loader.bar, bar); counted.detach();
  }
  for (const fault of ['revision', 'offset', 'total', 'duplicate', 'overshoot', 'empty', 'detail_expired']) {
    let broken = true;
    context.invalidApi = async (_, request) => {
      if (request.action === 'open') return {token:'invalid'};
      if (request.action === 'close') return {};
      const response = JSON.parse(JSON.stringify(input.first)); response.offset = request.offset;
      response.result.view.prompt_blocks[0].rows = response.result.view.prompt_blocks[0].rows.slice(request.offset, request.offset + 25);
      if (broken && request.action === 'chunk') {
        if (fault === 'detail_expired') throw new Error(fault);
        if (fault === 'revision') response.revision = 'foreign';
        if (fault === 'offset') response.offset = 0;
        if (fault === 'total') response.total++;
        if (fault === 'duplicate') response.result.view.prompt_blocks[0].rows[0].id = input.first.result.view.prompt_blocks[0].rows[0].id;
        if (fault === 'overshoot') response.result.view.prompt_blocks[0].rows = Array(101).fill(response.result.view.prompt_blocks[0].rows[0]);
        if (fault === 'empty') response.result.view.prompt_blocks[0].rows = [];
      }
      return response;
    };
    vm.runInContext("globalThis.invalid = new SessionDetail.View(invalidApi, 'invalid')", context);
    const invalid = context.invalid; invalid.attached = true; await invalid.load();
    assert.equal(invalid.body.children.length,25,'only the verified first chunk is visible');
    assert.equal(invalid.scroll.attributes['aria-busy'], 'false'); assert.equal(invalid.loader.root.hidden, true);
    assert.equal(invalid.status.hidden,true,'usable rows remain visible on interrupted acquisition');
    broken = false; await invalid.load(); assert.equal(invalid.body.children.length, 100); invalid.detach();
  }
  for (const failure of ['instance_stopping', 'authentication_required', 'host_identity_changed']) {
    context.stoppingApi = async (_, request) => {
      if (request.action === 'open') return {token:'stopping'};
      if (request.action === 'close') return {};
      throw new Error(failure);
    };
    vm.runInContext("globalThis.stopping = new SessionDetail.View(stoppingApi, 'stopping')", context);
    const stopping = context.stopping; stopping.attached = true; await stopping.load();
    assert.equal(stopping.attached, false); assert.equal(stopping.token, null);
    assert.equal(stopping.scroll.attributes['aria-busy'], 'false');
    assert.equal(stopping.loader.root.hidden, true); assert.doesNotMatch(stopping.status.textContent, new RegExp(failure));
  }
  let resolveOpen, opening = true;
  const raceCalls = [];
  context.raceApi = async (path, value) => {
    raceCalls.push(value);
    if (value.action === 'open') {
      if (opening) { opening = false; return new Promise(resolve => { resolveOpen = resolve; }); }
      return {token: 'new'};
    }
    if (value.action === 'close') return {};
    return {state: 'loading', result: null};
  };
  vm.runInContext("globalThis.race = new SessionDetail.View(raceApi, 'root-0000')", context);
  const race = context.race, parent = new Node('main');
  race.attach(parent); race.detach(); race.attach(parent);
  resolveOpen({token: 'late'});
  await new Promise(setImmediate);
  assert.ok(raceCalls.some(call => call.action === 'close' && call.token === 'late'));
  assert.equal(race.token, 'new');
  assert.equal(timers.size, 1, 'reattach during open leaves one polling timer');
  race.detach(); assert.equal(timers.size, 0);
  let resolveCatalog;
  const catalogCalls = [];
  const catalogData = {token: 'catalog', epoch: 'epoch', total: 0, size: 25, offset: 0, period:'today',
    sort: 'activity', direction: -1, state: 'observed', view: {session_usage: []}};
  context.catalogApi = async (path, value) => {
    catalogCalls.push(value);
    if (catalogCalls.length === 1) return new Promise(resolve => { resolveCatalog = resolve; });
    return {...catalogData,sort:value.sort,direction:value.direction};
  };
  vm.runInContext('globalThis.catalog = new SessionsCatalog.View(catalogApi)', context);
  const catalog = context.catalog;
  catalog.configure(new URLSearchParams()); catalog.attach(parent);
  catalog.detach(); catalog.configure(new URLSearchParams('sort=ccost')); catalog.attach(parent);
  resolveCatalog(catalogData); await new Promise(setImmediate);
   const pageCalls = catalogCalls.filter(value=>value.action!=='interest');
     assert.equal(pageCalls.length, 2, 'late HTTP does not make a redundant catalog request');
    assert.equal(pageCalls[1].sort, 'ccost');
    assert.equal(catalog.data.sort, 'ccost', 'late HTTP cannot replace the active sort');
    assert.ok(!catalogCalls.some(value=>value.action==='interest' && value.visible===false), 'late response cannot demote the same reattached lease');
   assert.equal(timers.size, 1, 'catalog route race leaves one polling timer');
   catalog.detach(); assert.equal(timers.size, 0);
   const timestamp = expression => vm.runInContext(`ReportView.timestamp(${expression}, "Europe/Stockholm")`, context);
   const originalTZ = process.env.TZ;
   const originalLocaleString = Date.prototype.toLocaleString;
   try {
     const expected = ['2026-03-29 01:30', '2026-03-29 03:30', '2026-10-25 02:30', '2026-10-25 02:30'];
     for (const locale of ['sv-SE', 'en-US']) for (const zone of ['Europe/Stockholm', 'America/New_York']) {
       process.env.TZ = zone;
       // Formatting must not invoke browser-locale defaults, including 12-hour locales.
       Date.prototype.toLocaleString = () => { throw new Error('locale-dependent timestamp: ' + locale); };
       ['2026-03-29T00:30Z', '2026-03-29T01:30Z', '2026-10-25T00:30Z', '2026-10-25T01:30Z'].forEach((instant, index) => {
         assert.equal(timestamp(Date.parse(instant)), expected[index]);
       });
     }
   } finally { if (originalTZ === undefined) delete process.env.TZ; else process.env.TZ = originalTZ; Date.prototype.toLocaleString = originalLocaleString; }
   assert.equal(timestamp(null), 'N/A');
    // An initial pending response is not useful content and cannot pin an empty
    // table forever while the requested global sort finishes.
    vm.runInContext('globalThis.coldCatalog = new SessionsCatalog.View(catalogApi)', context);
    context.coldCatalog.update({...catalogData,state:'loading',pending_sort:true});
    assert.ok(!context.coldCatalog.usable);
    context.coldCatalog.update({...catalogData,pending_sort:true,total:1,view:{session_usage:[{
      session_id:'first',title:'First usable row',indexed:false,metric_state:'pending'}]}});
    assert.equal(context.coldCatalog.body.children.length,1,'cheap metadata is visible with an explicit provisional-order label');
    assert.equal(context.coldCatalog.status.hidden,true,'passive first acquisition has no loading banner');
    assert.equal(context.coldCatalog.data,null,'provisional order is not published as the requested globally sorted data');
     const cold = Array.from({length:25}, (_, index) => ({session_id:'cold-'+index, title:'Pending '+index,
     last_activity_ms:1000, indexed:false, has_summary:false, metric_state:'pending', display:{ccost:'N/A',duration_ms:'N/A'}}));
   catalog.update({...catalogData,total:26,view:{session_usage:cold}});
   assert.equal(catalog.body.children.length, 25);
    assert.ok(catalog.body.children.every(row => row.metrics.every(node =>
      node.textContent === '' && node.children[0].attributes['aria-label'].startsWith('Loading '))));
   assert.equal(catalog.previous.tag, 'button'); assert.equal(catalog.previous.disabled,true); assert.equal(catalog.next.disabled,false);
   catalog.next.events.click(); assert.match(context.location.hash, /offset=25/);
   const known = {...cold[0],indexed:true,has_summary:true,metric_state:'ready',running:true,prompt_count:0,model:'N/A',display:{ccost:'0.00',duration_ms:'0s'}};
   catalog.update({...catalogData,offset:25,total:26,view:{session_usage:[known]}});
   assert.equal(catalog.previous.disabled,false); assert.equal(catalog.next.disabled,true);
   assert.equal(catalog.body.children[0].className,'session-running');
    assert.equal(catalog.body.children[0].statusIcon.textContent,'▶');
    assert.doesNotMatch(catalog.body.children[0].children[1].textContent,/\[RUNNING\]/);
    assert.equal(catalog.body.children[0].name.textContent,'Pending 0');
     assert.deepEqual(catalog.body.children[0].children.slice(2).map(cell=>cell.textContent),['','0.00','0','0s','']);
   selected=catalog.body.children[0].children[1];
   catalog.update({...catalogData,total:1,view:{session_usage:[{...known,running:false}]}});
    assert.equal(catalog.body.children[0].className,'');
     // Age/background updates retain the grid; an explicit pending navigation has progress.
    const usable = {...catalogData,total:26,age_ms:7200000,view:{session_usage:cold.map((row, index) =>
      ({...known,session_id:row.session_id,title:'Loaded '+index}))}};
    catalog.update(usable);
    const firstRow = catalog.body.children[0], labelBefore = catalog.label.textContent;
    catalog.update({...usable,pending_sort:true,sort:'activity',indexed:1,available:26,view:{session_usage:[]}});
    assert.equal(catalog.body.children[0],firstRow);
    assert.equal(catalog.label.textContent,labelBefore);
      assert.equal(catalog.status.hidden,true,'passive pending-sort observation is silent');
    assert.notEqual(catalog.pan.hidden,true); assert.notEqual(catalog.pager.hidden,true);
       assert.equal(catalog.operation,null);
      catalog.navigateTo('#/sessions?sort=ccost&direction=1',null,'sort');
      catalog.configure(new URLSearchParams('sort=ccost&direction=1'));
      catalog.update({...usable,pending_sort:true});
      assert.match(catalog.next.destination,/sort=activity&direction=-1/,'retained pager belongs to the actual displayed order');
      assert.equal(catalog.pan.hidden,false);
       assert.equal(catalog.operation.pending,true);
       assert.match(catalog.status.textContent,/Sorting sessions by CCost/);
       assert.equal(catalog.loader,undefined);
    catalog.attached=true;
     for (const direction of [1,-1]) for (const offset of [0,25]) {
       const requests=[]; let expire=true;
       catalog.configure(new URLSearchParams(`offset=${offset}&epoch=expired&sort=ccost&direction=${direction}`));
      catalog.token='expired';
      catalog.api=async (_,request) => {
        if(request.action==='interest') return {};
        requests.push({...request});
        if(expire) {expire=false; throw new Error('catalog_expired');}
         return {...usable,token:'reopened',epoch:'new-epoch',sort:'ccost',direction,offset:0};
      };
      await catalog.load();
      assert.equal(requests.length,2);
      assert.equal(requests[1].token,null); assert.equal(requests[1].offset,0);
       assert.equal(requests[1].sort,'ccost'); assert.equal(requests[1].direction,direction);
       assert.equal(catalog.offset,0); assert.equal(catalog.data.epoch,'new-epoch');
       assert.equal(context.location.hash,`#/sessions?period=today&sort=ccost&direction=${direction}`);
       assert.match(catalog.label.textContent,/Page 1 of 2/);
       assert.equal(catalog.status.textContent,'','successful lease recovery has no live-region announcement');
       assert.equal(catalog.status.hidden,true);
       assert.equal(catalog.recovering,false);
       assert.ok(!catalog.rebased,'no persistent rebase presentation state survives recovery');
       assert.equal(catalog.headers.find(header=>header.key==='ccost').th.attributes['aria-sort'],direction===1?'ascending':'descending');
       assert.equal(catalog.body.children[0],firstRow,'reopening retains keyed rows and focus targets');
       for (let poll=0;poll<3;poll++) {
         await catalog.poll();
         assert.equal(catalog.status.textContent,''); assert.equal(catalog.status.hidden,true);
         assert.equal(catalog.body.children[0],firstRow);
          assert.equal(catalog.operation,null); assert.equal(catalog.pan.hidden,false);
         assert.equal(delays.at(-1),5000,'recovery returns to normal visible polling');
       }
    }
    let failures=0;
    catalog.api=async (_,request)=> {if(request.action==='interest')return {}; failures++;throw new Error('catalog_expired');};
    await catalog.load();
    assert.equal(failures,2,'one bounded reopen even when the source keeps expiring');
    assert.equal(catalog.body.children.length,25); assert.equal(catalog.status.textContent,'');
     catalog.api=async ()=>{throw new Error('offline');}; await catalog.load();
     assert.equal(catalog.body.children.length,25); assert.equal(catalog.status.textContent,'');
     catalog.api=async (_,request)=>request.action==='interest'?{}:{...usable,sort:'ccost',direction:-1};
     await catalog.load();
     assert.equal(catalog.status.textContent,'','a later successful poll retires a real failure too');
     assert.equal(catalog.recovering,false);
     // A focused older-page row must not survive under the recovered page-one label.
     vm.runInContext('globalThis.rebasedCatalog = new SessionsCatalog.View(catalogApi)',context);
     const rebasedView=context.rebasedCatalog;
     rebasedView.configure(new URLSearchParams('sort=ccost&direction=-1'));
     rebasedView.update({...usable,sort:'ccost',direction:-1,offset:25});rebasedView.attached=true;
      const protectedRow=rebasedView.body.children[0], protectedLink=protectedRow.name;
     document.activeElement=protectedLink;protectedLink.blur=()=>{document.activeElement=null;};
     const savedSelection=selected;selected=null;
     let rebase=true;
     const replacement=cold.map((value,index)=>({...known,session_id:'replacement-'+index}));
     rebasedView.api=async (_,request)=>{
       if(request.action==='interest')return {};
       if(rebase){rebase=false;throw new Error('catalog_expired');}
       return {...usable,sort:'ccost',direction:-1,epoch:'replacement-epoch',view:{session_usage:replacement}};
     };
     await rebasedView.poll();
     assert.equal(rebasedView.body.children.length,25);
     assert.deepEqual(rebasedView.body.children.map(row=>row.dataset.id),replacement.map(row=>row.session_id));
     assert.equal(protectedRow.parentNode,null,'incompatible focused membership is retired before relabeling');
     assert.equal(document.activeElement,null);
     assert.equal(rebasedView.status.textContent,'');rebasedView.detach();
     selected=savedSelection;
    catalog.detach();
    catalog.recovering=false;
    catalog.update({...catalogData,total:1,view:{session_usage:[{...known,running:false}]}});
    assert.ok(!catalog.body.children[0].children[1].textContent.includes('[RUNNING]'));
    assert.equal(catalog.body.children[0].children[1],selected,'status changes preserve selected title DOM');
    selected=null;
     const liveRow=catalog.body.children[0], link=liveRow.name, model=liveRow.children[2].children[0];
     for(const [phase,label] of [['running','Running'],['background','Background activity'],['waiting','Scheduled / Waiting'],
       ['completed','Completed'],['aborted','Aborted']]) {
       const terminal=['completed','aborted'].includes(phase);
       const value={...known,running:!terminal,ongoing:terminal?null:{phase},terminal_status:terminal?phase:null,
         terminal_until_ms:terminal?Date.now()+30_000:null};
       catalog.update({...catalogData,total:1,view:{session_usage:[value]}});
       assert.equal(liveRow.statusIcon.attributes['aria-label'],label);
       assert.equal(liveRow.statusIcon.hidden,false);
       link.events.focus();
       const panel=document.body.children.at(-1);
       assert.equal(panel.children[0].dataset.phase,phase);
       assert.deepEqual(panel.textContent.split('\n').slice(1),['Pending 0']);
       assert.match(panel.textContent.split('\n')[0],new RegExp(label));
     }
     catalog.update({...catalogData,total:1,view:{session_usage:[{...known,running:false}]}});
     link.events.focus();
     assert.equal(document.body.children.at(-1).textContent,'Pending 0');
     assert.equal(liveRow.statusIcon.hidden,true);
      const duration=liveRow.children[5].children[0];
      const prompts=liveRow.children[4].children[0];
     for(const state of ['pending','retained','ready','unavailable','ready']) {
       catalog.update({...catalogData,total:1,view:{session_usage:[{...known,metric_state:state}]}});
       assert.equal(liveRow.children[5].children[0],duration);
       assert.ok(!duration.className.includes('help-value'));
       assert.equal(duration.events.focus,undefined);
       assert.equal(duration.attributes['aria-describedby'],undefined);
        assert.equal(duration.tabIndex,undefined);
        assert.ok(!prompts.className.includes('help-value'));
        assert.equal(prompts.tabIndex,undefined);
        assert.equal(Object.keys(prompts.events).length,0);
        assert.equal(prompts.attributes['aria-describedby'],undefined);
     }
     const durationHeader=catalog.headers.find(header=>header.key==='duration');
     assert.equal(durationHeader.th.children[0].tag,'button','Duration sorting remains present');
     assert.ok(durationHeader.th.children[0].events.focus,'Duration header help remains present');
     document.activeElement=link;
      const multiple={...known,model:'Main Model',multiple_models:true,has_model_details:true,contributor_models:['alpha/model','beta/model'],contributor_models_complete:false,
      display:{ccost:'1.25?',duration_ms:'3s',model_help:'alpha/model\nbeta/model\nObserved so far; contributing model coverage may be incomplete.'},prompt_count:2};
     catalog.update({...catalogData,total:1,view:{session_usage:[multiple]}});
     assert.equal(liveRow.children[2].textContent, 'Main Model*');
     assert.equal(liveRow.name,link,'focused link survives live metric deltas');
    assert.equal(liveRow.children[2].children[0],model,'metric/help target remains keyed');
     assert.equal(liveRow.children[3].textContent,'1.25?','focus cannot freeze live cost');
     assert.equal(liveRow.children[4].textContent,'2');
    model.events.focus();
    assert.match(document.body.children.at(-1).textContent,/alpha\/model[\s\S]*beta\/model/);
     assert.match(document.body.children.at(-1).textContent,/Observed so far/);
    catalog.update({...catalogData,total:1,view:{session_usage:[{...multiple,contributor_models:['alpha/model','beta/model','child/model'],
      display:{...multiple.display,model_help:'alpha/model\nbeta/model\nchild/model\nObserved so far'}} ]}});
    assert.match(document.body.children.at(-1).textContent,/child\/model/,'open help refreshes without losing its target');
    document.activeElement=null;
    catalog.update({...catalogData,total:1,view:{session_usage:[{...known,metric_states:{model:'pending'},duration_ms:null}]} });
     assert.equal(liveRow.children[2].textContent,'');
     assert.equal(model.children[0].attributes['aria-label'],'Loading model');
     assert.equal(liveRow.children[4].textContent,'0','known zero count remains independent of pending model');
    catalog.update({...catalogData,total:1,view:{session_usage:[{...cold[0],metric_state:'unavailable'}]}});
     assert.deepEqual(catalog.body.children[0].children.slice(2).map(cell => [
       cell.textContent, cell.children[0].children[0].attributes['aria-label']
     ]), ['model','CCost','prompt count','duration','context'].map(field => ['',`Loading ${field}`]));
   assert.equal(catalog.body.children[0].className,'');
    await require('../fixtures/sessions_navigation_vm.cjs')({vm, context, Node, timers});
    const ictxPage = JSON.parse(JSON.stringify(input.first)); ictxPage.revision='first-context';
   ictxPage.result.view.prompt_blocks[0].rows[0].display.incoming_context_tokens='2K → 19K';
   ictxPage.result.view.prompt_blocks[0].rows[0].display.first_incoming_context_tokens='17K';
   page=ictxPage; view.attached=true; await view.load();
   assert.equal(view.body.children[0].children[6].textContent,'17K');
   view.detach();
    await require('../fixtures/session_refresh_vm.cjs')({vm, context, Node, input, document, delays});
    require('../fixtures/session_values_vm.cjs')({vm, context, Node, input, document});
   for (const reason of ['authentication_required','host_identity_changed']) {
     vm.runInContext("globalThis.retired = new SessionDetail.View(api, 'root-0000')",context);
     const retired=context.retired;retired.update(JSON.parse(JSON.stringify(input.first)));
     retired.attached=true;retired.token='retired';
     retired.api=async (_,request)=>{if(request.action==='close')return {};throw new Error(reason);};
     await retired.load();
     assert.equal(retired.body.children.length,0,'terminal host/auth loss clears retained table');
     assert.equal(retired.footer.children.length,0);
     assert.equal(retired.attached,false);
   }
   console.log('PASS complete history, keyed selection, running/end, retained errors, lease release and navigation races');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
