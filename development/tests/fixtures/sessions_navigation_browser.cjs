// Real HTTP/DTO/browser, seeded scalar keys; no personal source or model inference.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, until, fixture, command}) => {
  const checks = [], layouts = [];
  const load = () => evaluate('current.catalog.load()');
  const ids = () => evaluate('[...current.catalog.body.rows].map(row=>row.dataset.id)');
  await fixture('catalog-large'); await fixture('catalog-index');
  await evaluate(`location.hash='#/sessions'`);
  await until('current.catalog?.data?.total===3217');
  assert.deepEqual(await evaluate('current.catalog.headers.map(header=>header.name)'),
    ['Last activity','Session name','Model','Effort','CCost','Prompts','Duration','CTX']);
  await evaluate('current.catalog.headers[7].th.querySelector("button").focus()');
  await until('document.getElementById("context-help")?.textContent.includes("Estimated session-level next incoming context")');
  assert.match(await evaluate('document.getElementById("context-help").textContent'),/not remaining model capacity or a sum of prompts[\s\S]*selected period/);
  await evaluate(`window.pagerApi=current.catalog.api;window.pagerHeld=false;
    current.catalog.api=async(...args)=>{const data=await pagerApi(...args);
      if(!args[1]?.action && args[1]?.offset===25 && !pagerHeld){pagerHeld=true;
        return new Promise(resolve=>{window.releasePager=()=>resolve(data);});}return data;};`);
  const nextPoint = await evaluate(`(()=>{current.catalog.next.scrollIntoView();const r=current.catalog.next.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await command('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...nextPoint});
  await command('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...nextPoint});
  await until('window.releasePager && !current.catalog.loader.root.hidden');
  assert.equal(await evaluate('document.activeElement===current.catalog.cancel'),true);
  assert.equal(await evaluate('current.catalog.operation.focus===current.catalog.next'),true,'operation remembers the activating pager');
  await evaluate('releasePager();current.catalog.api=pagerApi');
  await until('current.catalog.data.offset===25 && !current.catalog.operation && !current.catalog.busy');
  assert.equal(await evaluate('document.activeElement===current.catalog.next'),true,'page navigation retains Next focus');
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r',unmodifiedText:'\r'});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await until('current.catalog.data.offset===50 && !current.catalog.operation && !current.catalog.busy');
  await evaluate('current.catalog.previous.focus();current.catalog.previous.click()');
  await until('current.catalog.data.offset===25 && !current.catalog.operation && !current.catalog.busy');
  assert.equal(await evaluate('document.activeElement===current.catalog.previous'),true,'page navigation retains Previous focus');
  await evaluate(`window.releasePager=null;window.pagerHeld=false;
    current.catalog.api=async(...args)=>{const data=await pagerApi(...args);
      if(!args[1]?.action && args[1]?.offset===50 && !pagerHeld){pagerHeld=true;
        return new Promise(resolve=>{window.releasePager=()=>resolve(data);});}return data;};
    current.catalog.next.focus();current.catalog.next.click()`);
  await until('window.releasePager && !current.catalog.loader.root.hidden');
  await evaluate(`document.querySelector('nav a[href="#/accounts"]').focus();releasePager();current.catalog.api=pagerApi`);
  await until('current.catalog.data.offset===50 && !current.catalog.operation && !current.catalog.busy');
  assert.equal(await evaluate('document.activeElement.getAttribute("href")'),'#/accounts','completion cannot steal deliberately moved focus');
  await evaluate('current.catalog.previous.focus();current.catalog.previous.click()');
  await until('current.catalog.data.offset===25 && !current.catalog.operation && !current.catalog.busy');
  checks.push('delayed page mouse activation, loading Cancel focus, enabled Next restoration, trusted Enter, Previous focus and no focus theft');
  const original = await ids();
  const oldHash = await evaluate('location.hash');
  await fixture('catalog-clear');
   await evaluate(`current.catalog.headers[4].th.querySelector('button').focus()`);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r',unmodifiedText:'\r'});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await until('current.catalog.operation && !current.catalog.loader.root.hidden');
  assert.equal(await evaluate('current.catalog.data.sort'),'activity');
  assert.equal(await evaluate('current.catalog.pan.hidden && current.catalog.pager.hidden'),true);
  assert.equal(await evaluate('current.catalog.loader.bar.value'),0);
  await fixture('catalog-partial'); await load();
  assert.equal(await evaluate('current.catalog.loader.bar.value'),13);
   assert.match(await evaluate('current.catalog.count.textContent'),/428 of 3,217/);
   assert.equal(await evaluate('current.catalog.task.textContent'),'Sorting sessions by CCost');
   await evaluate('window.stableBar=current.catalog.loader.bar;window.stableTask=current.catalog.task;window.stableCount=current.catalog.count');
   const slots = [];
   for (let update=0;update<20;update++) {
     await fixture('catalog-churn'); await load();
     slots.push(await evaluate(`(()=>{const c=current.catalog;return {heading:c.task.textContent,count:c.count.textContent,
       failed:c.operation.failed,identity:stableBar===c.loader.bar&&stableTask===c.task&&stableCount===c.count,
       positions:[c.task,c.loader.bar,c.count,c.loader.stage,c.cancel].map(n=>Math.round(n.getBoundingClientRect().top))};})()`));
   }
   assert.equal(new Set(slots.map(value=>value.count)).size,20);
   for (const slot of slots) {
     assert.equal(slot.heading,'Sorting sessions by CCost'); assert.equal(slot.failed,false); assert.equal(slot.identity,true);
     assert.deepEqual(slot.positions,slots[0].positions,'20 source generations/counts keep the same geometry');
   }
   checks.push({source_churn_updates:20,stable_slots:slots[0].positions,final_count:slots.at(-1).count});
  // Hover/focus help belongs to the Cancel button, not a nearby caption.
  await evaluate('current.catalog.cancel.focus()');
  await until('document.getElementById("context-help")?.textContent.includes("Cancel this sort")');
  assert.equal(await evaluate('current.catalog.cancel.getAttribute("aria-describedby")'),'context-help');
  for (const theme of ['classic','light','dark']) for (const width of [360,800,1366,1920]) for (const zoom of [1,1.5]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]});
    await evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme==='classic'?'classic':'web')};document.body.style.zoom=${zoom}`);
    const geometry = await evaluate(`(()=>{const panel=current.catalog.loader.root,bar=panel.querySelector('progress').getBoundingClientRect(),
       cancel=current.catalog.cancel.getBoundingClientRect(),box=panel.getBoundingClientRect(),
       task=current.catalog.task.getBoundingClientRect(),count=current.catalog.count.getBoundingClientRect(),work=current.catalog.loader.stage.getBoundingClientRect();return {
       center:Math.abs((bar.left+bar.right)/2-(box.left+box.right)/2),below:cancel.top>=bar.bottom,
       slots:task.bottom<=bar.top&&count.top>=bar.bottom&&work.top>=count.bottom&&cancel.top>=work.bottom,
      overflow:document.documentElement.scrollWidth>innerWidth+1,determinate:panel.querySelector('progress').hasAttribute('value'),
      animated:getComputedStyle(panel.querySelector('progress')).animationName};})()`);
     assert.ok(geometry.center<2); assert.equal(geometry.below,true); assert.equal(geometry.overflow,false);
     assert.equal(geometry.slots,true);
    assert.equal(geometry.determinate,true); assert.equal(geometry.animated,'none');
    layouts.push({theme,width,zoom,...geometry});
  }
  await evaluate('current.catalog.cancel.click()');
  assert.equal(await evaluate('location.hash'),oldHash);
  assert.deepEqual(await ids(),original);
  assert.equal(await evaluate('current.catalog.offset'),25);
   assert.equal(await evaluate('document.activeElement===current.catalog.headers[4].th.querySelector("button")'),true);
  await until('!current.catalog.busy');
   checks.push('eight headers; CTX heading help; trusted Enter starts cold scoped CCost 0/428 progress over 3217 roots; old-page/sort/hash/focus Cancel; determinate layout 24 combinations');
  await evaluate(`window.normalCatalogApi=current.catalog.api;window.catalogHeld=false;
    current.catalog.api=async(...args)=>{const data=await normalCatalogApi(...args);
      if(!args[1]?.action && args[1]?.sort==='ccost' && !catalogHeld){catalogHeld=true;
        return new Promise(resolve=>{window.releaseCatalog=()=>resolve(data);});}return data;};
    current.catalog.headers[4].th.querySelector('button').click()`);
  await until('window.releaseCatalog && !current.catalog.loader.root.hidden');
  await evaluate('current.catalog.cancel.focus()');
  assert.equal(await evaluate('document.activeElement===current.catalog.cancel && !current.catalog.cancel.disabled && current.catalog.cancel.getBoundingClientRect().height>0'),true);
  await evaluate(`window.cancelKeys=[];current.catalog.cancel.addEventListener('keydown',event=>cancelKeys.push(event.key));
    current.catalog.cancel.addEventListener('click',()=>cancelKeys.push('click'))`);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r',unmodifiedText:'\r'});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await until('!current.catalog.operation && !current.catalog.busy');
  assert.deepEqual(await evaluate('cancelKeys'),['Enter','click']);
  await evaluate('releaseCatalog();Promise.resolve().then(()=>Promise.resolve())');
  await until('!current.catalog.busy');
  assert.equal(await evaluate('current.catalog.data.sort'),'activity');
  assert.equal(await evaluate('current.catalog.data.offset'),25); assert.deepEqual(await ids(),original);
  await evaluate('current.catalog.api=normalCatalogApi');
  checks.push('trusted keyboard Enter activates Cancel; held post-HTTP answer cannot replace original page/sort');
  await evaluate(`location.hash='#/sessions?sort=ctx&direction=1'`);
  await until('current.catalog.operation && !current.catalog.loader.root.hidden');
  await fixture('fail'); await load();
   await until('current.catalog.operation?.failed && !current.catalog.retry.hidden');
   assert.equal(await evaluate('current.catalog.data.sort'),'activity');
   assert.equal(await evaluate('current.catalog.pan.hidden'),true,'failure cannot reveal the old order above its error');
   assert.equal(await evaluate('current.catalog.task.textContent'),'Sorting sessions by CTX');
   assert.match(await evaluate('current.catalog.loader.stage.textContent'),/source_unavailable/);
  await fixture('recover');
  await fixture('catalog-index');
  await until('api("/api/sessions",{token:current.catalog.token}).then(data=>data.state==="observed")');
  await evaluate('current.catalog.retry.click()');
  await until('current.catalog.data.sort==="ctx" && !current.catalog.operation && !current.catalog.busy');
  checks.push('cold CTX outage retains actual Activity; visible Retry recovers to globally qualified CTX');
  // Observe actual layout swaps, not just final hidden state, for cached navigation.
  await evaluate(`window.loaderFlashes=0;window.loaderObserver=new MutationObserver(records=>{
    for(const record of records)if(record.oldValue===null)loaderFlashes++;
  });loaderObserver.observe(current.catalog.loader.root,{attributes:true,attributeFilter:['hidden'],attributeOldValue:true});`);
  const timings = [];
  for (const sort of ['activity','name','model','ccost','prompts','duration','ctx']) for (const direction of [1,-1]) {
    const started = Date.now();
    await evaluate(`location.hash='#/sessions?sort=${sort}&direction=${direction}'`);
    await until(`current.catalog.data.sort==='${sort}' && current.catalog.data.direction===${direction} && !current.catalog.operation`);
    const rows = await ids();
    assert.equal(rows.length,25); assert.equal(rows[0],direction===1?'root-0000':'root-3216');
    timings.push({sort,direction,milliseconds:Date.now()-started});
  }
  assert.equal(await evaluate('loaderFlashes'),0,'all warm sorts apply without a loading layout swap');
  await evaluate('loaderObserver.disconnect()');
  checks.push({warm_scoped_sorts:timings,eligible_keys:3217,rendered_rows:25});
  await command('Emulation.setTouchEmulationEnabled',{enabled:true});
  const ctxTouch = await evaluate(`(()=>{const b=current.catalog.headers[7].th.querySelector('button');b.scrollIntoView();const r=b.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[ctxTouch]});
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await until('current.catalog.data.sort==="ctx" && current.catalog.data.direction===1 && !current.catalog.operation');
  await until('document.getElementById("context-help")?.matches(":popover-open")');
  assert.match(await evaluate('document.getElementById("context-help").textContent'),/Estimated session-level/);
  await command('Emulation.setTouchEmulationEnabled',{enabled:false});
  checks.push('trusted touch reverses CTX sort and exposes its heading help on the same retained button');
  await evaluate(`location.hash='#/sessions?sort=activity&direction=-1'`);
  await until('current.catalog.data.sort==="activity"');
  await fixture('catalog-page-cold');
  const pageOne = await ids();
  await evaluate('current.catalog.next.focus();current.catalog.next.click()');
  await until('current.catalog.operation?.kind==="page" && !current.catalog.loader.root.hidden');
   assert.match(await evaluate('current.catalog.count.textContent'),/0 of 25/);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  await evaluate('current.catalog.cancel.focus()');
  await until('document.getElementById("context-help")?.textContent.includes("Cancel loading this page")');
  await command('Emulation.setTouchEmulationEnabled',{enabled:true});
  const touch = await evaluate(`(()=>{const r=current.catalog.cancel.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch]});
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await until('!current.catalog.operation');
  assert.deepEqual(await ids(),pageOne); assert.equal(await evaluate('current.catalog.offset'),0);
  await command('Emulation.setTouchEmulationEnabled',{enabled:false});
  await until('!current.catalog.busy');
  await evaluate(`current.catalog.next.click()`);
  await until('current.catalog.operation?.kind==="page"');
  await fixture('fail'); await load();
  await until('current.catalog.operation?.failed');
  assert.equal(await evaluate('current.catalog.retry.hidden'),false);
   assert.equal(await evaluate('current.catalog.pan.hidden'),true,'failure keeps prior rows recoverable behind the actionable error');
  await fixture('recover'); await fixture('catalog-index');
  await until('api("/api/sessions",{token:current.catalog.token}).then(data=>data.state==="observed")');
  await evaluate('current.catalog.retry.click()');
  await until('current.catalog.data.offset===25 && !current.catalog.operation');
  const epoch = await evaluate('current.catalog.data.epoch');
  await evaluate(`location.hash='#/sessions?sort=activity&direction=-1&offset=3175&epoch=${epoch}'`);
  await until('current.catalog.data.offset===3175 && !current.catalog.busy');
  await evaluate('current.catalog.next.focus();current.catalog.next.click()');
  await until('current.catalog.data.offset===3200 && !current.catalog.busy');
  assert.equal(await evaluate('document.activeElement===current.catalog.previous'),true,'last-page Next hands focus to enabled Previous');
  await evaluate(`location.hash='#/sessions?sort=activity&direction=-1&offset=50&epoch=${epoch}'`);
  await until('current.catalog.data.offset===50 && !current.catalog.busy');
  await evaluate(`location.hash='#/sessions?sort=activity&direction=-1&offset=3200&epoch=${epoch}'`);
  await until('current.catalog.data.offset===3200 && !current.catalog.operation');
  assert.equal((await ids()).length,17);
  assert.match(await evaluate('current.catalog.label.textContent'),/3201–3217 of 3217/);
  await evaluate('history.back()'); await until('current.catalog.data.offset===50 && !current.catalog.operation');
  await evaluate('history.forward()'); await until('current.catalog.data.offset===3200 && !current.catalog.operation');
  checks.push('uncached page 0/25, operation-specific button help, touch Cancel, outage visible Retry, exact 17-row last page, Back/Forward');
  return {checks,layouts};
};
