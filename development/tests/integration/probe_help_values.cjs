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
    assert.match(text,/^Incoming Context CCost \(I\): [^\n]+\nExtra CCost \(E\): [^\n]+\n/);
    assert.match(text,/Main prompt — fixture\/main-model · High\n• Input: 8\n• Cached input: 2\n• Cache write: 1\n• Output: 14\nCalls: 2 · Subtotal: 25/);
    assert.match(text,/Subagent 1 — fixture\/child-model · Low\n• Number of prompts: 1\n• Input:[\s\S]*Subtotal: 8[\s\S]*Subagent 2 — fixture\/child-model · Low[\s\S]*Subtotal: 0[\s\S]*Total CCost: 33/);
    assert.doesNotMatch(text,/input tokens|Default \(/);
    await evaluate(owner,`ReportView.setUnit('usd',current.watch.root)`);
    assert.match(await evaluate(owner,`document.querySelector('#context-help').textContent`),/• Input: \$0.08[\s\S]*Total CCost: \$0.33/);
    await evaluate(owner,`ReportView.setUnit('credits',current.watch.root);document.activeElement.blur()`);
  }
  for(const [unit,total,main,child] of [['credits','25 Credits','4000','583'],['usd','\\$0.25','\\$40.00','\\$5.82']]) {
    // Settings applies the unit and rerenders Mini's compact prepared help.
    await evaluate(owner,`ReportView.setUnit('${unit}',current.watch.root);miniWatch.render()`);
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},mini);
    await evaluate(mini,`document.querySelector('.mini-prompts tr[data-id="root"] td:nth-child(3) .help-value').focus()`);
    await until(mini,`document.querySelector('#context-help')?.matches(':popover-open')`);
    const compact=await evaluate(mini,`document.querySelector('#context-help').textContent`);
    assert.match(compact,new RegExp('^Prompt #\\d+\\nMain Model: fixture/main-model — High\\nMain Model CCost: '+total+
      '\\n\\nSub Agent 1: fixture/child-model — Low\\nSub Agent 1 CCost: '+(unit==='credits'?'8 Credits':'\\$0.08')+
      '\\n\\nDuration: '));
    assert.doesNotMatch(compact,/• Input:|• Cached input:|• Cache write:/,'Mini uses compact help, not the full category essay');
    for(const [id,selector] of [[owner,'.watch-active .watch-session-summary > div:nth-child(2) .help-value'],
        [mini,'.mini-prompts tr[data-id="root"] td:nth-child(4) .help-value']]) {
      await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},id);
      await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).focus()`);
      await until(id,`document.querySelector('#context-help')?.matches(':popover-open')`);
      const whole=await evaluate(id,`document.querySelector('#context-help').textContent`);
      assert.match(whole, id===owner ?
        new RegExp('Whole root session tree\\nAll main requests: '+main+'\\nAll linked subagent requests: '+child) :
        new RegExp('^Session Model 1: fixture/main-model — High\\nSession Model 1 CCost: '+main+
          (unit==='credits'?' Credits':'')+'\\n\\nSub Agent 1: fixture/child-model — Low\\nSub Agent 1 CCost: '+child+
          (unit==='credits'?' Credits':'')+'\\n\\nDuration: N/A$'));
      await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},id);
    }
  }
  await evaluate(owner,`ReportView.setUnit('credits',current.watch.root);miniWatch.render()`);
  checks.push('Credits/USD compact Mini model/effort prompt groups and Full/Mini whole-session main/subagent totals share prepared values');
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
