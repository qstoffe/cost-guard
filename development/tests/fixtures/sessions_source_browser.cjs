// Read-only installed-source observation: never export row titles, IDs or transcripts.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, until}) => {
  await evaluate(`window.sourceTrace=[];window.sourceApi=api;
    window.hashEvents=[];addEventListener('hashchange',()=>hashEvents.push(location.hash));
    location.hash='#/sessions'`);
  await until('current.catalog?.data?.total>0');
  await evaluate(`window.sourceCatalog=current.catalog;window.originalSourceApi=sourceCatalog.api;
    sourceCatalog.api=async(...args)=>{const start=performance.now();const value=await originalSourceApi(...args);
      if(!args[1]?.action)sourceTrace.push({ms:Math.round(performance.now()),request_ms:Math.round(performance.now()-start),
        requested:args[1].sort,applied:value.sort,pending:value.pending_sort,state:value.state,
        generation:value.progress.generation,phase:value.progress.phase,completed:value.progress.completed,total:value.progress.total,
        status:value.progress.status,reason:value.progress.reason,metrics:value.progress.metrics,work:value.progress.work,
        revalidating:value.progress.revalidating,running_rows:value.view.session_usage.filter(row=>row.running).length,
        controller:sourceCatalog.generation,token_same:args[1].token===value.token,
        epoch_same:args[1].epoch===value.epoch,aborted:args[2]?.aborted??false});return value;};
    sourceCatalog.headers[3].th.querySelector('button').click()`);
  await until('sourceCatalog.sort==="ccost"');
  const started = Date.now(), samples=[];
  while (Date.now()-started<135000) {
    samples.push(await evaluate(`({elapsed:Math.round(performance.now()),hash:location.hash,
      requested:sourceCatalog.sort,applied:sourceCatalog.data.sort,controller:sourceCatalog.generation,
      attached:sourceCatalog.attached,host_kind:hostState.kind,host_terminal:hostState.terminal,
      operation:sourceCatalog.operation?{kind:sourceCatalog.operation.kind,rebases:sourceCatalog.operation.rebases,
        failed:sourceCatalog.operation.failed,completed:sourceCatalog.operation.completed}:null,
      loader_hidden:sourceCatalog.loader.root.hidden,table_hidden:sourceCatalog.pan.hidden,
      stage:sourceCatalog.loader.stage.textContent,heading:sourceCatalog.task?.textContent,
      loader_y:Math.round(sourceCatalog.loader.root.getBoundingClientRect().top),
      viewport:innerHeight})`));
    if(samples.at(-1).operation?.failed || !samples.at(-1).operation || !samples.at(-1).attached || samples.at(-1).host_terminal) break;
    await new Promise(resolve=>setTimeout(resolve,1000));
  }
  return {source:'installed V2 read-only; no source mutations or inference',seconds:Math.round((Date.now()-started)/1000),
    requests:await evaluate('sourceTrace'),hash_events:await evaluate('hashEvents'),samples};
};

// Real host HTTP expiry (unknown client token), not a synthetic source or API reply.
module.exports.recovery = async ({evaluate, until, command}) => {
  const forbidden = /previous catalog expired|showing the latest first page|Refreshing sessions/i;
  await evaluate(`location.hash='#/sessions'`);
  await until('current.catalog?.data?.total>0 && !current.catalog.busy');
  await evaluate(`window.recoveryCatalog=current.catalog;window.recoveryRequests=0;window.recoveryExpiries=0;
    window.recoveryApi=recoveryCatalog.api;recoveryCatalog.api=async(...args)=>{
      if(!args[1]?.action)recoveryRequests++;
      try{return await recoveryApi(...args);}catch(error){if(!args[1]?.action && error.message==='catalog_expired')recoveryExpiries++;throw error;}
    }`);
  const total = await evaluate('recoveryCatalog.data.total');
  const pages = [];
  for (const offset of total>50 ? [0,50] : [0]) {
    if(offset) {
      await evaluate('location.hash=recoveryCatalog.next.destination');
      // Real page preparation can make measured source progress beyond the
      // synthetic driver's 30-second wait. This changes no product deadline.
      await until(`recoveryCatalog.data.offset===${offset} && !recoveryCatalog.busy`,120000);
    }
    const result = await evaluate(`(async()=>{
      const view=recoveryCatalog,rows=[...view.body.children],epoch=view.data.epoch;
      const link=rows[0].querySelector('a');link.focus();const scroll=scrollY;
      view.interest(false);view.token='00000000000000000000000000000000';
      const pending=view.poll();
      const retained=view.body.firstChild===rows[0] && !view.pan.hidden && !view.pager.hidden;
      await pending;
      const data=view.data;
      return {retained,offset:data.offset,newEpoch:data.epoch!==epoch,token:data.token===view.token,
        coherent:[...view.body.children].every((row,index)=>row.dataset.id===data.view.session_usage[index].session_id),
        rowCount:view.body.children.length,pageOne:/Page 1 of/.test(view.label.textContent),
        header:view.headers[0].th.getAttribute('aria-sort'),url:location.hash,
        focus:document.activeElement===link,scroll:scrollY===scroll,
        status:view.status.textContent,recovering:!!view.recovering,rebased:!!view.rebased};})()`);
    assert.equal(result.retained,true);assert.equal(result.offset,0);assert.equal(result.newEpoch,true);
    assert.equal(result.token,true);assert.equal(result.coherent,true);assert.equal(result.rowCount,Math.min(50,total));
    assert.equal(result.pageOne,true);assert.equal(result.header,'descending');assert.equal(result.url,'#/sessions?sort=activity&direction=-1');
    if(!offset)assert.equal(result.focus,true);
    assert.equal(result.scroll,true);assert.equal(result.status,'');assert.equal(result.recovering,false);assert.equal(result.rebased,false);
    for(let poll=0;poll<3;poll++) {
      await evaluate('recoveryCatalog.poll()');
      assert.equal(await evaluate('recoveryCatalog.status.textContent'), '');
      const ax=(await command('Accessibility.getFullAXTree')).nodes.filter(node=>!node.ignored).map(node=>node.name?.value||'').join('\n');
      assert.doesNotMatch(ax,forbidden);
    }
    pages.push({requestedOffset:offset,...result});
  }
  const before=await evaluate('recoveryRequests');
  await until(`recoveryRequests>${before} && !recoveryCatalog.busy`);
  await evaluate(`Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));
    Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'))`);
  await until('!recoveryCatalog.busy');
  await evaluate(`location.hash='#/settings'`);await until(`current.section==='settings'`);
  await evaluate(`location.hash='#/sessions'`);await until('current.catalog?.data && !current.catalog.busy');
  assert.equal(await evaluate('current.catalog.status.textContent'),'');
  assert.equal(await evaluate('recoveryExpiries'),pages.length);
  return {source:'installed read-only source; client-only invalid lease token; real HTTP catalog_expired',total,pages,
    postRecoveryPolls:3,normalFiveSecondPoll:true,hiddenReturn:true,routeReturn:true,
    requests:await evaluate('recoveryRequests'),expiries:await evaluate('recoveryExpiries'),
    limitations:'No source mutations or inference; not natural five-minute expiry, physical desktop or screen-reader proof.'};
};
