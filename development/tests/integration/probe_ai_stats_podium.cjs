// Standing contract: architecture/modules/reports.md, AI Stats best effort / never Unavailable.
module.exports = async ({command,evaluate,until,fixture,tab,checks}) => {
  const assert=require('node:assert/strict'), cases=await fixture('stats-evidence');
  const original=await evaluate(`current.result`), period=await evaluate(`current.period`);
  for(const [name,count] of [['empty',0],['complete',1],['podium-two',2],['podium-three',3]]) {
    const item=cases.find(c=>c.name===name);
    await evaluate(`current.result=${JSON.stringify(item.result)};current.period='all';current.stats.update(current);`);
    const rows=await evaluate(`[...document.querySelectorAll('[data-metric="token-rate"] .ai-stat-racer')].map(r=>({
      label:r.querySelector('.ai-stat-model').textContent,speed:r.querySelector('.ai-stat-speed').textContent,
      sample:r.querySelector('.ai-stat-sample').textContent,rank:r.getAttribute('aria-label'),medal:r.firstChild.textContent}))`);
    assert.equal(rows.length,count);
    if(count) {
      assert.deepEqual(rows.map(r=>r.medal),['🥇','🥈','🥉'].slice(0,count));
      assert.ok(rows.every(r=>r.sample==='1 sampled call' && /tok\/s/.test(r.speed)));
    }
    if(count===3) assert.deepEqual(rows.map(r=>r.speed),['300 tok/s','200 tok/s','100 tok/s']);
    assert.equal(await evaluate(`document.querySelectorAll('[data-metric="token-rate"] .ai-stat-rate').length`),0);
    assert.doesNotMatch(await evaluate(`[...document.querySelectorAll('.ai-stat')].map(c=>c.textContent).join(' ')`),/Unavailable|N\/A/);
  }
  await evaluate(`document.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true}));
    window.__podiumHeading=document.querySelector('[data-metric="token-rate"] h4 button');__podiumHeading.focus();`);
  await until(`!document.getElementById('context-help').hidden`);
  assert.match(await evaluate(`document.getElementById('context-help').textContent`),/round trip.*network.*first token/);
  await evaluate(`window.__racer=document.querySelector('.ai-stat-racer');current.stats.update(current);`);
  assert.equal(await evaluate(`document.activeElement===__podiumHeading && __racer===document.querySelector('.ai-stat-racer')`),true);
  for(const width of [360,800]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},tab);
    assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth`),true);
  }
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'},tab);
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'},tab);
  await evaluate(`current.result=${JSON.stringify(original)};current.period=${JSON.stringify(period)};current.stats.update(current);`);
  checks.push('canonical 0/1/2/3 medal rows, weighted prepared speeds, sampled count, no hourly token rows, best-effort all-card policy, responsive podium and retained focus/help');
};
