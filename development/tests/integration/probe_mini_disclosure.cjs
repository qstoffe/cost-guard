// Actual hidden PiP user activation and outer/inner bounds; no OS desktop input.
const assert = require('node:assert/strict');
module.exports = async function disclosure({evaluate,until,fixture,command,pipSession,layouts,checks,capture}) {
  const read = () => evaluate(`(() => {const w=miniWatch.window,v=miniWatch.view;return {
    outer:[w.outerWidth,w.outerHeight],inner:[w.innerWidth,w.innerHeight],
    session:[v.prompts.clientHeight,v.prompts.scrollHeight],accounts:[v.accounts.clientHeight,v.accounts.scrollHeight],
    expanded:!v.earlier.hidden,pressed:v.earlierToggle.getAttribute('aria-pressed'),attempts:w.probeResizeCalls.length,
    restore:v.disclosureSize.restore,pending:!!v.disclosureSize.pending,
    layout:v.disclosureLayout(),root:v.root.getBoundingClientRect().height,earlier:v.earlier.getBoundingClientRect().height,
    zoom:w.document.body.currentCSSZoom||1,dpr:w.devicePixelRatio,
    calls:w.probeResizeCalls,scrollY:w.scrollY,focus:w.document.activeElement?.className,
    document:[w.document.documentElement.clientHeight,w.document.documentElement.scrollHeight],
    clones:w.document.querySelectorAll('.mini-measuring').length};})()`);
  const click = async () => {
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},pipSession);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},pipSession);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},pipSession);
    await evaluate(`miniWatch.view.earlierToggle.scrollIntoView({block:'nearest',inline:'nearest'})`);
    const point=await evaluate(`(() => {const r=miniWatch.view.earlierToggle.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
    for (const type of ['mousePressed','mouseReleased'])
      await command('Input.dispatchMouseEvent',{type,button:'left',clickCount:1,...point},pipSession);
    await until(`!miniWatch.view.disclosureSize.pending`);
  };
  const keyboard = async () => {
    await command('Runtime.evaluate',{expression:`document.querySelector('.mini-earlier-toggle').focus()`},pipSession);
    for (const type of ['keyDown','keyUp']) await command('Input.dispatchKeyEvent',{
      type,key:'Enter',code:'Enter',windowsVirtualKeyCode:13,...(type==='keyDown'?{text:'\r'}:{})},pipSession);
    await until(`!miniWatch.view.disclosureSize.pending`);
  };
  await command('Page.bringToFront',{},pipSession);
  await evaluate(`(() => {const w=miniWatch.window;w.probeResizeCalls=[];w.probeNativeResize=w.resizeTo.bind(w);w.probeNativeResizeBy=w.resizeBy.bind(w);
    w.resizeTo=(...args)=>{w.probeResizeCalls.push(args);return w.probeNativeResize(...args);};
    w.resizeBy=(...args)=>{w.probeResizeCalls.push(args);return w.probeNativeResizeBy(...args);};})()`);
  const size = async (width,height) => {
    await evaluate(`miniWatch.window.resizeTo(${width},${height})`,true);
    await evaluate(`new Promise(resolve=>miniWatch.window.requestAnimationFrame(()=>miniWatch.window.requestAnimationFrame(resolve)))`);
    await evaluate(`miniWatch.window.probeResizeCalls=[]`);
  };
  const roundTrip=async(label,activate=click)=>{
    const before=await read();assert.equal(before.expanded,false);
    const delta=(before.layout.expanded-before.layout.collapsed)*before.layout.scale;
    await activate();const after=await read();assert.equal(after.pressed,'true',JSON.stringify({label,before,after}));
    assert.equal(after.attempts-before.attempts,1);assert.equal(after.calls.at(-1)[0],0);
    if(after.outer[0]===before.outer[0] && after.outer[1]<Math.min(1000,await evaluate('miniWatch.window.screen.availHeight')))
      assert.ok(Math.abs(after.outer[1]-before.outer[1]-delta)<=2,JSON.stringify({before,after,delta}));
    else after.nativeClamp=true;
    await activate();const collapsed=await read();assert.equal(collapsed.pressed,'false');
    if(!after.nativeClamp && after.layout.width===before.layout.width)
      assert.equal(collapsed.outer[1],before.outer[1],JSON.stringify({before,after,collapsed}));
    assert.ok(collapsed.attempts-after.attempts<=1);assert.equal(collapsed.clones,0);
    layouts.push({case:label,before,after,collapsed,delta});return collapsed;
  };
  for(const mode of ['fit-on-open','remember-last']) {
    await evaluate(`miniWatch.window.document.documentElement.dataset.miniSize='${mode}'`);
    for(const rows of [0,1,3]) for(const running of [0,1,4]) {
      await fixture(`history-${rows}-${running}-1`);await until(`miniWatch.view.historyRows.size===${rows} && miniWatch.view.promptRows.size===${running}`);
      for(const baseline of [220,400,650]) {await size(560,baseline);await roundTrip(`delta-${mode}-${rows}-${running}-${baseline}`,rows===1?keyboard:click);}
    }
    await fixture('history-3-1-1');await until('miniWatch.view.historyRows.size===3 && miniWatch.view.promptRows.size===1');
    await size(560,650);await evaluate('miniWatch.view.fitButton.click()',true);await until('!miniWatch.view.disclosureSize.pending');
    for(let cycle=0;cycle<4;cycle++)await roundTrip(`fit-before-delta-${mode}-${cycle}`);
    const fitted=await read();await evaluate('miniWatch.view.fitButton.click()',true);await until('!miniWatch.view.disclosureSize.pending');
    assert.deepEqual((await read()).outer,fitted.outer,'Fit after collapse must not shrink again');
  }
  for(const theme of ['classic','web'])for(const color of ['light','dark'])for(const zoom of [1,1.25,1.5,2]) {
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:color}]},pipSession);
    await evaluate(`miniWatch.window.document.documentElement.dataset.theme='${theme}';miniWatch.window.document.body.style.zoom='${zoom}'`);
    for(const font of ['system-ui','serif']) {
      await evaluate(`miniWatch.window.document.body.style.fontFamily='${font}'`);await size(560,300);
      await roundTrip(`delta-appearance-${theme}-${color}-${zoom}-${font}`);
    }
    await click();
    layouts.push({case:'pressed-fill',theme,color,zoom,states:[]});const filled=layouts.at(-1);
    for(const state of ['expanded','hover','focus']) {
      if(state==='hover') {
        const point=await evaluate(`(()=>{const r=miniWatch.view.earlierToggle.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
        await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},pipSession);
      }
      if(state==='focus')await evaluate('miniWatch.view.earlierToggle.focus()');
      const style=await evaluate(`(()=>{const w=miniWatch.window,b=miniWatch.view.earlierToggle,s=w.getComputedStyle(b);return {shadow:s.boxShadow,fill:s.backgroundColor,ink:s.color,pressed:b.getAttribute('aria-pressed')};})()`);
      assert.equal(style.shadow,'none');assert.notEqual(style.fill,style.ink);assert.equal(style.pressed,'true');
      filled.states.push({state,...style});
      if(capture)await capture(`fill-${theme}-${color}-${zoom}-${state}`,await evaluate(`(()=>{const r=miniWatch.view.earlierToggle.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,scale:1};})()`));
    }
    await click();
  }
  await command('Emulation.setEmulatedMedia',{features:[{name:'forced-colors',value:'active'}]},pipSession);await click();
  assert.equal(await evaluate(`miniWatch.window.getComputedStyle(miniWatch.view.earlierToggle).outlineStyle`),'solid');await click();
  await command('Emulation.setEmulatedMedia',{features:[]},pipSession);
  await evaluate(`miniWatch.window.document.body.style.zoom='';miniWatch.window.document.body.style.fontFamily=''`);
  for(const command of ['empty','watch-delay-0']) {
    await fixture(command);await until('miniWatch.publication.view.now_ms===liveValue.view.now_ms');await size(560,300);await roundTrip(`delta-${command}`);
  }
  await size(280,300);await roundTrip('delta-narrow-wrapping');
  await size(560,300);await click();await fixture('history-1-4-3');await until('miniWatch.view.historyRows.size===1 && miniWatch.view.promptRows.size===4');
  const changed=await read();await click();const reconciled=await read();
  assert.ok(Math.abs(changed.outer[1]-reconciled.outer[1]-(changed.layout.expanded-changed.layout.collapsed)*changed.layout.scale)<=2);
  layouts.push({case:'delta-changed-content',changed,reconciled});
  await click();await size(600,460);const manual=await read();await click();
  assert.ok(Math.abs(manual.outer[1]-(await read()).outer[1]-(manual.layout.expanded-manual.layout.collapsed)*manual.layout.scale)<=2);
  await fixture('history-3-1-1');await until('miniWatch.view.historyRows.size===3 && miniWatch.view.promptRows.size===1');await size(560,300);
  await until(`!miniWatch.window.navigator.userActivation.isActive && !navigator.userActivation.isActive`);
  const noActivationBefore=await read();
  await evaluate(`miniWatch.view.earlierToggle.click()`);
  await until(`!miniWatch.view.disclosureSize.pending`);
  const noActivation=await read(); assert.deepEqual(noActivation.restore.before,noActivation.restore.after);
  assert.deepEqual(noActivation.outer,noActivationBefore.outer); assert.equal(noActivation.expanded,true);
  await evaluate(`miniWatch.view.earlierToggle.click();miniWatch.window.probeResizeCalls=[]`);
  await size(560,220);
  await evaluate(`miniWatch.window.resizeBy=(...args)=>{miniWatch.window.probeResizeCalls.push(args);return miniWatch.window.probeNativeResizeBy(args[0],Math.min(args[1],10));}`);
  const shortBefore=await read(); await click(); const short=await read();
  assert.equal(short.attempts,1); assert.ok(short.restore); assert.ok(short.document[1]>short.document[0]);
  await click(); (await read()).outer.forEach((n,i)=>assert.ok(Math.abs(n-shortBefore.outer[i])<=1));
  await evaluate(`miniWatch.window.probeResizeCalls=[]`);
  await evaluate(`miniWatch.window.resizeBy=undefined;miniWatch.window.resizeTo=(...args)=>{miniWatch.window.probeResizeCalls.push(args);throw new Error('blocked resize');}`);
  await click(); const refused=await read(); assert.deepEqual(refused.restore.before,refused.restore.after); assert.equal(refused.expanded,true);
  await click(); assert.equal((await read()).attempts,1);
  await evaluate(`miniWatch.window.resizeTo=undefined`); await click(); assert.equal((await read()).restore.layout,null); await click();
  await evaluate(`miniWatch.window.resizeTo=(...args)=>miniWatch.window.probeResizeCalls.push(args)`);
  await click(); const clamped=await read(); assert.deepEqual(clamped.restore.before,clamped.restore.after); await click();
  await evaluate(`miniWatch.window.resizeTo=(...args)=>{miniWatch.window.probeResizeCalls.push(args);return miniWatch.window.probeNativeResize(...args);}`);
  await evaluate(`miniWatch.window.resizeBy=(...args)=>{miniWatch.window.probeResizeCalls.push(args);return miniWatch.window.probeNativeResizeBy(...args);}`);
  layouts.push({case:'disclosure-no-activation-short-refused-clamped',noActivation,short,refused,clamped});
  await size(560,300); await fixture('running'); await until(`miniWatch.view.promptRows.size===2`);
  checks.push('Relative rendered Earlier delta, both modes and fitted/tall/short baselines; repeated no-drift cycles, 0/1/3 history x 0/1/4 running, themes/fonts/zoom, narrow wrapping, changed content/manual bounds, activation/refusal/clamps and one height-only call');
};

