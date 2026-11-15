// Operation generations, retained DOM and measured progress in the shipped controller.
const assert = require('node:assert/strict');
module.exports = async ({vm, context, Node, timers}) => {
  const document = context.document;
  Node.prototype.focus = function() { document.activeElement = this; };
  const calls = [];
  const row = {session_id:'previous',title:'Previous',indexed:true,has_summary:true,metric_state:'ready',
    prompt_count:1,model:'Known',context_tokens:172000,context_detail:'Estimated next incoming session context.',
    display:{ccost:'1.00',duration_ms:'1s',context_tokens:'172k'}};
  const previous = {token:'owned',epoch:'pinned',offset:25,total:117,size:25,period:'today',sort:'activity',direction:-1,
    state:'observed',page_ready:1,view:{session_usage:[row]}};
  let delayed, signal;
  context.navigationApi = async (_, value, requestSignal) => {
    calls.push(value);
    if (value.action === 'interest') return {};
    if (value.sort === 'ctx') { signal = requestSignal; return new Promise(resolve => { delayed = resolve; }); }
    return previous;
  };
  vm.runInContext('globalThis.navigation = new SessionsCatalog.View(navigationApi)', context);
  const view = context.navigation;
  new Node('main').append(view.root); view.attached = true; view.token = previous.token;
  view.update(previous);
  const labelOnlyPager = (catalog = view) => {
    for (const button of [catalog.previous,catalog.next,...catalog.pageButtons.values()]) {
      assert.equal(button.children.length,0,'pager labels must not reserve any hidden child slot');
      assert.equal(button.attributes['aria-busy'],undefined,'the existing table/banner own progress');
      assert.match(button.textContent,/^(Previous|Next|\d+)$/);
    }
  };
  labelOnlyPager();
  vm.runInContext('globalThis.singlePage = new SessionsCatalog.View(navigationApi)', context);
  const singlePage = context.singlePage;
  singlePage.update({...previous,total:1,offset:0});
  labelOnlyPager(singlePage);
  assert.equal(singlePage.previous.disabled,true); assert.equal(singlePage.next.disabled,true);
  const start = (params, button = null) => {
    view.navigateTo('#/sessions?' + params, button, button ? 'page' : null);
    view.configure(new URLSearchParams(params));
  };
  const restorePrevious = async () => {
    view.detach();
    const params = 'period=today&sort=activity&direction=-1&offset=25&epoch=pinned';
    context.location.hash = '#/sessions?' + params;
    view.configure(new URLSearchParams(params)); view.attached = true;
    await view.poll();
  };
   assert.equal(view.headers.length,7); assert.equal(view.headers[6].name,'Ctx');
   assert.equal(view.body.children[0].metrics[4].textContent,'172k');
  const retained = view.body.children[0];
  view.next.focus();
   start('sort=ctx&direction=1');
  const pending = view.load();
  await restorePrevious();
  assert.equal(signal.aborted, true);
  assert.equal(view.offset, 25); assert.equal(view.sort, 'activity'); assert.equal(view.direction, -1);
  assert.equal(view.body.children[0], retained);
  assert.equal(document.activeElement, view.next);
  assert.match(context.location.hash, /period=today.*offset=25&epoch=pinned/);
  delayed({...previous,sort:'ctx',offset:0}); await pending; await new Promise(setImmediate);
  assert.equal(view.data, previous, 'late cancelled completion cannot replace the restored snapshot');
  assert.ok(calls.some(value => value.action === 'interest' && !value.visible));
  assert.equal(calls.filter(value => !value.action).at(-1).sort, 'activity');
  start('sort=ctx&direction=1');
  const progress = (completed, generation=1, total=3217) => ({...previous,pending_sort:true,
    progress:{generation,phase:'index',status:'pending',completed,total}});
  view.update(progress(428));
   assert.equal(view.pan.hidden,false); assert.equal(view.pager.hidden,false);
  assert.equal(view.operation.percent,13);
  const banner = view.status;
  assert.equal(view.loader,undefined); assert.equal(view.cancel,undefined);
  for (let generation=2;generation<=22;generation++) {
    view.update(progress(428+generation,generation));
    assert.equal(view.operation.failed,false,'ordinary source generations cannot exhaust navigation');
    assert.equal(view.status,banner);
  }
   assert.equal(view.status.textContent,'Sorting sessions by Ctx · 450 of 3,217 sessions');
  assert.equal(view.operation.completed,450);
  const operation = view.operation;
  view.configure(new URLSearchParams('sort=ctx&direction=1'));
  assert.equal(view.operation,operation,'redundant route notification preserves pending intent');
  view.update(progress(1600)); assert.equal(view.operation.percent,49);
  view.operation.advanced = Date.now()-61000;
  view.update(progress(1601,22));
  assert.equal(view.operation.failed,false,'real count advancement survives more than a minute of slow work');
   view.update(progress(50,23)); assert.doesNotMatch(view.status.textContent,/revalidating|worker|Indexed|Prepared/);
  assert.equal(view.operation.percent,1,'new source generation explicitly restarts measured progress');
  view.operation.advanced = 0;
  view.update({...progress(50,23),progress:{...progress(50,23).progress,work:{active:true,stage:'reading_summary',sequence:1}}});
  assert.equal(view.operation.failed,false,'an owned bounded slow source read is not a no-work stall');
   assert.equal(view.status.textContent,'Sorting sessions by Ctx · 50 of 3,217 sessions');
   view.update(progress(50,23)); assert.equal(view.operation.failed,false);
   assert.equal(view.retry,undefined); assert.equal(view.pan.hidden,false);
  view.configure(new URLSearchParams('sort=ctx&direction=1'));
   assert.equal(view.operation.failed,false,'a redundant hash notification retains recoverable intent');
   assert.match(view.status.textContent,/Loading paused\. Retrying/);
  await restorePrevious();
  const pageFive = view.pageButtons.get(5);
  pageFive.focus();
  start('sort=activity&direction=-1&offset=100&epoch=pinned',pageFive);
  view.update({...previous,offset:100,progress:{generation:2,phase:'page',status:'pending',completed:4,total:17}});
  labelOnlyPager();
  assert.equal(view.pageButtons.get(5),pageFive,'pending navigation retains button identity');
  assert.equal(pageFive.disabled,false); assert.equal(pageFive.attributes['aria-disabled'],'true');
  const pendingHash = context.location.hash;
  pageFive.events.click();
  assert.equal(context.location.hash,pendingHash,'the focusable initiating button remains inert');
  assert.equal(view.next.disabled,true);
  assert.equal(view.operation.kind,'page'); assert.equal(view.operation.percent,23);
   assert.equal(view.status.textContent,'Loading Sessions page 5 · 4 of 17 sessions');
  assert.equal(view.operation.completed,4);
  view.update({...previous,offset:100,progress:{generation:2,phase:'page',status:'failed',completed:4,total:17,reason:'http_auth_failure'}});
    assert.equal(view.operation.failed,true); assert.match(view.status.textContent,/Access unavailable/);
   assert.doesNotMatch(view.status.textContent,/Cancel/);
   assert.equal(view.operation.pending,false);
   labelOnlyPager();
   const authCalls = calls.length; await view.poll();
   assert.equal(calls.length,authCalls,'terminal authority failure cannot keep retrying');
   await restorePrevious();
   assert.equal(view.offset,25); assert.equal(view.body.children[0],retained);
   view.terminal=false; // The following independent scenarios model a newly authorized host/view.
  start('sort=duration&direction=1');
  view.update({...previous,sort:'duration',direction:1,offset:0,pending_sort:false});
  assert.equal(view.operation,null); assert.equal(view.status.hidden,true);
  let releaseTimeout;
  view.api = async (_, request) => {
    calls.push(request);
    return request.action ? {} : new Promise(resolve => { releaseTimeout = resolve; });
  };
  start('sort=model&direction=1');
   const stalled = view.load();
   timers.get(view.requestDeadline)();
   await stalled;
    assert.equal(view.operation.failed,false); assert.match(view.status.textContent,/Loading paused\. Retrying/);
   assert.ok(view.retryDelay>=1000 && view.retryDelay<=30000);
  const beforeLate = calls.length;
  releaseTimeout({...previous,sort:'model',direction:1,offset:0}); await stalled;
  assert.equal(view.data.sort,'duration','a timed-out response is retired, not applied later');
  const lateCalls = calls.slice(beforeLate);
  assert.equal(lateCalls.some(request => !request.action && request.sort === 'model'),false,
    'a failed operation must not reinstate expensive sort demand');
   assert.equal(view.operation.failed,false,'timeout retains authorized automatic recovery');
  view.api = async (_, request) => { if (request.action) return {}; throw new Error('host_identity_changed'); };
  view.configure(new URLSearchParams('sort=model&direction=1')); await view.load();
   assert.equal(view.operation.failed,true); assert.match(view.status.textContent,/Could not finish/);
   assert.equal(view.data.sort,'duration');
   view.terminal=false;
  let expired = true;
  view.api = async (_, request) => {
    if (request.action) return {};
    if (expired) { expired=false; throw new Error('catalog_expired'); }
    return {...progress(600,50),token:'reopened',requested_sort:'ccost'};
  };
  start('sort=ccost&direction=1'); await view.load();
  assert.equal(view.operation.failed,false); assert.equal(view.sort,'ccost');
   assert.equal(view.token,'reopened'); assert.equal(view.status.textContent,'Sorting sessions by CCost · 600 of 3,217 sessions');
  assert.equal(view.operation.completed,600);
   assert.equal(view.data.sort,'duration','lease recovery cannot apply its Activity fallback');
   view.api = async (_, request) => { if (request.action) return {}; throw new Error('catalog_expired'); };
   await view.load();
   assert.equal(view.operation.failed,true,'restart budget is per action, not per poll');
   view.detach();
};
