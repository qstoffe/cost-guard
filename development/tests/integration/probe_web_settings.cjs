// Real hidden Chromium native picker input/layout; disposable HTTP/config/profile only.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output] = process.argv.slice(2);
async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output)); await fs.stat(browser);
  const profile = await fs.mkdtemp(path.join(path.dirname(output), 'settings-browser-'));
  const config = await fs.mkdtemp(path.join(path.dirname(output), 'settings-config-'));
  const server = spawn('py', ['-3', 'development/tests/integration/serve_mini_watch.py', config], {windowsHide:true,stdio:['pipe','pipe','pipe']});
  let serverErrors = ''; server.stderr.on('data', data => {serverErrors = (serverErrors + data).slice(-6000);});
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const child = spawn(browser, ['--headless=new','--no-first-run','--no-default-browser-check','--disable-extensions',
    '--disable-background-networking','--remote-debugging-pipe','--user-data-dir='+profile,'about:blank'],
    {windowsHide:true,stdio:['ignore','ignore','ignore','pipe','pipe']});
  const pending = new Map(); let sequence = 0, buffer = ''; const errors = [], checks = [], layouts = [];
  child.stdio[4].on('data', chunk => {
    buffer += chunk; let index;
    while ((index = buffer.indexOf('\0')) >= 0) {
      const value = JSON.parse(buffer.slice(0,index)); buffer = buffer.slice(index+1);
      if (value.id) { const entry = pending.get(value.id); pending.delete(value.id);
        if (entry) {clearTimeout(entry.timer); value.error ? entry.reject(new Error(JSON.stringify(value.error))) : entry.resolve(value.result);} }
      else if (value.method === 'Runtime.exceptionThrown') errors.push(value.params.exceptionDetails.text);
    }
  });
  const command = (method, params = {}, sessionId) => new Promise((resolve,reject) => {
    const id = ++sequence, timer = setTimeout(() => {pending.delete(id); reject(new Error('CDP timeout: '+method));},15000);
    pending.set(id,{resolve,reject,timer}); child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId ? {sessionId} : {})})+'\0');
  });
  let owner;
  const evaluate = async expression => {
    const result = await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},owner);
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails)); return result.result.value;
  };
  const until = async expression => {
    const end = Date.now()+15000;
    while (Date.now()<end) {if(await evaluate(expression)) return; await new Promise(resolve=>setTimeout(resolve,30));}
    const state = await evaluate(`({focus:document.activeElement?.outerHTML.slice(0,300),open:!!document.querySelector('select:open'),help:document.querySelector('#context-help')?.hidden})`);
    throw new Error('Condition not reached: '+expression+' '+JSON.stringify({state,errors,serverErrors}));
  };
  const key = async (key, code = key, windowsVirtualKeyCode = {Escape:27,Enter:13,Tab:9,ArrowDown:40,ArrowUp:38,' ':32}[key] || 0) => {
    for (const type of ['keyDown','keyUp']) await command('Input.dispatchKeyEvent',{type,key,code,windowsVirtualKeyCode,...(type==='keyDown'&&key.length===1?{text:key}:{})},owner);
  };
  const point = selector => evaluate(`(() => {const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
  const click = async selector => {
    await evaluate(`document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'nearest'})`);
    const p = await point(selector); await command('Input.dispatchMouseEvent',{type:'mouseMoved',...p},owner);
    for (const type of ['mousePressed','mouseReleased']) await command('Input.dispatchMouseEvent',{type,...p,button:'left',clickCount:1},owner);
  };
  const deadline = setTimeout(() => {child.kill();server.kill();},180000);
  let evidence = {outcome:'FAIL'};
  try {
    const launch = JSON.parse((await lines.next()).value); // Never log bootstrap credentials.
    const version = await command('Browser.getVersion');
    const {targetId} = await command('Target.createTarget',{url:'about:blank'});
    ({sessionId:owner} = await command('Target.attachToTarget',{targetId,flatten:true}));
    await command('Page.enable',{},owner); await command('Runtime.enable',{},owner);
    await command('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false},owner);
    await command('Page.navigate',{url:launch.url},owner);
    await until(`typeof csrf!=='undefined' && !!csrf && hostState.kind==='connected'`);
    await evaluate(`location.hash='#/settings'`); await until(`settingsView?.loaded && !settingsView.busy`);
    const capability = await evaluate(`({enhanced:settingsView.enhanced,appearance:CSS.supports('appearance','base-select'),picker:CSS.supports('selector(select::picker(select))'),selected:typeof HTMLSelectedContentElement})`);
    assert.equal(capability.enhanced,true,'actual Chromium customizable picker capability '+JSON.stringify(capability));
    assert.equal(await evaluate(`(() => {const ids=[...document.querySelectorAll('[id]')].map(n=>n.id);return new Set(ids).size===ids.length;})()`),true,'selectedcontent never clones description IDs');
    await evaluate(`window.settingWrites=[];window.settingRequests=[];const originalFetch=window.fetch;window.fetch=(url,options)=>{settingRequests.push(String(url));if(options?.method==='POST')settingWrites.push(String(url));return originalFetch(url,options);}`);
    assert.equal(await evaluate(`getComputedStyle(document.querySelector('.toolbar')).display`),'none');
    assert.equal(await evaluate(`document.querySelector('.web-settings h3, .web-settings .help-copy')===null`),true);
    for (const id of ['web-theme','ccost-unit','mini-placement','mini-size','quota-display']) {
      await click('#'+id); await until(`document.getElementById('${id}').matches(':open')`);
      const values = await evaluate(`[...document.getElementById('${id}').options].map(o=>o.value)`);
      for (const value of values) {
        const selector = `#${id} option[value="${value}"]`;
        await command('Input.dispatchMouseEvent',{type:'mouseMoved',...await point(selector)},owner);
        const facts = await evaluate(`(() => {const o=document.querySelector(${JSON.stringify(selector)}),d=o.querySelector('.settings-choice-help'),r=d.getBoundingClientRect();return {text:d.textContent,visible:getComputedStyle(d).visibility,hover:o.matches(':hover'),left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:innerWidth,height:innerHeight};})()`);
        assert.equal(facts.hover,true); assert.equal(facts.visible,'visible'); assert.ok(facts.text.length>30);
        assert.ok(facts.right>facts.left && facts.bottom>facts.top,'description actually has painted layout, not just a hidden DOM string');
        assert.ok(facts.left>=0&&facts.top>=0&&facts.right<=facts.width&&facts.bottom<=facts.height,JSON.stringify(facts));
        layouts.push({case:'option-hover',id,value,...facts});
      }
      await key('Escape'); assert.equal(await evaluate(`settingWrites.length`),0,'hover/open/Escape never save');
    }
    checks.push('All 15 native options: real pointer hover reveals their own bounded explanation; open/hover/Escape saves nothing');
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:1,y:1},owner);
    await key('Tab'); await evaluate(`document.getElementById('web-theme').focus()`);
    await key(' ' ,'Space'); await until(`document.getElementById('web-theme').matches(':open')`);
    await key('ArrowDown');
    const active = await evaluate(`(() => {const o=document.querySelector('#web-theme option:focus');return {value:o?.value,description:o?.getAttribute('aria-describedby'),visible:o&&getComputedStyle(o.querySelector('.settings-choice-help')).visibility};})()`);
    assert.ok(active.value); assert.equal(active.visible,'visible'); assert.ok(active.description);
    assert.equal(await evaluate(`settingWrites.length`),0,'keyboard preview never saves');
    await key('Escape'); assert.equal(await evaluate(`document.getElementById('web-theme').value`),'default');
    await click('#web-theme'); await click('#web-theme option[value="web"]');
    await until(`!settingsView.busy && settingsView.confirmed.theme==='web'`);
    assert.equal(await evaluate(`settingWrites.length`),1); assert.match(await evaluate(`settingsView.feedback.textContent`),/saved/);
    await command('Page.reload',{},owner); await until(`typeof settingsView!=='undefined' && settingsView?.loaded && !settingsView.busy`);
    assert.equal(await evaluate(`document.getElementById('web-theme').value`),'web');
    checks.push('Native Space/Arrow/Escape preview and cancellation; actual pointer commitment writes once through HTTP and survives reload');
    for (const theme of ['classic','light','dark']) for (const width of [1280,520,360]) for (const zoom of [1,2]) {
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},owner);
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},owner);
      await evaluate(`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}';document.documentElement.style.zoom='${zoom}'`);
      const facts = await evaluate(`(() => {const s=[...document.querySelectorAll('.web-settings select')],r=s.map(n=>n.getBoundingClientRect()),root=getComputedStyle(settingsView.root);return {overflow:document.documentElement.scrollWidth>innerWidth,starts:r.map(n=>n.left),heights:r.map(n=>n.height),frame:root.borderTopWidth,shadow:root.boxShadow,padding:root.paddingTop};})()`);
      assert.equal(facts.overflow,false,JSON.stringify({theme,width,zoom,...facts}));
      assert.equal(new Set(facts.starts).size,1); assert.equal(facts.frame,'0px'); assert.equal(facts.shadow,'none'); assert.equal(facts.padding,'0px');
      if (zoom===1) assert.ok(facts.heights.every(h=>h>=32&&h<=36));
      layouts.push({case:'layout',theme,width,zoom,...facts});
      await click('#mini-size'); await until(`document.getElementById('mini-size').matches(':open')`);
      await evaluate(`document.querySelector('#mini-size option[value="fit-on-open"]').scrollIntoView({block:'nearest'})`);
      await command('Input.dispatchMouseEvent',{type:'mouseMoved',...await point('#mini-size option[value="fit-on-open"]')},owner);
      const bounds = await evaluate(`(() => {const r=document.querySelector('#mini-size option[value="fit-on-open"] .settings-choice-help').getBoundingClientRect();return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:innerWidth,height:innerHeight};})()`);
      assert.ok(bounds.left>=0&&bounds.top>=0&&bounds.right<=bounds.width,JSON.stringify({theme,width,zoom,...bounds}));
      if (bounds.bottom>bounds.height && bounds.bottom-bounds.top>bounds.height) {
        // Narrow native pickers stack the complete descriptions in their own
        // scrollport. A tall description need not fit all at once, but its end
        // must be reachable without document overflow or clipped text.
        const end=await evaluate(`(()=>{const n=document.querySelector('#mini-size option[value="fit-on-open"] .settings-choice-help');n.scrollIntoView({block:'end'});const r=n.getBoundingClientRect();return {bottom:r.bottom,overflow:document.documentElement.scrollWidth>innerWidth};})()`);
        assert.ok(end.bottom>0&&end.bottom<=bounds.height,JSON.stringify({theme,width,zoom,...end}));
        assert.equal(end.overflow,false);
      } else assert.ok(bounds.bottom<=bounds.height,JSON.stringify({theme,width,zoom,...bounds}));
      await key('Escape');
    }
    checks.push('Classic/Web light/dark × 1280/520/360 × CSS zoom 100/200%: no page overflow, aligned controls, unframed rows, bounded native option help');
    await evaluate(`document.documentElement.style.zoom=''`);
    await command('Emulation.setDeviceMetricsOverride',{width:390,height:850,deviceScaleFactor:1,mobile:true},owner);
    await command('Emulation.setTouchEmulationEnabled',{enabled:true},owner);
    const p = await point('#quota-display');
    for (const type of ['touchStart','touchEnd']) await command('Input.dispatchTouchEvent',{type,touchPoints:type==='touchStart'?[p]:[]},owner);
    await until(`document.getElementById('quota-display').matches(':open')`);
    assert.equal(await evaluate(`[...document.querySelectorAll('#quota-display option .settings-choice-help')].every(n=>getComputedStyle(n).visibility==='visible')`),true,'touch can inspect all descriptions before a committing tap');
    await key('Escape'); await command('Emulation.setTouchEmulationEnabled',{enabled:false},owner);
    checks.push('Real emulated touch opens native picker with every description visible before selection');
    await command('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false},owner);
    await evaluate(`scrollTo(0,0)`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...await point('label[for="web-theme"]')},owner);
    await until(`document.querySelector('#context-help')?.matches(':popover-open')`);
    assert.match(await evaluate(`document.querySelector('#context-help').textContent`),/Appearance of Web.*Terminal colors/);
    assert.equal(await evaluate(`getComputedStyle(document.querySelector('label[for="web-theme"]')).cursor`),'help');
    await key('Escape'); await key('Tab'); await evaluate(`document.getElementById('web-theme').focus()`);
    await until(`document.querySelector('#context-help')?.matches(':popover-open')`);
    assert.match(await evaluate(`document.querySelector('#context-help').textContent`),/system’s light or dark/);
    assert.equal(await evaluate(`document.activeElement.getAttribute('aria-describedby')`),'settings-feedback context-help');
    await click('#web-theme'); await until(`document.getElementById('web-theme').matches(':open')`);
    assert.equal(await evaluate(`document.querySelector('#context-help').hidden`),true,'picker activation dismisses selected-value tooltip');
    const ax = await command('Accessibility.getFullAXTree',{},owner);
    assert.ok(ax.nodes.some(n=>n.role?.value==='combobox'&&n.name?.value==='Theme'));
    assert.ok(ax.nodes.some(n=>n.role?.value==='option'&&n.name?.value==='Web'&&/system’s light or dark/.test(n.description?.value)),'native option accessible description');
    await key('Escape');
    await fs.chmod(path.join(config,'config/user-config.jsonc'),0o444);
    await click('#web-theme'); await click('#web-theme option[value="classic"]');
    await until(`!settingsView.busy && settingsView.feedback.className==='error'`);
    assert.equal(await evaluate(`document.getElementById('web-theme').value`),'web','failed write rolls back');
    assert.match(await evaluate(`settingsView.feedback.textContent`),/Cannot write/);
    await fs.chmod(path.join(config,'config/user-config.jsonc'),0o600);
    await click('#web-theme'); await key('ArrowUp'); await key('Enter');
    await until(`!settingsView.busy && settingsView.feedback.className==='success'`);
    checks.push('Shared setting-label/value help, action dismissal, native AX name/option description, real readonly failure rollback and keyboard Enter retry');
    const defaultPath = path.join(config,'config/default-config.jsonc'), originalDefaults = await fs.readFile(defaultPath,'utf8');
    assert.match(originalDefaults,/"theme": "classic"/);
    await fs.writeFile(defaultPath,originalDefaults.replace('"theme": "classic"','"theme": "web"'));
    await evaluate(`settingsView.read()`);
    assert.equal(await evaluate(`document.getElementById('web-theme').value`),'classic','equal explicit choice stays pinned when the shipped default changes');
    assert.match(await evaluate(`document.querySelector('#web-theme option').textContent`),/Default \(Web\).*currently Web.*system’s light or dark/);
    await click('#web-theme'); await click('#web-theme option[value="default"]');
    await until(`!settingsView.busy && settingsView.confirmed.theme==='default'`);
    assert.equal(await evaluate(`document.documentElement.dataset.theme`),'web');
    checks.push('Changed shipped default refreshes native label/help while explicit Classic stays pinned; selecting Default inherits Web');
    await key('Tab'); await evaluate(`document.querySelector('label[for="web-theme"]').focus()`);
    await until(`document.querySelector('#context-help')?.matches(':popover-open')`);
    await evaluate(`location.hash='#/watch'`); await until(`document.body.dataset.section==='watch'`);
    await until(`document.querySelector('#context-help').hidden`);
    await evaluate(`location.hash='#/settings'`); await until(`settingsView.loaded && !settingsView.busy && document.body.dataset.section==='settings'`);
    checks.push('Route removal dismisses label help without preventing navigation');
    // Change zoom only inside this disposable hidden browser profile, never the personal browser.
    const settingsURL = path.basename(browser).toLowerCase()==='msedge.exe' ? 'edge://settings/appearance' : 'chrome://settings/appearance';
    const origin = new URL(launch.url).origin;
    await command('Emulation.clearDeviceMetricsOverride',{},owner);
    const nativeWindow = await command('Browser.getWindowForTarget',{targetId});
    await command('Browser.setWindowBounds',{windowId:nativeWindow.windowId,bounds:{width:1280,height:1000}});
    await command('Page.navigate',{url:settingsURL},owner);
    await until(`typeof chrome.settingsPrivate?.getDefaultZoom==='function'`);
    await evaluate(`new Promise(resolve=>chrome.settingsPrivate.setDefaultZoom(2,resolve))`);
    assert.equal(await evaluate(`new Promise(resolve=>chrome.settingsPrivate.getDefaultZoom(resolve))`),2);
    await command('Page.navigate',{url:origin+'/#/settings'},owner);
    await until(`typeof settingsView!=='undefined' && settingsView?.loaded && !settingsView.busy`);
    assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth`),true);
    await key('Tab');await evaluate(`document.getElementById('mini-size').focus()`);await key(' ','Space');
    await until(`document.getElementById('mini-size').matches(':open')`);
    await evaluate(`document.querySelector('#mini-size option[value="fit-on-open"]').scrollIntoView({block:'nearest'})`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...await point('#mini-size option[value="fit-on-open"]')},owner);
    const image = await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},owner);
    await fs.writeFile(output.replace(/\.json$/,'')+'-zoom.png',Buffer.from(image.data,'base64'));
    await key('Escape');
    layouts.push({case:'true-browser-zoom',...await evaluate(`({width:innerWidth,dpr:devicePixelRatio,overflow:document.documentElement.scrollWidth>innerWidth})`)});
    checks.push('Actual disposable-profile browser zoom 200%: Settings and native picker remain usable without page overflow');
    // Force only the progressive-enhancement capability off, then exercise the real native fallback.
    await command('Page.addScriptToEvaluateOnNewDocument',{source:`const supports=CSS.supports.bind(CSS);CSS.supports=(...args)=>args.includes('base-select')?false:supports(...args);`},owner);
    await command('Page.reload',{},owner);
    await until(`typeof settingsView!=='undefined' && settingsView?.loaded && !settingsView.busy`);
    assert.equal(await evaluate(`settingsView.enhanced`),false);
    await click('.settings-choice-fallback summary');
    assert.match(await evaluate(`document.querySelector('.settings-choice-fallback').innerText`),/Default[\s\S]*Follow the shipped default[\s\S]*Classic[\s\S]*Web/);
    await key('Tab'); await evaluate(`document.getElementById('web-theme').focus()`); await key('ArrowDown');
    await until(`!settingsView.busy && settingsView.feedback.className==='success'`);
    checks.push('Feature-disabled native fallback: accessible Choice help disclosure before commitment and working native keyboard save');
    assert.deepEqual(errors,[]);
    evidence = {outcome:'PASS',browser:version.product,checks,layouts,limits:['Headless Chromium, not physical OS input or a screen-reader session.','Fallback is feature-disabled Chromium, not proof from Firefox or Safari.']};
  } catch(error) {evidence = {...evidence,checks,layouts,error:error.message}; throw error;}
  finally {
    await fs.writeFile(output,JSON.stringify(evidence,null,2)+'\n');
    clearTimeout(deadline); await command('Browser.close').catch(()=>{}); server.stdin.end('{"command":"stop"}\n');
  }
  console.log(JSON.stringify({outcome:evidence.outcome,browser:evidence.browser,checks:evidence.checks}));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
