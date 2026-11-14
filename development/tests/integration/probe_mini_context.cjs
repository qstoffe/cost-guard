// Synthetic persisted source -> canonical capture -> Live/SSE -> actual Document PiP.
const assert=require('node:assert/strict');
module.exports=async function({evaluate,until,fixture,command,pip,open,close,checks}) {
  const show=async phase=>{const {published}=await fixture('handoff-'+phase);
    await until(`liveValue.view.now_ms===${published} && miniWatch.publication.view.now_ms===${published}`);};
  const read=()=>evaluate(`(()=>{const r=miniWatch.view.promptRows.get('root');return {text:r?.children[4].textContent,help:r?.contextHelp,
    running:r?.classList.contains('mini-running'),raw:liveValue.view.active_cards[0]?.rows[0]?.live_context.watch_next_context_tokens,
    handoff:liveValue.view.active_cards[0]?.context_handoff,
    full:document.querySelector('.watch-active [data-session="root"] .watch-session-summary')?.textContent,
    overflow:miniWatch.window.document.documentElement.scrollWidth>miniWatch.window.innerWidth+1};})()`);
  await show('prior');assert.equal((await read()).text,'230k');
  const before=await evaluate('structuredClone(liveValue)');
  await evaluate(`window.contextRow=miniWatch.view.promptRows.get('root')`);
  for(const [phase,gap] of [['early',500],['pending',5100]]) {
    await show(phase);const value=await read();assert.equal(value.text,'230k');assert.equal(value.raw,null);
    if(phase==='early')assert.equal(value.handoff,null,'first partial capture has no perfect handoff');
    assert.equal(value.running,true);assert.equal(value.overflow,false);assert.match(value.full,/Context: 230k/);
    assert.equal(value.help,'','retained pending context has no value tooltip');
    await evaluate(`new Promise(resolve=>setTimeout(resolve,${gap}))`);
    assert.equal((await read()).text,'230k');
    assert.equal(await evaluate(`contextRow===miniWatch.view.promptRows.get('root')`),true);
  }
  await evaluate(`miniWatch.view.promptRows.get('root').children[4].focus()`);
  assert.equal(await evaluate(`miniWatch.view.promptRows.get('root').children[4].tabIndex`),-1);
  assert.equal(await evaluate(`!!miniWatch.window.document.getElementById('context-help')?.matches(':popover-open')`),false);
  const ax=await command('Accessibility.getFullAXTree',{},pip);
  assert.ok(ax.nodes.some(n=>n.name?.value?.includes('230k')));
  await command('Page.bringToFront',{},pip);
  await evaluate(`miniWatch.view.promptRows.get('root').children[4].blur()`);
  for(const type of ['keyDown','keyUp'])await command('Input.dispatchKeyEvent',{type,key:'Escape',code:'Escape',windowsVirtualKeyCode:27},pip);
  const point=await evaluate(`(()=>{const r=miniWatch.view.promptRows.get('root').children[4].getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},pip);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},pip);
  await evaluate('new Promise(resolve=>setTimeout(resolve,700))');
  assert.equal(await evaluate(`!!miniWatch.window.document.getElementById('context-help')?.matches(':popover-open')`),false);
  for(const type of ['keyDown','keyUp'])await command('Input.dispatchKeyEvent',{type,key:'Escape',code:'Escape',windowsVirtualKeyCode:27},pip);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},pip);
  for(const type of ['touchStart','touchEnd'])await command('Input.dispatchTouchEvent',{type,
    touchPoints:type==='touchStart'?[{...point,id:1,radiusX:1,radiusY:1,force:1}]:[]},pip);
  assert.equal(await evaluate(`!!miniWatch.window.document.getElementById('context-help')?.matches(':popover-open')`),false);
  // Isolate the Total-heading portfolio's previously failing mixed-input order
  // on the changed Ctx value, without retries, synthetic movement or redraws.
  for(const type of ['keyDown','keyUp'])await command('Input.dispatchKeyEvent',{type,key:'Tab',code:'Tab',windowsVirtualKeyCode:9},pip);
  await evaluate(`miniWatch.view.promptRows.get('root').children[4].focus()`);
  for(const type of ['keyDown','keyUp'])await command('Input.dispatchKeyEvent',{type,key:'Escape',code:'Escape',windowsVirtualKeyCode:27},pip);
  await evaluate(`miniWatch.view.promptRows.get('root').children[4].blur()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},pip);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},pip);
  await evaluate('new Promise(resolve=>setTimeout(resolve,700))');
  assert.equal(await evaluate(`!!miniWatch.window.document.getElementById('context-help')?.matches(':popover-open')`),false);
  assert.equal((await read()).help,'');assert.equal((await read()).text,'230k');
  await evaluate(`miniWatch.update({...liveValue,view:{...liveValue.view,history_scope:'independent-history-restart'}})`);
  assert.equal((await read()).text,'230k','history bookkeeping is not context invalidation');
  await show('fresh');assert.equal((await read()).text,'235k');assert.match((await read()).full,/Context: 235k/);
  assert.doesNotMatch((await read()).help,/previous same-session/);
  await evaluate(`miniWatch.update(${JSON.stringify(before)})`);assert.equal((await read()).text,'235k');
  await show('tools');assert.equal((await read()).text,'235k');
  for(const phase of ['reset','model-selection','model','move','inactive']) {
    await show('prior');await show('early');assert.equal((await read()).text,'230k');
    await show(phase);assert.equal((await read()).text,'N/A',phase+' is positive incompatibility');
  }
  await show('prior');await show('unverified');assert.equal((await read()).text,'230k','execution uncertainty is not a context reset');
  await show('prior');await show('early');await close();await open();
  assert.equal((await read()).text,'230k','fresh Mini uses source-owned session summary');
  await show('equal');assert.equal((await read()).text,'230k');assert.equal((await read()).raw,230000);
  assert.doesNotMatch((await read()).help,/previous same-session/);
  checks.push('Source-shaped 230k -> 230k -> 230k -> 235k in native headless Document PiP and Full Watch; absent first handoff/null raw current Ctx, yellow new prompt, 0.5s/5s gaps, stable row and numeric AX, no pending keyboard/hover/touch tooltip, history-owner change, stale publication rejection, real invalidations, unknown execution, close/reopen and exact same-number current replacement');
};
