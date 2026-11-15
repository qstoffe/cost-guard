// Real HTTP/normalization/DTO/DOM: the same causal fixtures as backend truth tests.
const assert = require('node:assert/strict');
module.exports = async ({evaluate,until,fixture,command,zoom}) => {
  const checks=[],layouts=[];
  const cases=[
    ['one',false,false],['child-same',true,true],['child-effort',true,true],
    ['child-model',true,true],['main-models',true,true],['main-efforts',true,true],
    ['separate-efforts',true,false],['running-child',true,true],['unknown-main',true,true],
    ['native-same',true,true,'u1'],['native-effort',true,true,'u1']
  ];
  await fixture('model-details-source');
  for(const [name,catalogStar,promptStar,event='u_sub'] of cases) {
    await evaluate("location.hash='#/sessions?period=all&sort=model&direction=1'");
    await until('current.catalog?.data?.total===11 && !current.catalog.busy && !current.catalog.operation && current.catalog.data.view.session_usage.length===11');
    await evaluate(`window.catalogRow=[...current.catalog.body.rows].find(row=>row.value.session_id===${JSON.stringify('details-'+name)})`);
    await until(`catalogRow.value.has_model_details===${catalogStar}`);
    const catalog=await evaluate(`({text:catalogRow.cells[2].textContent,
      model:catalogRow.value.model,sort:current.catalog.data.sort})`);
    assert.equal(catalog.text,catalog.model+(catalogStar?'*':''));
    assert.equal(catalog.sort,'model');
    if(name==='unknown-main')assert.equal(catalog.text,'N/A*');
    await evaluate("catalogRow.cells[2].firstChild.focus()");
    const catalogHelp=await evaluate("document.getElementById('context-help').textContent");
    if(name.startsWith('child-'))assert.match(catalogHelp,/Session Models:[\s\S]*Sub Agents:/);
    await evaluate(`location.hash=${JSON.stringify('#/sessions/details-'+name)}`);
    await until('current.detail?.data?.result?.view?.prompt_blocks?.[0]?.rows?.length>0 && !current.detail.busy');
    await until(`current.detail.data.result.view.prompt_blocks[0].rows.find(r=>r.event_id===${JSON.stringify(event)})?.has_model_details===${promptStar}`);
    const detail=await evaluate(`(()=>{
      const values=current.detail.data.result.view.prompt_blocks[0].rows;
      return values.map(value=>({event:value.event_id,model:value.watch_model,star:value.has_model_details,
        text:[...current.detail.body.rows].find(row=>row.dataset.id===value.id).cells[1].textContent}));
    })()`);
    for(const row of detail) assert.equal(row.text,row.model+(row.star?'*':''),JSON.stringify({name,row}));
    assert.equal(detail.find(row=>row.event===event).star,promptStar);
    if(detail.some(row=>row.event==='u_next'))assert.equal(detail.find(row=>row.event==='u_next').star,false);
    await evaluate(`window.modelTarget=current.detail.body.rows[0].cells[1].firstChild;modelTarget.focus()`);
    const help=await evaluate("document.getElementById('context-help').textContent");
    if(name.startsWith('child-') || name.startsWith('native-'))assert.match(help,/Session Models:[\s\S]*Sub Agents:/);
    if(['main-efforts','child-effort','native-effort'].includes(name)) {
      assert.match(help,/high/i);assert.match(help,/max/i);
    }
    if(name==='main-efforts')assert.doesNotMatch(help,/Sub Agents/);
  }
  checks.push('eleven canonical cross-view scenarios, including native V2 adapter-normalized Sol High+High and Sol High+Max linked children; no-child model/effort switches, separate prompts, running child and unknown main; exactly one star; no prompt leakage');
  // A live same-source correction retains the focused keyed node and refreshes help.
  await evaluate("location.hash='#/sessions/details-child-same'");
  await until('current.detail?.id==="details-child-same" && current.detail.data');
  await until('current.detail.data.result.view.prompt_blocks[0].rows[0].linked_agent_count===1');
  await evaluate('window.modelTarget=current.detail.body.rows[0].cells[1].firstChild;modelTarget.focus()');
  await fixture('model-details-child-effort');
  await until('/max/i.test(document.getElementById("context-help").textContent)');
  assert.equal(await evaluate('document.activeElement===modelTarget && modelTarget.isConnected'),true);
  checks.push('same-source live child-effort revision updates open tooltip without replacing focused Model node');
  for(const view of ['detail','catalog']) {
    await evaluate(`location.hash=${JSON.stringify(view==='detail'?'#/sessions/details-child-same':'#/sessions?period=all&sort=model&direction=1')}`);
    await until(view==='detail'?'current.detail?.data && !current.detail.busy':
      'current.catalog?.data?.view?.session_usage?.length===11 && !current.catalog.busy');
    await evaluate(view==='detail'?
      'window.modelTarget=current.detail.body.rows[0].cells[1].firstChild':
      'window.modelTarget=[...current.catalog.body.rows].find(row=>row.value.session_id==="details-child-same").cells[2].firstChild');
    for(const theme of ['classic','web'])for(const scheme of ['light','dark'])for(const width of [360,1366])for(const factor of [1,2]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]});
    await evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme)}`);
    await zoom(factor);
    await command('Input.dispatchMouseEvent',{type:'mousePressed',x:0,y:0,button:'left',clickCount:1});
    await command('Input.dispatchMouseEvent',{type:'mouseReleased',x:0,y:0,button:'left',clickCount:1});
    await evaluate(`(()=>{modelTarget.scrollIntoView({block:"center",inline:"center"});
      const before=modelTarget.closest('tr').cells[${view==='detail'?0:1}].querySelectorAll('[tabindex="0"],a');
      before[before.length-1].focus();})()`);
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
    assert.equal(await evaluate('document.activeElement===modelTarget'),true,'trusted Tab reaches Model');
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9,modifiers:8});
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9,modifiers:8});
    assert.equal(await evaluate('document.activeElement===modelTarget'),false,'trusted Shift-Tab leaves Model');
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
    assert.equal(await evaluate('document.activeElement===modelTarget'),true);
    await until('document.getElementById("context-help").matches(":popover-open")');
    const geometry=await evaluate(`(()=>{
      const help=document.getElementById('context-help'),r=help.getBoundingClientRect();
      return {width:innerWidth,page:document.documentElement.scrollWidth,text:modelTarget.textContent,
        help:help.textContent,left:r.left,right:r.right,focused:document.activeElement===modelTarget};
    })()`);
    assert.ok(geometry.page<=geometry.width+1,JSON.stringify(geometry));
    assert.equal(geometry.focused,true);
    assert.equal((geometry.text.match(/\*/g)||[]).length,1);
    assert.ok(geometry.left>=-1 && geometry.right<=geometry.width+1);
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await evaluate('document.activeElement.blur()');
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0});
    await evaluate('modelTarget.scrollIntoView({block:"center",inline:"center"});new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
    const point=await evaluate('(()=>{const r=modelTarget.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()');
    assert.equal(await evaluate(`document.elementFromPoint(${point.x},${point.y})===modelTarget`),true,
      JSON.stringify({view,theme,scheme,width,factor,point}));
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point});
    await until('document.getElementById("context-help").matches(":popover-open")');
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0});
    await until('document.getElementById("context-help").hidden');
    await command('Input.dispatchMouseEvent',{type:'mousePressed',x:0,y:0,button:'left',clickCount:1});
    await command('Input.dispatchMouseEvent',{type:'mouseReleased',x:0,y:0,button:'left',clickCount:1});
    await command('Emulation.setTouchEmulationEnabled',{enabled:true});
    await evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
    const touchPoint=await evaluate('(()=>{const r=modelTarget.getBoundingClientRect();const x=r.x+r.width/2,y=r.y+r.height/2;return {x,y,hit:document.elementFromPoint(x,y)===modelTarget,coarse:matchMedia("(pointer: coarse)").matches}})()');
    assert.equal(touchPoint.hit,true);
    await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:touchPoint.x,y:touchPoint.y}]});
    await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    await until('document.getElementById("context-help").matches(":popover-open")');
    await command('Emulation.setTouchEmulationEnabled',{enabled:false});
    layouts.push({view,theme,scheme,physicalWidth:width,zoom:factor,...geometry,mousePoint:point,touchPoint});
    }
  }
  await zoom(1);
  checks.push('catalog/detail × Classic/Web × light/dark × 360/1366px × actual browser 100/200% zoom: trusted Tab/Shift-Tab, mouse hover and touch help; focus preserved, one star, no page overflow, bounded tooltip');
  return {checks,layouts};
};
