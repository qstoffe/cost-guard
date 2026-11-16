// Reduced native-browser control: no Cost Guard, help controller or layout loop.
// The unpaced race remains FAIL evidence, not a repaired production behavior.
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path');
const {spawn}=require('node:child_process');
const {nativeTouch}=require('./native_touch.cjs');
const [browser,output,mode='paced']=process.argv.slice(2);
async function main() {
  assert.ok(path.isAbsolute(browser)&&path.isAbsolute(output));
  assert.ok(['paced','unpaced'].includes(mode));await fs.stat(browser);
  const profile=await fs.mkdtemp(path.join(path.dirname(output),'mixed-hover-'));
  const child=spawn(browser,['--headless=new','--screen-info={1920x1200}','--no-first-run',
    '--no-default-browser-check','--disable-extensions','--disable-background-networking',
    '--remote-debugging-pipe','--user-data-dir='+profile,'about:blank'],
    {windowsHide:true,stdio:['ignore','ignore','ignore','pipe','pipe']});
  let sequence=0,buffer='',traceDone;const pending=new Map(),traces=[];
  child.stdio[4].on('data',chunk=>{buffer+=chunk.toString();let i;while((i=buffer.indexOf('\0'))>=0) {
    const value=JSON.parse(buffer.slice(0,i));buffer=buffer.slice(i+1);const entry=pending.get(value.id);
    if(entry){pending.delete(value.id);clearTimeout(entry.timer);value.error?entry.reject(Error(JSON.stringify(value.error))):entry.resolve(value.result);}
    if(value.method==='Tracing.dataCollected')traces.push(...value.params.value);
    if(value.method==='Tracing.tracingComplete')traceDone?.();
  }});
  const command=nativeTouch((method,params={},sessionId)=>new Promise((resolve,reject)=>{
    const id=++sequence,timer=setTimeout(()=>reject(Error('CDP timeout: '+method)),15000);
    pending.set(id,{resolve,reject,timer});
    child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');
  }),mode==='paced');
  const evidence={outcome:'FAIL',mode,touchSettleMs:mode==='paced'?250:0,
    limitations:['Reduced headless native input, not physical mouse presence or owner-incident proof.']};
  const deadline=setTimeout(()=>child.kill(),45000);
  try {
    evidence.browser=await command('Browser.getVersion');
    await command('Tracing.start',{categories:'input,blink',transferMode:'ReportEvents'});
    const {targetId}=await command('Target.createTarget',{url:'about:blank'});
    const {sessionId}=await command('Target.attachToTarget',{targetId,flatten:true});
    await command('Page.enable',{},sessionId);await command('Page.bringToFront',{},sessionId);
    const run=async expression=>{
      const result=await command('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true},sessionId);
      if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));return result.result.value;
    };
    await run(`document.open();document.write('<!doctype html><html><body><style>button:hover{color:red}</style>'+
      '<button id="target" style="position:absolute;left:100px;top:100px;width:100px;height:40px">Hover</button>'+
      '<button id="outside" style="position:absolute;left:10px;top:10px;width:40px;height:40px">Out</button></body></html>');document.close();
      window.events=[];window.samples=[];window.started=performance.now();
      for(const type of ['pointerenter','pointerleave','pointermove','pointerdown','pointerout','click'])
        document.addEventListener(type,e=>events.push({at:performance.now()-started,type,pointer:e.pointerType,
          target:e.target.id,trusted:e.isTrusted,hover:target.matches(':hover')}),true);
      window.sample=setInterval(()=>samples.push({at:performance.now()-started,hover:target.matches(':hover'),
        outside:outside.matches(':hover')}),10);
      new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));`);
    const move=(x,y)=>command('Input.dispatchMouseEvent',{type:'mouseMoved',x,y},sessionId);
    await move(150,120);await run('new Promise(resolve=>setTimeout(resolve,700))');
    assert.equal(await run('target.matches(":hover")'),true,'pre-touch control');
    await move(0,0);
    for(const type of ['touchStart','touchEnd'])await command('Input.dispatchTouchEvent',
      {type,touchPoints:type==='touchStart'?[{x:30,y:30}]:[]},sessionId);
    await move(150,120);await run('new Promise(resolve=>setTimeout(resolve,1200))');
    Object.assign(evidence,await run('clearInterval(sample);({events,samples})'));
    const complete=new Promise(resolve=>traceDone=resolve);await command('Tracing.end');await complete;
    evidence.trace=traces.filter(event=>/activeIntervalTimerFired|handleMouseMoveEvent/.test(event.name));
    const moves=evidence.trace.filter(event=>event.name.includes('handleMouseMoveEvent'));
    const timer=evidence.trace.find(event=>event.name.includes('activeIntervalTimerFired'));
    assert.equal(moves.length,3,'one pre-touch control, outside move, one post-touch arrival');
    assert.ok(timer,'native deferred tap timer was observed');
    evidence.timerAfterArrivalMs=(timer.ts-moves[2].ts)/1000;
    const arrival=evidence.events.filter(event=>event.type==='pointermove'&&event.target==='target').at(-1);
    assert.ok(arrival?.trusted&&arrival.hover,'same native target initially hovered on arrival');
    const hold=evidence.samples.filter(sample=>sample.at>=arrival.at+500);
    assert.ok(hold.length>20);
    assert.ok(hold.every(sample=>sample.hover),'post-touch stationary hover remains positive');
    assert.ok(evidence.timerAfterArrivalMs<0,'tap release precedes paced mouse arrival');
    evidence.outcome='PASS';
  } catch(error) { evidence.error=error.message;throw error; }
  finally {
    await fs.writeFile(output,JSON.stringify(evidence,null,2));clearTimeout(deadline);
    await command('Browser.close').catch(()=>{});child.kill();
    for(const item of pending.values())clearTimeout(item.timer);
    await fs.rm(profile,{recursive:true,force:true}).catch(error=>console.error('Retained owned profile: '+error.code));
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
