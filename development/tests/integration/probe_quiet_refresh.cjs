// All shipped routes: presentation lifecycle with canonical synthetic reports.
const assert = require('node:assert/strict');
module.exports = async ({command,evaluate,until,owner,checks,layouts}) => {
  const run = (expression,userGesture=false) => evaluate(owner,expression,userGesture);
  const ready = expression => until(owner,expression);
  const forbidden = /Historical snapshot as of|Previously verified sessions|checking for changes|Updates delayed|Update delayed|Partial history coverage|Page position changed|Waiting for a current session catalog|Source evidence:/i;
  const audit = async () => {
    const text = await run(`output.textContent+'\\n'+[...document.querySelectorAll('#result [aria-description],#result [role="status"],#host-state')].map(n=>n.textContent+' '+(n.getAttribute('aria-description')||'')).join('\\n')`);
    assert.doesNotMatch(text,forbidden);
    const ax = (await command('Accessibility.getFullAXTree',{},owner)).nodes.filter(n=>!n.ignored).map(n=>n.name?.value||'').join('\n');
    assert.doesNotMatch(ax,forbidden);
    assert.equal(await run(`!!document.getElementById('report-updating')`),false);
  };
  for(const section of ['models','token-mix','ai-stats','comparisons']) {
    await run(`location.hash='#/${section}'`);
    await ready(`current.section==='${section}' && !!current.result && !current.loading`);
    await audit();
    const lifecycle = await run(`(()=>{
      const first=output.firstChild, result=current.result;
      const focus=output.querySelector('button,a');focus?.focus();
      const oldFocus=document.activeElement;
      for(const refresh of ['running','queued','delayed','scheduled']) {
        current.loading=true;current.refreshState=refresh;show(current);
        if(output.firstChild!==first||document.activeElement!==oldFocus)throw Error('refresh replaced content/focus');
      }
      current.loading=false;current.failed=true;current.message='Update delayed; last completed report retained.';show(current);
      const retained=output.firstChild===first;
      current.failed=false;current.message='';show(current);
      return {retained,result:current.result===result,focus:document.activeElement===oldFocus};
    })()`);
    assert.deepEqual(lifecycle,{retained:true,result:true,focus:true});await audit();
    await run(`Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));
      Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));`);
    await ready(`!current.loading`);await audit();
    await run(`location.hash='#/watch'`);await ready(`current.section==='watch'`);
    await run(`location.hash='#/${section}'`);await ready(`current.section==='${section}' && !current.loading`);await audit();
    layouts.push({route:section,...lifecycle});
  }
  await run(`location.hash='#/watch'`);await ready(`!!current.watch`);
  const daily = await run(`(()=>{
    const saved=structuredClone(liveValue),view=current.watch;
    view.earlier.open=true;
    const row=view.active.firstChild,amount=view.daily.children[1],before=view.daily.textContent;
    for(const state of ['refreshing','retrying','unavailable']) {
      const p=structuredClone(saved);p.view.daily_state=state;p.view.daily_usage=null;
      p.view.history_state=state;view.update(p);
      if(view.active.firstChild!==row||view.daily.children[1]!==amount||view.daily.textContent!==before)throw Error('Live content changed on retry');
    }
    view.update(saved);
    return {noHelp:!view.daily.querySelector('[tabindex],[title],[aria-describedby],.help-value'),retained:true};
  })()`);
  assert.deepEqual(daily,{noHelp:true,retained:true});await audit();
  await run(`miniWatch.toggle()`,true);await ready(`!!miniWatch.view`);
  assert.equal(await run(`!!miniWatch.view.daily.querySelector('[tabindex],[title],[aria-describedby],.help-value')`),false);
  await run(`miniWatch.close();location.hash='#/accounts'`);await ready(`!!current.accounts?.cards.size`);await audit();
  layouts.push({route:'watch/mini/accounts',...daily});
  // The real HTTP catalog acquisition is tested independently. Here controlled
  // replies drive the shipped routing, bounded reopen, retained sort and DOM.
  await run(`sessionDetailAvailable=true; // Explicit synthetic route capability, not real source admission.
    window.quietApi=api;window.expireCatalog=false;window.catalogFailure=false;
    window.catalogRows=Array.from({length:51},(_,i)=>({session_id:'quiet-'+i,title:'Synthetic '+i,last_activity_ms:1000+i,
      indexed:true,has_summary:true,metric_state:'ready',prompt_count:1,model:'Test',display:{ccost:'1',duration_ms:'1s'}}));
    api=async(path,value,...rest)=>{
      if(path==='/api/sessions') {
        if(value.action==='interest')return {};
        if(catalogFailure)throw Error('offline');
        if(expireCatalog){expireCatalog=false;throw Error('catalog_expired');}
        return {token:'quiet-token',epoch:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',state:'observed',total:51,size:50,offset:value.offset,
          sort:value.sort,direction:value.direction,age_ms:7200000,view:{session_usage:catalogRows.slice(value.offset,value.offset+50)}};
      }
      if(path==='/api/detail') {
        if(value.action==='open')return {token:'quiet-detail'};if(value.action==='close')return {};
        const row={...liveValue.view.active_cards[0].rows[0].prompt,id:'quiet-prompt',watch_model:'Test'};
        return {state:'observed',revision:'quiet-revision',age_ms:7200000,total:1,offset:0,result:{view:{prompt_blocks:[{
          title:'Synthetic detail',rows:[row],totals:{display:{}},session_context:null}]}}};
      }
      return quietApi(path,value,...rest);
    };location.hash='#/sessions?sort=ccost&direction=1'`);
  await ready(`current.catalog?.body.children.length===50`);await audit();
  for(const offset of [0,50]) {
    await run(`location.hash='#/sessions?sort=ccost&direction=1&offset=${offset}&epoch=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'`);
    await ready(`current.catalog?.offset===${offset} && !current.catalog.busy`);
    await run(`expireCatalog=true;current.catalog.load()`);
    assert.equal(await run(`current.catalog.offset===0 && current.catalog.epoch==='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' && location.hash==='#/sessions?sort=ccost&direction=1'`),true);
    await audit();
  }
  await run(`catalogFailure=true;current.catalog.load()`);await audit();
  assert.equal(await run(`current.catalog.body.children.length===50 && !current.catalog.root.querySelector('progress')`),true);
  await run(`catalogFailure=false`);
  await run(`location.hash='#/sessions/quiet-0'`);await ready(`current.detail?.data?.revision==='quiet-revision'`);await audit();
  await run(`current.detail.sourceStatus({state:'history_retained'});current.detail.sourceStatus({state:'source_unavailable'})`);await audit();
  layouts.push({route:'sessions/detail',oldObservation:true,expiryPages:[0,50],silentRetainedFailure:true});
  await run(`location.hash='#/settings'`);await ready(`!!document.getElementById('ccost-unit') && !document.getElementById('ccost-unit').disabled`);
  const settings = await run(`(()=>{const root=output.firstChild;show(current);return {stable:root===output.firstChild,feedback:document.getElementById('settings-feedback').textContent};})()`);
  assert.equal(settings.stable,true);await audit();layouts.push({route:'settings',...settings});
  for(const width of [360,1366,1920])for(const theme of ['classic','light','dark']) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},owner);
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},owner);
    await run(`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}'`);
    for(const route of ['models','watch','accounts','sessions','sessions/quiet-0','token-mix','ai-stats','comparisons','settings']) {
      await run(`location.hash='#/${route}'`);
      await ready(`!current.loading && (current.result || current.live || current.catalog?.data || current.detail?.data || current.section==='settings')`);
      await audit();layouts.push({route,width,theme});
    }
  }
  await require('./probe_promotion_help.cjs')({command,run,ready,owner,checks,layouts});
  await run(`connectionStatus('Authentication expired. Use a fresh launcher link.',{kind:'authorization_required',terminal:true,writable:false})`);
  assert.equal(await run(`!document.getElementById('host-state').hidden && document.getElementById('host-state').textContent.includes('Authentication expired')`),true);
  checks.push('Nine-route DOM/AX matrix at 360/1366/1920 Classic/Web light/dark; finite-report retained refresh/delay/failure, focus, hidden/visible and navigation lifecycle');
  checks.push('Full/Mini daily has no help; five-second Sessions presentation retains hour-old rows and silently reopens expired first/older pages with exact URL/sort; terminal authorization remains actionable');
};
