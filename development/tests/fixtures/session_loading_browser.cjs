// Shipped HTTP route first; then controlled canonical rows isolate transfer/wait races.
const assert = require('node:assert/strict');
module.exports = async function sessionLoading({evaluate, until, command}) {
  const checks = [], layouts = [];
  await evaluate(`window.loadingEvents=[];
    const loading=SessionDetail.View.prototype.loading;
    SessionDetail.View.prototype.loading=function(...args){loading.call(this,...args);
      loadingEvents.push({percent:this.loader.bar.value,stage:this.loader.stage.textContent});};
    location.hash='#/sessions?sort=name&direction=1'`);
  await until(`document.querySelector('a[href="#/sessions/root-0000"]')`);
  await evaluate(`document.querySelector('a[href="#/sessions/root-0000"]').click()`);
  await until('current.detail?.data?.total===1001');
  assert.equal(await evaluate('current.detail.body.rows.length'),1001);
  const events = await evaluate('loadingEvents');
  assert.equal(events[0].percent,0);
  assert.ok(events.some(event=>event.stage==='Loading session history (1001 of 1001)…'));
  assert.equal(await evaluate('current.detail.loader.bar.value'),100);
  assert.equal(await evaluate('current.detail.scroll.getAttribute("aria-busy")'),'false');
  checks.push('actual Sessions link / authenticated open-begin-chunks / 1001 canonical rows / applied completion');
  await evaluate(`window.loadingProbe={seed:structuredClone(current.detail.data),requests:[],events:[]};
    current.detail.detach();
    loadingProbe.setup=(total,waiting=true,hold=false)=>{
      loadingProbe.view?.detach(); loadingProbe.waiting=waiting; loadingProbe.hold=hold;
      loadingProbe.requests=[]; loadingProbe.events=[];
      const full=structuredClone(loadingProbe.seed);full.total=total;full.revision='controlled-'+total;
      full.result.view.prompt_blocks[0].rows=full.result.view.prompt_blocks[0].rows.slice(0,total);
      const api=async (_,request)=>{
        loadingProbe.requests.push(request);
        if(request.action==='open')return {token:'controlled'};
        if(request.action==='close')return {};
        if(loadingProbe.waiting)return {state:'loading',pending:true,result:null};
        const response=structuredClone(full);response.offset=request.offset;
        response.result.view.prompt_blocks[0].rows=response.result.view.prompt_blocks[0].rows.slice(request.offset,request.offset+50);
        if(request.action==='chunk' && loadingProbe.hold)await new Promise(resolve=>loadingProbe.release=resolve);
        return response;
      };
      const view=new SessionDetail.View(api,'controlled');loadingProbe.view=view;
      const update=view.loader.update.bind(view.loader);
      view.loader.update=state=>{loadingProbe.events.push({percent:state.percent,stage:state.stage,rows:view.body.rows.length});update(state);};
      view.attach(document.getElementById('result'));loadingProbe.bar=view.loader.bar;
    }; loadingProbe.setup(220);`);
  await until('!loadingProbe.view.busy');
  for (const theme of ['classic','web']) for (const scheme of ['light','dark'])
    for (const width of [360,768,1366,1920]) for (const zoom of [1,1.25,1.5]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme},
        {name:'prefers-reduced-motion',value:'reduce'}]});
      await evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme)};document.body.style.zoom=${zoom};window.scrollTo(0,0)`);
      const facts = await evaluate(`(()=>{
        const view=loadingProbe.view,root=view.loader.root,bar=view.loader.bar,b=bar.getBoundingClientRect(),r=root.getBoundingClientRect();
        const reference=new ReportLoading.View();document.body.append(reference.root);
        const expected=getComputedStyle(reference.bar),actual=getComputedStyle(bar);
        const result={max:bar.max,value:bar.value,explicit:bar.hasAttribute('value'),stable:bar===loadingProbe.bar,
          centerX:Math.abs((b.left+b.right-r.left-r.right)/2),
          centerY:Math.abs((r.top+r.bottom)/2-(b.top+root.lastElementChild.previousElementSibling.getBoundingClientRect().bottom)/2),
          width:b.width,height:actual.height,sharedHeight:expected.height,animation:actual.animationName,
          overflow:document.documentElement.scrollWidth>innerWidth+1,warning:!view.status.hidden,
          live:view.loader.status.getAttribute('aria-live'),busyAncestor:root.closest('[aria-busy=true]')!==null,
          back:view.root.querySelector('a').textContent};
        reference.root.remove();return result;})()`);
      assert.equal(facts.max,100); assert.equal(facts.value,0); assert.equal(facts.explicit,true); assert.equal(facts.stable,true);
      assert.ok(facts.centerX<2); assert.ok(facts.centerY<3); assert.ok(facts.width>100);
      assert.equal(facts.height,facts.sharedHeight); assert.equal(facts.animation,'none');
      assert.equal(facts.overflow,false); assert.equal(facts.warning,false); assert.equal(facts.live,'polite');
      assert.equal(facts.busyAncestor,false,'history busy state cannot suppress stage announcements');
      assert.equal(facts.back,'Show all sessions'); layouts.push({theme,scheme,width,zoom,...facts});
    }
  checks.push('48 real Chromium layouts: Classic/Web light/dark, 360/768/1366/1920, 100/125/150%, reduced motion; centered stable determinate shared style');
  await evaluate(`(async()=>{document.body.style.zoom=1;
    loadingProbe.view.freshness();await loadingProbe.view.load();await loadingProbe.view.load();})()`);
  assert.equal(await evaluate('loadingProbe.view.loader.bar===loadingProbe.bar && loadingProbe.bar.value===0'),true);
  await evaluate(`(async()=>{loadingProbe.waiting=false;await loadingProbe.view.load()})()`);
  assert.equal(await evaluate('loadingProbe.view.body.rows.length'),220);
  const transferred = await evaluate('loadingProbe.events.filter(event=>event.stage.startsWith("Loading session history"))');
   assert.deepEqual(transferred.map(event=>event.percent),[75,81,87,92,95]);
  assert.deepEqual(transferred.map(event=>event.stage),[50,100,150,200,220].map(count=>`Loading session history (${count} of 220)…`));
  assert.equal(await evaluate('loadingProbe.events.at(-1).percent===100 && loadingProbe.events.at(-1).rows===220'),true);
  await evaluate(`(async()=>{window.keptHistory=loadingProbe.view.body.firstChild;
    const target=keptHistory.querySelector('.help-value');target.focus();
    const range=document.createRange();range.selectNodeContents(target);getSelection().removeAllRanges();getSelection().addRange(range);
    window.keptSelection=getSelection().toString();window.keptFocus=document.activeElement;window.keptScroll=scrollY;
    loadingProbe.waiting=true;await loadingProbe.view.load();})()`);
  assert.equal(await evaluate(`loadingProbe.view.body.firstChild===keptHistory && loadingProbe.view.loader.root.hidden &&
    getSelection().toString()===keptSelection && document.activeElement===keptFocus && scrollY===keptScroll`),true);
  await evaluate(`(async()=>{getSelection().removeAllRanges();
    loadingProbe.view.api=async()=>{throw new Error('offline')};await loadingProbe.view.load()})()`);
  assert.equal(await evaluate('loadingProbe.view.body.firstChild===keptHistory && loadingProbe.view.loader.root.hidden'),true);
  checks.push('exact 220-row/50-row chunks; repeated unknown waits stay 0; 100 only after DOM; quiet refresh/outage preserves focus/selection/scroll');
  for (const total of [0,1]) {
    await evaluate(`loadingProbe.setup(${total},false)`); await until('!loadingProbe.view.busy');
    assert.equal(await evaluate('loadingProbe.view.body.rows.length'),total);
    assert.equal(await evaluate('loadingProbe.view.loader.bar.value'),100);
  }
  await evaluate(`loadingProbe.setup(220,false,true)`); await until('Boolean(loadingProbe.release)');
  await evaluate(`window.abandoned=loadingProbe.view;window.oldBar=abandoned.loader.bar;window.oldPercent=oldBar.value;
    const release=loadingProbe.release;loadingProbe.setup(1);release();`);
  await until('!abandoned.busy && !loadingProbe.view.busy');
  assert.equal(await evaluate('oldBar.value===oldPercent && loadingProbe.view.loader.bar.value===0 && abandoned.scroll.getAttribute("aria-busy")==="false"'),true);
  const count = await evaluate('loadingProbe.requests.length');
  await evaluate(`(async()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});await loadingProbe.view.poll();delete document.hidden;})()`);
  assert.equal(await evaluate('loadingProbe.requests.length'),count);
  checks.push('empty/one-chunk success; abandoned A chunk cannot update B; hidden-tab polling adds no requests');
  // Integrated Chromium input is renderer-local, never shared desktop keyboard/mouse.
  const back = await evaluate(`(()=>{const link=loadingProbe.view.root.querySelector('a');link.focus();
    const r=link.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...back});
  assert.equal(await evaluate(`loadingProbe.view.root.querySelector('a').matches(':hover')`),true);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await until('location.hash==="#/sessions"');
  await command('Page.navigateToHistoryEntry',{entryId:(await command('Page.getNavigationHistory')).entries.at(-2).id});
  await until('current.detail?.data?.total===1001');
  assert.equal(await evaluate('current.detail.loader.root.hidden'),true);
  const touch = await evaluate(`(()=>{const r=current.detail.root.querySelector('a').getBoundingClientRect();
    return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch]});
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await until('location.hash==="#/sessions"');
  checks.push('mouse hover / keyboard / emulated touch Show all sessions and real browser Back; no stuck busy state');
  return {checks,layouts};
};

// Actual browser page zoom, separate from the already-covered CSS-layout/input cases.
module.exports.zoom = async function sessionLoadingZoom({evaluate,until,command,browser,targetId,origin}) {
  const layouts=[], diagnostics=[];
  const settingsURL=browser.toLowerCase().endsWith('msedge.exe')?'edge://settings/appearance':'chrome://settings/appearance';
  await command('Emulation.clearDeviceMetricsOverride');
  const {windowId}=await command('Browser.getWindowForTarget',{targetId});
  await command('Browser.setWindowBounds',{windowId,bounds:{width:1366,height:1000}});
  for (const zoom of [1,1.25,1.5]) {
    await command('Page.navigate',{url:settingsURL});
    await until(`typeof chrome.settingsPrivate?.getDefaultZoom==='function'`);
    await evaluate(`new Promise(resolve=>chrome.settingsPrivate.setDefaultZoom(${zoom},resolve))`);
    assert.equal(await evaluate('new Promise(resolve=>chrome.settingsPrivate.getDefaultZoom(resolve))'),zoom);
    await command('Page.navigate',{url:origin+'/#/sessions'});
    await until('typeof current!=="undefined" && current?.catalog?.data?.total===120');
    await evaluate(`document.body.style.zoom=1;current.catalog.detach();
      window.zoomView=new SessionDetail.View(async(_,request)=>request.action==='open'?{token:'zoom'}:
        request.action==='close'?{}:{state:'loading',pending:true,result:null},'zoom');
      zoomView.attach(current.catalog.root);`);
    const diagnostic=await evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,cssZoom:getComputedStyle(document.body).zoom})');
    diagnostics.push({zoom,requestedWidth:1366,...diagnostic});
    assert.equal(diagnostic.cssZoom,'1');
    if(zoom!==1) {
      assert.ok(Math.abs(diagnostic.width*zoom-diagnostics[0].width)<3,'actual page zoom changes CSS viewport at fixed bounds');
      assert.ok(Math.abs(diagnostic.dpr/diagnostics[0].dpr-zoom)<.02,'DPR independently proves native page zoom');
    }
    for(const width of [360,768,1366,1920]) {
      const requestedWidth=Math.round(width*zoom);
      await command('Browser.setWindowBounds',{windowId,bounds:{width:requestedWidth,height:1000}});
      // Headless native windows clamp below 512px; emulate device bounds only
      // after the independent un-overridden viewport/DPR zoom diagnostic above.
      await command('Emulation.setDeviceMetricsOverride',{width:requestedWidth,height:1000,deviceScaleFactor:1,mobile:false});
      for(const theme of ['classic','web']) for(const scheme of ['light','dark']) {
        await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme},
          {name:'prefers-reduced-motion',value:'reduce'}]});
        await evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme)}`);
        const geometry=await evaluate(`(()=>{
          const root=zoomView.loader.root,bar=zoomView.loader.bar,r=root.getBoundingClientRect(),b=bar.getBoundingClientRect(),stage=zoomView.loader.stage.getBoundingClientRect();
          return {viewport:innerWidth,height:innerHeight,dpr:devicePixelRatio,cssZoom:getComputedStyle(document.body).zoom,
            centerX:Math.abs((b.left+b.right-r.left-r.right)/2),centerY:Math.abs((r.top+r.bottom-b.top-stage.bottom)/2),
            barWidth:b.width,barHeight:b.height,connected:root.isConnected,hidden:root.hidden,explicit:bar.hasAttribute('value'),value:bar.value,max:bar.max,
            animation:getComputedStyle(bar).animationName,overflow:document.documentElement.scrollWidth>innerWidth+1,
            warning:!zoomView.status.hidden,busyAncestor:root.closest('[aria-busy=true]')!==null};})()`);
        assert.ok(geometry.centerX<2);assert.ok(geometry.centerY<3);assert.ok(geometry.barWidth>100,JSON.stringify({zoom,width,theme,scheme,...geometry}));
        assert.equal(geometry.cssZoom,'1');assert.equal(geometry.explicit,true);assert.equal(geometry.max,100);
        assert.ok(Math.abs(geometry.viewport-width)<2,JSON.stringify({width,zoom,...geometry}));
        assert.ok(Math.abs(geometry.dpr-zoom)<.02);
        assert.equal(geometry.value,0);assert.equal(geometry.animation,'none');assert.equal(geometry.warning,false);
        assert.equal(geometry.overflow,false);assert.equal(geometry.busyAncestor,false);
        layouts.push({case:'native-browser-zoom',theme,scheme,zoom,targetCSSWidth:width,requestedWindowWidth:requestedWidth,...geometry});
      }
    }
    await command('Emulation.clearDeviceMetricsOverride');
    await command('Browser.setWindowBounds',{windowId,bounds:{width:1366,height:1000}});
  }
  return {layouts,checks:[`actual disposable-profile page zoom 100/125/150%; fixed-bounds viewport/DPR proof ${JSON.stringify(diagnostics)}`,
    '48 native-page-zoom Classic/Web light/dark loader layouts: explicit requested device/window/actual CSS widths; metrics override only for layout matrix after independent native-zoom proof; no CSS zoom or desktop effects']};
};

