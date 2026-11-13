// Shared control contract across real opener and native Document PiP documents.
const assert = require('node:assert/strict');
module.exports = async function controlFocus({command,evaluate,until,owner,mini,checks,layouts}) {
  const transitions=[];
  const key = async (id,key,code,windowsVirtualKeyCode) => {
    for(const type of ['keyDown','keyUp']) await command('Input.dispatchKeyEvent',{type,key,code,windowsVirtualKeyCode,
      ...(type==='keyDown'&&['Enter',' '].includes(key)?{text:key==='Enter'?'\r':' '}:{})},id);
  };
  const sample = (id,selector) => evaluate(id,`(()=>{const n=document.querySelector(${JSON.stringify(selector)}),s=getComputedStyle(n);return {
    focus:n.matches(':focus'),visible:n.matches(':focus-visible'),active:n.matches(':active'),outline:s.outlineStyle,
    width:s.outlineWidth,shadow:s.boxShadow,border:s.borderColor,current:n.getAttribute('aria-current'),
    pressed:n.getAttribute('aria-pressed'),documentFocus:document.hasFocus(),pointer:n.hasAttribute('data-pointer-focus')};})()`);
  const tabTo = async (id,selector) => {
    await command('Page.bringToFront',{},id);
    // Position before the target, then the browser's real Tab traversal owns entry.
    await evaluate(id,`(()=>{const target=document.querySelector(${JSON.stringify(selector)});
      const nodes=[...document.querySelectorAll('button,a[href],input,select,summary,[tabindex="0"]')]
        .filter(n=>!n.disabled&&n.getClientRects().length&&!n.closest('[hidden],[inert]'));
      const index=nodes.indexOf(target);
      if(index>0)nodes[index-1].focus();else {document.body.tabIndex=-1;document.body.focus();document.body.removeAttribute('tabindex');}})()`);
    await key(id,'Tab','Tab',9);
    assert.equal((await sample(id,selector)).focus,true,'native Tab reaches '+selector);
  };
  const pointer = async (id,selector,touch=false) => {
    const point=await evaluate(id,`(()=>{const n=document.querySelector(${JSON.stringify(selector)});n.scrollIntoView({block:'center'});
      const r=n.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
    if(touch) {
      await command('Emulation.setTouchEmulationEnabled',{enabled:true},id);
      await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]},id);
      await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},id);
      await until(id,`!document.querySelector(${JSON.stringify(selector)}).matches(':active')`);
      await command('Emulation.setTouchEmulationEnabled',{enabled:false},id);
    } else {
      await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},id);
      await command('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...point},id);
      layouts.push({phase:'pressed',selector,...await sample(id,selector)});
      await command('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...point},id);
    }
  };
  // Observe the untouched native return, not merely callback execution. In
  // particular no bringToFront/focus emulation may establish the asserted result.
  for(const input of ['mouse','Enter',' ']) {
    await evaluate(owner,`location.hash='#/models';window.focusProbePip=miniWatch.window;
      window.focusProbeEvents=[];if(!window.focusProbeListening){focusProbeListening=true;
      for(const type of ['focus','blur'])window.addEventListener(type,()=>focusProbeEvents.push(type));}`);
    await until(owner,`current.section==='models'`);
    await evaluate(mini,`window.focusProbeEvents=[];if(!window.focusProbeListening){focusProbeListening=true;
      for(const type of ['focus','blur'])window.addEventListener(type,()=>focusProbeEvents.push(type));}`);
    await command('Page.bringToFront',{},mini);
    if(input!=='mouse')await tabTo(mini,'.mini-summary');
    const before={owner:await evaluate(owner,'document.hasFocus()'),mini:await evaluate(mini,'document.hasFocus()')};
    assert.equal(before.mini,true,'PiP actually focused before native return');
    if(input==='mouse')await pointer(mini,'.mini-summary');
    else await key(mini,input,input==='Enter'?'Enter':'Space',input==='Enter'?13:32);
    await until(owner,`current.section==='watch'`);
    const after={owner:await evaluate(owner,'document.hasFocus()'),mini:await evaluate(mini,'document.hasFocus()'),
      ownerEvents:await evaluate(owner,'focusProbeEvents'),miniEvents:await evaluate(mini,'focusProbeEvents'),
      sameWindow:await evaluate(owner,'miniWatch.window===focusProbePip&&!miniWatch.window.closed'),
      style:await sample(mini,'.mini-summary')};
    assert.equal(after.sameWindow,true);
    assert.equal(after.style.active,false);
    assert.equal(after.style.outline,input==='mouse'?'none':'solid');
    await command('Page.bringToFront',{},mini); // Now deliberately revisit, before Tab.
    const revisit=await sample(mini,'.mini-summary');
    assert.equal(revisit.outline,input==='mouse'?'none':'solid');
    assert.equal(revisit.active,false);
    transitions.push({input,before,after,revisit,focusTransferVerified:after.owner&&!after.mini});
  }
  const exercise = async (id,selector) => {
    await command('Page.bringToFront',{},id);
    await tabTo(id,selector);
    const keyboard=await sample(id,selector);
    assert.equal(keyboard.outline,'solid','visible keyboard cue '+selector);
    await pointer(id,selector);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:1,y:1},id);
    const mouse=await sample(id,selector);
    assert.equal(mouse.outline,'none','same-element pointer must clear extra halo '+selector);
    assert.equal(mouse.active,false);
    await tabTo(id,selector);
    assert.equal((await sample(id,selector)).outline,'solid','Tab restores keyboard cue '+selector);
    await pointer(id,selector,true);
    const touch=await sample(id,selector);
    assert.equal(touch.outline,'none','touch must clear extra halo '+selector);
    layouts.push({selector,document:id===mini?'PiP':'Web',keyboard,mouse,touch});
  };
  // PiP input is targeted to its actual document/target, never the opener.
  await exercise(mini,'.mini-summary');
  assert.equal(await evaluate(owner,`current.section==='watch'&&!miniWatch.window.closed`),true);
  for(const activation of [['Enter','Enter',13],[' ','Space',32]]) {
    await command('Page.bringToFront',{},mini);await tabTo(mini,'.mini-summary');
    await key(mini,...activation);
    const value=await sample(mini,'.mini-summary');
    assert.equal(value.outline,'solid','keyboard cue survives return-to-owner');
    assert.equal(value.active,false);
    layouts.push({selector:'.mini-summary',phase:'keyboard-return',...value});
  }
  await exercise(mini,'.mini-fit-height');
  await exercise(mini,'.mini-prompt-table th:first-child button');
  // Every primary navigation entry, both same-route and selected/unselected.
  for(const route of ['watch','models','sessions','accounts','token-mix','ai-stats','comparisons','settings']) {
    const selector=`nav a[href="#/${route}"]`;
    await exercise(owner,selector);
    await until(owner,`current.section===${JSON.stringify(route)}`);
    assert.equal((await sample(owner,selector)).current,'page','active-page selection preserved');
    await tabTo(owner,selector);await key(owner,'Enter','Enter',13);
    assert.equal((await sample(owner,selector)).outline,'solid','keyboard ring plus active page');
  }
  await evaluate(owner,`location.hash='#/models'`);
  await until(owner,`!!document.querySelector('.overview-model-table')`);
  await exercise(owner,'[data-model-control="column-1"]');
  await exercise(owner,'[data-model-control="all"]');
  await evaluate(owner,`location.hash='#/ai-stats'`);
  await until(owner,`!!document.querySelector('.ai-stats-periods button')`);
  await exercise(owner,'.ai-stats-periods button:nth-child(2)');
  await evaluate(owner,`location.hash='#/watch'`);
  await until(owner,`!!document.querySelector('.watch-active th button')`);
  await exercise(owner,'.watch-active th button');
  // Controlled catalog/detail replies, as in the existing quiet-refresh probe.
  // The actual views/actions/input run; no private history or native save is used.
  await evaluate(owner,`window.focusApi=api;sessionDetailAvailable=true;
    window.showSaveFilePicker=async()=>{throw new DOMException('Synthetic cancellation','AbortError');};
    api=async(path,value,...rest)=>{
      if(path==='/api/sessions') {
        if(value.action==='interest')return {};
        return {token:'focus-token',epoch:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',state:'observed',total:151,size:50,
          offset:value.offset,sort:value.sort,direction:value.direction,age_ms:0,
          view:{session_usage:Array.from({length:Math.min(50,151-value.offset)},(_,i)=>({
            session_id:'focus-'+(value.offset+i),title:'Synthetic focus session',last_activity_ms:1000,
            indexed:true,has_summary:true,metric_state:'ready',prompt_count:1,model:'Test',display:{ccost:'1',duration_ms:'1s'}}))}};
      }
      if(path==='/api/detail') {
        if(value.action==='open')return {token:'focus-detail'};if(value.action==='close')return {};
        return {state:'observed',export_available:true,revision:'focus-revision',age_ms:0,total:1,offset:0,
          result:{view:{prompt_blocks:[{title:'Synthetic focus detail',rows:[{
            ...liveValue.view.active_cards[0].rows[0].prompt,id:'focus-prompt',watch_model:'Test'}],totals:{display:{}},session_context:null}]}}};
      }
      return focusApi(path,value,...rest);
    };location.hash='#/sessions';`);
  await until(owner,`current.catalog?.body.children.length===50`);
  await exercise(owner,'.sessions-table th button');
  // Locate using the live view's own action, without guessing its CSS class.
  await evaluate(owner,`current.catalog.next.id='focus-next'`);
  await exercise(owner,'#focus-next');
  await evaluate(owner,`location.hash='#/sessions/focus-0'`);
  await until(owner,`current.detail?.data?.revision==='focus-revision'`);
  await exercise(owner,'.session-export button');
  await exercise(owner,'.session-history-table th button');
  layouts.push({phase:'sessions-detail',source:'synthetic catalog/detail API',export:'synthetic picker cancellation; no file saved'});
  await evaluate(owner,`location.hash='#/settings'`);
  await until(owner,`!!document.querySelector('.web-settings')`);
  await exercise(owner,'.web-settings label.help-value');
  const settings=await evaluate(owner,`[...document.querySelectorAll('#result button')].filter(n=>!n.disabled).map(n=>n.outerHTML.slice(0,150))`);
  layouts.push({phase:'settings-control-inventory',controls:settings});
  // Palette/zoom/forced-colors are shared CSS, not a screenshot-only assertion.
  for(const width of [360,1280]) for(const theme of ['classic','web']) for(const zoom of [1,1.5]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},owner);
    await evaluate(owner,`document.documentElement.dataset.theme='${theme}';document.documentElement.style.zoom=${zoom}`);
    await exercise(owner,'nav a[href="#/settings"]');
  }
  await command('Emulation.setEmulatedMedia',{features:[{name:'forced-colors',value:'active'},{name:'prefers-reduced-motion',value:'reduce'}]},owner);
  await tabTo(owner,'nav a[href="#/settings"]');
  assert.equal((await sample(owner,'nav a[href="#/settings"]')).outline,'solid');
  checks.push('native mouse/touch/Tab and Enter/Space: all eight nav entries, Models filter/sort, Watch/help, AI Stats period, Sessions sort/pager/detail/export cancellation, Settings help, actual PiP return/Fit/header; selected state and keyboard rings preserved; 360/1280 Classic/Web 100/150%, forced colors/reduced motion');
  return {focusTransferVerified:transitions.every(value=>value.focusTransferVerified),transitions};
};
