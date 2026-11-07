// Shipped app/HTTP/SSE in one hidden Chromium, synthetic accounts and owned config.
// No personal browser, real provider, model call or shared OpenCode mutation.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output] = process.argv.slice(2);
const quotaOnly = process.argv[4] === '--quota-only';
async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output));
  await fs.stat(browser); await fs.stat(path.dirname(output));
  const profile = await fs.mkdtemp(path.join(path.dirname(output), 'accounts-live-browser-'));
  const config = await fs.mkdtemp(path.join(path.dirname(output), 'accounts-live-config-'));
  const server = spawn('py', ['-3', 'development/tests/integration/serve_mini_watch.py', config, '--accounts-live'],
    {windowsHide:true, stdio:['pipe','pipe','pipe']});
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const next = async () => JSON.parse((await lines.next()).value);
  const fixture = async command => { server.stdin.write(JSON.stringify({command})+'\n'); assert.equal((await next()).ok, true); };
  const child = spawn(browser, ['--headless=new', '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--disable-background-networking', '--remote-debugging-pipe',
    '--user-data-dir='+profile, 'about:blank'], {windowsHide:true, stdio:['ignore','ignore','ignore','pipe','pipe']});
  const pending = new Map(), errors = []; let sequence = 0, buffer = '';
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
   const deadline = setTimeout(() => { child.kill(); server.kill(); }, 300000);
  const checks = [], layouts = []; let evidence = {outcome:'FAIL'};
  try {
    const launch = await next(); // One-use URL remains private to the browser pipe.
    const version = await command('Browser.getVersion');
    const {targetId} = await command('Target.createTarget', {url:'about:blank'});
    const {sessionId} = await command('Target.attachToTarget', {targetId,flatten:true});
    await command('Page.enable', {}, sessionId); await command('Runtime.enable', {}, sessionId);
    const evaluate = async (expression,userGesture=false) => {
      const value = await command('Runtime.evaluate', {expression,returnByValue:true,awaitPromise:true,userGesture}, sessionId);
      if (value.exceptionDetails) throw new Error(JSON.stringify(value.exceptionDetails));
      return value.result.value;
    };
    const until = async expression => {
      const end = Date.now()+15000;
      while (Date.now()<end) {if (await evaluate(expression)) return; await new Promise(resolve => setTimeout(resolve,40));}
      throw new Error('Condition not reached: '+expression);
    };
    const navigate = async section => {
      await evaluate(`document.querySelector('nav a[href="#/${section}"]').click()`);
      await until(`document.body.dataset.section === '${section}'`);
    };
    await command('Page.addScriptToEvaluateOnNewDocument', {source:`window.probeStreams=0;window.probeReports=0;
      const Stream=EventSource;window.EventSource=class extends Stream {constructor(...args){super(...args);window.probeStreams++;}};
      const request=fetch;window.fetch=(url,options)=>{if(url==='/api/reports')window.probeReports++;return request(url,options);};`}, sessionId);
    await command('Page.navigate', {url:launch.url}, sessionId);
    await until(`typeof current !== 'undefined' && csrf && liveConnection`);
    const reportCount = await evaluate('probeReports');
    await navigate('accounts');
    assert.equal(await evaluate(`document.getElementById('result').textContent`), 'Loading accounts…');
    assert.equal(await evaluate(`[...views.values()].some(state=>Boolean(state.watch))`), false, 'Accounts starts without a Watch view');
    checks.push('Initial Accounts is pending, not empty; no Watch DOM or new report');
    await fixture('running');
    await until(`document.querySelectorAll('#result .watch-subscription').length === 6`);
    const healthy = await evaluate(`(() => {
      const visible=node=>getComputedStyle(node).display!=='none';
      return {gridOnly:document.getElementById('result').firstChild.children.length===1,
        controls:['.toolbar','#notice','#scope-controls','.report-search','#mini-watch-controls'].some(s=>visible(document.querySelector(s))),
        text:document.getElementById('result').textContent};})()`);
    assert.equal(healthy.gridOnly,true); assert.equal(healthy.controls,false);
    assert.doesNotMatch(healthy.text,/Snapshot|Reading this report|Accounts Overview|Billed|Observation details/);
    const fingerprint = () => evaluate(`[...document.querySelectorAll('#result .watch-subscription')].map(node=>({html:node.outerHTML,
      width:node.getBoundingClientRect().width,rows:getComputedStyle(node).gridTemplateRows}))`);
    const accountsCards = await fingerprint();
    await navigate('watch');
    assert.deepEqual(await fingerprint(),accountsCards,'identical publication produces identical card markup and geometry');
    await navigate('accounts');
    assert.deepEqual(await fingerprint(),accountsCards);
    assert.deepEqual(await evaluate('({streams:probeStreams,reports:probeReports})'),{streams:1,reports:reportCount});
    checks.push('Watch ↔ Accounts parity, retained navigation, one SSE and no route report jobs');
    await evaluate(`window.savedCard=document.querySelector('.watch-subscription');window.savedBar=savedCard.querySelector('progress');
      window.savedHelp=savedCard.querySelector('.watch-quota-capacity span');savedHelp.focus();
      window.savedText=savedCard.querySelector('h4').firstChild;const selection=getSelection();selection.setBaseAndExtent(savedText,0,savedText,6);
      window.mutations=0;window.observer=new MutationObserver(events=>mutations+=events.filter(e=>e.type==='childList').length);
      observer.observe(document.querySelector('.watch-account-grid'),{subtree:true,childList:true});`);
    for (let n=0;n<5;n++) await fixture('running');
    await until(`liveValue.view.accounts !== null`);
    assert.deepEqual(await evaluate(`({card:savedCard===document.querySelector('.watch-subscription'),bar:savedBar===savedCard.querySelector('progress'),
      focus:document.activeElement===savedHelp,selection:getSelection().toString(),mutations})`),
      {card:true,bar:true,focus:true,selection:'GitHub',mutations:0});
    await evaluate(`getSelection().removeAllRanges();observer.disconnect();`);
    await evaluate(`(async()=>{applySettings(await api('/api/settings/ccost',{ccostDisplayUnit:'usd'}));
      applySettings(await api('/api/settings/quota-display',{quotaDisplayMode:'remaining'}));})()`);
    assert.match(await evaluate(`savedCard.querySelector('.watch-quota-summary').textContent`), /remaining.*\$/);
    assert.match(await evaluate(`document.getElementById('context-help').textContent`), /Capacity: \$/);
    assert.equal(await evaluate('document.activeElement===savedHelp'),true);
    for (const width of [1200,360]) for (const theme of ['classic','light','dark']) {
      await command('Emulation.setDeviceMetricsOverride', {width,height:800,deviceScaleFactor:1.5,mobile:false},sessionId);
      await command('Emulation.setEmulatedMedia', {features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'},
        {name:'prefers-reduced-motion',value:'reduce'}]},sessionId);
      await evaluate(`(async()=>applySettings(await api('/api/settings/theme',{theme:'${theme==='classic'?'classic':'web'}'})))()`);
      const layout = await evaluate(`({width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,
        widths:[...document.querySelectorAll('.watch-subscription')].map(n=>n.getBoundingClientRect().width),
        subgrid:[...document.querySelectorAll('.watch-subscription')].every(n=>getComputedStyle(n).gridTemplateRows.startsWith('subgrid'))})`);
      assert.equal(layout.overflow,false); assert.equal(layout.subgrid,true);
      assert.ok(layout.widths.every(w=>w*1.5<=450)); layouts.push({theme,...layout});
      const image=await command('Page.captureScreenshot',{format:'png'},sessionId);
      await fs.writeFile(output.replace(/\.json$/,'')+`-${theme}-${width}.png`,Buffer.from(image.data,'base64'));
    }
    checks.push('Unchanged ticks preserve nodes/focus/selection/help; live unit/mode/theme, DPR/narrow/reduced-motion layouts');
    if(!quotaOnly) await require('./probe_subscription_capacity.cjs')({command,evaluate,until,sessionId,navigate,checks,layouts});
    await navigate('watch');
    await evaluate(`(async()=>{applySettings(await api('/api/settings/ccost',{ccostDisplayUnit:'credits'}));
      applySettings(await api('/api/settings/quota-display',{quotaDisplayMode:'used'}));})()`);
    await evaluate(`miniWatch.toggle()`,true);
    const targets=await command('Target.getTargets'); let pipSession;
    for(const target of targets.targetInfos.filter(target=>target.type==='page'&&target.targetId!==targetId)) {
      const attached=await command('Target.attachToTarget',{targetId:target.targetId,flatten:true});
      const result=await command('Runtime.evaluate',{expression:`!!document.querySelector('.mini-watch')`,returnByValue:true},attached.sessionId);
      if(result.result.value){pipSession=attached.sessionId;break;}
    }
    assert.ok(pipSession,'actual hidden Document PiP for compact quota compatibility');
    await require('./probe_quota_display.cjs')({evaluate,until,command,sessionId,pipSession,checks,layouts,fixture,navigate});
    // Restore this driver's Remaining/USD prerequisites after the compact probe's defaults.
    await evaluate(`(async()=>{applySettings(await api('/api/settings/ccost',{ccostDisplayUnit:'usd'}));
      applySettings(await api('/api/settings/quota-display',{quotaDisplayMode:'remaining'}));})()`);
    await evaluate(`miniWatch.toggle()`,true);await navigate('accounts');
    await fixture('accounts-stale');
    await until(`document.querySelector('.watch-subscription').textContent.includes('Stale')`);
    assert.match(await evaluate(`document.getElementById('result').textContent`),/Connection failed/);
    await fixture('accounts-failed-empty');
    await until(`liveValue.view.accounts.accounts.length===0`);
    assert.equal(await evaluate(`document.querySelectorAll('.watch-subscription').length`),6);
    assert.match(await evaluate(`document.getElementById('result').textContent`),/retained, not current/);
    await fixture('accounts-empty');
    await until(`document.getElementById('result').textContent==='No configured accounts detected.'`);
    await fixture('quota-ratio');
    await until(`document.querySelectorAll('.watch-subscription').length===1`);
    assert.equal(await evaluate(`document.querySelectorAll('.watch-secondary-quota').length`),1);
    assert.match(await evaluate(`document.querySelector('.watch-subscription').textContent`),/90% remaining/);
    await fixture('quota-idle');
    await until(`document.querySelector('.watch-quota-summary').textContent.includes('100% remaining')`);
    assert.match(await evaluate(`document.querySelector('.watch-subscription').textContent`),/Window not started/);
    await fixture('running');
    await until(`document.querySelectorAll('.watch-subscription').length===6`);
    checks.push('Stale/failed retained observations, genuine empty, recovery/membership, primary/secondary and idle quota updates');
    await navigate('settings');
    await until(`!document.getElementById('ccost-unit').disabled`);
    await evaluate(`const select=document.getElementById('ccost-unit');select.value='default';select.dispatchEvent(new Event('change'));`);
    await until(`document.getElementById('settings-feedback').textContent==='CCost display saved.'`);
    await navigate('accounts');
    assert.doesNotMatch(await evaluate(`document.querySelector('.watch-quota-summary').textContent`),/\$/);
    assert.deepEqual(await evaluate('({streams:probeStreams,reports:probeReports})'),{streams:1,reports:reportCount});
    // The server's real terminal event is not hidden with the Accounts report shell.
    await fixture('stop');
    await until('hostState.terminal');
    assert.equal(await evaluate(`document.getElementById('host-state').hidden`),false);
    assert.equal(await evaluate(`document.querySelectorAll('.watch-subscription').length`),6);
    assert.deepEqual(errors,[]);
    checks.push('Settings default applies to retained route; actual host-stop SSE keeps cards and visible failure feedback');
    evidence={outcome:'PASS',browser:version.product,checks,layouts,streams:1,route_report_jobs:0,
      limitations:['Synthetic acquisition; real-installation account-owner proof is separate.',
        'Headless DOM/layout/input, not physical desktop, assistive technology or macOS proof.']};
  } catch(error) { evidence={outcome:'FAIL',checks,layouts,reason:error.message,errors};process.exitCode=1; }
  finally {
    clearTimeout(deadline);
    try {await command('Browser.close');} catch {}
    if(child.exitCode===null)child.kill();
    server.stdin.end();
    if(server.exitCode===null)await new Promise(resolve=>server.once('exit',resolve));
    for(const entry of pending.values())clearTimeout(entry.timer);
    await fs.writeFile(output,JSON.stringify(evidence,null,2)+'\n');
    console.log(JSON.stringify(evidence));
  }
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
