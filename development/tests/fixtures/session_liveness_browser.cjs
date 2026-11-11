// Actual authenticated HTTP, private spawned captures and shipped session UI; no mock API.
const assert = require('node:assert/strict');
module.exports = async function sessionLiveness({evaluate, until, fixture, command}) {
  const checks = [], layouts = [], measurements = {};
  const observeUntil = async predicate => {
    const deadline = Date.now()+10000;
    while (Date.now()<deadline) {
      const value = await fixture('detail-observe');
      if (predicate(value)) return value;
      await new Promise(resolve=>setTimeout(resolve,50));
    }
    throw new Error('Detail ownership transition not observed');
  };
  await fixture('detail-blocked');
  await evaluate(`window.detailEvents=[];window.detailReads=[];
    const fetchDetail=window.fetch;window.fetch=async(url,options)=>{
      const response=await fetchDetail(url,options);
      if(url==='/api/detail'){
        const request=JSON.parse(options.body),value=await response.clone().json();
        detailReads.push({action:request.action,at:performance.now(),phase:value.acquisition?.phase,
          reason:value.acquisition?.reason,result:!!value.result,attempts:value.acquisition?.attempts});
      }return response;};
    const status=SessionDetail.View.prototype.sourceStatus;
    SessionDetail.View.prototype.sourceStatus=function(value){status.call(this,value);
      detailEvents.push({at:performance.now(),phase:value.acquisition?.phase,percent:this.loader.bar.value});};
    const update=SessionDetail.View.prototype.update;
    SessionDetail.View.prototype.update=function(value){update.call(this,value);window.detailApplied=performance.now();};
    location.hash='#/sessions/root-0000'`);
  await until('current.detail?.token && detailEvents.some(event=>event.phase==="reading")');
  const before = await observeUntil(value=>value.started===1 && value.active);
  await evaluate(`Promise.all(Array.from({length:25},()=>api('/api/detail',
    {action:'begin',token:current.detail.token,offset:0})))`);
  const after = await fixture('detail-observe');
  assert.equal(after.started,before.started,'HTTP status burst cannot submit another source capture');
  assert.deepEqual(after.metrics.work,before.metrics.work,'HTTP status reads cannot perform detail source reads');
  measurements.status_only_reads = 25;
  await evaluate(`(async()=>{window.peerToken=(await api('/api/detail',
    {action:'open',session_id:'root-0001',mode:'snapshot'})).token})()`);
  try { await until(`(async()=>{const value=await api('/api/detail',{action:'begin',token:peerToken,offset:0});
    if(value.acquisition?.phase==='failed')throw new Error('Peer failed: '+JSON.stringify(value.acquisition));
    if(value.result){window.peerRows=value.total;return true;}return false;})()`); }
  catch(error){throw new Error(error.message+'; lane='+JSON.stringify(await fixture('detail-observe')));}
  assert.equal(await evaluate('peerRows'),1);
  await evaluate(`api('/api/detail',{action:'close',token:peerToken})`);
  checks.push('one permanently blocked owned child retires; healthy competing snapshot publishes one canonical row');
  await until('current.detail.retry.hidden===false && !current.detail.busy');
  const failed = await evaluate(`({text:current.detail.status.textContent,bar:current.detail.loader.bar.value,
    hidden:current.detail.loader.root.hidden,rows:current.detail.body.rows.length,
    phases:detailEvents.map(event=>event.phase),attempts:detailReads.filter(read=>read.reason==='detail_no_progress').at(-1).attempts})`);
  assert.match(failed.text,/No forward progress/); assert.match(failed.text,/Retry or return to Sessions/);
  assert.equal(failed.attempts,3); assert.equal(failed.bar,0); assert.equal(failed.hidden,true); assert.equal(failed.rows,0);
  assert.ok(failed.phases.includes('retrying')); assert.ok(failed.phases.includes('failed'));
  const terminal = await fixture('detail-observe');
  await evaluate(`Promise.all(Array.from({length:25},()=>api('/api/detail',
    {action:'begin',token:current.detail.token,offset:0})))`);
  assert.equal((await fixture('detail-observe')).started,terminal.started,'failed polls cannot reset retry budget');
  measurements.failed_attempts = failed.attempts;
  measurements.retired_children = terminal.retired;
  checks.push('repeated actual 500ms pending reads end in typed no-progress failure after three attempts; no fake percent or empty success');
  for (const theme of ['classic','web']) for (const scheme of ['light','dark'])
    for (const width of [360,1366]) for (const zoom of [1,1.25,1.5]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]});
      await evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme)};document.body.style.zoom=${zoom}`);
      const facts = await evaluate(`(()=>{const view=current.detail,r=view.retry.getBoundingClientRect();return {
        overflow:document.documentElement.scrollWidth>innerWidth+1,retryWidth:r.width,
        statusRole:view.status.getAttribute('role'),live:view.loader.status.getAttribute('aria-live'),
        busy:view.scroll.getAttribute('aria-busy'),back:view.root.querySelector('a').getAttribute('href')};})()`);
      assert.equal(facts.overflow,false); assert.ok(facts.retryWidth>50); assert.equal(facts.statusRole,'status');
      assert.equal(facts.live,'polite'); assert.equal(facts.busy,'false'); assert.equal(facts.back,'#/sessions');
      layouts.push({theme,scheme,width,zoom,...facts});
    }
  await evaluate(`(async()=>{document.body.style.zoom=1;window.hiddenReads=detailReads.length;
    Object.defineProperty(document,'hidden',{configurable:true,value:true});await current.detail.poll();delete document.hidden})()`);
  assert.equal(await evaluate('detailReads.length'),await evaluate('hiddenReads'));
  await fixture('detail-recover');
  await evaluate(`current.detail.retry.focus();window.retryAt=performance.now()`);
  assert.equal(await evaluate('document.activeElement===current.detail.retry'),true,'Retry is keyboard focusable');
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r'});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  try {await until('current.detail?.data?.total===1001 && !current.detail.busy');}
  catch(error){throw new Error(error.message+'; retry='+JSON.stringify(await evaluate('detailReads.filter(read=>read.action==="retry")'))+
    '; lane='+JSON.stringify(await fixture('detail-observe')));}
  const recovery = await evaluate(`({rows:current.detail.body.rows.length,percent:current.detail.loader.bar.value,
    elapsed:performance.now()-retryAt,readyToDOM:detailApplied-detailReads.find(read=>read.result && read.at>retryAt).at,
    retryHidden:current.detail.retry.hidden,busy:current.detail.scroll.getAttribute('aria-busy'),
    requests:detailReads.filter(read=>read.action==='begin').length})`);
  assert.equal(recovery.rows,1001); assert.equal(recovery.percent,100); assert.equal(recovery.retryHidden,true);
  assert.equal(recovery.busy,'false'); assert.ok(recovery.readyToDOM<5000,JSON.stringify(recovery));
  measurements.recovery = recovery; measurements.capture = (await fixture('detail-observe')).metrics;
  recovery.publicationToDOM = await evaluate('performance.timeOrigin+detailApplied') - measurements.capture.published_at_ms;
  assert.ok(recovery.publicationToDOM>=0 && recovery.publicationToDOM<5000,JSON.stringify(recovery));
  checks.push('keyboard Retry uses a fresh eligible attempt, correct 1001 rows/100 only after DOM; hidden tab adds no HTTP; responsive actionable error layouts');
  await fixture('detail-blocked');
  const started = (await fixture('detail-observe')).started;
  await evaluate(`api('/api/detail',{action:'retry',token:current.detail.token})`);
  // Wait for actual admission, then leave the route while the child is blocked.
  await observeUntil(value=>value.started>started && value.active);
  await evaluate(`location.hash='#/sessions/root-0001'`);
  await until('current.detail?.id==="root-0001" && current.detail.data?.total===1');
  await evaluate(`history.back()`);
  await until('current.detail?.id==="root-0000"');
  await evaluate(`history.forward()`);
  await until('current.detail?.id==="root-0001" && current.detail.data?.total===1');
  assert.equal(await evaluate('current.detail.body.rows.length'),1);
  await evaluate(`current.detail.root.querySelector('a').focus()`);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r'});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await until('current.catalog?.data?.total===120');
  const closed = await observeUntil(value=>!value.active);
  assert.ok(closed.retired>terminal.retired,'leaving the blocked route joins its owned child');
  measurements.final_retired_children = closed.retired;
  checks.push('route retirement, Back/Forward and focused Show all sessions never apply the old root to its healthy peer');
  return {checks,layouts,measurements};
};
