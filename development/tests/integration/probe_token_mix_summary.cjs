// Summary percentages alone own concise, current prepared CCost help.
const assert = require('node:assert/strict');
module.exports = async function probe({evaluate, until, command, tab, checks}) {
  const help = `document.getElementById('context-help')`;
  await evaluate(`document.activeElement?.blur();globalThis.summaryOriginal=current.result`);
  const expected = ['0 Credits', '1 Credits', '123 Credits', '0 Credits'];
  await evaluate(`(()=>{
    const value=structuredClone(summaryOriginal), mix=value.view.token_mix;
    // Prepared server values deliberately differ from any percentage-times-total guess.
    for(const [index,key] of ['input','cache','write','output'].entries()) {
      mix.display_units.credits['mix_'+key+'_cost_value']=${JSON.stringify(expected)}[index];
      mix.display_units.usd['mix_'+key+'_cost_value']=['$0.00','$0.01','$1.23','$0.00'][index];
    }
    current.tokenMix.update(value);
  })()`);
  for (const unit of ['credits', 'usd']) for (let index=0;index<4;index++) {
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab'},tab);
    await evaluate(`ReportView.setUnit('${unit}',current.tokenMix.root);
      document.activeElement?.blur();current.tokenMix.metrics[${index}].focus()`);
    await until(`${help}?.matches(':popover-open')`);
    assert.equal(await evaluate(`${help}.textContent`),
      unit==='credits'?expected[index]:['$0.00','$0.01','$1.23','$0.00'][index]);
    assert.equal(await evaluate(`current.tokenMix.metrics.every(value=>/^\\d+(?:\\.\\d)?%$/.test(value.textContent))`),true);
    assert.equal(await evaluate(`current.tokenMix.summary.querySelectorAll('.help-value').length`),4);
    assert.equal(await evaluate(`current.tokenMix.summary.querySelectorAll('div > span:is(.help-value,[tabindex],[title])').length`),0);
  }
  // An already-open summary tooltip updates both on unit changes and new snapshots.
  await evaluate(`ReportView.setUnit('credits',current.tokenMix.root)`);
  assert.equal(await evaluate(`${help}.textContent`),'0 Credits');
  await evaluate(`(()=>{
    const value=structuredClone(summaryOriginal);
    value.view.token_mix.display_units.credits.mix_output_cost_value='456 Credits';
    value.view.token_mix_period={period:'today',start_ms:100,end_ms:200};
    current.tokenMix.update(value);
  })()`);
  assert.equal(await evaluate(`${help}.textContent`),'456 Credits');
  for (const period of ['today','7-days','30-days','month','all']) {
    await evaluate(`document.activeElement?.blur();selectTokenMix(current,'${period}')`);
    await until(`!current.loading && current.result?.view.token_mix_period?.period==='${period}'`);
    for (let index=0;index<4;index++) {
      await evaluate(`document.activeElement?.blur();current.tokenMix.metrics[${index}].focus()`);
      await until(`${help}?.matches(':popover-open')`);
      const key=['input','cache','write','output'][index];
      assert.equal(await evaluate(`${help}.textContent`),
        await evaluate(`current.result.view.token_mix.display_units.credits.mix_${key}_cost_value`));
    }
  }
  await evaluate(`document.activeElement?.blur();current.tokenMix.metrics[0].scrollIntoView({block:'center'})`);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape'},tab);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},tab);
  const point=await evaluate(`(()=>{const r=current.tokenMix.metrics[0].getBoundingClientRect();
    return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},tab);
  await until(`${help}?.matches(':popover-open')`);
  const amount=await evaluate(`current.result.view.token_mix.display_units.credits.mix_input_cost_value`);
  assert.equal(await evaluate(`${help}.textContent`),amount);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},tab);
  await until(`!${help}.matches(':popover-open')`);
  await command('Emulation.setTouchEmulationEnabled',{enabled:true},tab);
  for(const type of ['touchStart','touchEnd']) await command('Input.dispatchTouchEvent',{
    type,touchPoints:type==='touchStart'?[{...point,id:1,radiusX:1,radiusY:1,force:1}]:[]},tab);
  await until(`${help}.matches(':popover-open')`);
  assert.equal(await evaluate(`${help}.textContent`),amount);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape'},tab);
  await command('Emulation.setTouchEmulationEnabled',{enabled:false},tab);
  checks.push('summary: percentages only, help-free labels, four focused costs in both units including zero, open-help unit/snapshot refresh, five periods, actual headless hover/touch');
};
