// Deterministic geometry/activation failures, separate from real PiP browser proof.
const assert = require('node:assert/strict');
module.exports = function disclosure(view, win, controller, input) {
  const prompts = view.prompts, accounts = view.accounts, frames = [], calls = [];
  const originalResize = win.resizeTo, originalStyle = win.getComputedStyle;
  Object.assign(win, {outerWidth:560, outerHeight:300, innerWidth:448});
  win.requestAnimationFrame = fn => frames.push(fn);
  win.getComputedStyle = () => ({maxHeight:'100px'});
  Object.assign(prompts, {clientHeight:90}); Object.assign(accounts, {clientHeight:60, scrollHeight:100});
  let collapsed = 90, expanded = 180;
  Object.defineProperty(prompts, 'scrollHeight', {configurable:true, get:() => view.earlier.hidden ? collapsed : expanded});
  const toggle = () => view.earlierToggle.fire('click');
  const settle = () => {while (frames.length) frames.shift()();};
  win.resizeTo = (width, height) => {
    calls.push([width,height]); win.outerWidth=width; win.outerHeight=height; win.fire('resize');
  };
  assert.equal(view.earlier.hidden,true);
  toggle(); assert.deepEqual(calls,[[560,465]],'overflow plus restored account viewport, converted from CSS pixels');
  settle(); assert.equal(view.disclosureSize.restore.after.height,465);
  for (let i=0;i<5;i++) {input.view.now_ms++; controller.update(input);}
  assert.equal(calls.length,1,'publications never resize');
  toggle(); assert.deepEqual(calls.at(-1),[560,300],'exact pre-expansion bounds');
  toggle(); settle(); win.outerHeight=500; win.fire('resize'); toggle();
  assert.equal(calls.length,3,'manual resize cancels collapse restore');
  win.outerHeight=300;
  for (const [before,after] of [[92,180],[90,90]]) {
    collapsed=before; expanded=after; const count=calls.length;
    toggle(); settle(); toggle(); assert.equal(calls.length,count,'existing scrollbar or already-fitting expansion');
  }
  collapsed=90; expanded=180;
  win.resizeTo = () => {throw new Error('No activation / denied');};
  toggle(); settle(); assert.equal(view.earlier.hidden,false); toggle();
  assert.equal(view.disclosureSize.restore,null,'refused API is not success');
  win.resizeTo = undefined; toggle(); toggle(); assert.equal(view.disclosureSize.restore,null);
  win.resizeTo = () => {}; toggle(); settle();
  assert.equal(view.disclosureSize.restore,null,'unchanged OS clamp is not success');
  win.outerHeight=600; win.fire('resize'); toggle();
  assert.equal(win.outerHeight,600,'later manual growth is not attributed to failed automatic request');
  win.outerHeight=300;
  win.resizeTo = (width,height) => {calls.push([width,height]); win.outerHeight=Math.min(height,350);win.fire('resize');};
  toggle(); settle(); assert.equal(view.disclosureSize.restore.after.height,350,'partial clamp records achieved bounds once');
  toggle(); assert.equal(win.outerHeight,300);
  // Two different native events within the pending confirmation also mean manual intent.
  toggle(); win.outerHeight=375; win.fire('resize'); settle();
  assert.equal(view.disclosureSize.restore,null); toggle(); assert.equal(win.outerHeight,375);
  delete prompts.scrollHeight; delete prompts.clientHeight;
  delete accounts.scrollHeight; delete accounts.clientHeight;
  win.resizeTo=originalResize; win.getComputedStyle=originalStyle;
};
