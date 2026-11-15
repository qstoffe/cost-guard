// Canonical synthetic identity/effort cases rendered by the shipped help/DOM lifecycle.
module.exports = async ({command,evaluate,until,cases,tab,checks}) => {
  const assert=require('node:assert/strict');
  const metrics=['hourly-rate','total-cost','subagent-cost','total-tokens','token-rate','working-time','average-cost'];
  const forbidden=/unverified|Catalog modelID|source-qualified|signature-|synthetic-scope|sampled calls|known categories|observed tokens|default \(/i;
  const escape=async()=>{
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'},tab);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'},tab);
  };
  for(const [name,labels] of [
    ['friendly-aliases',['Claude Sonnet 5.5']],['friendly-unknown',['Claude Sonnet']],
    ['friendly-releases',['Claude Sonnet 4.6','Claude Sonnet 5.5']]]) {
    const result=cases.find(c=>c.name===name).result;
    await evaluate(`current.result=${JSON.stringify(result)};current.period='all';current.stats.update(current);`);
    for(const metric of metrics) {
      const selector=`[data-metric="${metric}"] .ai-stat-model`;
      assert.deepEqual(await evaluate(`[...document.querySelectorAll('${selector}')].map(n=>n.textContent).sort()`),labels);
      await evaluate(`document.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true}));
        document.querySelector('${selector}').focus()`);
      await until(`!document.getElementById('context-help').hidden`);
      const copy=await evaluate(`document.getElementById('context-help').textContent`);
      assert.match(copy,/^claude-agent\/Claude Sonnet(?: [45]\.[56])?\n\nBy Effort:\n• /);
      assert.doesNotMatch(copy,forbidden);
      assert.equal((copy.match(/• Default/g)||[]).length,1);
      if(name==='friendly-aliases') assert.equal(copy.split('\n').length,5,'one Default and one High bullet');
      await evaluate(`window.__friendlyFocus=document.activeElement;current.stats.update(current)`);
      assert.equal(await evaluate(`document.activeElement===__friendlyFocus`),true);
      await evaluate(`ReportView.setUnit('usd',output)`);
      if(['hourly-rate','total-cost','subagent-cost','average-cost'].includes(metric))
        assert.match(await evaluate(`document.getElementById('context-help').textContent`),/— \$/);
      else assert.equal(await evaluate(`document.getElementById('context-help').textContent`),copy);
      await evaluate(`ReportView.setUnit('credits',output)`);
      assert.equal(await evaluate(`document.getElementById('context-help').textContent`),copy);
      await escape();
    }
  }
  // Every actual title owner exposes concise copy, including the single-sentence token joke.
  for(const metric of await evaluate(`[...document.querySelectorAll('.ai-stat')].map(n=>n.dataset.metric)`)) {
    await evaluate(`document.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true}));
      document.querySelector('[data-metric="${metric}"] h4 button').focus()`);
    await until(`!document.getElementById('context-help').hidden`);
    const copy=await evaluate(`document.getElementById('context-help').textContent`);
    assert.doesNotMatch(copy,forbidden);
    if(metric==='total-tokens') assert.equal(copy,'The robots have eaten the entire context buffet.');
    if(metric==='token-rate') { assert.ok(copy.length<218); assert.match(copy,/snacks\.\n\n/); }
    await escape();
  }
  // Real headless pointer hover and emulated touch on a model help owner.
  const selector='[data-metric="hourly-rate"] .ai-stat-model';
  await evaluate(`document.activeElement.blur();document.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));
    document.querySelector('${selector}').scrollIntoView({block:'center'})`);
  const point=await evaluate(`(() => {const r=document.querySelector('${selector}').getBoundingClientRect();
    return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},tab);
  await until(`!document.getElementById('context-help').hidden`);
  assert.match(await evaluate(`document.getElementById('context-help').textContent`),/By Effort:/);
  await escape();
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:1,y:1},tab);
  await command('Emulation.setTouchEmulationEnabled',{enabled:true},tab);
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]},tab);
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},tab);
  await until(`!document.getElementById('context-help').hidden`);
  assert.doesNotMatch(await evaluate(`document.getElementById('context-help').textContent`),forbidden);
  await escape(); await command('Emulation.setTouchEmulationEnabled',{enabled:false},tab);
  checks.push('all seven actual DOM/model help owners: aliases merged, releases separate, selected Default once, currency switching, no debug prose, retained focus, real hourly medal hover/emulated touch; all title help inspected');
};
