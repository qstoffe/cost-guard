// Real authenticated HTTP, canonical synthetic history and shipped native disclosures.
const assert = require('node:assert/strict');
module.exports = async function activity({evaluate, until, fixture, command}) {
  const checks = [], layouts = [];
  await fixture('activity-source');
  await evaluate("location.hash='#/sessions/root'");
  await until('current?.detail?.data?.activity?.failed_count === 60');
  assert.deepEqual(await evaluate(`(() => {const a=current.detail.activity;return [
    a.root.querySelectorAll(':scope > details').length,a.tools.node.open,a.skills.node.open,
    current.detail.data.activity.failures.length,current.detail.body.children.length];})()`),[2,false,false,25,3]);
  assert.match(await evaluate('current.detail.activity.tools.summary.textContent'),/65 tool calls.*61 failed \/ cancelled/);
  assert.equal(await evaluate('current.detail.activity.skills.summary.textContent'),'Skills · 1 confirmed custom skills');
  assert.equal(await evaluate('current.detail.body.children[0].children[4].textContent'),'3','wrapper, child and continuation model calls are not tool counts');
  // Native keyboard activation of the initially closed top-level disclosure.
  await evaluate('current.detail.activity.tools.summary.focus()');
  assert.equal(await evaluate('document.activeElement===current.detail.activity.tools.summary'),true);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:' ',code:'Space',windowsVirtualKeyCode:32,text:' '});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:' ',code:'Space',windowsVirtualKeyCode:32});
  await until('current.detail.activity.tools.node.open');
  await evaluate(`window.group=[...current.detail.activity.tools.rows.values()].find(v=>v.summary?.textContent==='60 × read failed');
    group.node.open=true;window.call=[...group.jobs.values()][0];call.node.open=true;window.input=call.input;
    call.summary.focus();`);
  assert.match(await evaluate('call.list.textContent'),/src\/same.py.*Recorded outcome: failed; source status: error.*prompt #/s);
  const click = async expression => {
    const point = await evaluate(`(() => {const n=${expression};n.scrollIntoView({block:'center'});const r=n.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
    await command('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...point});
    await command('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...point});
  };
  await click('current.detail.activity.more');
  await until('current.detail.data.activity.failures.length === 50');
  await click('current.detail.activity.more');
  await until('current.detail.data.activity.failures.length === 61');
  assert.equal(await evaluate('group.jobs.size'),60);
  assert.equal(await evaluate('current.detail.activity.more.hidden'),true);
  assert.equal(await evaluate('call.input===input && call.node.open && group.node.open'),true);
  assert.match(await evaluate('group.list.textContent'),/Failure reason unavailable/);
  assert.doesNotMatch(await evaluate('current.detail.activity.root.textContent'),/synthetic-secret|private file contents|private arbitrary error/);
  const cancel = await evaluate(`[...current.detail.activity.tools.rows.values()].find(v=>v.summary?.textContent==='1 × shell cancelled').list.textContent`);
  assert.match(cancel,/Recorded outcome: cancelled; source status: error/);
  assert.match(cancel,/--token \[redacted\] --check/);
  checks.push('three prompts/compaction; separate model calls; two closed panels; keyboard opening; 60 distinct read failures plus cancellation reachable in 25-call pages; redaction and unavailable reason');
  // Keep actual selected text, scroll and focused native summary through live growth.
  await evaluate(`call.summary.focus();window.range=document.createRange();range.selectNodeContents(input);
    getSelection().removeAllRanges();getSelection().addRange(range);window.selected=getSelection().toString();
    window.beforeY=scrollY;window.beforeRevision=current.detail.data.revision;`);
  await fixture('activity-update');
  await until('current.detail.data.activity.failed_count === 61');
  assert.equal(await evaluate(`group.node.open && call.node.open && call.input===input &&
    document.activeElement===call.summary && getSelection().toString()===selected && Math.abs(scrollY-beforeY)<2`),true);
  await fixture('activity-correction');
  await until("call.input.textContent.includes('src/corrected.py')");
  assert.match(await evaluate('call.note.textContent'),/Permission denied/);
  assert.equal(await evaluate('call.node.open && group.node.open && document.activeElement===call.summary'),true);
  checks.push('live additions/terminal source correction retain group/call/input DOM, open state, focus, selection and scroll; safe reason updates');
  await evaluate('getSelection().removeAllRanges();document.activeElement.blur()');
  for (const theme of ['light','dark']) for (const width of [360,1366]) for (const zoom of [1,1.5]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme}]});
    await evaluate(`document.documentElement.dataset.theme='web';document.body.style.zoom=${zoom}`);
    const geometry = await evaluate(`(() => {const root=current.detail.activity.root;const r=input.getBoundingClientRect();return {
      overflow:document.documentElement.scrollWidth>innerWidth+1,wrapping:getComputedStyle(input).whiteSpace,
      nested:call.node.getBoundingClientRect().left>group.node.getBoundingClientRect().left,
      color:getComputedStyle(group.summary).color,visible:r.width>0};})()`);
    assert.equal(geometry.overflow,false); assert.equal(geometry.visible,true); assert.equal(geometry.nested,true);
    layouts.push({theme,width,zoom,...geometry});
  }
  // Trusted touch toggles the other independent native disclosure.
  const point = await evaluate(`(() => {const n=current.detail.activity.skills.summary;n.scrollIntoView({block:'center'});const r=n.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]});
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await until('current.detail.activity.skills.node.open');
  assert.equal(await evaluate('current.detail.activity.tools.node.open'),true);
  await evaluate("window.oldActivity=current.detail.activity;location.hash='#/sessions/root-0001'");
  await until('current?.detail?.id==="root-0001" && current.detail.data');
  assert.equal(await evaluate("oldActivity.root.hidden && !oldActivity.root.textContent.includes('src/corrected.py')"),true);
  assert.equal(await evaluate('current.detail.activity.tools.node.open || current.detail.activity.skills.node.open'),false);
  checks.push('light/dark 360/1366 at 100/150% zoom; logical nesting, no page overflow; touch Skills independent; navigation clears previous invocation data/open state');
  return {checks,layouts};
};
