// Native CDP pointer travel with every exit/movement/blur handler suppressed.
const assert = require('node:assert/strict');
module.exports = async function watchdog({command,evaluate,until,owner,mini,checks}) {
  const evidence=[];
  for(const [id,selector] of [[mini,'.mini-summary'],[mini,'.mini-prompt-table th:first-child button'],
      [mini,'.mini-accounts .help-value'],[owner,'.watch-active th:nth-child(6) button']]) {
    await command('Page.bringToFront',{},id);
    await evaluate(id,`(() => {
      document.activeElement?.blur();
      if(window.suppressHelpExit)return;
      window.suppressHelpExit={enabled:false,events:[]};
      // Window capture precedes the shared document/trigger exit listeners, even
      // when the controller was already used by an earlier probe.
      for(const type of ['pointerout','pointerleave','pointermove','blur'])window.addEventListener(type,event=>{
        if(!suppressHelpExit.enabled)return;
        suppressHelpExit.events.push({type,trusted:event.isTrusted});event.stopImmediatePropagation();
      },true);
    })()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:1,y:1},id);
    const point=await evaluate(id,`(() => {const n=document.querySelector(${JSON.stringify(selector)});
      n.scrollIntoView({block:'nearest'});const r=n.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
    // First race: the pointer leaves silently during the 600ms opening delay.
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},id);
    await evaluate(id,`suppressHelpExit.enabled=true;suppressHelpExit.events=[]`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:-30,y:-30},id);
    await evaluate(id,`new Promise(resolve=>setTimeout(resolve,800))`);
    assert.equal(await evaluate(id,`!!document.querySelector('#context-help')?.matches(':popover-open')`),false,'silent pending exit cannot open help');
    await evaluate(id,`suppressHelpExit.enabled=false`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},id);
    await until(id,`document.querySelector('#context-help')?.matches(':popover-open')`);
    // No selector is mocked: native browser hover state changes, but the state
    // machine receives none of the corresponding exit or outside-move events.
    await evaluate(id,`suppressHelpExit.enabled=true;suppressHelpExit.events=[];window.watchdogOpened=performance.now()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:-30,y:-30},id);
    await until(id,`document.querySelector('#context-help').hidden`);
    const state=await evaluate(id,`({elapsed:performance.now()-watchdogOpened,events:suppressHelpExit.events,
      hovered:document.querySelector(${JSON.stringify(selector)}).matches(':hover'),
      described:document.querySelector(${JSON.stringify(selector)}).getAttribute('aria-describedby'),
      open:document.querySelector('#context-help').matches(':popover-open')})`);
    assert.ok(state.events.some(event=>event.trusted),'native exits really were intercepted');
    assert.ok(state.elapsed<2500,JSON.stringify(state));assert.equal(state.open,false);
    assert.equal(state.hovered,false);assert.ok(!state.described?.split(' ').includes('context-help'));
    await evaluate(owner,`miniWatch.render();current.watch.update(liveValue)`);
    assert.equal(await evaluate(id,`document.querySelector('#context-help').hidden`),true,'Live cannot reopen watchdog dismissal');
    evidence.push({document:id===mini?'mini':'watch',selector,...state});
    await evaluate(id,`suppressHelpExit.enabled=false`);
  }
  // Deliberate keyboard focus remains independent of hover.
  for(const id of [owner,mini]) {
    const selector=id===mini?'.mini-accounts .help-value':'.watch-active th:nth-child(6) button';
    await command('Page.bringToFront',{},id);
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},id);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},id);
    await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).focus()`);
    await until(id,`document.querySelector('#context-help').matches(':popover-open')`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:-30,y:-30},id);
    await evaluate(id,`new Promise(resolve=>setTimeout(resolve,1250))`);
    assert.equal(await evaluate(id,`document.querySelector('#context-help').hidden`),false,'keyboard help is not hover-owned');
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',windowsVirtualKeyCode:27},id);
    await evaluate(id,`document.activeElement?.blur()`);
  }
  const pin=await evaluate(mini,`(() => {const n=document.querySelector('.mini-accounts .help-value');
    n.scrollIntoView({block:'nearest'});const r=n.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
  await command('Page.bringToFront',{},mini);
  await command('Emulation.setTouchEmulationEnabled',{enabled:true},mini);
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[pin]},mini);
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},mini);
  await until(mini,`document.querySelector('#context-help').matches(':popover-open')`);
  await evaluate(mini,`new Promise(resolve=>setTimeout(resolve,1250))`);
  assert.equal(await evaluate(mini,`document.querySelector('#context-help').hidden`),false,'passive touch pin survives hover checks');
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:2,y:2}]},mini);
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},mini);
  assert.equal(await evaluate(mini,`document.querySelector('#context-help').hidden`),true,'outside tap dismisses passive help');
  await command('Emulation.setTouchEmulationEnabled',{enabled:false},mini);
  await evaluate(mini,`document.activeElement?.blur()`);
  checks.push({case:'watchdog: native silent opening/open exits in actual PiP and Full Watch, ARIA/Popover cleanup, no Live resurrection',evidence});
};
