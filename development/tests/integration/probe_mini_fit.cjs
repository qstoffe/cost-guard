// Owned headless Edge/Chromium Document PiP, shipped HTTP/CSP/SSE, synthetic data.
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path');
const {spawn}=require('node:child_process'),readline=require('node:readline');
const [browser,output,scale='1',zoom='1',scope='all',scrollbars='classic']=process.argv.slice(2);
async function main() {
  assert.ok(path.isAbsolute(browser)&&path.isAbsolute(output));await fs.stat(browser);
  const profile=await fs.mkdtemp(path.join(path.dirname(output),'mini-browser-'));
  const config=await fs.mkdtemp(path.join(path.dirname(output),'mini-config-'));
  const server=spawn('py',['-3','development/tests/integration/serve_mini_watch.py',config],{windowsHide:true,stdio:['pipe','pipe','pipe']});
  const lines=readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const launch=JSON.parse((await lines.next()).value); // Capability URL stays in memory.
  const fixture=async command=>{server.stdin.write(JSON.stringify({command})+'\n');return JSON.parse((await lines.next()).value);};
  const child=spawn(browser,['--headless=new',`--screen-info={${1920*Number(scale)}x${1200*Number(scale)}}`,
    '--force-device-scale-factor='+scale,'--no-first-run','--no-default-browser-check','--disable-extensions',
    '--disable-background-networking','--remote-debugging-pipe','--user-data-dir='+profile,
    ...(scrollbars==='overlay'?['--enable-features=OverlayScrollbar,FluentOverlayScrollbar,FluentScrollbar']:[]),'about:blank'],
    {windowsHide:true,stdio:['ignore','ignore','ignore','pipe','pipe']});
  const pending=new Map();let sequence=0,buffer='';
  child.stdio[4].on('data',chunk=>{buffer+=chunk.toString();let index;while((index=buffer.indexOf('\0'))>=0){
    const value=JSON.parse(buffer.slice(0,index));buffer=buffer.slice(index+1);const item=pending.get(value.id);
    if(item){clearTimeout(item.timer);pending.delete(value.id);value.error?item.reject(new Error(JSON.stringify(value.error))):item.resolve(value.result);}
  }});
  const command=(method,params={},sessionId)=>new Promise((resolve,reject)=>{const id=++sequence;
    const timer=setTimeout(()=>reject(new Error('CDP timeout '+method)),15000);pending.set(id,{resolve,reject,timer});
    child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');});
  const deadline=setTimeout(()=>{child.kill();server.kill();},240000);
   const evidence={outcome:'FAIL',scale,zoom,scrollbars,layouts:[],checks:[],limitations:['Headless native PiP, not physical desktop/work-area proof.']};
  try {
    evidence.browser=await command('Browser.getVersion');
    const {targetId}=await command('Target.createTarget',{url:'about:blank'});
    const {sessionId}=await command('Target.attachToTarget',{targetId,flatten:true});
    const ownerWindow=await command('Browser.getWindowForTarget',{targetId});
    await command('Browser.setWindowBounds',{windowId:ownerWindow.windowId,bounds:{width:1600,height:1000}});
    const evaluate=async(expression,userGesture=false,session=sessionId)=>{const result=await command('Runtime.evaluate',
      {expression,returnByValue:true,awaitPromise:true,userGesture},session);if(result.exceptionDetails)throw new Error(JSON.stringify(result.exceptionDetails));return result.result.value;};
    const until=async expression=>{const end=Date.now()+15000;while(Date.now()<end){if(await evaluate(expression))return;
      await new Promise(resolve=>setTimeout(resolve,25));}throw new Error('Condition not reached: '+expression);};
    await command('Page.enable',{},sessionId);await command('Page.navigate',{url:'chrome://settings/appearance'},sessionId);
    await until(`typeof chrome.settingsPrivate?.getDefaultZoom==='function'`);
    await evaluate(`new Promise(resolve=>chrome.settingsPrivate.setDefaultZoom(${Number(zoom)},resolve))`);
    evidence.browserZoom=await evaluate('new Promise(resolve=>chrome.settingsPrivate.getDefaultZoom(resolve))');
    assert.ok(Math.abs(evidence.browserZoom-Number(zoom))<.001);
    await command('Page.addScriptToEvaluateOnNewDocument',{source:`window.probeStreams=0;const Native=EventSource;window.EventSource=class extends Native{constructor(...args){super(...args);probeStreams++;}};`},sessionId);
    await command('Page.navigate',{url:launch.url},sessionId);
    await until(`typeof miniWatch!=='undefined' && miniWatch.measure?.ready && liveValue?.view?.active_cards?.length===2`);
    await evaluate(`location.hash='#/watch';window.probeRequests=[];const nativeRequest=documentPictureInPicture.requestWindow.bind(documentPictureInPicture);
      documentPictureInPicture.requestWindow=options=>{probeRequests.push(options);return nativeRequest(options);}`);
    const settle=()=>evaluate('new Promise(resolve=>miniWatch.window.requestAnimationFrame(()=>miniWatch.window.requestAnimationFrame(resolve)))');
    const open=async()=>{await evaluate('miniWatch.toggle()',true);await until('!!miniWatch.view');await settle();};
    const close=()=>evaluate('miniWatch.close()');
    const read=()=>evaluate(`(()=>{const w=miniWatch.window,v=miniWatch.view,d=w.document,p=v.prompts,rect=n=>n.getBoundingClientRect();return {
      outer:[w.outerWidth,w.outerHeight],inner:[w.innerWidth,w.innerHeight],request:probeRequests.at(-1),desired:v.fitHeight(),
      rows:v.promptRows.size,accounts:v.lines.size,header:(${require('./probe_mini_width.cjs').inspect.toString()})(v),
      documentOverflow:d.documentElement.scrollWidth>w.innerWidth+1,documentVertical:d.documentElement.scrollHeight>w.innerHeight+1,
      table:{height:p.clientHeight,scroll:p.scrollHeight,horizontal:p.scrollWidth>p.clientWidth+1,vertical:p.scrollHeight>p.clientHeight+1,
        header:rect(v.body.parentNode.tHead).height,rowHeights:[...v.body.rows].filter(r=>r.dataset.id).map(r=>rect(r).height)},
      accountsBottom:rect(v.accounts).bottom,bodyPadding:parseFloat(w.getComputedStyle(d.body).paddingBottom)};})()`);
    const pipSession=async()=>{for(const t of (await command('Target.getTargets')).targetInfos.filter(t=>t.targetId!==targetId&&t.type==='page')){
      const a=await command('Target.attachToTarget',{targetId:t.targetId,flatten:true});
      if(await evaluate('!!document.querySelector(".mini-watch")',false,a.sessionId))return a.sessionId;}throw new Error('No PiP target');};
    const capture=async label=>{const image=await command('Page.captureScreenshot',{format:'png'},await pipSession());
      await fs.writeFile(output.replace(/\.json$/,`-${label}.png`),Buffer.from(image.data,'base64'));};
    const settings=(field,endpoint,value)=>evaluate(`(async()=>applySettings(await api('/api/settings/${endpoint}',{${field}:'${value}'})))()`);
    if(scope==='context-only') {
      await open();await require('./probe_mini_context.cjs')({evaluate,until,fixture,command,pip:await pipSession(),open,close,checks:evidence.checks});
      evidence.outcome='PASS';return;
    }
    if(scope==='dates-only') {
      await open();await require('./probe_mini_activity.cjs')({evaluate,until,fixture,command,pip:await pipSession(),ownerSession:sessionId,layouts:evidence.layouts,checks:evidence.checks});
      await capture('activity');
      evidence.outcome='PASS';return;
    }
    if(scope==='help-only') {
      await open();await require('./probe_mini_help.cjs')({evaluate,until,fixture,command,pip:await pipSession(),checks:evidence.checks});
      await require('./probe_mini_duration.cjs')({evaluate,until,command,pip:await pipSession(),ownerSession:sessionId,checks:evidence.checks});
      evidence.outcome='PASS';return;
    }
    if(scope==='gutter-only'||scope==='all') {
      await require('./probe_mini_gutter.cjs')({evaluate,until,fixture,command,sessionId,open,close,capture,layouts:evidence.layouts,checks:evidence.checks});
      if(scope==='gutter-only') {evidence.outcome='PASS';return;}
    }
    await require('./probe_mini_theme.cjs')({evaluate,until,fixture,command,sessionId,open,close,capture,layouts:evidence.layouts,checks:evidence.checks});
    if(scope==='colors-only') {evidence.outcome='PASS';return;}
    if(scope!=='manual-only') {
    await require('./probe_mini_width.cjs')({evaluate,command,sessionId,open,close,read,capture,layouts:evidence.layouts,checks:evidence.checks});
    for(const count of [0,1,3,5,6,10])for(const accounts of [0,1,6]) {
      await fixture(`density-${count}-${accounts}`);await until(`liveValue.view.active_cards.length===${count}`);await open();const value=await read();
      assert.equal(value.rows,count);assert.equal(value.accounts,accounts);assert.equal(value.documentOverflow,false);
      const clamped=value.outer[1]+2<value.desired;value.nativeHeightClamp=clamped;
      if(!clamped){assert.equal(value.documentVertical,false,JSON.stringify(value));assert.ok(value.accountsBottom<=value.inner[1]+1,JSON.stringify(value));}
      assert.equal(value.table.vertical,count>5,JSON.stringify(value));
      assert.ok(value.table.height>=value.table.header+5*(value.table.rowHeights[0]||0)-1,JSON.stringify(value));
      const before=value.outer;
      await fixture(`density-10-${accounts}`);await until('miniWatch.view.promptRows.size===10');await settle();
      assert.deepEqual((await read()).outer,before,'SSE cannot resize native PiP');
      if(!clamped)assert.equal((await read()).documentVertical,false);
      evidence.layouts.push({case:`five-row-${count}-${accounts}`,...value});await close();
    }
    evidence.checks.push('0/1/3/5/6/10 distinct sessions × 0/1/6 accounts: five-row capacity, internal overflow, no passive native resize; clamps recorded');
    await fixture('history-5-1-1');await until('liveValue.view.history_cards.length===5');await open();
    assert.equal(await evaluate('miniWatch.view.promptRows.size'),5);
    await require('./probe_mini_activity.cjs')({evaluate,until,fixture,command,pip:await pipSession(),ownerSession:sessionId,layouts:evidence.layouts,checks:evidence.checks});
     await require('./probe_mini_help.cjs')({evaluate,until,fixture,command,pip:await pipSession(),checks:evidence.checks});
     await require('./probe_mini_duration.cjs')({evaluate,until,command,pip:await pipSession(),ownerSession:sessionId,checks:evidence.checks});
    await close();await require('./probe_history_readiness.cjs')({fixture,evaluate,until,command,sessionId,open,close,checks:evidence.checks});
    }
    await fixture('density-10-1');await until('liveValue.view.active_cards.length===10');
    for(const mode of ['fit-on-open','remember-last']) {
      await settings('miniWatchSize','mini-size',mode);await open();const pip=await pipSession();
      await command('Page.bringToFront',{},pip);await evaluate('miniWatch.window.resizeTo(600,800)',true);await settle();
      await evaluate(`miniWatch.window.probeResizes=[];for(const name of ['resizeBy','resizeTo']){const native=miniWatch.window[name].bind(miniWatch.window);miniWatch.window[name]=(...args)=>{miniWatch.window.probeResizes.push({name,args});return native(...args);};}`);
      for(const key of [null,'Enter',' ','touch']) {
        await evaluate('miniWatch.window.resizeTo(600,800)',true);await settle();const before=await read();
        await evaluate('miniWatch.window.probeResizes=[];miniWatch.view.fitButton.focus()');
        if(key&&key!=='touch')for(const type of ['keyDown','keyUp'])await command('Input.dispatchKeyEvent',{type,key,code:key===' '?'Space':'Enter',windowsVirtualKeyCode:key===' '?32:13,...(type==='keyDown'?{text:key===' '?' ':'\r'}:{})},pip);
        else {const point=await evaluate(`(()=>{const r=miniWatch.view.fitButton.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
          if(key==='touch')for(const type of ['touchStart','touchEnd'])await command('Input.dispatchTouchEvent',{type,touchPoints:type==='touchStart'?[{...point,id:1,radiusX:1,radiusY:1,force:1}]:[]},pip);
          else for(const type of ['mousePressed','mouseReleased'])await command('Input.dispatchMouseEvent',{type,button:'left',clickCount:1,...point},pip);}
        await settle();const fitted=await read(),calls=await evaluate('miniWatch.window.probeResizes');
        evidence.layouts.push({case:`fit-${mode}-${key||'pointer'}`,before,fitted,calls});
        assert.ok(calls.length<=1);assert.equal(fitted.rows,10);assert.equal(fitted.table.vertical,true);
        if(before.outer[1]>before.desired+4)assert.ok(fitted.outer[1]<before.outer[1],JSON.stringify({before,fitted,calls}));
        else {
          assert.ok(before.outer[1]+4<before.desired,'not a shrink trial: actual native baseline is clamped below fit');
          assert.ok(fitted.outer[1]>=before.outer[1]);fitted.nativeFitClamp=fitted.outer[1]+2<fitted.desired;
          if(fitted.nativeFitClamp)assert.equal(fitted.documentVertical,true,'clamped accounts remain reachable by normal scrolling');
        }
        assert.equal(await evaluate(`!!miniWatch.view.doc.getElementById('context-help')?.matches(':popover-open')`),false);
        assert.equal(calls[0].args[0],calls[0].name==='resizeBy'?0:before.outer[0]);
      }
      await evaluate('miniWatch.window.resizeTo(280,250)',true);await settle();const narrow=await read();
      assert.equal(narrow.documentOverflow,false);assert.equal(narrow.table.horizontal,true);assert.equal(narrow.rows,10);
      await capture('narrow-'+mode);
      if(mode==='remember-last') {
        await evaluate('miniWatch.window.resizeTo(520,420)',true);await settle();const manual=await read();await close();await open();
        const restored=await read();assert.equal(restored.request.preferInitialWindowPlacement,false);
        if(Number(zoom)<=1.25)manual.outer.forEach((n,i)=>assert.ok(Math.abs(n-restored.outer[i])<=1,JSON.stringify({manual,restored})));
        evidence.layouts.push({case:'remembered-manual-reopen',manual,restored});
      }
      await close();
    }
    await settings('miniWatchSize','mini-size','default');assert.equal(await evaluate('probeStreams'),1);
    assert.deepEqual(await evaluate('({local:localStorage.length,session:sessionStorage.length})'),{local:0,session:0});
    evidence.checks.push('Pointer/Enter/Space/touch bounded height-only Fit, immediate help dismissal, both sizing modes, narrow horizontal panning, remembered manual-size reopen, one SSE/no geometry storage');
    evidence.outcome='PASS';
  }catch(error){evidence.error=String(error.stack||error);throw error;}
  finally{await fs.writeFile(output,JSON.stringify(evidence,null,2));clearTimeout(deadline);try{await command('Browser.close');}catch(_){}
    child.kill();server.stdin.end();for(const item of pending.values())clearTimeout(item.timer);}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
