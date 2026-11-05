// Actual hidden PiP user activation and outer/inner bounds; no OS desktop input.
const assert = require('node:assert/strict');
module.exports = async function disclosure({evaluate,until,fixture,command,pipSession,layouts,checks}) {
  const read = () => evaluate(`(() => {const w=miniWatch.window,v=miniWatch.view;return {
    outer:[w.outerWidth,w.outerHeight],inner:[w.innerWidth,w.innerHeight],
    session:[v.prompts.clientHeight,v.prompts.scrollHeight],accounts:[v.accounts.clientHeight,v.accounts.scrollHeight],
    expanded:!v.earlier.hidden,attempts:w.probeResizeCalls.length,
    restore:v.disclosureSize.restore,pending:!!v.disclosureSize.pending};})()`);
  const click = async () => {
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},pipSession);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},pipSession);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},pipSession);
    const point=await evaluate(`(() => {const r=miniWatch.view.earlierToggle.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
    for (const type of ['mousePressed','mouseReleased'])
      await command('Input.dispatchMouseEvent',{type,button:'left',clickCount:1,...point},pipSession);
    await until(`!miniWatch.view.disclosureSize.pending`);
  };
  const keyboard = async () => {
    await command('Runtime.evaluate',{expression:`document.querySelector('.mini-earlier-toggle').focus()`},pipSession);
    for (const type of ['keyDown','keyUp']) await command('Input.dispatchKeyEvent',{
      type,key:'Enter',code:'Enter',windowsVirtualKeyCode:13,...(type==='keyDown'?{text:'\r'}:{})},pipSession);
    await until(`!miniWatch.view.disclosureSize.pending`);
  };
  await command('Page.bringToFront',{},pipSession);
  await evaluate(`(() => {const w=miniWatch.window;w.probeResizeCalls=[];w.probeNativeResize=w.resizeTo.bind(w);w.probeNativeResizeBy=w.resizeBy.bind(w);
    w.resizeTo=(...args)=>{w.probeResizeCalls.push(args);return w.probeNativeResize(...args);};
    w.resizeBy=(...args)=>{w.probeResizeCalls.push(args);return w.probeNativeResizeBy(...args);};})()`);
  const size = async (width,height) => {
    await evaluate(`miniWatch.window.resizeTo(${width},${height})`,true);
    await evaluate(`new Promise(resolve=>miniWatch.window.requestAnimationFrame(()=>miniWatch.window.requestAnimationFrame(resolve)))`);
    await evaluate(`miniWatch.window.probeResizeCalls=[]`);
  };
  await fixture('history-3-1'); await until(`miniWatch.view.historyRows.size===3 && miniWatch.view.promptRows.size===1`);
  for (const activate of [click,keyboard,click]) {
    await size(560,300);
    const before=await read(); assert.equal(before.expanded,false);
    assert.ok(before.session[1]<=before.session[0]+1,JSON.stringify(before));
    await activate(); const after=await read();
    assert.equal(after.attempts,1,JSON.stringify({before,after})); assert.equal(after.outer[0],before.outer[0]);
    assert.ok(after.outer[1]>before.outer[1],JSON.stringify(after)); assert.ok(after.restore);
    assert.ok(after.session[1]<=after.session[0]+1,JSON.stringify(after));
    await fixture('history-1-1'); await until(`miniWatch.view.historyRows.size===1`);
    assert.deepEqual((await read()).outer,after.outer,'ordinary history updates never resize');
    await activate(); const collapsed=await read(); collapsed.outer.forEach((n,i)=>assert.ok(Math.abs(n-before.outer[i])<=1));
    layouts.push({case:activate===keyboard?'disclosure-keyboard':'disclosure-pointer',before,after,collapsed});
    await fixture('history-3-1'); await until(`miniWatch.view.historyRows.size===3`);
  }
  await size(560,650); const fit=await read(); await click();
  assert.equal((await read()).attempts,0); await click(); assert.deepEqual((await read()).outer,fit.outer);
  await fixture('history-3-12'); await until(`miniWatch.view.promptRows.size===12`);
  await size(560,300); const scroll=await read(); assert.ok(scroll.session[1]>scroll.session[0]+1);
  await click(); assert.equal((await read()).attempts,0); await click();
  await fixture('history-3-1'); await until(`miniWatch.view.promptRows.size===1`);
  await size(560,300);
  const beforeManual=await read(); await click(); const grownManual=await read();
  assert.ok(grownManual.restore,JSON.stringify({beforeManual,grownManual}));
  await size(600,460); const manual=await read(); await click(); assert.deepEqual((await read()).outer,manual.outer,'manual CDP/native bounds win');
  await size(560,300);
  await until(`!miniWatch.window.navigator.userActivation.isActive && !navigator.userActivation.isActive`);
  const noActivationBefore=await read();
  await evaluate(`miniWatch.view.earlierToggle.click()`);
  await until(`!miniWatch.view.disclosureSize.pending`);
  const noActivation=await read(); assert.equal(noActivation.restore,null);
  assert.deepEqual(noActivation.outer,noActivationBefore.outer); assert.equal(noActivation.expanded,true);
  await evaluate(`miniWatch.view.earlierToggle.click();miniWatch.window.probeResizeCalls=[]`);
  await evaluate(`miniWatch.window.resizeBy=(...args)=>{miniWatch.window.probeResizeCalls.push(args);return miniWatch.window.probeNativeResizeBy(args[0],Math.min(args[1],10));}`);
  const shortBefore=await read(); await click(); const short=await read();
  assert.equal(short.attempts,1); assert.ok(short.restore); assert.ok(short.session[1]>short.session[0]);
  await click(); (await read()).outer.forEach((n,i)=>assert.ok(Math.abs(n-shortBefore.outer[i])<=1));
  await evaluate(`miniWatch.window.probeResizeCalls=[]`);
  await evaluate(`miniWatch.window.resizeBy=undefined;miniWatch.window.resizeTo=(...args)=>{miniWatch.window.probeResizeCalls.push(args);throw new Error('blocked resize');}`);
  await click(); const refused=await read(); assert.equal(refused.restore,null); assert.equal(refused.expanded,true);
  assert.ok(refused.session[1]>refused.session[0]); await click(); assert.equal((await read()).attempts,1);
  await evaluate(`miniWatch.window.resizeTo=undefined`); await click(); assert.equal((await read()).restore,null); await click();
  await evaluate(`miniWatch.window.resizeTo=(...args)=>miniWatch.window.probeResizeCalls.push(args)`);
  await click(); const clamped=await read(); assert.equal(clamped.restore,null); await click();
  await evaluate(`miniWatch.window.resizeTo=(...args)=>{miniWatch.window.probeResizeCalls.push(args);return miniWatch.window.probeNativeResize(...args);}`);
  await evaluate(`miniWatch.window.resizeBy=(...args)=>{miniWatch.window.probeResizeCalls.push(args);return miniWatch.window.probeNativeResizeBy(...args);}`);
  await size(280,650); await click(); const narrow=await read(); assert.equal(narrow.attempts,0); await click();
  layouts.push({case:'disclosure-fit-existing-scroll-manual-refused-clamped-narrow',fit,scroll,noActivation,short,refused,clamped,narrow});
  await size(560,300); await fixture('running'); await until(`miniWatch.view.promptRows.size===2`);
  checks.push('Native pointer/keyboard disclosure grows height once only for new vertical overflow; achieved outer/inner bounds fit rows and collapse restores; existing-scroll, fit, narrow horizontal-only, manual bounds, refused/unsupported/unchanged clamp and SSE never cause repeated resizing');
};
