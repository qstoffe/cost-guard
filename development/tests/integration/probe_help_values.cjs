// Real pointer/focus proof for direct text targets and delayed rich prompt detail.
const assert = require('node:assert/strict');
module.exports = async function values({command,evaluate,until,owner,mini,checks,layouts}) {
  await evaluate(owner,`ReportView.setUnit('credits',current.watch.root);ReportView.setUnit('credits',miniWatch.view.root)`);
  const pause = (id,ms) => evaluate(id,`new Promise(resolve=>setTimeout(resolve,${ms}))`);
  const move = (id,point) => command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},id);
  for (const [id,selector] of [[owner,'.watch-active tbody td:nth-child(6) .help-value'],
      [mini,'.mini-prompts > table th:first-child button']]) {
    await command('Page.bringToFront',{},id);
    await evaluate(id,`document.activeElement?.blur()`);await move(id,{x:0,y:0});await pause(id,200);
    const point=await evaluate(id,`(() => {const n=document.querySelector(${JSON.stringify(selector)});n.scrollIntoView({block:'center',inline:'center'});const r=n.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
    await move(id,point);await pause(id,250);
    assert.equal(await evaluate(id,`!!document.querySelector('#context-help')?.matches(':popover-open')`),false,'no early hover popup');
    await move(id,{x:0,y:0});await pause(id,450);
    assert.equal(await evaluate(id,`!!document.querySelector('#context-help')?.matches(':popover-open')`),false,'flyover stays closed');
    await move(id,point);await pause(id,300);
    assert.equal(await evaluate(id,`!!document.querySelector('#context-help')?.matches(':popover-open')`),false,'fresh re-entry gets a full delay');
    await until(id,`document.querySelector('#context-help')?.matches(':popover-open')`);
    await move(id,{x:-20,y:-20});await pause(id,200);
  }
  for (const selector of ['.watch-active tbody td:nth-child(6) .help-value','.watch-history tbody td:nth-child(6) .help-value']) {
    await evaluate(owner,`document.querySelector('.watch-earlier').open=true`);
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},owner);
    await evaluate(owner,`document.querySelector(${JSON.stringify(selector)}).focus()`);
    const text=await evaluate(owner,`document.querySelector('#context-help').textContent`);
    assert.match(text,/Main prompt — Main Model · High\n• Input: 8\n• Cached input: 2\n• Cache write: 1\n• Output: 14\nSubtotal: 25/);
    assert.match(text,/Subagents — Child Model · Low \(2 agents\)\n• Number of prompts: 2\n• Input:[\s\S]*Subtotal: 8[\s\S]*Total CCost: 33/);
    assert.doesNotMatch(text,/input tokens|Default \(/);
    await evaluate(owner,`ReportView.setUnit('usd',current.watch.root)`);
    assert.match(await evaluate(owner,`document.querySelector('#context-help').textContent`),/• Input: \$0.08[\s\S]*Total CCost: \$0.33/);
    await evaluate(owner,`ReportView.setUnit('credits',current.watch.root);document.activeElement.blur()`);
  }
  for (const selector of ['.watch-subscription .metric-value > .help-value','.watch-quota-capacity .help-value']) {
    const target=await evaluate(owner,`(() => {const n=document.querySelector(${JSON.stringify(selector)}),p=n.parentNode;n.scrollIntoView({block:'center'});const r=n.getBoundingClientRect(),b=p.getBoundingClientRect();return {cursor:getComputedStyle(n).cursor,display:getComputedStyle(n).display,text:n.textContent,width:r.width,parentWidth:b.width,focusable:n.tabIndex};})()`);
    assert.equal(target.cursor,'help');assert.equal(target.focusable,0);
    assert.ok(target.width<target.parentWidth,'no full-card trigger');layouts.push({case:'account-value-target',selector,...target});
  }
  assert.equal(await evaluate(owner,`document.querySelector('.watch-active tbody td:nth-child(4)').textContent`),'Model*');
  assert.equal(await evaluate(owner,`document.querySelector('.watch-history tbody td:nth-child(4)').textContent`),'Model*');
  const summary=await evaluate(owner,`[...document.querySelector('.watch-active .watch-session-summary').children].map(n=>({text:n.textContent,top:n.getBoundingClientRect().top}))`);
  assert.match(summary[0].text,/^Context: /);assert.match(summary[1].text,/^Total CCost: /);assert.ok(summary[1].top>summary[0].top);
  assert.equal(await evaluate(owner,`document.querySelectorAll('.help-cue').length`),0);
  checks.push('600ms delayed opening/flyover cancellation in main/PiP; rich main/linked-agent category costs in both Full Watch tables and live unit switching; direct account text hitboxes; separate Context/Total CCost rows');
};
