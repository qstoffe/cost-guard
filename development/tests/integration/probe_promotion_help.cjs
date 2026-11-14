// Native hidden-browser input against the canonical promoted Models fixture.
const assert = require('node:assert/strict');
module.exports = async ({command,run,ready,owner,checks,layouts}) => {
  await run(`location.hash='#/models'`);await ready(`current.section==='models' && !current.loading`);
  await run(`current.result={view:liveValue.probe_models,source:{status:'acquired'}};
    current.models={all:false,latest:false,sorts:[{index:2,direction:-1}]};show(current)`);
  const selector='.model-relative.promotion';
  await ready(`!!output.querySelector('${selector}')`);
  const expected='GitHub Copilot · USD / 1M tokens\nBase context tier:\nInput $8 · Cached input $8\nCache write $8 · Output $8\n' +
    'Input context >200000 tokens:\nInput $16 · Cached input $16\nCache write $16 · Output $16\n' +
    'Input context ≥1000000 tokens:\nInput $32 · Cached input $32\nCache write $32 · Output $32\n' +
    'Price Promotion\nGPT-5.1\n50% off standard GitHub Copilot rates\nPromotion ends: 2026-11-10\nStandard prices resume: 2026-11-11\n\n' +
    'Token Mix · 1 completed priced prompts\nInput 20% · Cached input 60%\nCache write 10% · Output 10%';
  const opened=async()=>{
    await ready(`document.querySelector('#context-help')?.matches(':popover-open')`);
    assert.equal(await run(`document.querySelector('#context-help').textContent`),expected);
    assert.equal(await run(`output.querySelector('${selector}').hasAttribute('title')`),false);
  };
  const escape=async()=>{
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},owner);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},owner);
    assert.equal(await run(`document.querySelector('#context-help').hidden`),true);
  };
  for(const theme of ['classic','light','dark'])for(const width of [360,1366,1920]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},owner);
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},owner);
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},owner);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},owner);
    await run(`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}';
      output.querySelector('${selector}').scrollIntoView({block:'center',inline:'center'});
      output.querySelector('${selector}').focus()`);
    await opened();
    const layout=await run(`(()=>{const n=output.querySelector('${selector}'),p=document.querySelector('#context-help'),r=p.getBoundingClientRect();
      return {text:n.textContent,whiteSpace:getComputedStyle(p).whiteSpace,color:getComputedStyle(n).color,
        bounded:r.left>=0&&r.top>=0&&r.right<=innerWidth&&r.bottom<=innerHeight};})()`);
    assert.match(layout.text,/8\.0x → 16\.0x \(>200K\) → 32\.0x \(≥1M\) \*$/);
    assert.equal(layout.whiteSpace,'pre-line');assert.equal(layout.bounded,true);await escape();
    await run(`document.activeElement.blur()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},owner);
    const point=await run(`(()=>{const r=output.querySelector('${selector}').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},owner);await opened();await escape();
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},owner);
    await command('Emulation.setTouchEmulationEnabled',{enabled:true},owner);
    const touch=await run(`(()=>{const n=output.querySelector('${selector}');n.scrollIntoView({block:'center',inline:'center'});
      const r=n.getBoundingClientRect(),x=Math.max(2,Math.min(innerWidth-2,r.left+r.width/2)),y=r.top+r.height/2;
      if(!n.contains(document.elementFromPoint(x,y)))throw Error('promotion touch point not on trigger');return {x,y};})()`);
    await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch]},owner);
    await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},owner);await opened();
    await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:2,y:2}]},owner);
    await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},owner);
    assert.equal(await run(`document.querySelector('#context-help').hidden`),true);
    await command('Emulation.setTouchEmulationEnabled',{enabled:false},owner);
    await run(`document.activeElement?.blur()`);layouts.push({route:'promotion-help',theme,width,...layout});
  }
  checks.push('Canonical promotion: exact multiline model/discount/dates, one postfix after tiers, focus/hover/Escape/touch/outside-dismiss and bounded help in nine theme/width cases');
};
