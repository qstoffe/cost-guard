// Headless Chromium only; isolated profile, synthetic SQLite, shipped host/assets.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output, mode = 'auto'] = process.argv.slice(2);
async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output)); await fs.stat(browser);
  const profile = await fs.mkdtemp(path.join(path.dirname(output), 'v1-browser-'));
  const config = await fs.mkdtemp(path.join(path.dirname(output), 'v1-host-'));
  const server = spawn('py', ['-3', 'development/tests/integration/serve_v1_watch.py', config, mode],
    {windowsHide:true, stdio:['pipe', 'pipe', 'pipe']});
  let errors = ''; server.stderr.on('data', value => { errors += value; });
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const launch = JSON.parse((await lines.next()).value);
  const fixture = async command => { server.stdin.write(JSON.stringify({command}) + '\n');
    assert.equal(JSON.parse((await lines.next()).value).ok, true, errors); };
  const child = spawn(browser, ['--headless=new', '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--disable-background-networking', '--remote-debugging-pipe',
    '--user-data-dir=' + profile, 'about:blank'], {windowsHide:true, stdio:['ignore', 'ignore', 'ignore', 'pipe', 'pipe']});
  let sequence = 0, buffer = ''; const pending = new Map();
  child.stdio[4].on('data', chunk => { buffer += chunk; let index;
    while ((index = buffer.indexOf('\0')) >= 0) {
      const value = JSON.parse(buffer.slice(0, index)); buffer = buffer.slice(index + 1);
      const item = pending.get(value.id); if (!item) continue;
      clearTimeout(item.timer); pending.delete(value.id);
      value.error ? item.reject(new Error(JSON.stringify(value.error))) : item.resolve(value.result);
    }
  });
  const command = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const id = ++sequence, timer = setTimeout(() => reject(new Error('CDP timeout ' + method)), 15000);
    pending.set(id, {resolve, reject, timer});
    child.stdio[3].write(JSON.stringify({id, method, params, ...(sessionId ? {sessionId} : {})}) + '\0');
  });
  const deadline = setTimeout(() => { child.kill(); server.kill(); }, 240000);
  const evidence = {outcome:'FAIL', mode, checks:[], layouts:[], limitations:['Synthetic history, not the reported private installation or physical desktop proof.']};
  try {
    evidence.browser = await command('Browser.getVersion');
    const {targetId} = await command('Target.createTarget', {url:'about:blank'});
    const {sessionId} = await command('Target.attachToTarget', {targetId, flatten:true});
    const evaluate = async (expression, userGesture = false) => {
      const result = await command('Runtime.evaluate', {expression, returnByValue:true, awaitPromise:true, userGesture}, sessionId)
        .catch(error => { throw new Error(error.message + ': ' + expression.slice(0, 160)); });
      if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
      return result.result.value;
    };
    const until = async expression => { const end = Date.now() + 20000;
      while (Date.now() < end) { if (await evaluate(expression)) return; await new Promise(resolve => setTimeout(resolve, 40)); }
      throw new Error('Condition not reached: ' + expression + '\n' + errors);
    };
    await command('Page.enable', {}, sessionId);
    await command('Page.addScriptToEvaluateOnNewDocument', {source:`window.probeStreams=[];const Native=EventSource;
      window.EventSource=class extends Native{constructor(...args){super(...args);probeStreams.push(this);}};`}, sessionId);
    await command('Page.navigate', {url:launch.url}, sessionId);
    await until(`typeof liveValue !== 'undefined' && liveValue?.state==='starting'`);
    assert.equal(await evaluate(`document.getElementById('source-compatibility').hidden`), true);
    await fixture('run');
    await until(`hostState.kind==='connected' && !sourceNotice.hidden && liveValue.view.active_cards.some(c=>c.session_id==='ses_root' && c.rows.length)`);
    assert.equal(await evaluate(`liveValue.source_generation`), 'v1');
    assert.equal(await evaluate(`probeStreams.length`), 1);
    const notice = await evaluate(`sourceNotice.textContent`);
    assert.match(notice, /supports V1 with polling; native session export requires V2/);
    for (const route of ['models', 'watch', 'sessions', 'accounts', 'token-mix', 'ai-stats', 'comparisons', 'settings']) {
      await evaluate(`location.hash='#/${route}'`); await until(`document.body.dataset.section==='${route}'`);
      assert.equal(await evaluate(`document.querySelectorAll('#source-compatibility').length===1 && !sourceNotice.hidden && sourceNotice.nextElementSibling.id==='host-state'`), true);
    }
    await evaluate(`history.back()`); await until(`document.body.dataset.section==='comparisons'`);
    await evaluate(`history.forward()`); await until(`document.body.dataset.section==='settings'`);
    evidence.checks.push('authoritative V1; all eight routes; Back/Forward; one top-level notice and SSE');
    await evaluate(`location.hash='#/watch'`); await until(`current?.watch && miniWatch.measure?.ready`);
    await evaluate(`document.getElementById('search').value='Root';document.getElementById('search').dispatchEvent(new Event('input'))`);
    await evaluate(`miniWatch.toggle()`, true); await until(`!!miniWatch.view`);
    assert.equal(await evaluate(`miniWatch.window.document.querySelector('#source-compatibility')===null && !sourceNotice.hidden`), true);
    await fixture('complete');
    await until(`liveValue.view.active_cards.some(c=>c.rows.some(r=>r.prompt.event_id==='live-user' && !r.prompt.in_progress))`);
    assert.equal(await evaluate(`sourceNotice.hidden`), false);
    assert.equal(await evaluate(`miniWatch.view.promptRows.size>0`), true);
    await evaluate(`miniWatch.close()`);
    evidence.checks.push('real SQLite update → polling → Live/HTTP/SSE → Full/Mini; filtering and terminal transition retain notice');
    for (const gate of ['pending', 'failed', 'wire-v2', 'wire-private-invalid']) {
      await fixture(gate); await until(`liveValue?.${gate==='pending' || gate==='failed' ? `state==='${gate==='pending'?'starting':'failed'}'` : `source_generation==='${gate.slice(5)}'`}`);
      assert.equal(await evaluate(`sourceNotice.hidden`), true);
    }
    await fixture('run'); await until(`!sourceNotice.hidden`);
    await command('Network.enable', {}, sessionId);
    await command('Network.emulateNetworkConditions', {offline:true, latency:0, downloadThroughput:-1, uploadThroughput:-1}, sessionId);
    await evaluate(`window.dispatchEvent(new Event('offline'))`);
    assert.equal(await evaluate(`sourceNotice.hidden`), true);
    await command('Network.emulateNetworkConditions', {offline:false, latency:0, downloadThroughput:-1, uploadThroughput:-1}, sessionId);
    await evaluate(`liveConnection.resync()`); await until(`!sourceNotice.hidden && hostState.kind==='connected'`);
    evidence.checks.push('pending/failed/V2/invalid enum hide; offline hides; authenticated reconnect restores verified V1');
    // Actual page zoom through Chromium's own settings; no shipped CSS mutations.
    const {targetId:settingsId} = await command('Target.createTarget', {url:'chrome://settings/appearance'});
    const {sessionId:settingsSession} = await command('Target.attachToTarget', {targetId:settingsId, flatten:true});
    for (const zoom of [1, 1.5]) {
      const result = await command('Runtime.evaluate', {expression:`new Promise(resolve=>chrome.settingsPrivate.setDefaultZoom(${zoom},resolve))`, awaitPromise:true}, settingsSession);
      assert.ok(!result.exceptionDetails);
      await command('Page.bringToFront', {}, sessionId);
      for (const width of [1440, 360]) for (const theme of ['classic', 'web']) for (const scheme of ['light', 'dark']) {
        await command('Emulation.setDeviceMetricsOverride', {width, height:900, deviceScaleFactor:1, mobile:false}, sessionId);
        await command('Emulation.setEmulatedMedia', {features:[{name:'prefers-color-scheme', value:scheme}, {name:'prefers-reduced-motion', value:'reduce'}]}, sessionId);
        await evaluate(`document.documentElement.dataset.theme='${theme}';window.scrollTo(0,0)`);
        await evaluate(`new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`);
        const layout = await evaluate(`(()=>{const r=sourceNotice.getBoundingClientRect(),n=document.querySelector('nav').getBoundingClientRect();return {
          width:innerWidth,height:r.height,top:r.top,navBottom:n.bottom,overflow:document.documentElement.scrollWidth>innerWidth+1,
          background:getComputedStyle(sourceNotice).backgroundColor,color:getComputedStyle(sourceNotice).color,
          padding:parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop)};})()`);
        assert.equal(layout.overflow, false); assert.ok(layout.top >= layout.navBottom - 1);
        assert.ok(layout.height < 900 / zoom / 3); assert.ok(layout.padding >= layout.height);
        const luminance = rgb => rgb.match(/\d+/g).slice(0,3).map(Number).map(v=>v/255)
          .map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
        const light = [luminance(layout.color), luminance(layout.background)].sort((a,b)=>b-a);
        layout.contrast = (light[0]+.05)/(light[1]+.05); assert.ok(layout.contrast>=4.5);
        if (zoom===1.5 && theme==='web' && scheme==='light') {
          const image = await command('Page.captureScreenshot', {format:'png'}, sessionId);
          await fs.writeFile(output.replace(/\.json$/, `-${width}.png`), Buffer.from(image.data,'base64'));
        }
        await evaluate(`window.scrollTo(0,document.documentElement.scrollHeight)`);
        assert.ok(await evaluate(`sourceNotice.getBoundingClientRect().top>=-1`));
        evidence.layouts.push({zoom, width, theme, scheme, ...layout});
      }
    }
    await evaluate(`document.getElementById('skip').click()`);
    assert.equal(await evaluate(`document.activeElement.id`), 'content');
    await command('Input.dispatchKeyEvent', {type:'keyDown', key:'Tab', code:'Tab', windowsVirtualKeyCode:9}, sessionId);
    await command('Input.dispatchKeyEvent', {type:'keyUp', key:'Tab', code:'Tab', windowsVirtualKeyCode:9}, sessionId);
    assert.equal(await evaluate(`(()=>{const r=document.activeElement.getBoundingClientRect(),b=sourceNotice.getBoundingClientRect();return r.bottom<=b.top || r.top>=b.bottom;})()`), true);
    evidence.checks.push('Classic/Web light/dark, reduced motion, 360/1440 widths, 100/150% browser zoom, sticky geometry and keyboard focus clearance');
    await evaluate(`probeStreams[0].dispatchEvent(new MessageEvent('live',{lastEventId:'old-instance:999999',data:JSON.stringify({state:'running',source_generation:'v1',view:liveValue.view})}))`);
    assert.equal(await evaluate(`hostState.kind==='identity_changed' && sourceNotice.hidden`), true);
    evidence.checks.push('stale other-instance SSE fails closed without retaining V1');
    evidence.outcome = 'PASS';
  } finally {
    clearTimeout(deadline); child.kill();
    server.stdin.end(JSON.stringify({command:'stop'}) + '\n');
    await fs.writeFile(output, JSON.stringify(evidence, null, 2));
  }
  console.log(JSON.stringify({outcome:evidence.outcome, mode, checks:evidence.checks.length, layouts:evidence.layouts.length}));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
