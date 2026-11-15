// Shipped authenticated HTTP/controller in isolated headless Chromium; synthetic data only.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, until, fixture, command}) => {
  const checks = [], layouts = [];
  await fixture('catalog-large'); await fixture('catalog-index');
  await evaluate(`location.hash='#/sessions'`);
  await until('current.catalog?.data?.total===3217 && !current.catalog.busy');
  await evaluate(`window.catalog=current.catalog;window.normalApi=catalog.api;
    window.disabledChanges=0;window.pagerObserver=new MutationObserver(records=>disabledChanges+=records.length);
    pagerObserver.observe(catalog.pager,{subtree:true,attributes:true,attributeFilter:['disabled']});
    window.savedNext=catalog.next;window.savedTitle=catalog.body.rows[0].name;catalog.next.focus();
    window.passiveRelease=null;catalog.api=async(...args)=>{const data=await normalApi(...args);
      return args[1]?.action ? data : new Promise(resolve=>{passiveRelease=()=>resolve(data);});};
    window.passive=catalog.load();void 0`);
  await until('window.passiveRelease!==null');
  assert.equal(await evaluate('catalog.next.disabled'), false);
  await evaluate('passiveRelease();catalog.api=normalApi;passive');
  assert.equal(await evaluate('disabledChanges'), 0);
  assert.equal(await evaluate('savedNext===catalog.next && savedTitle===catalog.body.rows[0].name && document.activeElement===savedNext'), true);
  await evaluate('pagerObserver.disconnect()');
  checks.push('passive HTTP poll: zero disabled attribute changes; stable Next/title nodes and focus');
  for (const pages of [0, 1, 2, 3, 100]) {
    const actual = await evaluate(`(()=>{const data=structuredClone(catalog.data);data.total=${pages}*25;catalog.update(data);
      return {labels:[...catalog.numbers.querySelectorAll('button')].map(n=>Number(n.textContent)),
        current:catalog.numbers.querySelector('[aria-current=page]')?.textContent,
        ellipses:[...catalog.numbers.querySelectorAll('.page-gap')].every(n=>n.tagName==='SPAN'&&!n.hasAttribute('tabindex'))};})()`);
    assert.equal(actual.labels[0], 1); assert.equal(actual.labels.at(-1), Math.max(1, pages));
    assert.equal(new Set(actual.labels).size, actual.labels.length); assert.equal(actual.current, '1');
    assert.equal(actual.ellipses, true);
  }
  await evaluate('catalog.load()');
  await evaluate('catalog.pageButtons.get(129).click()');
  await until('catalog.data.offset===3200 && !catalog.operation && !catalog.busy');
  assert.equal(await evaluate('catalog.body.rows.length'), 17);
  assert.equal(await evaluate('catalog.numbers.querySelector("[aria-current=page]").textContent'), '129');
  await evaluate('catalog.pageButtons.get(1).click()');
  await until('catalog.data.offset===0 && !catalog.operation && !catalog.busy');
  await evaluate('history.back()');
  await until('catalog.data.offset===3200 && !catalog.operation && !catalog.busy');
  await evaluate('history.forward()');
  await until('catalog.data.offset===0 && !catalog.operation && !catalog.busy');
  checks.push('0/1/2/3/100-page DOM fixtures; unique first/last/neighbors, inert ellipses, aria-current; HTTP page129/17 rows, one-click page1 and Back/Forward');
  for (const width of [360, 1366]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
    const facts = await evaluate(`({overflow:document.documentElement.scrollWidth>innerWidth+1,
      pages:catalog.numbers.querySelectorAll('button').length})`);
    assert.equal(facts.overflow, false); layouts.push({width,...facts});
  }
  // Thirteen genuinely qualified rows on page four; twelve missing keys have already failed five times.
  await evaluate(`location.hash='#/sessions?period=today&sort=activity&direction=-1&offset=50&epoch='+catalog.data.epoch`);
  await until('catalog.data.offset===50 && !catalog.operation && !catalog.busy');
  await fixture('catalog-page-four-partial');
  await evaluate(`window.previousIds=[...catalog.body.rows].map(row=>row.dataset.id);
    window.previousHash=location.hash;window.oldEpoch=catalog.data.epoch;
     catalog.pageButtons.get(4).click()`);
  await until('catalog.operation?.completed===13');
  assert.equal(await evaluate('catalog.operation.failed'), false);
   assert.equal(await evaluate('catalog.status.textContent'), 'Loading Sessions page 4. Loading paused. Retrying…');
  assert.equal(await evaluate('catalog.operation.total'),25);
  assert.equal(await evaluate('catalog.pan.hidden'), false);
  assert.equal(await evaluate('catalog.retry===undefined'), true);
  // Hold one response beyond the actual 15s client deadline. The late answer must not apply.
  await evaluate(`catalog.retire();window.releaseLate=null;
    catalog.api=async(...args)=>{const data=await normalApi(...args);return args[1]?.action ? data :
      new Promise(resolve=>{releaseLate=()=>resolve(data);});};window.deadlineFlight=catalog.load();void 0`);
   await until('catalog.status.textContent.includes("Loading paused. Retrying") && !catalog.busy && window.releaseLate', 22000);
  assert.equal(await evaluate('catalog.operation.failed'), false);
  await evaluate('releaseLate();catalog.api=normalApi;deadlineFlight');
  assert.equal(await evaluate('catalog.data.offset'), 50);
  await fixture('fail');
  await until('api("/api/sessions",{token:catalog.token}).then(data=>data.state==="source_unavailable")');
  await evaluate(`window.recoveryCalls=0;window.inFlight=0;window.maxFlights=0;
    catalog.api=async(...args)=>{if(args[1]?.action)return normalApi(...args);
      recoveryCalls++;maxFlights=Math.max(maxFlights,++inFlight);
      try{return await normalApi(...args);}finally{inFlight--;}};
    catalog.poll()`);
  await new Promise(resolve=>setTimeout(resolve, 47000));
  assert.equal(await evaluate('catalog.operation.failed'), false);
  assert.equal(await evaluate('catalog.data.offset'), 50);
  const recovery = await evaluate('({calls:recoveryCalls,maxFlights,delay:catalog.retryDelay,completed:catalog.operation.completed})');
  assert.ok(recovery.calls <= 8 && recovery.calls >= 2, JSON.stringify(recovery));
  assert.equal(recovery.maxFlights, 1); assert.ok(recovery.delay<=30000); assert.equal(recovery.completed,13);
  await fixture('recover'); await fixture('catalog-index');
  await until('catalog.data.offset===75 && !catalog.operation && !catalog.busy', 40000);
  await evaluate('catalog.api=normalApi');
  checks.push({automatic_recovery:'page4 after 13/25, five prior key failures, real 15s deadline and 47s outage; no manual Retry',...recovery});
  // Irrecoverable identity/permission errors stop the operation and source interest.
  for (const reason of ['http_auth_failure', 'host_identity_changed', 'permission_denied', 'invalid_request']) {
    await evaluate(`catalog.terminal=false;catalog.api=async(_,value)=>{if(value.action)return {};throw new Error('${reason}');};
      location.hash='#/sessions?period=today&sort=name&direction=1'`);
    await until('catalog.operation?.failed && !catalog.busy');
     assert.match(await evaluate('catalog.status.textContent'), /Access unavailable|Could not finish/);
     assert.doesNotMatch(await evaluate('catalog.status.textContent'), new RegExp(reason));
    assert.doesNotMatch(await evaluate('catalog.status.textContent'),/Cancel/);
    assert.equal(await evaluate('catalog.pager.querySelectorAll("[aria-busy=true]").length'),0);
    await evaluate('catalog.api=normalApi;history.back()');
    await until('!catalog.operation && !catalog.busy');
    assert.equal(await evaluate('catalog.terminal'), true);
  }
  checks.push('terminal authorization/host identity/permission/invalid request stop retrying; actionable single banner, no Cancel/spinner; Back retains last-good page');
  await evaluate(`window.sample=Date.parse('2026-10-25T00:30:00Z');`);
  for (const timezoneId of ['America/New_York', 'Asia/Tokyo']) {
    await command('Emulation.setTimezoneOverride',{timezoneId});
    const labels = await evaluate(`[
      ReportView.activityHelp(sample,'Europe/Stockholm',Date.parse('2026-10-25T23:30Z')),
      ReportView.activityHelp(sample,'Europe/Stockholm',Date.parse('2026-10-25T12:00Z')),
      ReportView.activityHelp(sample,'Europe/Stockholm',Date.parse('2026-10-27T12:00Z')),
      ReportView.activityHelp(sample,'Europe/Stockholm',Date.parse('2026-11-01T12:00Z'))]`);
    assert.match(labels[0], /Yesterday$/); assert.match(labels[1], /Today$/);
    assert.match(labels[2], /Sunday$/); assert.doesNotMatch(labels[3], /Today|Yesterday|Sunday/);
    assert.match(labels[0], /GMT\+02:00/);
  }
  checks.push('configured-local Today/Yesterday/weekday/older exact-offset activity help, unaffected by two browser timezones');
  return {checks,layouts};
};
