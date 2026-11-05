// Three wall-clock minutes of full-app Watch/SSE, owned hidden Chromium and synthetic source only.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output] = process.argv.slice(2);
async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output));
  await fs.mkdir(output, {recursive:true});
  const profile = await fs.mkdtemp(path.join(output,'watch-profile-'));
  const server = spawn('py',['-3','development/tests/integration/serve_mini_watch.py'],
    {windowsHide:true,stdio:['pipe','pipe','pipe']});
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const next = async () => JSON.parse((await lines.next()).value);
  const fixture = async command => {server.stdin.write(JSON.stringify({command})+'\n');assert.equal((await next()).ok,true);};
  const child = spawn(browser,['--headless=new','--no-first-run','--no-default-browser-check',
    '--disable-extensions','--disable-background-networking','--remote-debugging-pipe',
    '--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','ignore','pipe','pipe']});
  const pending = new Map(); let sequence=0, buffer='', exceptions=0;
  child.stdio[4].on('data',chunk=>{
    buffer+=chunk.toString(); let index;
    while((index=buffer.indexOf('\0'))>=0) {
      const value=JSON.parse(buffer.slice(0,index));buffer=buffer.slice(index+1);
      if(value.method==='Runtime.exceptionThrown') exceptions++;
      const entry=pending.get(value.id);
      if(entry) {pending.delete(value.id);clearTimeout(entry.timer);
        value.error?entry.reject(new Error('CDP request failed')):entry.resolve(value.result);}
    }
  });
  const command = (method,params={},sessionId) => new Promise((resolve,reject)=>{
    const id=++sequence,timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout: '+method));},15000);
    pending.set(id,{resolve,reject,timer});
    child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');
  });
  const deadline=setTimeout(()=>{child.kill();server.kill();},260000);
  try {
    const launch=await next(); // Never print/persist the one-use URL or browser session.
    await fixture('watch-starting');
    const version=await command('Browser.getVersion');
    const {targetId}=await command('Target.createTarget',{url:'about:blank'});
    const {sessionId}=await command('Target.attachToTarget',{targetId,flatten:true});
    await command('Page.enable',{},sessionId);
    await command('Runtime.enable',{},sessionId);
    const evaluate=async expression=>{
      const result=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},sessionId);
      assert.equal(result.exceptionDetails,undefined,'page evaluation failed');return result.result.value;
    };
    const until=async expression=>{
      const end=Date.now()+15000;
      while(Date.now()<end) {if(await evaluate(expression)) return;await new Promise(resolve=>setTimeout(resolve,50));}
      throw new Error('Condition not reached: '+expression);
    };
    await command('Page.addScriptToEvaluateOnNewDocument',{source:`window.probeStreams=0;const Native=EventSource;
      window.EventSource=class extends Native {constructor(...args){super(...args);window.probeStreams++;}};`},sessionId);
    await command('Page.navigate',{url:launch.url},sessionId);
    await until(`typeof liveValue!=='undefined'&&liveValue?.state==='running'&&csrf!==null`);
    assert.equal(await evaluate(`window.probeStreams`),1,'EventSource instrumentation installed before app startup');
    await evaluate(`location.hash='#/watch'`);await until(`current?.live`);
    const initial=await evaluate(`(() => {const now=Date.now;try {
      Date.now=()=>now()+180000;show(current);
      return {body:output.textContent,progress:output.querySelectorAll('progress').length,source:hostState.kind};
    } finally {Date.now=now;}})()`);
    assert.deepEqual(initial,{body:'',progress:0,source:'starting'});
    const started=Date.now(), samples=[];
    for(let seconds=0;seconds<=180;seconds+=10) {
      if(seconds) await new Promise(resolve=>setTimeout(resolve,Math.max(0,started+seconds*1000-Date.now())));
      await fixture('watch-delay-'+seconds);
      await until(`current.watch?.active.querySelector('tbody tr')?.cells[6].textContent==='${seconds+1}'`);
      const sample=await evaluate(`(() => {
        const w=current.watch,row=w.active.querySelector('tbody tr');
        if(!window.anchoredWatch) window.anchoredWatch={root:w.root,row};
        return {warning:w.empty.textContent,calls:row.cells[6].textContent,cards:w.active.children.length,
          sameRoot:anchoredWatch.root===w.root,sameRow:anchoredWatch.row===row,
          loading:liveValue.view.history_state,accounts:liveValue.view.accounts,
          generic:document.body.textContent.includes('Still loading Watch data'),progress:w.active.querySelectorAll('progress').length};
      })()`);
      assert.equal(sample.warning,'');assert.equal(sample.generic,false);assert.equal(sample.sameRoot,true);
      assert.equal(sample.sameRow,true);assert.equal(sample.loading,'loading');assert.equal(sample.accounts,null);
      assert.equal(sample.cards,seconds<60?1:2);assert.equal(sample.progress,0);samples.push(sample);
      if(seconds===90) {
        await evaluate(`location.hash='#/token-mix'`);await until(`!current.live`);
        await evaluate(`location.hash='#/watch'`);await until(`current.live`);
        assert.equal(await evaluate(`current.watch.root===anchoredWatch.root`),true);
      }
    }
    await fixture('watch-retrying');await until(`hostState.kind==='source_retrying'`);
    assert.match(await evaluate(`document.getElementById('host-message').textContent`),/Retrying source read.*not current/);
    await fixture('recovering');await until(`hostState.kind==='source_unavailable'`);
    assert.match(await evaluate(`document.getElementById('host-message').textContent`),/SOURCE UNAVAILABLE.*not live/);
    await fixture('running');await until(`hostState.kind==='connected'`);
    await evaluate(`window.dispatchEvent(new Event('offline'))`);
    assert.match(await evaluate(`document.getElementById('host-message').textContent`),/OFFLINE.*not live/);
    await evaluate(`window.dispatchEvent(new Event('online'))`);await until(`hostState.kind==='connected'`);
    assert.equal(await evaluate(`probeStreams`),1);assert.equal(exceptions,0);
    await fixture('stop');await until(`hostState.terminal`);
    assert.match(await evaluate(`document.getElementById('host-message').textContent`),/STOPPED.*NOT LIVE/);
    const evidence={outcome:'PASS',browser:version.product,initial,samples,wallSeconds:(Date.now()-started)/1000,
      checks:['initial app fallback','advancing cards with delayed history/accounts/daily','route retention',
        'source retry/unavailable/recovery','offline/revalidation','one EventSource','terminal host shutdown'],
      limitations:['Synthetic source; initial timer is virtual, active delay uses wall time; no physical desktop or screen-reader proof.']};
    await fs.writeFile(path.join(output,'browser.json'),JSON.stringify(evidence,null,2));
    console.log(JSON.stringify({outcome:evidence.outcome,browser:evidence.browser,wallSeconds:evidence.wallSeconds,samples:samples.length}));
  } finally {
    clearTimeout(deadline);
    if(child.exitCode===null) {const exited=new Promise(resolve=>child.once('exit',resolve));await command('Browser.close');await exited;}
    if(server.exitCode===null) {const exited=new Promise(resolve=>server.once('exit',resolve));server.stdin.end();await exited;}
    await fs.rm(profile,{recursive:true});
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
