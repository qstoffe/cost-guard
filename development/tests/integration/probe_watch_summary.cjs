// Bounded synthetic Watch layout/pixel probe; owns one headless browser/profile.
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const [browser, output] = process.argv.slice(2);
if (!browser || !fs.statSync(browser).isFile() || !output || !fs.statSync(path.dirname(output)).isDirectory())
  throw new Error('Explicit browser and existing owned output parent required');
const profile = fs.mkdtempSync(path.join(path.resolve(path.dirname(output)), 'watch-browser-'));
const child = spawn(browser, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--disable-extensions', '--disable-background-networking', '--remote-debugging-port=0', '--user-data-dir=' + profile,
  'http://127.0.0.1:18753/case.html'], {stdio:'ignore', windowsHide:true});
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const pending = new Map();
let socket, id = 0;
function command(method, params = {}) {
  const key = ++id;
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {pending.delete(key); reject(new Error('CDP timeout: ' + method));}, 10000);
    pending.set(key, value => {clearTimeout(timeout); value.error ? reject(new Error(JSON.stringify(value.error))) : resolve(value.result);});
    socket.send(JSON.stringify({id:key, method, params}));
  });
}
async function evaluate(expression) {
  const result = await command('Runtime.evaluate', {expression, returnByValue:true});
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
(async () => {
  const cases = [];
  let evidence;
  try {
    const portFile = path.join(profile, 'DevToolsActivePort'), deadline = Date.now() + 15000;
    while (!fs.existsSync(portFile) && Date.now() < deadline) await delay(100);
    const port = Number(fs.readFileSync(portFile, 'utf8').split('\n')[0]);
    const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    const page = targets.find(t => t.type === 'page' && t.url === 'http://127.0.0.1:18753/case.html');
    assert.ok(page, 'exact synthetic page');
    socket = new WebSocket(page.webSocketDebuggerUrl);
    socket.addEventListener('message', event => {const value = JSON.parse(event.data); if (value.id) {pending.get(value.id)?.(value); pending.delete(value.id);}});
    await new Promise((resolve, reject) => {socket.addEventListener('open', resolve, {once:true}); socket.addEventListener('error', reject, {once:true});});
    for (const width of [1920, 1366, 360]) for (const [theme, scheme, background] of [
      ['classic','light','#101112'], ['web','light','#eef2f8'], ['web','dark','#0c1422']]) {
      await command('Emulation.setDeviceMetricsOverride', {width, height:1200, deviceScaleFactor:1, mobile:false});
      await command('Page.navigate', {url:`http://127.0.0.1:18753/case.html?theme=${theme}&scheme=${scheme}`});
      const ready = Date.now() + 10000;
      while (!await evaluate(`document.readyState === 'complete' && location.search === '?theme=${theme}&scheme=${scheme}' && document.documentElement.dataset.theme === '${theme}' && document.querySelectorAll('.watch-subscription').length === 6 && getComputedStyle(document.documentElement).getPropertyValue('--bg').trim() === '${background}'`) && Date.now() < ready) await delay(50);
      // Put the required monthly/five-hour/weekly-only combination side by side.
      // This rearranges synthetic fixture nodes only, not production account ordering.
      await evaluate(`(() => {const grid=document.querySelector('.watch-account-grid'); grid.insertBefore(grid.lastElementChild,grid.children[2]);})()`);
      const layout = await evaluate(`(() => {
        const cards=[...document.querySelectorAll('.watch-subscription')];
        return {width:innerWidth, background:getComputedStyle(document.documentElement).getPropertyValue('--bg').trim(),
          noOverflow:document.documentElement.scrollWidth<=innerWidth,
          cards:cards.map(c=>({title:c.querySelector('h4').textContent,
            centered:getComputedStyle(c.querySelector('h4')).textAlign==='center',
            band:getComputedStyle(c.querySelector('h4')).backgroundColor,
            left:getComputedStyle(c).textAlign==='left', noOverflow:c.scrollWidth<=c.clientWidth,
            secondary:c.querySelectorAll('.watch-account-details').length,
            top:c.getBoundingClientRect().top, tracks:[...c.children].slice(1,4).map(n=>n.getBoundingClientRect().top),
            clippedTitle:c.querySelector('h4').scrollHeight>c.querySelector('h4').clientHeight,
            reset:c.children[4].textContent}))}; })()`);
      assert.equal(layout.width, width); assert.equal(layout.background, background); assert.ok(layout.noOverflow);
      assert.equal(layout.cards.length, 6);
      for (const card of layout.cards) assert.ok(card.centered && card.left && card.noOverflow && !card.clippedTitle);
      assert.deepEqual(layout.cards.map(c=>c.secondary), [0,1,0,1,0,1]);
      assert.equal(layout.cards[2].title, 'OpenAI Pro Lite');
      if (width >= 1366) assert.ok(Math.abs(layout.cards[0].top-layout.cards[2].top)<1, 'monthly/five-hour/weekly-only side by side');
       assert.match(layout.cards[0].reset, /Reset.*Remaining: .*\/day.*Remaining: .*\/workday/);
       const warningTransitions = await evaluate(`(() => {
          const card=state.watch.cards.values().next().value, warning=INPUT.view.active_cards[0].session_summary.context.warning;
         const original=warning.severity, root=document.documentElement, theme=root.dataset.theme;
         const outcomes=[];
         for (const currentTheme of [theme,theme==='classic'?'web':'classic',theme]) {
           root.dataset.theme=currentTheme;
           for (const severity of ['approaching','exceeded','none','approaching']) {
             warning.severity=severity; ReportView.renderLive(document.getElementById('result'),INPUT,state);
             const color=node=>getComputedStyle(node).color;
              outcomes.push({theme:currentTheme,severity,hidden:card.warningIcon.hidden,
               foreground:color(document.body),icon:color(card.warningIcon),text:color(card.warningText),
                cleared:severity!=='none'||card.warningText.textContent===''});
           }
         }
         warning.severity=original;root.dataset.theme=theme;
         ReportView.renderLive(document.getElementById('result'),INPUT,state);return outcomes;
       })()`);
       for (const result of warningTransitions) {
         assert.equal(result.hidden, result.severity === 'none'); assert.ok(result.cleared);
         if (result.severity === 'none') continue;
         assert.notEqual(result.icon, result.foreground);
         assert.equal(result.text, result.severity === 'approaching' ? result.foreground : result.icon);
       }
      for (const card of layout.cards) for (const peer of layout.cards.filter(c=>Math.abs(c.top-card.top)<1))
        card.tracks.forEach((y,i)=>assert.ok(Math.abs(y-peer.tracks[i])<1, 'common tracks align'));
      const image = await command('Page.captureScreenshot', {format:'png', captureBeyondViewport:true});
      const name = output.replace(/\.json$/, '') + `-${theme}-${scheme}-${width}.png`;
      fs.writeFileSync(name, Buffer.from(image.data, 'base64'));
       cases.push({theme, scheme, ...layout, warningTransitions, screenshot:path.basename(name)});
    }
    evidence = {outcome:'PASS', cases, limitations:['Synthetic headless Chromium, not live-provider pixels or physical desktop acceptance.']};
  } catch (error) {
    evidence = {outcome:'FAIL', cases, reason:error.message}; process.exitCode=1;
  } finally {
    if (socket?.readyState === WebSocket.OPEN) {try {await command('Browser.close');} catch {} socket.close();}
    if (child.exitCode === null) await Promise.race([new Promise(resolve=>child.once('exit',resolve)), delay(5000)]);
    if (child.exitCode === null) child.kill();
    try {fs.rmSync(profile,{recursive:true});} catch {}
    fs.writeFileSync(output, JSON.stringify(evidence,null,2)+'\n');
    console.log(JSON.stringify(evidence));
  }
})();
