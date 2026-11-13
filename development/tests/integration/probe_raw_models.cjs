// Actual headless hover/focus/touch with server-prepared native replay and synthetic finite DTOs.
const assert = require('node:assert/strict');
module.exports = async function rawModels({command,evaluate,until,owner,mini,checks,layouts,capture}) {
  await evaluate(owner,`window.rawCapture=${JSON.stringify(capture)};current.watch.earlier.open=true;
    current.watch.update(liveValue);miniWatch.update(liveValue);`);
  async function close(id) {
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},id);
    await evaluate(id,`document.activeElement?.blur()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},id);
  }
  async function open(id,selector,mode) {
    await command('Page.bringToFront',{},id);
    await close(id);
    await command('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,x:1,y:1},id);
    await command('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,x:1,y:1},id);
    await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'center',inline:'center'})`);
    const point=await evaluate(id,`(()=>{const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2}})()`);
    if(mode==='focus') {
      await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},id);
      await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).focus()`);
    } else if(mode==='touch') {
      await command('Emulation.setTouchEmulationEnabled',{enabled:true},id);
      await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]},id);
      await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},id);
    } else await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},id);
    try { await until(id,`document.querySelector('#context-help')?.matches(':popover-open')`); }
    catch(error) {
      const hit=await evaluate(id,`(()=>{const n=document.querySelector(${JSON.stringify(selector)}),r=n.getBoundingClientRect();
        return{rect:r.toJSON(),point:${JSON.stringify(point)},hit:document.elementFromPoint(${point.x},${point.y})?.outerHTML,
          hover:n.matches(':hover'),theme:document.documentElement.dataset.theme,zoom:document.documentElement.style.zoom}})()`);
      throw new Error(`${id===mini?'Mini':'Full'} ${selector} ${mode}: ${JSON.stringify(hit)} ${error.message}`);
    }
    const result=await evaluate(id,`(()=>{const p=document.querySelector('#context-help'),r=p.getBoundingClientRect();return{text:p.textContent,
      linked:document.querySelector(${JSON.stringify(selector)}).getAttribute('aria-describedby')==='context-help',
      fits:r.left>=0&&r.top>=0&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1}})()`);
    assert.ok(result.linked&&result.fits,JSON.stringify(result));
    if(mode==='touch') await command('Emulation.setTouchEmulationEnabled',{enabled:false},id);
    await close(id);return result.text;
  }
  for(const theme of ['classic','light','dark']) for(const width of [1280,360]) for(const zoom of [1,1.5]) {
    for(const id of [owner,mini]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},id);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},id);
      await evaluate(id,`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}';document.documentElement.style.zoom='${zoom}'`);
    }
    for(const [id,selectors] of [[owner,['.watch-active tbody td:nth-child(4) .help-value',
        '.watch-history tbody td:nth-child(4) .help-value','.watch-active tbody td:nth-child(7) .help-value',
        '.watch-history tbody td:nth-child(7) .help-value','.watch-active tbody td:nth-child(6) .help-value',
        '.watch-history tbody td:nth-child(6) .help-value']],
        [mini,['.mini-prompt-table tr[data-id="replay-active_cards-0"] td:nth-child(3) .help-value',
          '.mini-prompt-table tr[data-id="replay-history_cards-0"] td:nth-child(3) .help-value']]]) {
      for(const selector of selectors) for(const mode of ['focus','hover','touch']) {
        const text=await open(id,selector,mode);
        assert.match(text,/claude-agent\/sonnet/);assert.match(text,/Catalog modelID: claude-sonnet-5-5/);
        assert.doesNotMatch(text,/Claude Sonnet 5\.5\s*\[/);
      }
    }
    layouts.push({theme,width,zoom,surfaces:'Full Running/Earlier Model, Calls; Mini prompt cost',interactions:['focus','hover','touch']});
  }
  for(const id of [owner,mini]) await evaluate(id,`document.documentElement.style.zoom=''`);
  await command('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false},owner);
  await evaluate(owner,`window.rawAudit=document.createElement('section');document.body.append(rawAudit);
    window.rawSessions=new SessionsCatalog.View(()=>{});rawAudit.append(rawSessions.root);
    rawSessions.data={view:rawCapture.synthetic_views.sessions};rawSessions.rows(rawCapture.synthetic_views.sessions.session_usage);
    window.rawDetail=new SessionDetail.View(()=>{},'root-0000');rawAudit.append(rawDetail.root);
    rawDetail.update({result:{view:rawCapture.synthetic_views.session}});
    window.rawComparisons=new ComparisonsView.View(()=>{});rawAudit.append(rawComparisons.root);
    rawComparisons.update({result:{view:rawCapture.synthetic_views.comparisons},withheld:false,loading:false});
    window.rawStats=new AIStatsView.View(()=>{});rawAudit.append(rawStats.root);
    rawStats.update({period:'all',result:{view:rawCapture.synthetic_views['ai-stats']}});
    [...rawStats.cards.get('token-rate').podium].find((item,index)=>
      rawStats.cards.get('token-rate').metric.podium[index]?.model_help.includes('claude-agent/sonnet')).label.classList.add('raw-agent-racer');`);
  for(const theme of ['classic','light','dark']) for(const width of [1280,360]) for(const zoom of [1,1.5]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},owner);
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},owner);
    await evaluate(owner,`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}';document.documentElement.style.zoom='${zoom}'`);
    for(const selector of ['.sessions-table tr[data-id="root-0000"] td:nth-child(3) .help-value',
        '.session-history-table tbody td:nth-child(2) .help-value','.session-history-table tbody td:nth-child(5) .help-value',
        '.comparison-table tr[data-session="root-0000"] td:nth-child(3) button','.raw-agent-racer']) {
      for(const mode of ['focus','hover','touch']) assert.match(await open(owner,selector,mode),/claude-agent\/sonnet/,selector+' '+mode);
    }
    layouts.push({theme,width,zoom,surfaces:'Sessions, Session detail Model/Calls, Comparisons, AI Stats',interactions:['focus','hover','touch']});
  }
  const copilot=await open(owner,'.comparison-table tr[data-session="root-0001"] td:nth-child(3) button','focus');
  assert.match(copilot,/github-copilot\/claude-sonnet-5-5/);assert.doesNotMatch(copilot,/claude-agent\/sonnet/);
  await evaluate(owner,`const failed=rawCapture.browser_rows.find(r=>r.recorded_selections.length);
    rawDetail.update({result:{view:{...rawCapture.synthetic_views.session,prompt_blocks:[{
      ...rawCapture.synthetic_views.session.prompt_blocks[0],rows:[{...failed,id:'failed-owned'}]}]}}});`);
  const failed=await open(owner,'.session-history-table tbody td:nth-child(2) .help-value','focus');
  assert.match(failed,/Recorded selection: claude-agent\/claude-haiku-4-5-20251001[\s\S]*Usage unavailable; cost unknown/);
  await evaluate(owner,`document.activeElement?.blur();rawDetail.update({result:{view:{...rawCapture.synthetic_views.session,prompt_blocks:[{
    ...rawCapture.synthetic_views.session.prompt_blocks[0],rows:rawCapture.synthetic_prompt_cases.map((row,index)=>({...row,id:'case-'+index}))}]}}});`);
  for(const mode of ['focus','hover','touch']) {
    const mixed=await open(owner,'.session-history-table tr[data-id="case-0"] td:nth-child(2) .help-value',mode);
    assert.match(mixed,/Main prompt — claude-agent\/claude-sonnet-5-5[\s\S]*Subagent 1 — github-copilot\/claude-sonnet-5-5/);
    const compact=await open(owner,'.session-history-table tr[data-id="case-1"] td:nth-child(2) .help-value',mode);
    assert.match(compact,/openrouter\/vendor\/future-release/);assert.doesNotMatch(compact,/claude-agent|github-copilot/);
  }
  checks.push('Recorded alias and distinct Copilot route in actual Sessions/detail/Comparisons/AI Stats focus, hover and touch; saved failed assistant selection stays separate from unknown usage.');
  checks.push('Owned Sonnet replay in Full Running/Earlier Model/Calls/CCost and Mini Running/Earlier cost, plus synthetic finite views at 360/1280, 100/150% zoom, Classic/light/dark; all three interactions, clamped panel and ARIA link.');
  checks.push('Synthetic same-model mixed parent/child routes and independently attributed compaction in actual Session detail focus, hover and touch.');
};
