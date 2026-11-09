// Deterministic activation/clamp/race policy; real browser owns layout measurements.
const assert = require('node:assert/strict');
module.exports = function disclosure(view, win, controller, input) {
  const frames = [], calls = [], size = view.disclosureSize;
  const originalResize = win.resizeTo;
  Object.assign(win, {outerWidth:650, outerHeight:400, innerWidth:628, screen:{availHeight:1000}});
  win.requestAnimationFrame = fn => frames.push(fn);
  let layout = {width:600,collapsed:200,expanded:350,scale:1};
  view.disclosureLayout = () => ({...layout});
  view.fitHeight = () => {throw new Error('Disclosure must never fit the whole window');};
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
  toggle(); settle(); assert.deepEqual(calls.at(-1),[650,400],'collapse restores the preceding baseline');
  toggle(); settle(); win.outerWidth=600; win.outerHeight=700; win.fire('resize'); toggle();
  settle(); assert.deepEqual(calls.at(-1),[600,550],'manual resize invalidates restoration and subtracts only current delta');
  size.mode='remember-last'; win.outerHeight=450;
  toggle(); settle(); toggle(); assert.deepEqual(calls.at(-1),[600,450]);
  toggle(); settle(); win.outerHeight=500; win.fire('resize'); toggle(); settle();
  assert.equal(win.outerHeight,350,'both modes reconcile manual resize using only current delta');
  for (const mode of ['fit-on-open','remember-last']) for (const baseline of [220,400,800]) {
    size.mode=mode;win.outerHeight=baseline;
    for(let index=0;index<4;index++){toggle();settle();assert.equal(win.outerHeight,baseline+150);toggle();settle();assert.equal(win.outerHeight,baseline);}
  }
  win.outerHeight=400;toggle();settle();layout={...layout,expanded:300};toggle();settle();
  assert.equal(win.outerHeight,450,'changed history subtracts its current rendered contribution, not a stale baseline');
  layout={...layout,expanded:350};
  win.outerHeight=1005;const cappedCount=calls.length;toggle();settle();toggle();settle();
  assert.equal(win.outerHeight,1005);assert.equal(calls.length,cappedCount,'disclosure cannot shrink a baseline already above the fit cap');
  const count=calls.length;
  size.mode='fit-on-open'; win.outerHeight=400;
  win.navigator={userActivation:{isActive:false}}; toggle(); settle();
  assert.equal(calls.length,count); assert.equal(view.earlier.hidden,false);
  toggle(); win.navigator.userActivation.isActive=true;
  win.navigator.userActivation.isActive=false;toggle();settle();win.navigator.userActivation.isActive=true;
  toggle();settle();assert.equal(win.outerHeight,400,'an inactive expansion contributes no height to remove on active collapse');
  win.resizeTo = () => {throw new Error('NotAllowedError');};
  toggle(); settle(); assert.equal(size.restore.after.height,400); toggle();settle();assert.equal(calls.length,count,'refusal cannot cause a later spurious collapse shrink');
  win.resizeTo = () => {}; toggle(); settle(); assert.equal(size.restore.after.height,400); toggle();settle();assert.equal(win.outerHeight,400);
  win.resizeTo = undefined; toggle(); toggle(); assert.equal(size.restore,null);
  win.resizeTo = (width,height) => {calls.push([width,height]); win.outerHeight=Math.min(height,480);win.fire('resize');};
  toggle(); settle(); assert.equal(size.restore.after.height,480,'achieved clamp, not requested target');
  toggle(); assert.equal(win.outerHeight,400);
  toggle(); win.outerHeight=490; win.fire('resize'); settle(); assert.equal(size.restore,null);
  toggle(); settle(); assert.equal(view.earlier.hidden,true,'rapid toggle cancels pending work');
  assert.equal(size.pending,null);
  win.outerHeight=400;win.outerWidth=600;
  view.disclosureLayout=()=>({...layout,width:win.outerWidth,expanded:win.outerWidth===600?350:360});
  win.resizeTo=(width,height)=>{calls.push([width,height]);win.outerWidth=500;win.outerHeight=Math.min(height,450);win.fire('resize');};
  toggle();settle();assert.equal(size.restore.layout.width,500,'observe the achieved native-width layout');
  toggle();settle();assert.equal(win.outerHeight,400,'remove only achieved growth despite native width change');
  assert.deepEqual(calls.at(-1),[500,400],'collapse requests the baseline height at actual current width');
  view.disclosureLayout=()=>({...layout});
  win.outerWidth=600;win.outerHeight=400;
  win.resizeBy=(dx,dy)=>{assert.equal(dx,0,'no width correction request');win.outerHeight+=Math.round(dy);win.fire('resize');};
  layout={...layout,expanded:250.25,scale:1.5};
  for(let index=0;index<4;index++){toggle();settle();assert.equal(win.outerHeight,475);toggle();settle();assert.equal(win.outerHeight,400);}
  delete win.resizeBy;
  let desired=270;
  view.fitHeight=reserve=>{assert.equal(reserve,false,'manual fit excludes the opening reserve');return desired;};
  size.mode='remember-last';calls.length=0;
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
  delete view.fitHeight; delete view.disclosureLayout; delete win.navigator;
  win.resizeTo=originalResize;
};
