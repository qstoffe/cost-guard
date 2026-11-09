// Compatibility entrypoint: current layout is probe_mini_fit; dedicated lease proof below.
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path');
const {spawn}=require('node:child_process'),readline=require('node:readline');
const [browser,output,scale='1',scope='all']=process.argv.slice(2);
async function main() {
  assert.ok(path.isAbsolute(browser)&&path.isAbsolute(output));assert.ok(['all','--history-demand-only'].includes(scope));
  if(scope==='all') {
    const child=spawn(process.execPath,['development/tests/integration/probe_mini_fit.cjs',browser,output,scale,'1'],{windowsHide:true,stdio:'inherit'});
    process.exitCode=await new Promise(resolve=>child.once('exit',code=>resolve(code??1)));return;
  }
  await fs.stat(browser);const profile=await fs.mkdtemp(path.join(path.dirname(output),'lease-browser-'));
  const config=await fs.mkdtemp(path.join(path.dirname(output),'lease-config-'));
  const server=spawn('py',['-3','development/tests/integration/serve_mini_watch.py',config,'--history-demand'],{windowsHide:true,stdio:['pipe','pipe','pipe']});
  const lines=readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const launch=JSON.parse((await lines.next()).value); // Capability never logged/retained.
  const child=spawn(browser,['--headless=new',`--screen-info={${1920*Number(scale)}x${1080*Number(scale)}}`,
    '--force-device-scale-factor='+scale,'--no-first-run','--no-default-browser-check','--disable-extensions',
    '--disable-background-networking','--remote-debugging-pipe','--user-data-dir='+profile,'about:blank'],
    {windowsHide:true,stdio:['ignore','ignore','ignore','pipe','pipe']});
  const pending=new Map(),interest=[],errors=[];let sequence=0,buffer='';
  child.stdio[4].on('data',chunk=>{buffer+=chunk.toString();let index;while((index=buffer.indexOf('\0'))>=0){
    const value=JSON.parse(buffer.slice(0,index));buffer=buffer.slice(index+1);
    const entry=pending.get(value.id);
    if(entry){clearTimeout(entry.timer);pending.delete(value.id);value.error?entry.reject(new Error(JSON.stringify(value.error))):entry.resolve(value.result);}
    else if(value.method==='Runtime.exceptionThrown')errors.push(value.params.exceptionDetails.text);
    else if(value.method==='Network.requestWillBeSent'&&value.params.request.url.endsWith('/api/interest')) {
      const p=JSON.parse(value.params.request.postData);interest.push({requestId:value.params.requestId,session:value.sessionId,
        tab:p.tab,visible:p.visible,history:p.history,section:p.section});
    }else{const row=interest.find(r=>r.requestId===value.params?.requestId&&r.session===value.sessionId);
      if(row&&value.method==='Network.responseReceived')row.status=value.params.response.status;
      if(row&&value.method==='Network.loadingFinished')row.finished=true;}
  }});
  const command=(method,params={},sessionId)=>new Promise((resolve,reject)=>{const id=++sequence,
    timer=setTimeout(()=>reject(new Error('CDP timeout '+method)),15000);pending.set(id,{resolve,reject,timer});
    child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');});
  const deadline=setTimeout(()=>{child.kill();server.kill();},90000);let evidence={outcome:'FAIL'};
  try {
    const version=await command('Browser.getVersion'),{targetId}=await command('Target.createTarget',{url:'about:blank'}),
      {sessionId}=await command('Target.attachToTarget',{targetId,flatten:true});
    await command('Page.enable',{},sessionId);await command('Runtime.enable',{},sessionId);await command('Network.enable',{},sessionId);
    const evaluate=async(expression,userGesture=false)=>{const r=await command('Runtime.evaluate',
      {expression,returnByValue:true,awaitPromise:true,userGesture},sessionId);if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
    const until=async expression=>{const end=Date.now()+15000;while(Date.now()<end){if(await evaluate(expression))return;
      await new Promise(resolve=>setTimeout(resolve,25));}throw new Error('Condition not reached: '+expression);};
    await command('Page.addScriptToEvaluateOnNewDocument',{source:`window.probeStreams=0;const Native=EventSource;window.EventSource=class extends Native{constructor(...args){super(...args);probeStreams++;}};`},sessionId);
    await command('Page.navigate',{url:launch.url},sessionId);
    await until(`typeof miniWatch!=='undefined'&&hostState.kind==='connected'&&miniWatch.measure?.ready&&liveValue?.view?.running?.count===2`);
    await evaluate(`location.hash='#/watch'`);await evaluate('miniWatch.toggle()',true);
    evidence=await require('./probe_mini_history_demand.cjs')({command,evaluate,until,sessionId,targetId,interest,errors,browser:version.product});
  }catch(error){evidence.error=String(error.stack||error);throw error;}
  finally{await fs.writeFile(output,JSON.stringify(evidence,null,2));clearTimeout(deadline);try{await command('Browser.close');}catch(_){}
    child.kill();server.stdin.end();for(const entry of pending.values())clearTimeout(entry.timer);}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
