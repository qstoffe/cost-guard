// Real app/Attempt control flow with virtual time and transport; no browser/source.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
let now = 0, sequence = 0, busy = 0, sourceWait = 0;
const timers = new Map(), jobs = new Map(), admissions = [], handlers = {}, ids = {};
const node = () => ({dataset:{}, attrs:{}, setAttribute(key,value){this.attrs[key]=value;}, removeAttribute(){}, addEventListener(){}, focus(){},
  replaceChildren(...children){this.firstChild=children[0];}, querySelector(){return null;}});
for (const id of ['host-state','host-message','host-details','status','result','notice','refresh','heading','scope-controls','search','content','skip','product-version']) ids[id]=node();
const document = {hidden:false, body:node(), getElementById:id=>ids[id] || null,
  querySelector:()=>null, querySelectorAll:()=>[], addEventListener:(key,fn)=>{handlers[key]=fn;}};
const location = {hash:'#/watch'}, history = {replaceState(){}};
class Clock extends Date {static now(){return now;}}
const context = vm.createContext({document, location, history, URLSearchParams, AbortController, Date:Clock,
  setTimeout(fn,ms){const id=++sequence;timers.set(id,{fn,ms});return id;}, clearTimeout:id=>timers.delete(id),
  window:{addEventListener:(key,fn)=>{handlers[key]=fn;}},
  ReportRoutes:{resolve(hash){const section=hash.slice(2);return {section,title:section,
    live:section==='watch',request:['models','token-mix','ai-stats','comparisons'].includes(section)?
      {kind:section==='models'?'normal':section}:null};},controls(){}},
  ReportView:{element:node,text(){},defaultUnit(){},render(parent,result){parent.replaceChildren(result);}},
  WebSettings:{apply(){return {values:{}};}},
  LiveConnection:{connect(api,update,status){status('connected',{kind:'connected',writable:true});return {resync(){}};}},
  fetch:async (path,options)=>{
    let value;
    if(path==='/api/session') value={csrf:'synthetic'};
    else if(path==='/api/settings') value={};
    else if(path==='/api/status') value={session_detail:false};
    else if(path==='/api/reports') {
      const request=JSON.parse(options.body);admissions.push(request.kind);
      const error=busy-- > 0?'busy':sourceWait-- > 0?'source_starting':null;
      if(error)return {ok:false,status:429,json:async()=>({error})};
      const id='job-'+jobs.size; jobs.set(id,{status:'running',progress:{phase:'history'},result:null});value={id};
    } else if(path.endsWith('/cancel')) assert.fail('no navigation/UI cancellation request allowed');
    else if(path.startsWith('/api/jobs/')) value=jobs.get(path.split('/').at(-1));
    else assert.fail('unexpected API '+path);
    return {ok:true,json:async()=>value};
  }});
context.ReportView.LiveStatus = vm.runInNewContext(fs.readFileSync('src/web/assets/render.js','utf8') + '\nReportView.LiveStatus', {Date:Clock});
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
    const result={view:{kind:section==='models'?'normal':section,ai_stats:[{period:'30-days'}]},
      source:{status:'acquired'},observed_at_ms:now};
    jobs.get(active).status='complete';jobs.get(active).result=result;
    await tick();
    assert.equal(original.result,result,'completion belongs to inactive original view');
    assert.equal(original.loading,false);assert.equal(original.percent,100);
    assert.equal(run('current.section'),'watch','late completion cannot attach another page');
    assert.equal(admissions.length,count,'inactive completion schedules no history check');
    await hide(false);await go(section);
    assert.equal(run('current.result'),result);assert.equal(admissions.length,count);
  }
  // Exhausted pre-admission waits end with their real reason while inactive.
  await go('watch');run(`views.delete('#/comparisons')`);sourceWait=100;
  const before=admissions.length;await go('comparisons');const failed=run('current');
  await go('watch');await hide(true);
  for(let i=0;i<8;i++)await tick();
  assert.equal(admissions.length,before+9);assert.equal(failed.loading,false);
  assert.equal(failed.failed,true);assert.match(failed.message,/Source startup did not recover/);
  assert.equal(failed.attempt,null);assert.ok(failed.percent<100);
  await hide(false);await go('comparisons');
  assert.equal(admissions.length,before+9,'return retains error instead of a new hidden retry loop');
  assert.equal(ids.refresh.hidden,false,'real failures retain Retry');
  assert.equal(document.getElementById('cancel'),null);
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
    assert.equal(ids.status.attrs['aria-description'],'Retrying source read');
  }
  now=graceStart+60000;
  run(`connectionStatus('Retrying source read', {kind:'source_retrying',observedAt:100})`);
  assert.equal(ids['host-state'].hidden,false,'sustained source retry has one host notice');
  run(`connectionStatus('Live connected.', {kind:'connected',observedAt:100});
    connectionStatus('Retrying source read', {kind:'source_retrying',observedAt:100})`);
  assert.equal(ids['host-state'].hidden,false,'same source replay never resets failure clock');
  run(`connectionStatus('Live connected.', {kind:'connected',observedAt:101});
    connectionStatus('Retrying source read', {kind:'source_retrying',observedAt:101})`);
  assert.equal(ids['host-state'].hidden,true,'genuinely newer evidence restores grace');
  for(const kind of ['source_unavailable','offline','authorization_required']) {
    context.failureKind=kind;
    run(`connectionStatus('Action required', {kind:failureKind})`);
    assert.equal(ids['host-state'].hidden,false,'actionable failures remain immediate');
  }
  console.log('PASS: four routes preserve pending/admitted work, hidden completion, retained errors, bounded retries and no duplicate/new inactive scans');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
