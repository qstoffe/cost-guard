// Actual hidden Chromium + Document PiP, shipped HTTP/CSP/SSE; no personal profile.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output] = process.argv.slice(2);
async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output));
  await fs.stat(browser); await fs.stat(path.dirname(output));
  const profile = await fs.mkdtemp(path.join(path.dirname(output), 'help-browser-'));
  const config = await fs.mkdtemp(path.join(path.dirname(output), 'help-config-'));
  const server = spawn('py', ['-3', 'development/tests/integration/serve_mini_watch.py', config, '--help-audit'], {windowsHide:true,stdio:['pipe','pipe','pipe']});
  let serverErrors = '';
  server.stderr.on('data', chunk => {serverErrors = (serverErrors + chunk.toString()).slice(-12000);});
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const child = spawn(browser, ['--headless=new','--no-first-run','--no-default-browser-check','--disable-extensions',
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
    const state=await evaluate(id,`(async () => {const state=typeof current==='undefined'?null:current;const job=state?.active ? await api('/api/jobs/'+state.active) : null;return {section:document.body.dataset.section,notice:document.getElementById('notice')?.textContent,text:document.getElementById('result')?.textContent.slice(0,300),loading:state?.loading,job:job&&{status:job.status,error:job.error,result:!!job.result},visibility:document.visibilityState,focus:document.hasFocus(),events:window.helpEvents};})()`);
    throw new Error('Condition not reached: '+expression+' '+JSON.stringify({state,errors})+'\n'+serverErrors);
  };
  const key=async (id,key)=>{
    await command('Input.dispatchKeyEvent',{type:'keyDown',key,code:key,windowsVirtualKeyCode:key==='Escape'?27:9},id);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key,code:key,windowsVirtualKeyCode:key==='Escape'?27:9},id);
  };
  const checks=[],layouts=[]; let evidence={outcome:'FAIL'};
  const deadline=setTimeout(()=>{child.kill();server.kill();},150000);
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
    await require('./probe_help_lifecycle.cjs')({command,evaluate,until,owner,mini,checks});
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
      assert.match(cost,/I — Incoming context cost on the first model request\.\nE — Other cost/);
      assert.match(cost,/not your bill[\s\S]*N\/A[\s\S]*not zero[\s\S]*cannot be priced/);
      const mix=await focus(owner,'.watch-active th:nth-child(8) button');
      assert.match(mix,/I \/ C \/ W \/ O[\s\S]*I — Input[\s\S]*C — Cached[\s\S]*W — Cache write[\s\S]*O — Output[\s\S]*reasoning/);
      const model=await focus(owner,'.watch-active th:nth-child(4) button');
      assert.match(model,/Linked subagents[\s\S]*different models[\s\S]*Unlinked or unpriced/);
      await key(owner,'Escape');
      await interaction(mini,'.mini-prompts > table th:last-child button');
      for (const id of [owner,mini]) {
        const selector=id===owner?'.watch-active th:nth-child(6) button':'.mini-prompts > table th:first-child button';
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
      const layout=await evaluate(owner,`(() => {const d=document.querySelector('.watch-daily'),h=d.querySelector('.help-cue'),r=h.getBoundingClientRect(),b=d.getBoundingClientRect(),s=getComputedStyle(d);return {cues:d.querySelectorAll('.help-cue').length,direct:h.parentNode===d,rightGap:b.right-r.right-(parseFloat(s.paddingRight)+parseFloat(s.borderRightWidth))*${zoom},overlaps:[...d.children].filter(n=>n!==h).some(n=>{const a=n.getBoundingClientRect();return a.left<r.right&&a.right>r.left&&a.top<r.bottom&&a.bottom>r.top;}),pageOverflow:document.documentElement.scrollWidth>innerWidth};})()`);
      assert.equal(layout.cues,1);assert.equal(layout.direct,true);assert.ok(Math.abs(layout.rightGap)<2,JSON.stringify(layout));
      assert.equal(layout.overlaps,false);assert.equal(layout.pageOverflow,false);
      layouts.push({case:'daily-far-right',width,zoom,...layout});
    }
    await evaluate(owner,`document.documentElement.style.zoom=''`);
    await command('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false},owner);
    const quota=await focus(mini,'.mini-accounts li:nth-child(2) .help-cue');
    assert.match(quota,/Primary quota\n5-hour[\s\S]*\n\nAdditional quotas\nWeekly[\s\S]*Native Used:[\s\S]*CCost Used:/);
    assert.doesNotMatch(quota,/Last quota update|Source:|Availability:/);
    await key(mini,'Escape');
    await evaluate(owner,`(() => {const p=structuredClone(liveValue);p.view.now_ms++;for(const card of p.view.active_cards){card.title='<script>Exact title</script> '+ 'long title '.repeat(30);card.session_summary.cost.display.known_ccost='?12';card.session_summary.cost.display_units.credits.known_ccost='?12';card.session_summary.cost.complete=false;card.state='observed';}miniWatch.update(p);p.view.now_ms++;for(const card of p.view.active_cards){card.state='retrying';card.session_summary.state='unavailable';}miniWatch.update(p);})()`);
    const title=await evaluate(mini,`document.querySelector('.mini-prompts > table .mini-session').textContent`);
    assert.ok(title.startsWith('<script>Exact title</script> '));
    assert.match(await evaluate(mini,`document.querySelector('.mini-prompts > table .mini-source-note').textContent`),/not current/);
    assert.equal(await evaluate(mini,`document.querySelectorAll('tbody .help-trigger,.mini-header .help-cue').length`),0);
    const heading=await focus(mini,'.mini-prompts > table th:first-child button');
    assert.match(heading,/Session —[^\n]+\n\nTotal CCost —[\s\S]*entire session/);
    assert.equal(await evaluate(mini,`document.querySelector('#context-help script')===null`),true);
    await key(mini,'Escape');
    await evaluate(owner,`miniWatch.update(liveValue)`);
    for (const selector of ['.watch-active tbody td:first-child .help-trigger','.watch-daily-help']) {
      const metadata=await focus(owner,selector);assert.ok(metadata.length>0);await key(owner,'Escape');
    }
    await evaluate(mini,`document.documentElement.style.fontSize='150%'`);
    await focus(mini,'.mini-prompts > table th:last-child button');
    assert.equal(await evaluate(mini,`(() => {const r=document.querySelector('#context-help').getBoundingClientRect();return r.right<=innerWidth&&r.bottom<=innerHeight;})()`),true);
    await key(mini,'Escape');await evaluate(mini,`document.documentElement.style.fontSize=''`);
    assert.equal(await evaluate(owner,`document.querySelectorAll('.watch-prompt-label .help-trigger').length`),0);
    checks.push('Verbatim selectable/accessible long hostile session title without row cues; two-part Mini heading, date reveal, consolidated daily help, retained warnings, no HTML injection and Mini 150% text zoom');
    await command('Page.bringToFront',{},owner);
    for (const route of ['models','sessions','sessions/root','accounts','reports?date=1970-01-01','token-mix','cost-per-hour','settings']) {
      await evaluate(owner,`location.hash='#/${route}'`);
      await until(owner,`document.body.dataset.section==='${route.split(/[?\/]/)[0]}'`);
      if (['token-mix','cost-per-hour'].includes(route)) await evaluate(owner,`acquire(current)`);
      await until(owner,`!current.loading && !document.getElementById('result').getAttribute('aria-busy')?.includes('true')`);
      assert.equal(await evaluate(owner,`current.failed===true`),false,route+' report is usable');
      const count=await evaluate(owner,`(async () => {const targets=[...document.querySelectorAll('#result button,#result input')].filter(n=>!n.disabled);let checked=0;for(const n of targets){n.focus();const p=document.querySelector('#context-help');if(n.getAttribute('aria-describedby')?.split(' ').includes('context-help')){if(!p.textContent||n.hasAttribute('title'))throw Error('invalid help');checked++;}}document.activeElement?.blur();return checked;})()`);
      checks.push(`${route}: rendered help/disclosure inventory (${count} focusable help targets); visible field/disclosure text retained`);
    }
    assert.deepEqual(errors,[]);
    evidence={outcome:'PASS',browser:version.product,checks,layouts,limitations:['Immediate in-memory synthetic report jobs; no report-process lifecycle proof.','Headless Chromium only; no physical desktop, screen-reader or other-engine acceptance claimed.']};
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
