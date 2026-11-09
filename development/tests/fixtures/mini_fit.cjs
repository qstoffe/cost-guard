// Explicit fit only: obsolete disclosure/delta assertions intentionally retired.
const assert=require('node:assert/strict');
module.exports=function fit(view,win,controller,input) {
  const calls=[],original=win.resizeTo;let desired=270;
  Object.assign(win,{outerWidth:650,outerHeight:400,innerWidth:628,screen:{availHeight:1000}});
  view.fitHeight=reserve=>{assert.equal(reserve,false);return desired;};
  win.resizeTo=(width,height)=>{calls.push([width,height]);win.outerHeight=height;};
  const click=()=>view.fitButton.fire('click');
  click();assert.deepEqual(calls,[[650,270]]);click();assert.equal(calls.length,1);
  desired=570;click();click();assert.deepEqual(calls,[[650,270],[650,570]]);
  for(let i=0;i<5;i++){input.view.now_ms++;controller.update(input);}assert.equal(calls.length,2);
  win.navigator={userActivation:{isActive:false}};desired=230;click();assert.equal(calls.length,2);
  win.navigator.userActivation.isActive=true;win.closed=true;click();assert.equal(calls.length,2);win.closed=false;
  Object.defineProperty(view.root,'isConnected',{value:false,configurable:true});click();assert.equal(calls.length,2);delete view.root.isConnected;
  win.resizeTo=()=>{calls.push('refused');throw new Error('NotAllowedError');};click();assert.equal(calls.at(-1),'refused');
  win.resizeTo=undefined;click();assert.equal(calls.length,3);
  win.resizeBy=(dx,dy)=>{assert.equal(dx,0);win.outerHeight+=dy;calls.push([dx,dy]);};click();assert.equal(win.outerHeight,230);
  delete win.resizeBy;delete view.fitHeight;delete win.navigator;win.resizeTo=original;
};
