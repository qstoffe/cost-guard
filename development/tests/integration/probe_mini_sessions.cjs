// Real hidden Document PiP session totals/disclosure/layout cases, over shipped SSE.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises'), path = require('node:path');
module.exports = async function sessions({evaluate,until,fixture,command,pipSession,layouts,checks,output,screenshots}) {
  assert.equal(await evaluate(`miniWatch.view.earlier.hidden`),true);
  const initial = await evaluate(`({width:miniWatch.window.innerWidth,height:miniWatch.window.innerHeight})`);
  const activate = async key => {
    await command('Page.bringToFront',{},pipSession);
    await command('Runtime.evaluate',{expression:`document.querySelector('.mini-earlier-toggle').focus()`},pipSession);
    const code = key==='Enter' ? 13 : 32;
    await command('Input.dispatchKeyEvent',{type:'keyDown',key,code:key==='Enter'?'Enter':'Space',windowsVirtualKeyCode:code,text:key==='Enter'?'\r':' '},pipSession);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key,code:key==='Enter'?'Enter':'Space',windowsVirtualKeyCode:code},pipSession);
  };
  await activate('Enter');
  assert.equal(await evaluate(`miniWatch.view.earlierToggle.getAttribute('aria-expanded')`),'true');
  assert.equal(await evaluate(`miniWatch.window.getComputedStyle(miniWatch.view.earlierToggle).outlineStyle !== 'none'`),true);
  for (const count of [0,1,3,5]) {
    await fixture(`history-${count}-12`);
    await until(`liveValue.view.history_cards.length===${count} && miniWatch.view.body.rows.length===12 && miniWatch.view.historyRows.size===${Math.min(count,3)}`);
    const value = await evaluate(`(() => {const w=miniWatch.window,d=w.document,v=miniWatch.view;
      const cells=[...v.prompts.querySelectorAll('tbody td:first-child')].filter(cell=>cell.querySelector('.mini-session-value'));
      const rect=node=>node.getBoundingClientRect(), active=v.body.rows[0].cells[0];
      return {width:w.innerWidth,height:w.innerHeight, pageOverflow:d.documentElement.scrollWidth>w.innerWidth || d.documentElement.scrollHeight>w.innerHeight,
        headings:[...v.historyBody.parentNode.querySelectorAll('th')].map(cell=>cell.textContent),
        ids:[...v.historyBody.rows].map(row=>row.dataset.id).filter(Boolean),running:v.body.rows.length,
        columns:[...v.historyBody.rows].filter(row=>row.dataset.id).map(row=>row.cells.length),
        onlyRegion:[v.earlier,...v.prompts.querySelectorAll('table')].every(node=>!['auto','scroll'].includes(w.getComputedStyle(node).overflowY)),
        unframed:w.getComputedStyle(v.earlier).borderTopWidth==='0px' && w.getComputedStyle(v.earlier).padding==='0px' && w.getComputedStyle(v.earlier).boxShadow==='none',
        scroll:v.prompts.scrollHeight>v.prompts.clientHeight,accounts:v.accounts.clientHeight,
        costs:cells.map(cell=>cell.querySelector('.mini-session-total').textContent),
        suffixVisible:cells.every(cell=>{const total=cell.querySelector('.mini-session-total');return rect(total).right<=rect(cell).right+1 && total.scrollWidth<=total.clientWidth+1;}),
        ellipsis:active.querySelector('.mini-session').scrollWidth>active.querySelector('.mini-session').clientWidth,
        title:active.title,accessible:active.getAttribute('aria-label'),
        sameHeaderRow:Math.abs(rect(v.earlierToggle).top-rect(v.summary).top)<8 && Math.abs(rect(v.daily).top-rect(v.summary).top)<8};})()`);
    layouts.push({case:'earlier-'+count,...value});
    assert.deepEqual({width:value.width,height:value.height},initial,'disclosure never resizes PiP');
    assert.equal(value.pageOverflow,false); assert.equal(value.onlyRegion,true); assert.equal(value.scroll,true);
    assert.equal(value.unframed,true,'earlier table does not inherit generic section-card chrome');
    assert.ok(value.accounts>=32); assert.equal(value.suffixVisible,true); assert.equal(value.ellipsis,true);
    assert.deepEqual(value.headings,['Session | Total CCost','CTX']);
    assert.deepEqual(value.ids,Array.from({length:Math.min(count,3)},(_,index)=>'earlier-'+(Math.max(0,count-3)+index)));
    assert.ok(value.columns.every(count=>count===2)); assert.ok(value.costs.every(cost=>cost===' | 4583'));
    assert.match(value.accessible,/Whole-session CCost: 4583/); assert.match(value.title,/Active long title/);
    if (value.width>=540) assert.equal(value.sameHeaderRow,true);
    await evaluate(`miniWatch.view.prompts.scrollTop=miniWatch.view.prompts.scrollHeight`);
    assert.equal(await evaluate(`(() => {const v=miniWatch.view,r=v.body.rows[11].getBoundingClientRect(),p=v.prompts.getBoundingClientRect();return r.bottom<=p.bottom+1 && r.top>=p.top;})()`),true,'last running prompt remains reachable');
    assert.equal(await evaluate(`miniWatch.view.accounts.scrollTop`),0);
    if (count===5) {
      await command('Runtime.evaluate',{expression:`document.querySelector('.mini-prompts').focus()`},pipSession);
      await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Home',code:'Home',windowsVirtualKeyCode:36,modifiers:2},pipSession);
      await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Home',code:'Home',windowsVirtualKeyCode:36,modifiers:2},pipSession);
      await until(`miniWatch.view.prompts.scrollTop===0`);
      await command('Input.dispatchKeyEvent',{type:'keyDown',key:'PageDown',code:'PageDown',windowsVirtualKeyCode:34},pipSession);
      await command('Input.dispatchKeyEvent',{type:'keyUp',key:'PageDown',code:'PageDown',windowsVirtualKeyCode:34},pipSession);
      await until(`miniWatch.view.prompts.scrollTop>0`);
    }
  }
  await activate(' '); assert.equal(await evaluate(`miniWatch.view.earlier.hidden`),true);
  await fixture('history-3-0'); await until(`miniWatch.view.promptRows.size===0`);
  assert.equal(await evaluate(`miniWatch.view.body.textContent.includes('No running or recently ended prompts')`),true);
  await fixture('history-3-1'); await until(`miniWatch.view.promptRows.size===1`);
  assert.equal(await evaluate(`miniWatch.view.earlier.hidden`),true,'SSE keeps collapsed choice');
  await evaluate(`miniWatch.view.earlierToggle.click()`);
  assert.equal(await evaluate(`miniWatch.view.earlier.hidden`),false,'mouse/touch click disclosure');
  await evaluate(`miniWatch.view.prompts.scrollTop=0`);
  await command('Runtime.evaluate',{expression:`document.querySelector('td .mini-session-value').parentNode.focus()`},pipSession);
  assert.equal(await evaluate(`miniWatch.view.historyBody.rows[0].cells[0].querySelector('.mini-session-help').matches(':popover-open')`),true);
  assert.equal(await evaluate(`miniWatch.view.historyBody.rows[0].cells[0].querySelector('.mini-session-help').textContent===miniWatch.view.historyBody.rows[0].cells[0].title`),true,'keyboard focus visibly exposes full title and cost scope outside clipping');
  await command('Runtime.evaluate',{expression:`document.querySelector('.mini-earlier-toggle').focus()`},pipSession);
  await evaluate(`miniWatch.view.prompts.scrollTop=0;new Promise(resolve=>miniWatch.window.requestAnimationFrame(()=>miniWatch.window.requestAnimationFrame(resolve)))`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},pipSession);
  const point = await evaluate(`(() => {const v=miniWatch.view,r=v.historyBody.rows[0].cells[0].getBoundingClientRect(),
    region=v.prompts.getBoundingClientRect(),header=v.historyBody.parentNode.querySelector('th').getBoundingClientRect();
    return {x:(Math.max(r.left,region.left)+Math.min(r.right,region.right))/2,
      y:(Math.max(r.top,header.bottom,region.top)+Math.min(r.bottom,region.bottom))/2};})()`);
  assert.equal(await evaluate(`miniWatch.window.document.elementFromPoint(${point.x},${point.y})?.closest('td')===miniWatch.view.historyBody.rows[0].cells[0]`),true,'hover target is below the sticky header');
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},pipSession);
  await until(`miniWatch.view.historyBody.rows[0].cells[0].querySelector('.mini-session-help').matches(':popover-open')`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},pipSession);
  await until(`!miniWatch.view.historyBody.rows[0].cells[0].querySelector('.mini-session-help').matches(':popover-open')`);
  await command('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...point},pipSession);
  await command('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...point},pipSession);
  assert.equal(await evaluate(`miniWatch.view.historyBody.rows[0].cells[0].querySelector('.mini-session-help').matches(':popover-open')`),true,'click exposes full title');
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},pipSession);
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},pipSession);
  await command('Runtime.evaluate',{expression:`document.querySelector('.mini-earlier-toggle').focus()`},pipSession);
  const image = await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},pipSession);
  const imagePath = output.replace(/\.json$/,'')+'-earlier.png';
  await fs.writeFile(imagePath,Buffer.from(image.data,'base64')); screenshots.push(path.basename(imagePath));
  await command('Runtime.evaluate',{expression:`document.documentElement.style.fontSize='150%'`},pipSession);
  assert.equal(await evaluate(`miniWatch.view.doc.documentElement.scrollWidth<=miniWatch.window.innerWidth && miniWatch.view.doc.documentElement.scrollHeight<=miniWatch.window.innerHeight`),true);
  await command('Runtime.evaluate',{expression:`document.documentElement.style.fontSize=''`},pipSession);
  await evaluate(`(() => {const p=structuredClone(liveValue); p.view.now_ms++;
    for(const card of [...p.view.active_cards,...p.view.history_cards]) {
      card.session_summary.cost.display_units.credits.known_ccost='?123 456 789';
      card.session_summary.cost.display_units.usd.known_ccost='?$1 234 567.89';
    } miniWatch.update(p);})()`);
  for (const unit of ['credits','usd']) {
    await evaluate(`ReportView.setUnit('${unit}');miniWatch.settings()`);
    const valid = await evaluate(`(() => {const v=miniWatch.view;return [...v.prompts.querySelectorAll('td .mini-session-total')].every(node=>{
      const r=node.getBoundingClientRect(),cell=node.closest('td').getBoundingClientRect();return r.right<=cell.right+1 && node.scrollWidth<=node.clientWidth+1;
    }) && v.doc.documentElement.scrollWidth<=miniWatch.window.innerWidth;})()`);
    assert.equal(valid,true,'large/partial full total never ellipsizes or overflows its cell');
  }
  await evaluate(`ReportView.setUnit('credits');miniWatch.settings()`);
  const headersSafe = await evaluate(`(() => {const v=miniWatch.view,region=v.prompts;
    for(const position of [0,30,60,90,120]) {region.scrollTop=position;
      const earlier=v.historyBody.parentNode.querySelector('th').getBoundingClientRect(),active=v.body.parentNode.querySelector('th').getBoundingClientRect();
      if(earlier.bottom>active.top+1) return false;
    }return true;})()`);
  assert.equal(headersSafe,true,'table-scoped sticky headers never cover each other');
  await fixture('running'); await until(`miniWatch.view.body.rows.length===2`);
  await evaluate(`miniWatch.view.earlierToggle.click();miniWatch.view.prompts.scrollTop=0`);
  checks.push('Whole-session suffix stays visible before/after title ellipsis; canonical newest-three Earlier Sessions, zero/one/three/five history, keyboard/click disclosure, stable SSE choice and shared scroll keep every running row reachable without PiP resize or second SSE');
};
