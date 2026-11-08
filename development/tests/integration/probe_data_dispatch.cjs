// Shipped HTTP/CSRF/assets and host registry in a fresh hidden Chromium profile.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const {setTimeout: pause} = require('node:timers/promises');

async function main() {
  const [browser, directory] = process.argv.slice(2), output = path.resolve(directory);
  await fs.mkdir(output, {recursive:true}); await fs.stat(browser);
  const profile = await fs.mkdtemp(path.join(output, 'browser-'));
  const config = await fs.mkdtemp(path.join(output, 'config-'));
  const server = spawn('py', ['-3', 'development/tests/integration/serve_data_dispatch.py', config],
    {windowsHide:true, stdio:['pipe','pipe','pipe']});
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  let serverErrors = ''; server.stderr.on('data', value => serverErrors += value.toString());
  const fixture = async action => { server.stdin.write(JSON.stringify({command:action})+'\n');
    return JSON.parse((await lines.next()).value); };
  const child = spawn(browser, ['--headless=new','--no-first-run','--no-default-browser-check',
    '--disable-extensions','--disable-background-networking','--remote-debugging-pipe','--user-data-dir='+profile,'about:blank'],
    {windowsHide:true, stdio:['ignore','ignore','ignore','pipe','pipe']});
   const pending = new Map(), errors = [], retryTypes = []; let sequence = 0, buffer = '', tab;
  child.stdio[4].on('data', chunk => { buffer += chunk.toString(); let end;
    while ((end=buffer.indexOf('\0'))>=0) { const value=JSON.parse(buffer.slice(0,end)); buffer=buffer.slice(end+1);
      const entry=pending.get(value.id);
      if(entry) { pending.delete(value.id); clearTimeout(entry.timer); value.error ? entry.reject(new Error(JSON.stringify(value.error))) : entry.resolve(value.result); }
       else if(value.method==='Runtime.exceptionThrown') errors.push(value.params.exceptionDetails.text);
       else if(value.method==='Network.requestWillBeSent' && value.params.request.url.endsWith('/api/data'))
         retryTypes.push(typeof JSON.parse(value.params.request.postData).retry);
    }
  });
  const command = (method, params={}, sessionId=tab) => new Promise((resolve,reject) => {
    const id=++sequence, timer=setTimeout(()=>reject(new Error('CDP timeout '+method)),20000);
    pending.set(id,{resolve,reject,timer}); child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');
  });
  const evaluate = async expression => { const value=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
    assert.equal(value.exceptionDetails,undefined,JSON.stringify(value.exceptionDetails)); return value.result.value; };
  const until = async expression => {
    const ready = await evaluate(`new Promise(resolve=>{const end=Date.now()+15000;
      const check=()=>{if(${expression})resolve(true);else if(Date.now()>end)resolve(false);else setTimeout(check,30);};check();})`);
    if (!ready) console.log(JSON.stringify({browser:await evaluate(`({title:document.title,
      host:typeof hostState==='undefined'?null:hostState.kind,
      view:typeof current==='undefined'?null:{section:current?.section,loading:current?.loading,
        failed:current?.failed,message:current?.message,stage:current?.stage}})`),host:await fixture('status')}));
    assert.equal(ready,true,expression+' '+serverErrors);
  };
  const facts=[]; let outcome='FAIL';
  const deadline=setTimeout(()=>{child.kill();server.kill();},180000);
  try {
    const launch=JSON.parse((await lines.next()).value);
    const target=await command('Target.createTarget',{url:'about:blank'});
    tab=(await command('Target.attachToTarget',{targetId:target.targetId,flatten:true})).sessionId;
     await command('Runtime.enable'); await command('Page.enable'); await command('Network.enable');
    await command('Page.navigate',{url:launch.url});
    await until(`typeof current!=='undefined' && !!current?.result && !current.loading`);
    const end=Date.now()+75000; let status;
    do { status=await fixture('status'); if(status.ready.length===4)break; await pause(100); } while(Date.now()<end);
    assert.equal(status.ready.length,4,'unvisited top-level reports warmed on the host');
    facts.push('all four reports warm without navigation');
    for(const section of ['token-mix','ai-stats','comparisons','models']) {
      await evaluate(`location.hash='#/${section}'`);
      await until(`current.section==='${section}' && !!current.result && !current.loading && !current.withheld`);
      assert.equal(await evaluate(`!!document.querySelector('.report-loading')`),false);
       assert.equal(await evaluate(`!!document.querySelector('#cancel')`),false);
       if(section!=='models') {
         const partial=await evaluate(`output.textContent`);
         assert.match(partial,/3 changing root sessions could not be verified and were omitted/);
         assert.match(partial,/do not cover the full source/);
       }
     }
     assert.match(await evaluate(`document.getElementById('host-details').textContent`),/Reports refresh through the host/);
     assert.deepEqual(await evaluate(`[null,-1,1.5,'3',Number.MAX_SAFE_INTEGER+1].map(count=>
       ReportView.historyWarning({source:{status:'partial',omitted_roots:count}}))`),
       Array(5).fill('Partial source history. Values may be incomplete.'));
     assert.equal(await evaluate(`ReportView.historyWarning({source:{status:'partial',omitted_roots:1}}).includes('1 changing root session could')`),true);
     assert.equal(await evaluate(`ReportView.historyWarning({source:{status:'acquired',omitted_roots:3}})`),'');
     facts.push('all three historical views expose verified omission count and incomplete totals');
     await evaluate(`(async()=>{window.__content=output.firstChild;await acquire(current,true);return true;})()`);
    assert.equal(await evaluate(`output.firstChild===__content`),true,'unchanged warm lookup retains DOM');
    assert.equal((await fixture('status')).jobs,status.jobs,'browser lookup creates no new acquisition');
      facts.push('warm route entry and quiet lookup preserve content without duplicate jobs');
      const retryAttempts = await evaluate(`(async()=>{const original=api, attempts=[];
        api=async(url,body,...rest)=>{if(url==='/api/data'){attempts.push(body.retry);
          if(attempts.length===1)throw Object.assign(new Error('source_starting'),{retryable:true});}
          return original(url,body,...rest);};
        try{current.failed=true;await acquire(current);return attempts;}finally{api=original;}})()`);
      assert.deepEqual(retryAttempts,[true,false],'automatic admission retries cannot repeatedly clear host backoff');
       facts.push('explicit Retry clears backoff only once across transient admission failure');
       const transientResult = await evaluate(`(async()=>{const original=api;
         api=async(url,...rest)=>{const value=await original(url,...rest);
           return url==='/api/data'?{...value,error:'source_unavailable',terminal:false}:value;};
         try{await acquire(current,true);return {failed:current.failed,error:current.dispatchError,retry:!refresh.hidden};}
         finally{api=original;}})()`);
       assert.deepEqual(transientResult,{failed:false,error:null,retry:false},'a usable result supersedes a transient admission error');
       const terminalResult = await evaluate(`(async()=>{const original=api;
         api=async(url,...rest)=>{const value=await original(url,...rest);
           return url==='/api/data'?{...value,error:'http_auth_failure',terminal:true}:value;};
         try{await acquire(current,true);return {failed:current.failed,message:current.message,retry:!refresh.hidden};}
         finally{api=original;}})()`);
       assert.equal(terminalResult.failed,true);assert.equal(terminalResult.retry,true);
       assert.match(terminalResult.message,/Source authentication failed/,'terminal source faults remain visible beside retained data');
       await evaluate(`(async()=>{await acquire(current,true);return true;})()`);
       assert.equal(await evaluate(`current.failed || !!current.dispatchError || !refresh.hidden`),false,'a new healthy lookup clears an old terminal notice');
       facts.push('transient admission errors cannot overwrite success; terminal source faults survive until a healthy lookup');
     await fixture('invalidate'); await evaluate(`acquire(current,true);true`);
     await until(`current.loading && current.withheld && !!document.querySelector('.report-loading')`);
     await fixture('complete'); await until(`!!current.result && !current.loading && !current.withheld`);
     facts.push('host dependency invalidation withholds even a locally young result');
    await evaluate(`location.hash='#/sessions'`);
    await until(`current.catalog?.data?.epoch && current.catalog.data.view.session_usage.length===50`);
    await evaluate(`location.hash='#/sessions?offset=450&epoch='+current.catalog.data.epoch+'&sort=activity&direction=-1'`);
    await until(`current.catalog?.data?.offset===450 && current.catalog.data.view.session_usage.length===50`);
    await evaluate(`window.__rows=current.catalog.data.view.session_usage.map(row=>row.session_id);location.hash='#/watch'`);
    await until(`current.section==='watch'`);
    await evaluate(`document.querySelector('nav a[href="#/sessions"]').click();true`);
    await until(`current.section==='sessions' && current.catalog?.data?.offset===450`);
    assert.deepEqual(await evaluate(`current.catalog.data.view.session_usage.map(row=>row.session_id)`),await evaluate(`__rows`));
    facts.push('Sessions main navigation restores page 10 and its stable fifty rows');
    // Earlier dependency invalidation cleared every product; first qualify this scope again.
    await evaluate(`location.hash='#/token-mix'`);
    await until(`current.section==='token-mix' && !!current.result && !current.loading && !current.withheld`);
    await fixture('age');
    const peer=await command('Target.createTarget',{url:'about:blank'});
    tab=(await command('Target.attachToTarget',{targetId:peer.targetId,flatten:true})).sessionId;
    await command('Runtime.enable');await command('Page.enable');
    await command('Page.navigate',{url:launch.url.split('#')[0]+'#/token-mix'});
    await until(`typeof current!=='undefined' && current.section==='token-mix' && !!current.result && !current.loading && !current.withheld`);
    assert.equal(await evaluate(`!document.querySelector('.report-loading') && document.getElementById('report-updating').textContent.includes('Historical snapshot as of')`),true,
      'aged qualified data remain visible with the original historical observation');
    const aged=await evaluate(`CachedReports.observation(current.result)`);
    await fixture('complete'); await until(`CachedReports.observation(current.result)>${aged} && !current.loading && !current.withheld`);
    facts.push('aged host result remains visible during refresh and is replaced by a coherent newer publication');
     assert.ok(retryTypes.length>0); assert.ok(retryTypes.every(value=>value==='boolean'),'every managed admission includes its strict retry boolean');
     assert.deepEqual(errors,[]); outcome='PASS'; console.log(JSON.stringify({outcome,facts}));
  } finally {
    clearTimeout(deadline);await fs.writeFile(path.join(output,'browser.json'),JSON.stringify({outcome,facts,errors,serverErrors},null,2));
    server.stdin.end('{"command":"stop"}\n');await command('Browser.close').catch(()=>{});
    if(server.exitCode===null)await new Promise(resolve=>server.once('exit',resolve));
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
