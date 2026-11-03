// Real Document PiP in an owned hidden Chromium profile, shipped HTTP/CSP/SSE.
// Explicit browser/output, no package installs, personal profiles or desktop input.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output] = process.argv.slice(2);
async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output));
  await fs.stat(browser); await fs.stat(path.dirname(output));
  const profile = await fs.mkdtemp(path.join(path.dirname(output), 'mini-browser-'));
  const server = spawn('py', ['-3', 'development/tests/integration/serve_mini_watch.py'], {windowsHide:true, stdio:['pipe','pipe','pipe']});
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const next = async () => JSON.parse((await lines.next()).value);
  const fixture = async command => {server.stdin.write(JSON.stringify({command})+'\n'); return next();};
  const child = spawn(browser, ['--headless=new', '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--disable-background-networking', '--remote-debugging-pipe',
    '--user-data-dir=' + profile, 'about:blank'], {windowsHide:true, stdio:['ignore','ignore','ignore','pipe','pipe']});
  const pending = new Map(); let sequence = 0, buffer = '', errors = [];
  child.stdio[4].on('data', chunk => {
    buffer += chunk.toString(); let index;
    while ((index = buffer.indexOf('\0')) >= 0) {
      const value = JSON.parse(buffer.slice(0,index)); buffer = buffer.slice(index+1);
      if (value.id) {
        const entry = pending.get(value.id); pending.delete(value.id);
        if (entry) { clearTimeout(entry.timer); value.error ? entry.reject(new Error(JSON.stringify(value.error))) : entry.resolve(value.result); }
      } else if (value.method === 'Runtime.exceptionThrown') errors.push(value.params.exceptionDetails.text);
    }
  });
  const command = (method, params = {}, sessionId) => new Promise((resolve,reject) => {
    const id = ++sequence, timer = setTimeout(() => {pending.delete(id); reject(new Error('CDP timeout: '+method));}, 15000);
    pending.set(id, {resolve,reject,timer});
    child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId ? {sessionId} : {})})+'\0');
  });
  const deadline = setTimeout(() => {child.kill(); server.kill();}, 150000);
  const checks = [], screenshots = []; let evidence = {outcome:'FAIL'};
  try {
    const launch = await next(); // Secret bootstrap URL is never logged or retained.
    const version = await command('Browser.getVersion');
    const {targetId} = await command('Target.createTarget', {url:'about:blank'});
    const {sessionId} = await command('Target.attachToTarget', {targetId,flatten:true});
    await command('Page.enable', {}, sessionId); await command('Runtime.enable', {}, sessionId);
    const evaluate = async (expression, userGesture=false) => {
      const value = await command('Runtime.evaluate', {expression,returnByValue:true,awaitPromise:true,userGesture}, sessionId);
      if (value.exceptionDetails) throw new Error(value.exceptionDetails.text);
      return value.result.value;
    };
    const until = async expression => {
      const end = Date.now()+15000;
      while (Date.now()<end) {if (await evaluate(expression)) return; await new Promise(resolve=>setTimeout(resolve,50));}
      throw new Error('Condition not reached: '+expression);
    };
    await command('Page.addScriptToEvaluateOnNewDocument', {source:`window.probeStreams=0; const Native=EventSource; window.EventSource=class extends Native {constructor(...args){super(...args);window.probeStreams++;}};`}, sessionId);
    await command('Page.navigate', {url:launch.url}, sessionId);
    await until(`typeof miniWatch !== 'undefined' && hostState.kind === 'connected' && liveValue?.view?.running?.count === 2`);
    await evaluate(`location.hash='#/watch'`);
    await until(`document.body.dataset.section === 'watch'`);
    assert.equal(await evaluate(`document.getElementById('mini-watch-toggle').disabled`),false);
    const support = await evaluate(`({secure:isSecureContext,api:typeof documentPictureInPicture?.requestWindow})`);
    assert.deepEqual(support,{secure:true,api:'function'});
    // Browser user-activation flag is scoped to this explicit test interaction.
    await evaluate(`miniWatch.toggle()`,true);
    const open = await evaluate(`({on:!!miniWatch.window,reason:miniWatch.feedback.textContent})`);
    assert.equal(open.on,true,open.reason);
    const metrics = () => evaluate(`miniWatch.view.values.map(node=>node.textContent)`);
    assert.deepEqual(await metrics(),['2','4','20m']);
    assert.equal(await evaluate(`documentPictureInPicture.window === miniWatch.window`),true);
    await until(`miniWatch.window.getComputedStyle(miniWatch.view.root).borderTopWidth === '1px'`);
    checks.push('Real user-activated Document PiP opens with coherent two-prompt aggregate and external CSP styles');
    const pip = () => evaluate(`!!miniWatch.window && !miniWatch.window.closed`);
    const targets = await command('Target.getTargets');
    let pipSession = null;
    for (const target of targets.targetInfos.filter(item=>item.targetId!==targetId && item.type==='page')) {
      const attached = await command('Target.attachToTarget',{targetId:target.targetId,flatten:true});
      const found = await command('Runtime.evaluate',{expression:'!!document.querySelector(".mini-card")',returnByValue:true},attached.sessionId);
      if (found.result.value) {pipSession=attached.sessionId; break;}
    }
    assert.ok(pipSession,'owned Document PiP target available for rendered geometry and theme checks');
    // PiP is not consistently exposed as a CDP target; DOM is accessible through its owning document.
    await evaluate(`location.hash='#/settings'`);
    await until(`document.getElementById('web-theme')?.disabled === false`);
    assert.equal(await pip(),true);
    await evaluate(`document.getElementById('web-theme').value='web'; document.getElementById('web-theme').dispatchEvent(new Event('change'))`);
    await until(`miniWatch.window.document.documentElement.dataset.theme === 'web'`);
    await evaluate(`document.getElementById('ccost-unit').value='usd'; document.getElementById('ccost-unit').dispatchEvent(new Event('change'))`);
    await until(`miniWatch.view.values[1].textContent === '$0.04'`);
    await evaluate(`miniWatch.view.summary.click()`,true);
    await until(`location.hash === '#/watch'`);
    assert.equal(await pip(),true);
    assert.equal(await evaluate('probeStreams'),1);
    checks.push('Navigation, existing-opener return, live theme/USD propagation keep Mini and exactly one EventSource');
    for (const [theme,scheme,background] of [['classic','light','#101112'],['web','light','#eef2f8'],['web','dark','#0c1422']]) {
      await evaluate(`document.documentElement.dataset.theme='${theme}'; miniWatch.settings()`);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]},pipSession);
      await until(`miniWatch.window.getComputedStyle(miniWatch.window.document.documentElement).getPropertyValue('--bg').trim() === '${background}'`);
      const layout = await evaluate(`(() => {const w=miniWatch.window,d=w.document,r=miniWatch.view.root;return {background:w.getComputedStyle(d.documentElement).getPropertyValue('--bg').trim(),overflow:d.documentElement.scrollWidth>w.innerWidth,lines:miniWatch.view.accounts.children.length,clutter:/Reset|CCost Today|Provisional/.test(r.textContent),title:r.querySelector('li').textContent};})()`);
      assert.equal(layout.background,background); assert.equal(layout.overflow,false); assert.equal(layout.lines,6); assert.equal(layout.clutter,false);
      if (pipSession) {
        const image = await command('Page.captureScreenshot',{format:'png'},pipSession);
        const name = output.replace(/\.json$/,'')+`-${theme}-${scheme}.png`;
        await fs.writeFile(name,Buffer.from(image.data,'base64')); screenshots.push(path.basename(name));
      }
    }
    checks.push('Classic/Web light/dark styles, long account labels, primary-only six-account content without page overflow');
    // Keyboard interaction stays inside the hidden owned browser, not shared OS input.
    await command('Runtime.evaluate',{expression:`document.querySelector('.mini-summary').focus()`},pipSession);
    assert.equal(await evaluate(`miniWatch.window.getComputedStyle(miniWatch.view.summary).outlineStyle !== 'none'`),true);
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r'},pipSession);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13},pipSession);
    assert.equal(await pip(),true);
    // Resize via the browser-owned PiP API with user activation; no CSS emulated popup.
    await evaluate(`miniWatch.window.resizeTo(280,320)`,true);
    await until(`miniWatch.window.innerWidth <= 300`);
    assert.equal(await evaluate(`miniWatch.window.document.documentElement.scrollWidth <= miniWatch.window.innerWidth`),true);
    checks.push('Keyboard summary focus/activation and user-activated native PiP resize remain usable');
    const backgroundTarget = await command('Target.createTarget',{url:'about:blank'});
    const backgroundSession = await command('Target.attachToTarget',{targetId:backgroundTarget.targetId,flatten:true});
    await command('Page.bringToFront',{},backgroundSession.sessionId);
    await until(`document.hidden`);
    assert.equal(await evaluate(`miniWatch.window.document.hidden`),false);
    await fixture('terminal'); await until(`miniWatch.view.values[0].textContent === '1'`);
    assert.deepEqual(await metrics(),['1','$0.01','10m']);
    await fixture('empty'); await until(`miniWatch.view.values[0].textContent === '0'`);
    assert.deepEqual(await metrics(),['0','$0.00','—']);
    await fixture('recovering'); await until(`miniWatch.view.health.textContent.includes('not live')`);
    await fixture('running'); await until(`miniWatch.view.health.textContent === 'Live'`);
    checks.push('With main document actually hidden and PiP visible, real SSE completion/empty/recovery updates drop count/cost/max without rAF');
    await command('Page.bringToFront',{},sessionId);
    await command('Target.closeTarget',{targetId:backgroundTarget.targetId});
    await evaluate(`documentPictureInPicture.requestWindow({width:300,height:200}).then(()=>true)`,true);
    await until(`!miniWatch.window && !!documentPictureInPicture.window`);
    assert.equal(await evaluate(`document.getElementById('mini-watch-toggle').textContent`),'Mini Watch: Off');
    await evaluate(`documentPictureInPicture.window.close()`);
    await evaluate(`miniWatch.toggle()`,true);
    await evaluate(`miniWatch.window.close()`);
    await until(`document.getElementById('mini-watch-toggle').textContent === 'Mini Watch: Off'`);
    await evaluate(`miniWatch.toggle()`,true); assert.equal(await pip(),true);
    await evaluate(`miniWatch.view.root.querySelector('.mini-close').click()`,true);
    await until(`!miniWatch.window`);
    await evaluate(`miniWatch.toggle()`,true);
    await command('Page.reload',{},sessionId);
    await until(`typeof miniWatch !== 'undefined' && hostState.kind === 'connected' && !miniWatch.window`);
    checks.push('Native API replacement, browser-owned close, custom close, reopen and main reload synchronize Off; no auto-open');
    // Unsupported and rejected requests are deterministic VM cases; actual lack of
    // user activation can also be tested against the native browser API.
    await evaluate(`location.hash='#/watch'`);
    await until(`document.body.dataset.section === 'watch'`);
    await evaluate(`miniWatch.toggle()`,true);
    await fixture('stop');
    await until(`hostState.kind === 'stopped'`);
    assert.match(await evaluate(`miniWatch.view.health.textContent`),/Host stopped · not live/);
    assert.equal(await pip(),true,'host shutdown marks retained figures not live without pretending window close');
    checks.push('Real terminal shutdown reaches open Mini as not live');
    assert.deepEqual(errors,[]);
    evidence = {outcome:'PASS',browser:version.product,checks,screenshots,
      limitations:['Headless Chromium only; no physical/native X, native return/replacement chrome, minimized-opener restoration, always-on-top OS geometry or screen-reader proof.']};
  } catch (error) {evidence={outcome:'FAIL',checks,screenshots,reason:error.message};process.exitCode=1;}
  finally {
    clearTimeout(deadline);
    try {await command('Browser.close');} catch {}
    server.stdin.end();
    await new Promise(resolve=>{if(child.exitCode!==null) resolve(); else {child.once('exit',resolve);setTimeout(resolve,3000);}});
    if(child.exitCode===null) child.kill();
    if(server.exitCode===null) server.kill();
    try {await fs.rm(profile,{recursive:true});} catch {}
    await fs.writeFile(output,JSON.stringify(evidence,null,2)+'\n'); console.log(JSON.stringify(evidence));
  }
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
