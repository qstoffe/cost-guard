// Raw synthetic persisted source -> analysis/capture -> SSE -> real Document PiP.
const assert=require('node:assert/strict');
module.exports=async function({evaluate,until,fixture,command,pip,open,close,checks}) {
  const show=async phase=>{const {published}=await fixture('handoff-'+phase);
    await until(`liveValue.view.now_ms===${published} && miniWatch.publication.view.now_ms===${published}`);};
  const read=()=>evaluate(`(()=>{const r=miniWatch.view.promptRows.get('root');return {text:r?.children[4].textContent,help:r?.contextHelp,
    focal:liveValue.view.active_cards[0]?.focal_id,raw:liveValue.view.active_cards[0]?.rows[0]?.live_context.watch_next_context_tokens};})()`);
  await show('prior');assert.equal((await read()).text,'172k');
  const before=await evaluate('structuredClone(liveValue)');
  for(let i=0;i<3;i++) {
    await show('pending');const value=await read();assert.equal(value.text,'172k');assert.equal(value.raw,null);
    assert.match(value.help,/previous same-session estimate; current prompt pending refresh/);
    assert.match(value.help,/Δ Ctx: N\/A/);
    await evaluate('miniWatch.render()');assert.equal((await read()).text,'172k');
  }
  await evaluate(`miniWatch.view.promptRows.get('root').children[4].focus()`);
  await until(`miniWatch.window.document.getElementById('context-help')?.textContent.includes('previous same-session estimate')`);
  const ax=await command('Accessibility.getFullAXTree',{},pip);
  assert.ok(ax.nodes.some(n=>n.name?.value?.includes('previous same-session estimate')),'accessible retained provenance');
  await show('fresh');assert.equal((await read()).text,'175k');
  assert.doesNotMatch((await read()).help,/previous same-session/);
  await evaluate(`miniWatch.update(${JSON.stringify(before)})`);assert.equal((await read()).text,'175k','late snapshot rejected');
  await show('tools');assert.equal((await read()).text,'175k');
  await show('partial-usage');assert.equal((await read()).text,'172k','canonical provisional estimate remains authoritative');
  assert.doesNotMatch((await read()).help,/previous same-session/);
  for(const phase of ['reset','model-selection','model','move','inactive','unverified']) {
    await show('prior');await show('pending');assert.equal((await read()).text,'172k');
    await show(phase);assert.equal((await read()).text,'N/A',phase+' clears incompatible context');
  }
  await show('prior');await show('pending');await close();await open();
  assert.equal((await read()).text,'N/A','new Mini has never displayed an eligible predecessor');
  checks.push('Real headless Document PiP: source-validated 172k -> 172k -> 175k across SSE/timer draws, focused/AX provenance, prompt-local delta, late HTTP rejection, tool continuation, source-supported partial usage, reset/model/move/inactive/unverified invalidation, fresh Mini');
};
