// Actual shipped complete-history assets in a deterministic VM/DOM.
const assert = require('node:assert/strict'), vm = require('node:vm'), fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.dataset = {}; this.events = {}; this.text = ''; this.attributes = {}; }
  set textContent(value) { this.text = String(value); this.replaceChildren(); }
  get textContent() { return this.text + this.children.map(c => c.textContent).join(''); }
  get parentNode() { return this.parent; }
  get isConnected() { return Boolean(this.parent); }
  append(...children) { for (const child of children) { child.remove(); this.children.push(child); child.parent = this; } }
  replaceChildren(...children) { for (const child of this.children) child.parent = null; this.children = []; this.append(...children); }
  insertBefore(child, before) { child.remove(); const index = before ? this.children.indexOf(before) : this.children.length; this.children.splice(index, 0, child); child.parent = this; }
  remove() { if (this.parent) { this.parent.children.splice(this.parent.children.indexOf(this), 1); this.parent = null; } }
  contains(child) { return child === this || this.children.some(c => c.contains(child)); }
  setAttribute(key, value) { this.attributes[key] = value; }
  removeAttribute(key) { delete this.attributes[key]; }
  addEventListener(key, fn) { this.events[key] = fn; }
  getBoundingClientRect() { return {top: 100, bottom: 120}; }
}
async function main() {
  let selected = null, offline = false, page = input.first;
  const calls = [], scrolls = [], delays = [], timers = new Map(); let timerId = 0;
  const document = {createElement: tag => new Node(tag), createElementNS: (_, tag) => new Node(tag), activeElement: null};
  const context = vm.createContext({document, console, Date, URLSearchParams, location: {},
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
  for (const file of ['render', 'watch', 'session', 'sessions']) vm.runInContext(fs.readFileSync(`src/web/assets/${file}.js`, 'utf8'), context);
  vm.runInContext("globalThis.view = new SessionDetail.View(api, 'root-0000')", context);
  const view = context.view; view.attached = true;
  new Node('main').append(view.root);
  await view.load();
  assert.equal(view.body.children.length, 100);
  assert.equal(view.body.children[0].children.length, 10);
  assert.match(view.root.textContent, /Show all sessions/);
  assert.match(view.root.textContent, /Session ID: root-0000/);
  assert.match(view.footer.textContent, /Complete session/);
  assert.equal(view.footer.children.length, 10);
  assert.ok(!/Freeze|Snapshot|Go to row|Refresh|Token Mix order/.test(view.root.textContent));
  const row = view.body.children[10], cell = row.children[0];
  page = input.changed;
  await view.load();
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
  const latest = page.result.view.prompt_blocks[0].rows.at(-1); latest.in_progress = true; page.revision = 'running';
  await view.load();
  assert.match(view.body.children.at(-1).textContent, /\[RUNNING\]/);
  assert.equal(view.body.children.at(-1).className, 'session-running');
  latest.in_progress = false; page.revision = 'ended'; await view.load();
  assert.ok(!view.body.children.at(-1).textContent.includes('[RUNNING]'));
  assert.equal(view.body.children.at(-1).className, '');
  const retained = view.body.textContent; offline = true; await view.load();
  assert.equal(view.body.textContent, retained); assert.match(view.status.textContent, /retained/);
  assert.ok(calls.some(call => call.action === 'chunk' && call.offset === 100));
  assert.equal(scrolls.length, 0, 'stable document geometry never scrolls');
  view.detach();
  assert.ok(calls.some(call => call.action === 'close' && call.token === 'owned'));
  offline = false;
  let pending = true, pendingState = 'observed';
  context.pendingApi = async (path, value) => {
    if (value.action === 'open') return {token:'pending-lease'};
    if (value.action === 'close') return {};
    if (pending) return {state:pendingState,pending:true,result:null};
    const result = JSON.parse(JSON.stringify(input.first));
    result.offset = value.offset;
    result.result.view.prompt_blocks[0].rows = result.result.view.prompt_blocks[0].rows.slice(value.offset, value.offset + 25);
    return result;
  };
  vm.runInContext("globalThis.pendingView = new SessionDetail.View(pendingApi, 'root-0000')", context);
  const pendingView = context.pendingView;
  pendingView.attach(new Node('main')); await new Promise(setImmediate);
  assert.equal(pendingView.body.children.length, 0);
   assert.match(pendingView.status.textContent, /Loading session/);
   assert.equal(pendingView.status.children[1].tag, 'progress');
   assert.equal(pendingView.status.children[1].attributes.value, undefined, 'initial progress is indeterminate');
  assert.equal(pendingView.status.hidden, false);
  assert.equal(delays.at(-1), 5000, 'pending capture retains the configured five-second polling cadence');
  assert.equal(timers.size, 1);
  pendingState = 'source_unavailable'; await pendingView.load();
   assert.match(pendingView.status.textContent, /Source unavailable/);
   assert.ok(!pendingView.status.children.some(node => node.tag === 'progress'));
  assert.ok(!pendingView.status.textContent.includes('Waiting'), 'a pending lease cannot hide explicit source failure');
  pending = false;
  const [pendingTimer, resume] = timers.entries().next().value;
  timers.delete(pendingTimer); resume(); await new Promise(setImmediate);
  assert.equal(pendingView.body.children.length, 100);
  assert.equal(pendingView.status.hidden, true);
  pendingView.detach(); assert.equal(timers.size, 0);
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
  const catalogData = {token: 'catalog', epoch: 'epoch', total: 0, size: 50, offset: 0,
    sort: 'activity', direction: -1, state: 'observed', view: {session_usage: []}};
  context.catalogApi = async (path, value) => {
    catalogCalls.push(value);
    if (catalogCalls.length === 1) return new Promise(resolve => { resolveCatalog = resolve; });
    return catalogData;
  };
  vm.runInContext('globalThis.catalog = new SessionsCatalog.View(catalogApi)', context);
  const catalog = context.catalog;
  catalog.configure(new URLSearchParams()); catalog.attach(parent);
  catalog.detach(); catalog.configure(new URLSearchParams('sort=ccost')); catalog.attach(parent);
  resolveCatalog(catalogData); await new Promise(setImmediate);
  assert.equal(catalogCalls.length, 2, 'changed route reruns after stale request completes');
  assert.equal(catalogCalls[1].sort, 'ccost');
  assert.equal(timers.size, 1, 'catalog route race leaves one polling timer');
   catalog.detach(); assert.equal(timers.size, 0);
   const timestamp = expression => vm.runInContext(`SessionsCatalog.localTimestamp(${expression})`, context);
   const originalTZ = process.env.TZ;
   const originalLocaleString = Date.prototype.toLocaleString;
   try {
     for (const locale of ['sv-SE', 'en-US']) for (const [zone, expected] of [
       ['Europe/Stockholm', ['2026-03-29 01:30', '2026-03-29 03:30', '2026-10-25 02:30', '2026-10-25 02:30']],
       ['America/New_York', ['2026-03-28 20:30', '2026-03-28 21:30', '2026-10-24 20:30', '2026-10-24 21:30']]]) {
       process.env.TZ = zone;
       // Formatting must not invoke browser-locale defaults, including 12-hour locales.
       Date.prototype.toLocaleString = () => { throw new Error('locale-dependent timestamp: ' + locale); };
       ['2026-03-29T00:30Z', '2026-03-29T01:30Z', '2026-10-25T00:30Z', '2026-10-25T01:30Z'].forEach((instant, index) => {
         assert.equal(timestamp(Date.parse(instant)), expected[index]);
       });
     }
   } finally { if (originalTZ === undefined) delete process.env.TZ; else process.env.TZ = originalTZ; Date.prototype.toLocaleString = originalLocaleString; }
   assert.equal(timestamp(null), 'N/A');
   const cold = Array.from({length:50}, (_, index) => ({session_id:'cold-'+index, title:'Pending '+index,
     last_activity_ms:1000, indexed:false, has_summary:false, metric_state:'pending', display:{ccost:'N/A',duration_ms:'N/A'}}));
   catalog.update({...catalogData,total:51,view:{session_usage:cold}});
   assert.equal(catalog.body.children.length, 50);
   assert.ok(catalog.body.children.every(row => row.children.slice(2).every(cell => cell.textContent === 'Loading…')));
   assert.equal(catalog.previous.tag, 'button'); assert.equal(catalog.previous.disabled,true); assert.equal(catalog.next.disabled,false);
   catalog.next.events.click(); assert.match(context.location.hash, /offset=50/);
   const known = {...cold[0],indexed:true,has_summary:true,metric_state:'ready',running:true,prompt_count:0,model:'N/A',display:{ccost:'0.00',duration_ms:'0s'}};
   catalog.update({...catalogData,offset:50,total:51,view:{session_usage:[known]}});
   assert.equal(catalog.previous.disabled,false); assert.equal(catalog.next.disabled,true);
   assert.equal(catalog.body.children[0].className,'session-running');
   assert.match(catalog.body.children[0].children[1].textContent,/^\[RUNNING\] Pending/);
   assert.deepEqual(catalog.body.children[0].children.slice(2).map(cell=>cell.textContent),['N/A','0.00','0','0s']);
   selected=catalog.body.children[0].children[1];
   catalog.update({...catalogData,total:1,view:{session_usage:[{...known,running:false}]}});
   assert.equal(catalog.body.children[0].className,'');
   assert.ok(!catalog.body.children[0].children[1].textContent.includes('[RUNNING]'));
   assert.equal(catalog.body.children[0].children[1],selected,'status changes preserve selected title DOM');
   selected=null;
   catalog.update({...catalogData,total:1,view:{session_usage:[{...cold[0],metric_state:'unavailable'}]}});
   assert.ok(catalog.body.children[0].children.slice(2).every(cell=>cell.textContent==='Unavailable'));
   assert.equal(catalog.body.children[0].className,'');
   const ictxPage = JSON.parse(JSON.stringify(input.first)); ictxPage.revision='first-context';
   ictxPage.result.view.prompt_blocks[0].rows[0].display.incoming_context_tokens='2K → 19K';
   ictxPage.result.view.prompt_blocks[0].rows[0].display.first_incoming_context_tokens='17K';
   page=ictxPage; view.attached=true; await view.load();
   assert.equal(view.body.children[0].children[6].textContent,'17K');
   view.detach();
  console.log('PASS complete history, keyed selection, running/end, retained errors, lease release and navigation races');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
