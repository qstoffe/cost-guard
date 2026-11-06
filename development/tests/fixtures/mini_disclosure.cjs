// Deterministic activation/clamp/race policy; real browser owns layout measurements.
const assert = require('node:assert/strict');
module.exports = function disclosure(view, win, controller, input) {
  const frames = [], calls = [], size = view.disclosureSize;
  const originalResize = win.resizeTo;
  Object.assign(win, {outerWidth:650, outerHeight:400, innerWidth:628, screen:{availHeight:1000}});
  win.requestAnimationFrame = fn => frames.push(fn);
  view.fitHeight = () => view.earlier.hidden ? 400 : 550;
  const toggle = () => view.earlierToggle.fire('click');
  const settle = () => {while (frames.length) frames.shift()();};
  win.resizeTo = (width, height) => {
    calls.push([width,height]); win.outerWidth=width; win.outerHeight=height; win.fire('resize');
  };
  toggle(); settle(); assert.deepEqual(calls,[[650,550]]);
  for (let i=0;i<5;i++) {input.view.now_ms++; controller.update(input);}
  assert.equal(calls.length,1,'passive publications never resize');
  toggle(); assert.deepEqual(calls.at(-1),[650,400],'fit collapse uses current two-row baseline');
  toggle(); settle(); win.outerWidth=600; win.outerHeight=700; win.fire('resize'); toggle();
  assert.deepEqual(calls.at(-1),[600,400],'fit collapse preserves current manual width');
  size.mode='remember-last'; win.outerHeight=450;
  toggle(); settle(); toggle(); assert.deepEqual(calls.at(-1),[600,450]);
  toggle(); settle(); win.outerHeight=500; win.fire('resize'); const count=calls.length; toggle();
  assert.equal(calls.length,count,'manual resize invalidates remembered restoration');
  size.mode='fit-on-open'; win.outerHeight=400;
  win.navigator={userActivation:{isActive:false}}; toggle(); settle();
  assert.equal(calls.length,count); assert.equal(view.earlier.hidden,false);
  toggle(); win.navigator.userActivation.isActive=true;
  win.resizeTo = () => {throw new Error('NotAllowedError');};
  toggle(); settle(); assert.equal(size.restore,null); toggle();
  win.resizeTo = () => {}; toggle(); settle(); assert.equal(size.restore,null); toggle();
  win.resizeTo = undefined; toggle(); toggle(); assert.equal(size.restore,null);
  win.resizeTo = (width,height) => {calls.push([width,height]); win.outerHeight=Math.min(height,480);win.fire('resize');};
  toggle(); settle(); assert.equal(size.restore.after.height,480,'achieved clamp, not requested target');
  toggle(); assert.equal(win.outerHeight,400);
  toggle(); win.outerHeight=490; win.fire('resize'); settle(); assert.equal(size.restore,null);
  toggle(); settle(); assert.equal(view.earlier.hidden,true,'rapid toggle cancels pending work');
  assert.equal(size.pending,null);
  win.outerWidth=600;win.outerHeight=400;size.widthCorrection=0;
  win.resizeBy=(dx,dy)=>{win.outerWidth+=dx+1;win.outerHeight+=dy;win.fire('resize');};
  for(let index=0;index<4;index++){toggle();settle();toggle();settle();}
  assert.equal(win.outerWidth,601,'observed one-DIP native rounding cannot accumulate across clicks');
  delete win.resizeBy;
  delete view.fitHeight; delete win.navigator;
  win.resizeTo=originalResize;
};
