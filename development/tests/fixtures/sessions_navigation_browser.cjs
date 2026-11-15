// Real HTTP/DTO/browser, seeded scalar keys; no personal source or model inference.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, until, fixture, command}) => {
  const checks = [], layouts = [];
  const load = () => evaluate('current.catalog.load()');
  const ids = () => evaluate('[...current.catalog.body.rows].map(row=>row.dataset.id)');
  const settled = offset => until(`current.catalog.data.offset===${offset} && !current.catalog.operation && !current.catalog.busy`);
  const singleBanner = async () => {
    assert.deepEqual(await evaluate(`(()=>{const c=current.catalog;return {
      statuses:c.root.querySelectorAll('[role=status]').length,progress:c.root.querySelectorAll('progress,.report-loading').length,
      cancel:[...c.root.querySelectorAll('button')].some(b=>b.textContent==='Cancel'),
      scope:!!c.root.querySelector('.sessions-candidate-scope'),
      order:[...c.root.children].map(n=>n===c.periods?'periods':n===c.status?'status':n===c.pan?'table':n===c.pager?'pager':'unexpected')};})()`),
      {statuses:1,progress:0,cancel:false,scope:false,order:['periods','status','table','pager']});
    assert.doesNotMatch(await evaluate('current.catalog.root.textContent'),/Periods verify prompt activity|Cancel|%/);
  };
  // Hold a genuine HTTP answer, not a synthetic controller update.
  const holdPage = async (button, offset) => {
    await evaluate(`window.pagerApi=current.catalog.api;window.releasePager=null;window.pagerHeld=false;
      current.catalog.api=async(...args)=>{const data=await pagerApi(...args);
        if(!args[1]?.action && args[1]?.offset===${offset} && !pagerHeld){pagerHeld=true;
          return new Promise(resolve=>{window.releasePager=()=>resolve(data);});}return data;};
      window.initiator=${button};initiator.focus();window.originalWidth=initiator.getBoundingClientRect().width;initiator.click()`);
    await until('window.releasePager && current.catalog.operation?.pending');
    await singleBanner();
    assert.equal(await evaluate(`current.catalog.operation.button===initiator && document.activeElement===initiator &&
      initiator.getAttribute('aria-busy')==='true' && initiator.getAttribute('aria-disabled')==='true' &&
      !initiator.disabled && initiator.querySelector('.sessions-page-spinner').getAttribute('aria-hidden')==='true'`),true);
    assert.equal(await evaluate(`current.catalog.pager.querySelectorAll('[aria-busy=true]').length`),1);
    assert.equal(await evaluate('initiator.getBoundingClientRect().width'),await evaluate('originalWidth'));
    const hash = await evaluate('location.hash');
    await evaluate('initiator.click()');
    assert.equal(await evaluate('location.hash'),hash,'aria-disabled initiating action is truly inert');
  };
  const releasePage = async offset => {
    await evaluate('releasePager();current.catalog.api=pagerApi');
    await settled(offset);
    assert.equal(await evaluate('current.catalog.pager.querySelectorAll("[aria-busy=true]").length'),0);
  };
  await fixture('catalog-large'); await fixture('catalog-index');
  await evaluate(`location.hash='#/sessions'`);
  await until('current.catalog?.data?.total===3217 && !current.catalog.busy');
  await singleBanner();
  assert.deepEqual(await evaluate('current.catalog.headers.map(header=>header.name)'),
    ['Last activity','Session name','Model','CCost','Prompts','Duration','Ctx']);
  await evaluate('current.catalog.headers[6].th.querySelector("button").focus()');
  await until('document.getElementById("context-help")?.textContent.includes("Estimated context for this session, in tokens.")');
  assert.doesNotMatch(await evaluate('document.getElementById("context-help").textContent'),/Activate to sort/);
  await holdPage('current.catalog.next',25);
  assert.match(await evaluate('current.catalog.status.textContent'),/Loading Sessions page 2/);
  for (const theme of ['classic','light','dark']) for (const width of [360,800,1366,1920]) for (const zoom of [1,1.5]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]});
    await evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme==='classic'?'classic':'web')};document.body.style.zoom=${zoom}`);
    const geometry = await evaluate(`(()=>{const c=current.catalog,b=initiator,s=b.querySelector('span'),busy=getComputedStyle(b),
      active=getComputedStyle(c.periodButtons[1].button);return {
      overflow:document.documentElement.scrollWidth>innerWidth+1,
      border:busy.borderTopStyle,enabledBorder:active.borderTopStyle,background:busy.backgroundColor,enabledBackground:active.backgroundColor,
      label:b.textContent,spinner:getComputedStyle(s).visibility,animation:getComputedStyle(s).animationName,
      textBeforeSpinner:b.firstChild.nodeType===Node.TEXT_NODE && s.getBoundingClientRect().right<=b.getBoundingClientRect().right,
      choices:c.periodButtons.every(({button})=>!button.disabled)&&c.headers.every(({th})=>!th.querySelector('button').disabled)};})()`);
    assert.equal(geometry.overflow,false,JSON.stringify({theme,width,zoom,...geometry})); assert.equal(geometry.border,'dashed'); assert.equal(geometry.enabledBorder,'solid');
    assert.notEqual(geometry.background,geometry.enabledBackground); assert.equal(geometry.label,'Next');
    assert.equal(geometry.spinner,'visible'); assert.equal(geometry.animation,'sessions-page-spin');
    assert.equal(geometry.textBeforeSpinner,true); assert.equal(geometry.choices,true);
    layouts.push({theme,width,zoom,...geometry});
  }
  await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  assert.equal(await evaluate('getComputedStyle(initiator.querySelector("span")).animationName'),'none');
  assert.equal(await evaluate('getComputedStyle(initiator.querySelector("span")).visibility'),'visible');
  await command('Emulation.setEmulatedMedia',{features:[]});
  await evaluate('document.body.style.zoom=1');
  await releasePage(25);
  assert.equal(await evaluate('document.activeElement===current.catalog.next'),true);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r',unmodifiedText:'\r'});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await settled(50);
  await holdPage('current.catalog.previous',25); await releasePage(25);
  assert.equal(await evaluate('document.activeElement===current.catalog.previous'),true);
  await holdPage('current.catalog.pageButtons.get(1)',0); await releasePage(0);
  assert.equal(await evaluate('document.activeElement===current.catalog.next'),true,'newly current numbered page transfers focus to an available action');
  await holdPage('current.catalog.next',25);
  await evaluate(`document.querySelector('nav a[href="#/accounts"]').focus()`);
  await releasePage(25);
  assert.equal(await evaluate('document.activeElement.getAttribute("href")'),'#/accounts','completion never steals deliberately moved focus');
  checks.push('Next/Previous/numbered initiating spinner, inert focused busy button, constant width, keyboard Enter, focus fallback/no theft; 24 theme/width/zoom layouts and reduced motion');
  const original = await ids();
  await fixture('catalog-clear');
  await evaluate(`current.catalog.headers[3].th.querySelector('button').focus()`);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r',unmodifiedText:'\r'});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await until('current.catalog.operation?.pending');
  await singleBanner();
  assert.equal(await evaluate('current.catalog.data.sort'),'activity');
  assert.equal(await evaluate('current.catalog.pan.hidden || current.catalog.pager.hidden'),false);
  assert.equal(await evaluate('current.catalog.pager.querySelectorAll("[aria-busy=true]").length'),0,'sorts never impersonate page clicks');
  await fixture('catalog-partial'); await load();
  assert.equal(await evaluate('current.catalog.operation.completed'),428);
  const status = await evaluate('current.catalog.status.textContent');
   assert.equal(status,'Sorting sessions by CCost · 428 of 3,217 sessions');
  for (let update=0;update<20;update++) {
    await fixture('catalog-churn'); await load();
    assert.equal(await evaluate('current.catalog.operation.failed'),false);
     assert.match(await evaluate('current.catalog.status.textContent'),/^Sorting sessions by CCost · \d/);
    assert.equal(await evaluate('current.catalog.statusCount.textContent.includes(current.catalog.operation.completed.toLocaleString("en-US")+" of 3,217")'),true);
    assert.equal(await evaluate('current.catalog.statusCount.getAttribute("aria-live")'),'off');
  }
  await evaluate('history.back()');
  await settled(25); assert.deepEqual(await ids(),original);
  checks.push('cold CCost preserves actual Activity page; 20 source generations visibly advance source counts without per-count live announcements; Back retires pending sort');
  await evaluate(`window.normalCatalogApi=current.catalog.api;window.catalogHeld=false;
    current.catalog.api=async(...args)=>{const data=await normalCatalogApi(...args);
      if(!args[1]?.action && args[1]?.sort==='ccost' && !catalogHeld){catalogHeld=true;
        return new Promise(resolve=>{window.releaseCatalog=()=>resolve(data);});}return data;};
    current.catalog.headers[3].th.querySelector('button').click()`);
  await until('window.releaseCatalog && current.catalog.operation?.pending');
  await evaluate('history.back()'); await settled(25);
  await evaluate('releaseCatalog();current.catalog.api=normalCatalogApi');
  assert.deepEqual(await ids(),original);
  assert.equal(await evaluate('current.catalog.data.sort'),'activity');
  checks.push('Back supersedes held post-HTTP sort; late answer cannot replace retained page');
  await evaluate(`current.catalog.headers[6].th.querySelector('button').click()`);
  await until('current.catalog.operation?.pending');
  await fixture('fail'); await load();
  await until('current.catalog.operation && !current.catalog.operation.failed && current.catalog.retryDelay>0');
  assert.equal(await evaluate('current.catalog.data.sort'),'activity');
  assert.equal(await evaluate('current.catalog.pan.hidden'),false);
   assert.match(await evaluate('current.catalog.status.textContent'),/Sorting sessions by Ctx.*Loading paused\. Retrying/);
  await fixture('recover'); await fixture('catalog-index');
  await until('api("/api/sessions",{token:current.catalog.token}).then(data=>data.state==="observed")');
  await evaluate('current.catalog.poll()');
  await until('current.catalog.data.sort==="ctx" && !current.catalog.operation && !current.catalog.busy');
  checks.push('cold Ctx outage retains actual Activity; automatic recovery applies globally qualified Ctx');
  await evaluate(`window.spinnerFlashes=0;window.disabledFlashes=0;window.spinnerObserver=new MutationObserver(records=>{
    spinnerFlashes+=records.filter(record=>record.attributeName==='aria-busy' &&
      (record.oldValue==='true'||record.target.getAttribute('aria-busy')==='true')).length;
    disabledFlashes+=records.filter(record=>record.attributeName==='disabled'&&record.target===current.catalog.next).length;
  });spinnerObserver.observe(current.catalog.pager,{subtree:true,attributes:true,attributeFilter:['aria-busy','disabled'],attributeOldValue:true});`);
  const timings = [];
  for (const sort of ['activity','name','model','ccost','prompts','duration','ctx']) for (const direction of [1,-1]) {
    const started = Date.now();
    await evaluate(`location.hash='#/sessions?sort=${sort}&direction=${direction}'`);
    await until(`current.catalog.data.sort==='${sort}' && current.catalog.data.direction===${direction} && !current.catalog.operation`);
    const rows = await ids();
    assert.equal(rows.length,25); assert.equal(rows[0],direction===1?'root-0000':'root-3216');
    timings.push({sort,direction,milliseconds:Date.now()-started});
  }
  assert.equal(await evaluate('spinnerFlashes'),0);
  // Validated warm page navigation and a slow passive HTTP poll never look busy.
  await evaluate('current.catalog.next.click()'); await settled(25);
  await evaluate(`window.passiveRelease=null;window.passiveApi=current.catalog.api;
    current.catalog.api=async(...args)=>{const data=await passiveApi(...args);return args[1]?.action?data:
      new Promise(resolve=>{passiveRelease=()=>resolve(data);});};window.passive=current.catalog.load();void 0`);
  await until('window.passiveRelease!==null');
  assert.equal(await evaluate('current.catalog.next.disabled'),false);
  assert.equal(await evaluate('spinnerFlashes'),0);
  assert.equal(await evaluate('disabledFlashes'),0);
  await evaluate('passiveRelease();current.catalog.api=passiveApi;passive');
  await evaluate('spinnerObserver.disconnect()');
  checks.push({warm_scoped_sorts:timings,eligible_keys:3217,rendered_rows:25});
  // The deliberate Ctx click above pinned its help. Begin the touch toggle from
  // a known closed state rather than accidentally testing a second-close click.
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  await until('!document.getElementById("context-help")?.matches(":popover-open")');
  await command('Emulation.setTouchEmulationEnabled',{enabled:true});
  const ctxTouch = await evaluate(`(()=>{const b=current.catalog.headers[6].th.querySelector('button');b.scrollIntoView();const r=b.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[ctxTouch]});
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await until('current.catalog.data.sort==="ctx" && current.catalog.data.direction===1 && !current.catalog.operation');
  await until('document.getElementById("context-help")?.matches(":popover-open")');
  assert.match(await evaluate('document.getElementById("context-help").textContent'),/Estimated context for this session/);
  await command('Emulation.setTouchEmulationEnabled',{enabled:false});
  await evaluate(`location.hash='#/sessions?sort=activity&direction=-1'`);
  await until('current.catalog.data.sort==="activity" && !current.catalog.busy');
  await fixture('catalog-page-cold');
  const pageOne = await ids();
  await evaluate('current.catalog.next.focus();current.catalog.next.click()');
  await until('current.catalog.operation?.kind==="page" && current.catalog.operation.pending');
  assert.equal(await evaluate('current.catalog.operation.completed'),0);
  assert.deepEqual(await ids(),pageOne,'pending page never replaces the last applied rows under the old pager');
  await evaluate('history.back()'); await settled(0);
  assert.deepEqual(await ids(),pageOne);
  await evaluate('current.catalog.next.click()');
  await until('current.catalog.operation?.kind==="page"');
  await fixture('fail'); await load();
  await until('current.catalog.operation && current.catalog.retryDelay>0');
  await singleBanner();
  await fixture('recover'); await fixture('catalog-index');
  await until('api("/api/sessions",{token:current.catalog.token}).then(data=>data.state==="observed")');
  await evaluate('current.catalog.poll()'); await settled(25);
  const epoch = await evaluate('current.catalog.data.epoch');
  await evaluate(`location.hash='#/sessions?sort=activity&direction=-1&offset=3175&epoch=${epoch}'`);
  await settled(3175);
  await evaluate('current.catalog.next.focus();current.catalog.next.click()'); await settled(3200);
  assert.equal(await evaluate('document.activeElement===current.catalog.previous'),true);
  assert.equal((await ids()).length,17);
  assert.match(await evaluate('current.catalog.label.textContent'),/3201–3217 of 3217/);
  await evaluate('history.back()'); await settled(3175);
  await evaluate('history.forward()'); await settled(3200);
  await holdPage('current.catalog.previous',3175);
  await evaluate(`window.detachedCatalog=current.catalog;location.hash='#/accounts'`);
  await until('current.section==="accounts"');
  assert.equal(await evaluate('detachedCatalog.pager.querySelectorAll("[aria-busy=true]").length'),0);
  await evaluate('releasePager();detachedCatalog.api=pagerApi');
  checks.push('trusted touch Ctx help; uncached page Back supersession, automatic outage recovery, 17-row last page, Back/Forward; route exit clears spinner');
  return {checks,layouts};
};
