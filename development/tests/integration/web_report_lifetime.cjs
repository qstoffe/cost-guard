// Real app/Attempt control flow with virtual time and transport; no browser/source.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
let now = 1000000000, sequence = 0, busy = 0, sourceWait = 0, managedResponse = null, liveUpdate = null;
const timers = new Map(), jobs = new Map(), admissions = [], lookups = [], handlers = {}, ids = {}, jobFetches = {};
const node = () => {
  const classes=new Set();
  return {dataset:{}, attrs:{}, classList:{toggle(name,on){if(on)classes.add(name);else classes.delete(name);},contains:name=>classes.has(name)},
    setAttribute(key,value){this.attrs[key]=value;}, getAttribute(key){return this.attrs[key];}, removeAttribute(){}, addEventListener(){},
    matches(selector){return selector===':focus-visible' && this.keyboardVisible===true;},
    focus(){document.activeElement=this;},
    replaceChildren(...children){this.firstChild=children[0];}, querySelector(){return null;}};
};
for (const id of ['host-state','host-message','host-details','status','result','notice','refresh','heading','scope-controls','search','content','skip','product-version','report-updating']) ids[id]=node();
const document = {hidden:false, body:node(), getElementById:id=>ids[id] || null,
  querySelector:()=>null, querySelectorAll:()=>[], addEventListener:(key,fn)=>{handlers[key]=fn;}};
const location = {hash:'#/watch'}, history = {replaceState(){}};
class Clock extends Date {static now(){return now;}}
const context = vm.createContext({document, location, history, URLSearchParams, AbortController, Date:Clock,
  setTimeout(fn,ms){const id=++sequence;timers.set(id,{fn,ms});return id;}, clearTimeout:id=>timers.delete(id),
  window:{addEventListener:(key,fn)=>{handlers[key]=fn;},scrollTo(){}},console,
  ReportRoutes:{resolve(hash){const section=hash.slice(2);return {section,title:section,
    live:section==='watch',request:['models','token-mix','ai-stats','comparisons'].includes(section)?
      {kind:section==='models'?'normal':section}:null};},controls(){}},
  ReportView:{element:node,text(element,value){element.textContent=value;},defaultUnit(){},render(parent,result){parent.replaceChildren(result);}},
  WebSettings:{apply(){return {values:{}};}},
  LiveConnection:{connect(api,update,status){liveUpdate=update;status('connected',{kind:'connected',writable:true});return {resync(){}};}},
  fetch:async (path,options)=>{
    let value;
    if(path==='/api/session') value={csrf:'synthetic'};
    else if(path==='/api/settings') value={};
    else if(path==='/api/status') value={session_detail:false};
    else if(path==='/api/reports' || path==='/api/data') {
      const body=JSON.parse(options.body),request=body.request || body;admissions.push(request.kind);
      if(path==='/api/data') lookups.push(body);
      if(path==='/api/data' && managedResponse) return {ok:true,json:async()=>managedResponse};
      const error=busy-- > 0?'busy':sourceWait-- > 0?'source_starting':null;
      if(error)return {ok:false,status:429,json:async()=>({error})};
      const id='job-'+jobs.size; jobs.set(id,{status:'running',progress:{phase:'history'},result:null});value={id};
    } else if(path.endsWith('/cancel')) assert.fail('no navigation/UI cancellation request allowed');
    else if(path.startsWith('/api/jobs/')) {const id=path.split('/').at(-1);jobFetches[id]=(jobFetches[id]||0)+1;value=jobs.get(id);}
    else assert.fail('unexpected API '+path);
    return {ok:true,json:async()=>value};
  }});
const presentation = vm.runInNewContext(fs.readFileSync('src/web/assets/render.js','utf8') + '\nReportView', {Date:Clock});
for (const key of ['LiveStatus','timestamp','setTimezone']) context.ReportView[key] = presentation[key];
for(const file of ['report-loading.js','cached-reports.js']) vm.runInContext(fs.readFileSync('src/web/assets/'+file,'utf8'),context);
// Presentation is independently tested in rendered probes; retain actual lifetime logic.
vm.runInContext(`ReportLoading.show=(parent,state)=>parent.replaceChildren(state);
  class View {update(){} attach(){}}
  const TokenMixView={valid:()=>true,View}, ComparisonsView={valid:()=>true,View};
  const AIStatsView={valid:()=>true,View,prioritize(){},observe(){return true;},remember(state,result){state.result=result;}};`,context);
