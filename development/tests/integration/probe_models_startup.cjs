// Fresh authenticated startup, real LiveRuntime/HTTP/shipped assets, no private source.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const {setTimeout: pause} = require('node:timers/promises');

async function main() {
  const [browser, directory, width='1366', theme='web'] = process.argv.slice(2);
  const output=path.resolve(directory); await fs.mkdir(output,{recursive:true}); await fs.stat(browser);
  const profile=await fs.mkdtemp(path.join(output,'browser-')), config=await fs.mkdtemp(path.join(output,'config-'));
  const server=spawn('py',['-3','development/tests/integration/serve_models_startup.py',config],
    {windowsHide:true,stdio:['pipe','pipe','pipe']});
  const lines=readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  let serverErrors=''; server.stderr.on('data',value=>serverErrors+=value.toString());
  const fixture=async command=>{server.stdin.write(JSON.stringify({command})+'\n');return JSON.parse((await lines.next()).value);};
  const child=spawn(browser,['--headless=new','--no-first-run','--no-default-browser-check','--disable-extensions',
    '--disable-background-networking','--remote-debugging-pipe','--user-data-dir='+profile,'about:blank'],
    {windowsHide:true,stdio:['ignore','ignore','ignore','pipe','pipe']});
  const pending=new Map(), errors=[], network=[], trace=[]; let sequence=0,buffer='',tab,outcome='FAIL';
  child.stdio[4].on('data',chunk=>{buffer+=chunk.toString();let end;
    while((end=buffer.indexOf('\0'))>=0){const value=JSON.parse(buffer.slice(0,end));buffer=buffer.slice(end+1);
      const entry=pending.get(value.id);
      if(entry){pending.delete(value.id);clearTimeout(entry.timer);value.error?entry.reject(new Error(JSON.stringify(value.error))):entry.resolve(value.result);}
      else if(value.method==='Runtime.exceptionThrown')errors.push(value.params.exceptionDetails.text);
      else if(value.method==='Network.responseReceived' && /\/api\/(data|interest)$/.test(value.params.response.url))
        network.push({requestId:value.params.requestId,route:new URL(value.params.response.url).pathname,
          status:value.params.response.status,at:value.params.timestamp});
    }
  });
  const command=(method,params={},sessionId=tab)=>new Promise((resolve,reject)=>{
    const id=++sequence,timer=setTimeout(()=>reject(new Error('CDP timeout '+method)),20000);
    pending.set(id,{resolve,reject,timer});child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');
  });
  const evaluate=async expression=>{const value=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
    assert.equal(value.exceptionDetails,undefined,JSON.stringify(value.exceptionDetails));return value.result.value;};
  const until=async expression=>assert.equal(await evaluate(`new Promise(resolve=>{const end=Date.now()+12000;
    const check=()=>{if(${expression})resolve(true);else if(Date.now()>end)resolve(false);else setTimeout(check,30);};check();})`),true,expression);
  const snapshot=()=>evaluate(`({kind:hostState.kind,loading:current.loading,failed:!!current.failed,
    message:current.message,stage:current.stage,percent:current.percent,retry:!refresh.hidden,
    result:!!current.result,withheld:!!current.withheld,dispatchError:current.dispatchError||null})`);
  const deadline=setTimeout(()=>{child.kill();server.kill();},90000);
  try {
    const launch=JSON.parse((await lines.next()).value), target=await command('Target.createTarget',{url:'about:blank'});
    tab=(await command('Target.attachToTarget',{targetId:target.targetId,flatten:true})).sessionId;
    await command('Runtime.enable');await command('Page.enable');await command('Network.enable');
    await command('Emulation.setDeviceMetricsOverride',{width:Number(width),height:900,deviceScaleFactor:1,mobile:false});
    await command('Page.addScriptToEvaluateOnNewDocument',{source:`window.__startup=[];
      new MutationObserver(()=>{if(typeof current!=='undefined'&&current) __startup.push({at:performance.now(),
        failed:!!current.failed,retry:!document.getElementById('refresh').hidden,percent:current.percent,
        result:!!current.result,text:document.getElementById('result').textContent});})
        .observe(document,{subtree:true,childList:true,attributes:true,characterData:true});`});
    await command('Page.navigate',{url:launch.url});
    await until(`typeof current!=='undefined' && current?.attempted && (current.failed || current.stage==='Waiting for source…')`);
    await evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme)};true`);
    await pause(650);
    const before=await snapshot(), host=await fixture('status'); trace.push({phase:'held',browser:before,host});
    assert.equal(host.startup.ready,true);assert.equal(host.identity,true);assert.equal(host.observed,false);
    assert.deepEqual(host.jobs,[],'no work before first healthy Live observation');
    const response=await evaluate(`(async()=>{try{return await api('/api/data',{request:current.request,retry:false});}
      catch(error){return {error:error.message,retryable:error.retryable};}})()`);
    trace.push({phase:'held-http',response});
    if(!before.failed) {
      const layout=await evaluate(`(()=>{const loader=document.querySelector('.report-loading'),bar=loader.querySelector('progress');
        const bounds=loader.getBoundingClientRect(),track=bar.getBoundingClientRect();return {
          width:innerWidth,theme:document.documentElement.dataset.theme,
          centered:Math.abs((bounds.left+bounds.right-track.left-track.right)/2)<2,
          inside:track.left>=0&&track.right<=innerWidth,label:bar.getAttribute('aria-label'),value:bar.value};})()`);
      assert.equal(layout.centered,true);assert.equal(layout.inside,true);assert.equal(layout.value,5);
      assert.equal(layout.label,'Report loading progress');assert.equal(layout.theme,theme);
      trace.push({phase:'loader-layout',layout});
      const accessibility=await command('Accessibility.getFullAXTree');
      assert.ok(accessibility.nodes.some(node=>node.role?.value==='progressbar'&&node.name?.value==='Report loading progress'));
      const image=await command('Page.captureScreenshot',{format:'png'});
      await fs.writeFile(path.join(output,'waiting.png'),Buffer.from(image.data,'base64'));
    }
    const primary=tab;
    const peer=await command('Target.createTarget',{url:'about:blank'});
    tab=(await command('Target.attachToTarget',{targetId:peer.targetId,flatten:true})).sessionId;
    await command('Runtime.enable');await command('Page.enable');
    await command('Page.navigate',{url:launch.url.split('#')[0]+'#/models'});
    await until(`typeof current!=='undefined' && current?.attempted && (current.failed || current.stage==='Waiting for source…')`);
    const secondary=tab;tab=primary;
    await fixture('release');
    await until(`hostState.kind==='connected'`);
    await pause(1200);
    const after=await snapshot(); trace.push({phase:'released',browser:after,host:await fixture('status')});
    // Record both sides of the causal failure before asserting desired UX (RED on old assets).
    if(before.failed) console.log(JSON.stringify({trace}));
    assert.equal(before.failed,false,'healthy first-Live waiting must not become a terminal report error');
    assert.equal(before.retry,false,'Retry must not flash during healthy startup');
    assert.ok(before.percent<100);assert.equal(before.stage,'Waiting for source…');
    await until(`!!current.result && !current.loading`);
    const final=await snapshot(), status=await fixture('status');trace.push({phase:'ready',browser:final,host:status});
    assert.equal(final.failed,false);assert.equal(final.retry,false);assert.equal(final.percent,100);
    assert.equal(final.dispatchError,null);assert.equal(final.withheld,false);
    assert.equal(status.jobs.filter(job=>job.kind==='normal').length,1);
    assert.equal(status.jobs[0].kind,'normal','foreground Models precedes speculative warming');
    const observations=await evaluate('__startup');
    trace.push({phase:'browser-timing',firstResultMs:observations.find(value=>value.result)?.at});
    assert.equal(observations.some(value=>value.failed||value.retry),false,'no false failure/Retry flash');
    assert.equal(observations.some(value=>value.percent===100&&!value.result),false,'100% requires a coherent result');
    assert.equal(await evaluate(`!!document.querySelector('#cancel')`),false);
    assert.equal(await evaluate(`!!document.querySelector('.overview-models')`),true);
    const image=await command('Page.captureScreenshot',{format:'png'});
    await fs.writeFile(path.join(output,'ready.png'),Buffer.from(image.data,'base64'));
    tab=secondary;await until(`!!current.result && !current.loading`);
    assert.equal((await snapshot()).failed,false,'second tab shares automatic startup recovery');
    await command('Page.reload');await until(`typeof current!=='undefined' && !!current?.result && !current.loading`);
    assert.equal((await snapshot()).failed,false,'authenticated warm deep link reuses the result');
    assert.equal((await fixture('status')).jobs.filter(job=>job.kind==='normal').length,1);
    assert.deepEqual(errors,[]);outcome='PASS';console.log(JSON.stringify({outcome,width,theme,
      seconds:status.seconds,modelsJobs:status.jobs.filter(job=>job.kind==='normal').length,
      falseFailure:observations.some(value=>value.failed||value.retry)}));
  } finally {
    clearTimeout(deadline);await fs.writeFile(path.join(output,'startup.json'),JSON.stringify({outcome,width,theme,trace,network,errors,serverErrors},null,2));
    server.stdin.end('{"command":"stop"}\n');await command('Browser.close').catch(()=>{});
    if(server.exitCode===null)await new Promise(resolve=>server.once('exit',resolve));
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
