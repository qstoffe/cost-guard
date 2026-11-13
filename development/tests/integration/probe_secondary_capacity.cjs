// Server-prepared partial secondary/later estimates through real HTTP/SSE and shared cards.
const assert=require('node:assert/strict');
module.exports=async({command,evaluate,fixture,until,navigate,sessionId,checks})=>{
  await fixture('secondary-capacity-partial');
  await until(`document.querySelectorAll('#result .watch-subscription').length===1`);
  const quotas=`[liveValue.view.accounts.accounts[0].primary.quota,...liveValue.view.accounts.accounts[0].secondary.map(s=>s.quota)]`;
  for(const route of ['accounts','watch']) {
    await navigate(route);
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},sessionId);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},sessionId);
    await evaluate(`window.capacityCard=document.querySelector('#result .watch-subscription');
      window.capacityBars=[...capacityCard.querySelectorAll('progress')];
      window.capacityRows=[...capacityCard.querySelectorAll('.watch-quota-capacity,.watch-monthly-capacity')];`);
    for(const unit of ['credits','usd'])for(const mode of ['used','remaining']) {
      await evaluate(`ReportView.setUnit('${unit}');ReportView.setQuotaMode('${mode}');ReportView.syncUnits(capacityCard)`);
      const observed=await evaluate(`(()=>{const qs=${quotas};return {
        reference:qs.map(q=>q.ccost_reference),display:qs.map(q=>q.display_units['${unit}']),
        lines:capacityRows.map(row=>row.textContent),
        stable:capacityCard===document.querySelector('#result .watch-subscription')&&capacityBars.every((bar,i)=>bar===capacityCard.querySelectorAll('progress')[i])};})()`);
      assert.equal(observed.stable,true);
      assert.deepEqual(observed.reference.map(q=>q.capacity),['1.00E+3','14571.42857142857142857142857','8E+1']);
      assert.equal(observed.reference[1].monthly_capacity,'62448.97959183673469387755101');
      for(let i=0;i<3;i++) {
        assert.ok(observed.lines[2*i].endsWith(observed.display[i].ccost_capacity),JSON.stringify({route,unit,mode,lines:observed.lines,expected:observed.display[i].ccost_capacity}));
        assert.ok(observed.lines[2*i+1].endsWith(observed.display[i].monthly_capacity));
      }
      await evaluate(`capacityRows[2].querySelector('span').focus()`);
      await until(`document.getElementById('context-help').textContent.includes('1020 ÷ 0.07')`);
      assert.match(await evaluate(`document.getElementById('context-help').textContent`),/1020 ÷ 0\.07 = 14571\.42857142857142857142857 Credits[\s\S]*unpriced usage may make this low/);
      assert.doesNotMatch(await evaluate(`document.getElementById('context-help').textContent`),/Native Used|Native Remaining/);
      await evaluate(`capacityRows[3].querySelector('span').focus()`);
      await until(`document.getElementById('context-help').textContent.includes('30 days ÷ 604800 seconds')`);
      assert.match(await evaluate(`document.getElementById('context-help').textContent`),/^Monthly Capacity: ~/);
    }
    await evaluate(`capacityRows[2].querySelector('span').focus()`);
    await fixture('secondary-capacity-complete');
    await until(`(${quotas})[1].period_ccost.cost.complete`);
    await until(`document.getElementById('context-help').textContent.includes('1020 ÷ 0.07')&&!document.getElementById('context-help').textContent.includes('unpriced')`);
    assert.doesNotMatch(await evaluate(`document.getElementById('context-help').textContent`),/unpriced/);
    await fixture('secondary-capacity-raw');
    await until(`(${quotas})[1].remaining_fraction==='0.9301'`);
    await until(`document.getElementById('context-help').textContent.includes('1020 ÷ 0.0699')`);
    assert.match(await evaluate(`document.getElementById('context-help').textContent`),/1020 ÷ 0\.0699/);
    await fixture('secondary-capacity-history');
    await until(`(${quotas})[1].ccost_reference.capacity===null`);
    await until(`document.getElementById('context-help').textContent.includes('waiting for complete period history')`);
    assert.match(await evaluate(`capacityRows[2].textContent`),/Weekly Capacity: \?$/);
    assert.match(await evaluate(`document.getElementById('context-help').textContent`),/waiting for complete period history/);
    assert.equal(await evaluate(`document.activeElement===capacityRows[2].querySelector('span')`),true);
    await fixture('secondary-capacity-reset');
    await until(`(${quotas})[1].remaining_fraction==='1'`);
    await until(`document.getElementById('context-help').textContent.includes('matching quota window')`);
    assert.match(await evaluate(`document.getElementById('context-help').textContent`),/matching quota window/);
    await fixture('secondary-capacity-partial');
    await until(`(${quotas})[1].ccost_reference.capacity!==null`);
    // Trusted hidden-browser hover and touch, no shared OS input or visible window.
    const box=await evaluate(`(()=>{const r=capacityRows[2].querySelector('span').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
    await evaluate(`document.activeElement.blur()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...box},sessionId);
    await until(`!document.getElementById('context-help').hidden&&document.getElementById('context-help').textContent.includes('unpriced usage')`);
    await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[box]},sessionId);
    await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},sessionId);
    assert.match(await evaluate(`document.getElementById('context-help').textContent`),/Estimate from priced requests/);
  }
  checks.push('Accounts/Full Watch: independent primary/secondary/later raw Capacity and 30-day estimates; partial→complete, raw fraction, missing history/reset, Credits/USD × Used/Remaining, retained rows/focus, hidden hover/touch');
};
