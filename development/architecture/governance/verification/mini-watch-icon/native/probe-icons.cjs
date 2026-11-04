// Owned browser only; headless first. Native mode requires the FR570 scoped decision.
const fs=require('node:fs/promises'), path=require('node:path'), assert=require('node:assert/strict');
const {spawn}=require('node:child_process'), readline=require('node:readline');
const [browser,outputArgument,mode='headless']=process.argv.slice(2);
const output=path.resolve(outputArgument);
async function main(){
  assert.ok(['headless','native'].includes(mode));
  await fs.mkdir(output,{recursive:true});
  const profile=await fs.mkdtemp(path.join(output,'profile-'));
  const server=spawn('py',['-3','development/tests/integration/serve_mini_watch.py'],{windowsHide:true,stdio:['pipe','pipe','pipe']});
  const lines=readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const child=spawn(browser,[...(mode==='headless'?['--headless=new','--screen-info={2880x1620}']:[]),
    '--no-first-run','--no-default-browser-check','--disable-extensions','--disable-background-networking',
    '--remote-debugging-pipe','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','ignore','pipe','pipe']});
  const pending=new Map();let id=0,buffer='',helper=null;
  child.stdio[4].on('data',chunk=>{buffer+=chunk.toString();let end;while((end=buffer.indexOf('\0'))>=0){
    const v=JSON.parse(buffer.slice(0,end));buffer=buffer.slice(end+1);const p=pending.get(v.id);
    if(p){clearTimeout(p.timer);pending.delete(v.id);v.error?p.reject(Error(JSON.stringify(v.error))):p.resolve(v.result);}
  }});
  const command=(method,params={},sessionId)=>new Promise((resolve,reject)=>{
    const key=++id,timer=setTimeout(()=>{pending.delete(key);reject(Error('CDP timeout '+method));},10000);
    pending.set(key,{resolve,reject,timer});child.stdio[3].write(JSON.stringify({id:key,method,params,...(sessionId?{sessionId}:{})})+'\0');
  });
  const start=Date.now(),deadline=setTimeout(()=>{helper?.kill();child.kill();server.kill();},mode==='native'?85000:120000);
  let evidence={outcome:'FAIL',mode,cases:[]};
  try{
    const launch=JSON.parse((await lines.next()).value);
    evidence.browser=await command('Browser.getVersion');
    const infos=await command('Target.getTargets'),targetId=infos.targetInfos.find(x=>x.type==='page').targetId;
    const {sessionId}=await command('Target.attachToTarget',{targetId,flatten:true});
    await command('Page.enable',{},sessionId);
    const evaluate=async(expression,userGesture=false)=>{
      const v=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true,userGesture},sessionId);
      if(v.exceptionDetails)throw Error(JSON.stringify(v.exceptionDetails));return v.result.value;
    };
    const until=async expression=>{const limit=Date.now()+12000;while(Date.now()<limit){if(await evaluate(expression))return;await new Promise(r=>setTimeout(r,50));}throw Error('Condition timeout '+expression);};
    await command('Page.navigate',{url:launch.url},sessionId);
    await until(`typeof miniWatch!=='undefined'&&hostState.kind==='connected'&&liveValue?.view?.running?.count===2`);
    await evaluate(`window.iconViolations=[];document.addEventListener('securitypolicyviolation',e=>iconViolations.push({directive:e.violatedDirective,blocked:e.blockedURI}));`);
    const native=async name=>{
      if(mode!=='native')return undefined;
      helper=spawn('py',['-3',path.join(__dirname,'probe-icons.py'),'--pid',String(child.pid),'--output',output,
        '--icon',path.resolve('src/web/assets/favicon.ico'),'--case',name],{windowsHide:true,stdio:['ignore','pipe','pipe']});
      let text='',errors='';helper.stdout.on('data',v=>text+=v);helper.stderr.on('data',v=>errors+=v);
      const code=await new Promise(r=>helper.once('close',r));helper=null;
      if(code!==0)throw Error('Native helper '+errors);return JSON.parse(text);
    };
    const snapshot=async name=>{
      await until(`miniWatch.window&&miniWatch.window.getComputedStyle(miniWatch.view.root).display!=='inline'`);
      const dom=await evaluate(`(()=>{const w=miniWatch.window;return {inner:[w.innerWidth,w.innerHeight],outer:[w.outerWidth,w.outerHeight],dpr:w.devicePixelRatio,
        ownerIcon:document.querySelector('link[rel=icon]')?.href,pipIcons:[...w.document.querySelectorAll('link[rel=icon]')].map(n=>({href:n.href,type:n.type})),
        iconFetches:w.performance.getEntriesByType('resource').filter(n=>n.name.includes('favicon')).map(n=>({name:n.name,initiatorType:n.initiatorType})),
        ownerViolations:iconViolations,pipViolations:window.pipViolations||[],streams:document.querySelectorAll('.mini-watch').length,
        apiSame:documentPictureInPicture.window===w,title:w.document.title};})()`);
      const nativeData=await native(name);evidence.cases.push({name,dom,...(nativeData?{native:nativeData}:{})});
    };
    await evaluate(`miniWatch.toggle()`,true);await snapshot('baseline');
    await evaluate(`window.pipViolations=[];miniWatch.window.document.addEventListener('securitypolicyviolation',e=>pipViolations.push({directive:e.violatedDirective,blocked:e.blockedURI}));
      (()=>{const link=miniWatch.window.document.createElement('link');link.rel='icon';link.type='image/x-icon';link.href=new URL('/favicon-cg1.ico',location.href).href;miniWatch.window.document.head.append(link);})()`);
    await evaluate(`new Promise(resolve=>{const image=new miniWatch.window.Image();image.onload=()=>resolve(true);image.onerror=()=>resolve(false);image.src=new URL('/favicon-cg1.ico',location.href).href;})`).then(v=>assert.equal(v,true));
    await new Promise(r=>setTimeout(r,1500)); // bounded browser favicon propagation observation, not workflow scheduling
    await snapshot('delayed-link');
    await evaluate(`miniWatch.close();documentPictureInPicture.addEventListener('enter',e=>{const link=e.window.document.createElement('link');link.rel='icon';link.type='image/x-icon';link.href=new URL('/favicon-cg1.ico',location.href).href;e.window.document.head.append(link);});`);
    await evaluate(`miniWatch.toggle()`,true);
    await new Promise(r=>setTimeout(r,1500));await snapshot('immediate-link-reopen');
    assert.ok(evidence.cases.every(c=>c.dom.apiSame&&c.dom.ownerViolations.length===0&&c.dom.pipViolations.length===0));
    evidence.outcome='MEASURED';
    evidence.limitations=['Synthetic HTTP/SSE; no personal profile or installed source calls.','HICON metadata is not actual taskbar/Alt+Tab rendering.','Headless mode is not physical desktop proof.'];
  }catch(error){evidence.reason=error.stack;process.exitCode=1;}
  finally{
    helper?.kill();try{await command('Browser.close');}catch{}
    if(child.exitCode===null)await new Promise(r=>{child.once('exit',r);setTimeout(r,2000);});
    if(child.exitCode===null)child.kill();server.stdin.end();if(server.exitCode===null)server.kill();clearTimeout(deadline);
    evidence.elapsedMs=Date.now()-start;try{await fs.rm(profile,{recursive:true});}catch{}
    await fs.writeFile(path.join(output,'result.json'),JSON.stringify(evidence,null,2)+'\n');console.log(JSON.stringify(evidence));
  }
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
