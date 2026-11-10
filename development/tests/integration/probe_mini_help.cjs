// Synthetic value-help acceptance in real headless Document PiP; no desktop claims.
const assert = require('node:assert/strict');
module.exports = async function help({evaluate,until,fixture,command,pip,checks}) {
  const input = (method,params) => command(method,params,pip);
  const key = async key => {
    for (const type of ['keyDown','keyUp']) await input('Input.dispatchKeyEvent',{
      type,key,code:key,windowsVirtualKeyCode:key==='Tab'?9:27});
  };
  await evaluate(`window.helpPublication=structuredClone(liveValue);
    {const v=helpPublication.view,c=v.active_cards[0],r=c.rows[0];
    v.active_cards=[c];v.history_cards=[];v.history_state='observed';v.history_epoch=1;
    c.session_id='help-synthetic';c.title='Example Session';c.focal_id=r.prompt.event_id;
    Object.assign(r.prompt,{prompt_number:21,preview:'Implement pagination for this table'});
    r.live_context.display={watch_next_context_tokens:'128k',watch_delta_context_tokens:'+4k'};
    c.session_summary.context={display:{watch_next_context_tokens:'900k'},warning:{
      text:'[Approaching price threshold >200k]',display:{warning_cost:'(2.4x more expensive)'}}};
     window.helpUpdate=miniWatch.update.bind(miniWatch);miniWatch.update=()=>helpUpdate(helpPublication);
     miniWatch.update(helpPublication);}
    window.helpRow=miniWatch.view.promptRows.get('help-synthetic');
    window.helpTitle=helpRow.querySelector('.mini-session');window.helpCtx=helpRow.cells[4];`);
  const panel = `miniWatch.view.doc.getElementById('context-help')`;
  const read = () => evaluate(`({session:helpRow.sessionHelp,context:helpRow.contextHelp,
     visible:helpRow.cells[4].textContent,columns:helpRow.cells.length,
    buttons:helpRow.querySelectorAll('button').length,native:!!helpRow.querySelector('[title]'),
    overflow:miniWatch.view.doc.documentElement.scrollWidth>miniWatch.window.innerWidth+1,
    table:[miniWatch.view.prompts.clientWidth,miniWatch.view.prompts.clientHeight]})`);
  const before = await read();
  assert.equal(before.session,'Example Session\nPrompt #21: Implement pagination for…');
  assert.match(before.context,/^Next Ctx: 128k .*\n\nΔ Ctx: \+4k[\s\S]*Approaching price threshold >200k\n2.4x more expensive$/);
  assert.equal(before.visible,'128k');assert.equal(before.columns,5);assert.equal(before.buttons,0);assert.equal(before.native,false);
  await command('Page.bringToFront',{},pip);
  await key('Tab');await evaluate('helpRow.cells[0].firstChild.focus()');await key('Tab');
  await until(`${panel}?.matches(':popover-open') && miniWatch.view.doc.activeElement===helpTitle`);
  assert.equal(await evaluate(`${panel}.textContent`),before.session);
  await evaluate(`{const c=helpPublication.view.active_cards[0],r=c.rows[0];
    Object.assign(r.prompt,{prompt_number:22,preview:'a'.repeat(24)+'👨‍👩‍👧‍👦 tail'});
    r.live_context.display={watch_next_context_tokens:'256k',watch_delta_context_tokens:'-4k'};
    c.session_summary.context.warning.text='[Price threshold >200k exceeded]';miniWatch.update(helpPublication);}`);
  assert.equal(await evaluate(`${panel}.textContent`),'Example Session\nPrompt #22: '+'a'.repeat(24)+'👨‍👩‍👧‍👦…');
  assert.equal(await evaluate('miniWatch.view.doc.activeElement===helpTitle'),true);
  await key('Escape');await evaluate('helpTitle.blur()');
  await input('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0});
  const point = await evaluate(`(()=>{const r=helpCtx.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
  await input('Input.dispatchMouseEvent',{type:'mouseMoved',...point});
  assert.equal(await evaluate(`${panel}.matches(':popover-open')`),false,'hover keeps its delay');
  await until(`${panel}.matches(':popover-open')`);
  assert.match(await evaluate(`${panel}.textContent`),/^Next Ctx: 256k[\s\S]*Δ Ctx: -4k[\s\S]*Price threshold >200k exceeded\n2.4x more expensive$/);
  await evaluate(`{const v=helpPublication.view,c=v.active_cards[0];c.focal_id='';
    c.rows[0].prompt.in_progress=false;c.rows[0].prompt.completed_at_ms=1000;
    v.active_cards=[];v.history_cards=[c];miniWatch.update(helpPublication);}`);
  assert.equal(await evaluate(`miniWatch.view.promptRows.get('help-synthetic')===helpRow`),true);
  assert.match(await evaluate(`${panel}.textContent`),/^Next Ctx: 900k[\s\S]*Δ Ctx: -4k \(historical prompt change; session estimate may be later\)/);
  await evaluate(`helpPublication.view.history_cards[0].rows[0].live_context=null;miniWatch.update(helpPublication)`);
  assert.match(await evaluate(`${panel}.textContent`),/Next Ctx: 900k[\s\S]*Δ Ctx: N\/A/);
  await key('Escape');await input('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0});
  const titlePoint = await evaluate(`(()=>{const r=helpTitle.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
  for(const type of ['touchStart','touchEnd'])await input('Input.dispatchTouchEvent',{
    type,touchPoints:type==='touchStart'?[{...titlePoint,id:1,radiusX:1,radiusY:1,force:1}]:[]});
  await until(`${panel}.matches(':popover-open')`);
  await evaluate(`helpPublication.view.history_cards[0].rows[0].prompt.preview='<img src=x onerror=alert(1)>';miniWatch.update(helpPublication)`);
  assert.equal(await evaluate(`${panel}.textContent`),'Example Session\nPrompt #22: <img src=x onerror=alert(…');
  assert.equal(await evaluate(`${panel}.children.length`),0,'preview is literal text, not HTML');
  const after = await read();assert.deepEqual(after.table,before.table);assert.equal(after.overflow,false);
  await key('Escape');assert.equal(await evaluate(`${panel}.matches(':popover-open')`),false);
  await evaluate('miniWatch.update=helpUpdate;delete window.helpUpdate;miniWatch.update(liveValue)');
  checks.push('Mini value help: exact Next/representative delta, historical source handoff/N/A, approaching/exceeded cost guidance, short Unicode/text-only preview, real Tab/hover/touch/Escape and open-help refresh; five-column geometry');
  await fixture('context-running');
  await until(`miniWatch.view.promptRows.has('root') && liveValue.view.active_cards[0]?.rows[0]?.live_context.watch_next_context_tokens===112000`);
  await evaluate(`window.sourceRow=miniWatch.view.promptRows.get('root');sourceRow.cells[4].focus()`);
  await until(`${panel}.matches(':popover-open')`);
  assert.match(await evaluate(`${panel}.textContent`),/^Next Ctx: 112k[^\n]*\n\nΔ Ctx: \+12k/);
  assert.equal(await evaluate(`document.querySelector('.watch-card .watch-prompt-table')?.textContent.includes('+12k')`),true,'Full Watch uses same canonical delta');
  for(const [phase,next,delta] of [['later','117k','+17k'],['boundary','N/A','N/A'],
      ['running','112k','+12k'],['history','300k','+12k'],['zero','300k','0'],['waiting','N/A','N/A']]) {
    await fixture('context-'+phase);
    await until(`miniWatch.view.promptRows.get('root')?.cells[4].textContent===${JSON.stringify(next)} &&
      miniWatch.view.promptRows.get('root')?.contextHelp.includes(${JSON.stringify('Δ Ctx: '+delta+' (')})`);
    assert.equal(await evaluate(`miniWatch.view.promptRows.get('root')===sourceRow && miniWatch.view.doc.activeElement===sourceRow.cells[4]`),true);
    assert.match(await evaluate(`${panel}.textContent`),new RegExp('Δ Ctx: '+delta.replace('+','\\+')+' \\('));
    assert.equal(await evaluate('sourceRow.cells.length'),5);
    if(phase==='history')assert.match(await evaluate(`${panel}.textContent`),/historical prompt change; session estimate may be later/);
    if(phase==='waiting')assert.match(await evaluate(`${panel}.textContent`),/waiting for comparable request context/);
  }
  await key('Escape');
  checks.push('Normalized V2 → analysis → report → Live SSE → Full/Mini DOM: 100k incoming, running 112k/+12k then 117k/+17k, move invalidation/recovery, inactive historical 300k/+12k, exact zero, missing first request; stable row/focus/open tooltip and paragraph separation');
};
