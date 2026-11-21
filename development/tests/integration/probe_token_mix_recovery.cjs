// Shipped controller and DOM over the offline host, with controlled managed report replies.
const assert = require('node:assert/strict');

module.exports = async function probe({evaluate, until, checks}) {
  await until(`current.period==='7-days' && !current.loading`);
  await evaluate(`globalThis.weekMix=current.result;selectTokenMix(current,'all')`);
  await until(`current.result?.view.token_mix_period.period==='all' && !current.loading`);
  await evaluate(`globalThis.realMixApi=api;globalThis.mixStep='busy';globalThis.mixLookups=0;globalThis.mixPolls=0;
    globalThis.mixJobs=[];globalThis.mixPaint=[];
    globalThis.mixObserver=new MutationObserver(()=>{
      const view=current.tokenMix, loader=view.root.querySelector('.report-loading');
      mixPaint.push({period:current.period,ready:!view.content.hidden,
        message:current.mixLoading?.textContent,notice:notice.textContent,
        progress:loader?.querySelector('progress').getAttribute('value'),
        pressed:view.selector.querySelector('[aria-pressed="true"]')?.textContent});
    });
    mixObserver.observe(current.tokenMix.root,{subtree:true,childList:true,attributes:true,characterData:true});
    demand={update(){}};
    api=async (path, value, signal)=>{
      if (path==='/api/data') {
        if (value.request.token_mix_scope!=='7-days' || value.retry) throw new Error('wrong_test_scope');
        mixLookups++;
        const identity={source_identity:mixStep==='rotated'?'other-source':'original-source',projection_epoch:0};
        if(mixStep==='busy') {
          mixStep='queued';const err=new Error('busy');err.retryable=true;throw err;
        }
        if(mixStep==='waiting') return {...identity,id:null,refresh:'delayed',error:'concurrent_source_change',terminal:false};
        if(mixStep==='terminal') return {...identity,id:null,terminal:true,error:'source_permission_denied'};
        if(mixStep==='queued') return {...identity,id:'finite-week',refresh:'queued'};
        if(mixStep==='ready') return {...identity,result_id:'week-v1',result:weekMix};
        if(mixStep==='refresh-error') return {...identity,id:'week-v1',result_id:'week-v1',result:weekMix,refresh:'delayed'};
        if(mixStep==='refreshed') return {...identity,result_id:'week-v2',result:{...weekMix,sequence:weekMix.sequence+1}};
        const unknown={...weekMix,source:{...weekMix.source,status:'partial',omitted_roots:1},
          view:{...weekMix.view,token_mix:null,model_token_mix:[],publisher_token_mix:[],
            token_mix_period:{...weekMix.view.token_mix_period,coverage:'unknown'}}};
        return {...identity,result_id:'other-week',result:unknown};
      }
      if (path==='/api/jobs/finite-week') {
        const phase=++mixPolls;mixJobs.push({id:'finite-week',phase});
        if(phase===1)return {status:'running',progress:{sequence:1,phase:'history',stage:'history-cache',completed:2,total:4}};
        if(phase===2){const err=new Error('report_transport_unavailable');err.retryable=true;throw err;}
        if(phase<7)return {status:'queued',error:phase%2?'history_revision_churn':'report_cache_busy',
          progress:{sequence:phase,phase:'history',stage:'history-cache',completed:1,total:4}};
        mixStep='waiting';return {status:'failed',result:{error:{code:'concurrent_source_change',retryable:true}}};
      }
      return realMixApi(path,value,signal);
    };
    current.tokenMix.buttons.find(item=>item.id==='7-days').button.focus();
    selectTokenMix(current,'7-days')`);
  await until(`mixPolls>=7 && current.waitingReason==='concurrent_source_change'`, 15000);
  const pending = await evaluate(`({loading:current.loading, failed:current.failed, period:current.period,
    progress:!!current.mixLoading.querySelector('progress:not([value])'),
    stable:mixPaint.filter(frame=>frame.period==='7-days').every(frame=>
      !frame.ready && frame.progress===null && frame.pressed==='7 days' &&
      frame.message==='Loading…Loading…' && !frame.notice),
    live:current.mixLoading.querySelectorAll('[role="status"]').length, lookups:mixLookups, jobs:mixJobs})`);
  assert.equal(pending.loading, true);
  assert.equal(pending.failed, false);
  assert.equal(pending.progress, true);
  assert.equal(pending.stable, true);
  assert.equal(pending.live, 1);
  assert.ok(pending.lookups <= 4);
  assert.equal(new Set(pending.jobs.map(job => job.id)).size, 1);
  await evaluate(`mixStep='ready'`);
  await until(`current.result===weekMix && !current.loading`);
  const retained = `document.activeElement===mixFocus && current.tokenMix.models.body===mixBody &&
    current.tokenMix.models.root.firstElementChild.isConnected && current.tokenMix.models.root.querySelector('.token-mix-pan').scrollLeft===mixX &&
    window.scrollY===mixY && current.tokenMix.models.sort===mixSortBefore && !current.mixLoading.isConnected &&
    output.getAttribute('aria-busy')==='false' && document.querySelector('#context-help')?.matches(':popover-open')`;
  await evaluate(`mixObserver.disconnect();
    globalThis.mixBody=current.tokenMix.models.body;globalThis.mixFocus=current.tokenMix.title;
    current.tokenMix.models.headers[0].th.querySelector('button').click();
    const pan=current.tokenMix.models.root.querySelector('.token-mix-pan');
    pan.scrollLeft=120;window.scrollTo(0,0);mixFocus.focus();mixFocus.click();
    globalThis.mixX=pan.scrollLeft;globalThis.mixY=window.scrollY;globalThis.mixSortBefore=current.tokenMix.models.sort`);
  await until(`document.querySelector('#context-help')?.matches(':popover-open')`);
  await evaluate(`mixStep='refresh-error';acquire(current,true)`);
  assert.equal(await evaluate(`current.result===weekMix && (${retained})`), true);
  await evaluate(`mixStep='refreshed';acquire(current,true)`);
  assert.equal(await evaluate(`current.result.sequence===weekMix.sequence+1 && (${retained})`), true);
  await evaluate(`mixStep='rotated';acquire(current,true)`);
  assert.equal(await evaluate(`current.result.view.token_mix===null &&
    current.tokenMix.status.textContent==='Usage for this period could not be verified yet.' &&
    current.tokenMix.summary.hidden && current.tokenMix.models.root.hidden && !current.failed`), true);
  await evaluate(`mixStep='terminal';current.result=null;acquire(current)`);
  assert.equal(await evaluate(`current.failed && !current.loading &&
    current.mixLoading.textContent==='Check OpenCode access, then reopen Cost Guard.' && cachedReportTimer===null`), true);
  await evaluate(`api=realMixApi;demand=null;selectTokenMix(current,'all')`);
  await until(`current.result?.view.token_mix_period.period==='all' && !current.loading`);
  checks.push({scenario:'All time → cold 7 days; bounded busy/churn/cache/transport recovery, neutral indeterminate DOM and single status; quiet retained refresh, coherent swap, identity rotation, unknown coverage, terminal permissions',
    lookups:pending.lookups, job:pending.jobs[0].id, phases:pending.jobs.map(job => job.phase)});
};
