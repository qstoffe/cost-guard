// Rendered periods, stale browser attempts, shared spacing and percentage-value help.
const assert = require('node:assert/strict');
module.exports = async function probe({evaluate, until, command, tab, checks}) {
  // This offline host has no Sessions source. Mount the shipped controller for
  // geometry/defaults only; its HTTP unavailable state is not source validation.
  await evaluate(`sessionDetailAvailable=true`);
  const go = async section => {
    await evaluate(`location.hash='#/${section}'`);
    await until(`current.section==='${section}' && !current.loading`);
  };
  await go('token-mix');
  assert.equal(await evaluate(`current.period`),'all');
  assert.equal(await evaluate(`current.tokenMix.root.firstElementChild===current.tokenMix.selector`),true);
  for (const theme of ['classic','light','dark']) for (const width of [360,1280]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},tab);
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},tab);
    await evaluate(`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}'`);
    const positions=[];
    for (const section of ['sessions','ai-stats','token-mix']) {
      await go(section);
      positions.push(await evaluate(`(()=>{window.scrollTo(0,0);const r=document.querySelector('.ai-stats-periods').getBoundingClientRect();
        return {x:r.x,y:r.y,bottom:document.querySelector('header').getBoundingClientRect().bottom};})()`));
    }
    assert.ok(positions.every(p=>Math.abs(p.y-p.bottom-(positions[0].y-positions[0].bottom))<1),JSON.stringify(positions));
    assert.ok(positions.every(p=>p.x===positions[0].x),JSON.stringify(positions));
  }
  await evaluate(`globalThis.mixSort=JSON.stringify([current.tokenMix.models.sort,current.tokenMix.publishers.sort]);
    ReportView.setUnit('usd',current.tokenMix.root)`);
  for (const period of ['today','7-days','30-days','month','all']) {
    await evaluate(`current.tokenMix.buttons.find(b=>b.id==='${period}').button.click()`);
    assert.equal(await evaluate(`current.result===null && current.tokenMix.content.hidden`),true,'old scope hidden immediately');
    await until(`!current.loading && current.result?.view.token_mix_period?.period==='${period}'`);
    assert.equal(await evaluate(`current.tokenMix.selector.querySelector('[aria-pressed="true"]').textContent`),
      {today:'Today','7-days':'7 days','30-days':'30 days',month:'This month',all:'All time'}[period]);
    assert.equal(await evaluate(`JSON.stringify([current.tokenMix.models.sort,current.tokenMix.publishers.sort])===mixSort`),true);
    assert.match(await evaluate(`ReportView.display(current.result.view.token_mix,'mix_input_cost_help')`),/USD/,'period does not change the unit');
  }
  // Supersede a slow in-flight scope; its eventual completion must never win.
  await evaluate(`selectTokenMix(current,'today');selectTokenMix(current,'month')`);
  await until(`!current.loading && current.result?.view.token_mix_period?.period==='month'`);
  assert.equal(await evaluate(`current.period`),'month');
  await evaluate(`selectTokenMix(current,'all')`);
  await until(`!current.loading && current.result?.view.token_mix_period?.period==='all'`);
  const help=`document.getElementById('context-help')`;
  for (const unit of ['usd','credits']) for (const table of [0,1]) for (let col=4;col<8;col++) {
    await evaluate(`ReportView.setUnit('${unit}',current.tokenMix.root);document.activeElement?.blur();
      document.querySelectorAll('.token-mix-table')[${table}].tBodies[0].rows[0].cells[${col}].firstElementChild.focus()`);
    await until(`${help}?.matches(':popover-open')`);
    assert.match(await evaluate(`${help}.textContent`),new RegExp(`${['Input','Cached input','Cache write','Output'][col-4]} CCost: .*${unit==='usd'?'USD':'Credits'}`));
    assert.equal(await evaluate(`document.querySelectorAll('.token-mix-table [title]').length`),0);
  }
  for (const name of ['63','64']) {
    await evaluate(`document.activeElement?.blur();[...document.querySelectorAll('.token-mix-table')[0].tBodies[0].rows]
      .find(row=>row.cells[0].textContent.includes('model ${name}')).cells[4].firstElementChild.focus()`);
    await until(`${help}?.matches(':popover-open')`);
    assert.match(await evaluate(`${help}.textContent`),/Partial reference valuation.*not zero/);
    if (name==='63') assert.match(await evaluate(`${help}.textContent`),/N\/A/);
  }
  await evaluate(`document.activeElement?.blur();globalThis.categoryTarget=document.querySelector('.token-mix-table tbody tr').cells[4].firstElementChild;
    categoryTarget.scrollIntoView({block:'center',inline:'center'})`);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape'},tab);
  const point=await evaluate(`(()=>{const r=categoryTarget.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},tab);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},tab);
  await until(`${help}?.matches(':popover-open')`);
  assert.match(await evaluate(`${help}.textContent`),/Input CCost/);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},tab);
  await until(`!${help}.matches(':popover-open')`);
  await command('Emulation.setTouchEmulationEnabled',{enabled:true},tab);
  for (const type of ['touchStart','touchEnd']) await command('Input.dispatchTouchEvent',{
    type,touchPoints:type==='touchStart'?[{...point,id:1,radiusX:1,radiusY:1,force:1}]:[]},tab);
  await until(`${help}.matches(':popover-open')`);
  assert.match(await evaluate(`${help}.textContent`),/Input CCost/);
  await command('Emulation.setTouchEmulationEnabled',{enabled:false},tab);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape'},tab);
  await evaluate(`document.activeElement?.blur();current.tokenMix.models.headers[0].th.querySelector('button').focus()`);
  assert.equal(await evaluate(`current.tokenMix.models.headers[0].th.querySelector('.help-label')`),null);
  await evaluate(`current.tokenMix.models.headers[1].th.querySelector('button').focus()`);
  await until(`${help}?.matches(':popover-open')`);
  assert.doesNotMatch(await evaluate(`${help}.textContent`),/Activate to sort/);
  await go('ai-stats'); assert.equal(await evaluate(`current.period`),'30-days');
  await go('sessions'); assert.equal(await evaluate(`current.catalog.period`),'today');
  await evaluate(`location.hash='#/token-mix?period=7-days'`);
  await until(`current.section==='token-mix' && !current.loading && current.result?.view.token_mix_period?.period==='7-days'`);
  checks.push('five Token Mix scopes/deep link; stale attempts rejected; sort/unit/page defaults retained; 16 focused category help values plus real hover/touch and missing/partial help; compact three-page geometry in themes/mobile');
};
