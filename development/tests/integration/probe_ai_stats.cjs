// Shipped authenticated HTTP/jobs/assets in hidden Chromium, never a personal profile.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output] = process.argv.slice(2);
async function main() {
  await fs.stat(browser); await fs.stat(path.dirname(output));
  const profile = await fs.mkdtemp(path.join(path.dirname(output), 'ai-stats-browser-'));
  const config = await fs.mkdtemp(path.join(path.dirname(output), 'ai-stats-config-'));
  const server = spawn('py', ['-3', 'development/tests/integration/serve_mini_watch.py', config, '--ai-stats'],
    {windowsHide:true, stdio:['pipe','pipe','pipe']});
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const fixture=async command=>{server.stdin.write(JSON.stringify({command})+'\n');return JSON.parse((await lines.next()).value);};
  let serverErrors = ''; server.stderr.on('data', value => { serverErrors += value.toString(); });
  const child = spawn(browser, ['--headless=new','--no-first-run','--no-default-browser-check','--disable-extensions',
    '--disable-background-networking','--remote-debugging-pipe','--user-data-dir='+profile,'about:blank'],
    {windowsHide:true,stdio:['ignore','ignore','ignore','pipe','pipe']});
  const pending = new Map(); let sequence = 0, buffer = '', errors = [];
  child.stdio[4].on('data', chunk => {
    buffer += chunk.toString(); let index;
    while ((index=buffer.indexOf('\0'))>=0) {
      const value=JSON.parse(buffer.slice(0,index)); buffer=buffer.slice(index+1);
      if (value.id) { const item=pending.get(value.id); pending.delete(value.id);
        if(item) {clearTimeout(item.timer);value.error?item.reject(new Error(JSON.stringify(value.error))):item.resolve(value.result);} }
      else if(value.method==='Runtime.exceptionThrown') errors.push(value.params.exceptionDetails.exception?.description?.split('\n')[0] || value.params.exceptionDetails.text);
    }
  });
  const command=(method,params={},sessionId)=>new Promise((resolve,reject)=>{
    const id=++sequence,timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout: '+method));},15000);
    pending.set(id,{resolve,reject,timer});child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');
  });
  let tab;
  const evaluate=async (expression, target=tab)=>{
    const value=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},target);
    if(value.exceptionDetails) throw new Error(JSON.stringify(value.exceptionDetails)); return value.result.value;
  };
  const until=async (expression, target=tab)=>{
    const end=Date.now()+15000;
    while(Date.now()<end) {if(await evaluate(expression,target))return;await new Promise(resolve=>setTimeout(resolve,30));}
    const state=await evaluate(`({section:typeof current==='undefined'?null:current?.section,
      loading:typeof current==='undefined'?null:current?.loading,
      message:typeof current==='undefined'?null:current?.message,
      host:typeof hostState==='undefined'?null:hostState.kind})`,target);
    server.stdin.write('{"command":"jobs-status"}\n');
    const jobs=(await lines.next()).value;
    throw new Error('Condition not reached: '+expression+' '+JSON.stringify({errors,serverErrors,state,jobs}));
  };
  const layouts=[], checks=[]; let evidence={outcome:'FAIL'};
  const deadline=setTimeout(()=>{child.kill();server.kill();},180000);
  try {
    const launch=JSON.parse((await lines.next()).value);
    const {targetId}=await command('Target.createTarget',{url:'about:blank'});
    tab=(await command('Target.attachToTarget',{targetId,flatten:true})).sessionId;
    await command('Page.enable',{},tab); await command('Runtime.enable',{},tab);
    await command('Page.navigate',{url:launch.url},tab);
    await until(`typeof csrf!=='undefined' && csrf && hostState.writable`);
    await evaluate(`location.hash='#/cost-per-hour'`);
    await until(`current?.section==='ai-stats' && current.result && !current.loading`);
    assert.equal(await evaluate(`location.hash`),'#/ai-stats');
    assert.equal(await evaluate(`current.period`),'30-days');
    assert.equal(await evaluate(`document.querySelectorAll('.ai-stat').length`),10);
    assert.deepEqual(await evaluate(`[...document.querySelectorAll('.ai-stats-periods button')].map(b=>b.textContent)`),
      ['Today','7 days','30 days','This month','All time']);
    assert.equal(await evaluate(`document.querySelectorAll('.ai-stats-view img').length`),0);
    assert.equal(await evaluate(`[...document.querySelectorAll('.ai-stat-detail a')].every(a=>a.textContent.includes('<img') && a.hash.startsWith('#/sessions/'))`),true);
    assert.equal(await evaluate(`document.getElementById('refresh').hidden && document.getElementById('cancel').hidden`),true);
    checks.push('automatic default, retired-route alias, ten cards, five exact periods, safe real record links, no healthy toolbar');
    for(const theme of ['classic','light','dark']) for(const width of [360,1366,1920]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},tab);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},tab);
      const layout=await evaluate(`(() => {
        document.documentElement.dataset.theme=${JSON.stringify(theme==='classic'?'classic':'web')};
        const cards=[...document.querySelectorAll('.ai-stat')], rects=cards.map(c=>c.getBoundingClientRect());
        return {count:cards.length, pageOverflow:document.documentElement.scrollWidth>innerWidth,
          heights:rects.map(r=>Math.round(r.height)), widths:rects.map(r=>Math.round(r.width)),
          badScroll:cards.some(c=>c.scrollHeight>c.clientHeight+1),
          headings:document.querySelectorAll('.ai-stat h4 .help-trigger').length,
          foreground:getComputedStyle(document.querySelector('[aria-pressed="true"]')).color,
          background:getComputedStyle(document.querySelector('[aria-pressed="true"]')).backgroundColor}; })()`);
      assert.equal(layout.count,10); assert.equal(layout.pageOverflow,false); assert.equal(layout.badScroll,false);
      assert.equal(layout.headings,10); assert.equal(new Set(layout.heights).size,1);
      assert.equal(new Set(layout.widths).size,1); assert.notEqual(layout.foreground,layout.background);
      layouts.push({theme,width,...layout});
    }
    checks.push('Classic/Web light/dark, 360/1366/1920px, equal geometry, no page overflow or nested scrolling');
    await evaluate(`window.__root=current.stats.root; window.__cards=[...document.querySelectorAll('.ai-stat')];
      window.__observation=current.result.observed_at_ms; selectStats(current,'today'); selectStats(current,'7-days'); selectStats(current,'30-days');`);
    assert.equal(await evaluate(`current.result.observed_at_ms===__observation && !current.loading && __cards.every((c,i)=>c===document.querySelectorAll('.ai-stat')[i])`),true);
    await evaluate(`ReportView.setUnit('usd',output); ReportView.setUnit('credits',output)`);
    assert.equal(await evaluate(`current.result.observed_at_ms===__observation && !current.loading`),true);
    await evaluate(`selectStats(current,'all')`);
    await until(`!current.loading && current.result?.view.ai_stats.some(r=>r.period==='all')`);
    checks.push('period and unit changes reuse scope without acquisition; lazy All time completes');
    const ax=await command('Accessibility.getFullAXTree',{},tab);
    for(const name of ['AI Hourly Rate','Total AI Cost','AI Working Time','Average Cost per Session',
      'Most Expensive Session','Longest Session','Busiest Day','Night Owl','Coding Streak','Peak Parallel Sessions'])
      assert.ok(ax.nodes.some(node=>node.name?.value===name));
    await evaluate(`document.querySelectorAll('.ai-stat h4 button')[0].focus()`);
    await until(`!document.getElementById('context-help')?.hidden`);
    assert.match(await evaluate(`document.getElementById('context-help').textContent`),/human time saved/);
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'},tab);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'},tab);
    await until(`document.getElementById('context-help').hidden`);
    const key=async (key,code,modifiers=0)=>{
      const windowsVirtualKeyCode={Tab:9,Enter:13,Space:32}[code];
      await command('Input.dispatchKeyEvent',{type:'keyDown',key,code,modifiers,windowsVirtualKeyCode,
        ...(code==='Enter'?{text:'\r'}:code==='Space'?{text:' '}:{})},tab);
      await command('Input.dispatchKeyEvent',{type:'keyUp',key,code,modifiers,windowsVirtualKeyCode},tab);
    };
    await evaluate(`document.querySelectorAll('.ai-stats-periods button')[0].focus()`);
    await key('Tab','Tab'); assert.equal(await evaluate(`document.activeElement.textContent`),'7 days');
    await key('Enter','Enter'); await until(`current.period==='7-days'`);
    await key('Tab','Tab',8); assert.equal(await evaluate(`document.activeElement.textContent`),'Today');
    await key(' ','Space'); await until(`current.period==='today'`);
    await command('Emulation.setTouchEmulationEnabled',{enabled:true},tab);
    const touch=await evaluate(`(() => {const b=document.querySelectorAll('.ai-stats-periods button')[2];b.scrollIntoView();const r=b.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
    await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch]},tab);
    await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},tab);
    await until(`current.period==='30-days'`);
    await command('Emulation.setTouchEmulationEnabled',{enabled:false},tab);
    checks.push('all ten AX names, intrinsic title help, Tab/Shift-Tab traversal, Enter/Space activation, emulated touch period activation, Escape');
    await fixture('stats-hold-all');
    await evaluate(`current.statsResults.delete('all'); selectStats(current,'all')`);
    await until(`current.loading && !!current.active`);
    await evaluate(`selectStats(current,'today')`);
    assert.equal(await evaluate(`!!output.querySelector('.ai-stat') && current.loading`),true,'ready smaller period remains usable during broader acquisition');
    await evaluate(`location.hash='#/accounts'`); await until(`current.section==='accounts'`);
    await evaluate(`location.hash='#/ai-stats'`); await until(`current.section==='ai-stats' && current.loading`);
    await evaluate(`selectStats(current,'all'); document.getElementById('cancel').click()`);
    await until(`current.failed && !current.loading`);
    assert.match(await evaluate(`current.message`),/cancelled/i);
    assert.equal(await evaluate(`!!output.querySelector('.ai-stat')`),false);
    await evaluate(`selectStats(current,'today')`);
    assert.equal(await evaluate(`!!output.querySelector('.ai-stat')`),true);
    await fixture('stats-release-all');
    await evaluate(`selectStats(current,'all')`); await until(`current.result && !current.loading`);
    checks.push('in-flight All time survives route departure/return without duplicate; cached smaller scopes stay usable; cancel is terminal/nonzero and retry recovers');
    // Gate only the test transport, keeping the actual HTTP/job and accepted DOM.
    await evaluate(`window.__api=api; window.__calls=0; window.__hold=false; window.__fail=false;
      api=async function(path,value) { if(path==='/api/reports') { __calls++; if(__hold) await new Promise(resolve=>window.__release=resolve); if(__fail) throw new Error('synthetic_failure'); } return __api(path,value); };`);
    for(const section of ['ai-stats','token-mix']) {
      await evaluate(`location.hash='#/${section}'`);
      await until(`current?.section==='${section}'`);
      if(section==='token-mix') await evaluate(`acquire(current)`);
      await until(`current.result && !current.loading`);
      await evaluate(`window.__accepted=current.result; window.__dom=output.firstChild;
        current.result.observed_at_ms=Date.now()-3600001;
        if(current.result.source.observed_at_ms!=null) current.result.source.observed_at_ms=current.result.observed_at_ms;
        __hold=true; current.checkedAt=Date.now()-CachedReports.cadences[current.section]-1; scheduleCachedReport();`);
      await until(`current.loading && typeof __release==='function'`);
      assert.equal(await evaluate(`output.firstChild===__dom && !current.withheld && !output.querySelector('progress')`),true);
      await evaluate(`__hold=false; __release(); window.__release=null`);
      await until(`!current.loading`);
      // TTL < age <= one hour: re-entry is immediate and quiet, one in-flight check.
      await evaluate(`current.result.observed_at_ms=Date.now()-CachedReports.cadences[current.section]-1;
        if(current.result.source.observed_at_ms!=null) current.result.source.observed_at_ms=current.result.observed_at_ms;
        __hold=true; window.__before=__calls; enterCachedReport(current); enterCachedReport(current);`);
      await until(`current.loading && typeof __release==='function'`);
      assert.equal(await evaluate(`__calls===__before+1 && !current.withheld && !output.querySelector('progress')`),true);
      await evaluate(`__hold=false; __release(); window.__release=null`); await until(`!current.loading`);
      // >one-hour return must withhold, terminate failure and retain last success.
      await evaluate(`current.result.observed_at_ms=Date.now()-3600001;
        if(current.result.source.observed_at_ms!=null) current.result.source.observed_at_ms=current.result.observed_at_ms;
        window.__old=CachedReports.observation(current.result); __hold=true; __fail=true; enterCachedReport(current);`);
      await until(`current.loading && typeof __release==='function'`);
      assert.equal(await evaluate(`current.withheld && !!output.querySelector('progress') && !output.querySelector('.ai-stat') && !output.querySelector('.token-mix-table')`),true);
      await evaluate(`__hold=false; __release(); window.__release=null`); await until(`!current.loading && current.failed`);
      assert.equal(await evaluate(`!output.querySelector('progress') && CachedReports.observation(current.result)===__old`),true);
      await evaluate(`__fail=false; acquire(current)`); await until(`!current.loading && !current.withheld && !current.failed`);
      checks.push(section+': active >60m retains DOM; TTL re-entry quiet/single; >60m re-entry withholds; failure terminates and preserves provenance; retry restores');
    }
    // Server-side coalescing is exercised from independent browser documents.
    const peerId=(await command('Target.createTarget',{url:launch.url.split('#')[0]+'#/ai-stats'})).targetId;
    const peer=(await command('Target.attachToTarget',{targetId:peerId,flatten:true})).sessionId;
    await command('Runtime.enable',{},peer);
    await until(`typeof current!=='undefined' && current?.result && !current.loading`,peer);
    const one=await evaluate(`api('/api/reports',{kind:'ai-stats',stats_scope:'all'})`);
    const two=await evaluate(`api('/api/reports',{kind:'ai-stats',stats_scope:'all'})`,peer);
    assert.equal(one.id,two.id);
    checks.push('two independent tabs exercise fixture scope-job association (production coalescing/process proof is separate)');
    assert.deepEqual(errors,[]);
    evidence={outcome:'PASS',layouts,checks,limitations:[
      'AIStatsJobs uses immediate canonical fixture results; browser proof does not establish production spawning or coalescing.',
      'Production finite-process/coalescing tests and real-source acquisition probes are separate.',
      'Actual screen-reader speech, native physical device/font rendering and non-Chromium engines are unverified; scoped Decision Delegate exception applies.'
    ],runtimeErrors:errors};
    console.log(JSON.stringify({outcome:evidence.outcome,checks:checks.length,layouts:layouts.length}));
  } finally {
    clearTimeout(deadline); await fs.writeFile(output,JSON.stringify(evidence,null,2));
    server.stdin.write('{"command":"stop"}\n');
    await command('Browser.close').catch(()=>{});
    await new Promise(resolve=>server.once('exit',resolve));
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
