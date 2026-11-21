// Hidden Chromium, shipped app/auth/HTTP and controlled canonical in-memory reports.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const {probeToolbar} = require('./probe_models_toolbar.cjs');
const {probeModelsValues} = require('./probe_models_values.cjs');
const {probeModelsParity} = require('./probe_models_parity.cjs');
const [browser, output, baseline] = process.argv.slice(2);
const modelName = name => `[...document.querySelectorAll('.overview-model-table tbody tr')]
  .find(row => row.cells[1].textContent === ${JSON.stringify(name)}).cells[1].firstElementChild`;

async function probeCategory({command, evaluate, until, id, key}) {
  const name = modelName('GPT-Test'), panel = `document.querySelector('#context-help')`;
  const themeBefore = await evaluate(id,'document.documentElement.getAttribute("data-theme")');
  const open = `${panel}?.matches(':popover-open') && ${panel}.textContent === 'GitHub category: Powerful'`;
  const focusBeforeName = `(() => {
    const previous = (${name}).closest('tr').previousElementSibling;
    (previous?.querySelector('.model-relative') || document.querySelector('.overview-models')).focus();
  })()`;
  const escape = async () => {
    for (const type of ['keyDown','keyUp']) {
      await command('Input.dispatchKeyEvent',{type,key:'Escape',code:'Escape',windowsVirtualKeyCode:27},id);
    }
    await until(id,`${panel}.hidden`);
  };
  const point = `(() => {
    const n = ${name}; n.scrollIntoView({block:'center',inline:'center'});
    const r = n.getBoundingClientRect(); return {x:r.left+r.width/2,y:r.top+r.height/2};
  })()`;
  assert.equal(await evaluate(id,`(${modelName('GPT-Other-2')}).tabIndex`),-1);
  assert.equal(await evaluate(id,`(${name}).parentElement.tabIndex`),-1);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...await evaluate(id,point)},id);
  await until(id,open);
  await escape();
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:1,y:1},id);
  await command('Emulation.setTouchEmulationEnabled',{enabled:true},id);
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[await evaluate(id,point)]},id);
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},id);
  await until(id,open);
  await escape();
  await command('Emulation.setTouchEmulationEnabled',{enabled:false},id);

  for (const width of [360,1280]) for (const theme of ['classic','light','dark']) for (const zoom of [1,1.5]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},id);
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},id);
    await evaluate(id,`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}';
      document.documentElement.style.zoom='${zoom}'; ${focusBeforeName}`);
    await key(id);
    await until(id,open);
    const facts = await evaluate(id,`(() => {
      const tooltip = ${panel}, r = tooltip.getBoundingClientRect(), s = getComputedStyle(tooltip);
      const rgb = color => {
        const ctx = document.createElement('canvas').getContext('2d');
        ctx.fillStyle = color; ctx.fillRect(0,0,1,1);
        return [...ctx.getImageData(0,0,1,1).data];
      };
      const luma = values => values.slice(0,3).map(v => v/255)
        .map(v => v <= .04045 ? v/12.92 : ((v+.055)/1.055)**2.4)
        .reduce((n,v,i) => n + v*[.2126,.7152,.0722][i], 0);
      const fg = rgb(s.color), bg = rgb(s.backgroundColor);
      const luminances = [luma(fg),luma(bg)];
      return {
        fits:r.left>=0 && r.top>=0 && r.right<=innerWidth && r.bottom<=innerHeight,
        contrast:fg[3]===255 && bg[3]===255 &&
          (Math.max(...luminances)+.05)/(Math.min(...luminances)+.05)>=4.5,
        accessible:document.activeElement===(${name}) &&
          document.activeElement.getAttribute('aria-describedby')===tooltip.id &&
          tooltip.getAttribute('role')==='tooltip'
      };
    })()`);
    assert.deepEqual(facts,{fits:true,contrast:true,accessible:true},`${width}px ${theme} at ${zoom}x`);
    await escape();
  }
  await evaluate(id,`document.activeElement.blur(); document.documentElement.style.removeProperty('zoom');
    ${themeBefore === null ? "delete document.documentElement.dataset.theme" :
      `document.documentElement.dataset.theme=${JSON.stringify(themeBefore)}`}`);
  await command('Emulation.clearDeviceMetricsOverride',{},id);
  await command('Emulation.setEmulatedMedia',{features:[]},id);
}

