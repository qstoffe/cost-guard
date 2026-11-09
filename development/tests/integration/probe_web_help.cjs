// Actual hidden Chromium + Document PiP, shipped HTTP/CSP/SSE; no personal profile.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output, scope] = process.argv.slice(2);
async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output));
   assert.ok(scope === undefined || ['--watch-only','--live-status','--ccost-unavailable','--quiet-refresh'].includes(scope));
  await fs.stat(browser); await fs.stat(path.dirname(output));
  const profile = await fs.mkdtemp(path.join(path.dirname(output), 'help-browser-'));
  const config = await fs.mkdtemp(path.join(path.dirname(output), 'help-config-'));
  const server = spawn('py', ['-3', 'development/tests/integration/serve_mini_watch.py', config, '--help-audit'], {windowsHide:true,stdio:['pipe','pipe','pipe']});
  let serverErrors = '';
  server.stderr.on('data', chunk => {serverErrors = (serverErrors + chunk.toString()).slice(-12000);});
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
   const child = spawn(browser, ['--headless=new','--screen-info={1920x1080}','--no-first-run','--no-default-browser-check','--disable-extensions',
    '--disable-background-networking','--remote-debugging-pipe','--user-data-dir='+profile,'about:blank'],
    {windowsHide:true,stdio:['ignore','ignore','ignore','pipe','pipe']});
  const pending = new Map(); let sequence = 0, buffer = '', errors = [];
  child.stdio[4].on('data', chunk => {
    buffer += chunk.toString(); let index;
    while ((index=buffer.indexOf('\0'))>=0) {
      const value=JSON.parse(buffer.slice(0,index)); buffer=buffer.slice(index+1);
      if (value.id) { const entry=pending.get(value.id); pending.delete(value.id);
        if (entry) {clearTimeout(entry.timer); value.error?entry.reject(new Error(JSON.stringify(value.error))):entry.resolve(value.result);} }
      else if (value.method==='Runtime.exceptionThrown') errors.push(value.params.exceptionDetails.text);
    }
  });
  const command=(method,params={},sessionId)=>new Promise((resolve,reject)=>{
    const id=++sequence,timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout: '+method));},15000);
    pending.set(id,{resolve,reject,timer});child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');
  });
  const evaluate=async (sessionId,expression,userGesture=false)=>{
    const value=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true,userGesture},sessionId);
    if(value.exceptionDetails) throw new Error(JSON.stringify(value.exceptionDetails)); return value.result.value;
  };
  const until=async (id,expression)=>{
    const end=Date.now()+15000;
    while(Date.now()<end) {if(await evaluate(id,expression))return;await new Promise(resolve=>setTimeout(resolve,30));}
     const state=await evaluate(id,`(async () => {const state=typeof current==='undefined'?null:current;const job=state?.active ? await api('/api/jobs/'+state.active) : null;return {section:document.body.dataset.section,notice:document.getElementById('notice')?.textContent,text:document.getElementById('result')?.textContent.slice(0,300),loading:state?.loading,job:job&&{status:job.status,error:job.error,result:!!job.result},visibility:document.visibilityState,focus:document.hasFocus(),active:document.activeElement?.outerHTML.slice(0,500),panel:document.querySelector('#context-help')?.outerHTML.slice(0,700),events:window.helpEvents};})()`);
    throw new Error('Condition not reached: '+expression+' '+JSON.stringify({state,errors})+'\n'+serverErrors);
  };
  const key=async (id,key)=>{
    await command('Input.dispatchKeyEvent',{type:'keyDown',key,code:key,windowsVirtualKeyCode:key==='Escape'?27:9},id);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key,code:key,windowsVirtualKeyCode:key==='Escape'?27:9},id);
  };
  const checks=[],layouts=[]; let evidence={outcome:'FAIL'};
   const deadline=setTimeout(()=>{child.kill();server.kill();},170000);
  try {
    const launch=JSON.parse((await lines.next()).value); // Never log bootstrap credentials.
    const version=await command('Browser.getVersion');
    const {targetId}=await command('Target.createTarget',{url:'about:blank'});
    const {sessionId:owner}=await command('Target.attachToTarget',{targetId,flatten:true});
    await command('Page.enable',{},owner);await command('Runtime.enable',{},owner);
    await command('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false},owner);
    await command('Page.navigate',{url:launch.url},owner);
    await until(owner,`typeof miniWatch!=='undefined' && hostState.kind==='connected' && liveValue?.view?.active_cards?.length===2`);
    await evaluate(owner,`location.hash='#/watch'`);
     await until(owner,`current?.watch?.cards.size>0`);
     if(scope==='--quiet-refresh') {
       await require('./probe_quiet_refresh.cjs')({command,evaluate,until,owner,checks,layouts});
       assert.deepEqual(errors,[]);
       evidence={outcome:'PASS',browser:version.product,checks,layouts,errors,
         limitations:['Canonical synthetic finite reports and Live publications; injected Sessions/detail API responses, not real catalog acquisition.',
           'Headless DOM, input and AX evidence; not physical desktop or assistive-technology acceptance.']};
       console.log(JSON.stringify({outcome:'PASS',checks,cases:layouts.length}));return;
     }
    await evaluate(owner,`miniWatch.toggle()`,true);
    assert.equal(await evaluate(owner,`!!miniWatch.window`),true);
    const targets=await command('Target.getTargets');
    let mini;
    for (const target of targets.targetInfos.filter(target=>target.type==='page'&&target.targetId!==targetId)) {
      const attached=await command('Target.attachToTarget',{targetId:target.targetId,flatten:true});
      if(await evaluate(attached.sessionId,`!!document.querySelector('.mini-watch')`)){mini=attached.sessionId;break;}
    }
    assert.ok(mini, 'actual Document PiP target');
    await command('Runtime.enable',{},mini);await command('Page.enable',{},mini);
     await until(mini,`document.querySelector('.mini-prompt-table .help-trigger') && document.styleSheets.length===2`);
     const headerHelp=require('./probe_help_headers.cjs')({command,evaluate,until,owner,mini,checks,layouts});
      if(scope === '--ccost-unavailable') {
         await require('./probe_ccost_unavailable.cjs')({command,evaluate,until,owner,mini,checks,layouts});
         assert.deepEqual(errors,[]);
         evidence={outcome:'PASS',browser:version.product,checks,layouts,errors,
           limitations:['Synthetic canonical snapshots; not the historical owner incident.','Headless Chromium with real Document PiP; CDP focus emulation for opener Sessions checks after PiP closes. No physical desktop, screen-reader or other-engine proof.']};
        await fs.writeFile(output,JSON.stringify(evidence,null,2));
        console.log(JSON.stringify({outcome:evidence.outcome,checks,errors}));return;
      }
      await headerHelp.matrix();
     await require('./probe_help_lifecycle.cjs')({command,evaluate,until,owner,mini,checks});
      await require('./probe_help_values.cjs')({command,evaluate,until,owner,mini,checks,layouts});
      await require('./probe_cost_groups.cjs')({command,evaluate,until,owner,mini,checks,layouts});
    async function focus(id,selector) {
      await key(id,'Tab');
      await evaluate(id,`(() => {const n=document.querySelector(${JSON.stringify(selector)});if(document.activeElement===n)n.blur();n.focus();})()`);
      await until(id,`document.querySelector('#context-help')?.matches(':popover-open')`);
      return evaluate(id,`document.querySelector('#context-help').textContent`);
    }
    async function interaction(id,selector) {
      await command('Page.bringToFront',{},id);
      const copy=await focus(id,selector);
      assert.ok(copy.length>0);
      assert.equal(await evaluate(id,`document.activeElement.getAttribute('aria-describedby')==='context-help' && !document.activeElement.hasAttribute('title')`),true);
      await key(id,'Escape');
      assert.equal(await evaluate(id,`document.querySelector('#context-help').hidden`),true);
      await evaluate(owner,`miniWatch.render(); if(current.watch) current.watch.update(liveValue)`);
      assert.equal(await evaluate(id,`document.querySelector('#context-help').hidden`),true,'render never reopens dismissed help');
      await evaluate(id,`document.activeElement.blur()`);
      await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},id);
      await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'nearest',inline:'nearest'})`);
      const point=await evaluate(id,`(() => {const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
      await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},id);
      await until(id,`document.querySelector('#context-help').matches(':popover-open')`);
      const helpPoint=await evaluate(id,`(() => {const r=document.querySelector('#context-help').getBoundingClientRect();return {x:r.left+8,y:r.top+8};})()`);
      await command('Input.dispatchMouseEvent',{type:'mouseMoved',...helpPoint},id);
      await evaluate(id,`new Promise(resolve=>setTimeout(resolve,200))`);
      assert.equal(await evaluate(id,`document.querySelector('#context-help').matches(':popover-open')`),true,'pointer can read inside the help');
      await key(id,'Escape');
      await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},id);
      await command('Emulation.setTouchEmulationEnabled',{enabled:true},id);
      await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]},id);
      await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},id);
      await until(id,`document.querySelector('#context-help').matches(':popover-open')`);
      await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:2,y:2}]},id);
      await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},id);
      assert.equal(await evaluate(id,`document.querySelector('#context-help').hidden`),true,'tap outside dismisses');
      await command('Emulation.setTouchEmulationEnabled',{enabled:false},id);
      await evaluate(id,`document.activeElement?.blur()`);
      return copy;
    }
    for (const theme of ['classic','light','dark']) {
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},owner);
      await evaluate(owner,`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}';miniWatch.syncTheme()`);
      const cost=await interaction(owner,'.watch-active th:nth-child(6) button');
       assert.match(cost,/not your bill[\s\S]*value for Incoming\/Extra CCost and model\/subagent details/);
      assert.doesNotMatch(cost,/displayed zero|N\/A|not zero|cannot be priced|Input token share/);
      const mix=await focus(owner,'.watch-active th:nth-child(8) button');
      assert.match(mix,/I \/ C \/ W \/ O[\s\S]*I — Input[\s\S]*C — Cached[\s\S]*W — Cache write[\s\S]*O — Output[\s\S]*reasoning/);
      const model=await focus(owner,'.watch-active th:nth-child(4) button');
       assert.match(model,/^• Main prompt[^\n]*\n• Linked subagents/);
       assert.doesNotMatch(model,/Unlinked or unpriced/);
      await key(owner,'Escape');
      await interaction(mini,'.mini-prompts > table th:last-child button');
      for (const id of [owner,mini]) {
        const selector=id===owner?'.watch-active tbody td:nth-child(6) .help-value':'.mini-prompts > table th:first-child button';
        await focus(id,selector);
        const facts=await evaluate(id,`(() => {const p=document.querySelector('#context-help'),r=p.getBoundingClientRect(),s=getComputedStyle(p);return {width:innerWidth,height:innerHeight,left:r.left,top:r.top,right:r.right,bottom:r.bottom,whiteSpace:s.whiteSpace,cursor:getComputedStyle(document.activeElement).cursor,theme:document.documentElement.dataset.theme};})()`);
        assert.equal(facts.whiteSpace,'pre-line');assert.equal(facts.cursor,'help');
        assert.ok(facts.left>=0&&facts.top>=0&&facts.right<=facts.width&&facts.bottom<=facts.height);
        layouts.push({theme,document:id===owner?'watch':'mini',...facts});
        const image=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},id);
        await fs.writeFile(output.replace(/\.json$/,'')+`-${theme}-${id===owner?'watch':'mini'}.png`,Buffer.from(image.data,'base64'));
        await key(id,'Escape');
      }
    }
    checks.push('Classic/Web light/Web dark: real keyboard, hover, pointer transfer, Escape, touch and outside-dismiss in full Watch and actual Document PiP');
    for (const width of [1280,360]) for (const zoom of [1,1.5]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},owner);
      await evaluate(owner,`document.documentElement.style.zoom='${zoom}'`);
       const layout=await evaluate(owner,`(() => {const d=document.querySelector('.watch-daily');return {cues:document.querySelectorAll('.help-cue').length,targets:d.querySelectorAll('.help-value').length,overlaps:[...d.children].some((n,i)=>[...d.children].slice(i+1).some(m=>{const a=n.getBoundingClientRect(),b=m.getBoundingClientRect();return a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top;})),pageOverflow:document.documentElement.scrollWidth>innerWidth};})()`);
       assert.equal(layout.cues,0);assert.equal(layout.targets,0);
      assert.equal(layout.overlaps,false);assert.equal(layout.pageOverflow,false);
       layouts.push({case:'daily-value-targets',width,zoom,...layout});
       for (const table of ['watch-active','watch-history']) {
         const text=await focus(owner,`.${table} tbody td:nth-child(6) .help-value`);
          assert.match(text,/Main prompt[\s\S]*Subagents[\s\S]*Total CCost: 33/);
         const bounds=await evaluate(owner,`(() => {const n=document.querySelector('#context-help'),r=n.getBoundingClientRect();return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:innerWidth,height:innerHeight,scroll:n.scrollHeight>n.clientHeight};})()`);
         assert.ok(bounds.left>=0&&bounds.top>=0&&bounds.right<=bounds.width&&bounds.bottom<=bounds.height,JSON.stringify({table,zoom,...bounds}));
         layouts.push({case:'rich-cost-bounds',table,width,zoom,...bounds});await key(owner,'Escape');
       }
    }
    await evaluate(owner,`document.documentElement.style.zoom=''`);
    await command('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false},owner);
     const quota=await focus(mini,'.mini-accounts li:nth-child(2) .help-value');
      assert.match(quota,/^Capacity: [^\n]+\nNext reset: [^\n]+\nCapacity — Guesstimate before display rounding: 1680 Credits\.\nUnrounded calculation, not verified provider usage or a guaranteed balance\.$/);
    assert.doesNotMatch(quota,/Last quota update|Source:|Availability:/);
    await key(mini,'Escape');
    await evaluate(owner,`(() => {window.helpMiniUpdate=miniWatch.update;window.helpMiniEpoch=liveValue.view.now_ms;
      miniWatch.update=function(p){if(p===liveValue&&p?.view?.now_ms===helpMiniEpoch)return;return helpMiniUpdate.call(this,p);};
      const p=structuredClone(liveValue);p.view.now_ms++;for(const card of p.view.active_cards){card.title='<script>Exact title</script> '+ 'long title '.repeat(30);card.session_summary.cost.display.known_ccost='?12';card.session_summary.cost.display_units.credits.known_ccost='?12';card.session_summary.cost.complete=false;card.state='observed';}miniWatch.update(p);p.view.now_ms++;for(const card of p.view.active_cards){card.state='retrying';card.session_summary.state='unavailable';}miniWatch.update(p);})()`);
    const title=await evaluate(mini,`document.querySelector('.mini-prompts tr[data-id="root"] .mini-session').textContent`);
    assert.ok(title.startsWith('<script>Exact title</script> '));
    assert.equal(await evaluate(mini,`document.querySelector('.mini-source-note')`),null);
    const retainedHelp=await focus(mini,'.mini-prompts tr[data-id="root"] .mini-cost-value > span:first-child');
    assert.match(retainedHelp,/Prompt #[\s\S]*Main model:/);assert.doesNotMatch(retainedHelp,/Source evidence:/);
    assert.match(await focus(mini,'.mini-prompts tr[data-id="root"] .mini-session'),/^<script>Exact title<\/script>[\s\S]*Prompt #\d+ in this session: Keep completed literally/);
    assert.equal(await evaluate(mini,`document.querySelectorAll('tbody .help-trigger,.mini-header .help-cue').length`),0);
    const heading=await focus(mini,'.mini-prompts > table th:nth-child(2) button');
     assert.equal(heading,'The name of the session.');
     const totalHeading=await focus(mini,'.mini-prompts > table th:nth-child(3) button');
     assert.match(totalHeading,/First: the representative prompt’s reference CCost[\s\S]*In parentheses: the entire session’s reference CCost/);
    assert.equal(await evaluate(mini,`document.querySelector('#context-help script')===null`),true);
    await key(mini,'Escape');
    await evaluate(owner,`miniWatch.update=helpMiniUpdate;delete window.helpMiniUpdate;delete window.helpMiniEpoch;miniWatch.update(liveValue)`);
     for (const selector of ['.watch-active tbody td:first-child .help-value']) {
      const metadata=await focus(owner,selector);assert.ok(metadata.length>0);await key(owner,'Escape');
    }
    await evaluate(mini,`document.documentElement.style.fontSize='150%'`);
    await focus(mini,'.mini-prompts > table th:last-child button');
    assert.equal(await evaluate(mini,`(() => {const r=document.querySelector('#context-help').getBoundingClientRect();return r.right<=innerWidth&&r.bottom<=innerHeight;})()`),true);
    await key(mini,'Escape');await evaluate(mini,`document.documentElement.style.fontSize=''`);
    assert.equal(await evaluate(owner,`document.querySelectorAll('.watch-prompt-label .help-trigger').length`),0);
     checks.push('Verbatim selectable/accessible long hostile session title without row cues; separate Session/cost help, quiet retained row without source-status help, no HTML injection and Mini 150% text zoom');
    await command('Page.bringToFront',{},owner);
    const routes = scope === '--watch-only' ? [] : scope === '--live-status' ?
      ['models','accounts','token-mix','ai-stats','comparisons','settings'] :
      ['models','sessions','sessions/root','accounts','token-mix','ai-stats','settings'];
    for (const route of routes) {
      await evaluate(owner,`location.hash='#/${route}'`);
      await until(owner,`document.body.dataset.section==='${route.split(/[?\/]/)[0]}'`);
      if (route==='token-mix') await evaluate(owner,`acquire(current)`);
       await until(owner,`!current.loading && !document.getElementById('result').getAttribute('aria-busy')?.includes('true')`);
       assert.equal(await evaluate(owner,`current.failed===true`),false,route+' report is usable');
       await headerHelp.audit(owner);
       if (['models','sessions'].includes(route)) {
         layouts.push({case:'sort-label-hover',route,...await headerHelp.target(owner,'#result th:first-child .help-label')});
       }
      await key(owner,'Tab');
      const count=await evaluate(owner,`(async () => {const targets=[...document.querySelectorAll('#result button,#result input,#result .help-value')].filter(n=>!n.disabled);let checked=0;for(const n of targets){n.focus();const p=document.querySelector('#context-help');if(n.getAttribute('aria-describedby')?.split(' ').includes('context-help')){if(!p.textContent||n.hasAttribute('title'))throw Error('invalid help');checked++;}}document.activeElement?.blur();return checked;})()`);
      checks.push(`${route}: rendered help/disclosure inventory (${count} focusable help targets); visible field/disclosure text retained`);
    }
    assert.deepEqual(errors,[]);
    evidence={outcome:'PASS',browser:version.product,scope:scope || 'all-routes',checks,layouts,limitations:['Immediate in-memory synthetic report jobs; no report-process lifecycle proof.','Headless Chromium only; no physical desktop, screen-reader or other-engine acceptance claimed.',...(scope === '--watch-only' ? ['Watch/Mini only; no unrelated report-route audit in this mode.'] : scope === '--live-status' ? ['Live surfaces and cached-report routes only; synthetic Sessions catalog/detail are not configured in this host.'] : [])]};
  } finally {
    clearTimeout(deadline);
    await fs.writeFile(output,JSON.stringify(evidence,null,2));
    await command('Browser.close').catch(()=>{});if(child.exitCode===null)child.kill();
    server.stdin.end();await new Promise(resolve=>server.once('exit',resolve));
    await fs.rm(profile,{recursive:true,force:true});await fs.rm(config,{recursive:true,force:true});
  }
  console.log(JSON.stringify(evidence));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
