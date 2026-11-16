// Actual native source observations, shipped LiveRuntime/SSE/auth/controller/DOM.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, until, fixture}) => {
  await until('liveValue?.catalog_hint');
  await fixture('arrival-seed');
  await evaluate("location.hash='#/sessions?period=all'");
  await until('current?.catalog?.data?.total===25 && !current.catalog.operation && !current.catalog.busy');
  await evaluate(`window.arrivalRequests=[];window.arrivalMax=0;window.arrivalFlights=0;
    const originalApi=current.catalog.api;
    current.catalog.api=async(...args)=>{
      if(args[1]?.action)return originalApi(...args);
      arrivalRequests.push({at:Date.now(),...args[1]});arrivalMax=Math.max(arrivalMax,++arrivalFlights);
      try{return await originalApi(...args);}finally{arrivalFlights--;}
    };
    window.quietViolations=[];
    new MutationObserver(()=>{if(!current.catalog.status.hidden)quietViolations.push('banner');})
      .observe(current.catalog.status,{attributes:true,childList:true,subtree:true});`);
  const measurements = [];
  for (let trial=0;trial<3;trial++) {
    // Establish the normal recovery deadline immediately before the source event.
    await until('!current.catalog.busy');
    await evaluate('current.catalog.poll()');
    await fixture('arrival-new-'+trial);
    const row = `document.querySelector('tr[data-id="ses_arrival_${trial}"]')`;
    await until(`${row}?.titleNode?.textContent==='Real source title ${trial}'`,4500);
    const titleMs = await evaluate('Date.now()');
    assert.deepEqual(await evaluate(`[...${row}.cells].slice(2).map(cell=>cell.textContent)`),Array(5).fill('Loading…'));
    assert.equal(await evaluate(`${row}.value.running`),false);
    await evaluate(`window.keptArrival=${row};window.keptArrivalLink=keptArrival.name;keptArrivalLink.focus();`);
    await fixture('arrival-running-'+trial);
    await until(`${row}?.value.running===true && current.catalog.body.firstChild===${row}`,4500);
    const runningMs = await evaluate('Date.now()');
    assert.equal(await evaluate('document.activeElement===keptArrivalLink && keptArrival.isConnected'),true);
    assert.equal(await evaluate('current.catalog.body.children.length'),25);
    const evidence = await fixture('arrival-observe'), key='ses_arrival_'+trial;
    measurements.push({trial, title_observation_to_dom_ms:titleMs-evidence.observed[key].title_ms,
      title_event_to_observation_ms:evidence.observed[key].title_ms-evidence.events[key].title_event_ms,
      running_observation_to_dom_ms:runningMs-evidence.observed[key].running_ms,
      running_event_to_observation_ms:evidence.observed[key].running_ms-evidence.events[key].running_event_ms});
    assert.ok(measurements.at(-1).title_observation_to_dom_ms<4500);
    assert.ok(measurements.at(-1).running_observation_to_dom_ms<4500);
    await evaluate('document.activeElement.blur()');
  }
  await fixture('arrival-hydrate');
  await until(`document.querySelector('tr[data-id="ses_arrival_2"]')?.metrics[2]?.textContent==='1'`);
  assert.equal(await evaluate(`document.querySelector('tr[data-id="ses_arrival_2"]')===keptArrival`),true);
  assert.equal(await evaluate('arrivalMax'),1);
  assert.deepEqual(await evaluate('quietViolations'),[]);
  assert.doesNotMatch(await evaluate('current.catalog.root.textContent'),/Refreshing/);
  await fixture('arrival-hold');
  await evaluate(`window.stableArrival=document.querySelector('tr[data-id="ses_fixture_00000"]');
    window.stableModel=stableArrival.metrics[0];stableModel.focus();
    const range=document.createRange();range.selectNodeContents(stableArrival.titleNode);
    getSelection().removeAllRanges();getSelection().addRange(range);
    window.arrivalSelection=getSelection().toString();window.scrollTo(0,100);window.arrivalScroll=scrollY;`);
  await until('document.querySelector("#context-help")?.matches(":popover-open")');
  await fixture('arrival-new-3');
  await until('document.querySelector("tr[data-id=ses_arrival_3]")');
  assert.equal(await evaluate(`stableArrival.isConnected && document.activeElement===stableModel &&
    getSelection().toString()===arrivalSelection && Math.abs(scrollY-arrivalScroll)<2 &&
    document.querySelector("#context-help").matches(":popover-open")`),true);
  assert.equal(await evaluate('current.catalog.body.children.length'),25);
  await evaluate(`window.arrivalLabelChanges=0;
    new MutationObserver(records=>arrivalLabelChanges+=records.length)
      .observe(current.catalog.label,{childList:true,characterData:true,subtree:true});`);
  const before = await evaluate('arrivalRequests.length');
  await evaluate('new Promise(resolve=>setTimeout(resolve,6200))');
  const after = await evaluate('arrivalRequests.length');
  assert.ok(after-before<=2,'unchanged Live clock publications do not produce HTTP churn');
  assert.equal(await evaluate('arrivalLabelChanges'),0,'unchanged polite pager text is not rewritten/announced');
  const source = await fixture('arrival-observe');
  return {checks:['three native-V2 title arrivals and qualified prompt starts before 5s recovery, scalars withheld',
    'title and five Loading cells; Watch-qualified running top/yellow; in-place real summary hydration',
    'focus/keyed rows/25 visible retained; silent banner; one in-flight; unchanged Live frames bounded by recovery'],
    measurements,requests:await evaluate('arrivalRequests.length'),source};
};
