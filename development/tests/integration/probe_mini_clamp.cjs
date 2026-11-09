// Focused compounded zoom/DPR lifecycle: requested geometry is not achieved geometry.
const assert = require('node:assert/strict');
module.exports = async ({evaluate,command,targetId,open,close,read,capture,fixture,until,layouts,checks}) => {
  await fixture('history-3-2-1');
  await until('liveValue.view.history_cards.length===3 && liveValue.view.active_cards.length===2');
  const settle=()=>evaluate('new Promise(resolve=>miniWatch.window.requestAnimationFrame(()=>miniWatch.window.requestAnimationFrame(resolve)))');
  for(const mode of ['fit-on-open','remember-last']) {
    await evaluate(`(async()=>applySettings(await api('/api/settings/mini-size',{miniWatchSize:'${mode}'})))()`);
    await open();
    let pip;
    for(const target of (await command('Target.getTargets')).targetInfos.filter(t=>t.targetId!==targetId&&t.type==='page')) {
      const attached=await command('Target.attachToTarget',{targetId:target.targetId,flatten:true});
      if(await evaluate('!!document.querySelector(".mini-watch")',false,attached.sessionId)){pip=attached.sessionId;break;}
    }
    assert.ok(pip);await command('Page.bringToFront',{},pip);
    await evaluate(`(()=>{const w=miniWatch.window;w.clampResizes=[];for(const name of ['resizeTo','resizeBy']){
      const native=w[name].bind(w);w[name]=(...args)=>{w.clampResizes.push({name,args,before:[w.outerWidth,w.outerHeight],active:w.navigator.userActivation.isActive});return native(...args);};}})()`);
    const collapsed=await read();assert.equal(collapsed.header.button.pressed,'false');
    await capture(mode+'-collapsed');
    const activate=async()=>{
      await evaluate('miniWatch.window.scrollTo(0,0)');await settle();
      const p=await evaluate(`(()=>{const r=miniWatch.view.earlierToggle.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
      for(const type of ['mousePressed','mouseReleased'])await command('Input.dispatchMouseEvent',{type,...p,button:'left',clickCount:1},pip);
      await settle();
    };
    await activate();const expanded=await read();
    assert.equal(expanded.expanded,true);assert.equal(expanded.header.button.pressed,'true');
    assert.equal(expanded.header.button.expanded,'true');assert.equal(expanded.header.parts[1].text,'Earlier Sessions');
    assert.equal(expanded.header.documentOverflow,false);
    assert.ok(expanded.header.parts.every(p=>p.lines.length && !p.overflow));
    await capture(mode+'-expanded');
    const first=await evaluate('miniWatch.window.clampResizes');assert.ok(first.length<=1);
    const reached=await evaluate(`(()=>{const v=miniWatch.view,w=miniWatch.window;return [v.historyBody.lastElementChild,v.body.lastElementChild,v.accounts.lastElementChild].map(n=>{
      n.scrollIntoView({block:'end'});const r=n.getBoundingClientRect();return {visible:r.top<w.innerHeight&&r.bottom>0,top:r.top,bottom:r.bottom,height:w.innerHeight};});})()`);
    assert.ok(reached.every(n=>n.visible),'document scrolling reaches Earlier, active rows and accounts');
    await evaluate(`(()=>{const p=structuredClone(miniWatch.publication);p.view.now_ms++;miniWatch.update(p);miniWatch.settings();})()`);
    await settle();const passive=await read();assert.equal(passive.expanded,true);
    assert.deepEqual(passive.outer,expanded.outer);assert.equal((await evaluate('miniWatch.window.clampResizes')).length,first.length);
    await activate();const compact=await read();assert.equal(compact.expanded,false);assert.equal(compact.header.button.pressed,'false');
    const requests=await evaluate('miniWatch.window.clampResizes');assert.ok(requests.length<=first.length+1);
    for(const r of requests){assert.equal(r.active,true);assert.ok(r.name==='resizeBy'?Math.abs(r.args[0])<=1:Math.abs(r.args[0]-r.before[0])<=1);}
    assert.equal(compact.header.documentOverflow,false);
    layouts.push({case:'high-scale-clamp',mode,collapsed,expanded,passive,compact,reached,requests});
    await close();
  }
  checks.push('Compounded zoom/DPR: both sizing modes, real trusted disclosure, collapsed/expanded screenshots, requested/achieved bounds, <=1 height-only native request per action, stable passive state, usable reflow and scrolling to history/active/accounts');
};
