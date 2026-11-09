// Intrinsic Models value help, effort input and the real authenticated manual lane.
const assert = require('node:assert/strict');

async function probeModelsValues({command, evaluate, until, id, fixture}) {
  const checks = [];
  const key = async (key, code, windowsVirtualKeyCode) => {
    await command('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode,
      ...(key==='Enter'?{text:'\r'}:key===' '?{text:' '}:{})},id);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode},id);
  };
  const point = selector => evaluate(id,`(()=>{const n=document.querySelector(${JSON.stringify(selector)});n.scrollIntoView({block:'center'});const r=n.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
  const click = async selector => {
    const p = await point(selector);
    await command('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...p},id);
    await command('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...p},id);
  };
  const show = async selector => {
    await evaluate(id,`document.activeElement?.blur()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:1,y:1},id);
    await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).focus()`);
    await until(id,`document.querySelector('#context-help')?.matches(':popover-open')`);
    return evaluate(id,`document.querySelector('#context-help').textContent`);
  };
  const referenceValue = '.overview-model-table tbody tr:first-child .model-relative';
  const referenceHelp = await show(referenceValue);
  assert.match(referenceHelp,/^GitHub Copilot · USD \/ 1M tokens\nInput \$1 · Cached input \$0.1\nCache write N\/A · Output \$4\n\nToken Mix · \d+ completed priced prompts\nInput .*Cached input .*\nCache write .*Output /);
  assert.equal(await evaluate(id,`[...document.querySelectorAll('.overview-model-table .model-relative')].every(n=>n.tabIndex===0 && n.parentElement!==n && !n.parentElement.hasAttribute('tabindex'))`),true);
  const modelHelp = await show('.benchmark-table tbody tr:first-child td:nth-child(2) span');
  assert.match(modelHelp,/^Coding Client: (Claude Code|Other client)\nClient version:/);
  const taskHelp = await show('.benchmark-table tbody tr:first-child td:nth-child(4) span');
  assert.match(taskHelp,/Terminal-Bench 4.0 · Harbor Hub\nUSD\/Task: \$\d+ per attempted task \(failures included\)/);
  await evaluate(id,`(()=>{const n=document.querySelector('#context-help'),r=document.createRange();r.selectNodeContents(n);getSelection().removeAllRanges();getSelection().addRange(r);})()`);
  assert.equal(await evaluate(id,`getSelection().toString()`),taskHelp,'help remains selectable without clipboard use');
  await evaluate(id,`getSelection().removeAllRanges();document.activeElement.blur()`);
  await key('Escape','Escape',27);
  const refChoice = await evaluate(id,`JSON.stringify(current.models)`);
  const starting = await fixture('benchmark-status'); assert.equal(starting.fetches,0);
  await evaluate(id,`document.querySelector('.effort-picker summary').scrollIntoView({block:'center'});document.querySelector('.effort-picker summary').focus()`);
  await key('Enter','Enter',13);
  assert.equal(await evaluate(id,`current.benchmark.picker.open`),true);
  await evaluate(id,`current.benchmark.options.querySelector('input').focus()`);
  await key(' ','Space',32);
  assert.equal(await evaluate(id,`current.benchmark.choice.efforts.size`),2);
  await key('Escape','Escape',27);
  assert.equal(await evaluate(id,`!current.benchmark.picker.open && document.activeElement===current.benchmark.summary`),true);
  await click('.effort-picker summary');
  await evaluate(id,`current.benchmark.effortInputs.forEach(([,input])=>{if(input.checked)input.click();})`);
  assert.equal(await evaluate(id,`current.benchmark.body.rows.length===0 && current.benchmark.empty.textContent==='No matching benchmark rows'`),true);
  await evaluate(id,`current.benchmark.effortInputs.find(([key])=>key==='high')[1].click()`);
  assert.equal(await evaluate(id,`current.benchmark.body.rows.length===1 && current.benchmark.body.rows[0].cells[2].textContent==='high'`),true);
  await click('.benchmark-section h2');
  assert.equal(await evaluate(id,`current.benchmark.picker.open`),false);
  assert.equal(await evaluate(id,`JSON.stringify(current.models)`),refChoice);
  assert.equal((await fixture('benchmark-status')).fetches,0);
  checks.push('Keyboard dropdown/Space/Escape/outside dismiss, zero and High-only selection remain local and independent');
  // Touch opens only the selected row value, not a cell-wide or row-wide surface.
  await command('Emulation.setTouchEmulationEnabled',{enabled:true},id);
  const p = await point('.benchmark-table tbody tr:first-child td:nth-child(4) span');
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{...p,radiusX:1,radiusY:1}]},id);
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},id);
  await until(id,`document.querySelector('#context-help')?.matches(':popover-open') && document.querySelector('#context-help').textContent.includes('per attempted task')`);
  await key('Escape','Escape',27);
  await command('Emulation.setTouchEmulationEnabled',{enabled:false},id);
  checks.push('Per-row coding client and source USD/attempt help supports focus, touch, selection and Escape');
  const old = await evaluate(id,`({date:current.benchmark.data.fetched_at_ms,rows:JSON.stringify(current.benchmark.data.rows)})`);
  await fixture('benchmark-hold');
  await click('[data-benchmark-control="refresh"]');
  await until(id,`current.benchmark.data.refreshing && current.benchmark.refresh.disabled`);
  await evaluate(id,`Promise.all([api('/api/models/benchmark/refresh',{}),api('/api/models/benchmark/refresh',{})])`);
  assert.equal((await fixture('benchmark-status')).fetches,1);
  await fixture('benchmark-offline');await fixture('benchmark-release');
  await until(id,`!current.benchmark.data.refreshing && !current.benchmark.refresh.disabled && current.benchmark.data.unavailable`);
  assert.deepEqual(await evaluate(id,`({date:current.benchmark.data.fetched_at_ms,rows:JSON.stringify(current.benchmark.data.rows)})`),old);
  assert.equal(await evaluate(id,`current.benchmark.status.textContent.includes('failed')`),true);
  await fixture('benchmark-online');await click('[data-benchmark-control="refresh"]');
  await until(id,`!current.benchmark.data.refreshing && !current.benchmark.data.unavailable && current.benchmark.data.fetched_at_ms>${old.date}`);
  assert.equal((await fixture('benchmark-status')).fetches,2);
  assert.equal((await fixture('models-status')).fetches,1,'benchmark failures/refresh never touch reference pricing');
  assert.equal(await evaluate(id,`current.benchmark.body.rows.length===1 && current.benchmark.choice.efforts.has('high')`),true);
  checks.push('Fresh-cache manual POST coalesces, retains last-good rows/date after failure, recovers with a new retrieval independently of prices');
  return checks;
}
module.exports = {probeModelsValues};
