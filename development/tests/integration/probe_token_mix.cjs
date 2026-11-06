// Shipped authenticated HTTP/CSP/app in hidden Chromium; no personal profile or model work.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output, cadence] = process.argv.slice(2);
async function main() {
  await fs.stat(browser); await fs.stat(path.dirname(output));
  const profile = await fs.mkdtemp(path.join(path.dirname(output), 'token-mix-browser-'));
  const config = await fs.mkdtemp(path.join(path.dirname(output), 'token-mix-config-'));
  const server = spawn('py', ['-3', 'development/tests/integration/serve_mini_watch.py', config, '--token-mix'],
    {windowsHide:true, stdio:['pipe','pipe','pipe']});
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
      else if (value.method==='Runtime.exceptionThrown') errors.push(value.params.exceptionDetails.exception?.description?.split('\n')[0] || value.params.exceptionDetails.text);
    }
  });
  const command=(method,params={},sessionId)=>new Promise((resolve,reject)=>{
    const id=++sequence,timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout: '+method));},15000);
    pending.set(id,{resolve,reject,timer});child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');
  });
  let tab;
  const evaluate=async expression=>{
    const value=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},tab);
    if(value.exceptionDetails) throw new Error(JSON.stringify(value.exceptionDetails)); return value.result.value;
  };
  const until=async (expression, timeout=15000)=>{
    const end=Date.now()+timeout;
    while(Date.now()<end) {if(await evaluate(expression))return;await new Promise(resolve=>setTimeout(resolve,40));}
    const state=await evaluate(`({section:current?.section, loading:current?.loading, message:current?.message,
      resultKind:current?.result?.view?.kind, host:hostState.kind, refreshDisabled:document.getElementById('refresh').disabled,
      notice:document.getElementById('notice').textContent})`);
    throw new Error('Condition not reached: '+expression+' '+JSON.stringify({state,errors}));
  };
  const layouts=[], checks=[]; let evidence={outcome:'FAIL'};
  const deadline=setTimeout(()=>{child.kill();server.kill();},390000);
  try {
    const launch=JSON.parse((await lines.next()).value); // Credential stays in this private pipe.
    const {targetId}=await command('Target.createTarget',{url:'about:blank'});
    tab=(await command('Target.attachToTarget',{targetId,flatten:true})).sessionId;
    await command('Page.enable',{},tab); await command('Runtime.enable',{},tab);
    await command('Emulation.setDeviceMetricsOverride',{width:1366,height:900,deviceScaleFactor:1,mobile:false},tab);
    await command('Page.navigate',{url:launch.url},tab);
    await until(`typeof csrf!=='undefined' && csrf && hostState.writable`);
    await evaluate(`location.hash='#/token-mix'`);
    await until(`current?.section==='token-mix'`);
    assert.equal(await evaluate(`!!current.result`), false, 'navigation alone does not load deep history');
    await until(`!document.getElementById('refresh').disabled`);
    await evaluate(`document.getElementById('refresh').click()`);
    await until(`current?.result?.view?.kind==='token-mix' && !current.loading`);
    const loadedAt=await evaluate(`current.checkedAt`);
    const rows=await evaluate(`current.result.view.model_token_mix`);
    assert.equal(rows.length,65);
    for (const theme of ['classic','light','dark']) for (const width of [360,1366,1920]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},tab);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},tab);
      const layout=await evaluate(`(() => {
        document.documentElement.dataset.theme=${JSON.stringify(theme==='classic'?'classic':'web')};
        const pans=[...document.querySelectorAll('.token-mix-pan')], tables=[...document.querySelectorAll('.token-mix-table')];
        return {tables:tables.length, rows:tables.map(t=>t.tBodies[0].rows.length), columns:tables.map(t=>t.tHead.rows[0].cells.length),
          vertical:pans.map(p=>p.scrollHeight>p.clientHeight), horizontal:pans.map(p=>p.scrollWidth>p.clientWidth),
          nowrap:tables.every(t=>[...t.rows].every(r=>[...r.cells].every(c=>getComputedStyle(c).whiteSpace==='nowrap'))),
          boxed:document.querySelectorAll('.token-mix-section').length && [...document.querySelectorAll('.token-mix-section')].some(s=>getComputedStyle(s).borderTopWidth!=='0px'),
          prose:/Snapshot|Reading this report|Sample and price coverage|Token category order|\\?/.test(document.getElementById('result').textContent),
          tooltipTargets:document.querySelectorAll('.token-mix-table th .help-label').length}; })()`);
      assert.equal(layout.tables,2); assert.deepEqual(layout.rows,[65,65]); assert.deepEqual(layout.columns,[13,13]);
      assert.deepEqual(layout.vertical,[false,false]); assert.equal(layout.nowrap,true); assert.equal(layout.boxed,false);
      assert.equal(layout.prose,false); assert.equal(layout.tooltipTargets,26);
      if(width===360) assert.deepEqual(layout.horizontal,[true,true]);
      layouts.push({theme,width,...layout});
    }
    checks.push('three themes, three widths, 65 uncapped single-line rows, 13 columns, horizontal-only panning, text help');
    const publishers=await evaluate(`document.querySelectorAll('tbody')[1].textContent`);
    const total=await evaluate(`current.tokenMix.title.textContent`);
    function fraction(value) {
      if(value==null) return null;
      const match=/^(\d+)(?:\.(\d*))?(?:E([+-]?\d+))?$/i.exec(String(value));
      const exponent=Number(match[3]||0)-(match[2]||'').length;
      return exponent>=0 ? [BigInt(match[1]+(match[2]||''))*10n**BigInt(exponent),1n] :
        [BigInt(match[1]+(match[2]||'')),10n**BigInt(-exponent)];
    }
    const compare=(a,b,direction)=> {
      if(a==null||b==null) return a==null?b==null?0:1:-1;
      const left=a[0]*b[1],right=b[0]*a[1]; return (left<right?-1:left>right?1:0)*direction;
    };
    const metric=(row,col)=> {
      if(col===1||col===2) return fraction(col===1?row.prompts:row.calls);
      if(col===3) return fraction(row.mix.known_total_tokens);
      if(col===12) return row.mix.priced_requests?fraction(row.mix.total_cost):null;
      const index=Math.floor((col-4)/2);
      if(col%2) return row.mix.priced_requests?fraction(row.mix.costs?.[index]):null;
      return row.mix.shares[index]==null?null:[BigInt(row.mix.exact_totals[index]),BigInt(row.mix.exact_total_tokens)];
    };
    for (const [table,key] of [[0,'model'],[1,'publisher']]) {
      const source=table?await evaluate(`current.result.view.publisher_token_mix`):rows;
      const other=await evaluate(`document.querySelectorAll('tbody')[${1-table}].textContent`);
      for(let col=0;col<13;col++) for(const direction of [1,-1]) {
        await evaluate(`document.querySelectorAll('.token-mix-table')[${table}].tHead.rows[0].cells[${col}].querySelector('button').click()`);
        const actual=await evaluate(`[...document.querySelectorAll('.token-mix-table')[${table}].tBodies[0].rows].map(row=>row.cells[0].textContent)`);
        const expected=[...source].sort((a,b)=>(col===0?a[key].localeCompare(b[key])*direction:compare(metric(a,col),metric(b,col),direction))||
          b.calls-a.calls||a[key].localeCompare(b[key],undefined,{numeric:true})).map(row=>row[key]);
        assert.deepEqual(actual,expected,'exact '+key+' column '+col+' direction '+direction);
        assert.equal(await evaluate(`document.querySelectorAll('tbody')[${1-table}].textContent`),other);
        assert.equal(await evaluate(`current.tokenMix.title.textContent`),total);
      }
    }
    checks.push('all 26 headings sort both directions by exact independent expectations; unknown last, other table/total untouched');
    await evaluate(`document.querySelector('.token-mix-table th button').focus()`);
    await until(`document.getElementById('context-help')?.hidden===false`);
    assert.equal(await evaluate(`document.querySelectorAll('.token-mix-table [title]').length`),0);
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape'},tab);
    await until(`document.getElementById('context-help').hidden`);
    checks.push('keyboard-focused contextual help and Escape, no duplicate native titles');
    await evaluate(`ReportView.setUnit('usd',current.tokenMix.root)`);
    assert.equal(await evaluate(`document.querySelectorAll('tbody')[1].textContent===${JSON.stringify(publishers)}`),false);
    await evaluate(`ReportView.setUnit('credits',current.tokenMix.root); location.hash='#/settings'`);
    await until(`current.section==='settings'`);
    await evaluate(`location.hash='#/token-mix'`);
    await until(`current.section==='token-mix'`);
    assert.equal(await evaluate(`current.result.sequence`),1,'return reuses captured data without another job');
    await command('Emulation.setDeviceMetricsOverride',{width:360,height:900,deviceScaleFactor:1,mobile:false},tab);
    // Select name ordering so updated costs do not intentionally reorder the anchor rows.
    await evaluate(`document.querySelector('.token-mix-table th button').click()`);
    await evaluate(`globalThis.retainedRoot=current.tokenMix.root; globalThis.retainedRows=[...document.querySelectorAll('tbody tr')];
      globalThis.retainedButton=document.querySelector('.token-mix-table th button'); retainedButton.focus();
      document.querySelector('.token-mix-pan').scrollLeft=200; window.scrollTo(0,500);
      globalThis.retainedX=document.querySelector('.token-mix-pan').scrollLeft; globalThis.retainedY=window.scrollY;
      globalThis.oldValue=current.tokenMix.summary.textContent`);
    assert.ok(await evaluate(`retainedX>0`),'refresh proof starts with a genuinely panned narrow table');
    if(cadence!=='--wall-clock') await evaluate(`current.checkedAt=Date.now()-300001; scheduleTokenMix()`);
    await until(`current.loading`,cadence==='--wall-clock'?315000:15000);
    const startedAt=await evaluate(`Date.now()`);
    if(cadence==='--wall-clock') assert.ok(startedAt-loadedAt>=299000 && startedAt-loadedAt<312000);
    assert.equal(await evaluate(`current.tokenMix.summary.textContent===oldValue && current.tokenMix.root===retainedRoot && document.getElementById('result').getAttribute('aria-busy')==='false' && document.getElementById('notice').textContent===''`),true);
    await until(`!current.loading && current.result.sequence===2`);
    const retained=await evaluate(`({root:current.tokenMix.root===retainedRoot,rows:retainedRows.every(row=>row.isConnected),
      focus:document.activeElement===retainedButton,x:document.querySelector('.token-mix-pan').scrollLeft,expectedX:retainedX,
      y:window.scrollY,expectedY:retainedY,changed:current.tokenMix.summary.textContent!==oldValue})`);
    evidence.retained=retained;
    assert.ok(retained.root && retained.rows && retained.focus && retained.x===retained.expectedX &&
      retained.y===retained.expectedY && retained.changed,'quiet coherent replacement '+JSON.stringify(retained));
    checks.push(cadence==='--wall-clock'?'real approximately-five-minute check and slow coherent replacement':'virtual overdue check and slow coherent replacement');
    assert.deepEqual(errors,[]);
    evidence={outcome:'PASS',checks,layouts,cadence_ms:startedAt-loadedAt,
      limitations:['Synthetic browser history; real installation performance is measured by the separate read-only process probe.','No physical OS input or screen-reader proof.']};
  } catch (error) {
    evidence={...evidence,outcome:'FAIL',checks,layouts,error:String(error.stack || error),errors};
    throw error;
  } finally {
    clearTimeout(deadline);
    await command('Browser.close').catch(()=>child.kill());
    server.stdin.end('{"command":"stop"}\n');
    await fs.writeFile(output,JSON.stringify(evidence,null,2)+'\n');
  }
  console.log(JSON.stringify(evidence));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
