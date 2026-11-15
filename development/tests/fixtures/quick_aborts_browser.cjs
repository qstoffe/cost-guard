// Canonical source → HTTP → shipped Sessions/detail → actual hover/focus/touch.
const assert = require('node:assert/strict');
module.exports = async ({evaluate,until,fixture,command,checks,layouts}) => {
  async function help(selector, mode) {
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await evaluate('document.activeElement?.blur()');
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0});
    await command('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,x:1,y:1});
    await command('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,x:1,y:1});
    await evaluate(`document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'center',inline:'center'})`);
    const point=await evaluate(`(()=>{const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2}})()`);
    if(mode==='focus') {
      await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
      await evaluate(`document.querySelector(${JSON.stringify(selector)}).focus()`);
    } else if(mode==='touch') {
      await command('Emulation.setTouchEmulationEnabled',{enabled:true});
      await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]});
      await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    } else await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point});
    try { await until("document.querySelector('#context-help')?.matches(':popover-open')"); }
    catch(error) { throw new Error(`${selector} ${mode}: ${error.message}`); }
    const result=await evaluate("document.querySelector('#context-help').textContent");
    if(mode==='touch') await command('Emulation.setTouchEmulationEnabled',{enabled:false});
    return result;
  }
  await fixture('quick-aborts');
  await evaluate("location.hash='#/sessions?period=all'");
  await until("current?.catalog?.body.rows.length===1 && current.catalog.body.rows[0].cells[2].textContent==='Claude Sonnet 5.5'");
  const catalogModel='.sessions-table tbody td:nth-child(3) span';
  assert.deepEqual(await evaluate("[...current.catalog.body.rows[0].cells].slice(4).map(c=>c.textContent)"),['2','0s','N/A']);
  assert.equal(await evaluate(`(()=>{const n=current.catalog.body.rows[0].cells[4].firstChild;return !n.classList.contains('help-value') &&
    !n.hasAttribute('tabindex') && !n.hasAttribute('aria-describedby')})()`),true);
  for(const mode of ['hover','focus','touch']) {
    const text=await help(catalogModel,mode);
    assert.match(text,/Claude Sonnet 5.5 · Low/);
    assert.match(text,/Selected model · no request usage recorded/);
    assert.doesNotMatch(text,/Session Models:|N\/A — N\/A|Main models used/);
  }
  const header=await help('.sessions-table thead th:nth-child(5) button','focus');
  assert.match(header,/Number of prompts/);
  await evaluate("document.activeElement?.blur();location.hash='#/sessions/root'");
  await until("current?.detail?.body.rows.length===2");
  for(const width of [1280,360]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
    for(const unit of ['credits','usd']) {
      await evaluate(`ReportView.setUnit('${unit}',current.detail.root)`);
      for(const index of [1,2]) for(const mode of ['hover','focus','touch']) {
        const text=await help(`.session-history-table tbody tr:nth-child(${index}) td:nth-child(2) span`,mode);
        assert.match(text,/Selected model · no request usage recorded/);
        assert.match(text,/Claude Sonnet 5.5 · Low/);
        assert.doesNotMatch(text,/Session Models:|N\/A — N\/A|Recorded selection|Catalog modelID|contribution proof/);
      }
      const cost=await help('.session-history-table tbody tr td:nth-child(4) span','focus');
      assert.match(cost,/No model usage recorded/);
      assert.doesNotMatch(cost,/N\/A — N\/A|Recorded selection/);
      layouts.push({width,unit,interactions:['hover','focus','touch'],surface:'two quick aborts'});
    }
  }
  await fixture('quick-aborts-unknown');
  await until("current.detail.body.rows[1].cells[1].textContent==='N/A'");
  assert.equal(await evaluate("current.detail.body.rows[0].cells[1].textContent"),'Claude Sonnet 5.5');
  await evaluate("document.activeElement?.blur();location.hash='#/sessions?period=all&sort=model&direction=1'");
  await until("current?.catalog?.data && current.catalog.body.rows[0].cells[2].textContent==='N/A'");
  checks.push('Two same-minute canonical cancellations through HTTP: own Model/Low, selection-only help in both units at 360/1280 using actual hover/focus/touch, zero duration rounding and unknown Ctx; latest unknown never borrows first model');
  checks.push('Prompts=2 is plain non-focusable text; genuine heading help remains; no cost parts produces truthful no-usage copy and no execution star');
};
