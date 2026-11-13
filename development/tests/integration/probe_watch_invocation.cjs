// Called inside the owned hidden Chromium outcome probe. No real source/input.
const assert = require('node:assert/strict');
module.exports = async (evaluate, command, session) => {
  const initial = await evaluate(`(() => {
    const card=[...state.watch.cards.values()].find(c=>c.value.session_id==='root');
    const target=card.runningDetail;
    target.summary.focus({preventScroll:true});
    return {collapsed:!target.node.open, text:target.input.textContent,
      noteHidden:target.note.hidden, note:target.note.textContent,
      commandFirst:[...target.jobs.values()][0].list.firstElementChild===target.input,
      background:card.backgroundDetail.input.textContent}; })()`);
  assert.equal(initial.collapsed, true);
  assert.ok(initial.text.startsWith('command:\n"C:\\Python313\\python.exe" "D:\\dev\\scripts\\tokenizer.py" --mode=fast --limit=25\n'));
  assert.match(initial.text, /timeout:\n120000 ms \(2 min\)/);
  assert.match(initial.background, /tokenizer\.py/);
  assert.equal(initial.noteHidden, true); assert.equal(initial.note, ''); assert.equal(initial.commandFirst, true);
  await command('Input.dispatchKeyEvent', {type:'keyDown', key:'Enter', code:'Enter', windowsVirtualKeyCode:13, text:'\r'}, session);
  await command('Input.dispatchKeyEvent', {type:'keyUp', key:'Enter', code:'Enter', windowsVirtualKeyCode:13}, session);
  assert.equal(await evaluate(`[...state.watch.cards.values()].find(c=>c.value.session_id==='root').running.open`), true);
  await command('Input.dispatchKeyEvent', {type:'keyDown', key:' ', code:'Space', windowsVirtualKeyCode:32, text:' '}, session);
  await command('Input.dispatchKeyEvent', {type:'keyUp', key:' ', code:'Space', windowsVirtualKeyCode:32}, session);
  assert.equal(await evaluate(`[...state.watch.cards.values()].find(c=>c.value.session_id==='root').running.open`), false);
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
    const corrected=target.node.open && target.input.textContent==='command:\\ngit log';
    tool.background_kinds=['shell','shell']; ReportView.renderLive(document.getElementById('result'), INPUT, state);
    const aggregate=card.backgroundDetail.input.textContent==='' && /Original call links missing/.test(card.backgroundDetail.note.textContent);
    INPUT.view.active_cards[0].state='unavailable'; ReportView.renderLive(document.getElementById('result'), INPUT, state);
    const unavailable=target.input.textContent==='' && !target.node.open;
    INPUT.view.active_cards[0].state='observed'; Object.assign(tool,saved);
    document.activeElement?.blur(); ReportView.renderLive(document.getElementById('result'), INPUT, state);
    return {changed,corrected,aggregate,unavailable}; })()`);
  assert.deepEqual(reset, {changed:true,corrected:true,aggregate:true,unavailable:true});
  const multi = await evaluate(`(() => {
    const card=[...state.watch.cards.values()].find(c=>c.value.session_id==='root'), target=card.backgroundDetail;
    const tool=INPUT.view.active_cards[0].rows[0].tool, saved=structuredClone(tool);
    tool.background_kinds=['shell','shell'];
    tool.background_invocations=[1,2].map(i=>({identity:'shell-job-'+i,revision:'r1',kind:'shell',
      text:'command:\\npython task'+i+'.py --check\\n\\ncwd:\\nC:/fixture',qualification:'',mode:'background'}));
    ReportView.renderLive(document.getElementById('result'), INPUT, state); target.node.open=true;
    const jobs=[...target.jobs.values()], original=jobs[1].input.firstChild;
    jobs[1].summary.focus({preventScroll:true});
    const range=document.createRange(); range.selectNodeContents(original);
    const selection=getSelection(); selection.removeAllRanges(); selection.addRange(range);
    const selected=selection.toString(), focus=document.activeElement, y=scrollY;
    for(let i=0;i<8;i++) {
      tool.display.background_ms=(30+i)+'s';
      ReportView.renderLive(document.getElementById('result'), INPUT, state);
    }
    const stable=target.node.open && jobs.every(j=>j.node.open) && jobs[1].input.firstChild===original &&
      selection.toString()===selected && document.activeElement===focus && scrollY===y;
    tool.background_invocations.reverse();
    ReportView.renderLive(document.getElementById('result'), INPUT, state);
    const reordered={node:jobs[1].input.firstChild===original, selection:selection.toString()===selected,
      focus:document.activeElement===focus, identity:target.jobs.get('shell-job-2')===jobs[1]};
    tool.background_invocations.reverse();
    tool.background_invocations[0].revision='corrected'; tool.background_invocations[0].text='command:\\npython corrected.py';
    ReportView.renderLive(document.getElementById('result'), INPUT, state);
    const isolated=jobs[0].node.open && jobs[1].node.open && jobs[1].input.firstChild===original;
    const commands=jobs.map(j=>j.input.textContent.includes('python'));
    selection.removeAllRanges(); document.activeElement?.blur();
    Object.assign(tool,saved,{background_invocations:[]});
    ReportView.renderLive(document.getElementById('result'), INPUT, state);
    return {stable,reordered,isolated,commands,overflow:document.documentElement.scrollWidth>innerWidth}; })()`);
  assert.deepEqual(multi, {stable:true,reordered:{node:true,selection:true,focus:true,identity:true},
    isolated:true,commands:[true,true],overflow:false});
  const causal = await evaluate(`(() => {
    const card=[...state.watch.cards.values()].find(c=>c.value.session_id==='root');
    const saved=structuredClone(INPUT.view.active_cards[0].rows[0].tool), results=[];
    const render=()=>ReportView.renderLive(document.getElementById('result'), INPUT, state);
    for(const [name, [before,after]] of Object.entries(REVISIONS)) {
      INPUT.view.active_cards[0].rows[0].tool=structuredClone(before); render();
      const mode=name.startsWith('background')?'background':'running';
      const target=mode==='background'?card.backgroundDetail:card.runningDetail;
      target.node.open=true;
      const job=[...target.jobs.values()][0]; job.node.open=true;
      (name.endsWith('-1')?target.summary:job.summary).focus({preventScroll:true});
      const original=job.input.firstChild, selection=getSelection(), range=document.createRange();
      range.selectNodeContents(original); selection.removeAllRanges(); selection.addRange(range);
      const focus=document.activeElement, y=scrollY;
      INPUT.view.active_cards[0].rows[0].tool=structuredClone(after); render();
      const revised=target.node.open && job.node.open && target.jobs.get(after[mode+'_invocations'][0].identity)===job &&
        job.input.firstChild===original && selection.anchorNode===original && document.activeElement===focus &&
        scrollY===y && job.input.textContent.includes('--limit=2000') &&
        after[mode+'_ms']>before[mode+'_ms'] &&
        after[mode+'_invocations'][0].started_at_ms===before[mode+'_invocations'][0].started_at_ms;
      selection.removeAllRanges(); job.node.open=false; render();
      const manual=!job.node.open; job.node.open=true;
      const tool=INPUT.view.active_cards[0].rows[0].tool;
      const sibling={...tool[mode+'_invocations'][0],identity:'identical-command-new-call'};
      tool[mode+'_invocations'].push(sibling);
      if(mode==='background') tool.background_kinds.push('shell');
      else tool.running_invocation_count++;
      render();
      const child=target.jobs.get(sibling.identity), added=job.node.open && !child.node.open;
      tool[mode+'_invocations']=[tool[mode+'_invocations'][0]];
      if(mode==='background') tool.background_kinds=['shell']; else tool.running_invocation_count=1;
      render();
      const survived=target.jobs.get(job.identity)===job && job.node.open && target.node.open;
      tool[mode+'_invocations']=[sibling]; render();
      const switched=!target.node.open && job.input.textContent==='' && !job.node.open;
      results.push({name,revised,manual,added,survived,switched});
      document.activeElement?.blur();
    }
    INPUT.view.active_cards[0].rows[0].tool=saved; render(); return results; })()`);
  assert.equal(causal.length, 4);
  for (const item of causal) for (const name of ['revised','manual','added','survived','switched'])
    assert.equal(item[name], true, item.name + ': ' + name);
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
