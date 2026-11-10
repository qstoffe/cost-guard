// Operation generations, retained DOM and measured progress in the shipped controller.
const assert = require('node:assert/strict');
module.exports = async ({vm, context, Node, timers}) => {
  const document = context.document;
  Node.prototype.focus = function() { document.activeElement = this; };
  const calls = [];
  const row = {session_id:'previous',title:'Previous',indexed:true,has_summary:true,metric_state:'ready',
    prompt_count:1,model:'Known',display:{ccost:'1.00',duration_ms:'1s'}};
  const previous = {token:'owned',epoch:'pinned',offset:50,total:117,size:50,sort:'activity',direction:-1,
    state:'observed',page_ready:1,view:{session_usage:[row]}};
  let delayed, signal;
  context.navigationApi = async (_, value, requestSignal) => {
    calls.push(value);
    if (value.action === 'interest') return {};
    if (value.sort === 'ccost') { signal = requestSignal; return new Promise(resolve => { delayed = resolve; }); }
    return previous;
  };
  vm.runInContext('globalThis.navigation = new SessionsCatalog.View(navigationApi)', context);
  const view = context.navigation;
  new Node('main').append(view.root); view.attached = true; view.token = previous.token;
  view.update(previous);
  const retained = view.body.children[0];
  view.next.focus();
  view.configure(new URLSearchParams('sort=ccost&direction=1'));
  const pending = view.load();
  view.cancelNavigation();
  assert.equal(signal.aborted, true);
  assert.equal(view.offset, 50); assert.equal(view.sort, 'activity'); assert.equal(view.direction, -1);
  assert.equal(view.body.children[0], retained);
  assert.equal(document.activeElement, view.next);
  assert.match(context.location.hash, /offset=50&epoch=pinned/);
  delayed({...previous,sort:'ccost',offset:0}); await pending; await new Promise(setImmediate);
  assert.equal(view.data, previous, 'late cancelled completion cannot replace the restored snapshot');
  assert.ok(calls.some(value => value.action === 'interest' && !value.visible));
  assert.equal(calls.filter(value => !value.action).at(-1).sort, 'activity');
  view.configure(new URLSearchParams('sort=model&direction=1'));
  const progress = (completed, generation=1, total=3217) => ({...previous,pending_sort:true,
    progress:{generation,phase:'index',status:'pending',completed,total}});
  view.update(progress(428));
  assert.equal(view.pan.hidden,true); assert.equal(view.pager.hidden,true);
  assert.equal(view.loader.bar.max,100); assert.equal(view.loader.bar.value,13);
  assert.match(view.loader.stage.textContent,/Indexing Model.*428 of 3217/);
  assert.equal(view.loader.status.textContent,'Indexing Model');
  view.update(progress(1600)); assert.equal(view.loader.bar.value,49);
  view.update(progress(50,2)); assert.match(view.loader.stage.textContent,/Source changed; restarting/);
  assert.equal(view.loader.bar.value,1,'new source generation explicitly restarts measured progress');
  view.operation.advanced = 0;
  view.update(progress(50,2)); assert.equal(view.operation.failed,true);
  assert.equal(view.retry.hidden,false); assert.equal(view.pan.hidden,false);
  assert.match(view.loader.stage.textContent,/no_source_progress/);
  view.cancelNavigation(); await new Promise(setImmediate);
  view.configure(new URLSearchParams('sort=activity&direction=-1&offset=100&epoch=pinned'));
  view.update({...previous,offset:100,progress:{generation:2,phase:'page',status:'pending',completed:4,total:17}});
  assert.equal(view.operation.kind,'page'); assert.equal(view.loader.bar.value,23);
  assert.match(view.loader.stage.textContent,/Preparing page 3.*4 of 17/);
  view.update({...previous,offset:100,progress:{generation:2,phase:'page',status:'failed',completed:4,total:17,reason:'http_auth_failure'}});
  assert.equal(view.operation.failed,true); assert.match(view.loader.stage.textContent,/http_auth_failure/);
  view.cancelNavigation(); await new Promise(setImmediate);
  assert.equal(view.offset,50); assert.equal(view.body.children[0],retained);
  view.configure(new URLSearchParams('sort=duration&direction=1'));
  view.update({...previous,sort:'duration',direction:1,offset:0,pending_sort:false});
  assert.equal(view.operation,null); assert.equal(view.loader.root.hidden,true);
  assert.equal(view.loader.bar.value,100,'100 is reserved for an applied correct page');
  let releaseTimeout;
  view.api = async (_, request) => {
    calls.push(request);
    return request.action ? {} : new Promise(resolve => { releaseTimeout = resolve; });
  };
  view.configure(new URLSearchParams('sort=model&direction=1'));
  const stalled = view.load();
  timers.get(view.requestDeadline)();
  assert.equal(view.operation.failed,true); assert.match(view.loader.stage.textContent,/request_timeout/);
  const beforeLate = calls.length;
  releaseTimeout({...previous,sort:'model',direction:1,offset:0}); await stalled;
  assert.equal(view.data.sort,'duration','a timed-out response is retired, not applied later');
  const lateCalls = calls.slice(beforeLate);
  assert.equal(lateCalls.some(request => !request.action && request.sort === 'model'),false,
    'a failed operation must not reinstate expensive sort demand');
  assert.ok(lateCalls.some(request => request.action === 'interest' && request.token === previous.token && !request.visible));
  view.api = async (_, request) => { if (request.action) return {}; throw new Error('host_identity_changed'); };
  view.configure(new URLSearchParams('sort=model&direction=1')); await view.load();
  assert.equal(view.operation.failed,true); assert.match(view.loader.stage.textContent,/host_identity_changed/);
  assert.equal(view.data.sort,'duration');
  view.detach();
};
