// Shipped HTTP/controller/DOM; monotonic server age, genuine headless-tab visibility.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, until, fixture, targetId, command, browserCommand}) => {
  const traces = [], timings = [], work = [];
  const settled = offset => until(`current.catalog?.data?.offset===${offset} &&
    !current.catalog.busy && !current.catalog.operation && !current.catalog.recovering`);
  const trace = async name => {
    const state = await evaluate(`(()=>{const c=current.catalog,d=c.data;return {
      hidden:document.hidden,attached:c.attached,route_offset:Number(new URLSearchParams(location.hash.split('?')[1]).get('offset')||0),
      applied:d?{offset:d.offset,total:d.total,size:d.size,epoch:d.epoch===window.idleEpoch?'original':'replacement'}:null,
      token:!!c.token,recovering:!!c.recovering,busy:c.busy,pending_sort:!!c.idleReply?.pending_sort,
      operation:c.operation?{kind:c.operation.kind,userInitiated:c.operation.userInitiated,pending:c.operation.pending,
        failed:c.operation.failed,navigation:!!c.operation.navigation}:null,
      progress:!c.status.hidden,label:c.label.textContent,rows:c.body.children.length,
      coherent:!!d && c.body.children.length===d.view.session_usage.length &&
        [...c.body.children].every((r,i)=>r.dataset.id===d.view.session_usage[i].session_id),
      table_busy:c.pan.getAttribute('aria-busy'),actionFocus:!!c.actionFocus,
      focus:c.pager.contains(document.activeElement)?document.activeElement.textContent:
        document.activeElement===document.body?'body':'outside',
      buttons:[c.previous,...c.pageButtons.values(),c.next].map(b=>({label:b.textContent,
        destination:b.destination?Number(new URLSearchParams(b.destination.split('?')[1]).get('offset')||0):null,
        disabled:b.disabled,navigationDisabled:b.navigationDisabled,ariaDisabled:b.getAttribute('aria-disabled'),
        current:b.getAttribute('aria-current')}))};})()`);
    traces.push({name,...state}); return state;
  };
  const available = (state, total, offset=0) => {
    assert.equal(state.applied.total,total); assert.equal(state.applied.offset,offset);
    assert.equal(state.rows,Math.min(25,total-offset));
    assert.equal(state.coherent,true); assert.equal(state.route_offset,offset);
    assert.match(state.label,new RegExp(`Page ${offset/25+1} of ${Math.max(1,Math.ceil(total/25))}$`));
    for (const button of state.buttons) {
      const expected = button.label==='Previous' ? offset>0 : button.label==='Next' ? offset+25<total :
        Number(button.label)!==offset/25+1;
      assert.equal(button.disabled,!expected,JSON.stringify({name:state.label,button}));
      assert.equal(button.navigationDisabled,!expected);
      assert.equal(button.ariaDisabled,null);
    }
    assert.equal(state.recovering,false); assert.equal(state.progress,false);
  };
  const instrument = () => evaluate(`(()=>{window.idleEpoch=current.catalog.data.epoch;
    window.idleRequests=[];window.idleExpiries=0;window.idleBaseApi ||= current.catalog.api;
    const original=idleBaseApi;
    current.catalog.api=async(...args)=>{
      const r=args[1],start=performance.now();
      try {const data=await original(...args);
        if(!r.action){current.catalog.idleReply=data;idleRequests.push({offset:r.offset,token:!!r.token,
          navigation:!!r.navigation,pending_sort:data.pending_sort,ms:performance.now()-start});}
        return data;
      }catch(error){if(!r.action && error.message==='catalog_expired')idleExpiries++;throw error;}
    };})()`);
  for (const total of [25,26,50,51]) {
    await fixture('catalog-idle-source-'+total); await fixture('catalog-index');
    await evaluate(`location.hash='#/sessions?period=all&sort=name&direction=1'`);
    await until(`current.catalog?.data?.total===${total} && !current.catalog.busy`);
    await instrument();
    available(await trace('settled-'+total),total);
    // Visible polls renew touched even across a cumulative period above five minutes.
    for (let step=0;step<2;step++) {
      await fixture('catalog-idle-advance-240'); await evaluate('current.catalog.poll()');
    }
    assert.equal(await evaluate('idleExpiries'),0);
    available(await trace('visible-idle-'+total),total);
    if (total>25) {
      const before = await fixture('catalog-idle-observe');
      for (const offset of [25,0,25,0]) {
        const timing = await evaluate(`(async()=>{
          const c=current.catalog,start=performance.now(),body=c.body.firstChild;
          window.idleAppliedAt=null;window.idleProgressShown=false;c.idleUpdate ||= c.update;
          const update=c.idleUpdate;
          window.idleProgressObserver=new MutationObserver(records=>{
            if(records.some(r=>r.oldValue===null) || !c.status.hidden)idleProgressShown=true;
          });
          idleProgressObserver.observe(c.status,{attributes:true,attributeFilter:['hidden'],attributeOldValue:true});
          c.update=function(data){update.call(this,data);if(this.data===data && data.offset===${offset})
            idleAppliedAt=performance.now()-start;};
          const button=c.pageButtons.get(${offset/25+1});button.click();
          return {retainedBeforeReply:c.body.firstChild===body,offset:${offset}};})()`);
        await settled(offset);
        timing.click_to_apply_ms = await evaluate('idleAppliedAt');
        timing.request_ms = await evaluate('idleRequests.at(-1).ms');
        timing.progress = await evaluate('idleProgressObserver.disconnect();idleProgressShown');
        timings.push({total,...timing});
        available(await trace('warm-'+total+'-'+offset),total,offset);
      }
      const after = await fixture('catalog-idle-observe');
      assert.equal(after.history_reads,before.history_reads,'warm navigation never reacquires synthetic history');
      assert.equal(after.metrics.attempts,before.metrics.attempts);
      work.push({total,new_history_reads:after.history_reads-before.history_reads,
        new_summary_attempts:after.metrics.attempts-before.metrics.attempts});
      await evaluate('history.back()'); await settled(25);
      await evaluate('history.forward()'); await settled(0);
      await fixture('catalog-churn'); await evaluate('current.catalog.poll()');
      const revised = await trace('live-revision-pending-'+total);
      assert.equal(revised.progress,false); assert.equal(revised.applied.offset,0);
      await fixture('catalog-index'); await evaluate('current.catalog.poll()'); await settled(0);
      available(await trace('live-revision-qualified-'+total),total);
    }
    if(total===51) {
      await evaluate('current.catalog.next.click()'); await settled(25);
      await evaluate('current.catalog.body.querySelector("a").focus()');
    }
    // A second actual target, not an overridden document.hidden or synthetic event.
    const {targetId:other} = await browserCommand('Target.createTarget',{url:'about:blank'});
    await browserCommand('Target.activateTarget',{targetId:other});
    await until('document.hidden');
    const requestsBefore = await evaluate('idleRequests.length');
    await fixture('catalog-idle-advance-301'); await evaluate('current.catalog.poll()');
    assert.equal(await evaluate('idleRequests.length'),requestsBefore);
    await trace('hidden-idle-'+total);
    // Hold a real successful reopen response; expose the legitimate recovery window.
    await evaluate(`window.idleRelease=null;window.idleHeld=false;window.idleWrapped=current.catalog.api;
      current.catalog.api=async(...args)=>{const data=await idleWrapped(...args);
        if(!args[1]?.action && !args[1]?.token && !idleHeld){idleHeld=true;
          return new Promise(resolve=>{idleRelease=()=>resolve(data);});}return data;}`);
    await browserCommand('Target.activateTarget',{targetId});
    await until('!document.hidden && idleRelease!==null');
    const recovering = await trace('expired-reopening-'+total);
    assert.equal(recovering.recovering,true); assert.equal(recovering.busy,true);
    assert.ok(recovering.buttons.every(b=>b.disabled && b.navigationDisabled),JSON.stringify(recovering));
    assert.equal(recovering.progress,false);
    await evaluate('idleRelease();current.catalog.api=idleWrapped');
    await settled(0);
    available(await trace('recovered-'+total),total);
    assert.equal(await evaluate('idleExpiries'),1);
    await browserCommand('Target.closeTarget',{targetId:other});
    await evaluate(`location.hash='#/settings'`); await until('current.section==="settings"');
    await evaluate(`location.hash='#/sessions?period=all&sort=name&direction=1'`); await settled(0);
    available(await trace('route-return-'+total),total);
  }
  // Cold explicit page qualification is different from warm HTTP/DOM overhead.
  await fixture('catalog-page-cold');
  await evaluate(`window.coldStarted=performance.now();current.catalog.next.click()`);
  await until('current.catalog.operation?.kind==="page" && current.catalog.operation.pending && !current.catalog.busy');
  const cold = await trace('cold-page-pending');
  assert.equal(cold.applied.offset,0); assert.equal(cold.progress,true);
  await fixture('catalog-index'); await evaluate('current.catalog.poll()'); await settled(25);
  timings.push({total:51,offset:25,cold_controlled_qualification_ms:await evaluate('performance.now()-coldStarted'),
    progress:true,qualification:'test-held missing keys, then explicitly seeded; not source throughput'});
  available(await trace('cold-page-applied'),51,25);
  await evaluate('current.catalog.previous.click()'); await settled(0);
  // A deferred reopen may truthfully retain the old 1-of-3 label and inert pager.
  await fixture('catalog-clear');
  await evaluate(`current.catalog.interest(false);current.catalog.token='00000000000000000000000000000000';
    current.catalog.sort='ccost';current.catalog.direction=1;
    window.pendingRecovery=current.catalog.poll();void 0`);
  await evaluate('pendingRecovery');
  const pending = await trace('provisional-reopen');
  assert.equal(pending.recovering,true); assert.equal(pending.pending_sort,true);
  assert.equal(pending.progress,false); assert.ok(pending.buttons.every(b=>b.disabled));
  await fixture('catalog-index'); await evaluate('current.catalog.poll()'); await settled(0);
  available(await trace('provisional-recovered'),51);
  // Interrupted passive recovery returns through the same route and rejects late data.
  await evaluate(`window.lateRelease=null;window.lateApi=current.catalog.api;
    current.catalog.api=async(...args)=>{const data=await lateApi(...args);
      if(!args[1]?.action && !lateRelease)return new Promise(resolve=>{lateRelease=()=>resolve(data);});
      return data;};window.latePoll=current.catalog.poll();void 0`);
  await until('lateRelease!==null');
  await evaluate(`location.hash='#/settings'`); await until('current.section==="settings"');
  await evaluate(`location.hash='#/sessions?period=all&sort=ccost&direction=1'`); await settled(0);
  const data = await evaluate('current.catalog.data.epoch');
  await evaluate('lateRelease();current.catalog.api=lateApi;latePoll');
  assert.equal(await evaluate('current.catalog.data.epoch'),data);
  available(await trace('late-detached-reply'),51);
  return {checks:['25/26/50/51-row coherent pager','visible idle renewal','genuine hidden/resume + 301s server-clock expiry',
    'held real reopen response','warm 1↔2 and Back/Forward','cold page qualification','provisional recovery',
    'route return and late response retirement'],
    traces,timings,work,limitations:'Synthetic source; controlled server monotonic age, not five minutes of wall time. No personal history, physical input or screen-reader speech proof.'};
};
