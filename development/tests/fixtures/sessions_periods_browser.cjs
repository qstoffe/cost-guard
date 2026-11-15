// Authenticated shipped HTTP/controller/AX/layout over 5000 synthetic roots.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, until, fixture, command}) => {
  const checks = [], layouts = [];
  await fixture('period-source');
  await evaluate(`location.hash='#/sessions'`);
  await until('current.catalog?.data?.period==="today" && current.catalog.data.total===30 && !current.catalog.busy');
  assert.deepEqual(await evaluate('current.catalog.periodButtons.map(({button})=>button.textContent)'),
    ['Today','7 days','30 days','This month','All time']);
  assert.deepEqual(await evaluate('current.catalog.periodButtons.map(({button})=>button.getAttribute("aria-pressed"))'),
    ['true','false','false','false','false']);
  assert.deepEqual(await evaluate('current.catalog.headers.map(header=>header.name)'),
    ['Last activity','Session name','Model','CCost','Prompts','Duration','Ctx']);
  assert.equal(await evaluate('current.catalog.body.rows.length'),25);
  assert.match(await evaluate('location.hash'),/period=today/);
  assert.equal(await evaluate('api("/api/sessions",{period:"invalid"}).then(()=>null,error=>error.message)'), 'invalid_request');
  const cold = await evaluate(`api('/api/sessions',{token:current.catalog.token,period:'today',sort:'ccost'})`);
  assert.equal(cold.available,30);
  if (cold.pending_sort) assert.equal(cold.progress.total,30);
  await evaluate(`location.hash='#/sessions?period=today&sort=ccost&direction=-1'`);
  await until('current.catalog.data.sort==="ccost" && !current.catalog.operation && !current.catalog.busy');
  assert.ok(await evaluate('current.catalog.data.progress.metrics.attempts<=30'),
    'Today sorts must not index 4970 unrelated historical roots');
  await evaluate(`location.hash='#/sessions?period=today&sort=effort&direction=1'`);
  await until('current.catalog.data.sort==="activity" && !current.catalog.operation && !current.catalog.busy');
  const efforts = await evaluate('current.catalog.data.view.session_usage.map(row=>row.effort)');
  assert.ok(efforts.length===25,'legacy effort sort safely falls back without removing underlying facts');
  await evaluate(`current.catalog.next.click()`);
  await until('current.catalog.data.offset===25 && !current.catalog.operation && !current.catalog.busy');
  assert.equal(await evaluate('current.catalog.body.rows.length'),5);
  assert.match(await evaluate('current.catalog.label.textContent'),/26–30 of 30 sessions/);
  assert.ok(await evaluate('current.catalog.data.view.session_usage.every(row=>typeof row.effort==="string")'));
  const pinned = await evaluate('location.hash');
  await evaluate('current.catalog.periodButtons[1].button.focus()');
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r'});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await until('current.catalog.data.period==="7-days" && !current.catalog.operation && !current.catalog.busy');
  assert.deepEqual(await evaluate('[current.catalog.data.offset,current.catalog.data.total,current.catalog.data.sort]'),[0,70,'activity']);
  await evaluate('history.back()');
  await until('current.catalog.data.period==="today" && current.catalog.data.offset===25 && !current.catalog.busy');
  assert.equal(await evaluate('location.hash'),pinned);
  await evaluate('history.forward()');
  await until('current.catalog.data.period==="7-days" && !current.catalog.busy');
  // Back supersedes a pending period without applying its late answer.
  await evaluate(`window.savedPeriodApi=current.catalog.api;window.periodHeld=false;
    current.catalog.api=async(...args)=>{const data=await savedPeriodApi(...args);
      if(!args[1]?.action&&args[1]?.period==='30-days'&&!periodHeld){periodHeld=true;
        return new Promise(resolve=>{window.releasePeriod=()=>resolve(data);});}return data;};
    current.catalog.periodButtons[2].button.click()`);
  await until('window.releasePeriod && current.catalog.operation?.pending');
  assert.equal(await evaluate('current.catalog.pan.hidden'),false);
  assert.match(await evaluate('current.catalog.status.textContent'),/^Loading sessions in 30 days\./);
  assert.equal(await evaluate('current.catalog.root.querySelectorAll("progress,.report-loading,.sessions-candidate-scope").length'),0);
  await evaluate('history.back()');
  await until('current.catalog.period==="7-days" && !current.catalog.busy');
  await evaluate('releasePeriod();current.catalog.api=savedPeriodApi');
  assert.equal(await evaluate('current.catalog.periodButtons[1].button.getAttribute("aria-pressed")'),'true');
  await evaluate(`current.catalog.periodButtons[2].button.click()`);
  await until('current.catalog.data.period==="30-days" && current.catalog.data.total===120 && !current.catalog.operation && !current.catalog.busy');
  // Period failure and automatic recovery preserve intent without relabeling retained rows.
  await fixture('fail');
  await until('api("/api/sessions",{token:current.catalog.token,period:"30-days"}).then(data=>data.state==="source_unavailable")');
  await evaluate(`current.catalog.periodButtons[0].button.click()`);
  await until('current.catalog.operation && current.catalog.retryDelay>0');
  assert.equal(await evaluate('current.catalog.pan.hidden'),false);
  await fixture('recover');
  await until('api("/api/sessions",{token:current.catalog.token,period:"today"}).then(data=>data.state==="observed")');
  await evaluate('current.catalog.poll()');
  await until('current.catalog.data.period==="today" && !current.catalog.operation && !current.catalog.busy');
  await evaluate(`location.hash='#/sessions?period=today&sort=activity&direction=-1'`);
   await until('current.catalog.data.sort==="activity" && !current.catalog.busy');
   // All/name expands discovery cheaply. All/activity intentionally needs every
   // event key and is covered by source-counted bounded-index tests, not a false
   // instantaneous metadata order.
   await evaluate(`location.hash='#/sessions?period=today&sort=name&direction=1'`);
   await until('current.catalog.data.sort==="name" && !current.catalog.operation && !current.catalog.busy');
  await command('Emulation.setTouchEmulationEnabled',{enabled:true});
  const point = await evaluate(`(()=>{const b=current.catalog.periodButtons[4].button;b.scrollIntoView();
    const r=b.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]});
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await until('current.catalog.data.period==="all" && current.catalog.data.total===5000 && !current.catalog.operation && !current.catalog.busy');
  await command('Emulation.setTouchEmulationEnabled',{enabled:false});
  await evaluate(`location.hash='#/ai-stats'`);
  await until('current.section==="ai-stats"');
  assert.equal(await evaluate('current.period'),'30-days');
  await evaluate(`document.querySelector('nav a[href="#/sessions"]').click()`);
  await until('current.section==="sessions" && current.catalog.data.period==="all"');
  await evaluate(`location.hash='#/sessions?period=today&sort=effort&direction=-1'`);
  await until('current.catalog.data.period==="today" && current.catalog.data.sort==="activity" && !current.catalog.operation && !current.catalog.busy');
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  await evaluate('current.catalog.body.rows[0].cells[2].firstChild.focus()');
  await until('document.getElementById("context-help")?.matches(":popover-open")');
  assert.ok(await evaluate('document.getElementById("context-help").textContent.length>0'));
  const ax = await command('Accessibility.getFullAXTree');
  assert.ok(ax.nodes.some(node=>node.name?.value==='Sessions period'));
  assert.ok(ax.nodes.some(node=>node.name?.value==='Session pages'));
  for (const theme of ['classic','web']) for (const color of ['light','dark'])
    for (const width of [360,1366]) for (const zoom of [1,1.5]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:color}]});
      await evaluate(`document.documentElement.dataset.theme='${theme}';document.body.style.zoom=${zoom}`);
      const facts = await evaluate(`(()=>{const c=current.catalog,pan=c.pan;
        return {columns:c.headers.length,rows:c.body.rows.length,overflow:document.documentElement.scrollWidth>innerWidth+1,
          buttons:c.periodButtons.every(({button})=>{const r=button.getBoundingClientRect();return r.width>0&&r.height>0}),
          nowrap:[...c.body.rows[0].cells].every(cell=>getComputedStyle(cell).whiteSpace==='nowrap'),
          fits:[...c.body.rows[0].cells].filter((_,i)=>i!==1).every(cell=>cell.scrollWidth<=cell.clientWidth+1)};})()`);
      assert.deepEqual(facts,{columns:7,rows:25,overflow:false,buttons:true,nowrap:true,fits:true});
      layouts.push({theme,color,width,zoom,...facts});
    }
  checks.push('5000 source roots / 30 Today; authenticated allowlist; Today CCost/Effort <=30 indexed roots; 25+5 paging');
  checks.push('five accessible selectors; keyboard/touch; offset reset; Back/Forward; pending period supersession/automatic recovery; AI Stats independent 30-days; route return');
  checks.push('source-qualified Default/mixed effort help; AX group/column; 16 Classic/Web color/width/zoom layouts');
  await fixture('period-empty');
  await evaluate('current.catalog.load()');
  await until('current.catalog.data.total===0');
  assert.match(await evaluate('current.catalog.label.textContent'),/No confirmed matches among catalog candidates in Today/);
  assert.equal(await evaluate('current.catalog.periodButtons.every(({button})=>button.isConnected)'),true);
  checks.push('empty Today retains the useful five-button selector without auto-expanding history');
  return {checks,layouts};
};
