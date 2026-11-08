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
  const serverClosed = new Promise(resolve=>server.once('close',(code,signal)=>resolve({code,signal})));
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const fixture=async command=>{server.stdin.write(JSON.stringify({command})+'\n');return JSON.parse((await lines.next()).value);};
  let serverErrors = ''; server.stderr.on('data', value => { serverErrors += value.toString(); });
  const child = spawn(browser, ['--headless=new','--no-first-run','--no-default-browser-check','--disable-extensions',
    '--disable-background-networking','--remote-debugging-pipe','--user-data-dir='+profile,'about:blank'],
    {windowsHide:true,stdio:['ignore','ignore','ignore','pipe','pipe']});
  const browserClosed = new Promise(resolve=>child.once('close',(code,signal)=>resolve({code,signal})));
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
   const until=async (expression, target=tab, timeout=15000)=>{
     const end=Date.now()+timeout;
    while(Date.now()<end) {if(await evaluate(expression,target))return;await new Promise(resolve=>setTimeout(resolve,30));}
    const state=await evaluate(`({section:typeof current==='undefined'?null:current?.section,
      loading:typeof current==='undefined'?null:current?.loading,
      message:typeof current==='undefined'?null:current?.message,
      host:typeof hostState==='undefined'?null:hostState.kind,
      active:typeof current==='undefined'?null:current?.active,
      percent:typeof current==='undefined'?null:current?.percent,
      hidden:document.hidden})`,target);
    server.stdin.write('{"command":"jobs-status"}\n');
    const jobs=(await lines.next()).value;
    throw new Error('Condition not reached: '+expression+' '+JSON.stringify({errors,serverErrors,state,jobs}));
  };
  const layouts=[], textLayouts=[], contrasts=[], states=[], checks=[];
  let evidence={outcome:'FAIL',layouts,textLayouts,contrasts,states,checks};
  const deadline=setTimeout(()=>{child.kill();server.kill();},180000);
  try {
    const launch=JSON.parse((await lines.next()).value);
    if (process.argv.includes('--slices-only')) {
      const productionCleanup=await require('./probe_ai_stats_slices.cjs')({command,evaluate,until,config,checks});
      assert.deepEqual(errors,[]);
      evidence={outcome:'PASS',checks,runtimeErrors:errors,productionCleanup};
      return;
    }
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
    assert.equal(await evaluate(`document.getElementById('refresh').hidden && !document.getElementById('cancel')`),true);
    checks.push('automatic default, retired-route alias, ten cards, five exact periods, safe real record links, no healthy toolbar');
    await require('./probe_ai_stats_states.cjs')({command,evaluate,until,fixture,tab,contrasts,states,checks});
    await require('./probe_ai_stats_layout.cjs')({command,evaluate,until,tab,textLayouts,checks});
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
      assert.equal(layout.headings,10);
      assert.equal(new Set(layout.widths).size,1); assert.notEqual(layout.foreground,layout.background);
      layouts.push({theme,width,...layout});
    }
    checks.push('Classic/Web light/dark, 360/1366/1920px, equal column widths, no page overflow or nested scrolling (row heights checked with text geometry)');
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
    assert.match(await evaluate(`document.getElementById('context-help').textContent`),/silicon crew burns per hour/);
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
    await evaluate(`selectStats(current,'all'); void acquire(current)`);
    await until(`current.loading && !!current.active`);
    assert.equal(await evaluate(`!!output.querySelector('.ai-stat') && !output.querySelector('progress')`),true);
    assert.doesNotMatch(await evaluate(`output.textContent`),/Unavailable|vault/);
    await evaluate(`selectStats(current,'today')`);
    assert.equal(await evaluate(`!!output.querySelector('.ai-stat') && current.loading`),true,'ready smaller period remains usable during broader acquisition');
    await evaluate(`location.hash='#/accounts'`); await until(`current.section==='accounts'`);
    await evaluate(`location.hash='#/ai-stats'`); await until(`current.section==='ai-stats' && current.loading`);
    // Internal authenticated test ownership still exercises real backend cancellation.
    await evaluate(`selectStats(current,'all'); api('/api/jobs/'+current.active+'/cancel',{})`);
    await until(`current.failed && !current.loading`);
    assert.match(await evaluate(`current.message`),/cancelled/i);
    assert.equal(await evaluate(`!!output.querySelector('.ai-stat')`),true);
    await evaluate(`selectStats(current,'today')`);
    assert.equal(await evaluate(`!!output.querySelector('.ai-stat')`),true);
    await fixture('stats-release-all');
    await evaluate(`selectStats(current,'all')`); await until(`current.result && !current.loading`);
    checks.push('no UI Cancel; in-flight All time survives route departure/return; smaller scopes stay usable; direct internal API cancellation remains terminal and retry recovers');
    // Gate only the test transport, keeping the actual HTTP/job and accepted DOM.
    await evaluate(`window.__api=api; window.__calls=0; window.__hold=false; window.__fail=false;
      api=async function(path,value) { if(path==='/api/reports') { __calls++; if(__hold) await new Promise(resolve=>window.__release=resolve); if(__fail) throw new Error('synthetic_failure'); } return __api(path,value); };`);
    for(const section of ['ai-stats','token-mix']) {
      await evaluate(`location.hash='#/${section}'`);
      await until(`current?.section==='${section}'`);
      await until(`current.result && !current.loading`);
      await evaluate(`window.__accepted=current.result; window.__dom=output.firstChild;
        current.result.observed_at_ms=Date.now()-3600001;
        if(current.result.source.observed_at_ms!=null) current.result.source.observed_at_ms=current.result.observed_at_ms;
        __hold=true; current.checkedAt=Date.now()-CachedReports.cadences[current.section]-1; scheduleCachedReport();`);
      await until(`current.loading && typeof __release==='function'`);
      assert.deepEqual(await evaluate(`({retained:output.firstChild===__dom,
        withheld:!!current.withheld,progress:!!output.querySelector('progress')})`),
        {retained:true,withheld:false,progress:false},section+': aged warm refresh retains the accepted DOM');
      await evaluate(`__hold=false; __release(); window.__release=null`);
      await until(`!current.loading`);
      // TTL < age <= one hour: re-entry is immediate and quiet, one in-flight check.
      await evaluate(`current.result.observed_at_ms=Date.now()-CachedReports.cadences[current.section]-1;
        if(current.result.source.observed_at_ms!=null) current.result.source.observed_at_ms=current.result.observed_at_ms;
        __hold=true; window.__before=__calls; enterCachedReport(current); enterCachedReport(current);`);
      await until(`current.loading && typeof __release==='function'`);
      assert.equal(await evaluate(`__calls===__before+1 && !current.withheld && !output.querySelector('progress')`),true);
      await evaluate(`__hold=false; __release(); window.__release=null`); await until(`!current.loading`);
      // An aged qualified report remains visible while a genuine failed refresh is reported.
      await evaluate(`current.result.observed_at_ms=Date.now()-3600001;
        if(current.result.source.observed_at_ms!=null) current.result.source.observed_at_ms=current.result.observed_at_ms;
        window.__old=CachedReports.observation(current.result); __hold=true; __fail=true; enterCachedReport(current);`);
      await until(`current.loading && typeof __release==='function'`);
      assert.equal(await evaluate(`!current.withheld && !output.querySelector('progress') &&
        !!output.querySelector('.ai-stat,.token-mix-table') && (current.section==='ai-stats' ?
        document.getElementById('report-updating').textContent==='' : document.getElementById('report-updating').textContent.includes('Historical snapshot as of'))`),true);
      await evaluate(`__hold=false; __release(); window.__release=null`); await until(`!current.loading && current.failed`);
      assert.equal(await evaluate(`!output.querySelector('progress') && CachedReports.observation(current.result)===__old`),true);
      await evaluate(`__fail=false; acquire(current)`); await until(`!current.loading && !current.withheld && !current.failed`);
      checks.push(section+': aged completion/re-entry retains qualified content; refresh is quiet/single; genuine failure preserves original provenance; retry restores');
    }
    await evaluate(`location.hash='#/ai-stats'`); await until(`current.section==='ai-stats' && !current.loading`);
    await evaluate(`window.__savedStats=current.result; current.result=null; current.statsResults.clear();
      window.__realApi=api; api=async()=>{throw new Error('synthetic_failure')}; acquire(current);`);
    await until(`current.failed && !current.loading`);
    assert.equal(await evaluate(`document.querySelectorAll('.ai-stat-value').length`),10);
    assert.doesNotMatch(await evaluate(`output.textContent`),/Unavailable|Partial|Provisional|No data|N\/A|Unknown|Observed|≥|synthetic|snapshot interval/i);
    assert.equal(await evaluate(`[...document.querySelectorAll('.ai-stat-value')].every(node=>node.textContent.includes('0'))`),true);
    assert.equal(await evaluate(`document.querySelectorAll('.ai-stat-detail a').length`),0);
    await evaluate(`api=__realApi; AIStatsView.remember(current,__savedStats); current.failed=false; show(current)`);
    checks.push('cold failed acquisition has ten playful zero figures, no invented record links; warm failure retains fun results');
    // Server-side coalescing is exercised from independent browser documents.
    const peerId=(await command('Target.createTarget',{url:launch.url.split('#')[0]+'#/ai-stats'})).targetId;
    const peer=(await command('Target.attachToTarget',{targetId:peerId,flatten:true})).sessionId;
    await command('Runtime.enable',{},peer);
    await until(`typeof current!=='undefined' && current?.result && !current.loading`,peer);
    const one=await evaluate(`api('/api/reports',{kind:'ai-stats',stats_scope:'all'})`);
    const two=await evaluate(`api('/api/reports',{kind:'ai-stats',stats_scope:'all'})`,peer);
    assert.equal(one.id,two.id);
    checks.push('two independent tabs exercise fixture scope-job association (production coalescing/process proof is separate)');
    const productionCleanup=await require('./probe_ai_stats_slices.cjs')({command,evaluate,until,config,checks});
    assert.deepEqual(errors,[]);
    evidence={outcome:'PASS',layouts,textLayouts,contrasts,states,checks,limitations:[
      'AIStatsJobs uses immediate canonical fixture results; browser proof does not establish production spawning or coalescing.',
      'Production slice/priority/two-tab browser proof uses fixed synthetic history with valid coverage after repricing; real-source acquisition is separate.',
      'Actual screen-reader speech, native physical device/font rendering and non-Chromium engines are unverified.'
    ],runtimeErrors:errors,productionCleanup};
  } finally {
    try {
      server.stdin.write('{"command":"stop"}\n');
      await command('Browser.close').catch(()=>{});
      const [serverExit,browserExit]=await Promise.all([serverClosed,browserClosed]);
      assert.deepEqual(serverExit,{code:0,signal:null});
      assert.deepEqual(browserExit,{code:0,signal:null});
      assert.equal(serverErrors,'');
      assert.deepEqual(errors,[]);
      evidence.cleanup={serverExit,browserExit,serverErrors,runtimeErrors:errors};
    } catch(error) {
      evidence.outcome='FAIL'; evidence.cleanupError=error.message; throw error;
    } finally {
      clearTimeout(deadline);
      await fs.writeFile(output,JSON.stringify(evidence,null,2));
    }
    console.log(JSON.stringify(evidence));
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
