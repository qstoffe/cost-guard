// Neutral journey over the selected historical host's own shipped assets.
// The one-use launch URL arrives on stdin and is never written to evidence.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {createHash} = require('node:crypto');
const {setTimeout: pause} = require('node:timers/promises');

const hostEntry = (snapshot, section) => snapshot?.entries?.find(row=>
  row.scope.kind===(section==='models'?'normal':section) &&
  row.scope.default_scope && (section!=='ai-stats' || row.scope.stats_scope==='30-days') && !row.scope.comparison_offset);

function connectedUsablePaint(section, value) {
  if (!['accounts','accounts-switch'].includes(section)) return value.height>0 && value.text_length>100;
  return value.height>0 && value.text_length>0 && value.section==='accounts' && !value.hidden &&
    value.output_connected && value.account_root_attached && value.account_root_visible &&
    value.live_accounts===1 && value.account_cards===1 && value.account_nodes.length===1 &&
    value.account_nodes.every(card=>card.connected && card.attached && card.visible && card.height>0 &&
      card.width>0 && card.text_length>0 && card.value_present && card.shape_present && card.signature_present &&
      card.identity_matches && card.heading_visible && card.heading_matches && card.quota_visible && card.quota_matches);
}

// Runs in the shipped page. Keep one post-paint snapshot for both assertion and evidence.
function captureAccountsPaint(accounts=current.accounts, view=liveValue.view, parent=output) {
  const visible = node=>!!node?.isConnected && node.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}) &&
    node.getBoundingClientRect().height>0 && node.getBoundingClientRect().width>0;
  const items = view?.accounts?.accounts || [];
  return {section:current.section,hidden:document.hidden,output_connected:parent.isConnected,
    height:parent.getBoundingClientRect().height,text_length:parent.textContent.length,
    account_root_attached:accounts?.root?.parentNode===parent,account_root_visible:visible(accounts?.root),
    live_accounts:items.length,account_cards:accounts?.cards?.size??0,
    account_nodes:[...(accounts?.cards?.values()||[])].map(card=>{
      const identity=card.value?.observation;
      const matches=items.filter(row=>identity && typeof identity.id==='string' && typeof identity.provider_id==='string' &&
        row.observation.id===identity.id && row.observation.provider_id===identity.provider_id);
      const item=matches.length===1?matches[0]:null, primary=item?.primary, quota=primary?.quota;
      const heading=card.root.querySelector('h4'), label=card.root.querySelector('.watch-quota-summary>span');
      const display=quota?ReportView.quotaView(quota,primary):null;
      const summary=quota?.unlimited?'Unlimited':display?.percent==='—'?'—':display?.percent+' '+display?.mode;
      return {connected:card.root.isConnected,attached:accounts.root.contains(card.root),visible:visible(card.root),
        height:card.root.getBoundingClientRect().height,width:card.root.getBoundingClientRect().width,
        text_length:card.root.textContent.length,value_present:!!card.value,shape_present:!!card.shape,
        signature_present:!!card.signature,identity_matches:!!item,heading_visible:visible(heading),
        heading_matches:!!item && heading?.textContent===item.observation.label,quota_visible:visible(label),
        quota_matches:!!quota && label?.textContent===quota.label+' · '+summary,
        reset_text:card.root.querySelector('.watch-primary-details>p>span')?.textContent??null};
    })};
}

function qualifyUntouchedEntry({section, checkpoint, client, navigation, visited}) {
  const age = Number.isSafeInteger(checkpoint?.captured_wall_ms) ? navigation-checkpoint.captured_wall_ms : null;
  const host = hostEntry(checkpoint,section), reasons = [];
  if (age===null || age<0 || age>1000) reasons.push('checkpoint-not-fresh');
  if (visited || !client || client.view_present || client.acquisition_started) reasons.push('prior-client-visit-or-acquisition');
  if (!checkpoint || typeof checkpoint.dispatcher!=='boolean') reasons.push('dispatcher-state-missing');
  if (checkpoint?.dispatcher && (!host?.warm_complete || typeof host.publication!=='string' || !host.publication))
    reasons.push('exact-default-warm-publication-missing');
  return {valid:reasons.length===0,reasons,qualification_age_ms:age,host_before:host??null,
    classification:checkpoint?.dispatcher?'untouched-native-background-warming':'no-dispatcher-on-demand'};
}