module.exports.firstLoad = async function firstLoad({evaluate,until,fixture}) {
   await fixture('detail-delayed');
   await evaluate(`window.firstLoadEvents=[];window.firstLoadStart=performance.now();window.detailRequests=[];
     const fetchDetail=window.fetch;window.fetch=(url,options)=>{
       if(url==='/api/detail')detailRequests.push(JSON.parse(options.body).action);
       return fetchDetail(url,options);};
    const status=SessionDetail.View.prototype.sourceStatus;
     SessionDetail.View.prototype.sourceStatus=function(value){status.call(this,value);
       firstLoadEvents.push({at:performance.now(),phase:value.acquisition?.phase,
         count:value.acquisition?.completed,sourcePercent:value.acquisition?.percent,
         completed:value.acquisition?.phase_completed,total:value.acquisition?.phase_total,
         percent:this.loader.bar.value,result:!!value.result});
       if(!value.result){const bar=this.loader.bar;requestAnimationFrame(()=>requestAnimationFrame(()=>
         firstLoadEvents.push({paintAt:performance.now(),percent:bar.value,visible:!this.loader.root.hidden,
           pending:!this.data,stable:bar===this.loader.bar,stage:this.loader.stage.textContent})));}};
    const update=SessionDetail.View.prototype.update;
    SessionDetail.View.prototype.update=function(value){update.call(this,value);window.firstLoadApplied=performance.now();};
     location.hash='#/sessions?sort=name&direction=1'`);
   await until(`document.querySelector('a[href="#/sessions/root-0000"]')`);
   await evaluate(`window.firstLoadStart=performance.now();document.querySelector('a[href="#/sessions/root-0000"]').click()`);
  await until('current.detail?.data?.total===1001 && !current.detail.busy');
  const lane=await fixture('detail-observe');
  const measured=await evaluate(`({elapsed:firstLoadApplied-firstLoadStart,
    appliedAt:performance.timeOrigin+firstLoadApplied,events:firstLoadEvents,
    rows:current.detail.body.rows.length,percent:current.detail.loader.bar.value})`);
  measured.publicationToDOM=measured.appliedAt-lane.metrics.published_at_ms;
  // timeOrigin, not the route start, qualifies the browser/host clock join.
  measured.publicationToBegin=await evaluate('performance.timeOrigin')+
     measured.events.find(e=>e.result).at-lane.metrics.published_at_ms;
  assert.ok(measured.elapsed>=5000 && measured.elapsed<15000,JSON.stringify(measured));
  assert.ok(measured.publicationToBegin>=0 && measured.publicationToBegin<1250,JSON.stringify(measured));
  assert.ok(measured.publicationToDOM>=0 && measured.publicationToDOM<3000,JSON.stringify(measured));
   const pending=measured.events.filter(e=>e.at && !e.result);
   const paints=measured.events.filter(e=>e.paintAt);
   assert.ok(pending.length>=5 && pending.length<25);
   assert.ok(pending.some(e=>e.phase==='reading' && e.count>0));
   assert.ok(new Set(pending.filter(e=>e.percent>0).map(e=>e.percent)).size>=3,'source work advances before any ready begin');
   assert.ok(paints.some(e=>e.pending && e.visible && e.stable && e.percent>0 && e.percent<70),'an intermediate value survives a genuine pending browser paint');
   assert.ok(pending.every((e,i)=>!i || e.percent>=pending[i-1].percent));
   assert.ok(pending.some(e=>e.total>0 && e.completed>0));
   measured.firstNonzero=pending.find(e=>e.percent>0).at-(await evaluate('firstLoadStart'));
   measured.source=lane;
   const warm=await evaluate(`(async()=>{const view=current.detail,bar=view.loader.bar,row=view.body.firstChild;
     const start=performance.now(),before=detailRequests.length;await view.load();
     return {milliseconds:performance.now()-start,requests:detailRequests.slice(before),
       retained:row===view.body.firstChild,stable:bar===view.loader.bar,hidden:view.loader.root.hidden};})()`);
   assert.ok(warm.retained && warm.stable && warm.hidden);
   assert.deepEqual(warm.requests,['begin']);
   assert.equal(lane.started,1);assert.equal(lane.metrics.work.snapshot_reads,1);
   measured.warm=warm;
   measured.requests=await evaluate('detailRequests');
  assert.equal(measured.rows,1001);assert.equal(measured.percent,100);
   return {measurements:measured,checks:['authenticated Sessions click / supervised source-shaped ~5s message batches / real 500ms pending status; several source-owned nonzero values before ready begin and across browser paints; publication-to-begin <1.25s and 1001-row DOM <3s; 100 only after apply']};
};
