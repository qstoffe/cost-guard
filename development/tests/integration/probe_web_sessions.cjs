// Hidden fresh-profile Chromium: shipped app/HTTP/auth plus synthetic session truth.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output, mode] = process.argv.slice(2);
async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output));
  const directory = path.dirname(output);
  const profile = await fs.mkdtemp(path.join(directory, 'sessions-browser-'));
  const config = await fs.mkdtemp(path.join(directory, 'sessions-config-'));
  const python = process.env.COST_GUARD_TEST_PYTHON || 'py';
   const server = spawn(python, [...(process.env.COST_GUARD_TEST_PYTHON ? [] : ['-3']),
      mode === '--warm-sorts' ? 'development/tests/integration/serve_web_warm_sorts.py' :
      mode === '--cold-period' ? 'development/tests/integration/serve_web_cold_period.py' :
       ['--fast-arrivals','--detail-updates'].includes(mode) ? 'development/tests/integration/serve_web_arrivals.py' : 'development/tests/integration/serve_web_sessions.py',
    ['--catalog-real-churn','--catalog-real-recovery'].includes(mode) ? '--real-source' : config],
    {windowsHide:true, stdio:['pipe','pipe','pipe']});
  const serverExit = new Promise(resolve => server.once('exit',resolve));
  let serverError = ''; server.stderr.on('data', bytes => serverError += bytes.toString());
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const fixture = async command => {server.stdin.write(JSON.stringify({command})+'\n'); return JSON.parse((await lines.next()).value);};
   let extensionArgs = ['--disable-extensions'];
           if (mode === '--model-details') {
     const extension = path.join(profile, 'zoom-extension');
     await fs.mkdir(extension);
     await fs.writeFile(path.join(extension, 'manifest.json'), JSON.stringify({manifest_version:3,
       name:'Owned synthetic model details zoom',version:'1.0',permissions:['tabs'],background:{service_worker:'worker.js'}}));
     await fs.writeFile(path.join(extension, 'worker.js'), 'chrome.runtime.onInstalled.addListener(() => {});');
     extensionArgs = ['--disable-extensions-except='+extension, '--load-extension='+extension];
   }
   const child = spawn(browser, ['--headless=new', ...(process.env.COST_GUARD_CI_BROWSER==='1'?['--no-sandbox']:[]),
    '--screen-info={1920x1080}',
     '--no-first-run', '--no-default-browser-check', ...extensionArgs,
    '--disable-background-networking', '--remote-debugging-pipe', '--user-data-dir='+profile, 'about:blank'],
    {windowsHide:true, stdio:['ignore','ignore','ignore','pipe','pipe']});
  const browserExit = new Promise(resolve => child.once('exit',resolve));
  let sequence=0, buffer='', errors=[];
  const pending=new Map();
  child.stdio[4].on('data', bytes => {
    buffer+=bytes.toString(); let index;
    while ((index=buffer.indexOf('\0'))>=0) {
      const value=JSON.parse(buffer.slice(0,index)); buffer=buffer.slice(index+1);
      if (value.id) {
        const entry=pending.get(value.id); pending.delete(value.id);
        if (entry) { clearTimeout(entry.timer); value.error ? entry.reject(new Error(JSON.stringify(value.error))) : entry.resolve(value.result); }
      } else if (value.method==='Runtime.exceptionThrown') errors.push(value.params.exceptionDetails.text);
    }
  });
  const command=(method, params={}, sessionId) => new Promise((resolve,reject) => {
    const id=++sequence, timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout: '+method));},15000);
    pending.set(id,{resolve,reject,timer}); child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');
  });
  const deadline=setTimeout(()=>{child.kill();server.kill();},180000);
  const checks=[], layouts=[];
  let evidence={outcome:'FAIL'}, lastExpression='';
  try {
    const line=await lines.next();
    if (line.done) throw new Error('Fixture failed: '+serverError);
    const launch=JSON.parse(line.value);
     const version=await command('Browser.getVersion');
     evidence.browser=version.product;
    const {targetId}=await command('Target.createTarget',{url:'about:blank'});
    const {sessionId}=await command('Target.attachToTarget',{targetId,flatten:true});
     await command('Page.enable',{},sessionId); await command('Runtime.enable',{},sessionId);
     await command('Page.bringToFront',{},sessionId);
     const evaluate=async (expression, userGesture=false) => {
      lastExpression=expression;
       const value=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true,userGesture},sessionId).catch(async error=>{
        await command('Runtime.terminateExecution',{},sessionId).catch(()=>{});
        const state=await command('Runtime.evaluate',{expression:'JSON.stringify(window.detailProbe)',returnByValue:true},sessionId).catch(()=>({}));
        evidence.debug=state; throw new Error(error.message+': '+expression.slice(0,160)+'; '+JSON.stringify(state));
      });
      if (value.exceptionDetails) throw new Error(JSON.stringify(value.exceptionDetails));
      return value.result.value;
    };
     const until=async (expression, timeoutMs=30000) => {
       const end=Date.now()+timeoutMs;
      while (Date.now()<end) {if(await evaluate(expression))return;await new Promise(resolve=>setTimeout(resolve,50));}
       const state=await evaluate(mode==='--live-only' ?
          `JSON.stringify({focus:document.activeElement?.outerHTML,help:document.querySelector('#context-help')?.textContent,
            row:document.querySelector('tr[data-id=root-0121]')?.value})` :
          mode==='--catalog-idle-only' ?
         `JSON.stringify({hidden:document.hidden,section:current?.section,offset:current?.catalog?.offset,
           applied:current?.catalog?.data?.offset,total:current?.catalog?.data?.total,busy:current?.catalog?.busy,
           recovering:current?.catalog?.recovering,operation:current?.catalog?.operation,
           reply:current?.catalog?.idleReply?.progress,requests:window.idleRequests,expiries:window.idleExpiries})` :
         mode==='--calm-ui' ?
        `JSON.stringify({section:current?.section,hidden:document.hidden,detailTotal:current?.detail?.data?.total,detailBusy:current?.detail?.busy})` :
        'document.body.innerText');
      lastExpression=expression;
      throw new Error('Condition not reached: '+expression+'; '+state);
     };
     await command('Page.addScriptToEvaluateOnNewDocument',{source:`window.reportKinds=[];
       const request=fetch;window.fetch=(url,options)=>{if(url==='/api/reports')reportKinds.push(JSON.parse(options.body).kind);return request(url,options);};`},sessionId);
      await command('Page.navigate',{url:launch.url},sessionId);
           await until('typeof csrf !== "undefined" && csrf && hostState.kind === "connected"');
             if (mode === '--cold-period') {
               const details = await require('../fixtures/sessions_cold_period_browser.cjs')({evaluate, until, fixture});
               assert.deepEqual(errors, []);
               evidence = {outcome:'PASS', browser:version.product, ...details, inference_calls:0,
                 personal_profile:false, desktop_effects:false};
               console.log(JSON.stringify(evidence)); return;
             }
             if (mode === '--warm-sorts') {
               const details=await require('../fixtures/sessions_warm_sorts_browser.cjs')({evaluate,until,fixture,
                 command:(method,params)=>command(method,params,sessionId)});
               assert.deepEqual(errors,[]);
               evidence={outcome:'PASS',browser:version.product,...details,inference_calls:0,
                 personal_profile:false,desktop_effects:false};
               console.log(JSON.stringify(evidence));return;
             }
             if (mode === '--fast-arrivals') {
              const details=await require('../fixtures/sessions_arrivals_browser.cjs')({evaluate,until,fixture});
              assert.deepEqual(errors,[]);
              evidence={outcome:'PASS',browser:version.product,...details,inference_calls:0,
                personal_profile:false,desktop_effects:false};
               console.log(JSON.stringify(evidence));return;
             }
             if (mode === '--detail-updates') {
               const details=await require('../fixtures/session_updates_browser.cjs')({evaluate,until,fixture,targetId,
                 command:(method,params)=>command(method,params,sessionId)});
               assert.deepEqual(errors,[]);
               evidence={outcome:'PASS',browser:version.product,...details,inference_calls:0,
                 personal_profile:false,desktop_effects:false};
               console.log(JSON.stringify(evidence));return;
             }
            if (mode === '--sessions-return') {
             const newTab = async hash => {
               const {targetId:other} = await command('Target.createTarget',{url:new URL(launch.url).origin+'/'+hash});
               const {sessionId:otherSession} = await command('Target.attachToTarget',{targetId:other,flatten:true});
               try {
                 for (let attempt=0;attempt<200;attempt++) {
                   const value = await command('Runtime.evaluate',{expression:
                     'typeof current !== "undefined" && current?.detail?.back.getAttribute("href")',returnByValue:true},otherSession);
                   if (value.result?.value) return value.result.value;
                   await new Promise(resolve=>setTimeout(resolve,50));
                 }
                 throw new Error('new-tab detail timeout');
               } finally { await command('Target.closeTarget',{targetId:other}); }
             };
             checks.push(...await require('../fixtures/sessions_return_browser.cjs')({evaluate,until,fixture,newTab,
               command:(method,params)=>command(method,params,sessionId)}));
             assert.deepEqual(errors, []);
             evidence = {outcome:'PASS',browser:version.product,checks,inference_calls:0,
               personal_profile:false,desktop_effects:false};
             console.log(JSON.stringify(evidence)); return;
           }
           if (mode === '--model-details') {
            const targets = await command('Target.getTargets');
            const worker = targets.targetInfos.find(target=>target.type==='service_worker' && target.url.endsWith('/worker.js'));
            assert.ok(worker,'Owned zoom extension service worker must exist');
            const {sessionId:workerSession} = await command('Target.attachToTarget',{targetId:worker.targetId,flatten:true});
            const zoom = async factor => {
              const result = await command('Runtime.evaluate',{expression:`(async()=>{
                const tabs=await chrome.tabs.query({});
                const tab=tabs.find(tab=>tab.url?.startsWith(${JSON.stringify(new URL(launch.url).origin)}));
                if(!tab)throw new Error('owned_zoom_tab_missing');
                await chrome.tabs.setZoom(tab.id,${factor});return chrome.tabs.getZoom(tab.id);
              })()`,awaitPromise:true,returnByValue:true},workerSession);
              assert.equal(result.exceptionDetails,undefined,JSON.stringify(result.exceptionDetails));
              assert.equal(result.result.value,factor);
            };
            const details = await require('../fixtures/model_details_browser.cjs')({evaluate,until,fixture,zoom,
              command:(method,params)=>command(method,params,sessionId)});
            checks.push(...details.checks); layouts.push(...details.layouts);
            assert.deepEqual(errors,[]);
            evidence={outcome:'PASS',browser:version.product,checks,layouts,inference_calls:0,
              personal_profile:false,desktop_effects:false};
            console.log(JSON.stringify(evidence));return;
          }
           if (mode === '--calm-ui') {
            assert.equal(await evaluate('document.hidden'),false,'foreground recovery case requires a visible headless tab');
            await require('../fixtures/calm_ui_browser.cjs')({evaluate, until, fixture, checks, layouts,
              command:(method, params) => command(method, params, sessionId)});
            assert.deepEqual(errors, []);
            evidence = {outcome:'PASS',browser:version.product,checks,layouts,inference_calls:0,
              personal_profile:false,desktop_effects:false};
            console.log(JSON.stringify(evidence)); return;
          }
          if (mode === '--prompt-activity-parity') {
           const details = await require('../fixtures/catalog_activity_browser.cjs')({evaluate, until, fixture,
             command:(method, params) => command(method, params, sessionId)});
           checks.push(...details.checks);
           assert.deepEqual(errors, []);
           evidence = {outcome:'PASS',browser:version.product,checks,measurements:details.measurements,
             inference_calls:0,personal_profile:false,desktop_effects:false};
           console.log(JSON.stringify(evidence)); return;
         }
           if (mode === '--catalog-real-churn' || mode === '--catalog-real-recovery') {
            const probe = require('../fixtures/sessions_source_browser.cjs');
            const details = await (mode === '--catalog-real-recovery' ? probe.recovery : probe)({evaluate, until,
              command:(method, params) => command(method, params, sessionId)});
           checks.push(details);
           assert.deepEqual(errors, []);
           evidence = {outcome:'OBSERVED',browser:version.product,checks,layouts,inference_calls:0,
             personal_profile:false,desktop_effects:false};
            console.log(JSON.stringify(evidence)); return;
          }
          if (mode === '--running-first') {
            const details = await require('../fixtures/sessions_running_browser.cjs')({evaluate, until, fixture,
              command:(method, params) => command(method, params, sessionId)});
            assert.deepEqual(errors, []);
            evidence = {outcome:'PASS',browser:version.product,...details,inference_calls:0,
              personal_profile:false,desktop_effects:false};
            console.log(JSON.stringify(evidence)); return;
          }
             if (mode === '--detail-quota') {
               const details = await require('../fixtures/session_quota_browser.cjs')({evaluate, until, fixture,
                 browser,targetId,origin:new URL(launch.url).origin,
                 command:(method, params) => command(method, params, sessionId)});
               checks.push(...details.checks); layouts.push(...details.layouts);
               assert.deepEqual(errors, []);
               evidence = {outcome:'PASS',browser:version.product,checks,layouts,measurements:details.measurements,
                 inference_calls:0,personal_profile:false,desktop_effects:false};
               console.log(JSON.stringify(evidence)); return;
             }
             if (mode === '--detail-values') {
              const details = await require('../fixtures/session_values_browser.cjs')({evaluate, until, fixture,
                command:(method, params) => command(method, params, sessionId)});
              checks.push(...details.checks); layouts.push(...details.layouts);
              assert.deepEqual(errors, []);
              evidence = {outcome:'PASS',browser:version.product,checks,layouts,inference_calls:0,
                personal_profile:false,desktop_effects:false};
              console.log(JSON.stringify(evidence)); return;
            }
            if (mode === '--detail-activity') {
             const details = await require('../fixtures/session_activity_browser.cjs')({evaluate, until, fixture,
               command:(method, params) => command(method, params, sessionId)});
             checks.push(...details.checks); layouts.push(...details.layouts);
             assert.deepEqual(errors, []);
             evidence = {outcome:'PASS',browser:version.product,checks,layouts,inference_calls:0,
               personal_profile:false,desktop_effects:false};
             console.log(JSON.stringify(evidence)); return;
           }
           if (mode === '--quick-aborts') {
             await require('../fixtures/quick_aborts_browser.cjs')({evaluate,until,fixture,checks,layouts,
               command:(method,params)=>command(method,params,sessionId)});
             assert.deepEqual(errors,[]);
             evidence={outcome:'PASS',browser:version.product,checks,layouts,inference_calls:0,
               personal_profile:false,desktop_effects:false};
             console.log(JSON.stringify(evidence));return;
           }
           if (mode === '--detail-first-load') {
             const details = await require('../fixtures/session_loading_browser.cjs').firstLoad({evaluate,until,fixture});
             checks.push(...details.checks);
             assert.deepEqual(errors, []);
             evidence = {outcome:'PASS',browser:version.product,checks,measurements:details.measurements,
               inference_calls:0,personal_profile:false,desktop_effects:false};
             console.log(JSON.stringify(evidence));return;
           }
           if (mode === '--detail-liveness') {
            const details = await require('../fixtures/session_liveness_browser.cjs')({evaluate, until, fixture,
              command:(method, params) => command(method, params, sessionId)});
            checks.push(...details.checks); layouts.push(...details.layouts);
            assert.deepEqual(errors, []);
            evidence = {outcome:'PASS',browser:version.product,checks,layouts,measurements:details.measurements,
              inference_calls:0,personal_profile:false,desktop_effects:false};
            console.log(JSON.stringify({outcome:evidence.outcome,checks,measurements:details.measurements})); return;
          }
          if (mode === '--catalog-idle-only') {
            const details = await require('../fixtures/sessions_idle_browser.cjs')({evaluate, until, fixture, targetId,
              command:(method, params) => command(method, params, sessionId), browserCommand:command});
            checks.push(...details.checks);
            assert.deepEqual(errors, []);
            evidence = {outcome:'PASS',browser:version.product,...details,inference_calls:0,
              personal_profile:false,desktop_effects:false};
            console.log(JSON.stringify(evidence)); return;
          }
          if (['--periods-only', '--catalog-navigation-only', '--calendar-cache-only', '--catalog-banner-only', '--catalog-cohort-only'].includes(mode)) {
           const details = await require(mode === '--periods-only' ? '../fixtures/sessions_periods_browser.cjs' :
             mode === '--catalog-cohort-only' ? '../fixtures/sessions_cohort_browser.cjs' :
            mode === '--catalog-banner-only' ? '../fixtures/sessions_banner_browser.cjs' :
            mode === '--calendar-cache-only' ? '../fixtures/sessions_calendar_browser.cjs' : '../fixtures/sessions_navigation_browser.cjs')({evaluate, until, fixture,
            command:(method, params) => command(method, params, sessionId)});
          checks.push(...details.checks); layouts.push(...details.layouts);
          assert.deepEqual(errors, []);
          evidence = {outcome:'PASS',browser:version.product,checks,layouts,inference_calls:0,
            personal_profile:false,desktop_effects:false};
          console.log(JSON.stringify({outcome:evidence.outcome,checks})); return;
        }
       if (mode === '--loading-only' || mode === '--loading-zoom-only') {
         const probe = require('../fixtures/session_loading_browser.cjs');
         const details = await (mode === '--loading-zoom-only' ? probe.zoom : probe)({evaluate, until,
           browser, targetId, origin:new URL(launch.url).origin,
           command:(method, params) => command(method, params, sessionId)});
         checks.push(...details.checks); layouts.push(...details.layouts);
         assert.deepEqual(errors, []);
         evidence = {outcome:'PASS',browser:version.product,checks,layouts,inference_calls:0,
           personal_profile:false,desktop_effects:false};
         console.log(JSON.stringify({outcome:evidence.outcome,checks})); return;
       }
        if (mode === '--live-only' || mode === '--models-only') {
         const details = await require(mode === '--models-only' ? '../fixtures/sessions_models_browser.cjs' :
           '../fixtures/sessions_live_browser.cjs')({evaluate, until, fixture,
          command:(method, params) => command(method, params, sessionId)});
        checks.push(...details.checks); layouts.push(...details.layouts);
        assert.deepEqual(errors, []);
        evidence = {outcome:'PASS',browser:version.product,checks,layouts,inference_calls:0,
          personal_profile:false,desktop_effects:false};
        console.log(JSON.stringify({outcome:evidence.outcome,checks}));
         return;
       }
       if (mode === '--dates-only') {
         await evaluate(`location.hash='#/sessions'`);
         await until('current.catalog?.data?.view.session_usage.length===25');
         const original = await evaluate(`({raw:current.catalog.data.view.session_usage[0].last_activity_ms,
           zone:current.catalog.data.view.timezone_id,text:current.catalog.body.rows[0].cells[0].textContent})`);
         assert.equal(original.zone,'UTC');
         assert.equal(original.text,new Date(original.raw).toISOString().slice(0,16).replace('T',' '));
         for (const locale of ['en-US','sv-SE']) for (const timezoneId of ['America/New_York','Asia/Tokyo']) {
           await command('Emulation.setLocaleOverride',{locale},sessionId);
           await command('Emulation.setTimezoneOverride',{timezoneId},sessionId);
           await evaluate('current.catalog.rows(current.catalog.data.view.session_usage)');
           assert.equal(await evaluate('current.catalog.body.rows[0].cells[0].textContent'),original.text);
           assert.deepEqual(await evaluate(`['2026-03-29T00:30Z','2026-03-29T01:30Z','2026-10-25T00:30Z','2026-10-25T01:30Z']
             .map(value=>ReportView.timestamp(Date.parse(value),'Europe/Stockholm'))`),
             ['2026-03-29 01:30','2026-03-29 03:30','2026-10-25 02:30','2026-10-25 02:30']);
         }
         await evaluate(`location.hash='#/sessions/root-0000'`);
         await until('current.detail?.body.rows.length===1001');
         const values = await evaluate(`(()=>{const texts=[];for(const node of current.detail.body.querySelectorAll('.session-prompt-label .help-value')){
           node.focus();ContextHelp.refresh(node);const help=document.getElementById('context-help');if(help?.matches(':popover-open'))texts.push(help.textContent);}
           return {body:current.detail.root.textContent,help:texts};})()`);
         const forbidden=/\b\d{1,2}\/\d{1,2}\/\d{4}\b|\b\d{1,2}:\d{2}(?::\d{2})?\s*[AP]M\b/;
         assert.doesNotMatch(values.body,forbidden);
         values.help.forEach(text=>assert.doesNotMatch(text,forbidden));
         assert.ok(values.help.some(text=>/1970-01-\d{2} \d{2}:\d{2}/.test(text)));
         checks.push('real Sessions 25-row HTTP/DTO/DOM configured-UTC activity unchanged by two locales/two browser zones; Stockholm spring/fall DST');
         checks.push('complete 1001-row session detail and all clock help searched for 12-hour/date-order leaks');
         assert.deepEqual(errors,[]);
         evidence={outcome:'PASS',browser:version.product,checks,layouts,inference_calls:0,
           personal_profile:false,desktop_effects:false};
         console.log(JSON.stringify(evidence));return;
       }
     if (mode !== '--catalog-detail-only') {
     await until('current?.result && !current.loading');
     const retiredHashes=['#/reports','#/reports?date=2026-11-05','#/reports?date=2026-10-01:2026-11-05',
       '#/reports?date=2026-02-30','#/reports?date=%ZZ&sort=ccost&offset=50'];
     const captures=await evaluate('reportKinds.length');
     for(const hash of retiredHashes) {
       await command('Page.navigate',{url:launch.url.split('#')[0]+hash},sessionId);
        await until('location.hash.startsWith("#/sessions?period=today&") && current?.catalog?.data?.total === 120');
       assert.equal(await evaluate('current.catalog.data.sort'),'activity');
       assert.equal(await evaluate('current.catalog.data.direction'),-1);
       assert.equal(await evaluate('document.querySelectorAll("input[type=date], #scope-controls form").length'),0);
       assert.doesNotMatch(await evaluate('document.querySelector("#result").textContent'),/Capture date report|Snapshot:|Inclusive local range/);
       assert.equal(await evaluate('reportKinds.length'),captures);
       assert.equal(await evaluate('document.querySelector("nav a[aria-current=page]").getAttribute("href")'),'#/sessions');
     }
     await evaluate("history.replaceState(null,'','/#/reports?date=invalid')");
     await command('Page.reload',{},sessionId);
      await until('location.hash.startsWith("#/sessions?period=today&") && current?.catalog?.data?.total === 120');
     assert.deepEqual(await evaluate('reportKinds'),[],'cold legacy reload never starts even a Normal/date report');
     for(const width of [1920,360]) {
       await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},sessionId);
       assert.deepEqual(await evaluate('[...document.querySelectorAll("nav a")].map(node=>node.textContent)'),
        ['Models','Watch','Sessions','Accounts','Token Mix','AI Stats','Comparisons','Settings']);
       assert.equal(await evaluate(`[...document.querySelectorAll('a')].filter(node=>node.getAttribute('href')?.startsWith('#/reports')).length`),0);
       assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'),true);
     }
     await evaluate("location.hash='#/settings'"); await until('current.section === "settings"');
      await evaluate("location.hash='#/reports?date=invalid'"); await until('location.hash.startsWith("#/sessions?period=today&")');
     await evaluate("location.hash='#/token-mix'"); await until('current.section === "token-mix"');
      await evaluate('history.back()'); await until('location.hash.startsWith("#/sessions?period=today&") && current.catalog');
     await evaluate('history.back()'); await until('location.hash === "#/settings"');
      await evaluate('history.forward()'); await until('location.hash.startsWith("#/sessions?period=today&") && current.catalog');
      assert.equal(await evaluate('reportKinds.includes("date")'),false);
     checks.push('retired-hashes-valid-invalid-reload-back-forward-no-jobs-or-date-filter-wide-narrow-nav');
      for(const section of ['token-mix']) {
       const before=await evaluate('reportKinds.length');
       await evaluate(`location.hash='#/${section}'`); await until(`current.section === '${section}'`);
        await until('current.result && !current.loading');
        assert.equal(await evaluate('reportKinds.at(-1)'),section);
        assert.equal(await evaluate('document.querySelector("#refresh").hidden'),true,'automatic history has no manual Refresh gate');
        assert.ok(await evaluate('reportKinds.length')>=before);
     }
     assert.equal(await evaluate('reportKinds.includes("date")'),false);
        checks.push('automatic Token Mix cached route returns without a date report; AI Stats lifecycle has its own probe');
     }
     await evaluate("location.hash='#/sessions'");
    await until('current?.catalog?.data?.total === 120');
    assert.deepEqual(await evaluate('[...document.querySelectorAll("#result th")].map(node=>node.textContent.replace(/ [↑↓↕]$/, ""))'),
       ['Last activity','Session name','Model','CCost','Prompts','Duration','Ctx']);
    assert.equal(await evaluate('document.querySelectorAll("#result tbody tr").length'),25);
    assert.equal(await evaluate('getComputedStyle(document.querySelector(".toolbar")).display'),'none');
    assert.equal(await evaluate('document.querySelector("#scope-controls").textContent'),'');
     checks.push('seven-column-catalog-with-period-selector');
    await evaluate('document.querySelectorAll("#result th button")[4].click()');
    await until('current.catalog.data.sort === "prompts" && !current.catalog.data.pending_sort');
    assert.equal(await evaluate('current.catalog.data.total'),120);
    checks.push('cold-to-global-metric-sort-ready');
    await evaluate("location.hash='#/sessions'"); await until('current.catalog.data.sort === "activity"');
     const older=await evaluate('current.catalog.next.destination');
    await evaluate(`location.hash=${JSON.stringify(older)}`);
    await until('current.catalog.data.offset === 25');
    const membership=await evaluate('[...document.querySelectorAll("#result tbody tr")].map(row=>row.dataset.id)');
    const before=Date.now(); await fixture('arrive');
    await evaluate('current.catalog.load()');
    assert.deepEqual(await evaluate('[...document.querySelectorAll("#result tbody tr")].map(row=>row.dataset.id)'),membership);
    await evaluate("location.hash='#/sessions'"); await until('current.catalog.data.total === 121');
    const latency=Date.now()-before; assert.ok(latency<=30000);
     assert.equal(await evaluate('document.querySelector("#result tbody tr").dataset.id'),'root-0000');
     assert.equal(await evaluate('document.querySelectorAll("#result tbody tr")[1].dataset.id'),'root-0120');
    checks.push('stable-older-page-and-live-first-page');
     for(const theme of ['classic','light','dark']) for(const width of [1920,1366,800,360]) for(const zoom of [1,1.5]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},sessionId);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},sessionId);
      await evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme==='classic'?'classic':'web')}; document.body.style.zoom=${zoom}`);
      const layout=await evaluate(`(() => {const pan=document.querySelector('.sessions-table-pan'),table=pan.querySelector('table'),row=table.querySelector('tbody tr');return {
        innerVertical:pan.scrollHeight>pan.clientHeight,maxHeight:getComputedStyle(pan).maxHeight,
        rows:table.querySelectorAll('tbody tr').length,nowrap:[...row.cells].every(cell=>getComputedStyle(cell).whiteSpace==='nowrap'),
        numericFit:[...row.cells].filter((_,index)=>index!==1).every(cell=>cell.scrollWidth<=cell.clientWidth+1),
        pan:pan.scrollWidth>pan.clientWidth,pageWidth:document.documentElement.scrollWidth,viewport:innerWidth};})()`);
      assert.equal(layout.innerVertical,false); assert.equal(layout.maxHeight,'none'); assert.equal(layout.nowrap,true); assert.equal(layout.numericFit,true);
      assert.ok(layout.pageWidth<=width+1); layouts.push({route:'catalog',theme,width,zoom,...layout});
    }
    await evaluate(`window.detailProbe={elements:0,updates:0};const originalElement=ReportView.element;ReportView.element=(...args)=>{detailProbe.elements++;if(detailProbe.elements>60000)throw new Error('unbounded detail nodes');return originalElement(...args);};
      const originalUpdate=SessionDetail.View.prototype.update;SessionDetail.View.prototype.update=function(data){detailProbe.updates++;detailProbe.stage='start';const result=originalUpdate.call(this,data);detailProbe.stage='done';return result;};
      document.body.style.zoom=1; location.hash='#/sessions/root-0000/live'`);
    await until('current?.detail?.data?.total === 1001');
    assert.equal(await evaluate('location.hash'),'#/sessions/root-0000');
    assert.equal(await evaluate('document.querySelectorAll("#result tbody tr").length'),1001);
    assert.equal(await evaluate('document.querySelectorAll("#result th").length'),10);
    assert.equal(await evaluate('document.querySelectorAll("#result tfoot td").length'),10);
    assert.match(await evaluate('document.querySelector("#result h1").textContent'),/Synthetic 0000/);
    assert.match(await evaluate('document.querySelector("#result").textContent'),/Session ID: root-0000/);
     for(const theme of ['classic','light','dark']) for(const width of [1920,1366,800,360]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},sessionId);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},sessionId);
      await evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme==='classic'?'classic':'web')}`);
      const layout=await evaluate(`(() => {const pan=document.querySelector('.sessions-table-pan'),row=pan.querySelector('tbody tr'),running=pan.querySelector('tr.session-running');return {
        innerVertical:pan.scrollHeight>pan.clientHeight,rows:pan.querySelectorAll('tbody tr').length,
        numericFit:[...row.cells].slice(1).every(cell=>cell.scrollWidth<=cell.clientWidth+1),
        runningColors:[...running.cells].map(cell=>getComputedStyle(cell).color),foreground:getComputedStyle(row).color,
        columns:[...pan.querySelectorAll('th')].map(cell=>cell.textContent)};})()`);
      assert.equal(layout.innerVertical,false); assert.equal(layout.numericFit,true); assert.equal(new Set(layout.runningColors).size,1);
      assert.notEqual(layout.runningColors[0],layout.foreground); layouts.push({route:'detail',theme,width,...layout});
    }
    checks.push('1001-unpaged-chronological-prompts-ten-columns-themes');
    const selection=await evaluate(`(() => {const target=document.querySelectorAll('tbody tr')[500].querySelector('.session-preview');target.focus();window.scrollTo(0,target.getBoundingClientRect().top+scrollY-100);
      const range=document.createRange();range.selectNodeContents(target);getSelection().removeAllRanges();getSelection().addRange(range);window.retainedNode=target;return {text:getSelection().toString(),top:target.getBoundingClientRect().top};})()`);
    await fixture('end'); await until('current.detail.data.total === 1002');
    assert.equal(await evaluate('getSelection().toString()'),selection.text);
    assert.equal(await evaluate('retainedNode.isConnected'),true);
    assert.ok(Math.abs(await evaluate('retainedNode.getBoundingClientRect().top')-selection.top)<2);
    assert.equal(await evaluate('document.querySelectorAll("tr.session-running").length'),0);
     await evaluate(`getSelection().removeAllRanges();window.detailStates=[];
       const sourceStatus=current.detail.sourceStatus.bind(current.detail);
       current.detail.sourceStatus=data=>{detailStates.push(data.state);return sourceStatus(data);}`);
     await fixture('fail');
     await until('detailStates.includes("source_unavailable")');
      assert.equal(await evaluate('current.detail.loader.root.hidden'),true);
       assert.equal(await evaluate('current.detail.status.hidden'),true, 'populated detail recovers silently');
    assert.equal(await evaluate('document.querySelectorAll("tbody tr").length'),1002);
     await evaluate('detailStates.length=0');
     await fixture('recover'); await until('detailStates.includes("observed")');
     checks.push('selection-scroll-end-outage-recovery');
     const expected = ['2026-03-29 01:30','2026-03-29 03:30','2026-10-25 02:30','2026-10-25 02:30'];
     for (const locale of ['sv-SE','en-US']) for (const timezoneId of ['Europe/Stockholm','America/New_York']) {
       await command('Emulation.setLocaleOverride',{locale},sessionId);
       await command('Emulation.setTimezoneOverride',{timezoneId},sessionId);
       assert.deepEqual(await evaluate(`['2026-03-29T00:30Z','2026-03-29T01:30Z','2026-10-25T00:30Z','2026-10-25T01:30Z'].map(value=>ReportView.timestamp(Date.parse(value),'Europe/Stockholm'))`),expected);
     }
     await command('Emulation.setLocaleOverride',{},sessionId);await command('Emulation.setTimezoneOverride',{timezoneId:''},sessionId);
     checks.push('configured-local-24-hour-format-two-locales-two-browser-timezones-spring-and-autumn-DST');
     // Compare the actual post-596 tables to the Watch reference, not a CSS-text proxy.
     for (const route of ['watch','models','token-mix','sessions','sessions/root-0000']) {
       await evaluate(`document.body.style.zoom=1;location.hash=${JSON.stringify('#/'+route)}`);
       if (route==='models') await until('current.result && !current.loading');
       if (route==='watch') await until('document.querySelector(".watch-prompt-table tbody tr")');
        if (route==='token-mix') {
          await until('current.section === "token-mix"');
          await until('current.result && !current.loading');
         await until('document.querySelectorAll(".token-mix-table").length===2');
           assert.deepEqual(await evaluate('[...document.querySelectorAll(".token-mix-table")].map(t=>t.querySelectorAll("th").length)'),[10,9]);
       }
       if (route==='sessions') await until('current.catalog?.data?.total===121');
        if (route==='sessions/root-0000') {
          await until('current.detail?.data?.total===1002');
          await evaluate(`document.querySelector('.session-preview').textContent='A deliberately lengthy prompt preview that should grow on spacious displays but yield to real numeric columns on smaller screens'`);
        }
        if (route==='sessions') {
          await until('!current.catalog.busy && !current.catalog.operation');
           // Health callbacks may reattach this catalog. Isolate only its
           // transport while synthetic rows settle through real CSS transitions.
           await command('Network.enable',{},sessionId);
           await command('Network.setBlockedURLs',{urls:[new URL('/api/sessions',launch.url).href]},sessionId);
           await evaluate(`(() => {
             window.pagerCatalog=current.catalog;
             window.pagerParent=pagerCatalog.root.parentNode;
             window.pagerOriginal=null;
             pagerCatalog.detach();
           })()`);
         }
       try {
        for(const theme of ['classic','light','dark']) for(const width of [1920,1366,800,360]) for(const zoom of [1,1.5]) {
         await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},sessionId);
         await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},sessionId);
         await evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme==='classic'?'classic':'web')};document.body.style.zoom=${zoom}`);
         const facts=await evaluate(`(() => {const tables=[...document.querySelectorAll('.watch-prompt-table,.sessions-table,.overview-model-table,.token-mix-table')];return {
           pageWidth:document.documentElement.scrollWidth,viewport:innerWidth,tables:tables.map(table=>{
             const pan=table.parentNode,th=table.querySelector('th'),cell=table.querySelector('td'),head=getComputedStyle(th),shell=getComputedStyle(pan),button=th.querySelector('button');
             return {columns:table.querySelectorAll('th').length,padding:[head.paddingTop,head.paddingRight],headerHeight:th.getBoundingClientRect().height/Number(getComputedStyle(document.body).zoom),
               headerBackground:head.backgroundColor,position:head.position,border:shell.borderTopWidth,radius:shell.borderTopLeftRadius,
               divider:getComputedStyle(cell).borderRightWidth,innerVertical:pan.scrollHeight>pan.clientHeight,maxHeight:shell.maxHeight,
               buttonHeight:button.getBoundingClientRect().height/Number(getComputedStyle(document.body).zoom),
               numericFit:[...table.querySelector('tbody tr').cells].every((c,i)=>(table.matches('.watch-prompt-table')?i===2:table.matches('.session-catalog-table')?i===1:i===0)||getComputedStyle(c).whiteSpace!=='nowrap'||c.scrollWidth<=c.clientWidth+1),
               previewWidth:table.querySelector('.session-preview')?.clientWidth};})};})()`);
         assert.ok(facts.tables.length>0); assert.ok(facts.pageWidth<=width+1);
         for (const table of facts.tables) {
           assert.deepEqual(table.padding,['5.25px','9px']); assert.equal(table.radius,'6px');
           assert.ok(Math.abs(parseFloat(table.border)*zoom-1)<.01); assert.ok(Math.abs(parseFloat(table.divider)*zoom-1)<.01);
           assert.equal(table.innerVertical,false); assert.equal(table.maxHeight,'none'); assert.equal(table.numericFit,true);
           assert.equal(table.position,['watch','models'].includes(route)?'static':'sticky');
           assert.ok(table.buttonHeight<25, 'compact visible-text header targets');
         }
         layouts.push({route,theme,width,zoom,...facts});
         if (theme==='classic' && width===1366 && zoom===1) {
           const image=await command('Page.captureScreenshot',{format:'png'},sessionId);
           await fs.writeFile(path.join(directory,'table-'+route.replaceAll('/','-')+'.png'),Buffer.from(image.data,'base64'));
         }
          if (route==='sessions') {
            await evaluate(`(()=>{window.pagerOriginal=current.catalog.data;const value=structuredClone(pagerOriginal);
              value.total=1234567;value.view.session_usage[0].running=true;current.catalog.update(value);})()`);
            await until(`(()=>{const row=document.querySelector('.session-catalog-table tbody tr');return row.classList.contains('session-running') &&
              new Set([...row.querySelectorAll('td,a,span,button')].map(n=>getComputedStyle(n).color)).size===1;})()`);
            const pager=await evaluate(`(() => {
              const bar=document.querySelector('.page-navigation'),label=bar.querySelector(':scope > span').getBoundingClientRect(),buttons=[...bar.querySelectorAll('button')].map(b=>b.getBoundingClientRect()),bounds=bar.getBoundingClientRect();
             const row=document.querySelector('.session-catalog-table tbody tr'),colors=[...row.querySelectorAll('td,a,span,button')].map(n=>getComputedStyle(n).color);
               const result={center:Math.abs((label.left+label.right)/2-(bounds.left+bounds.right)/2),overlap:buttons.some(b=>b.left<label.right&&b.right>label.left&&b.top<label.bottom&&b.bottom>label.top),colors:[...new Set(colors)],marker:row.cells[1].textContent.startsWith('[RUNNING] '),
                 labelOnly:[...bar.querySelectorAll('button')].every(b=>!b.children.length && b.childNodes.length===1 && b.firstChild.nodeType===Node.TEXT_NODE && !b.hasAttribute('aria-busy'))};
               current.catalog.update(pagerOriginal);window.pagerOriginal=null;return result;})()`);
             assert.ok(pager.center<2);assert.equal(pager.overlap,false);assert.equal(pager.colors.length,1,JSON.stringify(pager));assert.equal(pager.marker,true);
              assert.equal(pager.labelOnly,true,'all pager states use only meaningful text, never a reserved spinner slot');
         }
        }
       } catch(error) {
         if(route==='sessions') evidence.catalogIsolation=await evaluate(`(() => {
           const row=pagerCatalog.body.firstElementChild;
           return {attached:pagerCatalog.attached,busy:pagerCatalog.busy,
             running:row?.value.running,className:row?.className,
             colors:[...row.querySelectorAll('td,a,span,button')].map(node=>({
               tag:node.tagName,className:node.className,color:getComputedStyle(node).color}))};
         })()`);
         throw error;
       } finally {
         if (route==='sessions') {
           try {
             await evaluate(`(() => {
               try {if(pagerOriginal) pagerCatalog.update(pagerOriginal);}
               finally {window.pagerOriginal=null;pagerCatalog.detach();}
             })()`);
           } finally {
             await command('Network.setBlockedURLs',{urls:[]},sessionId);
             await evaluate('pagerCatalog.attach(pagerParent)');
           }
         }
       }
     }
      checks.push('watch-sessions-detail-models-ten/nine-column-token-mix-parity-three-themes-four-widths-two-zooms');
     assert.deepEqual(errors,[]);
     evidence={outcome:'PASS',browser:version.product,checks,layouts,discovery_ms:latency,
       synthetic_catalog_transport_isolated:true,
      inference_calls:0,personal_profile:false,desktop_effects:false};
  } catch (error) {
    const bounded = value => String(value ?? '').replace(/https?:\/\/[^\s"'<>]+/g, '[url]').slice(0, 2500);
    evidence.diagnostic = {
      name: bounded(error.name), message: bounded(error.message),
      location: bounded(error.stack?.split('\n').filter(line => /\bat /.test(line)).slice(0, 3).join('\n')),
      actual: bounded(JSON.stringify(error.actual)), expected: bounded(JSON.stringify(error.expected)),
      lastExpression: bounded(lastExpression)
    };
    throw error;
  } finally {
    clearTimeout(deadline); server.stdin.end();
    await command('Browser.close').catch(()=>child.kill()); await browserExit;
    await serverExit;
    await fs.writeFile(output,JSON.stringify({...evidence,checks,layouts,lastExpression,errors,serverError},null,2));
    await fs.rm(profile,{recursive:true,force:true}).catch(()=>{}); await fs.rm(config,{recursive:true,force:true}).catch(()=>{});
  }
  console.log(JSON.stringify({outcome:evidence.outcome,checks:evidence.checks,discovery_ms:evidence.discovery_ms}));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
