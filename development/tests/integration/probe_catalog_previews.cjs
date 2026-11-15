// Actual authenticated Sessions + Live, native headless PiP, DOM and AX semantics.
const assert=require('node:assert/strict');
module.exports=async({fixture,evaluate,until,command,sessionId,open,close,evidence})=>{
  const initial=await fixture('preview-counts');
  assert.equal(initial.leases,0);
  const started=Date.now();
  await fixture('preview-cold');await open();
  await until('miniWatch.view.promptRows.size===5');
  const cold=Date.now()-started;
  assert.equal((await fixture('preview-counts')).reads,0,'cold first paint performs no source hydration');
  assert.equal((await fixture('preview-counts')).leases,0,'no Sessions tab/lease is required');
  const rows=()=>evaluate(`[...miniWatch.view.body.rows].map(r=>({id:r.dataset.id,
    cells:[...r.cells].map(c=>c.textContent),aria:r.getAttribute('aria-label'),className:r.className}))`);
  for(const row of await rows()){
    assert.match(row.cells[1],/^Synthetic/);assert.equal(row.cells[2],'Loading…');
    assert.equal(row.cells[3],'Loading…');assert.equal(row.cells[4],'Loading…');assert.equal(row.className,'');
    assert.doesNotMatch(row.aria,/Prompt|Completed|Ended|Running/);
  }
  const bounds=await evaluate('[miniWatch.window.outerWidth,miniWatch.window.outerHeight]');
  const key=await evaluate(`(()=>{window.previewNode=miniWatch.view.body.rows[0];return previewNode.dataset.id})()`);
  await evaluate(`miniWatch.view.prompts.focus()`);
  await fixture('preview-warm');
  await until(`[...miniWatch.view.body.rows].every(r=>r.cells[3].textContent!=='Loading…')`);
  assert.equal(await evaluate(`miniWatch.view.promptRows.get(${JSON.stringify(key)})===previewNode`),true);
  assert.equal(await evaluate(`miniWatch.window.document.activeElement===miniWatch.view.prompts`),true);
  const warmCounts=await fixture('preview-counts');
  assert.equal(warmCounts.reads,25,'only the requested Sessions slice was qualified');
  await close();await evaluate(`location.hash='#/sessions'`);
  await until(`current?.catalog?.data?.view.session_usage.length===25&&!current.catalog.data.pending_sort`);
  const sessionsAt=Date.now();
  const firstFive=await evaluate('current.catalog.data.view.session_usage.slice(0,5).map(r=>r.session_id)');
  const sessionsCells=await evaluate('current.catalog.body.rows[0].textContent');
  assert.match(sessionsCells,/Synthetic/);
  await fixture('preview-warm');await open();
  await until('miniWatch.view.promptRows.size===5');
  const painted=Date.now();
  assert.deepEqual((await rows()).map(row=>row.id),firstFive.slice().reverse());
  assert.equal((await fixture('preview-counts')).reads,warmCounts.reads,'warm Sessions facts are reused');
  const upgrade=firstFive[0];
  const oldTotal=await evaluate(`(()=>{window.upgradeNode=miniWatch.view.promptRows.get(${JSON.stringify(upgrade)});
    return upgradeNode.cells[3].textContent})()`);
  await fixture('preview-upgrade');
  await until(`miniWatch.view.promptRows.get(${JSON.stringify(upgrade)}).cells[2].textContent!=='Loading…'`);
  assert.equal(await evaluate(`miniWatch.view.promptRows.get(${JSON.stringify(upgrade)})===upgradeNode`),true);
  assert.equal(await evaluate('upgradeNode.cells[3].textContent'),oldTotal,'qualified catalog total survives rich upgrade');
  assert.match(await evaluate('upgradeNode.getAttribute("aria-label")'),/Completed/);
  assert.equal(await evaluate('liveValue.view.history_epoch'),0,'one real representative is not global proof');
  await fixture('preview-two-running');
  await until('miniWatch.view.promptRows.has("preview-running-1")');
  assert.equal((await rows()).filter(row=>row.id.startsWith('root-')).length,3);
  assert.equal((await rows()).length,5);
  const pip=await (async()=>{for(const target of (await command('Target.getTargets')).targetInfos.filter(t=>t.type==='page')){
    const attached=await command('Target.attachToTarget',{targetId:target.targetId,flatten:true});
    if(await evaluate('!!document.querySelector(".mini-watch")',false,attached.sessionId))return attached.sessionId;
  }})();
  const ax=(await command('Accessibility.getFullAXTree',{},pip)).nodes.filter(n=>!n.ignored).map(n=>n.name?.value||'').join('\n');
  assert.match(ax,/Synthetic/);assert.doesNotMatch(ax,/Loading earlier sessions|checked|3217|global proof/);
  assert.deepEqual(await evaluate('[miniWatch.window.outerWidth,miniWatch.window.outerHeight]'),bounds);
  assert.equal(await evaluate('probeStreams'),1);
  evidence.previewTiming={coldOpenToFiveTitlesMs:cold,sessionsVisibleToMiniReopenMs:painted-sessionsAt,
    warmReads:warmCounts.reads,checked:20,total:3217};
  evidence.checks.push('Catalog previews: cold without Sessions/reads, warm actual 25-row Sessions reuse, independent Loading cells, neutral AX, keyed scalar/real-prompt upgrade with retained Total/focus, 0/2 running, one SSE, stable native PiP bounds');
};
