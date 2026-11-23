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
    assert.deepEqual(await evaluate(`[...${row}.cells].slice(2).map(cell=>[cell.textContent,
      cell.querySelector('.metric-spinner')?.getAttribute('aria-label')])`),
      ['model','CCost','prompt count','duration','context'].map(label=>['','Loading '+label]));
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
  // Select a retained ordinary row on the current page, not a fixed ID
  // that newer source history may legitimately have displaced to page two.
  await evaluate(`window.stableArrival=[...current.catalog.body.rows].find(
      row=>row.dataset.id.startsWith('ses_fixture_') && row.metrics[0].tabIndex===0);
    window.stableModel=stableArrival.metrics[0];stableModel.focus();
    const range=document.createRange();range.selectNodeContents(stableArrival.titleNode);
    getSelection().removeAllRanges();getSelection().addRange(range);
    window.arrivalSelection=getSelection().toString();window.scrollTo(0,100);window.arrivalScroll=scrollY;`);
  await until('document.querySelector("#context-help")?.matches(":popover-open")');
  await fixture('arrival-new-3');
  await until('document.querySelector("tr[data-id=ses_arrival_3]")');
  assert.deepEqual(await evaluate(`({connected:stableArrival.isConnected,focus:document.activeElement===stableModel,
    selection:getSelection().toString()===arrivalSelection,scroll:Math.abs(scrollY-arrivalScroll)<2,
    help:document.querySelector("#context-help").matches(":popover-open")})`),
    {connected:true,focus:true,selection:true,scroll:true,help:true});
  assert.equal(await evaluate('current.catalog.body.children.length'),25);
  await evaluate(`window.arrivalLabelChanges=0;
    new MutationObserver(records=>arrivalLabelChanges+=records.length)
      .observe(current.catalog.label,{childList:true,characterData:true,subtree:true});`);
  const before = await evaluate('arrivalRequests.length');
  await evaluate('new Promise(resolve=>setTimeout(resolve,6200))');
  const after = await evaluate('arrivalRequests.length');
  assert.ok(after-before<=2,'unchanged Live clock publications do not produce HTTP churn');
  assert.equal(await evaluate('arrivalLabelChanges'),0,'unchanged pager text is not rewritten');
  const source = await fixture('arrival-observe');
  await fixture('arrival-seed');
  await evaluate("location.hash='#/sessions?period=today'");
  await until('current.catalog?.data?.period==="today" && !current.catalog.operation');
  const warm = await evaluate('current.catalog.data.epoch');
  await evaluate("location.hash='#/watch'");
  await until('current?.section==="watch"');
  await fixture('arrival-burst-100');
  await until('liveValue?.view?.earlier_previews?.some(row=>row.session_id==="ses_arrival_100")');
  await evaluate("document.querySelector('a[href=\"#/sessions\"]').click()");
  await until('current?.catalog?.data?.epoch!=='+JSON.stringify(warm)+
    ' && document.querySelector("tr[data-id=ses_arrival_100]")?.value.catalog_activity_ms>0');
  await evaluate(`window.burstRoots=Array.from(current.catalog.body.rows).slice(0,3);
    window.burstClocks=burstRoots.map(row=>row.activity.textContent);
    window.removedRunning=[];
    new MutationObserver(records=>{for(const record of records)for(const row of record.removedNodes)
      if(burstRoots.includes(row)) removedRunning.push(row.dataset.id);}).observe(current.catalog.body,{childList:true});
    burstRoots[0].name.focus({preventScroll:true});
    const selection=getSelection(), span=burstRoots[0].titleNode.firstChild;
    selection.setBaseAndExtent(span,0,span,span.length);
    window.burstSelection=selection.toString();window.burstScroll=scrollY;`);
  const layout = () => evaluate(`(()=>{
    const view=current.catalog,rect=node=>node.getBoundingClientRect();
    return {columns:view.headers.map(({th})=>rect(th).width),
      heights:[...view.body.rows].map(row=>rect(row).height),
      pan:[view.pan.scrollWidth,view.pan.clientWidth,view.pan.scrollHeight,view.pan.clientHeight]};
  })()`);
  const burstGeometry=await layout();
  assert.deepEqual(await evaluate('burstRoots.map(row=>row.dataset.id)'),['ses_arrival_2','ses_arrival_1','ses_arrival_0']);
  await fixture('arrival-omit-running-hint');
  const burstMeasurements = [];
  const beforeBurst = (await fixture('arrival-observe')).metrics.attempts;
  for (let burst=1;burst<=9;burst++) {
    const key = 'ses_arrival_'+(100+25*burst);
    await fixture('arrival-burst-'+(100+25*burst));
    await until(`document.querySelector("tr[data-id=${key}]")?.value.catalog_activity_ms>0`,10000);
    burstMeasurements.push({key, visible:await evaluate('Date.now()')});
    assert.equal(await evaluate('current.catalog.body.rows.length'),25);
    assert.equal(await evaluate('current.catalog.next.disabled'),false);
    const state = await evaluate(`({
      running: [...current.catalog.body.rows].filter(row=>row.value.running).map(row=>row.dataset.id),
      retained: burstRoots.every((row,i)=>current.catalog.body.rows[i]===row && row.activity.textContent===burstClocks[i]),
      focus: document.activeElement===burstRoots[0].name,
      selection: getSelection().toString()===burstSelection, scroll: scrollY===burstScroll
    })`);
    assert.deepEqual(state,{running:['ses_arrival_2','ses_arrival_1','ses_arrival_0'],
      retained:true,focus:true,selection:true,scroll:true});
    assert.deepEqual(await layout(),burstGeometry);
  }
  assert.deepEqual(await evaluate('removedRunning'),[]);
  assert.deepEqual(await evaluate('quietViolations'),[]);
  const sustained = await fixture('arrival-observe');
  assert.equal(sustained.metrics.attempts,beforeBurst,'scalar acquisition remained held throughout the burst');
  for (const item of burstMeasurements) item.observation_to_dom_ms = item.visible - sustained.observed[item.key].title_ms;
  await evaluate(`window.firstBurstPage=[...current.catalog.body.rows].map(row=>row.dataset.id);
    current.catalog.next.click();`);
  await until('current.catalog?.data?.offset===25 && !current.catalog.operation');
  assert.match(await evaluate('current.catalog.label.textContent'),/catalog candidates \(preliminary\)/);
  assert.equal(await evaluate('[...current.catalog.body.rows].some(row=>firstBurstPage.includes(row.dataset.id))'),false);
  await evaluate('history.back()');
  await until('current.catalog?.data?.offset===0 && !current.catalog.operation');
  assert.equal(await evaluate('JSON.stringify([...current.catalog.body.rows].map(row=>row.dataset.id))===JSON.stringify(firstBurstPage)'),true);
  const {finish_ms}=await fixture('arrival-finish');
  const finished=`document.querySelector('tr[data-id="ses_arrival_1"]')`;
  await until(`${finished} && !${finished}.value.running`,4500);
  assert.deepEqual(await evaluate('Array.from(current.catalog.body.rows).filter(row=>row.value.running).map(row=>row.dataset.id)'),
    ['ses_arrival_2','ses_arrival_0']);
  assert.equal(await evaluate(`${finished}===current.catalog.body.rows[2] &&
    ${finished}.value.last_activity_ms===null && ${finished}.activity.textContent.endsWith('*')`),true);
  await fixture('arrival-hydrate');
  // The scalar queue still contains the 250 burst arrivals. Its eventual
  // qualification is distinct from prompt removal, which was bounded above.
  await until(`${finished}?.value.last_activity_ms===${finish_ms} && !${finished}.activity.textContent.endsWith('*')`,100000);
  return {checks:['three native-V2 title arrivals and qualified prompt starts before 5s recovery, scalars withheld',
     'title and five labelled spinners; Watch-qualified running top/yellow; in-place real summary hydration',
     'focus/keyed rows/25 visible retained; silent banner; one in-flight; unchanged Live frames bounded by recovery',
     'warm Today return and 250 nonrunning inserts with stable column/row/scroll geometry; alternating lost hints, no scalar reads; provisional paging and Back',
     'explicit prompt end removes Running before scalar qualification; provisional placement then exact source finish'],
    measurements, burst_ms:burstMeasurements.map(item=>item.observation_to_dom_ms),
    requests:await evaluate('arrivalRequests.length'),source};
};
