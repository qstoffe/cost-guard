// Hidden fresh-profile Chromium against serve_watch_summary.py --tool-outcomes only.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const args = process.argv.slice(2), argument = name => args[args.indexOf(name) + 1];
const browser = argument('--browser'), output = argument('--output');
async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output));
  await fs.mkdir(output, {recursive: true});
  const profile = await fs.mkdtemp(path.join(output, 'outcomes-profile-'));
  const child = spawn(browser, ['--headless=new', '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--disable-background-networking', '--remote-debugging-pipe',
    '--user-data-dir=' + profile, 'about:blank'], {stdio: ['ignore', 'ignore', 'ignore', 'pipe', 'pipe'], windowsHide: true});
  const pending = new Map(), listeners = new Map(); let id = 0, buffer = '';
  child.stdio[4].on('data', chunk => {
    buffer += chunk.toString(); let end;
    while ((end = buffer.indexOf('\0')) >= 0) {
      const data = JSON.parse(buffer.slice(0, end)); buffer = buffer.slice(end + 1);
      if (data.id) {
        const call = pending.get(data.id); pending.delete(data.id);
        if (call) data.error ? call.reject(new Error(JSON.stringify(data.error))) : call.resolve(data.result);
      } else {
        const key = data.sessionId + ':' + data.method;
        if (listeners.has(key)) { listeners.get(key)(data.params); listeners.delete(key); }
      }
    }
  });
  const command = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    pending.set(++id, {resolve, reject});
    child.stdio[3].write(JSON.stringify({id, method, params, ...(sessionId ? {sessionId} : {})}) + '\0');
  });
  const event = (method, session) => new Promise(resolve => listeners.set(session + ':' + method, resolve));
  const deadline = setTimeout(() => {
    for (const call of pending.values()) call.reject(new Error('probe_deadline'));
    child.kill();
  }, 60000);
  const cases = [];
  try {
    const version = await command('Browser.getVersion');
    for (const theme of ['classic', 'light', 'dark']) for (const width of [1366, 360]) {
      const {targetId} = await command('Target.createTarget', {url: 'about:blank'});
      const {sessionId} = await command('Target.attachToTarget', {targetId, flatten: true});
      await command('Page.enable', {}, sessionId);
      await command('Emulation.setDeviceMetricsOverride', {width, height: 900, deviceScaleFactor: 1, mobile: false}, sessionId);
      const loaded = event('Page.loadEventFired', sessionId);
      await command('Page.navigate', {url: 'http://127.0.0.1:18753/case.html?theme=' +
        (theme === 'classic' ? 'classic' : 'web') + '&scheme=' + (theme === 'dark' ? 'dark' : 'light')}, sessionId);
      await loaded;
       const evaluate = async expression => {
        const value = await command('Runtime.evaluate', {expression, returnByValue: true}, sessionId);
        assert.equal(value.exceptionDetails, undefined, JSON.stringify(value.exceptionDetails));
        return value.result.value;
       };
       const invocation = await require('./probe_watch_invocation.cjs')(evaluate, command, sessionId);
       const failures = await require('./probe_watch_failures.cjs')(evaluate, command, sessionId);
      await evaluate(`document.querySelector('.watch-active details summary').focus({preventScroll:true})`);
      await command('Input.dispatchKeyEvent', {type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, text: '\r'}, sessionId);
      await command('Input.dispatchKeyEvent', {type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13}, sessionId);
      const facts = await evaluate(`(() => {
        const card=[...state.watch.cards.values()].find(c=>c.value.session_id==='root');
        const focus=document.activeElement; card.tools.node.scrollTop=3;
        ReportView.renderLive(document.getElementById('result'), INPUT, state);
        const style=n=>getComputedStyle(n), lines=[...card.tools.list.children];
        return {open:card.tools.node.open, focusStable:document.activeElement===focus,
           summary:card.tools.summary.textContent, lines:lines.map(n=>n.tagName==='DETAILS'?n.firstElementChild.textContent:n.textContent),
           red:lines.slice(-2).map(n=>style(n.tagName==='DETAILS'?n.firstElementChild:n).color),
          ordinary:style(lines[0].firstChild).color, activity:style(card.activity).color,
          running:style(card.running).color, prompt:style(card.body.querySelector('.watch-running')).color,
          title:style(card.title).color, background:style(card.background).color,
          runningBackground:style(card.running).backgroundColor,
          pageOverflow:document.documentElement.scrollWidth>innerWidth,
          detailOverflow:card.tools.list.scrollWidth>card.tools.list.clientWidth,
          injected:card.tools.list.querySelectorAll('custom-tool,img,script').length,
          errorRole:style(document.documentElement).getPropertyValue('--error').trim()}; })()`);
      assert.equal(facts.open, true); assert.equal(facts.focusStable, true);
      assert.match(facts.summary, /^12 tool calls.*3 failed \/ cancelled/);
      assert.equal(facts.lines.length, 9);
      assert.deepEqual(facts.lines.slice(-2), ['2 × grep failed', '1 × execute cancelled']);
      assert.ok(facts.lines.includes('1 × <custom-tool>'));
      assert.equal(facts.injected, 0);
      assert.equal(facts.running, facts.prompt); assert.equal(facts.running, facts.title);
       assert.equal(facts.ordinary, facts.activity); assert.equal(facts.background, facts.running);
      assert.notEqual(facts.running, facts.activity); assert.notEqual(facts.red[0], facts.activity);
      assert.equal(facts.red[0], facts.red[1]);
      assert.equal(facts.runningBackground, 'rgba(0, 0, 0, 0)');
      assert.equal(facts.pageOverflow, false); assert.equal(facts.detailOverflow, false);
      if (theme === 'classic') assert.equal(facts.running, 'rgb(255, 255, 85)');
      const help = await evaluate(`(() => {
         const cue=document.querySelector('.watch-active details summary'); cue.blur(); cue.focus();
        const panel=document.getElementById('context-help');
        return {open:panel.matches(':popover-open'), text:panel.textContent,
          labelled:cue.getAttribute('aria-describedby')===panel.id}; })()`);
      assert.equal(help.open, true); assert.equal(help.labelled, true);
      assert.match(help.text, /subset, not extra calls/); assert.match(help.text, /missing evidence is not success/);
      await command('Input.dispatchKeyEvent', {type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27}, sessionId);
      await command('Input.dispatchKeyEvent', {type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27}, sessionId);
      assert.equal(await evaluate(`document.querySelectorAll(':popover-open').length`), 0);
       await evaluate(`(() => {
         const card=[...state.watch.cards.values()].find(c=>c.value.session_id==='root');
         const group=card.tools.rows.get(JSON.stringify(['grep','failed']));
         group.node.open=true; for(const call of group.jobs.values()) call.node.open=true; })()`);
       const screenshot = await command('Page.captureScreenshot', {format: 'png'}, sessionId);
      await fs.writeFile(path.join(output, theme + '-' + width + '.png'), Buffer.from(screenshot.data, 'base64'));
      const ended = await evaluate(`(() => {
        document.activeElement?.blur(); const row=INPUT.view.active_cards[0].rows[0];
        row.prompt.in_progress=false; row.prompt.completed_successfully=true;
        row.tool.running_tool=''; row.tool.running_ms=0; row.tool.background_kinds=[];
        ReportView.renderLive(document.getElementById('result'), INPUT, state);
        const card=[...state.watch.cards.values()].find(c=>c.value.session_id==='root');
        return {hidden:card.running.hidden, text:card.running.textContent, backgroundHidden:card.background.hidden,
          open:card.tools.node.open, lines:card.tools.list.children.length}; })()`);
      assert.deepEqual(ended, {hidden: true, text: '', backgroundHidden: true, open: true, lines: 9});
        cases.push({theme, width, ...facts, invocation, failures, helpAccessible: true, terminalCleared: true});
      await command('Target.closeTarget', {targetId});
    }
    await fs.writeFile(path.join(output, 'results.json'), JSON.stringify({browser: version.product, cases}, null, 2));
    console.log(JSON.stringify({status: 'ok', browser: version.product, cases: cases.length,
      keyboardDisclosure: true, accessibleHelp: true, themeColors: true, narrowLayout: true, terminalCleared: true}));
  } finally {
    clearTimeout(deadline);
    const exited = once(child, 'exit');
    child.kill(); await exited;
    await fs.rm(profile, {recursive: true, force: true});
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
