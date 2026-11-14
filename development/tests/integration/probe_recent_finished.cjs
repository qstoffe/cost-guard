// Controlled canonical 5,000-root source through shipped SSE, Full DOM and real PiP.
const assert = require('node:assert/strict');
module.exports = async ({fixture,evaluate,until,open,close,command,sessionId,targetId,checks,evidence}) => {
  await close();await fixture('recent-loading');
  await until(`liveValue.view.history_total===5000 && liveValue.view.history_epoch===0`);
  await open();
  const pending = async () => {
    assert.equal(await evaluate(`liveValue.view.history_state`),'loading');
    assert.equal(await evaluate(`liveValue.view.history_epoch`),0);
    assert.equal(await evaluate(`document.querySelector('.watch-history').textContent.includes('Loading earlier sessions…')`),
      await evaluate(`!document.querySelector('.watch-history article')`));
  };
  await pending();
  let dimensions = await evaluate(`[miniWatch.window.outerWidth,miniWatch.window.outerHeight]`);
  const latency = [], stages = [];
  for(let index=5000;index<5020;index++) {
    const began=performance.now(),result=await fixture(`recent-finish-${index}-1`);
    const published=performance.now();
    await until(`miniWatch.view.promptRows.has('root-${index}') && document.querySelector('.watch-history article[data-session="root-${index}"]')`);
    await evaluate(`new Promise(resolve=>miniWatch.window.requestAnimationFrame(()=>miniWatch.window.requestAnimationFrame(resolve)))`);
    const painted=performance.now();
    latency.push({source_to_publication_ack_ms:published-began,publication_ack_to_both_painted_ms:painted-published,total_ms:painted-began});
    stages.push(result.timings.at(-1));
    await pending();
    assert.deepEqual(await evaluate(`[miniWatch.window.outerWidth,miniWatch.window.outerHeight]`),dimensions);
    const ids=await evaluate(`[...miniWatch.view.promptRows.keys()]`);
    assert.equal(ids.length,Math.min(5,index-4999));
    assert.equal(new Set(ids).size,ids.length);
    assert.deepEqual(await evaluate(`liveValue.view.recent_finished_cards.map(c=>[c.session_id,c.rows[0].prompt.event_id,c.rows[0].prompt.completed_at_ms])`),
      await evaluate(`miniWatch.observations.view.recent_finished_cards.map(c=>[c.session_id,c.rows[0].prompt.event_id,c.rows[0].prompt.completed_at_ms])`));
  }
  await close();await open(); // Opening after an already completed fast prompt.
  assert.equal(await evaluate(`miniWatch.view.promptRows.has('root-5019')`),true);
  await evaluate(`location.hash='#/accounts'`);
  await until(`!document.querySelector('.watch-view')`);
  assert.equal(await evaluate(`miniWatch.view.promptRows.has('root-5019')`),true);
  await evaluate(`location.hash='#/watch'`);
  await until(`!!document.querySelector('.watch-history article[data-session="root-5019"]')`);
  await evaluate(`miniWatch.window.dispatchEvent(new Event('blur'));miniWatch.render()`);
  assert.equal(await evaluate(`miniWatch.view.promptRows.size`),5);
  // Same-instance HTTP resync supplies the identical detached recent population.
  await evaluate(`(async()=>{const snapshot=await api('/api/live');window.recentReconnect=snapshot.values.live;
    miniWatch.update(recentReconnect);})()`);
  assert.deepEqual(await evaluate(`recentReconnect.view.recent_finished_cards.map(c=>c.session_id)`),
    await evaluate(`[...miniWatch.view.promptRows.keys()]`));
  const owner=await command('Browser.getWindowForTarget',{targetId});
  await command('Browser.setWindowBounds',{windowId:owner.windowId,bounds:{windowState:'minimized'}});
  await fixture('recent-finish-5020-1');
  await until(`miniWatch.view.promptRows.has('root-5020')`);
  await command('Browser.setWindowBounds',{windowId:owner.windowId,bounds:{windowState:'normal'}});
  // Reopening/Fit and explicit native minimize/restore may choose new bounds;
  // compare passive publications only within this same restored opening.
  dimensions = await evaluate(`[miniWatch.window.outerWidth,miniWatch.window.outerHeight]`);
  await command('Network.enable',{},sessionId);
  const network=offline=>command('Network.emulateNetworkConditions',{offline,latency:0,
    downloadThroughput:-1,uploadThroughput:-1},sessionId);
  await network(true);
  assert.equal(await evaluate(`miniWatch.view.promptRows.has('root-5020')`),true,'offline retains qualified recent data');
  await network(false);
  await evaluate(`liveConnection.resync()`);
  await fixture('recent-finish-5021-1');
  await until(`miniWatch.view.promptRows.has('root-5021')`);
  await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:'dark'}]},sessionId);
  await evaluate(`(async()=>{applySettings(await api('/api/settings/theme',{theme:'web'}));
    applySettings(await api('/api/settings/ccost',{ccostDisplayUnit:'usd'}));})()`);
  assert.equal(await evaluate(`miniWatch.view.promptRows.size`),5);
  await fixture('recent-finish-5019-2');
  await until(`miniWatch.view.promptRows.get('root-5019')?.getAttribute('aria-label')?.includes('Prompt 2')`);
  await evaluate(`window.recentFull=document.querySelector('.watch-history article[data-session="root-5019"]');
    window.recentMini=miniWatch.view.promptRows.get('root-5019');
    document.querySelector('.watch-earlier').open=true;
    recentFull.querySelector('h3 a').focus({preventScroll:true});window.recentFocus=document.activeElement;`);
  await fixture('recent-converge');
  await until(`liveValue.view.history_state==='observed' && liveValue.view.recent_finished_cards.length===0`);
  assert.equal(await evaluate(`document.querySelectorAll('.watch-history article').length`),5);
  assert.equal(await evaluate(`recentFull===document.querySelector('.watch-history article[data-session="root-5019"]') && recentMini===miniWatch.view.promptRows.get('root-5019') && document.activeElement===recentFocus`),true);
  assert.equal(await evaluate(`document.querySelector('.watch-history').textContent.includes('Loading earlier sessions')`),false);
  assert.deepEqual(await evaluate(`[miniWatch.window.outerWidth,miniWatch.window.outerHeight]`),dimensions);
  await close();await open();
  assert.equal(await evaluate(`miniWatch.view.promptRows.size`),5);
  const summary=rows=>Object.fromEntries(Object.keys(rows[0]).filter(k=>k.endsWith('_ms')).map(key=>{
    const values=rows.map(row=>row[key]).sort((a,b)=>a-b);
    return [key,{p50:values[Math.ceil(values.length*.5)-1],p95:values[Math.ceil(values.length*.95)-1]}];
  }));
  evidence.recentFinished={samples:latency.length,stages:summary(stages),transport_and_paint:summary(latency),
    clockQualification:'Synthetic source duration 300ms; wall-clock stage/transport/paint measurements are separate, not private incident latency.'};
  checks.push('5,000 cold roots: 20 never-running source-confirmed prompts in Full/PiP before historical proof; five-slot cap, repeated session, keyed convergence/focus, early/late reopen, route away/back, blur, headless owner minimization, offline/resync, theme/unit change, no passive resize');
  await close();
};
