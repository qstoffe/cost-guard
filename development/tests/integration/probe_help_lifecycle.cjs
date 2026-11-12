// Shared controller evidence using real Chromium pointer/key input in main/PiP.
const assert = require('node:assert/strict');
module.exports = async function lifecycle({command,evaluate,until,owner,mini,checks}) {
  const events = [];
  for (const [id, selector] of [[mini,'.mini-summary'],[mini,'.mini-prompts > table th:first-child button'],
      [mini,'.mini-accounts .help-value'],[owner,'.watch-active th:nth-child(6) button']]) {
    await command('Page.bringToFront',{},id);
    await evaluate(id,`(() => {window.helpEvents=[];if(window.helpEventsInstalled)return;window.helpEventsInstalled=true;for(const type of ['pointerout','pointerleave'])document.addEventListener(type,e=>{if(!e.relatedTarget&&!helpEvents.includes(type+':null'))helpEvents.push(type+':null');},true);window.addEventListener('blur',()=>helpEvents.push('blur'));})()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:1,y:1},id);
    const point = await evaluate(id,`(() => {const n=document.querySelector(${JSON.stringify(selector)});n.scrollIntoView({block:'nearest'});const r=n.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},id);
    await until(id,`document.querySelector('#context-help')?.matches(':popover-open')`);
    // Mouse-owned focus, not keyboard intent. Do not click the action under test.
    await evaluate(id,`document.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));document.querySelector(${JSON.stringify(selector)}).focus()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:-30,y:-30},id);
    await evaluate(id,`new Promise(resolve=>setTimeout(resolve,220))`);
    const state = await evaluate(id,`({hidden:document.querySelector('#context-help').hidden,events:helpEvents,focused:document.activeElement===document.querySelector(${JSON.stringify(selector)})})`);
    events.push({document:id===mini?'mini':'watch',selector,...state});
    assert.equal(state.hidden,true,'hover must close beyond document even with mouse-owned focus: '+JSON.stringify(events));
    await evaluate(owner,`miniWatch.render();current.watch.update(liveValue)`);
    assert.equal(await evaluate(id,`document.querySelector('#context-help').hidden`),true,'rerender cannot resurrect exit-dismissed help');
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},id);
    await until(id,`document.querySelector('#context-help').matches(':popover-open')`);
    // Simulate a missed trigger leave: only the document boundary is delivered.
    await evaluate(id,`document.dispatchEvent(new PointerEvent('pointerout',{relatedTarget:null,bubbles:true}))`);
    await until(id,`document.querySelector('#context-help').hidden`);
    await evaluate(id,`document.activeElement.blur()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:-30,y:-30},id);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},id);
    await until(id,`document.querySelector('#context-help').matches(':popover-open')`);
    await command('Page.bringToFront',{},id===mini?owner:mini);
    const blur=await evaluate(id,`({focused:document.hasFocus(),events:helpEvents})`);
    // Headless PiP can start unfocused, so bringing another target forward may
    // produce no OS blur. Exercise that handler explicitly and disclose which ran.
    if (!blur.events.includes('blur')) await evaluate(id,`window.dispatchEvent(new Event('blur'))`);
    events.push({document:id===mini?'mini':'watch',case:'window-blur',native:blur.events.includes('blur'),focused:blur.focused});
    await until(id,`document.querySelector('#context-help').hidden`);
    await command('Page.bringToFront',{},id);
    // A genuine keyboard interaction owns its help despite incidental mouse exit.
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},id);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},id);
    await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).focus()`);
    await until(id,`document.querySelector('#context-help').matches(':popover-open')`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:-30,y:-30},id);
    await evaluate(id,`new Promise(resolve=>setTimeout(resolve,220))`);
    assert.equal(await evaluate(id,`document.querySelector('#context-help').hidden`),false,'keyboard ownership survives pointer exit: '+selector);
    await evaluate(id,`document.activeElement.blur()`);
  }
  for (const activation of ['mouse','touch','Enter','Space']) {
    await evaluate(owner,`location.hash='#/settings'`);
    await until(owner,`document.body.dataset.section==='settings'`);
    await command('Page.bringToFront',{},mini);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:1,y:1},mini);
    const point=await evaluate(mini,`(() => {const r=document.querySelector('.mini-summary').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},mini);
    await until(mini,`document.querySelector('#context-help').matches(':popover-open')`);
    if (activation==='mouse') {
      for(const type of ['mousePressed','mouseReleased']) await command('Input.dispatchMouseEvent',{type,button:'left',clickCount:1,...point},mini);
    } else if (activation==='touch') {
      await command('Emulation.setTouchEmulationEnabled',{enabled:true},mini);
      await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]},mini);
      await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},mini);
      await command('Emulation.setTouchEmulationEnabled',{enabled:false},mini);
    } else {
      await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},mini);
      await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},mini);
      await evaluate(mini,`document.querySelector('.mini-summary').focus()`);
      const key=activation==='Space'?' ':activation,code=activation==='Space'?32:13;
      await command('Input.dispatchKeyEvent',{type:'keyDown',key,code:activation,windowsVirtualKeyCode:code,text:code===13?'\r':' '},mini);
      await command('Input.dispatchKeyEvent',{type:'keyUp',key,code:activation,windowsVirtualKeyCode:code},mini);
    }
    assert.equal(await evaluate(mini,`document.querySelector('#context-help').hidden`),true,activation+' dismisses action help immediately');
    await until(owner,`document.body.dataset.section==='watch'`);
    await evaluate(owner,`miniWatch.render()`);
    await command('Page.bringToFront',{},mini);
    assert.equal(await evaluate(mini,`document.querySelector('#context-help').hidden`),true,'focus restoration and render do not reopen action help');
    await evaluate(mini,`document.activeElement.blur()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:1,y:1},mini);
  }
  checks.push({case:'rapid document exit with lingering pointer focus and missed element leave',events});
  checks.push('Return-to-Watch works and dismisses immediately for real mouse/touch/Enter/Space; no focus/Live resurrection');
};
