// Trusted headless input over the authenticated startup fixture's shipped DOM.
const assert = require('node:assert/strict');

async function probeModelsFocus({command,evaluate,until,focusSnapshot}) {
  const key=async (key,code,windowsVirtualKeyCode,text)=>{
    await command('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode,...(text?{text}:{})});
    await command('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode});
  };
  const point=selector=>evaluate(`(()=>{const n=document.querySelector(${JSON.stringify(selector)});
    n.scrollIntoView({block:'center'});const r=n.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  const click=async selector=>{
    const position=await point(selector);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...position});
    await command('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...position});
    await command('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...position});
  };
  const quiet=async phase=>{
    const focus=await focusSnapshot(phase);
    assert.equal(focus.active,'content');assert.equal(focus.outline.style,'none');
    assert.equal(focus.shadow,'none');assert.equal(focus.progress.length,0);assert.equal(focus.scroll,0);
  };
  await click('nav a[href="#/watch"]');await until(`current.section==='watch'`);
  await click('nav a[href="#/models"]');await until(`current.section==='models' && !current.loading`);
  await quiet('mouse-return');

  // Same-route presentation changes neither refocus nor reset the document anchor.
  await evaluate(`window.scrollTo(0,150);window.__focusScroll=scrollY;
    document.querySelector('[data-model-control="all"]').focus({preventScroll:true});
    document.querySelector('[data-model-control="all"]').click();true`);
  assert.equal(await evaluate(`scrollY===__focusScroll && document.activeElement.dataset.modelControl==='all'`),true);
  await evaluate(`document.querySelector('[data-model-control="column-1"]').focus({preventScroll:true});
    document.querySelector('[data-model-control="column-1"]').click();true`);
  assert.equal(await evaluate(`scrollY===__focusScroll && document.activeElement.dataset.modelControl==='column-1'`),true);

  await click('nav a[href="#/watch"]');await until(`current.section==='watch'`);
  await key('Tab','Tab',9);
  await evaluate(`document.querySelector('nav a[href="#/models"]').focus({preventScroll:true})`);
  assert.equal(await evaluate(`document.activeElement.matches(':focus-visible') && getComputedStyle(document.activeElement).outlineStyle==='solid'`),true);
  await key('Enter','Enter',13,'\r');await until(`current.section==='models' && !current.loading`);
  const keyboard=await focusSnapshot('keyboard-return');
  assert.equal(keyboard.active,'content');assert.equal(keyboard.focusVisible,true);
  assert.equal(keyboard.outline.style,'none');assert.match(keyboard.shadow,/inset/);assert.equal(keyboard.keyboard,true);
  assert.equal(keyboard.scroll,0);
  await key('Tab','Tab',9);
  assert.equal(await evaluate(`document.activeElement!==document.getElementById('content') &&
    document.activeElement.matches(':focus-visible') && getComputedStyle(document.activeElement).outlineStyle==='solid'`),true);
  // Skip remains discoverable and transfers focus to the named main landmark.
  await evaluate(`document.getElementById('skip').focus({preventScroll:true})`);
  assert.equal(await evaluate(`document.activeElement.matches(':focus-visible') && document.activeElement.getBoundingClientRect().left>=0`),true);
  await key('Enter','Enter',13,'\r');
  const skip=await focusSnapshot('skip-keyboard');
  assert.equal(skip.active,'content');assert.equal(skip.focusVisible,true);assert.match(skip.shadow,/inset/);
  const ax=await command('Accessibility.getFullAXTree');
  assert.ok(ax.nodes.some(node=>node.role?.value==='main' && node.name?.value==='Report content'));

  await command('Emulation.setTouchEmulationEnabled',{enabled:true});
  for(const section of ['watch','models']) {
    const position=await point(`nav a[href="#/${section}"]`);
    await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[position]});
    await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    await until(`current.section==='${section}'`);
  }
  await command('Emulation.setTouchEmulationEnabled',{enabled:false});
  await quiet('touch-return');
  const scheme=await evaluate(`matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'`);
  await command('Emulation.setEmulatedMedia',{features:[{name:'forced-colors',value:'active'}]});
  assert.equal(await evaluate(`getComputedStyle(document.getElementById('content')).outlineStyle`),'none');
  await key('Tab','Tab',9);await evaluate(`document.getElementById('skip').focus({preventScroll:true})`);
  await key('Enter','Enter',13,'\r');
  const contrast=await focusSnapshot('forced-keyboard');
  assert.equal(contrast.active,'content');assert.equal(contrast.outline.style,'solid');
  await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]});
}

module.exports={probeModelsFocus};
