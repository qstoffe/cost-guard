// Nested, source-owned failure controls in the same hidden browser/fixture.
const assert = require('node:assert/strict');
module.exports = async (evaluate, command, session) => {
  const key = async (key, code, windowsVirtualKeyCode, text) => {
    await command('Input.dispatchKeyEvent', {type:'keyDown',key,code,windowsVirtualKeyCode,...(text?{text}:{})}, session);
    await command('Input.dispatchKeyEvent', {type:'keyUp',key,code,windowsVirtualKeyCode}, session);
  };
  await evaluate(`(() => {
    const card=[...state.watch.cards.values()].find(c=>c.value.session_id==='root');
    card.tools.node.open=true; card.skills.node.open=true;
    const group=card.tools.rows.get(JSON.stringify(['grep','failed']));
    group.summary.focus({preventScroll:true}); })()`);
  await key('Enter','Enter',13,'\r');
  await evaluate(`(() => {
    const card=[...state.watch.cards.values()].find(c=>c.value.session_id==='root');
    const group=card.tools.rows.get(JSON.stringify(['grep','failed']));
    [...group.jobs.values()][1].summary.focus({preventScroll:true}); })()`);
  await key(' ','Space',32,' ');
  const facts = await evaluate(`(() => {
    const card=[...state.watch.cards.values()].find(c=>c.value.session_id==='root');
    const group=card.tools.rows.get(JSON.stringify(['grep','failed'])), jobs=[...group.jobs.values()];
    const call=jobs[1], before=performance.getEntriesByType('resource').length;
    const original=call.input.firstChild, selection=getSelection(), range=document.createRange();
    range.selectNodeContents(original); selection.removeAllRanges(); selection.addRange(range);
    const focused=document.activeElement, selected=selection.toString(), y=scrollY;
    const tool=INPUT.view.active_cards[0].rows[0].tool, saved=structuredClone(tool);
    for(let i=0;i<8;i++) {
      tool.counts[0][1]=4+i;
      tool.failed_invocations[1].reason='Permission denied'; tool.failed_invocations[1].revision='r'+i;
      ReportView.renderLive(document.getElementById('result'), INPUT, state);
    }
    const stable=group.node.open && call.node.open && !jobs[0].node.open && original===call.input.firstChild &&
      selection.toString()===selected && document.activeElement===focused && scrollY===y &&
      /Permission denied/.test(call.note.textContent);
    const x=n=>n.getBoundingClientRect().x;
    const indentation=x(group.summary)>x(card.tools.summary) && x(call.summary)>x(group.summary) &&
      x(call.input)>x(call.summary) && x(card.skills.list)>x(card.skills.summary) &&
      x(card.runningDetail.list)>x(card.runningDetail.summary) &&
      x(card.backgroundDetail.list)>x(card.backgroundDetail.summary);
    const sourceOwned=jobs[0].input.textContent.includes('src/example-1.py') &&
      call.input.textContent.includes('src/example-2.py') &&
      call.input.textContent.includes('<img src=x>') && call.list.querySelectorAll('img,script').length===0;
    const noNetwork=performance.getEntriesByType('resource').length===before;
    selection.removeAllRanges(); document.activeElement?.blur();
    tool.failed_invocations=tool.failed_invocations.slice(0,1); tool.outcomes[0].count=1;
    ReportView.renderLive(document.getElementById('result'), INPUT, state);
    const removed=group.jobs.size===1 && call.input.textContent==='' && !call.node.open;
    Object.assign(tool,saved); ReportView.renderLive(document.getElementById('result'), INPUT, state);
    const current=group.jobs.values().next().value; current.node.open=true;
    const prompt=INPUT.view.active_cards[0].rows[0].prompt; prompt.in_progress=false;
    ReportView.renderLive(document.getElementById('result'), INPUT, state);
    const terminal=group.node.open && current.node.open;
    prompt.in_progress=true; state.connection='Disconnected';
    ReportView.renderLive(document.getElementById('result'), INPUT, state);
    const cleared=current.input.textContent==='' && group.jobs.size===0;
    state.connection='Live connected.'; ReportView.renderLive(document.getElementById('result'), INPUT, state);
    card.tools.node.open=false;
    return {stable,indentation,sourceOwned,noNetwork,removed,terminal,cleared,
      overflow:document.documentElement.scrollWidth>innerWidth}; })()`);
  assert.deepEqual(facts, {stable:true,indentation:true,sourceOwned:true,noNetwork:true,
    removed:true,terminal:true,cleared:true,overflow:false});
  const position = await evaluate(`(() => {
    const card=[...state.watch.cards.values()].find(c=>c.value.session_id==='root');
    const group=card.tools.rows.get(JSON.stringify(['grep','failed']));
    card.tools.node.open=true; group.node.open=true;
    const call=[...group.jobs.values()][1]; call.node.open=false;
    call.summary.scrollIntoView(); const r=call.summary.getBoundingClientRect();
    return {x:r.x+r.width/2,y:r.y+r.height/2}; })()`);
  await command('Input.dispatchMouseEvent', {type:'mousePressed',...position,button:'left',clickCount:1}, session);
  await command('Input.dispatchMouseEvent', {type:'mouseReleased',...position,button:'left',clickCount:1}, session);
  const opened = `[...state.watch.cards.values()].find(c=>c.value.session_id==='root').tools.rows.get(JSON.stringify(['grep','failed'])).jobs.values()`;
  assert.equal(await evaluate(`[...${opened}][1].node.open`), true);
  await command('Emulation.setTouchEmulationEnabled', {enabled:true}, session);
  await command('Input.dispatchTouchEvent', {type:'touchStart',touchPoints:[position]}, session);
  await command('Input.dispatchTouchEvent', {type:'touchEnd',touchPoints:[]}, session);
  assert.equal(await evaluate(`[...${opened}][1].node.open`), false);
  await command('Emulation.setTouchEmulationEnabled', {enabled:false}, session);
  assert.equal(await evaluate(`(() => {
    document.body.style.zoom='1.25';
    const overflow=document.documentElement.scrollWidth>innerWidth;
    document.body.style.zoom=''; return overflow; })()`), false);
  await evaluate(`(() => {
    const card=[...state.watch.cards.values()].find(c=>c.value.session_id==='root');
    card.tools.node.open=false; document.activeElement?.blur(); })()`);
  return facts;
};
