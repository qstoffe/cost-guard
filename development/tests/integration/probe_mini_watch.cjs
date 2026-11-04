// Real Document PiP in an owned hidden Chromium profile, shipped HTTP/CSP/SSE.
// Explicit browser/output, no package installs, personal profiles or desktop input.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output, scale = '1'] = process.argv.slice(2);
async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output));
  assert.ok(['1','1.5','2'].includes(scale));
  await fs.stat(browser); await fs.stat(path.dirname(output));
  const profile = await fs.mkdtemp(path.join(path.dirname(output), 'mini-browser-'));
  const configRoot = await fs.mkdtemp(path.join(path.dirname(output), 'mini-config-'));
  let server, lines;
  const startServer = () => {
    server = spawn('py', ['-3', 'development/tests/integration/serve_mini_watch.py', configRoot], {windowsHide:true, stdio:['pipe','pipe','pipe']});
    lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  };
  startServer();
  const next = async () => JSON.parse((await lines.next()).value);
  const fixture = async command => {server.stdin.write(JSON.stringify({command})+'\n'); return next();};
  const restart = async () => {
    const exited = new Promise(resolve => server.once('exit', resolve)); server.stdin.end(); await exited;
    startServer(); return next();
  };
   const child = spawn(browser, ['--headless=new', `--screen-info={${1920*Number(scale)}x${1080*Number(scale)}}`, '--force-device-scale-factor='+scale, '--no-first-run', '--no-default-browser-check',
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
    const checks = [], screenshots = [], layouts = []; let evidence = {outcome:'FAIL'};
  try {
    let launch = await next(); // Secret bootstrap URL is never logged or retained.
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
    await require('./probe_mini_placement.cjs')({evaluate,until,command,sessionId,targetId,
      restart:async () => { launch = await restart(); return launch; },checks,layouts,output,screenshots});
    const checkIcon = async () => {
      await until(`miniWatch.window.performance.getEntriesByType('resource').some(entry =>
        entry.name === new URL('/favicon-cg1.ico',location.href).href && entry.initiatorType === 'other')`);
      const icon = await evaluate(`(() => {const icons=miniWatch.window.document.querySelectorAll('link[rel="icon"]');
        return {count:icons.length,type:icons[0]?.type,url:icons[0]?.href,owner:document.querySelector('link[rel="icon"]').href};})()`);
      assert.deepEqual(icon,{count:1,type:'image/x-icon',url:new URL('/favicon-cg1.ico',launch.url).href,
        owner:new URL('/favicon-cg1.ico',launch.url).href});
      const resource = await evaluate(`miniWatch.window.fetch(new URL('/favicon-cg1.ico',location.href)).then(async response =>
        ({status:response.status,type:response.headers.get('Content-Type'),bytes:(await response.arrayBuffer()).byteLength}))`);
      assert.equal(resource.status,200); assert.equal(resource.type,'image/x-icon'); assert.ok(resource.bytes>1000);
    };
    await checkIcon();
    const metrics = () => evaluate(`[...miniWatch.view.body.rows].map(row=>[...row.cells].map(cell=>cell.textContent))`);
    assert.deepEqual((await metrics()).map(row=>row.slice(1,4)),[['#24','3','20m'],['#23','2','10m']]);
    assert.deepEqual((await metrics()).map(row=>row[4]),['120k','120k']);
    assert.equal(await evaluate(`miniWatch.view.body.parentNode.querySelectorAll('th')[4].title`),
      'Estimated next incoming context for this prompt; N/A means unavailable');
    assert.match(await evaluate(`miniWatch.view.body.parentNode.getAttribute('aria-label')`), /estimated next incoming context \(CTX\)/);
    await evaluate(`miniWatch.view.drawDaily(null,false)`);
    assert.equal(await evaluate(`miniWatch.view.daily.textContent`),'CCost Today · Loading…');
    assert.match(await evaluate(`miniWatch.view.daily.getAttribute('aria-label')`), /^CCost Today · Loading…/);
    await evaluate(`miniWatch.settings()`);
    assert.equal(await evaluate(`documentPictureInPicture.window === miniWatch.window`),true);
    await until(`miniWatch.window.getComputedStyle(miniWatch.view.prompts).overflowY === 'auto'`);
    const alignment = await evaluate(`(() => {const w=miniWatch.window,v=miniWatch.view;return {
      headers:[...v.body.parentNode.querySelectorAll('th')].map(cell=>w.getComputedStyle(cell).textAlign),
      cells:[...v.body.rows[0].cells].map(cell=>w.getComputedStyle(cell).textAlign),
      daily:v.daily.textContent,full:[...document.querySelector('.watch-daily').children].slice(1,3).map(cell=>cell.textContent),
      separate:!v.summary.contains(v.daily),headerPadding:w.getComputedStyle(v.root.firstElementChild).padding,
      sameRow:Math.abs(v.summary.getBoundingClientRect().top-v.daily.getBoundingClientRect().top)<8};})()`);
    assert.deepEqual(alignment.headers,Array(5).fill('center'));
    assert.deepEqual(alignment.cells,['left','right','right','right','right']);
    assert.equal(alignment.daily,`CCost Today ${alignment.full[0]} · ${alignment.full[1]}`);
    assert.equal(await evaluate(`document.querySelector('.watch-daily strong').textContent`),'CCost Today');
    assert.equal(await evaluate(`document.querySelector('.watch-daily').getAttribute('aria-label')`),'CCost Today');
    assert.equal(alignment.separate,true); assert.equal(alignment.sameRow,true); assert.equal(alignment.headerPadding,'0px');
    await evaluate(`miniWatch.view.daily.click()`);
    assert.equal(await evaluate(`location.hash`),'#/watch','daily summary is non-navigating');
    assert.equal(await evaluate(`miniWatch.window.getComputedStyle(miniWatch.view.root).borderTopWidth`),'0px');
    assert.equal(await evaluate(`miniWatch.view.root.querySelector('.mini-close')`),null);
    await until(`getComputedStyle(miniWatch.button).backgroundColor === getComputedStyle(document.querySelector('nav a[aria-current="page"]')).backgroundColor`);
    checks.push('Real user-activated Document PiP opens prompt-local table with external CSP styles, no inner frame/close and selected On fill');
    const pip = () => evaluate(`!!miniWatch.window && !miniWatch.window.closed`);
    await fixture('density-5-3'); await until(`miniWatch.view.body.rows.length === 5 && miniWatch.view.accounts.children.length === 3`);
    const initial = await evaluate(`(() => {const w=miniWatch.window,v=miniWatch.view;return {width:w.innerWidth,height:w.innerHeight,outerHeight:w.outerHeight,dpr:w.devicePixelRatio,
      prompts:v.prompts.scrollHeight>v.prompts.clientHeight,accounts:v.accounts.scrollHeight>v.accounts.clientHeight,
      promptHeight:v.prompts.clientHeight,accountHeight:v.accounts.clientHeight,
      outer:w.document.documentElement.scrollHeight>w.innerHeight};})()`);
    layouts.push({case:'initial-unattached-5-3',...initial});
    assert.equal(initial.outer,false); assert.ok(initial.promptHeight>=32 && initial.accountHeight>=32,JSON.stringify(initial));
    await fixture('running'); await until(`miniWatch.view.body.rows.length === 2 && miniWatch.view.accounts.children.length === 6`);
    const targets = await command('Target.getTargets');
    let pipSession = null;
    for (const target of targets.targetInfos.filter(item=>item.targetId!==targetId && item.type==='page')) {
      const attached = await command('Target.attachToTarget',{targetId:target.targetId,flatten:true});
      const found = await command('Runtime.evaluate',{expression:'!!document.querySelector(".mini-watch")',returnByValue:true},attached.sessionId);
      if (found.result.value) {pipSession=attached.sessionId; break;}
    }
    assert.ok(pipSession,'owned Document PiP target available for rendered geometry and theme checks');
    await require('./probe_mini_theme.cjs')({evaluate,until,command,sessionId,pipSession,checks,layouts,output,screenshots});
    await require('./probe_quota_display.cjs')({evaluate,until,command,sessionId,pipSession,checks,layouts});
    const columns = () => evaluate(`(() => {
      const w=miniWatch.window,v=miniWatch.view,table=v.body.parentNode;
      const cells=[...table.rows].filter(row=>row.cells.length===5).map(row=>[...row.cells]);
      const intrinsic=cell=>{const range=w.document.createRange();range.selectNodeContents(cell);
        const s=w.getComputedStyle(cell);return range.getBoundingClientRect().width+
          parseFloat(s.paddingLeft)+parseFloat(s.paddingRight)+parseFloat(s.borderLeftWidth)+parseFloat(s.borderRightWidth);};
      return {width:w.innerWidth,pageOverflow:w.document.documentElement.scrollWidth>w.innerWidth,
        scroll:v.prompts.scrollWidth>v.prompts.clientWidth,region:v.prompts.clientWidth,
        widths:cells[0].map(cell=>cell.getBoundingClientRect().width),
        required:[1,2,3,4].map(index=>Math.max(...cells.map(row=>intrinsic(row[index])))),
        wrap:cells.flatMap(row=>row.slice(1)).map(cell=>w.getComputedStyle(cell).whiteSpace),
        ellipsis:cells.flatMap(row=>row.slice(1)).some(cell=>w.getComputedStyle(cell).textOverflow==='ellipsis'),
        title:v.body.querySelector('.mini-session')?.scrollWidth>v.body.querySelector('.mini-session')?.clientWidth};})()`);
    const checkColumns = async name => {
      const value=await columns(); layouts.push({case:name,...value});
      assert.equal(value.pageOverflow,false); assert.equal(value.ellipsis,false);
      assert.ok(value.wrap.every(mode=>mode==='nowrap'));
      value.required.forEach((width,index)=>assert.ok(Math.abs(value.widths[index+1]-width)<1.1,JSON.stringify(value)));
      if (!value.scroll) assert.ok(Math.abs(value.widths.reduce((a,b)=>a+b,0)-value.region)<1.1,JSON.stringify(value));
      return value;
    };
    await require('./probe_mini_sessions.cjs')({evaluate,until,fixture,command,pipSession,layouts,checks,output,screenshots});
    await require('./probe_mini_session_alignment.cjs')({evaluate,until,fixture,command,sessionId,pipSession,layouts,checks});
    await fixture('density-6-4-long'); await until(`miniWatch.view.body.rows.length===6`);
    assert.equal((await checkColumns('intrinsic-long-titles')).title,true);
    await evaluate(`(() => {const p=structuredClone(liveValue);p.state='running';p.view.now_ms++;
      p.view.active_cards[0].rows[0].prompt.prompt_number=123456;
      p.view.active_cards[0].rows[0].prompt.display.ccost='?123 456.78';
      p.view.active_cards[0].rows[0].prompt.display_units.credits.ccost='?123 456.78';
      p.view.active_cards[0].rows[0].display.watch_duration_ms='123h 59m';
      p.view.active_cards[0].rows[0].live_context.display.watch_next_context_tokens='123 456';
      miniWatch.update(p);})()`);
    const longColumns=await checkColumns('intrinsic-growing-metrics');
    assert.equal((await metrics()).find(row=>row[1]==='#123456')[4],'123 456');
    for (const formatted of ['234 567','0','N/A']) {
      await evaluate(`(() => {const p=structuredClone(miniWatch.publication);p.view.now_ms++;
        p.view.active_cards[0].rows[0].live_context.display.watch_next_context_tokens='${formatted}';miniWatch.update(p);})()`);
      assert.equal((await metrics()).find(row=>row[1]==='#123456')[4],formatted);
    }
    assert.equal(longColumns.scroll,false);
    await fixture('empty'); await until(`miniWatch.view.body.rows.length===1 && miniWatch.view.body.rows[0].cells.length===1`);
    await checkColumns('intrinsic-empty-colspan');
    await fixture('running'); await until(`miniWatch.view.body.rows.length===2`);
    await checkColumns('intrinsic-shrinking-metrics');
    const savedMetrics=await metrics(), savedDaily=await evaluate('miniWatch.view.daily.textContent');
    await fixture('unavailable'); await until(`liveValue.view.cards_state==='unavailable'`);
    assert.deepEqual(await metrics(),savedMetrics); assert.equal(await evaluate('miniWatch.view.daily.textContent'),savedDaily);
    assert.equal(await evaluate(`miniWatch.view.health.hidden && !/Not current|quota stale|not live/.test(miniWatch.view.root.textContent)`),true);
    await evaluate(`miniWatch.view.update(miniWatch.publication,{kind:'reconnecting'},true,miniWatch.observations,miniWatch.observations.started+599999)`);
    assert.equal(await evaluate('miniWatch.view.health.hidden'),true);
    await evaluate(`miniWatch.view.update(miniWatch.publication,{kind:'reconnecting'},true,miniWatch.observations,Date.now()+600000)`);
    assert.equal(await evaluate('miniWatch.view.health.textContent'),'Updates unavailable · showing last values');
    await fixture('running'); await until(`miniWatch.view.health.hidden`);
    checks.push('Intrinsic metric/header minima grow/shrink with content, empty colspan does not distort, only Session ellipsizes; failed reads retain figures quietly and one ten-minute notice clears on recovery');
    // PiP is not consistently exposed as a CDP target; DOM is accessible through its owning document.
    await evaluate(`location.hash='#/settings'`);
    await until(`document.getElementById('web-theme')?.disabled === false`);
    assert.equal(await pip(),true);
    await evaluate(`document.getElementById('web-theme').value='web'; document.getElementById('web-theme').dispatchEvent(new Event('change'))`);
    await until(`miniWatch.window.document.documentElement.dataset.theme === 'web'`);
    await evaluate(`document.getElementById('ccost-unit').value='usd'; document.getElementById('ccost-unit').dispatchEvent(new Event('change'))`);
    await until(`miniWatch.view.body.rows[0].cells[2].textContent === '$0.03'`);
    await evaluate(`miniWatch.view.summary.click()`,true);
    await until(`location.hash === '#/watch'`);
    assert.equal(await pip(),true);
    assert.equal(await evaluate('probeStreams'),1);
    checks.push('Navigation, existing-opener return, live theme/USD propagation keep Mini and exactly one EventSource');
    // Initial request geometry is checked separately; also exercise native resize
    // to the requested outer size before compact-target screenshots.
    await evaluate(`miniWatch.window.resizeTo(560,450)`,true);
    await until(`miniWatch.window.innerWidth <= 560 && miniWatch.window.innerHeight <= 450`);
    await fixture('density-5-3');
    await until(`miniWatch.view.body.rows.length === 5 && miniWatch.view.accounts.children.length === 3`);
    const geometry = () => evaluate(`(() => {const w=miniWatch.window,d=w.document,v=miniWatch.view;return {
      width:w.innerWidth,height:w.innerHeight,outer:d.documentElement.scrollHeight>w.innerHeight || d.body.scrollHeight>w.innerHeight,
      horizontal:d.documentElement.scrollWidth>w.innerWidth, prompts:v.prompts.scrollHeight>v.prompts.clientHeight,
      accounts:v.accounts.scrollHeight>v.accounts.clientHeight,barHeight:parseFloat(w.getComputedStyle(v.accounts.querySelector('progress')).height),
      promptHeight:v.prompts.clientHeight,promptContent:v.prompts.scrollHeight,accountHeight:v.accounts.clientHeight,accountContent:v.accounts.scrollHeight,
      header:w.getComputedStyle(v.body.parentNode.querySelector('th')).position,healthyHidden:v.health.hidden};})()`);
    const normal = await geometry();
    layouts.push({case:'native-resize-5-3',...normal});
    assert.equal(normal.outer,false); assert.equal(normal.horizontal,false);
    if (Number(scale)<=1.5) {
      assert.equal(normal.prompts,false,JSON.stringify(normal)); assert.equal(normal.accounts,false,JSON.stringify(normal));
    } else assert.ok(normal.promptHeight>=32 && normal.accountHeight>=32,'clamped higher-scale window retains reachable scroll regions');
    assert.equal(normal.healthyHidden,true);
    assert.equal(normal.header,'sticky'); assert.ok(normal.barHeight>=9 && normal.barHeight<=11);
    await fixture('density-6-4');
    await until(`miniWatch.view.body.rows.length === 6 && miniWatch.view.accounts.children.length === 4`);
    const overflow = await geometry(); assert.equal(overflow.prompts,true); assert.equal(overflow.accounts,true); assert.equal(overflow.outer,false);
    await evaluate(`miniWatch.view.prompts.scrollTop=30`);
    const promptScroll = await evaluate(`miniWatch.view.prompts.scrollTop`); assert.ok(promptScroll>0);
    assert.equal(await evaluate(`miniWatch.view.accounts.scrollTop`),0);
    await evaluate(`miniWatch.view.accounts.scrollTop=20`);
    assert.equal(await evaluate(`miniWatch.view.prompts.scrollTop`),promptScroll);
    for (const count of [1,2,3,4,6]) {
      await fixture('density-1-'+count); await until(`miniWatch.view.accounts.children.length === ${count}`);
      const layout = await geometry(); assert.equal(layout.outer,false);
      if (Number(scale)<=1.5 || count>3) assert.equal(layout.accounts,count>3);
    }
    await fixture('running'); await until(`miniWatch.view.body.rows.length === 2 && miniWatch.view.accounts.children.length === 6`);
    checks.push('Compact opening and higher-scale browser clamps keep reachable independent scroll regions; enlarged 5/3 fits at 100/150%, 6/4 scroll; centered headers, semantic data alignment, canonical separate daily summary');
    await evaluate(`miniWatch.view.earlierToggle.click();miniWatch.view.prompts.scrollTop=0`);
    for (const [theme,scheme,background] of [['classic','light','#101112'],['web','light','#eef2f8'],['web','dark','#0c1422']]) {
      await evaluate(`document.documentElement.dataset.theme='${theme}'; miniWatch.settings()`);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]},sessionId);
      await until(`miniWatch.window.getComputedStyle(miniWatch.window.document.documentElement).getPropertyValue('--bg').trim() === '${background}'`);
       const layout = await evaluate(`(() => {const w=miniWatch.window,d=w.document,r=miniWatch.view.root;return {width:w.innerWidth,height:w.innerHeight,background:w.getComputedStyle(d.documentElement).getPropertyValue('--bg').trim(),overflow:d.documentElement.scrollWidth>w.innerWidth,lines:miniWatch.view.accounts.children.length,clutter:/Reset|CCost Today|Provisional/.test(miniWatch.view.accounts.textContent),title:r.querySelector('li').textContent};})()`);
       layouts.push({case:theme+'-'+scheme,width:layout.width,height:layout.height});
      assert.equal(layout.background,background); assert.equal(layout.overflow,false); assert.equal(layout.lines,6); assert.equal(layout.clutter,false);
      if (pipSession) {
         const image = await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false,
           clip:{x:0,y:0,width:layout.width,height:layout.height,scale:1}},pipSession);
        const name = output.replace(/\.json$/,'')+`-${theme}-${scheme}.png`;
        await fs.writeFile(name,Buffer.from(image.data,'base64')); screenshots.push(path.basename(name));
      }
    }
    checks.push('Classic/Web light/dark styles, long account labels, primary-only six-account content without page overflow');
    await command('Runtime.evaluate',{expression:`document.documentElement.style.fontSize='125%'`},pipSession);
    assert.equal((await geometry()).horizontal,false);
    await command('Runtime.evaluate',{expression:`document.documentElement.style.fontSize=''`},pipSession);
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
    await checkColumns('intrinsic-narrow-native-resize');
    await evaluate(`(() => {const p=structuredClone(liveValue);p.view.now_ms++;
      p.view.active_cards[0].rows[0].prompt.prompt_number=123456789;
      p.view.active_cards[0].rows[0].prompt.display_units.usd.ccost='?$123 456.78';
      p.view.active_cards[0].rows[0].display.watch_duration_ms='123h 59m';
      p.view.active_cards[0].rows[0].live_context.display.watch_next_context_tokens='123 456';
      miniWatch.update(p);})()`);
    assert.equal((await checkColumns('intrinsic-narrow-large-metrics')).scroll,true);
    assert.equal(await evaluate(`!miniWatch.view.earlier.hidden && miniWatch.view.historyBody.rows[0].cells.length===2 && miniWatch.view.doc.documentElement.scrollWidth<=miniWatch.window.innerWidth`),true);
    const narrowImage=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},pipSession);
    const narrowPath=output.replace(/\.json$/,'')+'-earlier-narrow.png';
    await fs.writeFile(narrowPath,Buffer.from(narrowImage.data,'base64'));screenshots.push(path.basename(narrowPath));
    await evaluate(`miniWatch.view.earlierToggle.click()`);
    await fixture('running'); await until(`miniWatch.view.body.rows[0].cells[1].textContent==='#24'`);
    checks.push('Keyboard summary focus/activation and user-activated native PiP resize remain usable');
    const backgroundTarget = await command('Target.createTarget',{url:'about:blank'});
    const backgroundSession = await command('Target.attachToTarget',{targetId:backgroundTarget.targetId,flatten:true});
    await command('Page.bringToFront',{},backgroundSession.sessionId);
    await until(`document.hidden`);
    assert.equal(await evaluate(`miniWatch.window.document.hidden`),false);
    await fixture('terminal'); await until(`miniWatch.view.body.querySelector('.mini-success')`);
    assert.deepEqual((await metrics()).map(row=>row.slice(1,4)),[['#24','$0.03','20m'],['#23','$0.01','10m']]);
    await fixture('empty'); await until(`miniWatch.view.body.textContent.includes('No running or recently ended prompts')`);
    await fixture('recovering'); await until(`liveValue.state==='recovering'`);
    assert.equal(await evaluate(`miniWatch.view.health.hidden`),true);
    await fixture('running'); await until(`miniWatch.view.health.hidden`);
    checks.push('With main document actually hidden and PiP visible, real SSE preserves final prompt-local completion metrics and updates empty/recovery without rAF');
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
    assert.equal(await evaluate(`miniWatch.view.earlier.hidden`),true,'fresh PiP reopens history collapsed');
    await checkIcon();
    assert.equal(await evaluate('probeStreams'),1,'closing/reopening Mini never adds an EventSource');
    checks.push('Shipped controller attaches/fetches the existing absolute same-origin ICO on open/reopen; owner icon and single SSE unchanged (not OS icon proof)');
    await evaluate(`miniWatch.button.click()`,true);
    await until(`!miniWatch.window`);
    await evaluate(`miniWatch.toggle()`,true);
    await command('Page.reload',{},sessionId);
    await until(`typeof miniWatch !== 'undefined' && hostState.kind === 'connected' && !miniWatch.window`);
    checks.push('Native API replacement, browser-owned close, main toggle, reopen and main reload synchronize Off; no auto-open');
    // Unsupported and rejected requests are deterministic VM cases; actual lack of
    // user activation can also be tested against the native browser API.
    await evaluate(`location.hash='#/watch'`);
    await until(`document.body.dataset.section === 'watch'`);
    await evaluate(`miniWatch.toggle()`,true);
    await fixture('stop');
    await until(`hostState.kind === 'stopped'`);
    assert.match(await evaluate(`miniWatch.view.health.textContent`),/Host stopped · restart Cost Guard/);
    assert.equal(await pip(),true,'host shutdown marks retained figures not live without pretending window close');
    checks.push('Real terminal shutdown reaches open Mini as not live');
    assert.deepEqual(errors,[]);
      evidence = {outcome:'PASS',browser:version.product,emulatedDeviceScale:Number(scale),checks,layouts,screenshots,
      limitations:['Headless Chromium only; no physical/native X, native return/replacement chrome, minimized-opener restoration, always-on-top OS geometry or screen-reader proof.']};
   } catch (error) {console.error(error.stack);evidence={outcome:'FAIL',checks,layouts,screenshots,reason:error.message};process.exitCode=1;}
  finally {
    clearTimeout(deadline);
    try {await command('Browser.close');} catch {}
    server.stdin.end();
    await new Promise(resolve=>{if(child.exitCode!==null) resolve(); else {child.once('exit',resolve);setTimeout(resolve,3000);}});
    if(child.exitCode===null) child.kill();
    if(server.exitCode===null) server.kill();
    try {await fs.rm(profile,{recursive:true});} catch {}
    try {await fs.rm(configRoot,{recursive:true});} catch {}
    await fs.writeFile(output,JSON.stringify(evidence,null,2)+'\n'); console.log(JSON.stringify(evidence));
  }
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
