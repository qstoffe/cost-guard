// Deterministic activation/clamp/race policy; real browser owns layout measurements.
const assert = require('node:assert/strict');
module.exports = function disclosure(view, win, controller, input) {
  const frames = [], calls = [], size = view.disclosureSize;
  const originalResize = win.resizeTo;
  Object.assign(win, {outerWidth:650, outerHeight:400, innerWidth:628, screen:{availHeight:1000}});
  win.requestAnimationFrame = fn => frames.push(fn);
  view.fitHeight = () => view.earlier.hidden ? 400 : 550;
  const state = () => {
    const expanded = String(!view.earlier.hidden);
    assert.equal(view.earlierToggle.attributes['aria-pressed'],expanded);
    assert.equal(view.earlierToggle.attributes['aria-expanded'],expanded);
    assert.equal(view.prompts.dataset.expanded,expanded);
    assert.equal(view.earlierToggle.attributes['aria-controls'],'mini-earlier-sessions');
    assert.equal(view.earlierToggle.textContent,'Earlier Sessions');
  };
  const toggle = () => { view.earlierToggle.fire('click'); state(); };
  const settle = () => {while (frames.length) frames.shift()();};
  win.resizeTo = (width, height) => {
    state(); // State is synchronized before layout/resize observers can run.
    calls.push([width,height]); win.outerWidth=width; win.outerHeight=height; win.fire('resize');
  };
  toggle(); settle(); assert.deepEqual(calls,[[650,550]]);
  for (let i=0;i<5;i++) {input.view.now_ms++; controller.update(input);}
  state(); assert.equal(view.earlier.hidden,false,'ordinary updates preserve the pressed choice');
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
  let desired=270;
  view.fitHeight=reserve=>{assert.equal(reserve,false,'manual fit excludes the opening reserve');return desired;};
  size.mode='remember-last';size.widthCorrection=-1;calls.length=0;
  win.resizeTo=(width,height)=>{calls.push([width,height]);win.outerWidth=width;win.outerHeight=height;win.fire('resize');};
  const fit=()=>view.fitButton.fire('click');
  const width=win.outerWidth;fit();settle();assert.deepEqual(calls,[[width,270]]);
  assert.equal(view.earlier.hidden,true);assert.equal(size.restore,null);
  fit();settle();assert.equal(calls.length,1,'unchanged fit is idempotent');
  desired=570;fit();fit();settle();assert.deepEqual(calls.at(-1),[width,570]);assert.equal(calls.length,2);
  desired=230;fit();win.outerHeight=400;win.fire('resize');settle();
  assert.equal(win.outerHeight,400,'late observations never undo a manual native resize');assert.equal(size.restore,null);
  win.navigator.userActivation.isActive=false;fit();assert.equal(calls.length,3);
  win.navigator.userActivation.isActive=true;win.closed=true;fit();assert.equal(calls.length,3);win.closed=false;
  Object.defineProperty(view.root,'isConnected',{value:false,configurable:true});fit();assert.equal(calls.length,3);delete view.root.isConnected;
  win.resizeTo=()=>{calls.push('refused');throw new Error('NotAllowedError');};fit();settle();assert.equal(size.pending,null);
  win.resizeTo=undefined;fit();assert.equal(calls.at(-1),'refused');
  desired=397;win.outerHeight=400;const snugCalls=calls.length;
  view.doc.scrollingElement={scrollHeight:100,clientHeight:100};
  win.resizeTo=(width,height)=>{calls.push([width,height]);win.outerHeight=height;};
  fit();assert.equal(calls.length,snugCalls,'do not chase native rounding of an already scroll-free snug fit');
  view.doc.scrollingElement.scrollHeight=102;fit();settle();assert.equal(calls.length,snugCalls+1,'real overflow is not waived by the rounding guard');
  delete view.doc.scrollingElement;
  delete view.fitHeight; delete win.navigator;
  win.resizeTo=originalResize;
};
