// Owned strictly headless Chrome/Edge; shipped auth/CSP/SSE, no real data or OS input.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output, scale='1', zoom='1', scope='all'] = process.argv.slice(2);
async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output)); await fs.stat(browser);
  const profile = await fs.mkdtemp(path.join(path.dirname(output),'fit-browser-'));
  const config = await fs.mkdtemp(path.join(path.dirname(output),'fit-config-'));
  const server = spawn('py',['-3','development/tests/integration/serve_mini_watch.py',config],{windowsHide:true,stdio:['pipe','pipe','pipe']});
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const launch = JSON.parse((await lines.next()).value); // Never log the one-use URL.
  const fixture = async command => {server.stdin.write(JSON.stringify({command})+'\n'); return JSON.parse((await lines.next()).value);};
  const child = spawn(browser,['--headless=new',`--screen-info={${1920*Number(scale)}x${1200*Number(scale)}}`,
    '--force-device-scale-factor='+scale,'--no-first-run','--no-default-browser-check','--disable-extensions',
    '--disable-background-networking','--remote-debugging-pipe','--user-data-dir='+profile,'about:blank'],
    {windowsHide:true,stdio:['ignore','ignore','ignore','pipe','pipe']});
  const pending = new Map(); let sequence=0, buffer='';
  child.stdio[4].on('data',chunk => {
    buffer+=chunk.toString(); let index;
    while ((index=buffer.indexOf('\0'))>=0) {
      const value=JSON.parse(buffer.slice(0,index)); buffer=buffer.slice(index+1);
      const item=pending.get(value.id);
      if (item) {clearTimeout(item.timer);pending.delete(value.id);value.error?item.reject(new Error(JSON.stringify(value.error))):item.resolve(value.result);}
    }
  });
  const command=(method,params={},sessionId)=>new Promise((resolve,reject)=>{
    const id=++sequence,timer=setTimeout(()=>reject(new Error('CDP timeout '+method)),15000);
    pending.set(id,{resolve,reject,timer}); child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');
  });
  const deadline=setTimeout(()=>{child.kill();server.kill();},300000);
  const evidence={outcome:'FAIL',scale,zoom,layouts:[],checks:[]};
  try {
    evidence.browser=await command('Browser.getVersion');
    const {targetId}=await command('Target.createTarget',{url:'about:blank'});
    const {sessionId}=await command('Target.attachToTarget',{targetId,flatten:true});
    const ownerWindow=await command('Browser.getWindowForTarget',{targetId});
    await command('Browser.setWindowBounds',{windowId:ownerWindow.windowId,bounds:{width:1600,height:1000}});
    const evaluate=async (expression,userGesture=false,session=sessionId)=>{
      const result=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true,userGesture},session);
      if(result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));return result.result.value;
    };
    const until=async expression=>{
      const end=Date.now()+15000;
      while(Date.now()<end){if(await evaluate(expression))return;await new Promise(resolve=>setTimeout(resolve,30));}
      throw new Error('Condition not reached: '+expression);
    };
    await command('Page.enable',{},sessionId);
    await command('Page.navigate',{url:'chrome://settings/appearance'},sessionId);
    await until(`typeof chrome.settingsPrivate?.getDefaultZoom==='function'`);
    await evaluate(`new Promise(resolve=>chrome.settingsPrivate.setDefaultZoom(${Number(zoom)},resolve))`);
    evidence.browserZoom=await evaluate('new Promise(resolve=>chrome.settingsPrivate.getDefaultZoom(resolve))');
    assert.ok(Math.abs(evidence.browserZoom-Number(zoom))<.001);
    await command('Page.addScriptToEvaluateOnNewDocument',{source:`window.probeStreams=0;const Native=EventSource;window.EventSource=class extends Native{constructor(...args){super(...args);probeStreams++;}};`},sessionId);
    await command('Page.navigate',{url:launch.url},sessionId);
    await until(`typeof miniWatch!=='undefined' && miniWatch.measure?.ready && liveValue?.view?.active_cards?.length===2`);
    await evaluate(`location.hash='#/watch'`);
    evidence.owner=await evaluate('({outer:[outerWidth,outerHeight],inner:[innerWidth,innerHeight]})');
    await evaluate(`window.probeRequests=[];const nativeRequest=documentPictureInPicture.requestWindow.bind(documentPictureInPicture);documentPictureInPicture.requestWindow=options=>{probeRequests.push(options);return nativeRequest(options).then(w=>{if(window.probeFont)w.document.body.style.fontFamily=probeFont;return w;});}`);
    const open=async()=>{await evaluate('miniWatch.toggle()',true);await until('!!miniWatch.view');await until('miniWatch.window.document.styleSheets.length===2');
      await evaluate('new Promise(resolve=>miniWatch.window.requestAnimationFrame(()=>miniWatch.window.requestAnimationFrame(resolve)))');};
    const close=()=>evaluate('miniWatch.close()');
    const read=()=>evaluate(`(()=>{const w=miniWatch.window,v=miniWatch.view,d=w.document;return {
      outer:[w.outerWidth,w.outerHeight],position:[w.screenX,w.screenY],inner:[w.innerWidth,w.innerHeight],screen:[w.screen.availWidth,w.screen.availHeight],dpr:w.devicePixelRatio,
      request:probeRequests.at(-1),desired:v.fitHeight(),rows:v.promptRows.size,accounts:v.lines.size,expanded:!v.earlier.hidden,
      scroll:[d.documentElement,...v.root.querySelectorAll('*')].filter(n=>n.scrollHeight>n.clientHeight+1 && ['auto','scroll'].includes(w.getComputedStyle(n).overflowY)).map(n=>({tag:n.tagName,class:n.className,client:n.clientHeight,scroll:n.scrollHeight})),
      header:(${require('./probe_mini_width.cjs').inspect.toString()})(v),
      bodyHeight:d.body.getBoundingClientRect().height,rootHeight:v.root.getBoundingClientRect().height,
      promptRows:[...v.body.children].map(n=>n.getBoundingClientRect().height)};})()`);
    const layouts=evidence.layouts;
    const captureOpening=async(label='opening')=>{
      for(const target of (await command('Target.getTargets')).targetInfos.filter(t=>t.targetId!==targetId && t.type==='page')) {
        const attached=await command('Target.attachToTarget',{targetId:target.targetId,flatten:true});
        if(!await evaluate('!!document.querySelector(".mini-watch")',false,attached.sessionId))continue;
        const image=await command('Page.captureScreenshot',{format:'png'},attached.sessionId);
        await fs.writeFile(output.replace(/\.json$/,`-${label}.png`),Buffer.from(image.data,'base64'));return;
      }
      throw new Error('No native PiP screenshot target');
     };
     if(scope==='high-scale'){
       await require('./probe_mini_clamp.cjs')({evaluate,command,targetId,open,close,read,capture:captureOpening,fixture,until,layouts,checks:evidence.checks});
       evidence.outcome='PASS';return;
     }
      if(scope!=='manual-only')await require('./probe_mini_width.cjs')({evaluate,command,sessionId,targetId,open,close,read,capture:captureOpening,layouts,checks:evidence.checks});
      if(scope==='width-only'){evidence.outcome='PASS';return;}
      await require('./probe_mini_disclosure.cjs').fit({evaluate,until,fixture,command,sessionId,targetId,open,close,read,capture:captureOpening,layouts,checks:evidence.checks});
      if(scope==='manual-only'){evidence.outcome='PASS';return;}
    for(const [prompts,accounts,flags] of [[0,0,''],[1,1,''],[2,3,''],[4,6,'-long'],[2,6,'-long-warning']]) {
      await fixture(`density-${prompts}-${accounts}${flags.replace('-warning','')}`);
      await until(`liveValue.view.active_cards.length===${prompts} && liveValue.view.accounts.accounts.length===${accounts}`);
      if(flags.includes('warning'))await evaluate(`(()=>{const p=structuredClone(liveValue);p.view.now_ms++;p.view.daily_usage.total.complete=false;
        for(const item of p.view.accounts.accounts){item.observation.has_warning=true;item.observation.label+=' long account warning '.repeat(4);}miniWatch.update(p);})()`);
      await open(); const value=await read();
       assert.ok(value.request.width>0 && value.outer[0]>0,JSON.stringify(value));
      if(!value.header.fits) {
        assert.ok(value.outer[0]+2<value.request.width+16,JSON.stringify(value));
        assert.match(await evaluate('miniWatch.feedback.textContent'),/Browser size limits/);
        value.widthLimitedByBrowser=true;
      }
      assert.equal(value.header.documentOverflow,false,JSON.stringify(value));
      assert.ok(value.outer[1]<=Math.min(1000,value.screen[1])+1,JSON.stringify(value));
      if(value.outer[1]+2>=value.desired)assert.deepEqual(value.scroll,[],JSON.stringify(value));
      else value.limitedByBrowser=true;
      layouts.push({case:`open-${prompts}-${accounts}${flags}`,...value});
      assert.equal(value.rows,prompts); assert.equal(value.accounts,accounts);
      // Consuming the initial reserve must fit without any native size adjustment.
      if(prompts<2) {
        const before=value.outer;
        await fixture(`density-2-${accounts}`);await until('miniWatch.view.promptRows.size===2');
        const two=await read(); assert.deepEqual(two.outer,before);
        if(!value.widthLimitedByBrowser && !value.limitedByBrowser)assert.deepEqual(two.scroll,[],JSON.stringify(two));
        else if(two.scroll.length)assert.ok(two.scroll.some(n=>n.tag==='HTML'),'native clamps retain document scrolling');
      }
      await close();
    }
    evidence.checks.push('Opening real layout and two-row reserve; actual native clamps recorded separately from uncapped no-scroll cases');
    await require('./probe_history_readiness.cjs')({fixture,evaluate,until,command,sessionId,open,close,checks:evidence.checks});
    const disclosureAccounts=Number(zoom)===1?3:1;
    await fixture(`history-3-1-${disclosureAccounts}`);await until(`liveValue.view.history_cards.length===3 && liveValue.view.accounts.accounts.length===${disclosureAccounts}`);
    await open();
    const targets=await command('Target.getTargets');let pip;
    for(const target of targets.targetInfos.filter(t=>t.targetId!==targetId&&t.type==='page')) {
      const attached=await command('Target.attachToTarget',{targetId:target.targetId,flatten:true});
      if(await evaluate('!!document.querySelector(".mini-watch")',false,attached.sessionId)){pip=attached.sessionId;break;}
    }
    assert.ok(pip);
    const settle=()=>evaluate('new Promise(resolve=>miniWatch.window.requestAnimationFrame(()=>miniWatch.window.requestAnimationFrame(resolve)))');
    const toggle=async keyboard=>{
      if(keyboard) {
        await evaluate(`miniWatch.view.earlierToggle.focus()`);
        for(const type of ['keyDown','keyUp']) await command('Input.dispatchKeyEvent',{type,key:keyboard,code:keyboard===' '?'Space':keyboard,windowsVirtualKeyCode:keyboard===' '?32:13,...(type==='keyDown'?{text:keyboard===' '?' ':'\r'}:{})},pip);
      } else {
        const point=await evaluate(`(()=>{const r=miniWatch.view.earlierToggle.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
        for(const type of ['mousePressed','mouseReleased'])await command('Input.dispatchMouseEvent',{type,button:'left',clickCount:1,...point},pip);
      }
      await settle();
    };
    await command('Page.bringToFront',{},pip);
    await evaluate(`(()=>{const w=miniWatch.window;w.probeResizes=[];for(const name of ['resizeTo','resizeBy']){const native=w[name].bind(w);w[name]=(...args)=>{w.probeResizes.push({name,args,active:w.navigator.userActivation.isActive});return native(...args);}}})()`);
    const initial=await read();await toggle();const firstExpanded=await read();await toggle();
    layouts.push({case:'initial-native-disclosure-clamp',before:initial,expanded:firstExpanded,compact:await read()});
    // Chromium's headless native display can clamp ~650 on the first resize even
    // when DOM screen.availWidth reports 1920. Exercise unclamped width separately.
    await evaluate('miniWatch.window.resizeTo(600,300)',true);await settle();
    const stableWidth=(await read()).outer[0];
    for(const keyboard of [null,'Enter',' ']) {
      const before=await read();await toggle(keyboard);const expanded=await read();
      assert.equal(expanded.expanded,true);assert.ok(expanded.outer[1]>before.outer[1],JSON.stringify({before,expanded}));
      assert.ok(Math.abs(expanded.outer[0]-before.outer[0])<=1,JSON.stringify({before,expanded}));assert.deepEqual(expanded.scroll,[]);
      await toggle(keyboard);const compact=await read();assert.equal(compact.expanded,false);
      assert.ok(compact.outer[1]<expanded.outer[1]);assert.ok(Math.abs(compact.outer[0]-stableWidth)<=1,JSON.stringify(compact));assert.deepEqual(compact.scroll,[]);
      layouts.push({case:keyboard?'keyboard-'+keyboard:'pointer',before,expanded,compact});
    }
    const size=async(width,height)=>{await evaluate(`miniWatch.window.resizeTo(${width},${height})`,true);await settle();};
    await toggle();await size(600,400);const manualBefore=await read();await toggle();const manual=await read();
    assert.ok(Math.abs(manual.outer[0]-manualBefore.outer[0])<=1);assert.ok(manual.outer[1]<manualBefore.outer[1]);layouts.push({case:'fit-manual-width',...manual});
    const calls=await evaluate('miniWatch.window.probeResizes.length');const passiveBefore=(await read()).outer;
    await fixture('density-20-6-long');await until('miniWatch.view.promptRows.size===20');
    const overflow=await read();assert.ok(overflow.scroll.some(n=>n.tag==='HTML'));layouts.push({case:'passive-overflow',...overflow});
    for(const command of ['terminal','empty','running']){await fixture(command);await until('miniWatch.publication.view.now_ms===liveValue.view.now_ms');}
    assert.equal(await evaluate('miniWatch.window.probeResizes.length'),calls);assert.deepEqual((await read()).outer,passiveBefore);
    evidence.checks.push('Native pointer, Enter and Space expand/shrink; current manual width retained; advancing SSE never resizes');
    await until('!miniWatch.window.navigator.userActivation.isActive && !navigator.userActivation.isActive');
    const inactive=(await read()).outer;await evaluate('miniWatch.view.earlierToggle.click()');await settle();
    assert.deepEqual((await read()).outer,inactive);assert.equal((await read()).expanded,true);
    await evaluate('miniWatch.view.earlierToggle.click()');
    const settings=async(field,endpoint,value)=>evaluate(`(async()=>applySettings(await api('/api/settings/${endpoint}',{${field}:'${value}'})))()`);
    await close();
    for(const position of ['remember-last','standard'])for(const mode of ['fit-on-open','remember-last']) {
      await settings('miniWatchPlacement','mini-placement',position);await settings('miniWatchSize','mini-size',mode);
      await open();await size(520,420);const manuallySized=await read();await close();await open();const restored=await read();
      if(position==='remember-last'&&mode==='remember-last')assert.ok(Math.abs(restored.outer[0]-manuallySized.outer[0])<=1,JSON.stringify({manuallySized,restored}));
      else assert.equal(restored.request.preferInitialWindowPlacement,true,JSON.stringify(restored));
      layouts.push({case:position+'-'+mode,...restored});await close();
    }
    await settings('miniWatchSize','mini-size','default');await settings('miniWatchPlacement','mini-placement','default');
    const saved=JSON.parse(await fs.readFile(path.join(config,'config/user-config.jsonc'),'utf8'));
    assert.deepEqual(saved,{webSettings:{theme:'default',miniWatchPlacement:'default',miniWatchSize:'default'}});
    assert.equal(await evaluate('probeStreams'),1);
    assert.deepEqual(await evaluate('({local:localStorage.length,session:sessionStorage.length})'),{local:0,session:0});
    await fixture('history-3-1-1');await until('liveValue.view.accounts.accounts.length===1');
    await settings('miniWatchSize','mini-size','remember-last');await open();
    for(const target of (await command('Target.getTargets')).targetInfos.filter(t=>t.targetId!==targetId&&t.type==='page')) {
      const attached=await command('Target.attachToTarget',{targetId:target.targetId,flatten:true});
      if(await evaluate('!!document.querySelector(".mini-watch")',false,attached.sessionId)){pip=attached.sessionId;break;}
    }
    await command('Page.bringToFront',{},pip);await size(520,250);
    const remembered=await read();await toggle();const grown=await read();assert.ok(grown.outer[1]>remembered.outer[1]);
    await toggle();(await read()).outer.forEach((value,index)=>assert.ok(Math.abs(value-remembered.outer[index])<=1));
    await toggle();await size(520,350);const changed=await read();await toggle();assert.deepEqual((await read()).outer,changed.outer);
    layouts.push({case:'remembered-disclosure-manual-invalidation',before:remembered,grown,manual:changed});
    for(const theme of ['classic','web'])for(const color of ['light','dark']) {
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:color}]},sessionId);
      await settings('theme','theme',theme);
      const colors=await evaluate(`({owner:getComputedStyle(document.documentElement).getPropertyValue('--bg'),mini:miniWatch.window.getComputedStyle(miniWatch.window.document.body).backgroundColor})`);
      layouts.push({case:theme+'-'+color,...colors,...await read()});
      assert.ok(colors.mini!=='rgba(0, 0, 0, 0)');
    }
      await require('./probe_mini_activity.cjs')({evaluate,until,fixture,command,pip,ownerSession:sessionId,layouts,checks:evidence.checks});
      await require('./probe_mini_session_alignment.cjs')({evaluate,until,fixture,command,sessionId,pipSession:pip,layouts,checks:evidence.checks});
     const capture=await command('Page.captureScreenshot',{format:'png'},pip);
    await fs.writeFile(output.replace(/\.json$/,'-fit.png'),Buffer.from(capture.data,'base64'));
    await close();await settings('miniWatchSize','mini-size','default');
    evidence.checks.push('Absent activation keeps disclosure functional; four position/size intentions and symbolic defaults round-trip; browser coupling/remembered width measured; one SSE/no geometry storage');
    await fixture('density-40-6-long');await until('liveValue.view.active_cards.length===40');await open();
    const capped=await read();assert.ok(capped.request.height<=952);assert.ok(capped.outer[1]<=1000);
    assert.equal(capped.rows,40);assert.equal(capped.accounts,6);assert.ok(capped.scroll.some(n=>n.tag==='HTML'));
    await evaluate('miniWatch.window.scrollTo(0,miniWatch.window.document.documentElement.scrollHeight)');
    assert.ok(await evaluate('miniWatch.window.scrollY>0'));layouts.push({case:'capped-accessible-scroll',...capped});
    await size(280,300);
    const narrow=await evaluate(`(()=>{const w=miniWatch.window,v=miniWatch.view;return {horizontal:v.prompts.scrollWidth>v.prompts.clientWidth,
      documentOverflow:w.document.documentElement.scrollWidth>w.innerWidth+1,rows:v.promptRows.size,accounts:v.lines.size};})()`);
    assert.equal(narrow.horizontal,true);assert.equal(narrow.documentOverflow,false);assert.equal(narrow.rows,40);assert.equal(narrow.accounts,6);
    layouts.push({case:'narrow-horizontal-panning',...narrow});await close();
    evidence.outcome='PASS';
  } catch(error) {evidence.error=String(error.stack||error);throw error;}
  finally {
    await fs.writeFile(output,JSON.stringify(evidence,null,2));clearTimeout(deadline);
    try{await command('Browser.close');}catch(_){}child.kill();server.stdin.end();
    for(const item of pending.values())clearTimeout(item.timer);
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
