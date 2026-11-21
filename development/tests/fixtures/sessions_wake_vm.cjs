// Shipped controller: source-qualified wakeups never become client-side rows.
const assert = require('node:assert/strict');
module.exports = async ({vm, context, Node, timers}) => {
  context.wakeApi = async () => {};
  vm.runInContext('globalThis.waking = new SessionsCatalog.View(wakeApi)', context);
  const view = context.waking;
  const row = {session_id:'old',title:'Old',indexed:true,has_summary:true,model:'Known',prompt_count:1};
  const page = {token:'owned',epoch:'one',offset:0,total:1,size:25,period:'today',
    sort:'activity',direction:-1,state:'observed',view:{session_usage:[row]}};
  view.configure(new URLSearchParams('period=today'));
  new Node('main').append(view.root); view.attached = true; view.update(page);
  const kept = view.body.children[0];
  const pending = {...page,passive:true,pending_sort:true,order_state:'provisional',epoch:'two',total:2,
    view:{session_usage:[{session_id:'new',title:'Actual source title',metric_state:'pending'},row]}};
  view.update(pending);
  assert.equal(view.body.children[0].titleNode.textContent,'Actual source title');
  assert.equal(view.body.children[0].metrics[0].textContent,'');
  assert.equal(view.body.children[0].metrics[0].children[0].attributes['aria-label'],'Loading model');
  assert.equal(view.body.children[1],kept);
  assert.equal(view.status.hidden,true);
  const calls = [];
  let release;
  view.api = async (_, request) => {
    if (request.action) return {};
    calls.push(request); return new Promise(resolve => {release = resolve;});
  };
  view.wake('owner:1'); const timer = view.timer;
  view.wake('owner:1'); view.wake('owner:2');
  assert.equal(view.timer,timer,'bursts coalesce rather than postpone the wake');
  const flight = view.poll(); await new Promise(setImmediate);
  assert.equal(calls.length,1); assert.equal(calls[0].passive,true);
  view.wake('owner:3'); view.wake('owner:4');
  assert.equal(calls.length,1,'one page request in flight');
  release(pending); await flight;
  assert.equal(view.wakePending,true,'only one trailing wake is retained');
  const trailing = view.poll(); await new Promise(setImmediate);
  release(pending); await trailing;
  view.wake('owner:4'); assert.equal(view.wakePending,false,'repeated clock frames do not fetch');
  view.operation = {userInitiated:true,kind:'sort',navigation:1,advanced:Date.now(),highWater:-1};
  view.sort = 'ccost'; view.direction = 1;
  view.wake('owner:5');
  const action = view.operation, applied = view.data;
  view.update({...pending,navigation:1});
  assert.equal(view.operation,action); assert.equal(view.data,applied);
  assert.match(view.status.textContent,/Sorting sessions by CCost/);
  view.operation = null; view.wakePending = false;
  view.offset = 25; const olderTimer = view.timer; view.wake('owner:6');
  assert.equal(view.timer,olderTimer); assert.equal(view.wakePending,false);
  view.offset = 0; context.document.hidden = true; view.wake('owner:7');
  assert.equal(view.timer,olderTimer); assert.equal(view.wakePending,false);
  context.document.hidden = false; view.detach(); view.wake('owner:8');
  assert.equal(view.wakePending,false);
  assert.equal(timers.has(view.timer),false);
};
