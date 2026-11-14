// Native hidden-browser input against the canonical promoted Models fixture.
const assert = require('node:assert/strict');
module.exports = async ({command,run,ready,owner,checks,layouts,trace=false,isolate=false,stableTouch=false,input='mixed'}) => {
  await run(`location.hash='#/models'`);await ready(`current.section==='models' && !current.loading`);
  await run(`current.result={view:liveValue.probe_models,source:{status:'acquired',observed_at_ms:Date.now()}};
    window.promotionDismiss=document.createElement('div');promotionDismiss.setAttribute('aria-hidden','true');
    promotionDismiss.style.cssText='position:fixed;left:0;top:0;width:12px;height:12px;z-index:2147483647';
    document.body.append(promotionDismiss);
    current.models={all:false,latest:false,sorts:[{index:2,direction:-1}]};show(current)`);
  try {
  const selector='.model-relative.promotion';
  await ready(`!!output.querySelector('${selector}')`);
  await run(`window.promotionTarget=output.querySelector('${selector}')`);
  if(trace)await run(`(()=>{
    const target=output.querySelector('${selector}'),matches=target.matches;
    const descriptor=Object.getOwnPropertyDescriptor(target,'matches'),events=[];let arrival;
    const record=(kind,details={})=>{
      const hover=details.query===':hover'?details.result:matches.call(target,':hover');
      const panel=document.querySelector('#context-help'),r=target.getBoundingClientRect();
      events.push({at:performance.now(),stage:window.promotionStage,kind,...details,
        same:output.querySelector('${selector}')===target,connected:target.isConnected,
        focus:document.hasFocus(),active:document.activeElement===target,
        hover,hidden:panel?.hidden,open:panel?.matches(':popover-open'),
        bounds:{left:r.left,top:r.top,width:r.width,height:r.height},scroll:{x:scrollX,y:scrollY},
        viewport:{width:innerWidth,height:innerHeight,x:visualViewport.offsetLeft,y:visualViewport.offsetTop},
        arrival,hit:arrival?target.contains(document.elementFromPoint(arrival.x,arrival.y)):null});
    };
    target.matches=function(query){const result=matches.call(this,query);
      record('matches',{query,result,stack:new Error().stack});return result;};
    const types=['pointerenter','pointerleave','pointermove','pointerout','pointerdown','focus','blur','keydown'];
    const event=event=>{
      if(event.type==='pointermove'&&event.pointerType==='mouse'&&target.contains(event.target))
        arrival={x:event.clientX,y:event.clientY};
      record(event.type,{trusted:event.isTrusted,pointer:event.pointerType,key:event.key,
        target:event.target===target?'trigger':event.target?.nodeName,x:event.clientX,y:event.clientY});
    };
    for(const type of types)document.addEventListener(type,event,true);
    window.addEventListener('blur',event,true);window.addEventListener('focus',event,true);
    window.promotionTrace={events,restore(){
      for(const type of types)document.removeEventListener(type,event,true);
      window.removeEventListener('blur',event,true);window.removeEventListener('focus',event,true);
      if(descriptor)Object.defineProperty(target,'matches',descriptor);else delete target.matches;
    }};
  })()`);
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
  const cases=isolate?[0,1,2].map(phase=>({theme:'classic',width:1920,phase})):
    ['classic','light','dark'].flatMap(theme=>[360,1366,1920].map(width=>({theme,width})));
  const failures=[];
  if(stableTouch)await command('Emulation.setTouchEmulationEnabled',{enabled:true},owner);
  for(const {theme,width,phase} of cases) {
    if(trace)await run(`window.promotionStage=${JSON.stringify(`${theme}:${width}:${phase??'matrix'}`)}`);
    if(!isolate||phase===0)await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},owner);
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},owner);
    assert.equal(await run(`output.querySelector('${selector}')===promotionTarget && promotionTarget.isConnected`),true);
    const readLayout=async()=>{
      const layout=await run(`(()=>{const n=output.querySelector('${selector}'),p=document.querySelector('#context-help'),r=p.getBoundingClientRect();
        return {text:n.textContent,whiteSpace:getComputedStyle(p).whiteSpace,color:getComputedStyle(n).color,
          bounded:r.left>=0&&r.top>=0&&r.right<=innerWidth&&r.bottom<=innerHeight};})()`);
      assert.match(layout.text,/8\.0x → 16\.0x \(>200K\) → 32\.0x \(≥1M\) \*$/);
      assert.equal(layout.whiteSpace,'pre-line');assert.equal(layout.bounded,true);return layout;
    };
    let layout;
    if(input!=='touch') {
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},owner);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},owner);
    await run(`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}';
      output.querySelector('${selector}').scrollIntoView({block:'center',inline:'center'});
      output.querySelector('${selector}').focus()`);
    await opened();
    layout=await readLayout();await escape();
    await run(`document.activeElement.blur()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},owner);
    const point=await run(`(()=>{const n=output.querySelector('${selector}');n.scrollIntoView({block:'center',inline:'center'});
      const r=n.getBoundingClientRect(),x=Math.max(2,Math.min(innerWidth-2,r.left+r.width/2)),
        y=Math.max(2,Math.min(innerHeight-2,r.top+r.height/2));
      if(!n.contains(document.elementFromPoint(x,y)))throw Error('promotion hover point not on trigger');
      return {x,y};})()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},owner);
    try {await opened();await escape();}
    catch(error){if(!isolate)throw error;failures.push({phase,reason:error.message});}
    if(isolate&&phase!==1) {
      layouts.push({route:'promotion-isolation',phase,hover:!failures.some(f=>f.phase===phase),...layout});
      continue;
    }
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},owner);
    if(input==='mouse') {
      layouts.push({route:'promotion-help',input,theme,width,...layout});continue;
    }
    }
    if(input==='touch')await run(`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}'`);
    if(!stableTouch)await command('Emulation.setTouchEmulationEnabled',{enabled:true},owner);
    const touch=await run(`(()=>{const n=output.querySelector('${selector}');n.scrollIntoView({block:'center',inline:'center'});
      const r=n.getBoundingClientRect(),x=Math.max(2,Math.min(innerWidth-2,r.left+r.width/2)),y=r.top+r.height/2;
      if(!n.contains(document.elementFromPoint(x,y)))throw Error('promotion touch point not on trigger');return {x,y};})()`);
    await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch]},owner);
    await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},owner);await opened();
    if(input==='touch')layout=await readLayout();
    // The old (2,2) point could activate real navigation after dismissing help.
    assert.equal(await run(`document.elementFromPoint(6,6)===promotionDismiss`),true);
    await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:6,y:6}]},owner);
    await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},owner);
    assert.equal(await run(`document.querySelector('#context-help').hidden`),true);
    if(!stableTouch)await command('Emulation.setTouchEmulationEnabled',{enabled:false},owner);
    await run(`document.activeElement?.blur()`);layouts.push({route:isolate?'promotion-isolation':'promotion-help',
      input,theme,width,...(isolate?{phase,hover:!failures.some(f=>f.phase===phase)}:{}),...layout});
  }
  assert.deepEqual(failures,[],'fixed-viewport diagnostic hover failures');
  checks.push(isolate?'Diagnostic only: fixed Classic 1920, two pre-touch hover cycles and one post-touch cycle':
    `Canonical promotion (${input}): exact multiline model/discount/dates, one postfix after tiers, named input/dismissal and bounded help in nine theme/width cases`);
  } finally {
    if(stableTouch)await command('Emulation.setTouchEmulationEnabled',{enabled:false},owner);
    if(trace)layouts.push({route:'promotion-trace',events:await run(`(()=>{
      const trace=window.promotionTrace;trace?.restore();delete window.promotionTrace;delete window.promotionStage;
      return trace?.events;
    })()`)});
    await run(`promotionDismiss.remove();delete window.promotionTarget;`);
  }
};
