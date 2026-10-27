// Explicit Edge/Chromium acceptance probe. Requires serve_web_accounts.py and Node 22+.
// Only synthetic loopback fixtures; owns one temporary browser, never a user's profile.
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const assert = require('node:assert/strict');
const browser = process.argv[2], output = process.argv[3];
if (!browser || !fs.statSync(browser).isFile() || !output || !fs.statSync(path.dirname(output)).isDirectory()) {
  throw new Error('Explicit browser and existing owned output parent required');
}
const profile = fs.mkdtempSync(path.join(path.resolve(path.dirname(output)), 'accounts-browser-'));
const child = spawn(browser, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--disable-extensions', '--disable-background-networking', '--remote-debugging-port=0', '--user-data-dir=' + profile,
  'http://127.0.0.1:18749/case.html'], {stdio: 'ignore'});
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const pending = new Map();
let socket, id = 0;
async function command(method, params = {}) {
  const key = ++id;
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => { pending.delete(key); reject(new Error('CDP timeout: ' + method)); }, 10000);
    pending.set(key, value => {clearTimeout(timeout); value.error ? reject(new Error(JSON.stringify(value.error))) : resolve(value.result);});
    socket.send(JSON.stringify({id: key, method, params}));
  });
}
async function evaluate(expression) {
  const result = await command('Runtime.evaluate', {expression, returnByValue: true});
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function key(name, code) {
  const physical = name === ' ' ? 'Space' : name;
  await command('Input.dispatchKeyEvent', {type:'rawKeyDown', key:name, code:physical, windowsVirtualKeyCode:code});
  if (name === 'Enter' || name === ' ') await command('Input.dispatchKeyEvent', {type:'char', key:name,
    code:physical, text:name === 'Enter' ? '\r' : ' ', windowsVirtualKeyCode:code});
  await command('Input.dispatchKeyEvent', {type:'keyUp', key:name, code:physical, windowsVirtualKeyCode:code});
}
(async () => {
  const cases = [];
  let receipt;
  try {
    const portFile = path.join(profile, 'DevToolsActivePort');
    const deadline = Date.now() + 15000;
    while (!fs.existsSync(portFile) && Date.now() < deadline) await delay(100);
    const port = Number(fs.readFileSync(portFile, 'utf8').split('\n')[0]);
    const targets = await (await fetch('http://127.0.0.1:' + port + '/json/list')).json();
    const page = targets.find(t => t.type === 'page' && t.url === 'http://127.0.0.1:18749/case.html');
    assert.ok(page, 'exact synthetic page');
    socket = new WebSocket(page.webSocketDebuggerUrl);
    socket.addEventListener('message', event => {const value = JSON.parse(event.data); if (value.id) {pending.get(value.id)?.(value); pending.delete(value.id);}});
    await new Promise((resolve, reject) => {socket.addEventListener('open', resolve, {once:true}); socket.addEventListener('error', reject, {once:true});});
    while (!await evaluate('document.querySelectorAll(".account-card").length === 7') && Date.now() < deadline) await delay(100);
    for (const width of [1200, 360]) for (const theme of ['light', 'dark']) {
      await command('Emulation.setDeviceMetricsOverride', {width, height:1000, deviceScaleFactor:1, mobile:false});
      await command('Emulation.setEmulatedMedia', {features:[{name:'prefers-color-scheme', value:theme}]});
      const layout = await evaluate(`({width:innerWidth, noOverflow:document.documentElement.scrollWidth<=innerWidth,
        background:getComputedStyle(document.documentElement).getPropertyValue('--bg').trim(),
        cards:document.querySelectorAll('.account-card').length,
        progress:[...document.querySelectorAll('.account-card')].map(n=>n.querySelectorAll('progress').length)})`);
      assert.equal(layout.noOverflow, true);
      assert.equal(layout.width, width);
      assert.equal(layout.background, theme === 'dark' ? '#0c1422' : '#eef2f8');
      assert.deepEqual(layout.progress, [2,1,0,0,0,0,1]);
      await evaluate(`document.activeElement.blur(); document.querySelectorAll('details').forEach(n=>n.open=false); document.querySelector('.account-card summary').focus()`);
      await key('Enter', 13);
      assert.equal(await evaluate(`document.querySelector('.account-card details').open`), true, 'Enter opens native disclosure');
      await key(' ', 32);
      assert.equal(await evaluate(`document.querySelector('.account-card details').open`), false, 'Space closes native disclosure');
      await key('Tab', 9);
      const focus = await evaluate(`({tag:document.activeElement.tagName,card:document.activeElement.closest('.account-card')?.querySelector('h4').textContent,outline:getComputedStyle(document.activeElement).outlineStyle})`);
      assert.equal(focus.tag, 'SUMMARY');
      assert.equal(focus.card, 'Blocked');
      assert.equal(focus.outline, 'solid');
      cases.push({theme, ...layout, keyboard:'PASS: Enter opens, Space closes, Tab advances with visible focus'});
      const image = await command('Page.captureScreenshot', {format:'png'});
      fs.writeFileSync(output.replace(/\.json$/, '') + '-' + theme + '-' + width + '.png', Buffer.from(image.data, 'base64'));
    }
    receipt = {outcome:'PASS', cases, limitations:['Synthetic canonical report, not installed-history browser integration.',
      'Headless browser key dispatch/layout; no physical keyboard, screen-reader or macOS acceptance.']};
  } catch (error) {
    receipt = {outcome:'FAIL', cases, reason:error.message};
    process.exitCode = 1;
  } finally {
    if (socket?.readyState === WebSocket.OPEN) {try {await command('Browser.close');} catch {} socket.close();}
    if (child.exitCode === null) await Promise.race([new Promise(resolve=>child.once('exit', resolve)), delay(5000)]);
    if (child.exitCode === null) child.kill();
    // Exact mkdtemp-owned profile only. Failure preserves evidence rather than broad cleanup.
    try {fs.rmSync(profile, {recursive:true});} catch {}
    fs.writeFileSync(output, JSON.stringify(receipt, null, 2) + '\n');
    console.log(JSON.stringify(receipt));
  }
})();
