// Native option hit testing and trusted wheel input, not dispatchEvent-only proof.
const assert = require('node:assert/strict');
module.exports = async ({evaluate,command,owner,until,click,point,key,checks,layouts}) => {
  const selector = '#mini-size', option = value => `${selector} option[value="${value}"]`;
  const help = value => `${selector} > .settings-choice-help[data-choice="${value}"]`;
  const read = value => evaluate(`(()=>{const s=document.querySelector('${selector}'),o=document.querySelector('${option(value)}'),d=document.querySelector('${help(value)}');
    return {top:d.scrollTop,max:d.scrollHeight-d.clientHeight,visible:getComputedStyle(d).visibility,position:getComputedStyle(d).position,
      hovered:o.matches(':hover'),focused:o.matches(':focus'),preview:d.dataset.preview,value:s.value,open:s.matches(':open'),writes:settingWrites.length};})()`);
  const wheel = async (target, deltaY) => {
    await command('Input.dispatchMouseEvent',{type:'mouseWheel',...await point(target),deltaX:0,deltaY},owner);
    await evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
  };
  await evaluate(`window.wheelOriginal=[...document.querySelectorAll('${selector} > .settings-choice-help')].map(n=>n.textContent)`);
  const writes = await evaluate('settingWrites.length');
  await click(selector); await until(`document.querySelector('${selector}').matches(':open')`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...await point(option('fit-on-open'))},owner);
  const real = await read('fit-on-open'); assert.ok(real.max>0,JSON.stringify(real));
  await wheel(option('fit-on-open'),60);
  await until(`document.querySelector('${help('fit-on-open')}').scrollTop>0`);
  const actual = await read('fit-on-open'); assert.equal(actual.hovered,true); assert.equal(actual.value,'default');
  layouts.push({case:'real-fit-option-wheel',before:real,after:actual});
  await key('Escape');
  await evaluate(`[...document.querySelectorAll('${selector} > .settings-choice-help')].forEach(n=>{n.textContent+=' Extended explanation for substantial scrolling. '.repeat(150);})`);
  await click(selector); await until(`document.querySelector('${selector}').matches(':open')`);
  await evaluate(`[...document.querySelectorAll('${selector} > .settings-choice-help')].forEach(n=>{n.getBoundingClientRect();n.scrollTop=0;})`);
  for (const value of ['fit-on-open','default','remember-last']) {
    const target = option(value), direct=help(value);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...await point(target)},owner);
    const before = await read(value); assert.ok(before.max>500); assert.equal(before.top,0);
    for (let i=0;i<4;i++) await wheel(target,180);
    let state=await read(value); assert.ok(state.top>before.top+100,JSON.stringify(state));
    assert.equal(state.hovered,true); assert.equal(state.visible,'visible'); assert.equal(state.open,true);
    assert.equal(state.value,'default'); assert.equal(state.writes,writes);
    const midway=state.top; await wheel(target,-180); state=await read(value); assert.ok(state.top<midway);
    await wheel(target,100000); state=await read(value); assert.ok(Math.abs(state.top-state.max)<2,JSON.stringify(state));
    await wheel(target,100); assert.equal((await read(value)).hovered,true,'bottom never changes preview');
    await wheel(target,-100000); assert.equal((await read(value)).top,0);
    await wheel(target,-100); assert.equal((await read(value)).hovered,true,'top never changes preview');
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...await point(direct)},owner);
    await wheel(direct,180); state=await read(value); assert.ok(state.top>0,'direct wheel still works');
    assert.equal(state.preview,'true'); assert.equal(state.visible,'visible');
    assert.equal(state.value,'default'); assert.equal(state.writes,writes);
    if(value==='fit-on-open' && process.argv[4]!=='without-drag') {
      layouts.push({case:'scrollbar-viewport',...await evaluate('({inner:[innerWidth,innerHeight],outer:[outerWidth,outerHeight],dpr:devicePixelRatio,offset:[visualViewport.offsetLeft,visualViewport.offsetTop],scale:visualViewport.scale})')});
      await evaluate(`document.querySelector('${direct}').scrollTop=0`);
      // Capture forces the native scrollbar thumb's painted position to settle.
      const image=await command('Page.captureScreenshot',{format:'png'},owner);
      await require('node:fs/promises').writeFile(process.argv[3].replace(/\.json$/,'-scrollbar.png'),Buffer.from(image.data,'base64'));
      const bar=await evaluate(`(()=>{const d=document.querySelector('${direct}'),r=d.getBoundingClientRect();return {x:r.right-5,y:r.top+22,end:r.bottom-22};})()`);
      await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:bar.x,y:bar.y},owner);
      await evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
      await command('Input.dispatchMouseEvent',{type:'mousePressed',x:bar.x,y:bar.y,button:'left',clickCount:1},owner);
      await evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
      for(let step=1;step<=4;step++){
        await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:bar.x,y:bar.y+(bar.end-bar.y)*step/4,button:'left',buttons:1},owner);
        await evaluate('new Promise(resolve=>requestAnimationFrame(resolve))');
      }
      await evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
      const during=await read(value); assert.ok(during.top>100,'native drag moves the scrollbar before release '+JSON.stringify({bar,during}));
      await command('Input.dispatchMouseEvent',{type:'mouseReleased',x:bar.x,y:bar.end,button:'left',clickCount:1},owner);
      const dragged=await read(value); assert.ok(dragged.top>100); assert.equal(dragged.open,true);
      assert.equal(dragged.value,'default'); assert.equal(dragged.writes,writes); assert.equal(dragged.preview,'true');
      layouts.push({case:'native-help-scrollbar',during,after:dragged});
    }
    layouts.push({case:'long-option-wheel',value,...state});
  }
  await key('Escape');
  await click(selector); await key('ArrowDown');
  const focused=await evaluate(`document.querySelector('${selector} option:focus').value`);
  await evaluate(`document.querySelector('${help(focused)}').scrollTop=0`);
  await wheel(option(focused),120); const keyboard=await read(focused);
  assert.ok(keyboard.top>0); assert.equal(keyboard.focused,true); assert.equal(keyboard.value,'default');
  await key('Escape');
  await evaluate(`[...document.querySelectorAll('${selector} > .settings-choice-help')].forEach((n,i)=>{n.textContent=wheelOriginal[i];n.scrollTop=0;})`);
  await click('#web-theme'); await command('Input.dispatchMouseEvent',{type:'mouseMoved',...await point('#web-theme option[value="classic"]')},owner);
  assert.equal(await evaluate(`(()=>{const d=document.querySelector('#web-theme > .settings-choice-help[data-choice="classic"]');return d.scrollHeight===d.clientHeight;})()`),true);
  await wheel('#web-theme option[value="classic"]',100);
  assert.equal(await evaluate('settingWrites.length'),writes); await key('Escape');
  checks.push('Trusted native wheel over real Fit help, unselected/selected/Default long options: substantial forward/reverse/end/boundary scrolling, stable preview, direct help wheel, keyboard focus and no writes; short help remains native');
  checks.push(process.argv[4]==='without-drag'?'Native scrollbar drag excluded; prior Edge failure unresolved':'Native help scrollbar moves during drag and after release, popup stays open, preview/value/writes unchanged');
};
