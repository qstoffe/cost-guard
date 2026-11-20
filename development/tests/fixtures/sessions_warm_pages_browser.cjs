// Same native fixture on baseline and candidate; no transcript/identity output.
const assert = require('node:assert/strict');

module.exports = async ({evaluate, until, fixture}) => {
  const measuringBaseline = process.env.COST_GUARD_WARM_PAGE_BASELINE === '1';
  const settled = offset => until(`current.catalog.data?.offset===${offset} && !current.catalog.operation && !current.catalog.busy`);
  const identity = () => evaluate('[...current.catalog.body.rows].map(row=>row.dataset.id)');
  await evaluate("location.hash='#/sessions?period=today&sort=activity&direction=-1'");
  await until('current.catalog?.token');
  await fixture('warm');
  await settled(0);
  assert.equal(await evaluate('current.catalog.body.querySelectorAll(".session-running").length'),3);
  const first = await identity();
  await evaluate('current.catalog.next.click()');
  await settled(25);
  const second = await identity();
  assert.equal(first.length, 25);
  assert.equal(second.length, 18);
  assert.equal(new Set([...first,...second]).size, 43);
  assert.ok(first.includes('root-0042') && second.includes('root-0000'));

  await evaluate(`(() => {
    const view=current.catalog, original=view.api, update=view.update.bind(view);
    window.pageTrace=[];
    window.pageSample=null;
    window.pageInterests=0;
    view.api=async(...args)=>{
      if (args[1]?.action==='interest') pageInterests++;
      const start=performance.now(), data=await original(...args);
      if (!args[1]?.action && pageSample?.offset===args[1]?.offset)
        pageSample.http.push({ms:performance.now()-start, pending:data.pending_sort,
          phase:data.progress.phase, facts:data.progress.completed, total:data.progress.total,
          reused:data.page_reused===true, worker:data.progress.work?.active===true,
          generation:data.progress.generation, sameEpoch:data.epoch===pageSample.epoch});
      if (!args[1]?.action && args[1]?.offset===window.holdOffset && !window.releaseWarmPage)
        return new Promise(resolve=>{window.releaseWarmPage=()=>resolve(data);});
      return data;
    };
    view.update=data=>{
      update(data);
      if(pageSample && view.data===data && !view.operation && data.offset===pageSample.offset &&
         pageSample.applied==null) pageSample.applied=performance.now()-pageSample.started;
    };
    new MutationObserver(records=>{
      if(!pageSample) return;
      for(const record of records) {
        if(record.target===view.status && (record.oldValue===null || !view.status.hidden)) pageSample.banner=true;
        if(record.target===view.pan && (record.oldValue==='true' || view.pan.getAttribute('aria-busy')==='true'))
          pageSample.locked=true;
      }
    }).observe(view.root,{subtree:true,attributes:true,attributeFilter:['hidden','aria-busy'],attributeOldValue:true});
  })()`);
  const visit = async (offset, mode = 'number') => {
    await evaluate(`pageSample={offset:${offset},epoch:current.catalog.data.epoch,
      started:performance.now(),http:[],banner:false,locked:false};
      ${mode === 'number' ? `current.catalog.pageButtons.get(${offset === 0 ? 1 : 2}).click()` :
        mode === 'back' ? 'history.back()' : 'history.forward()'}`);
    await settled(offset);
    assert.deepEqual(await identity(), offset === 0 ? first : second);
    assert.match(await evaluate('current.catalog.label.textContent'), offset === 0 ? /1–25 of 43/ : /26–43 of 43/);
    await evaluate('pageTrace.push({...pageSample,epoch:undefined});pageSample=null');
  };

  const before = await fixture('stats');
  for (const offset of [0,25,0,25]) await visit(offset);
  const unchanged = await fixture('stats');
  assert.deepEqual(unchanged.metrics, before.metrics);
  assert.deepEqual(unchanged.reads, before.reads);
  for (let index=0; index<20; index++) {
    if (index%2===0) {
      await evaluate('current.catalog.load()'); // Acknowledge the last applied slice before the worker tick.
      await fixture('churn');
    }
    await visit(index%2===0 ? 0 : 25);
  }
  await fixture('join');
  const changed = await fixture('stats');
  await visit(0,'back');
  await visit(25,'forward');
  const trace = await evaluate('pageTrace');
  if (!measuringBaseline) {
    assert.ok(trace.every(sample=>sample.applied>=0 && !sample.banner && !sample.locked), JSON.stringify(trace));
    assert.ok(trace.every(sample=>sample.http[0]?.reused && sample.http[0].sameEpoch && !sample.http[0].pending));
    assert.equal(await evaluate('pageInterests'),0,'paging does not detach or register new interests');
    for (const [key, reads] of Object.entries(changed.reads)) {
      if (!['root-0042','root-0000','root-0040','root-0041'].includes(key))
        assert.equal(reads, unchanged.reads[key], `stable scalar replay: ${key}`);
    }
    // Hold a genuine page-one reply, supersede it using Back, then release it.
    await evaluate('window.holdOffset=0;current.catalog.previous.click()');
    await until('window.releaseWarmPage');
    await evaluate('history.back()');
    await settled(25);
    await evaluate('window.holdOffset=null;releaseWarmPage()');
    assert.deepEqual(await identity(), second);
  }
  const refreshStarted = Date.now();
  await evaluate('current.catalog.load()');
  await fixture('churn');
  await evaluate('current.catalog.previous.click()');
  await settled(0);
  const revisitedMs = Date.now() - refreshStarted;
  await evaluate('window.revisedRow=current.catalog.body.querySelector("[data-id=root-0042]")');
  const beforeFresh = await evaluate('revisedRow.value.metric_state');
  assert.equal(await evaluate('revisedRow.value.running'),true);
  const refreshed = await fixture('refresh');
  await evaluate('current.catalog.load()');
  await until('revisedRow.value.metric_state==="ready" || revisedRow.value.metric_state==="snapshot"');
  const refreshedMs = Date.now() - refreshStarted;
  if (!measuringBaseline) {
    assert.equal(beforeFresh,'retained');
    assert.equal(refreshed.stale,0,'both changed native revisions become current');
    assert.equal(await evaluate('revisedRow===current.catalog.body.querySelector("[data-id=root-0042]")'),true);
  }
  const started = Date.now();
  await fixture('finish');
  await fixture('refresh');
  await evaluate('current.catalog.load()');
  await until('current.catalog.body.querySelector("[data-id=root-0042]")?.value.running===false');
  const retirementMs = Date.now() - started;
  await evaluate("current.catalog.headers.find(h=>h.key==='name').th.querySelector('button').click()");
  await until('current.catalog.data?.sort==="name" && !current.catalog.operation');
  const times = trace.slice(4,24).map(sample=>sample.applied).sort((a,b)=>a-b);
  const extraReads = Object.entries(changed.reads).filter(([key, reads])=>reads!==unchanged.reads[key])
    .map(([key, reads])=>[Number(key.slice(5)), reads-(unchanged.reads[key] || 0)]);
  return {samples:times.length, min:times[0], median:times[9], p95:times[18], max:times[19],
    revisitedMs, refreshedMs, retirementMs, unchangedAttempts:unchanged.metrics.attempts-before.metrics.attempts,
    changedReadsByFixtureOrdinal:extraReads, unchangedMetrics:unchanged.metrics, changedMetrics:changed.metrics, trace};
};
