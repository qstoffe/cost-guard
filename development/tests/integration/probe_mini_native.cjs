// Explicitly authorized native geometry ONLY: disposable Chrome, synthetic data,
// owned-PID Win32 measurement, CDP input, no personal profile or focus cycling.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output, mode = 'baseline', zoomArgument = '1'] = process.argv.slice(2);
async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output));
  assert.ok(['baseline', 'final'].includes(mode));
  const requestedZoom = Number(zoomArgument);
  assert.ok([.8, 1, 1.25, 1.5].includes(requestedZoom));
  await fs.stat(browser); await fs.stat(path.dirname(output));
  const profile = await fs.mkdtemp(path.join(path.dirname(output), 'mini-native-'));
  const server = spawn('py', ['-3', 'development/tests/integration/serve_mini_watch.py'], {windowsHide:true, stdio:['pipe','pipe','pipe']});
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const next = async () => JSON.parse((await lines.next()).value);
  const child = spawn(browser, ['--no-first-run', '--no-default-browser-check', '--disable-extensions',
    '--disable-background-networking', '--remote-debugging-pipe', '--user-data-dir=' + profile, 'about:blank'],
    {windowsHide:true, stdio:['ignore','ignore','ignore','pipe','pipe']});
  const pending = new Map(); let sequence = 0, buffer = '', helper;
  child.stdio[4].on('data', chunk => {
    buffer += chunk.toString(); let index;
    while ((index = buffer.indexOf('\0')) >= 0) {
      const value = JSON.parse(buffer.slice(0,index)); buffer = buffer.slice(index+1);
      if (value.id) {
        const entry = pending.get(value.id); pending.delete(value.id);
        if (entry) {clearTimeout(entry.timer); value.error ? entry.reject(new Error(JSON.stringify(value.error))) : entry.resolve(value.result);}
      }
    }
  });
  const command = (method, params = {}, sessionId) => new Promise((resolve,reject) => {
    const id = ++sequence, timer = setTimeout(() => {pending.delete(id); reject(new Error('CDP timeout: '+method));}, 15000);
    pending.set(id, {resolve,reject,timer});
    child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId ? {sessionId} : {})})+'\0');
  });
  const deadline = setTimeout(() => {helper?.kill(); child.kill(); server.kill();}, 150000);
  const observations = []; let evidence;
  try {
    const launch = await next(); // Private bootstrap stays in process memory.
    const version = await command('Browser.getVersion');
    const targets = await command('Target.getTargets');
    const targetId = targets.targetInfos.find(item=>item.type==='page').targetId;
    const {sessionId} = await command('Target.attachToTarget', {targetId,flatten:true});
    await command('Page.enable', {}, sessionId);
    const evaluate = async (expression, userGesture=false) => {
      const value = await command('Runtime.evaluate', {expression,returnByValue:true,awaitPromise:true,userGesture}, sessionId);
      if (value.exceptionDetails) throw new Error(JSON.stringify(value.exceptionDetails));
      return value.result.value;
    };
    const until = async expression => {
      const end = Date.now()+15000;
      while (Date.now()<end) {if (await evaluate(expression)) return; await new Promise(resolve=>setTimeout(resolve,50));}
      throw new Error('Condition not reached: '+expression);
    };
    // Browser-owned settings API establishes real default browser zoom, not pinch/CSS emulation.
    await command('Page.navigate', {url:'chrome://settings/appearance'}, sessionId);
    await until(`typeof chrome.settingsPrivate?.getDefaultZoom === 'function'`);
    await evaluate(`new Promise(resolve=>chrome.settingsPrivate.setDefaultZoom(${requestedZoom},resolve))`);
    const defaultZoom = await evaluate(`new Promise(resolve=>chrome.settingsPrivate.getDefaultZoom(resolve))`);
    assert.ok(Math.abs(defaultZoom-requestedZoom)<.001,'browser-owned setting must confirm real page zoom');
    await command('Page.navigate', {url:launch.url}, sessionId);
    await until(`typeof miniWatch !== 'undefined' && hostState.kind === 'connected' && liveValue?.view?.running?.count === 2`);
    await evaluate(`(() => {const api=documentPictureInPicture,native=api.requestWindow.bind(api); api.requestWindow=async options=>{
      try {const w=await native(options),resize=w.resizeTo.bind(w); w.resizeTo=(...args)=>{try{return resize(...args);}catch(e){window.geometryError=e.name+': '+e.message;throw e;}};return w;}
      catch(e){window.geometryError=e.name+': '+e.message;throw e;}};})()`);
    if (mode === 'baseline') await evaluate(`(() => {const api=documentPictureInPicture,native=api.requestWindow.bind(api); api.requestWindow=options=>native({...options,height:450});})()`);
    const measure = async (name, action = 'miniWatch.toggle()') => {
      const file = output.replace(/\.json$/, '') + '-' + name + '.json';
      helper = spawn('py', ['-3','development/tests/integration/mini_native_geometry.py','--pid',String(child.pid),'--output',file],
        {windowsHide:true,stdio:['ignore','pipe','pipe']});
      let errors=''; helper.stderr.on('data', value=>errors+=value);
      const helperLines = readline.createInterface({input:helper.stdout})[Symbol.asyncIterator]();
      assert.equal(JSON.parse((await helperLines.next()).value).ready,true);
      await evaluate(action,true);
      const opening = await evaluate(`({on:!!miniWatch.window,feedback:miniWatch.feedback.textContent,error:window.geometryError})`);
      assert.ok(opening.on,JSON.stringify(opening));
      await until(`!!miniWatch.window && miniWatch.window.getComputedStyle(miniWatch.view.prompts).overflowY === 'auto'`);
      const dom = await evaluate(`(() => {const w=miniWatch.window,v=miniWatch.view; return {
        innerWidth:w.innerWidth,innerHeight:w.innerHeight,outerWidth:w.outerWidth,outerHeight:w.outerHeight,dpr:w.devicePixelRatio,
        screenWidth:w.screen.width,screenHeight:w.screen.height,screenAvailHeight:w.screen.availHeight,
        viewportScale:w.visualViewport.scale,ownerDpr:devicePixelRatio,ownerInnerWidth:innerWidth,ownerOuterWidth:outerWidth,header:v.root.firstElementChild.textContent,
        horizontal:w.document.documentElement.scrollWidth>w.innerWidth,vertical:w.document.documentElement.scrollHeight>w.innerHeight,
        health:v.health.textContent};})()`);
      const end = await helperLines.next();
      if (end.done) throw new Error('Native helper failed: '+errors);
      const native = JSON.parse(end.value);
      if (helper.exitCode === null) await new Promise(resolve=>helper.once('close',resolve)); helper = null;
      observations.push({name,dom,nativeFile:path.basename(file),native});
      assert.equal(native.final.filter(item=>item.capture).length,1,'one new owned native PiP frame must be captured');
      if (mode === 'final') {
        const pip = native.final.find(item=>item.capture);
        const opening = native.samples.flatMap(sample=>sample.windows).filter(item=>item.hwnd===pip.hwnd);
        assert.ok(opening.every(item=>item.window[3]-item.window[1]<=470),'no sampled initial outer-frame overshoot');
        assert.ok(pip.visibleFrame[3]-pip.visibleFrame[1]<=470,'actual visible native frame must fit physical cap');
        assert.equal(dom.horizontal,false); assert.equal(dom.vertical,false);
      }
    };
    await measure('first-open');
    if (mode === 'final') {
      await evaluate(`miniWatch.window.resizeTo(700,600)`,true);
      await until(`miniWatch.window.outerHeight >= 590`);
      await evaluate(`miniWatch.close()`);
      server.stdin.write(JSON.stringify({command:'density-6-4-warning'})+'\n'); await next();
      await until(`liveValue.view.active_cards.length === 6`);
      await measure('reopen-dense');
    }
    evidence = {outcome:'MEASURED',browser:version.product,defaultBrowserZoom:defaultZoom,mode,observations,
      limitations:['Owner personal Chrome zoom unknown; disposable own profile only. Physical capture requires visual inspection. No actual alternate Windows display settings tested.']};
  } catch(error) {evidence={outcome:'FAIL',reason:error.stack,observations}; process.exitCode=1;}
  finally {
    clearTimeout(deadline); helper?.kill();
    try {await command('Browser.close');} catch {}
    server.stdin.end();
    await new Promise(resolve=>{if(child.exitCode!==null) resolve(); else {child.once('exit',resolve);setTimeout(resolve,3000);}});
    if(child.exitCode===null) child.kill();
    if(server.exitCode===null) server.kill();
    try {await fs.rm(profile,{recursive:true});} catch {}
    await fs.writeFile(output,JSON.stringify(evidence,null,2)+'\n'); console.log(JSON.stringify(evidence));
  }
}
main().catch(error=>{console.error(error.stack);process.exitCode=1;});