// Same owned browser/fixture and resize owner; no second orchestration or stream.
module.exports.fit = async function fit({evaluate,until,fixture,command,sessionId,targetId,open,close,read,capture,layouts,checks}) {
  const settle=()=>evaluate('new Promise(resolve=>miniWatch.window.requestAnimationFrame(()=>miniWatch.window.requestAnimationFrame(resolve)))');
  const settings=(field,endpoint,value)=>evaluate(`(async()=>applySettings(await api('/api/settings/${endpoint}',{${field}:'${value}'})))()`);
  let pip;
  const density=async(rows,accounts)=>{await fixture(`density-${rows}-${accounts}`);await until(`miniWatch.view.promptRows.size===${rows} && miniWatch.view.lines.size===${accounts}`);};
  const instrument=()=>evaluate(`(()=>{const w=miniWatch.window;w.fitCalls=[];w.fitNativeBy=w.resizeBy;w.fitNativeTo=w.resizeTo;
    miniWatch.view.fitButton.addEventListener('click',()=>{w.fitHelpDismissed=!w.document.querySelector('.context-help:not([hidden])');});
    for(const name of ['resizeBy','resizeTo']){const native=w[name].bind(w);w[name]=(...args)=>{w.fitCalls.push({name,args,active:w.navigator.userActivation.isActive});return native(...args);};}})()`);
  const size=async(width,height)=>{await evaluate(`miniWatch.window.resizeTo(${width},${height})`,true);await settle();await evaluate('miniWatch.window.scrollTo(0,0);miniWatch.window.fitCalls=[]');};
  const snapshot=async()=>({...await read(),...await evaluate(`(()=>{const w=miniWatch.window,v=miniWatch.view,s=w.getComputedStyle(w.document.body),r=v.root.getBoundingClientRect();return {
    desiredManual:v.fitHeight(false),slack:w.innerHeight-r.height-(parseFloat(s.paddingTop)+parseFloat(s.paddingBottom))*(w.document.body.currentCSSZoom||1),
    calls:w.fitCalls,focus:w.document.activeElement===v.fitButton,scrollY:w.scrollY,help:w.document.querySelector('.context-help:not([hidden])')?.textContent||'',
    clones:w.document.querySelectorAll('.mini-measuring,.mini-header-measuring').length};})()`)});
  const activate=async(kind='pointer')=>{
    await evaluate('miniWatch.window.fitCalls=[];miniWatch.window.fitHelpDismissed=null');
    if(kind==='pointer'||kind==='touch') {
      const point=await evaluate(`(()=>{const r=miniWatch.view.fitButton.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
      if(kind==='touch') {
        await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]},pip);
        await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},pip);
      } else for(const type of ['mousePressed','mouseReleased'])await command('Input.dispatchMouseEvent',{type,button:'left',clickCount:1,...point},pip);
    } else {
      await evaluate('miniWatch.view.fitButton.focus()');
      for(const type of ['keyDown','keyUp'])await command('Input.dispatchKeyEvent',{type,key:kind,code:kind===' '?'Space':kind,windowsVirtualKeyCode:kind===' '?32:13,...(type==='keyDown'?{text:kind===' '?' ':'\r'}:{})},pip);
    }
    assert.equal(await evaluate('miniWatch.window.fitHelpDismissed'),true,'help closes synchronously in the activation');
    await settle();const result=await snapshot();assert.equal(result.help,'');return result;
  };
  const assertFit=(before,after)=>{
    assert.ok(after.calls.length<=1,JSON.stringify(after));assert.equal(after.expanded,before.expanded);
    for(const call of after.calls){assert.equal(call.active,true);assert.equal(call.args[0],call.name==='resizeBy'?0:before.outer[0]);}
    assert.equal(after.clones,0);assert.equal(after.header.documentOverflow,false);
    if(Math.abs(after.outer[0]-before.outer[0])>1)after.nativeWidthClamp={before:before.outer,after:after.outer};
    else {
      assert.ok(Math.abs(after.position[0]-before.position[0])<=1,JSON.stringify({before,after}));
      if(!after.scroll.length)assert.ok(after.slack>=-1,JSON.stringify(after));
      else {
        assert.ok(after.scroll.some(n=>n.tag==='HTML'),JSON.stringify(after));
        assert.ok(after.outer[1]<after.desiredManual-1 || after.desiredManual>=Math.min(1000,after.screen[1]),JSON.stringify(after));
        after.nativeHeightClamp=true;
      }
    }
  };
  for(const mode of ['fit-on-open','remember-last']) {
    await settings('miniWatchSize','mini-size',mode);await open();
    for(const target of (await command('Target.getTargets')).targetInfos.filter(t=>t.targetId!==targetId&&t.type==='page')) {
      const attached=await command('Target.attachToTarget',{targetId:target.targetId,flatten:true});
      if(await evaluate('!!document.querySelector(".mini-watch")',false,attached.sessionId)){pip=attached.sessionId;break;}
    }
    assert.ok(pip);await command('Page.bringToFront',{},pip);await instrument();
    for(const rows of [0,1,2,4,20])for(const accounts of [0,1,3]) {
      await density(rows,accounts);await size(600,220);
      const before=await snapshot(),grown=await activate();assertFit(before,grown);
      assert.ok(grown.calls.length===1 || Math.abs(before.outer[1]-before.desiredManual)<=1);
      const again=await activate('Enter');assertFit(grown,again);
      if(!grown.nativeWidthClamp && !again.nativeWidthClamp && !grown.nativeHeightClamp)assert.equal(again.calls.length,0,JSON.stringify({before,grown,again}));
      await size(600,850);const tall=await snapshot(),shrunk=await activate(' ');assertFit(tall,shrunk);
      if(tall.slack>=8 && tall.desiredManual<tall.outer[1]-1)assert.ok(shrunk.outer[1]<tall.outer[1],JSON.stringify(shrunk));
      if(!shrunk.nativeHeightClamp && !shrunk.nativeWidthClamp)assert.ok(shrunk.slack<8,JSON.stringify(shrunk));
      if(rows<2 && !shrunk.nativeHeightClamp && !shrunk.nativeWidthClamp)assert.ok(shrunk.slack<8,'no artificial two-row blank reserve');
      layouts.push({case:'manual-fit-density',mode,rows,accounts,before,grown,again,tall,shrunk});
    }
    await evaluate('miniWatch.view.summary.focus();miniWatch.window.fitCalls=[]');
    for(let index=0;index<2;index++)for(const type of ['keyDown','keyUp'])await command('Input.dispatchKeyEvent',{type,key:'Tab',code:'Tab',windowsVirtualKeyCode:9},pip);
    assert.equal((await snapshot()).focus,true,'Tab reaches the named icon button');
    assert.match((await snapshot()).help,/Fit Mini Watch height/);
    await evaluate('miniWatch.view.fitButton.blur();ContextHelp.dismiss(miniWatch.view.fitButton)');
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},pip);
    const hoverBefore=await snapshot(),point=await evaluate(`(()=>{const r=miniWatch.view.fitButton.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},pip);
    await until(`miniWatch.window.document.querySelector('.context-help:not([hidden])')?.textContent.startsWith('Fit Mini Watch height')`);
    const hovered=await snapshot();assert.equal(hovered.desiredManual,hoverBefore.desiredManual);assert.equal(hovered.calls.length,0);
    layouts.push({case:'manual-fit-help',mode,...hovered});
    await activate();await evaluate('new Promise(resolve=>miniWatch.window.setTimeout(resolve,700))');
    assert.equal((await snapshot()).help,'','stationary pointer/focus must not reopen action help');
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},pip);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},pip);
    await until(`miniWatch.window.document.querySelector('.context-help:not([hidden])')?.textContent.startsWith('Fit Mini Watch height')`);
    await activate('Enter');
    await fixture('history-3-1-3');await until('miniWatch.view.historyRows.size===3 && miniWatch.view.promptRows.size===1');
    await evaluate('miniWatch.view.earlierToggle.click()',true);await settle();await size(600,220);
    const expanded=await snapshot(),fitted=await activate('touch');assertFit(expanded,fitted);assert.equal(fitted.expanded,true);
    assert.equal(fitted.help,'','touch activation dismisses action help');
    await size(600,850);const repeated=await evaluate(`(()=>{miniWatch.view.fitButton.click();miniWatch.view.fitButton.click();return miniWatch.window.fitCalls.length;})()`,true);
    assert.ok(repeated<=1,'rapid synchronous clicks share pending resize ownership');await settle();
    const passive=await snapshot();await density(4,1);await density(1,0);assert.deepEqual((await snapshot()).outer,passive.outer);
    assert.equal((await snapshot()).calls.length,passive.calls.length,'SSE publications do not fit');
    for(const theme of ['classic','web'])for(const color of ['light','dark'])for(const font of ['system-ui','serif'])for(const zoom of [1,1.25,1.5,2]) {
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:color}]},sessionId);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:color}]},pip);
      await settings('theme','theme',theme);await evaluate(`miniWatch.window.document.body.style.fontFamily='${font}';miniWatch.window.document.body.style.zoom='${zoom}'`);
      await size(600,220);const before=await snapshot(),after=await activate();assertFit(before,after);
      layouts.push({case:'manual-fit-appearance',mode,theme,color,font,zoom,...after});
      if(font==='system-ui'&&zoom===1)await capture(`manual-${mode}-${theme}-${color}`);
    }
    await evaluate(`miniWatch.window.document.body.style.zoom='';miniWatch.window.document.body.style.fontFamily=''`);
    await size(280,220);const narrowBefore=await snapshot(),narrow=await activate();assertFit(narrowBefore,narrow);
    assert.equal(await evaluate('miniWatch.view.prompts.scrollWidth>miniWatch.view.prompts.clientWidth'),true);
    await density(40,6);await size(600,220);const capBefore=await snapshot(),capped=await activate();assertFit(capBefore,capped);
    assert.ok(capped.outer[1]<=Math.min(1000,capped.screen[1])+1);assert.ok(capped.scroll.some(n=>n.tag==='HTML'));
    await evaluate('miniWatch.window.scrollTo(0,miniWatch.window.document.documentElement.scrollHeight)');assert.ok(await evaluate('miniWatch.window.scrollY>0'));
    await size(600,220);await until('!miniWatch.window.navigator.userActivation.isActive && !navigator.userActivation.isActive');
    await evaluate('miniWatch.view.fitButton.click()');await settle();assert.equal((await snapshot()).calls.length,0);
    await evaluate(`(()=>{const w=miniWatch.window;w.resizeBy=undefined;w.resizeTo=(...args)=>{w.fitCalls.push({name:'resizeTo',args,active:w.navigator.userActivation.isActive});return w.fitNativeTo.apply(w,args);};})()`);
    const fallbackBefore=await snapshot(),fallback=await activate();assertFit(fallbackBefore,fallback);assert.equal(fallback.calls[0].name,'resizeTo');
    await evaluate(`miniWatch.window.fitNativeTo.call(miniWatch.window,600,220)`,true);await settle();
    await evaluate(`miniWatch.window.resizeTo=(...args)=>{miniWatch.window.fitCalls.push(args);throw new Error('NotAllowedError');}`);
    const refused=await activate();assert.equal(refused.calls.length,1);assert.ok(refused.scroll.some(n=>n.tag==='HTML'));
    await evaluate('miniWatch.window.resizeTo=undefined');const unsupported=await activate();assert.equal(unsupported.calls.length,0);
    assert.equal(await evaluate('!!miniWatch.view.disclosureSize.pending'),false);
    layouts.push({case:'manual-fit-bounds-refusal',mode,narrow,capped,fallback,refused,unsupported});await close();
  }
  await settings('miniWatchSize','mini-size','default');await settings('theme','theme','default');
  checks.push('Manual height-only native fit: both size modes; 0/1/2/4/20 prompt x 0/1/3 account rows; grow/shrink/idempotence, no two-row reserve, expanded history, pointer/Enter/Space/touch, rapid clicks, 4 CSS zooms x 2 fonts x 4 theme appearances, narrow panning, capped scroll, inactive/refused/unsupported/fallback and passive SSE');
};
