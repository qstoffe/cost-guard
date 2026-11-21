// Shipped DOM/controller with real HTTP completion and explicitly source-shaped
// pending replies. Counts are synthetic, not a real-source throughput measurement.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, until, fixture, command}) => {
  const checks = [], layouts = [];
  const run = source => evaluate(`(async()=>{${source}})()`);
  await fixture('catalog-large'); await fixture('catalog-index');
  await run(`window.bannerApi=api;window.bannerBase=await api('/api/sessions',{period:'today'});
    window.bannerMode='pending';window.bannerWork={phase:'index',status:'pending',generation:1};
    window.bannerHold=false;window.releaseBanner=null;
    const load=SessionsCatalog.View.prototype.load;
    SessionsCatalog.View.prototype.load=function(){
      this.api=async(url,request,signal)=>{
        if(request.action || bannerMode==='normal')return bannerApi(url,request,signal);
        if(bannerMode==='retry')throw new Error('source_unavailable');
         if(bannerMode==='terminal')throw new Error('permission_denied');
         const data=structuredClone(bannerBase);
         Object.assign(data,{period:request.period,requested_sort:request.sort,requested_direction:request.direction,
           offset:request.offset,epoch:request.epoch||data.epoch,navigation:request.navigation,
           passive:request.passive,page_reused:false,pending_sort:bannerMode==='pending',state:'observed',progress:{...bannerWork}});
         if (request.passive) {
           Object.assign(data,{sort:request.sort,direction:request.direction,
             order_state:data.pending_sort?'provisional':'verified',candidate_navigation:data.pending_sort,
             membership_pending:data.pending_sort});
         }
        if(bannerHold){bannerHold=false;return new Promise(resolve=>{releaseBanner=()=>resolve(data);});}
        return data;
      };return load.call(this);
    };
    location.hash='#/sessions'`);
   await until('current.catalog?.data?.candidate_navigation && !current.catalog.busy');
   assert.equal(await evaluate('current.catalog.operation'),null,'cold entry does not invent a user action');
   assert.equal(await evaluate('current.catalog.next.disabled'),false);
  const quiet = async () => {
    assert.equal(await evaluate('current.catalog.status.hidden'),true);
    assert.equal(await evaluate('current.catalog.status.textContent'),'');
    assert.equal(await evaluate('current.catalog.pager.querySelectorAll("[aria-busy=true]").length'),0);
    assert.equal(await evaluate('current.catalog.root.querySelectorAll("progress,.report-loading,.sessions-candidate-scope").length'),0);
  };
  await quiet();
  for (const completed of [3,4,5]) {
    await run(`bannerWork={phase:'index',status:'pending',generation:${completed},completed:${completed},total:100};
      await current.catalog.load()`);
    await quiet();
  }
  await run(`bannerMode='normal';await current.catalog.load()`);
  await until('current.catalog.data && !current.catalog.operation && !current.catalog.busy');
  // Actual row publications alternate with background key revalidation.
  for (const running of [true,true,false]) {
    await run(`bannerBase=structuredClone(current.catalog.data);bannerMode='observed';
      bannerBase.view.session_usage[0].running=${running};
      bannerBase.view.session_usage[0].display.duration_ms='${running?'12s':'13s'}';
      bannerWork={phase:'page',status:'ready',generation:(bannerWork.generation||0)+1,completed:25,total:25};
      await current.catalog.load()`);
    await quiet();
    assert.equal(await evaluate('current.catalog.body.rows[0].classList.contains("session-running")'),running);
    await run(`bannerMode='pending';bannerWork={phase:'index',status:'pending',generation:99,completed:3,total:100};
      await current.catalog.load()`);
    await quiet();
    assert.equal(await evaluate('current.catalog.operation'),null,'passive pending_sort never creates an operation');
    assert.equal(await evaluate('current.catalog.next.disabled'),false);
  }
  checks.push('passive first acquisition, running/finishing row publications and repeated pending_sort/generation/metric polls stay silent and interactive');
  await run(`bannerMode='normal';await current.catalog.load()`);
  const operations = [
    {action:'current.catalog.periodButtons[1].button.click()',label:'Loading sessions in 7 days',phase:'page'},
    {action:'current.catalog.headers[3].th.querySelector("button").click()',label:'Sorting sessions by CCost',phase:'index'},
    {action:'current.catalog.next.focus();current.catalog.next.click()',label:'Loading Sessions page 2',phase:'page'}
  ];
  for (const {action,label,phase} of operations) {
    await evaluate(`bannerMode='pending';bannerWork={phase:'${phase}',status:'pending',generation:1};${action}`);
    await until('current.catalog.operation?.userInitiated && current.catalog.operation.pending && !current.catalog.busy');
    assert.equal(await evaluate('current.catalog.statusCount.textContent'),'','unknown totals never borrow available/indexed counts');
     assert.equal(await evaluate('current.catalog.status.textContent'),label+'…');
    await evaluate('window.userOperation=current.catalog.operation');
    for (const completed of [3,4,5]) {
      await run(`bannerWork={phase:'${phase}',status:'pending',generation:${completed},completed:${completed},total:100};
        await current.catalog.load()`);
      assert.equal(await evaluate('current.catalog.statusTask.textContent'),label);
       assert.equal(await evaluate('current.catalog.statusCount.textContent'),` · ${completed} of 100 sessions`);
       assert.equal(await evaluate('current.catalog.statusStage.textContent'),'');
       assert.doesNotMatch(await evaluate('current.catalog.status.textContent'),/worker|revalidating|cached|source|Indexed|Prepared/i);
      assert.equal(await evaluate('current.catalog.statusCount.getAttribute("aria-live")'),'off');
      assert.equal(await evaluate('current.catalog.status.getAttribute("role")'),'status');
      assert.equal(await evaluate('current.catalog.status.getAttribute("aria-atomic")'),'false');
      assert.equal(await evaluate('current.catalog.operation===userOperation'),true,'source updates retain the initiating identity');
    }
    await run(`bannerWork={phase:'index',status:'pending',generation:20,completed:1,total:80};await current.catalog.load()`);
     assert.equal(await evaluate('current.catalog.status.textContent'),label+' · 1 of 80 sessions');
    await run(`bannerMode='retry';await current.catalog.load()`);
     assert.equal(await evaluate('current.catalog.statusTask.textContent'),label);
     assert.doesNotMatch(await evaluate('current.catalog.status.textContent'),/paused|Retrying|source/);
    assert.equal(await evaluate('current.catalog.operation===userOperation && !current.catalog.operation.failed'),true);
    await run(`bannerMode='pending';bannerWork={phase:'${phase}',status:'pending',generation:21,completed:5,total:100};await current.catalog.load()`);
    assert.equal(await evaluate('current.catalog.statusTask.textContent'),label);
    await run(`bannerMode='normal';await current.catalog.load()`);
    await until('!current.catalog.operation && !current.catalog.busy');
    await quiet();
    // Once applied, the same background progress cannot resurrect that banner.
    await run(`bannerMode='pending';await current.catalog.load()`);
    await quiet();
    await run(`bannerMode='normal';await current.catalog.load()`);
  }
  checks.push('deliberate period/sort/page clicks: unknown denominator, visible 3/100→4/100→5/100, correct phase, count-live-off accessibility, revalidation reset, automatic retry, completion and silent subsequent progress');
  // Hold the old response, supersede by a different real action, then deliver late.
  await evaluate(`bannerMode='pending';bannerWork={phase:'index',status:'pending',generation:50,completed:99,total:100};
    bannerHold=true;current.catalog.headers[4].th.querySelector('button').click()`);
  await until('window.releaseBanner && current.catalog.operation?.userInitiated && current.catalog.operation.pending');
  await evaluate(`bannerWork={phase:'page',status:'pending',generation:51,completed:3,total:100};
    current.catalog.periodButtons[2].button.click()`);
  await until('current.catalog.statusTask.textContent==="Loading sessions in 30 days" && current.catalog.operation?.completed===3');
  await evaluate('releaseBanner();void 0');
  assert.equal(await evaluate('current.catalog.statusTask.textContent'),'Loading sessions in 30 days');
   assert.match(await evaluate('current.catalog.statusCount.textContent'),/3 of 100/);
  await run(`bannerMode='normal';await current.catalog.load()`);
  await until('!current.catalog.operation && !current.catalog.busy'); await quiet();
  // A passive route notification/change is not itself a user gesture.
  await evaluate(`bannerMode='pending';location.hash='#/sessions?period=30-days&sort=name&direction=1'`);
  await until('current.catalog.operation?.pending && !current.catalog.busy');
  assert.equal(await evaluate('current.catalog.operation.userInitiated'),false); await quiet();
  await run(`bannerMode='retry';await current.catalog.load()`);
  await quiet();
   await run(`bannerMode='pending';await current.catalog.load()`); await quiet();
   await run(`bannerMode='terminal';await current.catalog.load()`);
   assert.equal(await evaluate('current.catalog.operation.failed'),true);
   assert.match(await evaluate('current.catalog.status.textContent'),/Check your access, then reopen Sessions/);
  assert.equal(await evaluate('current.catalog.pager.querySelectorAll("[aria-busy=true]").length'),0);
  const ax = await command('Accessibility.getFullAXTree');
  assert.ok(ax.nodes.some(node=>node.role?.value==='status'));
  checks.push('new action replaces old label/counts; late answer cannot resurrect 99/100; passive route/recovery is not initiation; terminal error is actionable, stopped and not loading');
  return {checks,layouts};
};
