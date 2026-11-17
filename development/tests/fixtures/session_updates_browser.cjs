// Native V2 wire → shared Watch owner → authenticated SSE → canonical detail DOM.
const assert = require('node:assert/strict');
module.exports = async ({evaluate,until,fixture,command,targetId}) => {
  const checks=[],measurements=[];
  await evaluate(`location.hash='#/sessions/ses_fixture_00000'`);
  await until(`current?.detail?.data?.total===1`);
  await evaluate(`window.detail=current.detail;window.oldRow=detail.body.firstChild;
    window.detailRequests=0;window.detailFlights=0;window.maxDetailFlights=0;window.sseMessages=0;
    const originalApi=detail.api;
    detail.api=async(...args)=>{detailRequests++;detailFlights++;maxDetailFlights=Math.max(maxDetailFlights,detailFlights);
      try{return await originalApi(...args);}finally{detailFlights--;}};
    window.paints=[];const update=detail.update.bind(detail);
    detail.update=value=>{update(value);paints.push({at:Date.now(),total:value.total});};
    window.liveCallback=detail.wake.bind(detail);detail.wake=hints=>{sseMessages++;
      if(!window.watchAt && liveValue?.view?.active_cards?.some(c=>c.session_id===detail.id &&
        c.rows.some(r=>r.prompt.in_progress)))window.watchAt=Date.now();
      liveCallback(hints);};`);
  const event=await fixture('detail-update');
  await until(`detail.data.total===2 && detail.body.lastChild.classList.contains('session-running')`,10000);
  await until(`Number.isFinite(window.watchAt)`);
  const metrics=await fixture('detail-metrics');
  const paint=await evaluate(`paints.find(p=>p.total===2).at`);
  assert.ok(paint-event.event_ms<4500,'no mandatory full five-second timer cycle');
  assert.equal(await evaluate(`detail.body.firstChild===oldRow && detail.status.hidden &&
    detail.loader.root.hidden && maxDetailFlights===1`),true);
  measurements.push({event_to_canonical_paint_ms:paint-event.event_ms,
    event_to_owner_revision_ms:metrics.revision_times.ses_fixture_00000-event.event_ms,
    watch_running_observation_ms:metrics.observations.ses_fixture_00000?.running_ms,
    event_to_watch_browser_observation_ms:await evaluate('watchAt')-event.event_ms,
    canonical_paint_ms:paint});
  await fixture('detail-telemetry');
  await until(`!detail.body.lastChild.classList.contains('session-running') &&
    detail.body.lastChild.cells[9].textContent==='?'`);
  assert.equal(await evaluate(`Number(detail.data.result.view.prompt_blocks[0].rows.at(-1).ccost)>0`),true);
  await evaluate(`detail.body.lastChild.cells[9].firstChild.focus()`);
  assert.match(await evaluate(`document.getElementById('context-help').textContent`),/known priced portion/);
  await evaluate(`document.activeElement.blur()`);
  await fixture('detail-telemetry-recover');
  await until(`/^\\d+\\/\\d+\\/\\d+\\/\\d+$/.test(detail.body.lastChild.cells[9].textContent)`);
  assert.equal(await evaluate(`detail.data.result.view.prompt_blocks[0].rows.at(-1).token_mix_percent.reduce((a,b)=>a+b)===100`),true);
  checks.push('native running arrival and terminal update; positive CCost/missing cache-write counter explains ?; explicit zero telemetry recovers numeric 100% mix automatically');
  // Real browser visibility in the disposable headless profile, never workstation focus.
  const {targetId:other}=await command('Target.createTarget',{url:'about:blank'});
  await command('Target.activateTarget',{targetId:other});
  await until(`document.hidden`);
  await fixture('detail-update-burst');
  await evaluate(`window.returnAt=Date.now()`);
  await command('Target.activateTarget',{targetId});
  await until(`!document.hidden`);
  await command('Target.closeTarget',{targetId:other});
  await until(`detail.data.total===12`,10000);
  measurements.push({return_to_ten_prompt_catchup_ms:await evaluate(`Date.now()-returnAt`)});
  // Cross 25-row transfer boundaries; a return during a held request must trail.
  await evaluate(`window.releaseRead=null;{const api=detail.api;window.holdRead=true;
    detail.api=async(...args)=>{if(holdRead && args[1]?.action==='begin'){
      holdRead=false;await new Promise(resolve=>releaseRead=resolve);}return api(...args);};
    detail.poll();}`);
  await until(`typeof releaseRead==='function'`);
  await fixture('detail-update-burst');
  await fixture('detail-update-burst');
  await evaluate(`detail.catchUp();detail.catchUp();releaseRead()`);
  await until(`detail.data.total===32 && !detail.busy`);
  assert.equal(await evaluate(`new Set([...detail.body.rows].map(r=>r.dataset.id)).size===32 &&
    detail.body.firstChild===oldRow && detail.footer.textContent.includes('Complete session') &&
    maxDetailFlights===1 && detail.status.hidden && detail.loader.root.hidden`),true);
  const before=await fixture('detail-metrics');
  await fixture('arrival-new-9');
  await fixture('arrival-running-9');
  await until(`liveValue?.detail_hints || sseMessages>3`);
  const after=await fixture('detail-metrics');
  assert.ok(after.entries.ses_fixture_00000.generation-before.entries.ses_fixture_00000.generation<=1,
    'unrelated source activity does not cause a selected-root capture storm');
  measurements.push({http_calls:await evaluate('detailRequests'),sse_messages:await evaluate('sseMessages'),
    maximum_browser_flights:await evaluate('maxDetailFlights'),source_requests:after.source.requests});
  checks.push('ten-prompt visibility catchup; inflight return coalescing; 32 keyed rows/chunks and footer; unchanged row DOM; unrelated source events bounded; one browser flight');
  return {checks,measurements,limitations:['Headless disposable-profile visibility is not physical OS background-window proof. No personal incident record was supplied.']};
};