async function requestWarmCheckpoint({directory, sequence, label, deadline, lastAcknowledgedSequence}) {
  const requested = Date.now();
  let stage = 'request-write';
  try {
    const temporary = path.join(directory,`warm-request-${sequence}.tmp`);
    await fs.writeFile(temporary,JSON.stringify({sequence,label}),{flag:'wx'});
    stage = 'request-publish';
    // Publish closed immutable bytes without overwriting a reader's file. Keep
    // both links until the owned fixture participants have stopped.
    await fs.link(temporary,path.join(directory,`warm-request-${sequence}.json`));
    while (Date.now()<deadline) {
      stage = 'acknowledgement-read';
      try {
        const value = JSON.parse(await fs.readFile(path.join(directory,`warm-ack-${sequence}.json`),'utf8'));
        assert.equal(value.sequence,sequence,'exact sequence file must acknowledge this request');
        return {...value,acknowledgement_delay_ms:Date.now()-requested};
      } catch (error) { if(error.code!=='ENOENT')throw error; }
      await pause(40);
    }
    throw new Error('checkpoint-deadline');
  } catch (error) {
    const failure = new Error('Warm checkpoint protocol failed: '+stage);
    failure.protocol = {stage,current_sequence:sequence,last_acknowledged_sequence:lastAcknowledgedSequence,
      error_class:error.constructor.name,errno:error.errno??null,winerror:error.winerror??null};
    throw failure;
  }
}

