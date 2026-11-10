// Read-only installed-source observation: never export row titles, IDs or transcripts.
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
