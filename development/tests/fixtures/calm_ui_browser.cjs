// Shipped HTTP/worker plus controlled frontend failures; never installed source or desktop.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, until, fixture, command, checks = [], layouts = []}) => {
  const run = source => evaluate(`(async()=>{${source}})()`);
  await evaluate(`window.initialRead={bodyLost:false,expired:false,stale:false,opens:0,replies:[],samples:0,gaps:0};
    window.normalFetch=window.fetch;
    window.fetch=async(url,options)=>{
      if(url!=='/api/detail')return normalFetch(url,options);
      const request=JSON.parse(options.body), trace=initialRead;
      if(request.action==='open')trace.opens++;
      // A fetch may resolve at headers and still lose the body before JSON is available.
      if(request.action==='begin' && !trace.bodyLost){
        trace.bodyLost=true;
        return new Response(new ReadableStream({start(controller){
          controller.error(new TypeError('Synthetic body transport interrupted'));
        }}));
      }
      if(request.action==='begin' && !trace.expired){
        trace.expired=true;
        await normalFetch(url,{...options,body:JSON.stringify({action:'close',token:request.token})});
      }
      if(request.action==='chunk' && !trace.stale){
        trace.stale=true;
        options={...options,body:JSON.stringify({...request,revision:'obsolete'})};
      }
      const reply=await normalFetch(url,options);
      if(!reply.ok)trace.replies.push([reply.status,(await reply.clone().json()).error]);
      return reply;
    };
    window.initialDOM=new MutationObserver(()=>{
      const view=current?.detail;
      if(!view?.root.isConnected || view.body.rows.length)return;
      initialRead.samples++;
      if(view.loader.root.hidden || !view.status.hidden || !view.retry.hidden ||
         view.scroll.getAttribute('aria-busy')!=='true')initialRead.gaps++;
    });
    initialDOM.observe(output,{attributes:true,subtree:true,childList:true,characterData:true});
    location.hash='#/sessions/root-0000'`);
  // The total is announced with the first usable rows. A stale later chunk
  // must recover autonomously, without another click or a forced poll.
  await until('current.detail?.body.rows.length===1001 && !current.detail.busy');
  const trace=await evaluate('initialDOM.disconnect();window.fetch=normalFetch;initialRead');
  assert.deepEqual(trace.replies,[[410,'detail_expired'],[409,'detail_read_stale']]);
  assert.equal(trace.opens,2,'only the expired lease needs reopening');
  assert.ok(trace.bodyLost && trace.samples>0); assert.equal(trace.gaps,0);
  checks.push('cold prompt history survives a dropped body, expired lease and stale chunk without losing its visible loader or requesting a click');
  await evaluate(`window.quietRow=current.detail.body.firstChild;window.quietFooter=current.detail.footer.textContent;
    window.quietRevision=current.detail.data.revision;window.quietFocus=current.detail.root.querySelector('a');
    quietFocus.focus();window.quietTop=current.detail.scroll.getBoundingClientRect().top;`);
  await fixture('detail-quiet-stall');
  await run(`await current.detail.pendingLoad;await current.detail.poll()`);
  const internal = await fixture('detail-observe');
  assert.ok(internal.entries.some(entry=>entry.reason==='detail_not_admitted'));
  const silent = async () => {
    assert.equal(await evaluate(`current.detail.status.hidden && current.detail.status.textContent==='' &&
      current.detail.retry.hidden && current.detail.loader.root.hidden &&
      current.detail.scroll.getAttribute('aria-busy')==='false' && current.detail.body.firstChild===quietRow`),true);
  };
  await silent();
  for (const theme of ['classic','web']) for (const scheme of ['light','dark']) for (const width of [360,1366]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]});
    await evaluate(`document.documentElement.dataset.theme='${theme}'`);
    await run(`await current.detail.pendingLoad;await current.detail.poll()`);
    await silent();
    const facts = await evaluate(`({warning:current.detail.status.getBoundingClientRect().height,
      retry:current.detail.retry.getBoundingClientRect().height,loader:current.detail.loader.root.getBoundingClientRect().height,
      focus:document.activeElement===quietFocus,overflow:document.documentElement.scrollWidth>innerWidth+1})`);
    assert.equal(facts.warning,0); assert.equal(facts.retry,0); assert.equal(facts.loader,0);
    assert.equal(facts.focus,true); assert.equal(facts.overflow,false);
    const ax = await command('Accessibility.getFullAXTree');
    assert.ok(!ax.nodes.some(node=>!node.ignored && /detail_not_admitted|Try again|Retry session loading/.test(node.name?.value || '')));
    layouts.push({theme,scheme,width,...facts});
  }
  assert.equal(await evaluate('current.detail.footer.textContent===quietFooter'),true);
  await fixture('detail-quiet-recover');
  // Observe only: the existing poll owner must discover the fresh acquisition.
  // A forced read here would not prove autonomous browser recovery.
  try {
    await until('current.detail?.data?.total===1002 && !current.detail.busy');
  } catch (_) {
    const frontend=await evaluate(`({hidden:document.hidden,attached:current.detail?.attached,
      busy:current.detail?.busy,total:current.detail?.data?.total,waiting:current.detail?.waiting})`);
    const backend=await fixture('detail-observe');
    throw new Error('Fresh detail recovery not observed: '+JSON.stringify({frontend,entries:backend.entries}));
  }
  await silent();
  assert.equal(await evaluate('current.detail.data.revision!==quietRevision'),true);
  checks.push('120s unadmitted loaded detail: typed failure, no warning/Retry/ARIA/layout/focus change; existing owner re-admits after 30s cooldown and publishes 1002 fresh rows without a click');
  const originalApi = await evaluate(`!!current.detail.api`);
  assert.equal(originalApi,true);
  await run(`await current.detail.pendingLoad;window.quietApi=current.detail.api;
    try{current.detail.api=async()=>{throw new Error('connection_timeout')};await current.detail.poll()}
    finally{current.detail.api=quietApi}`);
  await silent();
  checks.push('passive asynchronous exception retains source-qualified history with no 500ms busy retry or user affordance');
  // Real route composition and popovers, with controlled benign presentation
  // failures over the synthetic HTTP reports. No installed/private source.
  for (const route of ['models','watch','sessions','accounts','token-mix','ai-stats','settings']) {
    await evaluate(`location.hash='#/${route}'`);
    await until(`current?.section==='${route}'`);
    if (['models','token-mix','ai-stats'].includes(route))
      await until('current.result && !current.loading');
    if (route==='sessions') await until('current.catalog?.data && !current.catalog.busy');
    if (route==='settings') await until('settingsView?.loaded && !settingsView.busy');
    await run(`window.quietRouteRoot=output.firstChild;
      if(current.catalog){const view=current.catalog,api=view.api;
        try{view.api=async()=>{throw new Error('concurrent_source_change')};await view.load()}finally{view.api=api}}
      else if(current.section==='settings'){const api=settingsView.api;
        try{settingsView.api=async()=>{throw new Error('connection_timeout')};await settingsView.read()}finally{settingsView.api=api}}
      else {current.failed=true;current.userInitiated=false;current.message='detail_not_admitted';show(current)}`);
    assert.equal(await evaluate('output.firstChild===quietRouteRoot'),true,route+' retains actual DOM');
    const forbidden = /concurrent_source_change|detail_not_admitted|Retaining the last|worker failed|source-qualified|attribution incomplete/i;
    assert.doesNotMatch(await evaluate('output.innerText'),forbidden,route);
    assert.equal(await evaluate('notice.textContent'),'',route+' has no passive notice');
    const helps = await evaluate(`(()=>{
      const values=[];for(const node of [...output.querySelectorAll('.help-value,.help-button')].slice(0,6)){
        node.focus();ContextHelp.refresh(node);const panel=document.getElementById('context-help');
        if(panel?.matches(':popover-open'))values.push(panel.innerText)}
      ContextHelp.dismiss(output);return values})()`);
    helps.forEach(text=>assert.doesNotMatch(text,forbidden,route+' visible popover'));
    const ax = await command('Accessibility.getFullAXTree');
    assert.ok(!ax.nodes.some(node=>!node.ignored && forbidden.test(node.name?.value || '')),route+' AX tree');
    await evaluate('current.failed=false;current.message="";show(current)');
    checks.push(route+': real loaded DOM retained during benign failure; no technical visible/popover/AX notice');
  }
  await evaluate(`location.hash='#/watch'`);
  await until('miniWatch?.measure?.ready && miniWatch.placement');
  await evaluate('miniWatch.toggle()',true);
  await until('miniWatch.view && !miniWatch.pending');
  // Opening's clamp outcome is assigned in the child document's next frame,
  // after pending clears. Settle that explicit outcome before testing health.
  await evaluate('new Promise(resolve=>miniWatch.window.requestAnimationFrame(()=>miniWatch.window.requestAnimationFrame(resolve)))');
  const openingFeedback=await evaluate('miniWatch.feedback.textContent');
  await evaluate(`miniWatch.health({kind:'offline'});miniWatch.sync()`);
  assert.equal(await evaluate(`miniWatch.view.health.hidden`),true);
  assert.equal(await evaluate('miniWatch.feedback.textContent'),openingFeedback,'passive health cannot add or rewrite an explicit opening outcome');
  assert.doesNotMatch(await evaluate('miniWatch.window.document.body.innerText'),/source-qualified|worker failed|connection_timeout/i);
  await evaluate('miniWatch.close()');
  checks.push('native headless Mini document opens from explicit gesture and has no passive offline notice');
  // Explicit actions still own concise outcomes; cold unknown is not a zero.
  await evaluate(`window.quietSave=settingsView.api;settingsView.api=async()=>{throw new Error('private_failure')};
    settingsView.error(new Error('private_failure'));settingsView.api=quietSave`);
  assert.equal(await evaluate('settingsView.feedback.textContent'),'Could not save. Try again.');
  const unknownMix = await evaluate(`(()=>{
    const result={observed_at_ms:Date.now(),source:{status:'partial'},view:{kind:'token-mix',
      model_token_mix:[],publisher_token_mix:[],token_mix:null,
      token_mix_period:{period:'7-days',start_ms:Date.now()-604800000,end_ms:Date.now(),coverage:'unknown'}}};
    const view=new TokenMixView.View();view.update(result);view.selection('7-days',true);view.attach(output);
    return {valid:TokenMixView.valid(result),text:output.innerText,summaryHidden:view.summary.hidden,
      modelsHidden:view.models.root.hidden,publishersHidden:view.publishers.root.hidden};
  })()`);
  assert.equal(unknownMix.valid,true);
  assert.match(unknownMix.text,/Usage for this period could not be verified\./);
  assert.doesNotMatch(unknownMix.text,/N\/A|Not Applicable|0 tokens|Loading/);
  assert.ok(unknownMix.summaryHidden && unknownMix.modelsHidden && unknownMix.publishersHidden);
  checks.push('explicit Save failure is concise; unknown Token Mix displays neutral coverage, never zero or N/A');
  // Health rendering is fed controlled corroborated source evidence; transport
  // counting/20s qualification is independently covered in web_connection.cjs.
  await evaluate(`liveConnection.close();hostState={kind:'connected',writable:true,terminal:false};
    connectionStatus('technical SSE error',{kind:'reconnecting',writable:false,sourceOutage:false})`);
  assert.equal(await evaluate(`document.getElementById('host-state').hidden && document.getElementById('status').textContent===''`),true);
  await evaluate(`connectionStatus('internal reason',{kind:'source_unavailable',writable:true,sourceOutage:true})`);
  assert.equal(await evaluate(`document.getElementById('host-message').textContent`),'OpenCode connection lost. Trying to reconnect…');
  assert.equal(await evaluate(`document.getElementById('host-message').getBoundingClientRect().height>0`),true);
  assert.equal(await evaluate(`document.querySelectorAll('#host-state:not([hidden])').length`),1);
  await evaluate(`connectionStatus('healthy',{kind:'connected',writable:true,sourceOutage:false})`);
  assert.equal(await evaluate(`document.getElementById('host-state').hidden`),true);
  checks.push('single global visible/ARIA status for corroborated source loss; SSE-only interruption stays silent; qualified recovery clears it');
  // An actual cold-open action retains a small deliberate accessible recovery.
   await run(`window.coldQuiet=new SessionDetail.View(async(_,request)=>
    request.action==='open'?{token:'cold'}:{state:'source_unavailable',result:null,
      acquisition:{phase:'failed',reason:'detail_not_admitted',retry_available:true,retry_scheduled:false}},'cold');
    coldQuiet.attach(output);await coldQuiet.pendingLoad;`);
  assert.equal(await evaluate(`!coldQuiet.retry.hidden && coldQuiet.status.textContent==='Could not load. Try again or return to Sessions.'`),true);
  for (const theme of ['classic','web']) for (const scheme of ['light','dark']) for (const width of [360,1366]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]});
    await evaluate(`document.documentElement.dataset.theme='${theme}'`);
    assert.ok(await evaluate(`parseFloat(getComputedStyle(coldQuiet.retry).marginBottom)>=16`));
    const ax = await command('Accessibility.getFullAXTree');
    assert.ok(ax.nodes.some(node=>!node.ignored && node.role?.value==='button' && node.name?.value==='Try again'));
    layouts.push({surface:'cold-detail',theme,scheme,width,retryMarginAtLeast16:true,accessible:true});
  }
  checks.push('cold foreground failure keeps nontechnical, spaced and accessible Try again; never appears on populated history');
  await run(`window.quietExport=new SessionExport.Action(async()=>{throw new Error('export_source_unavailable')},'synthetic');
    output.replaceChildren(quietExport.root);quietExport.update('synthetic','unavailable');`);
  assert.equal(await evaluate('quietExport.button.disabled && quietExport.notice.textContent.includes("unavailable")'),true);
  await run(`const picker=window.showSaveFilePicker;
    try{window.showSaveFilePicker=undefined;quietExport.update('synthetic','ready','scope');await quietExport.activate();}
    finally{window.showSaveFilePicker=picker;}`);
  assert.equal(await evaluate('quietExport.notice.textContent'),'The selected OpenCode source is unavailable. Retry when it is ready.');
  checks.push('Genuine export blocker is explained and disabled; explicit synthetic failure has a truthful outcome without a dialog or file write');
  return {checks,layouts};
};
