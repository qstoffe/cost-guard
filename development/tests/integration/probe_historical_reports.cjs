// Opt-in real installation report/UI proof. Only sanitized aggregate evidence leaves this module.
const assert = require('node:assert/strict');

module.exports = async function({command,evaluate,until,tab,checks}) {
  const observations=[];
  await evaluate(`window.__traceApi=api; window.__reportTrace=[]; window.__traceSeen=new Map();
    api=async function(path,...args) {
      const value=await __traceApi(path,...args);
      if(path==='/api/interest' || path==='/api/data' || path.startsWith('/api/jobs/')) {
        const result=value.result, work=result?.view?.ai_stats_work;
        const row={endpoint:path.startsWith('/api/jobs/')?'job':path, id:value.id,
          section:args[0]?.section, visible:args[0]?.visible, lease:value.lease_seconds,
          refresh:value.refresh, terminal:value.terminal, error:value.error || result?.error?.code,
          status:value.status, policy:result?.view?.ai_stats_policy, valid:result?.view?.kind==='ai-stats'?AIStatsView.valid(result):undefined,
          ready:work?.scopes?.[current?.period]?.ready, completed:work?.completed,total:work?.total,
          checkpoint:work?.checkpoint_error, host:hostState.kind};
        const key=row.endpoint+':'+(row.id||row.section||''); const signature=JSON.stringify(row);
        if(signature!==__traceSeen.get(key)) {
          __traceSeen.set(key,signature); __reportTrace.push(row);
          if(__reportTrace.length>96) __reportTrace.splice(1,1);
        }
      }
      return value;
    }; if(demand) demand.api=api;`);
  for(const section of ['ai-stats','token-mix']) {
    const started=Date.now();
    await evaluate(`location.hash='#/${section}'`);
    await until(`current?.section==='${section}'`,tab);
    if(section==='ai-stats') assert.equal(await evaluate(`!!current.result ||
      (output.querySelectorAll('.ai-stat').length===12 && [...output.querySelectorAll('.ai-stat')].every(c=>c.textContent==='Loading…' && c.childNodes.length===1))`),true);
    await until(`current?.section==='${section}' && current.result && !current.loading && !current.failed &&
      (current.section!=='ai-stats' || current.result.view.ai_stats_work.scopes[current.period].ready===true)`,tab,540000);
    const summary=await evaluate(`({source:current.result.source.status,
      observed:current.result.source.observed_at_ms,
      valid:current.section==='ai-stats'?AIStatsView.valid(current.result):TokenMixView.valid(current.result),
      policy:current.result.view.ai_stats_policy, scope:current.period,
      ready:current.result.view.ai_stats_work?.scopes?.[current.period]?.ready,
      periods:current.result.view.ai_stats?.map(row=>({period:row.period,nonzero:Number(row.metrics[1].value)>0})),
      models:current.result.view.model_token_mix?.length,publishers:current.result.view.publisher_token_mix?.length,
      nonzeroTokens:Number(current.result.view.token_mix?.known_total_tokens)>0,
      cards:output.querySelectorAll('.ai-stat-value').length,
      failed:!!current.failed,interrupted:!!current.interrupted,trace:__reportTrace})`);
    assert.equal(summary.valid,true);assert.ok(['acquired','partial'].includes(summary.source));
    if(section==='ai-stats') {
      assert.equal(summary.periods.length,5);assert.equal(summary.cards,12);assert.equal(summary.ready,true);
      const scopes=[];
      for(const period of ['today','7-days','30-days','month','all']) {
        await evaluate(`selectStats(current,'${period}')`);
        await until(`current.period==='${period}' && current.result?.view.ai_stats_work.scopes['${period}'].ready===true &&
          AIStatsView.valid(current.result) && document.querySelectorAll('.ai-stat-value').length===12`,tab,60000);
        scopes.push(period);
      }
      summary.readyPeriods=scopes;
      await until(`!current.loading`,tab,60000);
    } else {
      assert.ok(summary.models>0 && summary.publishers>0 && summary.nonzeroTokens);
      assert.equal(await evaluate(`document.querySelectorAll('.token-mix-table').length`),2);
    }
    for(const width of [360,800,1280,1920]) for(const theme of ['classic','light','dark']) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},tab);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},tab);
      await evaluate(`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}'; ReportView.setUnit('usd',output); ReportView.setUnit('credits',output)`);
      assert.equal(await evaluate(`document.getElementById('refresh').hidden && document.querySelector('.toolbar').hidden`),true);
      assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth`),true);
    }
    await evaluate(`window.__goodHistory=current.result;window.__historyDOM=output.firstChild;
      window.__historyApi=api;api=async(path,...args)=>path==='/api/data'?{id:null,result:null,refresh:'stopped',terminal:true,error:'report_cache_unavailable'}:__historyApi(path,...args);
      void acquire(current,true)`);
    await until(`current.failed && !current.loading`,tab);
    assert.equal(await evaluate(`current.result===__goodHistory && output.firstChild===__historyDOM && !current.withheld && document.getElementById('refresh').hidden`),true);
    await evaluate(`api=__historyApi; scheduleCachedReport()`);
    await until(`!current.failed && !current.loading`,tab,15000);
    await evaluate(`location.hash='#/settings'`);await until(`current.section==='settings'`,tab);
    await evaluate(`location.hash='#/${section}'`);await until(`current.section==='${section}' && !current.loading`,tab,30000);
    assert.equal(await evaluate(`current.result.source.observed_at_ms===__goodHistory.source.observed_at_ms`),true);
    observations.push({section,seconds:(Date.now()-started)/1000,...summary});
  }
  // Controlled transport failure with no previous result: never synthesize empty usage.
  for(const section of ['ai-stats','token-mix']) {
    await evaluate(`location.hash='#/${section}'`);await until(`current.section==='${section}' && !current.loading`,tab);
    await evaluate(`current.result=null;current.statsResults?.clear();api=async(path,...args)=>path==='/api/data'?{id:null,result:null,refresh:'stopped',terminal:true,error:'internal_error'}:__historyApi(path,...args);void acquire(current)`);
    await until(`current.failed && !current.loading`,tab);
    assert.equal(await evaluate(`document.querySelectorAll('.ai-stat-value,.token-mix-table').length`),0);
    if(section==='ai-stats') {
      assert.match(await evaluate(`notice.textContent`),/Historical report failed \(internal_error\)/);
      assert.equal(await evaluate(`[...output.querySelectorAll('.ai-stat')].length===12 && [...output.querySelectorAll('.ai-stat')].every(c=>c.textContent==='Loading…' && c.childNodes.length===1)`),true);
    } else assert.match(await evaluate(`output.textContent`),/Historical report failed \(internal_error\)/);
    assert.equal(await evaluate(`document.getElementById('refresh').hidden && document.querySelector('.toolbar').hidden`),true);
    await evaluate(`api=__historyApi; scheduleCachedReport()`);
    await until(`!current.loading && !current.failed && current.result && !!output.querySelector('.ai-stat,.token-mix-table')`,tab,15000);
  }
  checks.push('Real read-only V2 host: both valid reports, all five Stats scopes ready with twelve cards, retained warm navigation/provenance, both units, three themes and 360/800/1280/1920px; no report toolbar/actions');
  checks.push('Controlled browser transport faults over real retained results: last-good DOM preserved, cold failure has no zero cards, automatic host lookups recover without clicks/reload/service restart');
  return observations;
};
