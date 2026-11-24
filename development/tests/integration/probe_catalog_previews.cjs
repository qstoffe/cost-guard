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
    cells:[...r.cells].map(c=>c.textContent),pending:[...r.cells].slice(2).map(c=>
      c.querySelector('.metric-spinner')?.getAttribute('aria-label')),
    aria:r.getAttribute('aria-label'),className:r.className}))`);
  const layout=()=>evaluate(`(()=>{
    const v=miniWatch.view,p=v.prompts,t=v.body.parentNode,rect=n=>n.getBoundingClientRect();
    return {columns:[...t.tHead.rows[0].cells].map(c=>rect(c).width),
      heights:[...v.body.rows].map(r=>rect(r).height),pan:[p.scrollWidth,p.clientWidth,p.scrollHeight,p.clientHeight]};
  })()`);
  for(const row of await rows()){
    assert.match(row.cells[1],/^Synthetic/);assert.deepEqual(row.cells.slice(2),['','','']);
    assert.deepEqual(row.pending,['Loading prompt CCost','Loading total CCost','Loading context']);
    assert.equal(row.className,'');
    assert.doesNotMatch(row.aria,/Prompt|Completed|Ended|Running/);
  }
  const coldGeometry=await layout();
  const key=await evaluate(`(()=>{window.previewNode=miniWatch.view.body.rows[0];return previewNode.dataset.id})()`);
  await evaluate(`miniWatch.view.prompts.focus()`);
  await fixture('preview-warm');
  await until(`[...miniWatch.view.body.rows].every(r=>r.cells[3].textContent!=='')`);
  assert.deepEqual(await layout(),coldGeometry,'cold to warm Total keeps column, row and scroll geometry');
  assert.equal(await evaluate(`miniWatch.view.promptRows.get(${JSON.stringify(key)})===previewNode`),true);
  assert.equal(await evaluate(`miniWatch.window.document.activeElement===miniWatch.view.prompts`),true);
  const warmCounts=await fixture('preview-counts');
  assert.equal(warmCounts.reads,25,'only the requested Sessions slice was qualified');
  await close();await evaluate(`location.hash='#/sessions'`);
  await until(`current?.catalog?.data?.view.session_usage.length===25&&!current.catalog.data.pending_sort`);
  const sessionsAt=Date.now();
  const shortlist=await evaluate('current.catalog.data.view.session_usage.slice(0,5).map(r=>r.session_id)');
  const sessionsCells=await evaluate('current.catalog.body.rows[0].textContent');
  assert.match(sessionsCells,/Synthetic/);
  await fixture('preview-warm');await open();
  await until('miniWatch.view.promptRows.size===5');
  const bounds=await evaluate('[miniWatch.window.outerWidth,miniWatch.window.outerHeight]');
  const painted=Date.now();
  assert.deepEqual((await rows()).map(row=>row.id).sort(),[...shortlist].sort(),'both views select the same sessions');
  assert.equal((await fixture('preview-counts')).reads,warmCounts.reads,'warm Sessions facts are reused');
  const upgrade=shortlist[0];
  const oldTotal=await evaluate(`(()=>{window.upgradeNode=miniWatch.view.promptRows.get(${JSON.stringify(upgrade)});
    return upgradeNode.cells[3].textContent})()`);
  await fixture('preview-upgrade');
  await until(`miniWatch.view.promptRows.get(${JSON.stringify(upgrade)}).cells[2].textContent!==''`);
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
  assert.match(ax,/Loading context/);assert.match(ax,/Synthetic/);
  assert.doesNotMatch(ax,/Loading earlier sessions|checked|3217|global proof|Reading…|Retrying|Unavailable|Not Applicable/);
  await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]},pip);
  assert.equal(await evaluate(`(()=>{const s=document.querySelector('.metric-spinner'),css=getComputedStyle(s);
    return css.animationName==='none' && css.pointerEvents==='none' && s.tabIndex===-1 &&
      s.getBoundingClientRect().width>0 && !s.closest('[aria-live]');})()`,false,pip),true);
  assert.deepEqual(await evaluate('[miniWatch.window.outerWidth,miniWatch.window.outerHeight]'),bounds);
  await fixture('preview-empty');
  const emptyRow=`miniWatch.view.promptRows.get('root-3217')`, cell=`${emptyRow}?.cells[4]`;
  await until(`${cell}?.textContent==='?'`);
  assert.deepEqual((await rows()).find(row=>row.id==='root-3217').cells.slice(2),['?','','?']);
  await evaluate(`window.emptyNode=${emptyRow}`);
  const container=`miniWatch.view.doc.getElementById('context-help')`;
  const point=await evaluate(`(()=>{const r=${cell}.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  const keyEvent=(key,code)=>command('Input.dispatchKeyEvent',{type:'keyDown',key,code:key,windowsVirtualKeyCode:code},pip);
  await command('Page.bringToFront',{},pip);
  await keyEvent('Tab',9);
  await evaluate(`${cell}.focus()`);
  await until(`${container}?.matches(':popover-open')`);
  assert.equal(await evaluate(`${container}.textContent`),'No recorded context is available for this session.');
  await keyEvent('Escape',27);
  await evaluate(`${cell}.blur()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},pip);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},pip);
  await until(`${container}?.matches(':popover-open')`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},pip);
  await until(`${container}.hidden`);
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{...point,id:1,radiusX:1,radiusY:1,force:1}]},pip);
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},pip);
  await until(`${container}?.matches(':popover-open')`);
  assert.equal(await evaluate(`${container}.textContent`),'No recorded context is available for this session.');
  await fixture('preview-revise');
  await until(`${cell}?.querySelector('.metric-spinner') && ${container}.hidden`);
  assert.equal(await evaluate(`${cell}.hasAttribute('aria-describedby')`),false);
  assert.equal(await evaluate(`${emptyRow}===emptyNode`),true);
  assert.equal(await evaluate('probeStreams'),1);
  evidence.previewTiming={coldOpenToShortlistMs:cold,sessionsVisibleToMiniReopenMs:painted-sessionsAt,
    warmReads:warmCounts.reads,checked:20,total:3217};
  evidence.layouts.push({case:'preview-cold-to-warm',...coldGeometry});
  evidence.checks.push('Catalog previews: cold without Sessions/reads, warm 25-row Sessions reuse, combined five rows including Running, labelled spinners, keyed rich upgrade, retained Total/focus, stable native bounds, qualified absence and revision withdrawal');
};