vm.runInContext(fs.readFileSync('src/web/assets/app.js','utf8'),context);
const run = code=>vm.runInContext(code,context);
const settle = async()=>{for(let i=0;i<40;i++)await Promise.resolve();};
const tick = async()=>{
  const entry=[...timers].find(([,timer])=>timer.ms<=4000);
  assert.ok(entry,'expected bounded admission/poll timer');
  const [id,timer]=entry;timers.delete(id);now+=timer.ms;timer.fn();await settle();
};
const go = async section=>{location.hash='#/'+section;handlers.hashchange();await settle();};
const hide = async hidden=>{document.hidden=hidden;handlers.visibilitychange();await settle();};
async function main(){
  await settle();assert.equal(run('hostState.writable'),true);
  run('focusReport({preventScroll:true})');
  assert.equal(document.activeElement,ids.content);
  assert.equal(ids.content.classList.contains('keyboard-focus'),false,'initial scripted focus has no keyboard cue');
  document.activeElement=ids.skip;ids.skip.keyboardVisible=true;
  run('focusReport()');
  assert.equal(document.activeElement,ids.content);
  assert.equal(ids.content.classList.contains('keyboard-focus'),true,'intentional keyboard transfer keeps a visible cue');
  ids.content.keyboardVisible=true;
  run('focusReport()');
  assert.equal(ids.content.classList.contains('keyboard-focus'),false,'a script cannot infer keyboard intent from the already-focused landmark');
  for(const section of ['models','token-mix','ai-stats','comparisons']){
    busy=1;const before=admissions.length;
    await go(section);
    const original=run('current'),attempt=original.attempt;
    assert.equal(original.loading,true);assert.equal(original.active,null);
    assert.equal(original.stage,'Waiting for report slot…');
    await go('watch');await hide(true);await tick();
    assert.equal(original.attempt,attempt,'pending intent survives navigation/visibility');
    assert.equal(attempt.reason,null);assert.ok(original.active);
    const active=original.active, count=admissions.length;
    assert.equal(count,before+2,'one bounded retry, one admitted job');
    await hide(false);await go(section); // Back/Forward-equivalent route activation.
    assert.equal(run('current'),original);assert.equal(original.active,active);
    assert.equal(admissions.length,count,'return never duplicates in-flight work');
    await hide(true);await go('watch');
    if(section==='comparisons')now+=150000; // Hidden timers may be throttled past the client budget.
    const result={view:{kind:section==='models'?'normal':section,ai_stats:[{period:'30-days',start_ms:0,end_ms:now}]},
      scope:{timezone_id:'UTC'},source:{status:'acquired',observed_at_ms:now},observed_at_ms:now};
    jobs.get(active).status='complete';jobs.get(active).result=result;
    await tick();
    assert.equal(original.result,result,'completion belongs to inactive original view');
    assert.equal(original.loading,false);assert.equal(original.percent,100);
    assert.equal(run('current.section'),'watch','late completion cannot attach another page');
    assert.equal(admissions.length,count,'inactive completion schedules no history check');
    await hide(false);await go(section);
    assert.equal(run('current.result'),result);assert.equal(admissions.length,count);
  }
  // Long healthy source startup never exhausts admission or requires Retry.
  await go('watch');run(`views.delete('#/comparisons')`);sourceWait=100;
  const before=admissions.length;await go('comparisons');const pending=run('current');
  await go('watch');await hide(true);
  for(let i=0;i<40;i++)await tick();
  assert.equal(admissions.length,before+41);assert.equal(pending.loading,true);
  assert.equal(pending.failed,false);assert.ok(pending.percent<100);
  now+=2*86400000;sourceWait=0;await tick();
  const active=pending.active;assert.ok(active);
  assert.equal(pending.failed,false);
  jobs.get(active).status='complete';jobs.get(active).result={view:{kind:'comparisons'},source:{status:'acquired',observed_at_ms:now}};
  await tick();assert.equal(pending.loading,false);assert.equal(pending.failed,false);
  await hide(false);await go('comparisons');
  assert.equal(admissions.length,before+42,'return reuses automatic completion without new work');
  assert.equal(document.getElementById('cancel'),null);
  // A visible terminal Live hint wakes only the matching status wait; the job fetch decides.
  const polls=()=>[...timers.values()].filter(timer=>timer.ms===500).length;
  await go('watch');run(`views.delete('#/token-mix')`);
  await go('token-mix');const woken=run('current'),wakeJob=woken.active;
  assert.ok(wakeJob);assert.equal(woken.loading,true);assert.equal(polls(),1);
  const fetchedBefore=jobFetches[wakeJob];
  liveUpdate(null,{jobs:[{id:'job-other',status:'complete'},{id:wakeJob,status:'running'}]});await settle();
  assert.equal(woken.loading,true,'foreign or nonterminal jobs never wake the wait');
  assert.equal(jobFetches[wakeJob],fetchedBefore);
  jobs.get(wakeJob).status='complete';
  jobs.get(wakeJob).result={view:{kind:'token-mix'},source:{status:'acquired',observed_at_ms:now}};
  liveUpdate(null,{jobs:[{id:wakeJob,status:'complete'}]});await settle();
  assert.equal(woken.loading,false,'terminal hint completes without waiting out the poll');
  assert.equal(jobFetches[wakeJob],fetchedBefore+1,'one authoritative job fetch');assert.equal(polls(),0);
  liveUpdate(null,{jobs:[{id:wakeJob,status:'complete'}]});await settle();
  assert.equal(jobFetches[wakeJob],fetchedBefore+1,'replayed hints request nothing');
  await go('watch');run(`views.delete('#/comparisons')`);
  await go('comparisons');const quiet=run('current'),quietJob=quiet.active;
  assert.ok(quietJob);await hide(true);
  jobs.get(quietJob).status='complete';
  jobs.get(quietJob).result={view:{kind:'comparisons'},source:{status:'acquired',observed_at_ms:now}};
  const quietBefore=jobFetches[quietJob];
  liveUpdate(null,{jobs:[{id:quietJob,status:'complete'}]});await settle();
  assert.equal(quiet.loading,true,'hidden documents keep ordinary polling');
  assert.equal(jobFetches[quietJob],quietBefore);
  await tick();assert.equal(quiet.loading,false);assert.equal(jobFetches[quietJob],quietBefore+1);
  await hide(false);
  // One long acquire lifetime can replace failed jobs indefinitely without an ID ledger.
  await go('watch');run(`views.delete('#/token-mix')`);
  await go('token-mix');const recovering=run('current'),retryAttempt=recovering.attempt;
  const beforeRetries=admissions.length;
  for(let index=0;index<1000;index++) {
    const failedJob=recovering.active;
    jobs.get(failedJob).status='failed';
    jobs.get(failedJob).result={error:{code:index%2?'ai_stats_checkpoint_busy':'concurrent_source_change',retryable:true}};
    liveUpdate(null,{jobs:[{id:failedJob,status:'failed'}]});await settle();
    assert.equal(recovering.attempt,retryAttempt,'recovery keeps the original acquire lifetime');
    assert.equal(recovering.loading,true);assert.equal(recovering.failed,false);
    assert.equal(recovering.active,null,'failed owner is released before throttled readmission');
    const delayed=admissions.length;
    liveUpdate(null,{jobs:[{id:failedJob,status:'failed'}]});await settle();
    assert.equal(admissions.length,delayed,'replayed terminal events cannot shorten backoff');
    await tick();
    assert.ok(recovering.active);assert.notEqual(recovering.active,failedJob);
  }
  const recoveredJob=recovering.active;
  const recovered={view:{kind:'token-mix'},source:{status:'acquired',observed_at_ms:now}};
  jobs.get(recoveredJob).status='complete';jobs.get(recoveredJob).result=recovered;
  liveUpdate(null,{jobs:[{id:recoveredJob,status:'complete'}]});await settle();
  assert.equal(recovering.loading,false);assert.equal(recovering.failed,false);
  assert.equal(recovering.result,recovered,'qualified success appears automatically without Retry');
  assert.equal(admissions.length,beforeRetries+1000);
  assert.equal(polls(),0,'completion releases the last poll timer');
  assert.equal(typeof retryAttempt.woken,'string','wake state stores one identity, not a growing history');
  assert.equal(retryAttempt.woken,recoveredJob,'wake state retains only the last identity, not retired jobs');
  // A changed pinned Comparisons revision must rebase once, never readmit that pin.
  await go('watch');run(`views.delete('#/comparisons')`);
  await go('comparisons');const paging=run('current');
  const firstPage={view:{kind:'comparisons',comparisons:{offset:0,total:321,revision:'a'.repeat(64)}},source:{status:'acquired',observed_at_ms:now}};
  jobs.get(paging.active).status='complete';jobs.get(paging.active).result=firstPage;await tick();
  run(`current.request={kind:'comparisons',comparison_offset:10,comparison_revision:'a'.repeat(64)};acquire(current)`);await settle();
  const staleJob=paging.active;
  jobs.get(staleJob).status='complete';jobs.get(staleJob).result={error:{code:'session_catalog_changed',retryable:true}};
  await tick();
  console.log(JSON.stringify({trace:'changed-pin',request:paging.request,retries:paging.attempt?.retries,stage:paging.stage}));
  assert.equal(paging.request.comparison_revision,undefined,'changed pinned revision is retired before any generic retry');
  assert.equal(paging.orderReset,true);
  assert.equal(paging.result,firstPage,'last-good page survives rebase');
  jobs.get(paging.active).status='complete';jobs.get(paging.active).result=firstPage;await tick();
  // Explicit page faults are bounded; timers never silently retry a failed page.
  busy=20;
  run(`current.pageNavigation=true;current.request={kind:'comparisons',comparison_offset:10,comparison_revision:'a'.repeat(64)};acquire(current)`);await settle();
  for(let i=0;i<3;i++)await tick();
  assert.equal(paging.loading,false);assert.equal(paging.failed,true);
  assert.match(paging.message,/three recovery attempts/);assert.equal(paging.result,firstPage);
  const failedAdmissions=admissions.length;run('scheduleCachedReport();enterCachedReport(current)');await settle();
  assert.equal(admissions.length,failedAdmissions,'only explicit Retry can restart failed navigation');
  busy=0;run('acquire(current)');await settle();
  now+=45001;await tick();
  assert.equal(paging.loading,false);assert.equal(paging.failed,true);
  assert.match(paging.message,/45 seconds/);assert.equal(paging.result,firstPage);
  run('acquire(current)');await settle();
  const nextPage={...firstPage,view:{...firstPage.view,comparisons:{...firstPage.view.comparisons,offset:10}}};
  jobs.get(paging.active).status='complete';jobs.get(paging.active).result=nextPage;await tick();
  assert.equal(paging.result,nextPage);assert.equal(paging.failed,false);assert.equal(paging.pageNavigation,false);
  // Managed first completion preserves an actually old as-of, not only a shifted worker timer.
  await go('watch');run(`views.delete('#/models');demand={update(){}};`);
  const started=now;await go('models');const aged=run('current'),owned=aged.active;
  now+=2*86400000;
  const historical={view:{kind:'normal'},source:{status:'acquired',observed_at_ms:started}};
  jobs.get(owned).status='complete';jobs.get(owned).result=historical;
  await tick();
  assert.equal(aged.result,historical);assert.equal(aged.withheld,false);assert.equal(aged.failed,false);
  assert.equal(ids.result.firstChild,historical,'aged first completion is displayed');
  assert.ok(!ids['report-updating'].textContent);
  assert.ok(!fs.readFileSync('src/web/assets/index.html','utf8').includes('id="report-updating"'));
  assert.ok(!ids['report-updating'].textContent);
  const revision=aged.dataRevision,content=ids.result.firstChild,ownedCount=jobs.size;
  for(const refresh of ['running','queued','scheduled','delayed','stopped']) {
    managedResponse={id:'distinct-refresh-job',result_id:owned,result:historical,refresh};
    await run('acquire(current,true)');await settle();
    assert.equal(aged.dataRevision,revision,'refresh job cannot manufacture a new publication');
    assert.equal(ids.result.firstChild,content);assert.equal(aged.withheld,false);
    assert.equal(historical.source.observed_at_ms,started);
    assert.equal(jobs.size,ownedCount,'publication lookups do not acquire source work');
    assert.ok(!ids['report-updating'].textContent);
  }
  managedResponse={id:owned,result_id:owned,result:historical,refresh:'scheduled'};
  await go('watch');await go('models');
  assert.equal(aged.result,historical);assert.equal(aged.withheld,false);
  // Managed historical recovery follows host due times, even with no publication.
  const hostTick=async()=>{
    const entry=[...timers].find(([,timer])=>timer.ms===5000);
    assert.ok(entry,'host lookup must remain scheduled without a result');
    const [id,timer]=entry;timers.delete(id);now+=timer.ms;timer.fn();await settle();
  };
  for(const section of ['token-mix','ai-stats']) {
    await go('watch');run(`views.delete('#/${section}')`);
    managedResponse={id:null,result:null,refresh:'delayed',error:'report_unavailable',terminal:false};
    await go(section);const recovering=run('current');
    for(let i=0;i<8;i++) {
      assert.equal(recovering.loading,true);assert.equal(recovering.failed,false);
      assert.equal(recovering.active,null);
      await hostTick();
    }
    assert.equal(ids.refresh.hidden,true,'no Retry button while recovering');
    const retainedResult={view:{kind:section,ai_stats:[{period:'30-days'}]},source:{status:'acquired',observed_at_ms:now}};
    managedResponse={id:'published',result_id:'published',result:retainedResult,refresh:'scheduled'};
    await hostTick();
    assert.equal(recovering.result,retainedResult);assert.equal(recovering.failed,false);
    managedResponse={id:null,result:null,refresh:'stopped',error:'report_cache_unavailable',terminal:true};
    await run('acquire(current,true)');await settle();
    assert.equal(recovering.result,retainedResult,'absent publication never erases matching last-good data');
    assert.equal(recovering.withheld,false);assert.equal(recovering.failed,true);
    assert.equal(ids.refresh.hidden,true,'no Retry button after a report failure');
    // A cold terminal failure stays truthful, but lookups can see relevant host recovery.
    await go('watch');run(`views.delete('#/${section}')`);await go(section);
    const cold=run('current');assert.equal(cold.failed,true);assert.equal(cold.result,null);
    assert.equal(ids.refresh.hidden,true);
    managedResponse={id:'recovered',result_id:'recovered',result:retainedResult,refresh:'scheduled'};
    await hostTick();
    assert.equal(cold.result,retainedResult);assert.equal(cold.failed,false);
  }
  assert.ok(lookups.every(body=>body.retry===false),'automatic history never bypasses host backoff with explicit Retry');
  // Host owns source retries; only a previously observed live view earns quiet grace.
  run(`liveValue={view:{}}; connectionStatus('Retrying source read', {kind:'source_retrying',observedAt:null})`);
  assert.equal(ids['host-state'].hidden,false,'no successful observation cannot be disguised as retained success');
  run(`connectionStatus('Live connected.', {kind:'connected',observedAt:100})`);
  const graceStart=now;
  run(`connectionStatus('Retrying source read', {kind:'source_retrying',observedAt:100})`);
  for(const elapsed of [1000,5000,10000,30000,59999]) {
    now=graceStart+elapsed;
    run(`connectionStatus('Retrying source read', {kind:'source_retrying',observedAt:100})`);
    assert.equal(ids['host-state'].hidden,true);
    assert.equal(ids.status.textContent,'Live connected.');
    assert.equal(ids.status.attrs['aria-description'],'');
  }
  now=graceStart+60000;
  run(`connectionStatus('Retrying source read', {kind:'source_retrying',observedAt:100})`);
  assert.equal(ids['host-state'].hidden,true,'sustained background retry remains silent');
  run(`connectionStatus('Live connected.', {kind:'connected',observedAt:100});
    connectionStatus('Retrying source read', {kind:'source_retrying',observedAt:100})`);
  assert.equal(ids['host-state'].hidden,true,'same source replay adds no warning');
  run(`connectionStatus('Live connected.', {kind:'connected',observedAt:101});
    connectionStatus('Retrying source read', {kind:'source_retrying',observedAt:101})`);
  assert.equal(ids['host-state'].hidden,true,'genuinely newer evidence restores grace');
  for(const kind of ['source_unavailable','offline','authorization_required']) {
    context.failureKind=kind;
    run(`connectionStatus('Action required', {kind:failureKind})`);
    assert.equal(ids['host-state'].hidden,false,'actionable failures remain immediate');
  }
  console.log('PASS: retained intent, aged managed completion/display, stable publication identity, visible terminal wake, honest refresh and factual errors');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