async function main() {
  let input = '';
  for await (const chunk of process.stdin) input += chunk;
  const spec = JSON.parse(input);
  const [browser, output] = process.argv.slice(2);
  await fs.stat(browser);
  await fs.mkdir(output, {recursive:false});
  const profile = await fs.mkdtemp(path.join(output, 'profile-'));
  const child = spawn(browser, ['--headless=new', '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--disable-background-networking', '--remote-debugging-pipe',
    '--user-data-dir='+profile, 'about:blank'],
    {windowsHide:true, stdio:['ignore','ignore','ignore','pipe','pipe']});
  const pending = new Map(), exceptions = [];
  let sequence = 0, buffer = '', tab;
  const facts = {outcome:'FAIL', routes:[], checks:[]};
  const deadline = Date.now() + spec.seconds * 1000;
  child.stdio[4].on('data', chunk => {
    buffer += chunk.toString();
    let end;
    while ((end = buffer.indexOf('\0')) >= 0) {
      const message = JSON.parse(buffer.slice(0, end)); buffer = buffer.slice(end + 1);
      const item = pending.get(message.id);
      if (item) {
        pending.delete(message.id); clearTimeout(item.timer);
        message.error ? item.reject(new Error('CDP command failed')) : item.resolve(message.result);
      } else if (message.method === 'Runtime.exceptionThrown') {
        const detail = message.params.exceptionDetails;
        exceptions.push({class:detail.exception?.className ?? null, line:detail.lineNumber, column:detail.columnNumber,
          frames:(detail.stackTrace?.callFrames || []).slice(0,5).map(frame=>({
            source:frame.url.split(/[?#]/)[0].split('/').at(-1), line:frame.lineNumber, column:frame.columnNumber}))});
      }
    }
  });
  const command = (method, params={}, sessionId=tab) => new Promise((resolve, reject) => {
    const id = ++sequence, timer = setTimeout(() => {
      pending.delete(id); reject(new Error('CDP timeout: '+method));
    }, 15000);
    pending.set(id, {resolve, reject, timer});
    child.stdio[3].write(JSON.stringify({id, method, params, ...(sessionId ? {sessionId} : {})})+'\0');
  });
  const evaluate = async (expression, userGesture=false) => {
    const result = await command('Runtime.evaluate', {expression, userGesture, returnByValue:true, awaitPromise:true});
    if (result.exceptionDetails) throw new Error('Page expression failed: '+expression);
    return result.result.value;
  };
  const until = async expression => {
    while (Date.now() < deadline) {
      if (await evaluate(expression)) return;
      await pause(40);
    }
    facts.wait_failure = await evaluate(`({section:current?.section??null,loading:!!current?.loading,
      failed:!!current?.failed,withheld:!!current?.withheld,result_present:!!current?.result,
      active_job_present:!!current?.active,period:current?.period??null,
      progress_sequence:current?.progressSequence??null,percent:current?.percent??null})`);
    throw new Error('Condition not reached: '+expression);
  };
  const paint = () => evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(true))))');
  const reportReady = section => `current?.section===${JSON.stringify(section)} && !!current.result && !current.loading && !current.withheld && !current.failed`;
  const assertPaint = async section => {
    await paint();
    const accounts = ['accounts','accounts-switch'].includes(section);
    const value = await evaluate(accounts ? `(${captureAccountsPaint.toString()})()` :
      `({height:output.getBoundingClientRect().height, text_length:output.textContent.length})`);
    if (accounts) (facts.accounts_paints??=[]).push({...value,label:section,
      old_text_threshold:value.height>0 && value.text_length>100,semantic_usable:connectedUsablePaint(section,value)});
    if (!connectedUsablePaint(section,value)) {
      facts.paint_failure = {section, ...value, exceptions:[...exceptions]};
    }
    assert.equal(connectedUsablePaint(section,value), true, 'Connected usable paint: '+section);
  };
  const recordRoute = async (section, started) => {
    await assertPaint(section);
    const elapsed = performance.now()-started;
    facts.routes.push({section, status:'complete', seconds:elapsed/1000,
      started_wall_ms:Date.now()-elapsed, ready_wall_ms:Date.now()});
  };
  const openEarlier = async () => {
    await until(`current?.section==='watch' && !!document.querySelector('.watch-earlier>summary')`);
    if (await evaluate(`!current.watch.earlier.open`)) {
      await evaluate(`current.watch.earlier.querySelector('summary').focus();true`);
      await command('Input.dispatchKeyEvent', {type:'keyDown', key:'Enter', code:'Enter', windowsVirtualKeyCode:13,
        text:'\r', unmodifiedText:'\r'});
      await command('Input.dispatchKeyEvent', {type:'keyUp', key:'Enter', code:'Enter', windowsVirtualKeyCode:13});
    }
    await until('current.watch.earlier.open');
  };
  const referenceHistory = async () => {
    const started = performance.now(), expected = JSON.stringify(spec.history_rows);
    await until(`typeof current!=='undefined'`);
    await evaluate(`location.hash='#/watch'`);
    await openEarlier();
    await until(`liveValue?.view?.history_state==='observed' && JSON.stringify(
      liveValue.view.history_cards.map(card=>[card.session_id,card.rows[0].prompt.event_id,
        card.rows[0].prompt.completed_at_ms]))===${JSON.stringify(expected)}`);
    const fullIds = JSON.stringify(spec.history_rows.map(row=>row[0]));
    await until(`JSON.stringify([...output.querySelectorAll('.watch-history [data-session]')]
      .map(row=>row.dataset.session))===${JSON.stringify(fullIds)}`);
    await paint();
    assert.equal(await evaluate(`current.watch.earlier.open && [...output.querySelectorAll('.watch-history [data-session]')]
      .every(row=>row.getBoundingClientRect().height>0)`), true);
    facts.routes.push({section:'watch-earlier',status:'complete',seconds:(performance.now()-started)/1000});
    facts.full = {count:spec.history_rows.length, identity_prompt_finish_order:true, dom_order:true};
    await until(`!!miniWatch.measure?.ready`);
    await evaluate('miniWatch.toggle()', true);
    await until('!!miniWatch.view && miniWatch.window.document.styleSheets.length===2');
    const expectedMini = require('../fixtures/mini_history_expected.cjs').toString();
    await until(`JSON.stringify([...miniWatch.view.body.querySelectorAll('[data-id]')]
      .map(row=>row.dataset.id))===JSON.stringify((${expectedMini})(liveValue.view).map(row=>row.id))`);
    const miniCount=await evaluate(`(()=>{
      miniWatch.render();
      const expected=(${expectedMini})(liveValue.view),now=Date.now();
      const today=ReportView.timestamp(now).slice(0,10);
      for(const value of expected) {
        const row=miniWatch.view.promptRows.get(value.id), time=row?.children[0].children[0];
        if(!row || row.getBoundingClientRect().height<=0 || row.activityHelp!==value.help)
          throw Error('Mini population/activity help mismatch');
        const known=Number.isSafeInteger(value.at) && value.at>=0, age=now-value.at;
        let label=known ? value.clock : '—';
        if(known && age>=12*3600000 && /^\\d{4}-\\d{2}-\\d{2} /.test(value.help) && !value.help.startsWith(today+' ')) {
          const unit=age<86400000 ? [3600000,'h'] : age<30*86400000 ? [86400000,'d'] :
            age<365*86400000 ? [30*86400000,'m'] : [365*86400000,'y'];
          label=Math.floor(age/unit[0])+unit[1]+' ago';
        }
        if(time.children[1].textContent!==label ||
            time.children[0].textContent!==(value.play ? '▶ ' : ''))
          throw Error('Mini start/finish activity mismatch');
      }
      return expected.length;
    })()`);
    const blank = await command('Target.createTarget', {url:'about:blank'}, null);
    const other = (await command('Target.attachToTarget', {targetId:blank.targetId, flatten:true}, null)).sessionId;
    await command('Page.bringToFront', {}, other);
    await until('document.hidden && !miniWatch.window.document.hidden');
    assert.equal(await evaluate(`miniWatch.demand.payload(true).history && miniWatch.demand.payload(true).visible`), true);
    facts.mini = {count:miniCount, dom_order:true, start_finish_display:true,
      opener_hidden:true, mini_visible:true, independent_history_demand:true};
    await command('Target.closeTarget', {targetId:blank.targetId}, null);
    await command('Page.bringToFront');
    await evaluate('miniWatch.close();true');
    assert.deepEqual(exceptions, []);
    facts.outcome = 'PASS';
  };
  const finiteSections = ['models', 'token-mix', 'ai-stats', 'comparisons'];
  let checkpointSequence = 0, lastAcknowledgedSequence = 0;
  const checkpoint = async label => {
    try {
      const value = await requestWarmCheckpoint({directory:spec.warm_directory,sequence:++checkpointSequence,
        label,deadline,lastAcknowledgedSequence});
      lastAcknowledgedSequence = value.sequence;
      return value;
    } catch (error) {
      facts.warm_protocol_error = error.protocol;
      throw error;
    }
  };
  const digest = fields => createHash('sha256').update(JSON.stringify(fields)).digest('hex');
  const clientFacts = async section => {
    const value = await evaluate(`(()=>{
      const state=[...views.values()].find(value=>value.section===${JSON.stringify(section)} &&
        (value.section!=='ai-stats' || value.period==='30-days'));
      const result=state?.result, view=result?.view, seen=result?.source?.observed_at_ms;
      const shape=!result?false:${section==='models' ? `view?.model_comparison_sample_size===100 &&
        view.model_catalog?.rows?.length>=5 && view.model_availability_unverified===false` :
        section==='token-mix' ? 'TokenMixView.valid(result)' : section==='ai-stats' ?
        `AIStatsView.valid(result) && view.ai_stats.some(row=>row.period==='30-days')` : 'ComparisonsView.valid(result)'};
      return {qualified:!!shape && !state.failed && !state.withheld && !result.error &&
          Number.isSafeInteger(seen) && seen<=Date.now() && ['acquired','partial'].includes(result.source.status),
        view_present:!!state, acquisition_started:!!(state?.attempt || state?.active || state?.loading || result || state?.dataRevision),
        loading:!!state?.loading, observed_at_ms:seen??null,
        identity:[result?.instance_id??null,result?.sequence??null,seen??null],
        job:state?.dataRevision?.split(':')[0]??null};})()`);
    value.content_publication = digest(value.identity);
    value.publication = value.job ? digest([value.job,...value.identity]) : null;
    delete value.identity; delete value.job;
    return value;
  };
  const matchPublication = (before, after) => !before?.warm_complete ? null : before.publication===after.publication;
  const passiveUntouchedWarm = async () => {
    const started = Date.now();
    let state = await checkpoint('untouched-after-models');
    while (state.dispatcher && !finiteSections.slice(1).every(section=>hostEntry(state,section)?.warm_complete)) {
      state = await checkpoint('untouched-still-warming');
    }
    facts.untouched_background = {started_wall_ms:started, ready_wall_ms:Date.now(),
      warming_seconds:(Date.now()-started)/1000, checkpoint:state, entries:[],
      classification:state.dispatcher?'untouched-native-background-warming':'no-dispatcher-retention'};
  };
  const checkpointedWarmEntry = async (section, mode, rows, reload=false) => {
    const before = await checkpoint(mode+'-'+section), retained = await clientFacts(section);
    const host = hostEntry(before,section), navigation = Date.now(), started = performance.now();
    const row = {section,status:'navigating',navigation_wall_ms:navigation,
      qualification_age_ms:navigation-before.captured_wall_ms,
      qualification_proved:navigation-before.captured_wall_ms>=0 && navigation-before.captured_wall_ms<=1000,
      client_before:reload?{qualified:false,classification:'fresh-document'}:retained,
      host_before:host??null,before};
    rows.push(row); // Preserve attempted observations even if a later checkpoint fails.
    if (reload) {
      await command('Page.reload',{ignoreCache:false});
      while (Date.now()<deadline) {
        try { if (await evaluate(`typeof __cgWarm==='undefined' && typeof current!=='undefined'`)) break; }
        catch (_) { /* New document replaces the execution context. */ }
        await pause(40);
      }
    } else await evaluate(`location.hash=${JSON.stringify('#/'+section)}`);
    await until(`current?.section===${JSON.stringify(section)} && !!current.result && !current.withheld && !current.failed`);
    await assertPaint(section);
    const visible = (performance.now()-started)/1000, painted = await clientFacts(section);
    Object.assign(row,{visible_seconds:visible,painted,status:'painted'});
    assert.equal(painted.qualified,true,'warm paint satisfies the actual route contract');
    const matching = matchPublication(host,painted);
    if (matching!==null) assert.equal(matching,true,'paint must reuse the checkpointed host publication');
    await until(reportReady(section));
    const settled = (performance.now()-started)/1000, settledWall = Date.now();
    Object.assign(row,{settled_seconds:settled,settled_wall_ms:settledWall,host_publication_match:matching});
    const after = await checkpoint(mode+'-'+section+'-settled');
    Object.assign(row,{after,status:'complete'});
  };
  const checkpointedWarmReentry = async () => {
    const sameTab = [], fresh = [];
    facts.checkpointed_warm_reentry = {same_tab_client_retained:sameTab,fresh_page_host_warm:fresh,
      limitation:'Shared hosts after the primary journey, not untouched-background trials. '
        +'Fresh Models includes reload. Submit calls/identities and report records determine acquisition, not global Live traffic.'};
    for (const section of finiteSections) await checkpointedWarmEntry(section,'same-tab',sameTab);
    await evaluate(`history.replaceState(null,'','/#/models');window.__cgWarm=true`);
    await checkpointedWarmEntry('models','fresh-page',fresh,true);
    for (const section of finiteSections.slice(1)) await checkpointedWarmEntry(section,'fresh-page',fresh);
  };
  // Visible retained content first, then settled host revalidation, for one finite route.
  const reenter = async (section, started, rows) => {
    await until(`current?.section===${JSON.stringify(section)} && !!current.result && !current.withheld && !current.failed`);
    await paint();
    const visible = (performance.now()-started)/1000;
    await until(reportReady(section));
    rows.push({section, visible_seconds:visible, settled_seconds:(performance.now()-started)/1000});
  };
  const warmIdleAndReentry = async () => {
    // Fixed browser settle, then browser-owned windows on Watch; neither is a product timeout.
    await evaluate(`location.hash='#/watch'`);
    await pause(spec.warm_settle * 1000);
    facts.warm_idle_windows = [];
    for (const label of ['earlier-open', 'earlier-closed']) {
      if (label === 'earlier-closed') {
        await evaluate(`current.watch.earlier.querySelector('summary').focus();true`);
        await command('Input.dispatchKeyEvent', {type:'keyDown', key:'Enter', code:'Enter', windowsVirtualKeyCode:13,
          text:'\r', unmodifiedText:'\r'});
        await command('Input.dispatchKeyEvent', {type:'keyUp', key:'Enter', code:'Enter', windowsVirtualKeyCode:13});
        await until('!current.watch.earlier.open');
      }
      const idle = {label, route:'watch', earlier_open:await evaluate('!!current.watch?.earlier.open'),
        history_demand:await evaluate(`(()=>{ try { return typeof demand!=='undefined' && demand ?
          demand.payload(true).history ?? null : null; } catch (_) { return null; } })()`),
        start_wall_ms:Date.now()};
      await pause(spec.warm_idle * 1000);
      idle.end_wall_ms = Date.now();
      facts.warm_idle_windows.push(idle);
    }
    const sameTab = [];
    for (const section of finiteSections) {
      const started = performance.now();
      await evaluate(`location.hash=${JSON.stringify('#/'+section)}`);
      await reenter(section, started, sameTab);
    }
    // Fresh page over the warm host: no client views, so host retention (or its absence) decides.
    await evaluate(`history.replaceState(null,'','/#/models'); window.__cgWarm=true`);
    const reloaded = performance.now();
    await command('Page.reload', {ignoreCache:false});
    while (true) {
      if (Date.now() >= deadline) throw new Error('Warm reload not reached');
      try { if (await evaluate(`typeof __cgWarm==='undefined' && typeof current!=='undefined'`)) break; }
      catch (_) { /* Context replaced during reload. */ }
      await pause(40);
    }
    const fresh = [];
    await reenter('models', reloaded, fresh);
    for (const section of finiteSections.slice(1)) {
      const started = performance.now();
      await evaluate(`location.hash=${JSON.stringify('#/'+section)}`);
      await reenter(section, started, fresh);
    }
    facts.warm_reentry = {same_tab_client_retained:sameTab, fresh_page_host_warm:fresh,
      limitation:'Same-tab rows reuse page memory; fresh-page rows include document reload/bootstrap for Models. '
        + 'Synthetic static source; visible = retained/admitted content painted, settled = no attempt in flight.'};
  };
  const watchdog = setTimeout(() => child.kill(), (spec.seconds + 2) * 1000);
  try {
    const version = await command('Browser.getVersion', {}, null);
    facts.browser = {product:version.product, protocolVersion:version.protocolVersion};
    const target = await command('Target.createTarget', {url:'about:blank'}, null);
    tab = (await command('Target.attachToTarget', {targetId:target.targetId, flatten:true}, null)).sessionId;
    await command('Runtime.enable'); await command('Page.enable');
    const started = performance.now();
    await command('Page.navigate', {url:spec.launch});
    if (spec.private_history) { await referenceHistory(); return; }
    if (spec.stats_lock_probe) {
      await until(`typeof current!=='undefined'`);
      facts.stats_lock_probe = {navigation_wall_ms:Date.now()};
      await evaluate(`location.hash='#/ai-stats'`);
      await until(reportReady('ai-stats'));
      await assertPaint('ai-stats-cache-lock');
      facts.stats_lock_recovered = true;
      facts.stats_lock_probe.ready_wall_ms = Date.now();
      await evaluate(`location.hash='#/models'`);
    }
    if (spec.finite_switch) {
      await until(`typeof current!=='undefined' && ${reportReady('models')}`);
      const before = await evaluate(`api('/api/jobs/'+${JSON.stringify(spec.promotion_job)})`);
      assert.ok(['queued','running'].includes(before.status),'the selected warming job must remain unfinished');
      assert.ok(before.progress.completed>0,'the selected warming job must already have actual progress');
      const switched = performance.now();
      facts.finite_promotion={section:spec.finite_switch,before,switch_wall_ms:Date.now()};
      await evaluate(`location.hash=${JSON.stringify('#/'+spec.finite_switch)}`);
      await until(reportReady(spec.finite_switch));
      await paint();
      facts.finite_promotion.switch_to_usable_seconds=(performance.now()-switched)/1000;
      facts.finite_promotion.ready_wall_ms=Date.now();
      facts.finite_promotion.same_job=await evaluate(`(async()=>{const id=${JSON.stringify(spec.promotion_job)}, job=await api('/api/jobs/'+id);
        const revision=[id,job.result?.instance_id,job.result?.sequence,CachedReports.observation(job.result)].join(':');
        return job.status==='complete' && current.dataRevision===revision &&
          job.result.source.observed_at_ms===current.result.source.observed_at_ms &&
          current.result.view.ai_stats.some(row=>row.period==='30-days');})()`);
      assert.equal(facts.finite_promotion.same_job,true,'original logical job supplies the qualified 30-day result');
      await evaluate(`location.hash='#/models'`);
    }
    if (spec.history_switch === 'mini') {
      // Visible Mini Earlier over a hidden opener while Models and history proof are both unfinished.
      await until(`typeof current!=='undefined' && current?.section==='models' && !!miniWatch?.measure?.ready`);
      const before = await evaluate(`({checked:liveValue?.view?.history_checked??null, total:liveValue?.view?.history_total??null,
        modelsReady:!!current.result, historyState:liveValue?.view?.history_state??null})`);
      assert.equal(before.modelsReady, false, 'Models must still be unfinished at the switch');
      assert.notEqual(before.historyState, 'observed', 'history must still have actual proof work');
      facts.promotion = {mode:'mini', before, switch_wall_ms:Date.now()};
      const switched = performance.now();
      await evaluate('miniWatch.toggle()', true);
      await until('!!miniWatch.view && miniWatch.window.document.styleSheets.length===2');
      const blank = await command('Target.createTarget', {url:'about:blank'}, null);
      const other = (await command('Target.attachToTarget', {targetId:blank.targetId, flatten:true}, null)).sessionId;
      await command('Page.bringToFront', {}, other);
      await until(`document.hidden && !miniWatch.window.document.hidden`);
      facts.promotion.demand = await evaluate(`({openerHidden:document.hidden, modelsReady:!!current.result,
        visible:miniWatch.demand.payload(true).visible, history:miniWatch.demand.payload(true).history})`);
      assert.equal(facts.promotion.demand.visible && facts.promotion.demand.history, true);
      facts.promotion.hidden_wall_ms = Date.now();
      const newest = JSON.stringify([...spec.winners].sort());
      await until(`liveValue?.view?.history_state==='observed' &&
        JSON.stringify([...miniWatch.view.promptRows.keys()].sort())===${JSON.stringify(newest)}`);
      await evaluate('new Promise(resolve=>miniWatch.window.requestAnimationFrame(()=>miniWatch.window.requestAnimationFrame(()=>resolve(true))))');
      facts.promotion.switch_to_certified_seconds = (performance.now()-switched)/1000;
      facts.promotion.certified_wall_ms = Date.now();
      await command('Target.closeTarget', {targetId:blank.targetId}, null);
      await command('Page.bringToFront');
      await evaluate('miniWatch.close();true');
    } else if (spec.history_switch) {
      await until(`typeof current!=='undefined' && current?.section==='models' && liveValue?.view?.history_checked>0`);
      await pause(1500); // Fixed partial-warming workload, not a product timeout.
      const before = await evaluate(`({checked:liveValue.view.history_checked, total:liveValue.view.history_total,
        modelsReady:!!current.result, historyState:liveValue.view.history_state})`);
      assert.equal(before.modelsReady, false, 'Models must still be unfinished at the switch');
      assert.ok(before.checked < before.total, 'history must still have actual proof work');
      facts.promotion = {before, switch_wall_ms:Date.now()};
      const switched = performance.now();
      await evaluate(`location.hash='#/watch'`);
      await openEarlier();
      await until(`demand?.payload(true)?.history===true`);
      const winners = JSON.stringify([...spec.winners].sort());
      await until(`liveValue?.view?.history_state==='observed' && JSON.stringify(
        [...output.querySelectorAll('.watch-history [data-session]')].map(row=>row.dataset.session).sort())===${JSON.stringify(winners)}`);
      await paint();
      facts.promotion.switch_to_certified_seconds = (performance.now()-switched)/1000;
      await evaluate(`location.hash='#/models'`);
    }
    await until(`typeof current!=='undefined' && ${reportReady('models')}`);
    assert.equal(await evaluate('current.result.view.model_comparison_sample_size'), 100);
    assert.ok(await evaluate('current.result.view.model_catalog.rows.length') >= 5);
    assert.equal(await evaluate('current.result.view.model_availability_unverified'), false);
    await recordRoute('models', started);
    facts.checks.push('Actual Models paint with 100 qualified prompts and verified model availability');
    if (spec.untouched_warm) await passiveUntouchedWarm();
    const visited = new Set(['models']);
    for (const section of ['token-mix', 'ai-stats', 'comparisons']) {
      let attempt = null;
      if (spec.untouched_warm) {
        attempt = {section,status:'qualifying',attempted_wall_ms:Date.now()};
        facts.untouched_background.entries.push(attempt); // Keep failed qualification, even before navigation.
        const qualification = await checkpoint('untouched-entry-'+section), client = await clientFacts(section);
        const navigation = Date.now();
        Object.assign(attempt,{qualification,client_before:client,navigation_wall_ms:navigation,
          ...qualifyUntouchedEntry({section,checkpoint:qualification,client,navigation,visited:visited.has(section)})});
        if (!attempt.valid) {
          attempt.status = 'invalid-qualification';
          throw new Error('Untouched entry qualification incomplete: '+section+' '+attempt.reasons.join(','));
        }
        attempt.status = 'navigating';
      }
      const routeStart = performance.now();
      visited.add(section);
      await evaluate(`location.hash=${JSON.stringify('#/'+section)}`);
      await until(reportReady(section));
      if (section === 'comparisons') assert.equal(await evaluate(`current.result.view.comparisons.groups.some(
        group=>new Set(group.runs.map(run=>run.model)).size>1)`), true);
      await recordRoute(section, routeStart);
      if (attempt) {
        const painted = await clientFacts(section), host = attempt.host_before;
        Object.assign(attempt,{painted,settled_seconds:facts.routes.at(-1).seconds,settled_wall_ms:Date.now()});
        assert.equal(painted.qualified,true);
        const matching = matchPublication(host,painted);
        attempt.host_publication_match = matching;
        if (attempt.qualification.dispatcher) assert.equal(matching,true,'untouched view reuses its background publication');
        attempt.after = await checkpoint('untouched-entry-'+section+'-settled');
        attempt.status = 'complete';
      }
    }
    const watchStart = performance.now();
    await evaluate(`location.hash='#/watch'`);
    await openEarlier();
    const sortedWinners = JSON.stringify([...spec.winners].sort());
    await until(`liveValue?.view?.history_state==='observed' && JSON.stringify(
      [...output.querySelectorAll('.watch-history [data-session]')].map(row=>row.dataset.session).sort())===${JSON.stringify(sortedWinners)}`);
    await recordRoute('watch-earlier', watchStart);
    facts.historyProof = await evaluate(`({state:liveValue.view.history_state,
      checked:liveValue.view.history_checked??null,total:liveValue.view.history_total??null})`);
    facts.checks.push('Full Earlier DOM matches the independent five winners (B0 remains provisional)');
    const accountsStart = performance.now();
    await evaluate(`location.hash='#/accounts'`);
    await until(`current?.section==='accounts' && liveValue?.view?.accounts?.accounts?.length===1 && !!current.accounts?.cards?.size`);
    await recordRoute('accounts', accountsStart);
    const sessionsStart = performance.now();
    await evaluate(`location.hash='#/sessions'`);
    await until(`current?.section==='sessions' && current.catalog?.data?.available===${spec.roots} && current.catalog.data.view.session_usage.length===50`);
    await evaluate(`location.hash='#/sessions?offset=50&epoch='+current.catalog.data.epoch+'&sort=activity&direction=-1'`);
    await until(`current.catalog?.data?.offset===50 && current.catalog.data.view.session_usage.length===${Math.min(50,spec.roots-50)}`);
    assert.deepEqual(await evaluate('current.catalog.data.view.session_usage.map(row=>row.session_id)'),
      spec.catalog_order.slice(50,100));
    await recordRoute('sessions-page-2', sessionsStart);
    facts.checks.push('Shipped Sessions page 2 matches independently ordered membership');
    await evaluate(`location.hash='#/watch'`);
    await until(`typeof miniWatch!=='undefined' && !!miniWatch.measure?.ready`);
    const miniStart = performance.now();
    await evaluate('miniWatch.toggle()', true);
    await until('!!miniWatch.view && miniWatch.window.document.styleSheets.length===2');
    // No running sessions in this workload: all five canonical winners fill Mini.
    const newestFive = JSON.stringify([...spec.winners].sort());
    await until(`JSON.stringify([...miniWatch.view.promptRows.keys()].sort())===${JSON.stringify(newestFive)}`);
    await evaluate('new Promise(resolve=>miniWatch.window.requestAnimationFrame(()=>miniWatch.window.requestAnimationFrame(()=>resolve(true))))');
    facts.routes.push({section:'mini-earlier',status:'complete',seconds:(performance.now()-miniStart)/1000});
    facts.checks.push('Headless Document PiP Activity DOM matches the independent newest five');
    if (spec.history_switch) {
      const blank = await command('Target.createTarget', {url:'about:blank'}, null);
      const other = (await command('Target.attachToTarget', {targetId:blank.targetId, flatten:true}, null)).sessionId;
      await command('Page.bringToFront', {}, other);
      await until(`document.hidden && !miniWatch.window.document.hidden`);
      const demand = await evaluate(`({openerHidden:document.hidden, miniHidden:miniWatch.window.document.hidden,
        visible:miniWatch.demand.payload(!miniWatch.window.document.hidden).visible,
        history:miniWatch.demand.payload(true).history})`);
      assert.equal(demand.visible, true); assert.equal(demand.history, true);
      facts.mini_visibility = demand;
      await command('Target.closeTarget', {targetId:blank.targetId}, null);
      await command('Page.bringToFront');
    }
    await evaluate('miniWatch.close();true');
    if (spec.accounts_switches) {
      facts.accounts_switches = [];
      for (let index=0;index<spec.accounts_switches;index++) {
        await evaluate(`location.hash='#/watch'`);
        await until(`current?.section==='watch'`);
        const observed = await evaluate('liveValue.source_observed_at_ms');
        assert.ok(Number.isSafeInteger(observed), 'a real source observation precedes each switch');
        await until(`liveValue.source_observed_at_ms!==${JSON.stringify(observed)}`);
        await evaluate(`location.hash='#/accounts'`);
        await until(`current?.section==='accounts' && liveValue?.view?.accounts?.accounts?.length===1 && !!current.accounts?.cards?.size`);
        await assertPaint('accounts-switch');
        facts.accounts_switches.push({ordinal:index+1, observed_at_ms:await evaluate('liveValue.source_observed_at_ms')});
      }
    }
    if (spec.warm_directory) {
      facts.primary_phase_end_wall_ms = Date.now();
      facts.primary_boundary = await checkpoint('primary-end');
    }
    if (spec.append_warm_reentry) await checkpointedWarmReentry();
    if (spec.warm_idle) await warmIdleAndReentry();
    if (spec.accounts_boundary_resets) {
      await evaluate(`location.hash='#/accounts'`);
      await until(`current?.section==='accounts' && !!current.accounts?.cards?.size`);
      facts.accounts_boundary = [];
      for (const reset of spec.accounts_boundary_resets) {
        const value = await evaluate(`(async()=>{
          const view=structuredClone(liveValue.view), sandbox=document.createElement('div');
          view.accounts.accounts[0].primary.display.watch_reset=${JSON.stringify(reset)};
          for (const unit of Object.values(view.accounts.accounts[0].primary.display_units||{}))
            unit.watch_reset=${JSON.stringify(reset)};
          output.append(sandbox);
          try {
            const cards=new AccountCards.View(); cards.update(view); cards.attach(sandbox);
            await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
            const capture=${captureAccountsPaint.toString()}, healthy=capture(cards,view,sandbox);
            const label=cards.root.querySelector('.watch-quota-summary>span'); label.hidden=true;
            const hidden=capture(cards,view,sandbox); label.remove();
            return {healthy,hidden,missing:capture(cards,view,sandbox)};
          } finally { sandbox.remove(); }
        })()`);
        assert.equal(connectedUsablePaint('accounts',value.healthy),true);
        assert.equal(connectedUsablePaint('accounts',value.hidden),false);
        assert.equal(connectedUsablePaint('accounts',value.missing),false);
        facts.accounts_boundary.push({reset,...value,old_text_threshold:value.healthy.text_length>100});
      }
    }
    assert.deepEqual(exceptions, []);
    facts.outcome = 'PASS';
  } catch (error) {
    facts.error = spec.private_history ? 'private_history_browser_journey_failed' : error.message;
    facts.browser_exceptions = exceptions;
    process.exitCode = 1;
  } finally {
    try { await command('Browser.close', {}, null); } catch (_) { child.kill(); }
    if (child.exitCode === null && child.signalCode === null) await new Promise(resolve => child.once('exit', resolve));
    clearTimeout(watchdog);
    for (const item of pending.values()) clearTimeout(item.timer);
    facts.browser_exited = child.exitCode !== null || child.signalCode !== null;
    await fs.writeFile(path.join(output,'result.json'), JSON.stringify(facts,null,2));
    process.stdout.write(JSON.stringify(facts));
  }
}
module.exports = {qualifyUntouchedEntry,requestWarmCheckpoint,connectedUsablePaint,captureAccountsPaint};
if (require.main===module)
  main().catch(() => {process.stdout.write(JSON.stringify({outcome:'FAIL',error:'browser_driver_failed'}));process.exitCode=1;});
