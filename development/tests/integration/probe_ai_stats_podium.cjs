// Standing contract: architecture/modules/reports.md, AI Stats best effort / never Unavailable.
module.exports = async ({command,evaluate,until,fixture,tab,checks}) => {
  const assert=require('node:assert/strict'), cases=await fixture('stats-evidence');
  const original=await evaluate(`current.result`), period=await evaluate(`current.period`);
  for(const [name,count] of [['empty',0],['complete',1],['podium-two',2],['podium-three',3]]) {
    const item=cases.find(c=>c.name===name);
    await evaluate(`current.result=${JSON.stringify(item.result)};current.period='all';current.stats.update(current);`);
    const rows=await evaluate(`[...document.querySelectorAll('[data-metric="token-rate"] .ai-stat-racer')].map(r=>({
      label:r.querySelector('.ai-stat-model').textContent,speed:r.querySelector('.ai-stat-speed').textContent,
      rank:r.getAttribute('aria-label'),medal:r.firstChild.textContent}))`);
    assert.equal(rows.length,count);
    if(count) {
      assert.deepEqual(rows.map(r=>r.medal),['🥇','🥈','🥉'].slice(0,count));
      assert.ok(rows.every(r=>!r.label.includes('/') && /tok\/s/.test(r.speed)));
    }
    if(count===3) assert.deepEqual(rows.map(r=>r.speed),['300 tok/s','200 tok/s','100 tok/s']);
    assert.equal(await evaluate(`document.querySelector('[data-metric="token-rate"] .ai-stat-value').textContent`),
      count ? `${count===3?200:count===2?250:100} tok/s` : 'No races yet. The podium is polished.');
    assert.equal(await evaluate(`document.querySelectorAll('[data-metric="token-rate"] .ai-stat-rate').length`),0);
    assert.equal(await evaluate(`document.querySelectorAll('.ai-stat-sample').length`),0);
    for(const metric of ['total-tokens','total-cost','working-time','average-cost']) {
      assert.equal(await evaluate(`document.querySelectorAll('[data-metric="${metric}"] .ai-stat-racer').length`),count,metric);
      assert.ok(await evaluate(`!!document.querySelector('[data-metric="${metric}"] .ai-stat-value').textContent`));
    }
    assert.doesNotMatch(await evaluate(`[...document.querySelectorAll('.ai-stat')].map(c=>c.textContent).join(' ')`),/Unavailable|N\/A/);
  }
  await evaluate(`document.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true}));
    window.__podiumHeading=document.querySelector('[data-metric="token-rate"] h4 button');__podiumHeading.focus();`);
  await until(`!document.getElementById('context-help').hidden`);
  assert.match(await evaluate(`document.getElementById('context-help').textContent`),/sprinters.*\n\n.*response time/);
  await evaluate(`window.__racer=document.querySelector('.ai-stat-racer');current.stats.update(current);`);
  assert.equal(await evaluate(`document.activeElement===__podiumHeading && __racer===document.querySelector('.ai-stat-racer')`),true);
  await evaluate(`window.__modelLabel=document.querySelector('[data-metric="token-rate"] .ai-stat-model');__modelLabel.focus();`);
  const helpEvidence=await evaluate(`(() => {
    const row=current.result.view.ai_stats.find(r=>r.period===current.period).metrics
      .find(m=>m.metric==='token-rate').podium[0];
    return {focused:document.activeElement===__modelLabel,visible:!document.getElementById('context-help').hidden,
      text:document.getElementById('context-help').textContent,prepared:row.model_help,
      display:ReportView.display(row,'model_help'),units:row.display_units};
  })()`);
  assert.equal(helpEvidence.text,helpEvidence.prepared,JSON.stringify(helpEvidence));
  await until(`document.getElementById('context-help').textContent.includes('synthetic/model-')`);
  assert.match(await evaluate(`document.getElementById('context-help').textContent`),/\n\nBy Effort:\n• Default — \d+ tok\/s$/);
  await evaluate(`current.stats.update(current);`);
  assert.equal(await evaluate(`document.activeElement===__modelLabel`),true);
  await evaluate(`ReportView.setUnit('usd',output)`);
  assert.ok(await evaluate(`[...document.querySelectorAll('[data-metric="total-cost"] .ai-stat-speed')].every(n=>n.textContent.startsWith('$'))`));
  await evaluate(`ReportView.setUnit('credits',output)`);
  for(const metric of ['total-cost','total-tokens','token-rate','working-time','average-cost']) {
    assert.equal(await evaluate(`(() => {const c=document.querySelector('[data-metric="${metric}"]');
      return [...c.querySelectorAll('.ai-stat-racer')].every(r=>{
        const model=r.querySelector('.ai-stat-model').getBoundingClientRect(),amount=r.querySelector('.ai-stat-speed').getBoundingClientRect();
        return Math.abs(model.top-amount.top)<2;
      });})()`),true,'one-line '+metric);
  }
  for(const width of [360,800]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},tab);
    assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth`),true);
  }
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'},tab);
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'},tab);
  await require('./probe_ai_stats_friendly.cjs')({command,evaluate,until,cases,tab,checks});
  await evaluate(`current.result=${JSON.stringify(original)};current.period=${JSON.stringify(period)};current.stats.update(current);`);
  checks.push('five shared canonical 0/1/2/3 medal lists, retained large totals, compact short names, no sample rows, units, model keyboard help and retained focus/nodes');
};
