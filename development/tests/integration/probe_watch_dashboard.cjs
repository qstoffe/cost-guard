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
      await until(`current.watch?.accounts.style.maxWidth`);
      const facts=await evaluate(`(()=>{
        const v=current.watch,b=miniWatch.button,r=n=>n.getBoundingClientRect(),cap=miniWatch.defaultContentWidth();
        return {same:b===dashboardToggle,controls:b.parentNode===dashboardControls,one:document.querySelectorAll('#mini-watch-toggle').length,
          attached:v.band.contains(b),first:v.root.firstElementChild===v.band,last:v.root.lastElementChild===v.accounts,
          width:r(v.accounts).width,cap,root:r(v.root).width,earlier:v.root.textContent.includes('Earlier Sessions'),
          overflow:document.documentElement.scrollWidth>innerWidth+1,
          right:Math.abs(r(v.band).right-r(dashboardControls).right)<2,
          noFullCards:v.accounts.querySelectorAll('.account-card').length===0};})()`);
      assert.equal(facts.same&&facts.controls&&facts.attached&&facts.first&&facts.last&&facts.noFullCards,true);
      assert.equal(facts.one,1);assert.equal(facts.earlier,false);assert.equal(facts.overflow,false);
      assert.ok(facts.width<=Math.min(facts.cap,facts.root)+1,JSON.stringify(facts));
      if(width===1366)assert.equal(facts.right,true);
    }
  }
  await command('Emulation.clearDeviceMetricsOverride',{},sessionId);
  await open();
  assert.equal(await evaluate(`current.watch.accounts.textContent===miniWatch.view.accounts.textContent`),true,
    'Watch and PiP share compact native subscription presentation');
  const before=await evaluate('miniWatch.defaultContentWidth()');
  await evaluate('miniWatch.window.resizeTo(900,700)',true);
  assert.equal(await evaluate('miniWatch.defaultContentWidth()'),before,'user PiP resize cannot change Watch cap');
  await close();
  checks.push('Watch desktop/mobile band, one surviving controller through route eviction, compact shared quota list/default width independent of resized PiP');
};
