// Hidden fresh-profile Chromium: shipped app/HTTP/auth plus synthetic session truth.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output] = process.argv.slice(2);
async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output));
  const directory = path.dirname(output);
  const profile = await fs.mkdtemp(path.join(directory, 'sessions-browser-'));
  const config = await fs.mkdtemp(path.join(directory, 'sessions-config-'));
  const server = spawn('py', ['-3', 'development/tests/integration/serve_web_sessions.py', config],
    {windowsHide:true, stdio:['pipe','pipe','pipe']});
  const serverExit = new Promise(resolve => server.once('exit',resolve));
  let serverError = ''; server.stderr.on('data', bytes => serverError += bytes.toString());
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const fixture = async command => {server.stdin.write(JSON.stringify({command})+'\n'); return JSON.parse((await lines.next()).value);};
  const child = spawn(browser, ['--headless=new', '--no-first-run', '--no-default-browser-check', '--disable-extensions',
    '--disable-background-networking', '--remote-debugging-pipe', '--user-data-dir='+profile, 'about:blank'],
    {windowsHide:true, stdio:['ignore','ignore','ignore','pipe','pipe']});
  const browserExit = new Promise(resolve => child.once('exit',resolve));
  let sequence=0, buffer='', errors=[];
  const pending=new Map();
  child.stdio[4].on('data', bytes => {
    buffer+=bytes.toString(); let index;
    while ((index=buffer.indexOf('\0'))>=0) {
      const value=JSON.parse(buffer.slice(0,index)); buffer=buffer.slice(index+1);
      if (value.id) {
        const entry=pending.get(value.id); pending.delete(value.id);
        if (entry) { clearTimeout(entry.timer); value.error ? entry.reject(new Error(JSON.stringify(value.error))) : entry.resolve(value.result); }
      } else if (value.method==='Runtime.exceptionThrown') errors.push(value.params.exceptionDetails.text);
    }
  });
  const command=(method, params={}, sessionId) => new Promise((resolve,reject) => {
    const id=++sequence, timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout: '+method));},15000);
    pending.set(id,{resolve,reject,timer}); child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');
  });
  const deadline=setTimeout(()=>{child.kill();server.kill();},180000);
  const checks=[], layouts=[];
  let evidence={outcome:'FAIL'}, lastExpression='';
  try {
    const line=await lines.next();
    if (line.done) throw new Error('Fixture failed: '+serverError);
    const launch=JSON.parse(line.value);
    const version=await command('Browser.getVersion');
    const {targetId}=await command('Target.createTarget',{url:'about:blank'});
    const {sessionId}=await command('Target.attachToTarget',{targetId,flatten:true});
    await command('Page.enable',{},sessionId); await command('Runtime.enable',{},sessionId);
    const evaluate=async expression => {
      lastExpression=expression;
      const value=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},sessionId).catch(async error=>{
        await command('Runtime.terminateExecution',{},sessionId).catch(()=>{});
        const state=await command('Runtime.evaluate',{expression:'JSON.stringify(window.detailProbe)',returnByValue:true},sessionId).catch(()=>({}));
        evidence.debug=state; throw new Error(error.message+': '+expression.slice(0,160)+'; '+JSON.stringify(state));
      });
      if (value.exceptionDetails) throw new Error(JSON.stringify(value.exceptionDetails));
      return value.result.value;
    };
     const until=async expression => {
      const end=Date.now()+30000;
      while (Date.now()<end) {if(await evaluate(expression))return;await new Promise(resolve=>setTimeout(resolve,50));}
      throw new Error('Condition not reached: '+expression+'; '+await evaluate('document.body.innerText'));
     };
     await command('Page.addScriptToEvaluateOnNewDocument',{source:`window.reportKinds=[];
       const request=fetch;window.fetch=(url,options)=>{if(url==='/api/reports')reportKinds.push(JSON.parse(options.body).kind);return request(url,options);};`},sessionId);
     await command('Page.navigate',{url:launch.url},sessionId);
     await until('typeof csrf !== "undefined" && csrf && hostState.kind === "connected"');
     await until('current?.result && !current.loading');
     const retiredHashes=['#/reports','#/reports?date=2026-11-05','#/reports?date=2026-10-01:2026-11-05',
       '#/reports?date=2026-02-30','#/reports?date=%ZZ&sort=ccost&offset=50'];
     const captures=await evaluate('reportKinds.length');
     for(const hash of retiredHashes) {
       await command('Page.navigate',{url:launch.url.split('#')[0]+hash},sessionId);
       await until('location.hash === "#/sessions" && current?.catalog?.data?.total === 120');
       assert.equal(await evaluate('current.catalog.data.sort'),'activity');
       assert.equal(await evaluate('current.catalog.data.direction'),-1);
       assert.equal(await evaluate('document.querySelectorAll("input[type=date], #scope-controls form").length'),0);
       assert.doesNotMatch(await evaluate('document.querySelector("#result").textContent'),/Capture date report|Snapshot:|Inclusive local range/);
       assert.equal(await evaluate('reportKinds.length'),captures);
       assert.equal(await evaluate('document.querySelector("nav a[aria-current=page]").getAttribute("href")'),'#/sessions');
     }
     await evaluate("history.replaceState(null,'','/#/reports?date=invalid')");
     await command('Page.reload',{},sessionId);
     await until('location.hash === "#/sessions" && current?.catalog?.data?.total === 120');
     assert.deepEqual(await evaluate('reportKinds'),[],'cold legacy reload never starts even a Normal/date report');
     for(const width of [1920,360]) {
       await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},sessionId);
       assert.deepEqual(await evaluate('[...document.querySelectorAll("nav a")].map(node=>node.textContent)'),
         ['Models','Watch','Sessions','Accounts','Token Mix','Cost per Active Hour','Settings']);
       assert.equal(await evaluate(`[...document.querySelectorAll('a')].filter(node=>node.getAttribute('href')?.startsWith('#/reports')).length`),0);
       assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'),true);
     }
     await evaluate("location.hash='#/settings'"); await until('current.section === "settings"');
     await evaluate("location.hash='#/reports?date=invalid'"); await until('location.hash === "#/sessions"');
     await evaluate("location.hash='#/token-mix'"); await until('current.section === "token-mix"');
     await evaluate('history.back()'); await until('location.hash === "#/sessions" && current.catalog');
     await evaluate('history.back()'); await until('location.hash === "#/settings"');
     await evaluate('history.forward()'); await until('location.hash === "#/sessions" && current.catalog');
     assert.deepEqual(await evaluate('reportKinds'),[]);
     checks.push('retired-hashes-valid-invalid-reload-back-forward-no-jobs-or-date-filter-wide-narrow-nav');
     for(const section of ['token-mix','cost-per-hour']) {
       const before=await evaluate('reportKinds.length');
       await evaluate(`location.hash='#/${section}'`); await until(`current.section === '${section}'`);
       assert.equal(await evaluate('reportKinds.length'),before,'opening remains explicit');
       assert.equal(await evaluate('document.querySelector("#refresh").disabled'),false);
       await evaluate('document.querySelector("#refresh").click()');
       await until('current.result && !current.loading');
       assert.equal(await evaluate('reportKinds.at(-1)'),section);
       await evaluate('document.querySelector("#refresh").click()');
       await until('!current.loading');
       assert.equal(await evaluate('reportKinds.length'),before+2,'explicit Refresh reacquires only this report');
       const frozen=await evaluate('document.querySelector("#result").textContent');
       await fixture('hold-captures');
       await evaluate('document.querySelector("#refresh").click()');
       await until('current.active && !document.querySelector("#cancel").disabled');
       await evaluate('document.querySelector("#cancel").click()');
       await until('!current.loading && document.querySelector("#notice").textContent.includes("cancelled")');
       assert.equal(await evaluate('document.querySelector("#result").textContent'),frozen);
       await fixture('resume-captures');
     }
     assert.equal(await evaluate('reportKinds.includes("date")'),false);
     checks.push('token-mix-and-active-hour-explicit-capture-refresh-cancel-retained-result');
     await evaluate("location.hash='#/sessions'");
    await until('current?.catalog?.data?.total === 120');
    assert.deepEqual(await evaluate('[...document.querySelectorAll("#result th")].map(node=>node.textContent.replace(/ [↑↓↕]$/, ""))'),
      ['Last activity','Session name','Model','CCost','Prompts','Duration']);
    assert.equal(await evaluate('document.querySelectorAll("#result tbody tr").length'),50);
    assert.equal(await evaluate('getComputedStyle(document.querySelector(".toolbar")).display'),'none');
    assert.equal(await evaluate('document.querySelector("#scope-controls").textContent'),'');
    checks.push('minimal-six-column-catalog');
    await evaluate('document.querySelectorAll("#result th button")[4].click()');
    await until('current.catalog.data.sort === "prompts" && !current.catalog.data.pending_sort');
    assert.equal(await evaluate('current.catalog.data.total'),120);
    checks.push('cold-to-global-metric-sort-ready');
    await evaluate("location.hash='#/sessions'"); await until('current.catalog.data.sort === "activity"');
    const older=await evaluate('document.querySelector(".sessions-pager a:last-child").getAttribute("href")');
    await evaluate(`location.hash=${JSON.stringify(older)}`);
    await until('current.catalog.data.offset === 50');
    const membership=await evaluate('[...document.querySelectorAll("#result tbody tr")].map(row=>row.dataset.id)');
    const before=Date.now(); await fixture('arrive');
    await evaluate('current.catalog.load()');
    assert.deepEqual(await evaluate('[...document.querySelectorAll("#result tbody tr")].map(row=>row.dataset.id)'),membership);
    await evaluate("location.hash='#/sessions'"); await until('current.catalog.data.total === 121');
    const latency=Date.now()-before; assert.ok(latency<=30000);
    assert.equal(await evaluate('document.querySelector("#result tbody tr").dataset.id'),'root-0120');
    checks.push('stable-older-page-and-live-first-page');
    for(const theme of ['classic','light','dark']) for(const width of [1920,900,360]) for(const zoom of [1,1.5]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},sessionId);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},sessionId);
      await evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme==='classic'?'classic':'web')}; document.body.style.zoom=${zoom}`);
      const layout=await evaluate(`(() => {const pan=document.querySelector('.sessions-table-pan'),table=pan.querySelector('table'),row=table.querySelector('tbody tr');return {
        innerVertical:pan.scrollHeight>pan.clientHeight,maxHeight:getComputedStyle(pan).maxHeight,
        rows:table.querySelectorAll('tbody tr').length,nowrap:[...row.cells].every(cell=>getComputedStyle(cell).whiteSpace==='nowrap'),
        numericFit:[...row.cells].filter((_,index)=>index!==1).every(cell=>cell.scrollWidth<=cell.clientWidth+1),
        pan:pan.scrollWidth>pan.clientWidth,pageWidth:document.documentElement.scrollWidth,viewport:innerWidth};})()`);
      assert.equal(layout.innerVertical,false); assert.equal(layout.maxHeight,'none'); assert.equal(layout.nowrap,true); assert.equal(layout.numericFit,true);
      assert.ok(layout.pageWidth<=width+1); layouts.push({route:'catalog',theme,width,zoom,...layout});
    }
    await evaluate(`window.detailProbe={elements:0,updates:0};const originalElement=ReportView.element;ReportView.element=(...args)=>{detailProbe.elements++;if(detailProbe.elements>60000)throw new Error('unbounded detail nodes');return originalElement(...args);};
      const originalUpdate=SessionDetail.View.prototype.update;SessionDetail.View.prototype.update=function(data){detailProbe.updates++;detailProbe.stage='start';const result=originalUpdate.call(this,data);detailProbe.stage='done';return result;};
      document.body.style.zoom=1; location.hash='#/sessions/root-0000/live'`);
    await until('current?.detail?.data?.total === 1001');
    assert.equal(await evaluate('location.hash'),'#/sessions/root-0000');
    assert.equal(await evaluate('document.querySelectorAll("#result tbody tr").length'),1001);
    assert.equal(await evaluate('document.querySelectorAll("#result th").length'),10);
    assert.equal(await evaluate('document.querySelectorAll("#result tfoot td").length'),10);
    assert.match(await evaluate('document.querySelector("#result h1").textContent'),/Synthetic 0000/);
    assert.match(await evaluate('document.querySelector("#result").textContent'),/Session ID: root-0000/);
    for(const theme of ['classic','light','dark']) for(const width of [1920,360]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},sessionId);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},sessionId);
      await evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme==='classic'?'classic':'web')}`);
      const layout=await evaluate(`(() => {const pan=document.querySelector('.sessions-table-pan'),row=pan.querySelector('tbody tr'),running=pan.querySelector('tr.session-running');return {
        innerVertical:pan.scrollHeight>pan.clientHeight,rows:pan.querySelectorAll('tbody tr').length,
        numericFit:[...row.cells].slice(1).every(cell=>cell.scrollWidth<=cell.clientWidth+1),
        runningColors:[...running.cells].map(cell=>getComputedStyle(cell).color),foreground:getComputedStyle(row).color,
        columns:[...pan.querySelectorAll('th')].map(cell=>cell.textContent)};})()`);
      assert.equal(layout.innerVertical,false); assert.equal(layout.numericFit,true); assert.equal(new Set(layout.runningColors).size,1);
      assert.notEqual(layout.runningColors[0],layout.foreground); layouts.push({route:'detail',theme,width,...layout});
    }
    checks.push('1001-unpaged-chronological-prompts-ten-columns-themes');
    const selection=await evaluate(`(() => {const target=document.querySelectorAll('tbody tr')[500].querySelector('.session-preview');target.focus();window.scrollTo(0,target.getBoundingClientRect().top+scrollY-100);
      const range=document.createRange();range.selectNodeContents(target);getSelection().removeAllRanges();getSelection().addRange(range);window.retainedNode=target;return {text:getSelection().toString(),top:target.getBoundingClientRect().top};})()`);
    await fixture('end'); await until('current.detail.data.total === 1002');
    assert.equal(await evaluate('getSelection().toString()'),selection.text);
    assert.equal(await evaluate('retainedNode.isConnected'),true);
    assert.ok(Math.abs(await evaluate('retainedNode.getBoundingClientRect().top')-selection.top)<2);
    assert.equal(await evaluate('document.querySelectorAll("tr.session-running").length'),0);
    await evaluate('getSelection().removeAllRanges()'); await fixture('fail');
    await until('current.detail.status.textContent.includes("Source unavailable")');
    assert.equal(await evaluate('document.querySelectorAll("tbody tr").length'),1002);
    await fixture('recover'); await until('current.detail.status.hidden');
    checks.push('selection-scroll-end-outage-recovery');
    assert.deepEqual(errors,[]);
    evidence={outcome:'PASS',browser:version.product,checks,layouts,discovery_ms:latency,
      inference_calls:0,personal_profile:false,desktop_effects:false};
  } finally {
    clearTimeout(deadline); server.stdin.end();
    await command('Browser.close').catch(()=>child.kill()); await browserExit;
    await serverExit;
    await fs.writeFile(output,JSON.stringify({...evidence,checks,layouts,lastExpression,errors,serverError},null,2));
    await fs.rm(profile,{recursive:true,force:true}).catch(()=>{}); await fs.rm(config,{recursive:true,force:true}).catch(()=>{});
  }
  console.log(JSON.stringify({outcome:evidence.outcome,checks:evidence.checks,discovery_ms:evidence.discovery_ms}));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
