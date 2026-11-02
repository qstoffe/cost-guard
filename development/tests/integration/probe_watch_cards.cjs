// Approval-only external headless Chromium, fresh owned profile, synthetic origin only.
// Node 22+ built-ins, no package install, personal profile or existing browser attachment.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const args = process.argv.slice(2);
const argument = key => args[args.indexOf(key) + 1];
const browser = argument('--browser'), output = argument('--output');
const origin = 'http://127.0.0.1:18754';
async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output), 'explicit browser and owned output directory required');
  await fs.mkdir(output, {recursive: true});
  const profile = await fs.mkdtemp(path.join(output, 'watch-owned-profile-'));
  const child = spawn(browser, ['--headless=new', '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--disable-background-networking', '--remote-debugging-pipe',
    '--user-data-dir=' + profile, 'about:blank'], {stdio: ['ignore', 'ignore', 'ignore', 'pipe', 'pipe']});
  const pending = new Map(), listeners = new Map(); let sequence = 0, buffer = '';
  child.stdio[4].on('data', chunk => {
    buffer += chunk.toString();
    let index;
    while ((index = buffer.indexOf('\0')) >= 0) {
      const value = JSON.parse(buffer.slice(0, index)); buffer = buffer.slice(index + 1);
      if (value.id) {
        const entry = pending.get(value.id); pending.delete(value.id);
        if (entry) value.error ? entry.reject(new Error(JSON.stringify(value.error))) : entry.resolve(value.result);
      } else {
        const key = value.sessionId + ':' + value.method;
        if (listeners.has(key)) { listeners.get(key)(value.params); listeners.delete(key); }
      }
    }
  });
  const command = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const id = ++sequence; pending.set(id, {resolve, reject});
    child.stdio[3].write(JSON.stringify({id, method, params, ...(sessionId ? {sessionId} : {})}) + '\0');
  });
  const event = (method, sessionId) => new Promise(resolve => listeners.set(sessionId + ':' + method, resolve));
  const deadline = setTimeout(() => { for (const entry of pending.values()) entry.reject(new Error('probe_deadline')); child.kill(); }, 90000);
  const cases = [];
  let version;
  try {
    version = await command('Browser.getVersion');
    for (const theme of ['classic', 'light', 'dark']) for (const [width, height] of [[1920, 1080], [1366, 768], [360, 800]]) {
      const {targetId} = await command('Target.createTarget', {url: 'about:blank'});
      const {sessionId} = await command('Target.attachToTarget', {targetId, flatten: true});
      await command('Page.enable', {}, sessionId);
      await command('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile: false}, sessionId);
      const loaded = event('Page.loadEventFired', sessionId);
      await command('Page.navigate', {url: origin + '/case.html?theme=' + theme}, sessionId);
      await loaded;
      await command('Page.bringToFront', {}, sessionId);
      const evaluate = async expression => {
        const value = await command('Runtime.evaluate', {expression, returnByValue: true}, sessionId);
        assert.equal(value.exceptionDetails, undefined, JSON.stringify(value.exceptionDetails));
        return value.result.value;
      };
      assert.equal(await evaluate('document.querySelector(".watch-earlier").open'), false);
      await evaluate('document.querySelector(".watch-earlier > summary").focus()');
      await command('Input.dispatchKeyEvent', {type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, text: '\r'}, sessionId);
      await command('Input.dispatchKeyEvent', {type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13}, sessionId);
      assert.equal(await evaluate('document.querySelector(".watch-earlier").open'), true, 'keyboard opens native disclosure');
      const layout = await evaluate(`(() => {
        const h=document.querySelector('.watch-history'), a=document.querySelector('.watch-active'), c=a.querySelector('.watch-card');
        const details=c.querySelectorAll('details'); details[0].open=true; details[1].open=true;
        details[0].querySelector('summary').focus({preventScroll:true}); h.scrollTop=70; const scroll=h.scrollTop, focus=document.activeElement;
        redraw(); const stable=document.activeElement===focus && details[0].open && details[1].open && h.scrollTop===scroll;
        const table=c.querySelector('.watch-table-scroll'), row=c.querySelector('tbody tr'), prompt=row.cells[1].firstChild;
        return {width:innerWidth,height:innerHeight,scrollY,activeTop:a.getBoundingClientRect().top, historyHeight:h.clientHeight,
          historyScroll:h.scrollHeight,historyCards:h.querySelectorAll('article').length,
          rows:c.querySelectorAll('tbody tr').length, historyBorder:parseFloat(getComputedStyle(h).borderTopWidth),
          ellipsis:getComputedStyle(prompt).textOverflow==='ellipsis' && prompt.scrollWidth>prompt.clientWidth,
          completeMetrics:[...row.cells].filter((_,i)=>i!==1).every(cell=>cell.scrollWidth<=cell.clientWidth),
          pageOverflow:document.documentElement.scrollWidth>innerWidth,
          activeInnerScroll:a.scrollHeight>a.clientHeight,tableVerticalScroll:table.scrollHeight>table.clientHeight,
          horizontalPan:table.scrollWidth>table.clientWidth,runningColor:getComputedStyle(c.querySelector('.watch-running')).color,
          border:getComputedStyle(c).borderTopWidth,background:getComputedStyle(c).backgroundColor,stable}; })()`);
       assert.equal(layout.historyCards, 5); assert.ok(layout.historyScroll > layout.historyHeight);
       assert.equal(layout.rows, 1); assert.ok(layout.historyBorder > 0);
       assert.equal(layout.ellipsis, true); assert.equal(layout.completeMetrics, true);
      assert.equal(layout.scrollY, 0, 'layout assertions use the unscrolled document');
      assert.equal(layout.pageOverflow, false); assert.equal(layout.activeInnerScroll, false);
      assert.equal(layout.tableVerticalScroll, false); assert.equal(layout.stable, true);
      assert.equal(layout.border, '0px'); assert.equal(layout.background, 'rgba(0, 0, 0, 0)');
      if (width === 1920) assert.ok(layout.activeTop < height - 120, 'expanded history leaves useful active content');
      if (width === 360) assert.equal(layout.horizontalPan, true);
      const screenshot = await command('Page.captureScreenshot', {format: 'png', captureBeyondViewport: false}, sessionId);
      await fs.writeFile(path.join(output, `watch-${theme}-${width}.png`), Buffer.from(screenshot.data, 'base64'));
      const scale = await evaluate(`(() => {
        const base=INPUT.view.active_cards[0];
        INPUT.view.active_cards=Array.from({length:100},(_,i)=>({...base,session_id:'scale-'+i}));redraw();
        const a=document.querySelector('.watch-active'); const count=a.children.length;
        const scroll=a.scrollHeight>a.clientHeight;
        INPUT.view.active_cards[0].rows.at(-1).prompt.in_progress=false;redraw();
        const success=getComputedStyle(a.querySelector('tr.watch-success')).color;
        INPUT.view.active_cards[0].rows.at(-1).prompt.aborted=true;redraw();
        const error=getComputedStyle(a.querySelector('tr.watch-error')).color;
        return {count,scroll,success,error}; })()`);
      assert.equal(scale.count, 100); assert.equal(scale.scroll, false);
      assert.notEqual(scale.success, layout.runningColor); assert.notEqual(scale.error, layout.runningColor);
      cases.push({theme, ...layout, scale, screenshot: `watch-${theme}-${width}.png`, outcome: 'PASS'});
      await command('Target.closeTarget', {targetId});
    }
    await fs.writeFile(path.join(output, 'browser.json'), JSON.stringify({outcome: 'PASS', browser: version.product, userAgent: version.userAgent, cases,
      limitations: ['Synthetic loopback fixture only; no real-installation browser/SSE, physical input, native fullscreen, screen-reader or macOS proof.']}, null, 2));
    console.log(JSON.stringify({outcome:'PASS', browser:version.product, cases:cases.length, evidence:path.join(output,'browser.json')}));
  } finally {
    try { if (child.exitCode === null) { const exited=once(child,'exit'); await command('Browser.close'); await exited; } }
    finally { clearTimeout(deadline); if (child.exitCode !== null) await fs.rm(profile, {recursive:true}); }
  }
}
main().catch(error => { console.error(error); process.exitCode=1; });
