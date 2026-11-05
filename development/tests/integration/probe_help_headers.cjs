// Real pointer hit-testing and computed styles, including the separate PiP document.
const assert = require('node:assert/strict');
module.exports = function headers({command,evaluate,until,owner,mini,checks,layouts}) {
  const move = (id,point) => command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},id);
  const settle = id => evaluate(id,`new Promise(resolve=>setTimeout(resolve,190))`);
  async function target(id,selector) {
    await command('Page.bringToFront',{},id);
    await evaluate(id,`document.activeElement?.blur()`);
    await move(id,{x:0,y:0}); await settle(id);
    await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'center',inline:'center'})`);
    const points = await evaluate(id,`(() => {
      const label=document.querySelector(${JSON.stringify(selector)}),cell=label.closest('th');
      const r=label.getBoundingClientRect(),c=cell.getBoundingClientRect(),range=document.createRange();
      range.selectNodeContents(label);const text=range.getBoundingClientRect();
      const dead=[{x:c.left+2,y:r.top+r.height/2},{x:c.right-2,y:r.top+r.height/2},{x:(c.left+c.right)/2,y:r.top+r.height/2}]
        .filter(p=>p.x>0&&p.x<innerWidth&&p.y>0&&p.y<innerHeight&&!document.elementFromPoint(p.x,p.y)?.closest('.help-trigger,.help-label'));
      const style=n=>{const s=getComputedStyle(n);return {color:s.color,background:s.backgroundColor,cursor:s.cursor,decoration:s.textDecorationLine,border:s.borderBottomStyle};};
      return {text:{x:(text.left+text.right)/2,y:(text.top+text.bottom)/2},dead,
        label:style(label),cell:style(cell),width:r.width,textWidth:text.width,viewport:{width:innerWidth,height:innerHeight}};
    })()`);
    assert.ok(points.dead.length,'visible header padding: '+selector);
    assert.ok(Math.abs(points.width-points.textWidth)<1,'help label must not stretch: '+JSON.stringify({selector,points}));
    assert.equal(points.label.decoration,'none');assert.notEqual(points.label.border,'dotted');assert.notEqual(points.label.border,'dashed');
    for (const dead of points.dead) {
      await move(id,dead); await settle(id);
      const state=await evaluate(id,`(() => {const n=document.elementFromPoint(${dead.x},${dead.y}),label=document.querySelector(${JSON.stringify(selector)}),cell=label.closest('th');
        return {open:!!document.querySelector('#context-help')?.matches(':popover-open'),cursor:getComputedStyle(n).cursor,
          labelColor:getComputedStyle(label).color,cellColor:getComputedStyle(cell).color,background:getComputedStyle(cell).backgroundColor};})()`);
      assert.equal(state.open,false,'dead space cannot open help: '+selector);
      assert.notEqual(state.cursor,'help');assert.equal(state.labelColor,points.label.color);
      assert.equal(state.cellColor,points.cell.color);assert.equal(state.background,points.cell.background);
    }
    const hit=await evaluate(id,`(() => {const n=document.elementFromPoint(${points.text.x},${points.text.y}),label=document.querySelector(${JSON.stringify(selector)});return {label:label.contains(n),cursor:getComputedStyle(n).cursor};})()`);
    assert.equal(hit.label,true,JSON.stringify({selector,points,hit}));assert.equal(hit.cursor,selector.includes('.help-label')?'pointer':'help');
    await move(id,points.text);await until(id,`document.querySelector('#context-help')?.matches(':popover-open')`);
    const hovered=await evaluate(id,`(() => {const label=document.querySelector(${JSON.stringify(selector)});
      return {labelBackground:getComputedStyle(label).backgroundColor,cellBackground:getComputedStyle(label.closest('th')).backgroundColor};})()`);
    assert.equal(hovered.labelBackground,points.label.background);
    assert.equal(hovered.cellBackground,points.cell.background);
    await move(id,points.dead[0]);await settle(id);
    const exit=await evaluate(id,`(() => {const p=document.querySelector('#context-help'),hit=document.elementFromPoint(${points.dead[0].x},${points.dead[0].y});return {hidden:p.hidden,panel:p.getBoundingClientRect().toJSON(),hit:hit?.outerHTML.slice(0,200),focus:document.activeElement?.outerHTML.slice(0,100)};})()`);
    assert.equal(exit.hidden,true,'text to same-header padding closes: '+JSON.stringify({selector,points,exit}));
    await evaluate(owner,`miniWatch.render();if(current.watch)current.watch.update(liveValue)`);
    await settle(id);assert.equal(await evaluate(id,`document.querySelector('#context-help').hidden`),true,'refresh cannot resurrect dead-space help');
    await move(id,points.text);await until(id,`document.querySelector('#context-help').matches(':popover-open')`);
    const panel=await evaluate(id,`(() => {const r=document.querySelector('#context-help').getBoundingClientRect();return {x:r.left+5,y:r.top+5};})()`);
    await move(id,panel);await settle(id);
    assert.equal(await evaluate(id,`document.querySelector('#context-help').hidden`),false,'text to panel preserves readable help');
    await move(id,{x:-20,y:-20});await settle(id);
    assert.equal(await evaluate(id,`document.querySelector('#context-help').hidden`),true,'fast document exit closes');
    if (selector.includes('.help-label')) {
      const action=await evaluate(id,`(() => {const label=document.querySelector(${JSON.stringify(selector)}),button=label.closest('button'),r=button.getBoundingClientRect();
        return {point:{x:r.left+1,y:r.top+r.height/2},before:label.closest('th').getAttribute('aria-sort')};})()`);
      await move(id,action.point);await settle(id);
      assert.equal(await evaluate(id,`document.querySelector('#context-help').hidden`),true,'sorting whitespace has no hover help');
      for (const type of ['mousePressed','mouseReleased']) await command('Input.dispatchMouseEvent',{type,button:'left',clickCount:1,...action.point},id);
      const after=await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).closest('th').getAttribute('aria-sort')`);
      assert.notEqual(after,action.before,'click outside text still sorts');
      assert.equal(await evaluate(id,`document.querySelector('#context-help').hidden`),true,'sorting action dismisses help');
    }
    return {selector,deadPoints:points.dead.length,labelWidth:points.width,textWidth:points.textWidth};
  }
  async function audit(id) {
    const errors=await evaluate(id,`[...document.querySelectorAll('.help-trigger,.help-label,.help-value')].flatMap(n=>{const s=getComputedStyle(n);
      return s.textDecorationLine.includes('underline')||['dotted','dashed'].includes(s.borderBottomStyle)?[n.textContent||n.getAttribute('aria-label')]:[];})`);
    assert.deepEqual(errors,[],'no tooltip underline, including standalone ? cues');
    assert.equal(await evaluate(id,`document.querySelectorAll('.help-cue').length`),0,'no standalone question-mark help icons');
  }
  async function matrix() {
    await evaluate(owner,`document.querySelector('.watch-earlier').open=true;miniWatch.view.earlier.hidden=false`);
    const selectors=[[owner,'.watch-active th:nth-child(3) button'],[owner,'.watch-history th:first-child button'],
      [mini,'.mini-prompts > table th:first-child button'],[mini,'.mini-prompts > section th:first-child button.mini-session-total']];
    for (const theme of ['classic','light','dark']) for (const [width,zoom] of [[1280,1],[360,1.5]]) {
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},owner);
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},owner);
      // Keep exposed header padding outside the readable panel at enlarged text sizes.
      // The parent probe separately checks viewport clamping in compact PiP sizes.
      await evaluate(owner,`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}';document.documentElement.style.zoom='${zoom}';miniWatch.syncTheme();miniWatch.window.resizeTo(${width===360?360:560},700)` ,true);
      await evaluate(mini,`document.documentElement.style.zoom='${zoom}'`);
      for (const [id,selector] of selectors) layouts.push({case:'text-only-header',theme,width,zoom,document:id===owner?'watch':'mini',...await target(id,selector)});
      await audit(owner);await audit(mini);
    }
    await evaluate(owner,`document.documentElement.style.zoom='';document.querySelector('.watch-earlier').open=false;miniWatch.view.earlier.hidden=true;miniWatch.window.resizeTo(560,400)`,true);
    await evaluate(mini,`document.documentElement.style.zoom='';document.querySelector('.mini-prompts').scrollTop=0`);
    await command('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false},owner);
    checks.push('Both full Watch and Mini Running/Earlier: text-sized hitboxes, no underline/help cursor/text/cell highlight in padding, bounded text-to-padding exit, panel transfer, re-entry and rapid document exit; Classic/Web light/dark, narrow and 150% zoom');
  }
  return {matrix,target,audit};
};
