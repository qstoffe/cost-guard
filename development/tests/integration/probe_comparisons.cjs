// Authenticated shipped HTTP/assets and canonical fixtures in hidden fresh-profile Chromium.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output] = process.argv.slice(2);
async function main() {
  await fs.stat(browser); await fs.stat(path.dirname(output));
  const profile = await fs.mkdtemp(path.join(path.dirname(output), 'comparison-browser-'));
  const config = await fs.mkdtemp(path.join(path.dirname(output), 'comparison-config-'));
  const server = spawn('py', ['-3', 'development/tests/integration/serve_mini_watch.py', config, '--comparisons'],
    {windowsHide:true, stdio:['pipe','pipe','pipe']});
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  let serverErrors = ''; server.stderr.on('data', chunk => serverErrors += chunk.toString());
  const child = spawn(browser, ['--headless=new','--no-first-run','--no-default-browser-check','--disable-extensions',
    '--disable-background-networking','--remote-debugging-pipe','--user-data-dir='+profile,'about:blank'],
    {windowsHide:true,stdio:['ignore','ignore','ignore','pipe','pipe']});
  const pending = new Map(); let sequence=0, buffer='', errors=[];
  child.stdio[4].on('data', chunk => {
    buffer+=chunk.toString(); let index;
    while((index=buffer.indexOf('\0'))>=0) {
      const value=JSON.parse(buffer.slice(0,index)); buffer=buffer.slice(index+1);
      if(value.id) { const item=pending.get(value.id);pending.delete(value.id);
        if(item) {clearTimeout(item.timer);value.error?item.reject(new Error(JSON.stringify(value.error))):item.resolve(value.result);} }
      else if(value.method==='Runtime.exceptionThrown') errors.push(value.params.exceptionDetails.exception?.description || value.params.exceptionDetails.text);
    }
  });
  const command=(method,params={},sessionId)=>new Promise((resolve,reject)=>{
    const id=++sequence,timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout: '+method));},15000);
    pending.set(id,{resolve,reject,timer});child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');
  });
  let tab;
  const evaluate=async expression=>{
    const result=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},tab);
    if(result.exceptionDetails)throw new Error(JSON.stringify(result.exceptionDetails));return result.result.value;
  };
  const until=async expression=>{
    const end=Date.now()+20000;
    while(Date.now()<end) {if(await evaluate(expression))return;await new Promise(resolve=>setTimeout(resolve,30));}
    throw new Error('Condition not reached: '+expression+' '+JSON.stringify({errors,serverErrors,
      state:await evaluate(`({message:current?.message,loading:current?.loading,section:current?.section})`)}));
  };
  let evidence={outcome:'FAIL'}, layouts=[]; const checks=[];
  const deadline=setTimeout(()=>{child.kill();server.kill();},150000);
  try {
    const launch=JSON.parse((await lines.next()).value);
    const target=await command('Target.createTarget',{url:'about:blank'});
    tab=(await command('Target.attachToTarget',{targetId:target.targetId,flatten:true})).sessionId;
    await command('Page.enable',{},tab);await command('Runtime.enable',{},tab);
    await command('Page.navigate',{url:launch.url},tab);
    await until(`typeof csrf!=='undefined' && csrf && hostState.writable`);
    await evaluate(`location.hash='#/comparisons'`);
    await until(`current?.section==='comparisons' && current.result && !current.loading`);
    assert.equal(await evaluate(`document.querySelectorAll('.comparison-group').length`),10, JSON.stringify({errors,
      state:await evaluate(`({message:current.message,withheld:current.withheld,groups:current.result.view.comparisons.groups.length,dom:output.innerHTML.slice(0,1200)})`)}));
    assert.equal(await evaluate(`document.querySelectorAll('.comparison-table tbody tr').length`),30);
    assert.equal(await evaluate(`document.querySelectorAll('.comparison-group img').length`),0);
    assert.equal(await evaluate(`document.querySelector('.comparison-group h3').textContent.includes('Quest <img')`),true);
    assert.deepEqual(await evaluate(`[...document.querySelectorAll('.comparison-table')[0].querySelectorAll('th')].map(n=>n.textContent)`),
      ['Session','Started','Model','Effort','CCost','Duration','Context','Token Mix','Calls']);
    assert.match(await evaluate(`document.querySelector('.comparisons-view .pager').textContent`),/Page 1 of 2.*11 groups/);
    const comparisonAX=await command('Accessibility.getFullAXTree',{},tab);
    assert.ok(comparisonAX.nodes.filter(n=>n.role?.value==='columnheader').length>=90);
    checks.push('automatic all-history acquisition; ten unframed groups, all three same-model repeats, exact columns, safe titles and links');
    for(const theme of ['classic','light','dark']) for(const width of [360,1366,1920]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},tab);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},tab);
      const layout=await evaluate(`(() => {document.documentElement.dataset.theme=${JSON.stringify(theme==='classic'?'classic':'web')};
        const group=document.querySelector('.comparison-group'), scroll=group.querySelector('.table-scroll'), css=getComputedStyle(group);
        return {overflow:document.documentElement.scrollWidth>innerWidth, border:css.borderTopWidth,
          padding:css.paddingLeft, background:css.backgroundColor, horizontal:scroll.scrollWidth>scroll.clientWidth,
          rowCount:document.querySelectorAll('.comparison-table tbody tr').length,
          numeric:[...group.querySelectorAll('td.numeric')].every(td=>getComputedStyle(td).textAlign==='right')};})()`);
      assert.equal(layout.overflow,false);assert.equal(layout.border,'0px');assert.equal(layout.padding,'0px');
      assert.equal(layout.numeric,true);assert.equal(layout.rowCount,30);
      if(width===360)assert.equal(layout.horizontal,true);
      layouts.push({theme,width,...layout});
    }
    checks.push('Classic/Web light/dark at 360/1366/1920px; unindented sections, right-aligned metrics, narrow table overflow not page overflow');
    await command('Emulation.setDeviceMetricsOverride',{width:1366,height:900,deviceScaleFactor:1,mobile:false},tab);
    await evaluate(`document.activeElement.blur();document.querySelector('.comparison-table').scrollIntoView()`);
    const point=await evaluate(`(() => {const r=document.querySelector('.comparison-table th:nth-child(7) button').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},tab);
    await until(`(() => {const panel=document.getElementById('context-help');return panel && !panel.hidden && panel.textContent.includes('Historical estimate')})()`);
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'},tab);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'},tab);
    await until(`document.getElementById('context-help').hidden`);
    await command('Emulation.setTouchEmulationEnabled',{enabled:true},tab);
    await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]},tab);
    await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},tab);
    await until(`!document.getElementById('context-help').hidden`);
    await command('Emulation.setTouchEmulationEnabled',{enabled:false},tab);
    checks.push('semantic column headers in the AX tree, real hidden mouse hover, Escape and emulated-touch contextual help');
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab'},tab);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab'},tab);
    await evaluate(`window.__target=document.querySelector('.comparison-table tbody tr td:nth-child(5) button'); __target.focus()`);
    await until(`document.getElementById('context-help') && !document.getElementById('context-help').hidden`);
    assert.match(await evaluate(`document.getElementById('context-help').textContent`),/Main:.*Linked children:/);
    await evaluate(`window.__root=current.comparisons.root;window.__calls=0;window.__api=api;api=async(p,v)=>{if(p==='/api/reports')__calls++;return __api(p,v)};acquire(current,true)`);
    await until(`!current.loading`);
    assert.equal(await evaluate(`document.activeElement===__target && __target.isConnected && current.comparisons.root===__root`),true);
    await evaluate(`ReportView.setUnit('usd',output)`);
    assert.match(await evaluate(`__target.textContent`),/\$/);
    assert.equal(await evaluate(`__calls`),1);
    checks.push('rich value help, canonical unit changes without acquisition, quiet refresh retains DOM/focus');
    await evaluate(`current.comparisons.next.click()`);await until(`!current.loading && current.result.view.comparisons.offset===10`);
    assert.equal(await evaluate(`document.querySelectorAll('.comparison-group').length`),1);
    await evaluate(`current.comparisons.previous.click()`);await until(`!current.loading && current.result.view.comparisons.offset===0`);
    await evaluate(`window.__link=document.querySelector('.comparison-table tbody a').hash; location.hash=__link`);
    await until(`location.hash===__link && document.title.startsWith('Session ')`);
    await evaluate(`history.back()`);await until(`current.section==='comparisons'`);
    checks.push('Previous/Next page comparison groups, canonical Sessions detail route and browser Back');
    await evaluate(`location.hash='#/ai-stats'`);await until(`current.section==='ai-stats' && current.result && !current.loading`);
    assert.equal(await evaluate(`document.querySelectorAll('.ai-stat').length`),11);
    assert.match(await evaluate(`document.querySelectorAll('.ai-stat')[10].textContent`),/Biggest AI Speed Gap.*3.0×/);
    checks.push('existing ten AI Stats cards preserved plus conditional eleventh matched-run fact, no separate Comparisons job');
    await evaluate(`location.hash='#/comparisons'`);await until(`current.section==='comparisons'`);
    await evaluate(`window.__hold=false;window.__release=null;api=async(p,v)=>{if(p==='/api/reports'){__calls++;if(__hold)await new Promise(r=>__release=r)}return __api(p,v)};
      __hold=true;current.checkedAt=Date.now()-300001;scheduleCachedReport()`);
    await until(`current.loading && typeof __release==='function'`);
    const before=await evaluate(`__calls`);
    await evaluate(`scheduleCachedReport();scheduleCachedReport()`);assert.equal(await evaluate(`__calls`),before);
    await evaluate(`__hold=false;__release()`);await until(`!current.loading`);
    await evaluate(`Object.defineProperty(document,'hidden',{configurable:true,value:true});current.checkedAt=Date.now()-300001;
      window.__timer=setTimeout;window.__scheduled=0;setTimeout=(...args)=>{__scheduled++;return __timer(...args)};scheduleCachedReport();setTimeout=__timer`);
    assert.equal(await evaluate(`__scheduled===0 && !current.loading`),true);
    await evaluate(`Object.defineProperty(document,'hidden',{configurable:true,value:false});location.hash='#/watch'`);await until(`current.section==='watch'`);
    assert.equal(await evaluate(`__calls`),before);
    checks.push('five-minute cache-first route cadence coalesces in-flight work; hidden/inactive routes do not admit periodic scans');
    const ax=await command('Accessibility.getFullAXTree',{},tab);assert.ok(ax.nodes.some(n=>n.name?.value==='Watch'));
    assert.deepEqual(errors,[]);
    evidence={outcome:'PASS',checks,layouts,uncaught:errors};
  } catch(error) {evidence={outcome:'FAIL',error:String(error),checks,layouts,errors,serverErrors};throw error;}
  finally {
    clearTimeout(deadline);await fs.writeFile(output,JSON.stringify(evidence,null,2));
    try {await command('Browser.close');}catch(_){}child.kill();server.stdin.write('{"command":"stop"}\n');
    await new Promise(resolve=>{server.once('close',resolve);setTimeout(resolve,3000);});server.kill();
    await fs.rm(profile,{recursive:true,force:true,maxRetries:3}).catch(()=>{});
    await fs.rm(config,{recursive:true,force:true,maxRetries:3}).catch(()=>{});
  }
}
main().catch(error=>{console.error(String(error));process.exitCode=1;});
