// Synthetic source facts through shipped DOM/PiP and native headless browser input.
const assert = require('node:assert/strict');
module.exports = async function defaultEffort({command,evaluate,until,owner,mini,checks,layouts,capture}) {
  const notes = /Likely effort|Inferred from current|Observed in the recorded|No supported concrete/;
  await evaluate(owner,`window.effortCapture=${JSON.stringify(capture)};
    current.watch.earlier.open=true;current.watch.update(liveValue);miniWatch.update(liveValue);`);
  async function close(id) {
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},id);
    await evaluate(id,`document.activeElement?.blur()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},id);
  }
  async function open(id,selector,mode='focus',retain=false) {
    await command('Page.bringToFront',{},id);await close(id);
    await command('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,x:1,y:1},id);
    await command('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,x:1,y:1},id);
    assert.equal(await evaluate(id,`!!document.querySelector(${JSON.stringify(selector)})`),true,selector);
    await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'center',inline:'center'})`);
    const point=await evaluate(id,`(()=>{const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();
      return{x:r.left+r.width/2,y:r.top+r.height/2}})()`);
    if(mode==='focus') {
      await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},id);
      await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).focus()`);
    } else if(mode==='touch') {
      await command('Emulation.setTouchEmulationEnabled',{enabled:true},id);
      await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]},id);
      await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},id);
    } else await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},id);
    try {await until(id,`document.querySelector('#context-help')?.matches(':popover-open')`);}
    catch(error) {throw new Error(`${selector} ${mode}: ${error.message}`);}
    const result=await evaluate(id,`(()=>{const p=document.querySelector('#context-help'),r=p.getBoundingClientRect();
      return{text:p.textContent,linked:document.querySelector(${JSON.stringify(selector)}).getAttribute('aria-describedby')==='context-help',
      fits:r.left>=0&&r.top>=0&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1}})()`);
    assert.ok(result.linked&&result.fits,JSON.stringify({selector,mode,...result}));
    if(mode==='touch') await command('Emulation.setTouchEmulationEnabled',{enabled:false},id);
    if(!retain) await close(id);
    return result.text;
  }
  function check(text,level,valueCell,source) {
    assert.ok(text.includes(`default (${level})${valueCell?'*':''}`),text);
    assert.doesNotMatch(text,/\([a-z]+\) \([a-z]+\)/);
    if(valueCell) assert.match(text,source || notes);
    else {assert.doesNotMatch(text,/default \([a-z]+\)\*/);assert.doesNotMatch(text,notes);}
  }
  const watch=(group,index,col)=>`.${group} .watch-card:nth-child(${index+1}) tbody td:nth-child(${col}) .help-value`;
  // Every confidence class, explicit selection and both Watch tables; unchanged visible effort.
  for(const group of ['watch-active','watch-history']) for(let index=0;index<5;index++) {
    for(const col of [4,5,6,7]) {
      const selector=watch(group,index,col),text=await open(owner,selector);
      if(index===4) {assert.doesNotMatch(text,/default \(|Likely effort|Inferred from current|Observed in the recorded/);}
      else check(text,index===1?'low':index===3?'unknown':'high',col===5,
        col!==5?null:index===0?/Likely effort.*Defaults may change/:index===1?/historical settings may differ/:
          index===2?/Observed in the recorded request/:/No supported concrete/);
    }
    const visible=await evaluate(owner,`document.querySelector(${JSON.stringify(watch(group,index,5))}).textContent`);
    assert.equal(visible,capture.browser_rows[index].watch_effort);
  }
  for(let index=0;index<5;index++) {
    const text=await open(mini,`.mini-prompt-table tr[data-id="replay-active_cards-${index}"] td:nth-child(3) .help-value`);
    if(index!==4) check(text,index===1?'low':index===3?'unknown':'high',false);
    else assert.doesNotMatch(text,/default \(/);
  }
  // Theme/size/zoom and real hover, keyboard, tap for new targets and ordinary parallel help.
  for(const theme of ['classic','light','dark']) for(const width of [1280,360]) for(const zoom of [1,1.5]) {
    for(const id of [owner,mini]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},id);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},id);
      await evaluate(id,`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}';document.documentElement.style.zoom='${zoom}'`);
    }
    for(const mode of ['focus','hover','touch']) {
      for(const group of ['watch-active','watch-history']) for(const col of [4,5,6,7])
        check(await open(owner,watch(group,0,col),mode),'high',col===5);
      check(await open(mini,'.mini-prompt-table tr[data-id="replay-active_cards-0"] td:nth-child(3) .help-value',mode),'high',false);
    }
    layouts.push({theme,width,zoom,surfaces:'Watch Running/Earlier Model/Effort/CCost/Calls; actual Mini PiP',modes:['focus','hover','touch']});
  }
  // Retained live Effort help survives publication without replacing the focused target.
  await open(owner,watch('watch-active',0,5),'focus',true);
  await evaluate(owner,`window.retainedEffort=document.activeElement;current.watch.update(liveValue)`);
  assert.equal(await evaluate(owner,`document.activeElement===retainedEffort && retainedEffort.getAttribute('aria-describedby')==='context-help'`),true);
  check(await evaluate(owner,`document.querySelector('#context-help').textContent`),'high',true);
  await close(owner);
  for(const id of [owner,mini]) await evaluate(id,`document.documentElement.style.zoom=''`);
  await evaluate(owner,`window.effortAudit=document.createElement('section');document.body.append(effortAudit);
    window.effortSessions=new SessionsCatalog.View(()=>{});effortAudit.append(effortSessions.root);
    effortSessions.data={view:effortCapture.synthetic_views.sessions};effortSessions.rows(effortCapture.synthetic_views.sessions.session_usage);
    window.effortDetail=new SessionDetail.View(()=>{},'root-0000');effortAudit.append(effortDetail.root);
    window.effortDetailData={result:{view:{...effortCapture.synthetic_views.session,prompt_blocks:[{
      ...effortCapture.synthetic_views.session.prompt_blocks[0],rows:effortCapture.browser_rows.map((r,i)=>({...r,id:'effort-'+i}))}]}}};
    effortDetail.update(effortDetailData);
    window.effortComparisons=new ComparisonsView.View(()=>{});effortAudit.append(effortComparisons.root);
    effortComparisons.update({result:{view:effortCapture.synthetic_views.comparisons},withheld:false,loading:false});
    window.effortStats=new AIStatsView.View(()=>{});effortAudit.append(effortStats.root);
    effortStats.update({period:'all',result:{view:effortCapture.synthetic_views['ai-stats']}});
    [...effortStats.cards.get('token-rate').podium].find((n,i)=>
      effortStats.cards.get('token-rate').metric.podium[i]?.model_help.includes('default (high)')).label.classList.add('effort-racer');`);
  const detail=(index,col)=>`.session-history-table tr[data-id="effort-${index}"] td:nth-child(${col}) .help-value`;
  const comparison=(index,col)=>`.comparison-table tr[data-session="root-000${index}"] td:nth-child(${col}) button`;
  for(let index=0;index<5;index++) for(const selector of [detail(index,2),detail(index,3),comparison(index,3),comparison(index,4)]) {
    const text=await open(owner,selector);
    if(index===4) assert.doesNotMatch(text,/default \(|Likely effort|Inferred from current|Observed in the recorded/);
    else check(text,index===1?'low':index===3?'unknown':'high',selector===detail(index,3)||selector===comparison(index,4));
  }
  for(const theme of ['classic','light','dark']) for(const width of [1280,360]) for(const zoom of [1,1.5]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},owner);
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},owner);
    await evaluate(owner,`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}';document.documentElement.style.zoom='${zoom}'`);
    for(const mode of ['focus','hover','touch']) for(const selector of [detail(0,2),detail(0,3),detail(0,4),detail(0,5),comparison(0,3),comparison(0,4),'.effort-racer'])
      check(await open(owner,selector,mode),'high',selector===detail(0,3)||selector===comparison(0,4));
    const catalog=await open(owner,'.sessions-table tr[data-id="root-0000"] td:nth-child(3) .help-value');
    assert.doesNotMatch(catalog,/default \(|Likely effort|Inferred from current|Observed in the recorded/,'catalog identity help invents no effort');
    layouts.push({theme,width,zoom,surfaces:'Sessions identity, detail Model/Effort/CCost/Calls, Comparisons Model/Effort, Stats podium',modes:['focus','hover','touch']});
  }
  await open(owner,detail(0,3),'focus',true);
  await evaluate(owner,`window.retainedDetail=document.activeElement;effortDetail.update(effortDetailData)`);
  assert.equal(await evaluate(owner,`document.activeElement===retainedDetail`),true);
  await close(owner);
  await evaluate(owner,`effortDetailData.result.view.prompt_blocks[0].rows=[{...effortCapture.mixed_prompt,id:'mixed-effort'}];effortDetail.update(effortDetailData)`);
  for(const mode of ['focus','hover','touch']) {
    const text=await open(owner,'.session-history-table tr[data-id="mixed-effort"] td:nth-child(2) .help-value',mode);
    assert.match(text,/Main prompt — anthropic\/claude-sonnet-5-5 · default \(high\)/);
    assert.match(text,/Subagent 1 — anthropic\/claude-opus-5-5 · default \(medium\)/);
    assert.doesNotMatch(text,/default \([a-z]+\)\*|Likely effort/);
  }
  for(const selector of ['.watch-active th:nth-child(5) button','.session-history-table th:nth-child(3) button','.comparison-table th:nth-child(4) button'])
    assert.doesNotMatch(await open(owner,selector),/default \(|Likely effort|Inferred from current|Observed in the recorded/);
  checks.push('All five evidence/selection classes preserve visible cells; only dedicated Effort values have source-sensitive footnotes.');
  checks.push('Classic/light/dark, 360/1280, 100/150% zoom; hover/focus/tap, clamped help, ARIA, real PiP and retained Watch/detail focus.');
  checks.push('Mixed parent Sonnet default(high) and child Opus default(medium), terse parallel help, unchanged generic headers and catalog identity.');
};
