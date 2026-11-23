// Hidden, owned Chromium only. Native dialog success is NOT claimed by this probe.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output] = process.argv.slice(2);
async function main() {
  const directory = path.dirname(output);
  const profile = await fs.mkdtemp(path.join(directory, 'export-browser-'));
  const workspace = await fs.mkdtemp(path.join(directory, 'export-host-'));
  const downloads = path.join(workspace, 'downloads'); await fs.mkdir(downloads);
  await fs.mkdir(path.join(profile,'Default'));
  await fs.writeFile(path.join(profile,'Default','Preferences'),JSON.stringify({
    download:{default_directory:downloads,prompt_for_download:false}
  }));
  const server = spawn(process.env.COST_GUARD_TEST_PYTHON || 'python', ['development/tests/integration/serve_session_export.py', workspace],
    {windowsHide:true, stdio:['pipe','pipe','pipe']});
  const serverExit = new Promise(resolve => server.once('exit', resolve));
  let serverError = ''; server.stderr.on('data', value => serverError += value.toString());
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const fixture = async command => { server.stdin.write(JSON.stringify({command})+'\n'); return JSON.parse((await lines.next()).value); };
  const child = spawn(browser, ['--headless=new', '--no-first-run', '--no-default-browser-check', '--disable-extensions',
    '--disable-background-networking', '--remote-debugging-pipe', '--user-data-dir='+profile, 'about:blank'],
    {windowsHide:true, stdio:['ignore','ignore','ignore','pipe','pipe']});
  const browserExit = new Promise(resolve => child.once('exit', resolve));
  const pending = new Map(); let sequence = 0, buffer = '', sessionId;
  child.stdio[4].on('data', value => {
    buffer += value.toString(); let end;
    while ((end = buffer.indexOf('\0')) >= 0) {
      const message = JSON.parse(buffer.slice(0, end)); buffer = buffer.slice(end+1);
      if (pending.has(message.id)) {
        const entry = pending.get(message.id); pending.delete(message.id); clearTimeout(entry.timer);
        message.error ? entry.reject(new Error(message.error.message)) : entry.resolve(message.result);
      }
    }
  });
  const command = (method, params={}, target=sessionId) => new Promise((resolve,reject) => {
    const id = ++sequence, timer = setTimeout(() => reject(new Error('CDP timeout: '+method)), 15000);
    pending.set(id,{resolve,reject,timer});
    child.stdio[3].write(JSON.stringify({id,method,params,...(target?{sessionId:target}:{})})+'\0');
  });
  const evaluate = async expression => {
    const result = await command('Runtime.evaluate', {expression,returnByValue:true,awaitPromise:true});
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  const until = async (check, label) => {
    const end = Date.now()+15000;
    while (Date.now()<end) { if (await check()) return; await new Promise(resolve=>setTimeout(resolve,50)); }
    throw new Error('Condition timeout: '+label);
  };
  const point = () => evaluate('(() => {const r=current.detail.exporter.button.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()');
  const hover = async () => command('Input.dispatchMouseEvent', {type:'mouseMoved',...await point()});
  const leave = () => command('Input.dispatchMouseEvent', {type:'mouseMoved',x:1,y:1});
  const click = async () => {
    const position = await point();
    await command('Input.dispatchMouseEvent', {type:'mousePressed',button:'left',clickCount:1,...position});
    await command('Input.dispatchMouseEvent', {type:'mouseReleased',button:'left',clickCount:1,...position});
  };
  const key = async (key, code, windowsVirtualKeyCode) => {
    await command('Input.dispatchKeyEvent', {type:'keyDown',key,code,windowsVirtualKeyCode,
      ...(key==='Enter'?{text:'\r'}:key===' '?{text:' '}:{})});
    await command('Input.dispatchKeyEvent', {type:'keyUp',key,code,windowsVirtualKeyCode});
  };
  const helpVisible = '!!document.querySelector("#context-help:not([hidden])")';
  const quiet = async () => {
    assert.equal(await evaluate(helpVisible), false, 'help closes synchronously');
    assert.equal(await evaluate(`new Promise(resolve => setTimeout(() => resolve(${helpVisible}), ContextHelp.HOVER_DELAY + 100))`), false,
      'stationary pointer and picker focus restoration cannot reopen help');
  };
  const configure = async (theme, width, zoom, coarse) => {
    await command('Emulation.setDeviceMetricsOverride', {width,height:900,deviceScaleFactor:1,mobile:false});
    await command('Emulation.setTouchEmulationEnabled', {enabled:coarse});
    await command('Emulation.setEmulatedMedia', {features:[{name:'prefers-color-scheme',value:theme==='web-light'?'light':'dark'}]});
    await evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme==='classic'?'classic':'web')};document.documentElement.style.zoom=${zoom}`);
  };
  const measure = selector => evaluate(`(() => {
    const button=document.querySelector(${JSON.stringify(selector)}), s=getComputedStyle(button), r=button.getBoundingClientRect();
    return {fontFamily:s.fontFamily,fontSize:s.fontSize,fontWeight:s.fontWeight,lineHeight:s.lineHeight,
      padding:s.padding,minHeight:s.minHeight,height:r.height,width:r.width,
      coarse:matchMedia('(pointer:coarse)').matches,noPageOverflow:document.documentElement.scrollWidth<=innerWidth};
  })()`);
  let evidence = {outcome:'FAIL'};
  const deadline = setTimeout(() => {child.kill();server.kill();}, 120000);
  try {
    const ready = await lines.next();
    if (ready.done) throw new Error('Fixture failed: '+serverError);
    const launch = JSON.parse(ready.value);
    const version = await command('Browser.getVersion');
    const {targetId} = await command('Target.createTarget', {url:'about:blank'});
    ({sessionId} = await command('Target.attachToTarget', {targetId,flatten:true}));
    await command('Page.enable');
    await command('Page.navigate', {url:launch.url});
    await until(()=>evaluate('typeof csrf !== "undefined" && !!csrf && hostState.kind === "connected"'), 'authorization');
    await evaluate('location.hash="#/models"');
    await until(()=>evaluate('!!document.querySelector("[data-model-control=refresh]")'), 'Models toolbar');
    const layouts = [];
    for (const theme of ['classic','web-light','web-dark']) for (const width of [1280,360])
      for (const zoom of [1,1.5]) for (const coarse of [false,true]) {
        await configure(theme,width,zoom,coarse);
        layouts.push({theme,width,zoom,coarse,models:await measure('[data-model-control=refresh]')});
      }
    await evaluate(`location.hash='#/sessions/${launch.session}'`);
    await until(()=>evaluate('!!current?.detail?.data && !current.detail.exporter.button.disabled'), 'observed selection');
    const filename = 'Synthetic LIVE-style å 日本語 🚀.zip';
    assert.equal(await evaluate('current.detail.exporter.filename'),filename,'observed detail title, not native payload title');
    for (const value of layouts) {
      await configure(value.theme,value.width,value.zoom,value.coarse);
      value.export=await measure('.session-export > button');
      for (const property of ['fontFamily','fontSize','fontWeight','lineHeight','padding','minHeight','height'])
        assert.equal(value.export[property],value.models[property],property+' parity: '+JSON.stringify(value));
      assert.equal(value.export.coarse,value.coarse);
      assert.equal(value.export.noPageOverflow,true);
      assert.ok(value.export.width<=value.width);
    }
    await configure('classic',1280,1,false);
    assert.equal(await evaluate(`(() => {const a=current.detail.exporter;
      return a.button.textContent==='Export Session Analysis ZIP' && !a.button.hasAttribute('title') &&
        a.root.querySelectorAll('button').length===1 && a.notice.textContent==='' &&
        getComputedStyle(a.notice).display==='none' && current.detail.body.children.length===3;})()`),true);
    await hover(); await until(()=>evaluate(helpVisible),'delayed action help');
    assert.equal(await evaluate('current.detail.exporter.button.getAttribute("aria-describedby")'),'context-help');
    const help = await evaluate('document.querySelector("#context-help").textContent');
    for (const phrase of [/nested subagents/i,/best effort/i,/not guaranteed secret-free or anonymous/i,/review.*before sharing/i])
      assert.match(help,phrase);
    const before = (await fixture('count')).requests;
    const activations = [];
    // Deferred picker doubles preserve the real trusted input/event ordering, but
    // are explicitly not OS dialog success/cancellation evidence.
    for (const activation of ['pointer','Enter','Space','touch','pending-hover']) {
      evidence.stage=activation;
      await leave();
      await evaluate(`window.showSaveFilePicker=options => {window.pickerState={hidden:!(${helpVisible}),active:navigator.userActivation.isActive,filename:options.suggestedName};
        return new Promise((resolve,reject)=>{window.cancelPicker=()=>reject(new DOMException('Cancelled','AbortError'));});};
        current.detail.exporter.button.blur();`);
      if (activation==='Enter' || activation==='Space' || activation==='touch') {
        await evaluate(`window.tabStart=document.createElement('button');current.detail.exporter.root.before(tabStart);tabStart.focus()`);
        await key('Tab','Tab',9);
        await until(()=>evaluate(helpVisible),'keyboard focus help');
        assert.equal(await evaluate('document.activeElement===current.detail.exporter.button'),true,'Tab reaches the export action');
        if (activation==='touch') {
          await command('Emulation.setTouchEmulationEnabled',{enabled:true});
          await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{...await point(),radiusX:1,radiusY:1}]});
          await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
        } else await key(activation==='Space'?' ':activation,activation,activation==='Space'?32:13);
      } else {
        await hover();
        if (activation!=='pending-hover') await until(()=>evaluate(helpVisible),'new intentional hover');
        await click();
      }
      await until(()=>evaluate('!!current.detail.exporter.operation'),'picker pending: '+activation);
      assert.deepEqual(await evaluate('pickerState'),{hidden:true,active:true,filename});
      await quiet(); await evaluate('cancelPicker()');
      await until(()=>evaluate('!current.detail.exporter.operation'),'picker double cancelled');
      await quiet();
      assert.match(await evaluate('current.detail.exporter.notice.textContent'),/cancelled/);
      if (activation==='touch') await command('Emulation.setTouchEmulationEnabled',{enabled:false});
      await evaluate('window.tabStart?.remove()');
      activations.push(activation);
    }
    assert.equal((await fixture('count')).requests,before,'all cancelled activations perform no native export');
    await leave(); await hover(); await until(()=>evaluate(helpVisible),'hover rearms');
    await key('Escape','Escape',27); await quiet();
    // Native-handle double verifies successful commit and synchronous focus help
    // dismissal; actual destination selection is not simulated as an OS PASS.
    await evaluate(`window.saved=[];window.showSaveFilePicker=async()=>({createWritable:async()=>({
      write:async blob=>saved.push(blob.type,Array.from(new Uint8Array(await blob.slice(0,4).arrayBuffer()))),close:async()=>saved.push('closed')})});`);
    await click(); await until(()=>evaluate('current.detail.exporter.notice.textContent.includes("ZIP saved")'),'handle double committed');
    await quiet(); assert.deepEqual(await evaluate('saved'),['application/zip',[80,75,3,4],'closed']);
    // Actual authenticated standard browser download, no picker support.
    await evaluate('window.showSaveFilePicker=undefined');
    await command('Browser.setDownloadBehavior', {behavior:'default'}, null);
    await evaluate('current.detail.exporter.button.focus()');
    await click();
    await until(async()=>{try{await fs.access(path.join(downloads,filename));return true;}catch{return false;}}, 'download');
    const original = await fs.readFile(path.join(downloads,filename));
    assert.equal((await fixture('check-downloads')).checked,1);
    assert.equal(await evaluate('document.activeElement === current.detail.exporter.button'),true);
    await until(()=>evaluate('current.detail.exporter.url === null'), 'object URL release');
    // Browser owns collision policy; a repeated download cannot overwrite the first.
    await click();
    const duplicate = 'Synthetic LIVE-style å 日本語 🚀 (1).zip';
    await until(async()=>{try{await fs.access(path.join(downloads,duplicate));return true;}catch{return false;}}, 'collision suffix');
    assert.deepEqual(await fs.readFile(path.join(downloads,filename)),original);
    assert.equal((await fixture('check-downloads')).checked,2);
    await fixture('invalid');
    await click();
    await until(()=>evaluate('current.detail.exporter.notice.textContent.includes("no complete ZIP was saved")'), 'missing descendant feedback');
    assert.deepEqual((await fs.readdir(downloads)).sort(),[filename,duplicate].sort(), 'no corrupt third download');
    await evaluate('location.hash="#/settings"');
    await until(()=>evaluate('current.section === "settings"'), 'navigation');
    evidence = {outcome:'PASS',browser:version.product,layouts,activations,
      checks:['canonical selected detail','trusted-click picker double activation/cancel without source work',
        'quiet one-action idle layout','computed Models parity across themes/width/zoom/coarse pointer',
        'pointer/Tab/Enter/Space/touch/pending-hover dismissal and stationary suppression','Escape and intentional re-entry',
        'handle-double commit and picker-focus suppression',
         'title-derived picker and actual fallback filename; browser collision suffix without overwrite',
          'all five compressed masked UTF-8 entries checked inside both downloaded ZIPs','focus retained','object URL released',
         'missing descendant saves no partial file','navigation preserved'],
      limitations:['Picker is mocked: actual native destination selection/write/cancel remains unverified.',
        'Synthetic LIVE-style native service, no Desktop session-list visibility assertion.'],
      inference_calls:0,desktop_effects:false};
  } catch(error) {evidence.error=error.stack; evidence.serverError=serverError;}
  finally {
    await command('Browser.close',{},null).catch(()=>{}); await browserExit;
    server.stdin.write('{"command":"stop"}\n'); server.stdin.end(); await serverExit;
    clearTimeout(deadline);
    for (const entry of pending.values()) clearTimeout(entry.timer);
    await fs.rm(profile,{recursive:true,force:true}); await fs.rm(workspace,{recursive:true,force:true});
    await fs.writeFile(output,JSON.stringify(evidence,null,2)+'\n');
  }
  console.log(JSON.stringify(evidence));
  assert.equal(evidence.outcome,'PASS');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