async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output));
  await fs.stat(browser); await fs.stat(path.dirname(output));
  const profile = await fs.mkdtemp(path.join(path.dirname(output), 'prices-browser-'));
  const config = await fs.mkdtemp(path.join(path.dirname(output), 'prices-config-'));
  const server = spawn('py', ['-3', 'development/tests/integration/serve_mini_watch.py', config, '--models-refresh'],
    {windowsHide:true,stdio:['pipe','pipe','pipe']});
  let serverErrors = ''; server.stderr.on('data', chunk => {serverErrors = (serverErrors + chunk.toString()).slice(-4000);});
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const child = spawn(browser, ['--headless=new','--no-first-run','--no-default-browser-check','--disable-extensions',
    '--disable-background-networking','--remote-debugging-pipe','--user-data-dir='+profile,'about:blank'],
    {windowsHide:true,stdio:['ignore','ignore','ignore','pipe','pipe']});
  const pending = new Map(); let sequence = 0, buffer = '', phase = 'startup'; const errors = [], checks = [], layouts = [], requests = [];
  child.stdio[4].on('data', chunk => {
    buffer += chunk.toString(); let index;
    while ((index=buffer.indexOf('\0'))>=0) {
      const value=JSON.parse(buffer.slice(0,index)); buffer=buffer.slice(index+1);
      if (value.id) { const entry=pending.get(value.id); pending.delete(value.id);
        if (entry) {clearTimeout(entry.timer); value.error?entry.reject(new Error(JSON.stringify(value.error))):entry.resolve(value.result);} }
      else if (value.method==='Runtime.exceptionThrown') errors.push(value.params.exceptionDetails.text);
      else if (value.method==='Network.requestWillBeSent') {
        const route = new URL(value.params.request.url).pathname;
        if(route.startsWith('/api/models')) requests.push({route,method:value.params.request.method,at:Date.now()});
      }
    }
  });
  const command=(method,params={},sessionId)=>new Promise((resolve,reject)=>{
    const id=++sequence,timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout: '+method+' in '+phase));},15000);
    pending.set(id,{resolve,reject,timer});child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');
  });
  const evaluate=async (id,expression,userGesture=false)=>{
    const value=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true,userGesture},id);
    if(value.exceptionDetails) throw new Error(JSON.stringify(value.exceptionDetails)); return value.result.value;
  };
  const until=async (id,expression)=>{
    const end=Date.now()+20000;
    while(Date.now()<end) {if(await evaluate(id,expression))return;await new Promise(resolve=>setTimeout(resolve,30));}
    const state=await evaluate(id,`({section:typeof current==='undefined'?null:current?.section,loading:typeof current==='undefined'?null:current?.loading,
      notice:document.getElementById('notice')?.textContent,text:document.getElementById('result')?.textContent.slice(0,300),
      host:typeof hostState==='undefined'?null:hostState.kind,focus:document.activeElement?.outerHTML,
      help:document.querySelector('#context-help')?.outerHTML.slice(0,500),hasFocus:document.hasFocus(),visibility:document.visibilityState})`);
    throw new Error('Condition not reached: '+expression+' '+JSON.stringify({state,errors,fixture:await mode('status')})+' '+serverErrors);
  };
  const mode=async value=>{server.stdin.write(JSON.stringify({command:'models-'+value})+'\n');return JSON.parse((await lines.next()).value);};
  const key=async id=>{
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},id);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},id);
  };
  let evidence={outcome:'FAIL'};
  const deadline=setTimeout(()=>{child.kill();server.kill();},300000);
  try {
    const launch=JSON.parse((await lines.next()).value); // One-use credential stays private.
    const {targetId}=await command('Target.createTarget',{url:'about:blank'});
    const {sessionId:id}=await command('Target.attachToTarget',{targetId,flatten:true});
    await command('Page.enable',{},id); await command('Runtime.enable',{},id); await command('Network.enable',{},id);
    await command('Page.bringToFront',{},id);
    await command('Page.navigate',{url:launch.url},id);
    await until(id,`typeof current!=='undefined' && !!current?.result && !current.loading && hostState.writable`);
    const read=()=>evaluate(id,`({date:current.result.view.pricing_retrieved_at_ms,revision:current.result.view.model_catalog,
      sample:current.result.view.token_mix,models:current.result.view.model_comparison,choice:current.models})`);
    const initial=await read(); assert.equal((await mode('status')).fetches,1);
    await until(id,`document.querySelectorAll('.benchmark-table tbody tr').length===4 && !current.benchmark.loading && !current.benchmark.refresh.disabled`);
    if (['--isolation-baseline','--isolation-only'].includes(baseline)) {
      phase='isolation';
      const isolation=await require('./probe_models_isolation.cjs').probeIsolation({command,evaluate,until,id,mode,requests,
        fixture:async command=>{server.stdin.write(JSON.stringify({command})+'\n');return JSON.parse((await lines.next()).value);},
        baseline:baseline==='--isolation-baseline'});
      evidence={outcome:baseline==='--isolation-baseline'?'OBSERVED':'PASS',browser:(await command('Browser.getVersion')).product,...isolation};
      console.log(JSON.stringify(evidence));return;
    }
    phase='model-category';
    await probeCategory({command,evaluate,until,id,key});
    assert.equal((await mode('status')).fetches,1);
    checks.push('Model-name help: native hover, touch, Tab and Escape; no request or missing-label focus stop; contrast, bounds and tooltip association in 12 theme/width/zoom cases');
    if (baseline === '--category-only') {
      await mode('changed');
      await evaluate(id,`document.querySelector('[data-model-control="refresh"]').click()`);
      await until(id,`!current.loading && current.result.view.model_catalog.rows
        .some(row=>row.model==='GPT-Test' && row.category==='Lightweight')`);
      await key(id);
      await evaluate(id,`(${modelName('GPT-Test')}).focus()`);
      await until(id,`document.querySelector('#context-help')?.matches(':popover-open') &&
        document.querySelector('#context-help').textContent === 'GitHub category: Lightweight'`);
      assert.equal((await mode('status')).fetches,2);
      checks.push('A normal price refresh updates the matching tooltip from Powerful to Lightweight');
      evidence={outcome:'PASS',browser:(await command('Browser.getVersion')).product,checks};
      console.log(JSON.stringify(evidence));return;
    }
    phase='models-values';
    checks.push(...await probeModelsValues({command,evaluate,until,id,fixture:async command=>{
      server.stdin.write(JSON.stringify({command})+'\n');return JSON.parse((await lines.next()).value);
    }}));
    const benchmarkImage=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},id);
    await fs.writeFile(output.replace(/\.json$/,'')+'-benchmark.png',Buffer.from(benchmarkImage.data,'base64'));
    const referenceChoice = await evaluate(id,`JSON.stringify(current.models)`);
    for (const [key, code, windowsVirtualKeyCode, expected] of [['Enter','Enter',13,'descending'],[' ','Space',32,'ascending']]) {
      await evaluate(id,`document.querySelector('[data-benchmark-control="3"]').focus()`);
      await command('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode,text:key==='Enter'?'\r':' '},id);
      await command('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode},id);
      assert.equal(await evaluate(id,`document.querySelector('.benchmark-table th:nth-child(4)').getAttribute('aria-sort')`),expected);
      assert.equal(await evaluate(id,`JSON.stringify(current.models)`),referenceChoice);
    }
    // Sorting deliberately suppresses help until a real focus/hover exit.
    await evaluate(id,`document.activeElement.blur()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:2,y:2},id);
    const labelPoint = await evaluate(id,`(()=>{const n=document.querySelector('[data-benchmark-control="3"] .help-label');n.scrollIntoView({block:'center'});const r=n.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...labelPoint},id);
    await until(id,`document.querySelector('#context-help')?.textContent.includes('Cost per attempt relative') && !document.querySelector('#context-help').hidden`);
    assert.equal(await evaluate(id,`document.querySelector('#context-help').textContent.length<120`),true);
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},id);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},id);
    await until(id,`document.querySelector('#context-help').hidden`);
    assert.equal((await mode('status')).fetches,1);
    checks.push('Benchmark native Enter/Space sorts independently, intrinsic concise help and Escape; no price refresh');
    if (baseline === '--baseline') {
      evidence = await evaluate(id, `(()=>{const sample=selector=>{const node=document.querySelector(selector),s=getComputedStyle(node),r=node.getBoundingClientRect();return {font:s.fontFamily,size:s.fontSize,height:r.height,padding:s.padding};};return {outcome:'OBSERVED',button:sample('[data-model-control="refresh"]'),date:sample('.model-tools span'),tier:sample('.model-relative'),ui:getComputedStyle(document.body).fontFamily};})()`);
      console.log(JSON.stringify(evidence)); return;
    }
    phase='toolbar'; layouts.push(...await probeToolbar({command,evaluate,id}));
    phase='price-refresh';
    await evaluate(id,`document.querySelector('[data-model-control="all"]').click();document.querySelector('[data-model-control="latest"]').click();
      document.querySelector('[data-model-control="column-1"]').dispatchEvent(new MouseEvent('click',{shiftKey:true}));
      ReportView.setUnit('usd',document.getElementById('result'));window.oldTable=document.querySelector('.overview-model-table');`);
     const choice=await evaluate(id,`JSON.stringify(current.models)`);
     await mode('hold');
    await evaluate(id,`document.querySelector('[data-model-control="refresh"]').click();document.querySelector('[data-model-control="refresh"]').click()`);
    assert.equal(await evaluate(id,`current.loading && document.querySelector('[data-model-control="refresh"]').disabled && document.querySelector('.model-price-controls').textContent.includes('Refreshing…') && oldTable===document.querySelector('.overview-model-table')`),true);
    // Two simultaneous tab actions share one queued/running refresh, not the Normal job.
    const same=await evaluate(id,`(async()=>{const [a,b]=await Promise.all([api('/api/models/refresh',{}),api('/api/models/refresh',{})]);return a.id===b.id&&a.id===current.active;})()`);
     assert.equal(same,true);
     await mode('release');
    await until(id,`!current.loading`);
    const unchanged=await read(); assert.ok(unchanged.date>initial.date);
    assert.deepEqual(unchanged.models,initial.models); assert.equal((await mode('status')).fetches,2);
    assert.equal(await evaluate(id,`JSON.stringify(current.models)`),choice);
    checks.push('Warm-cache synthetic upstream fetch; unchanged document advances factual observation only; disabled double-click and concurrent controlled fixture actions');
    await mode('changed');
    await evaluate(id,`document.querySelector('[data-model-control="refresh"]').click()`);
    await until(id,`!current.loading`);
    const changed=await read(); assert.ok(changed.date>unchanged.date);
    assert.notDeepEqual(changed.models,unchanged.models); assert.deepEqual(changed.sample,unchanged.sample);
    assert.ok(changed.models.find(row=>row.model==='GPT-Test').price_help.includes('Input: $10'));
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:1,y:1},id);
    await key(id);
    await evaluate(id,`[...document.querySelectorAll('.overview-model-table tbody tr')].find(row=>row.cells[1].textContent==='GPT-Test').querySelector('.model-relative').focus()`);
    await until(id,`document.querySelector('#context-help')?.matches(':popover-open') && document.querySelector('#context-help').textContent.includes('Input: $10')`);
    assert.equal(await evaluate(id,`document.querySelector('#context-help').textContent.endsWith('Output: $40') &&
      !document.querySelector('#context-help').textContent.includes('Token Mix')`),true);
    await evaluate(id,`(${modelName('GPT-Test')}).focus()`);
    await until(id,`document.querySelector('#context-help')?.matches(':popover-open') &&
      document.querySelector('#context-help').textContent === 'GitHub category: Lightweight'`);
    assert.equal(await evaluate(id,`JSON.stringify(current.models)`),choice);
    assert.equal(await evaluate(id,`document.querySelector('.overview-model-table th:nth-child(2)').textContent.includes('↑ 2')`),true);
    checks.push('Changed source rebuilds coherent Models rows and fixed relative ratios without synthetic usage; filters, multi-sort and USD retained');
    for (const failure of ['offline','invalid']) {
      await mode(failure);
      await evaluate(id,`window.retainedTable=document.querySelector('.overview-model-table');document.querySelector('[data-model-control="refresh"]').click()`);
      await until(id,`!current.loading`);
      assert.equal(await evaluate(id,`retainedTable===document.querySelector('.overview-model-table')`),true, `${failure}: retain the pricing table`);
      assert.deepEqual(await read(),changed);
      assert.equal(await evaluate(id,`document.querySelector('.model-price-controls [role="status"]').textContent === 'Could not load. Try again.' &&
        !document.querySelector('[data-model-control="refresh"]').disabled`),true, `${failure}: announce the explicit failure and permit retry`);
    }
    await mode('changed'); await evaluate(id,`document.querySelector('[data-model-control="refresh"]').click()`);await until(id,`!current.loading`);
    checks.push('Offline/invalid upstream retains exact table/timestamp with concise failure and successful retry');
    await command('Page.bringToFront',{},id);
    for (const [name,code,virtualKey] of [['Enter','Enter',13],[' ','Space',32]]) {
      const before=(await mode('status')).fetches;
      await evaluate(id,`document.querySelector('[data-model-control="refresh"]').focus()`);
      const text=name==='Enter'?'\r':' ';
      await command('Input.dispatchKeyEvent',{type:'keyDown',key:name,code,windowsVirtualKeyCode:virtualKey,text,unmodifiedText:text},id);
      await command('Input.dispatchKeyEvent',{type:'keyUp',key:name,code,windowsVirtualKeyCode:virtualKey},id);
      await until(id,`current.loading`); await until(id,`!current.loading`);
      assert.equal((await mode('status')).fetches,before+1);
      assert.equal(await evaluate(id,`document.activeElement?.dataset.modelControl==='refresh'`),true);
    }
    checks.push('Native Enter/Space activate one refresh each and retain focus after result replacement');
    await evaluate(id,`document.querySelector('[data-model-control="refresh"]').focus();document.querySelector('[data-model-control="refresh"]').click()`);
    await until(id,`current.loading`);
    await evaluate(id,`document.querySelector('[data-model-control="all"]').focus()`);
    await until(id,`!current.loading`);
    assert.equal(await evaluate(id,`document.activeElement?.dataset.modelControl==='all'`),true);
    checks.push('Refresh completion preserves a filter deliberately focused during the request, without focus theft');
    phase='price-touch';
    await command('Emulation.setTouchEmulationEnabled',{enabled:true},id);
    const touch=async selector=>{
      const point=await evaluate(id,`(()=>{const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
      await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]},id);
      await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},id);
    };
    const beforeTouch=(await mode('status')).fetches;
    await touch('[data-model-control="all"]');await touch('[data-model-control="all"]');
    assert.equal(await evaluate(id,`JSON.stringify(current.models)`),choice);
    assert.equal((await mode('status')).fetches,beforeTouch);
    await touch('[data-model-control="refresh"]');await until(id,`current.loading`);await until(id,`!current.loading`);
    assert.equal((await mode('status')).fetches,beforeTouch+1);
    await command('Emulation.setTouchEmulationEnabled',{enabled:false},id);
    checks.push('Native touch toggles the filter without acquisition and activates exactly one explicit price refresh');
    for (const width of [360,1280]) for (const theme of ['classic','light','dark']) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},id);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},id);
      await evaluate(id,`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}'`);
      await command('Page.bringToFront',{},id);
      await key(id);
      for (let column=0;column<4;column++) {
        await evaluate(id,`document.activeElement?.blur();document.querySelector('[data-model-control="column-${column}"]').focus()`);
        await until(id,`document.querySelector('#context-help')?.matches(':popover-open')`);
        const text=await evaluate(id,`document.querySelector('#context-help').textContent`);
        assert.ok(!text.includes('Hold Shift')); assert.ok(text.length>20);
        if(column===2) assert.equal(text,'Reference-price ratio to the cheapest comparable model (1.0x); not task performance.\n\nToken Mix is the percentage split of Input, Cached input, Cache write and Output tokens. This comparison uses a fixed statistical average: Input 3%, Cached input 95%, Cache write 1%, Output 1%.');
      }
       const layout=await evaluate(id,`(()=>{const r=document.querySelector('#context-help').getBoundingClientRect(),b=document.querySelector('.model-price-controls button').getBoundingClientRect(),t=document.querySelector('.model-price-controls').children[1].getBoundingClientRect();return {overflow:document.documentElement.scrollWidth>innerWidth,helpFits:r.left>=0&&r.top>=0&&r.right<=innerWidth&&r.bottom<=innerHeight,buttonFirst:b.top<=t.top};})()`);
      assert.equal(layout.overflow,false);assert.equal(layout.helpFits,true);assert.equal(layout.buttonFirst,true);
      layouts.push({width,theme,...layout});
      const image=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},id);
      await fs.writeFile(output.replace(/\.json$/,'')+`-${width}-${theme}.png`,Buffer.from(image.data,'base64'));
    }
    assert.equal(await evaluate(id,`!document.querySelector('details.overview-explanations') && !document.getElementById('result').textContent.includes('More information')`),true);
    await evaluate(id,`location.hash='#/watch'`);await until(id,`current.section==='watch'`);
    const mini=await evaluate(id,`(()=>{const s=getComputedStyle(document.querySelector('#mini-watch-toggle'));return {font:s.fontFamily,minHeight:s.minHeight};})()`);
    const toolbar=layouts.find(n=>n.width===1280&&n.theme==='classic'&&n.fontScale===1&&n.state==='normal');
    assert.equal(mini.font,toolbar.button.font);
    assert.ok(parseFloat(mini.minHeight) >= parseFloat(toolbar.button.minHeight), 'Watch header owns its larger toggle target');
    await evaluate(id,`location.hash='#/models'`);await until(id,`current.section==='models' && !!document.querySelector('.overview-model-table')`);
    assert.equal(await evaluate(id,`JSON.stringify(current.models)`),choice);
    assert.deepEqual(errors,[]);
    checks.push('Four semantic focus tooltips, toolbar wrapping and no document overflow in Classic/Web light/dark at 360/1280; navigation retains preferences');
    checks.push('240 toolbar cases: 360/800/1280/1366/1920, Classic/Web light/dark, 100/125/150/200% text scaling, normal/refreshing/long-error/unavailable states; separate coarse-pointer target check; shared Watch toggle font with independent target sizing');
    phase='models-parity'; layouts.push(...await probeModelsParity({command,evaluate,id,output}));
    checks.push('36 same-page computed table/heading/control parity cases at 360/768/1366/1920, Classic/Web light/dark and 100/125/150% text; full-page screenshots, one-column source list, vertical wheel and native touch input');
    evidence={outcome:'PASS',browser:(await command('Browser.getVersion')).product,checks,layouts,
      limitations:['Canonical Python report pipeline with synthetic upstream/source and controlled in-memory jobs. This does not prove production process startup/lifecycle or concurrency; those have separate backend tests.',
        'Production spawn, cancellation and actual source reads require the separate backend/real-installation checks, not this controlled browser fixture.',
        'Headless Chromium, not physical desktop/screen-reader or other-engine acceptance.']};
  } catch (error) {
    evidence={outcome:'FAIL',phase,reason:error.message,checks,layouts};
    throw error;
  } finally {
    clearTimeout(deadline);await fs.writeFile(output,JSON.stringify(evidence,null,2));
    await command('Browser.close').catch(()=>{});if(child.exitCode===null)child.kill();
    server.stdin.end();if(server.exitCode===null)await new Promise(resolve=>server.once('exit',resolve));
    await fs.rm(profile,{recursive:true,force:true,maxRetries:3});await fs.rm(config,{recursive:true,force:true});
  }
  console.log(JSON.stringify(evidence));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
