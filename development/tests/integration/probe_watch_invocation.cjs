// Called inside the owned hidden Chromium outcome probe. No real source/input.
const assert = require('node:assert/strict');
module.exports = async (evaluate, command, session) => {
  const initial = await evaluate(`(() => {
    const card=[...state.watch.cards.values()].find(c=>c.value.session_id==='root');
    const target=card.runningDetail;
    target.summary.focus({preventScroll:true});
    return {collapsed:!target.node.open, text:target.input.textContent,
      background:card.backgroundDetail.input.textContent}; })()`);
  assert.equal(initial.collapsed, true);
  assert.match(initial.text, /git grep "hello world"\nWrite-Output/);
  assert.match(initial.background, /git grep/);
  await command('Input.dispatchKeyEvent', {type:'keyDown', key:'Enter', code:'Enter', windowsVirtualKeyCode:13, text:'\r'}, session);
  await command('Input.dispatchKeyEvent', {type:'keyUp', key:'Enter', code:'Enter', windowsVirtualKeyCode:13}, session);
  const retained = await evaluate(`(() => {
    const card=[...state.watch.cards.values()].find(c=>c.value.session_id==='root'), target=card.runningDetail;
    const original=target.input.firstChild, range=document.createRange(); range.selectNodeContents(original);
    const selection=getSelection(); selection.removeAllRanges(); selection.addRange(range);
    const selected=selection.toString(), focused=document.activeElement;
    target.node.scrollIntoView(); const y=scrollY;
    for(let i=0;i<8;i++) {
      INPUT.view.active_cards[0].rows[0].tool.display.running_ms=(13+i)+'s';
      ReportView.renderLive(document.getElementById('result'), INPUT, state);
    }
    const facts={open:target.node.open, selection:selection.toString()===selected,
      focus:document.activeElement===focused, textNode:target.input.firstChild===original,
      scroll:scrollY===y, injected:target.list.querySelectorAll('script,img').length,
      overflow:document.documentElement.scrollWidth>innerWidth};
    selection.removeAllRanges(); document.activeElement?.blur(); return facts; })()`);
  assert.deepEqual(retained, {open:true, selection:true, focus:true, textNode:true, scroll:true, injected:0, overflow:false});
  const reset = await evaluate(`(() => {
    const card=[...state.watch.cards.values()].find(c=>c.value.session_id==='root'), target=card.runningDetail;
    const tool=INPUT.view.active_cards[0].rows[0].tool, saved=structuredClone(tool);
    tool.running_invocation={...tool.running_invocation,identity:'different-call',text:'command:\\ngit diff'};
    target.summary.focus(); ReportView.renderLive(document.getElementById('result'), INPUT, state);
    const changed=!target.node.open && target.input.textContent==='command:\\ngit diff';
    target.node.open=true; tool.running_invocation.revision='corrected'; tool.running_invocation.text='command:\\ngit log';
    ReportView.renderLive(document.getElementById('result'), INPUT, state);
    const corrected=!target.node.open && target.input.textContent==='command:\\ngit log';
    tool.background_kinds=['shell','shell']; ReportView.renderLive(document.getElementById('result'), INPUT, state);
    const aggregate=card.backgroundDetail.input.textContent==='' && /unavailable/.test(card.backgroundDetail.note.textContent);
    INPUT.view.active_cards[0].state='unavailable'; ReportView.renderLive(document.getElementById('result'), INPUT, state);
    const unavailable=target.input.textContent==='' && !target.node.open;
    INPUT.view.active_cards[0].state='observed'; Object.assign(tool,saved);
    document.activeElement?.blur(); ReportView.renderLive(document.getElementById('result'), INPUT, state);
    return {changed,corrected,aggregate,unavailable}; })()`);
  assert.deepEqual(reset, {changed:true,corrected:true,aggregate:true,unavailable:true});
  const position = await evaluate(`(() => {
    const target=[...state.watch.cards.values()].find(c=>c.value.session_id==='root').runningDetail;
    target.summary.scrollIntoView(); const r=target.summary.getBoundingClientRect();
    return {x:r.x+r.width/2,y:r.y+r.height/2}; })()`);
  await command('Input.dispatchMouseEvent', {type:'mousePressed',...position,button:'left',clickCount:1}, session);
  await command('Input.dispatchMouseEvent', {type:'mouseReleased',...position,button:'left',clickCount:1}, session);
  assert.equal(await evaluate(`[...state.watch.cards.values()].find(c=>c.value.session_id==='root').running.open`), true);
  await command('Emulation.setTouchEmulationEnabled', {enabled:true}, session);
  await command('Input.dispatchTouchEvent', {type:'touchStart',touchPoints:[position]}, session);
  await command('Input.dispatchTouchEvent', {type:'touchEnd',touchPoints:[]}, session);
  assert.equal(await evaluate(`[...state.watch.cards.values()].find(c=>c.value.session_id==='root').running.open`), false);
  await command('Emulation.setTouchEmulationEnabled', {enabled:false}, session);
  assert.equal(await evaluate(`(() => {
    const card=[...state.watch.cards.values()].find(c=>c.value.session_id==='root');
    const detail=INPUT.view.active_cards[0].rows[0].tool.running_invocation, saved=detail.text;
    detail.text='command: '+ 'long-unbroken-argument'.repeat(150); detail.revision='long';
    ReportView.renderLive(document.getElementById('result'), INPUT, state);
    card.running.open=true;
    const overflow=document.documentElement.scrollWidth>innerWidth;
    detail.text=saved; detail.revision='restored';
    ReportView.renderLive(document.getElementById('result'), INPUT, state);
    card.running.open=true; card.background.open=true;
    return overflow; })()`), false);
  return {durationStable:true, identityReset:true, sourceCleared:true, mouseKeyboardTouch:true};
};
