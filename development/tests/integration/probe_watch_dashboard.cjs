// Shipped app route/layout lifecycle in a fresh hidden headless browser.
const assert=require('node:assert/strict');
module.exports=async({evaluate,until,command,sessionId,open,close,checks})=>{
  await evaluate(`window.dashboardToggle=miniWatch.button;window.dashboardControls=miniWatch.button.parentNode`);
  for(const width of [1366,360]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},sessionId);
    for(const route of ['watch','accounts','sessions','settings','watch','token-mix','ai-stats','models','watch']) {
      await evaluate(`location.hash='#/${route}'`);
      await until(`current?.section==='${route}'`);
      if(route!=='watch')continue;
      await until(`!!current.watch?.band`);
      const facts=await evaluate(`(()=>{
        const v=current.watch,b=miniWatch.button,r=n=>n.getBoundingClientRect();
        return {same:b===dashboardToggle,controls:b.parentNode===dashboardControls,one:document.querySelectorAll('#mini-watch-toggle').length,
          attached:v.band.contains(b),first:v.root.firstElementChild===v.band,accounts:v.accounts.parentNode===v.band,
          width:r(v.accounts).width,root:r(v.root).width,earlier:v.root.textContent.includes('Earlier Sessions'),
          daily:[...v.daily.children].map(n=>({top:r(n).top,bottom:r(n).bottom,center:r(n).x+r(n).width/2})),
          border:getComputedStyle(v.band).borderBottomWidth,
          overflow:document.documentElement.scrollWidth>innerWidth+1,
          right:Math.abs(r(v.band).right-r(dashboardControls).right)<2,
          noFullCards:v.accounts.querySelectorAll('.account-card').length===0};})()`);
      assert.equal(facts.same&&facts.controls&&facts.attached&&facts.first&&facts.accounts&&facts.noFullCards,true);
      assert.equal(facts.one,1);assert.equal(facts.earlier,false);assert.equal(facts.overflow,false);
       assert.ok(facts.width<=facts.root+1,JSON.stringify(facts));
       assert.equal(facts.border,'0px');
       assert.ok(facts.daily[0].bottom<=facts.daily[1].top&&facts.daily[1].bottom<=facts.daily[2].top);
       assert.ok(facts.daily.every(line=>Math.abs(line.center-facts.daily[0].center)<1));
      if(width===1366)assert.equal(facts.right,true);
    }
  }
  await command('Emulation.clearDeviceMetricsOverride',{},sessionId);
  await evaluate(`window.dashboardOriginal=structuredClone(liveValue);
    window.dashboardNodes=[...current.watch.daily.children];
    window.dashboardRows=[...current.watch.accounts.children];
    window.dashboardCards=[...current.watch.active.children];
    current.watch.accounts.focus();`);
  const refreshed=await evaluate(`(()=>{
    const view=current.watch,before=view.band.getBoundingClientRect(),streams=probeStreams;
    liveValue=structuredClone(liveValue);liveValue.view.daily_usage.prompt_count=123456;
    show(current);
    const after=view.band.getBoundingClientRect();
    return {daily:[...view.daily.children].every((node,index)=>node===dashboardNodes[index]),
      rows:[...view.accounts.children].every((node,index)=>node===dashboardRows[index]),
      cards:[...view.active.children].every((node,index)=>node===dashboardCards[index]),
      text:view.daily.lastElementChild.textContent,focus:document.activeElement===view.accounts,
      stable:Math.abs(before.height-after.height)<1,streams:streams===probeStreams};
  })()`);
  assert.ok(refreshed.daily&&refreshed.rows&&refreshed.cards&&refreshed.focus&&refreshed.stable&&refreshed.streams,
    JSON.stringify(refreshed));
  assert.equal(refreshed.text,'123456 prompts');
  await evaluate('liveValue=dashboardOriginal;show(current);miniWatch.button.focus()');
  assert.equal(await evaluate(`document.activeElement===miniWatch.button&&getComputedStyle(miniWatch.button).outlineStyle!=='none'`),true);
  // Real browser-owned touch activation, not shared OS input or a fake PiP window.
  const point=await evaluate(`(()=>{const r=miniWatch.button.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
  for(const type of ['touchStart','touchEnd'])await command('Input.dispatchTouchEvent',
    {type,touchPoints:type==='touchStart'?[{...point,id:1,radiusX:1,radiusY:1,force:1}]:[]},sessionId);
  await until(`!!miniWatch.view&&miniWatch.button.getAttribute('aria-pressed')==='true'`);
  const miniStyle=await evaluate(`(()=>{
    const bar=miniWatch.view.accounts.querySelector('progress'),style=miniWatch.window.getComputedStyle(bar);
    return {height:style.height,margin:style.marginLeft,band:!!miniWatch.view.doc.querySelector('.watch-daily-band')};
  })()`);
  assert.ok(parseFloat(miniStyle.height)>parseFloat(await evaluate(`getComputedStyle(current.watch.accounts.querySelector('progress')).height`)));
  assert.equal(miniStyle.margin,'0px');assert.equal(miniStyle.band,false);
  await close();
  await open();
  assert.equal(await evaluate(`current.watch.accounts.textContent===miniWatch.view.accounts.textContent`),true,
    'Watch and PiP share compact native subscription presentation');
  const before=await evaluate('miniWatch.defaultContentWidth()');
  await evaluate('miniWatch.window.resizeTo(900,700)',true);
  assert.equal(await evaluate('miniWatch.defaultContentWidth()'),before,'user PiP resize cannot change Watch cap');
  await close();
  checks.push('Watch desktop/mobile three-line divider-free header; live count preserves daily/account/card DOM, focus, height and one SSE; keyboard focus and browser touch PiP opening; Mini keeps its own bar geometry; one controller through route eviction and shared quota list independent of resized PiP');
};
