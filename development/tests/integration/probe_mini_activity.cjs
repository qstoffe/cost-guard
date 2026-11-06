// Historical-only Activity acceptance in the owned headless PiP, not physical OS proof.
const assert = require('node:assert/strict');
module.exports = async function activity({evaluate,until,fixture,command,pip,ownerSession,layouts,checks}) {
  const input = (method,params) => command(method,params,pip);
  const settle = () => evaluate('new Promise(resolve=>miniWatch.window.requestAnimationFrame(()=>miniWatch.window.requestAnimationFrame(resolve)))');
  const values = () => evaluate(`(()=>{const v=miniWatch.view;return [...v.historyBody.rows].map(row=>({
    time:row.cells[0].textContent,help:row.finishHelp,columns:row.cells.length,id:row.dataset.id,
    focus:row.cells[0].firstChild.tabIndex,native:row.cells[0].firstChild.hasAttribute('title')}));})()`);
  const key = async key => {
    for(const type of ['keyDown','keyUp']) await input('Input.dispatchKeyEvent',{type,key,code:key,windowsVirtualKeyCode:key==='Tab'?9:27});
  };
  await fixture('history-times'); await until(`liveValue.view.history_cards[0].rows[0].prompt.display.finished_clock==='23:47'`);
  if(await evaluate('miniWatch.view.earlier.hidden')) await evaluate('miniWatch.view.earlierToggle.click()');
  await evaluate('window.activityRow=miniWatch.view.historyBody.rows[0];window.activityTime=activityRow.cells[0].firstChild');
  assert.deepEqual((await values()).map(row=>[row.time,row.help]),[
    ['23:47','2026-11-05 23:47 +0100'],['00:08','2026-11-06 00:08 +0100'],['—','Unknown finish time']]);
  assert.ok((await values()).every(row=>row.columns===4 && row.focus===0 && !row.native));
  assert.deepEqual(await evaluate(`[...miniWatch.view.historyBody.parentNode.querySelectorAll('th')].map(n=>n.textContent)`),
    ['Activity','Session','CCost (Total)','Ctx']);
  assert.deepEqual(await evaluate(`[...miniWatch.view.body.parentNode.querySelectorAll('th')].map(n=>n.textContent)`),
    ['Session','CCost (Total)','Duration','Ctx']);
  await evaluate('miniWatch.window.resizeTo(650,550)',true); await settle();
  await key('Tab'); await evaluate('activityTime.focus({preventScroll:true})');
  const help = `miniWatch.view.doc.getElementById('context-help')`;
  await until(`${help}?.matches(':popover-open')`);
  assert.equal(await evaluate(`${help}.textContent`),'2026-11-05 23:47 +0100');
  await fixture('history-dst'); await until(`miniWatch.view.historyBody.rows[0].finishHelp==='2026-10-25 02:30 +0200'`);
  assert.deepEqual((await values()).map(row=>[row.time,row.help]),[
    ['02:30','2026-10-25 02:30 +0200'],['02:30','2026-10-25 02:30 +0100'],['00:08','2026-11-06 00:08 +0100']]);
  assert.equal(await evaluate('miniWatch.view.historyBody.rows[0]===activityRow && activityRow.cells[0].firstChild===activityTime'),true);
  assert.equal(await evaluate(`${help}.textContent`),'2026-10-25 02:30 +0200','focused help refreshes in place');
  await key('Escape'); await evaluate('activityTime.blur()');
  await input('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0});
  const point = await evaluate(`(()=>{const r=activityTime.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
  await input('Input.dispatchMouseEvent',{type:'mouseMoved',...point});
  assert.equal(await evaluate(`${help}.matches(':popover-open')`),false,'hover is delayed, not native title help');
  await until(`${help}.matches(':popover-open')`);
  assert.equal(await evaluate(`${help}.textContent`),'2026-10-25 02:30 +0200');
  await input('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0});
  await until(`!${help}.matches(':popover-open')`);
  for(const type of ['touchStart','touchEnd']) await input('Input.dispatchTouchEvent',{
    type,touchPoints:type==='touchStart'?[{...point,id:1,radiusX:1,radiusY:1,force:1}]:[]});
  await until(`${help}.matches(':popover-open')`);
  assert.equal(await evaluate(`${help}.textContent`),'2026-10-25 02:30 +0200','touch exposes equivalent full local date');
  await key('Escape'); await evaluate('activityTime.blur()');
  for(const theme of ['classic','web']) for(const color of ['light','dark']) {
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:color}]},ownerSession);
    await evaluate(`(async()=>applySettings(await api('/api/settings/theme',{theme:'${theme}'})))()`);
    for(const width of [650,520,280]) {
      await evaluate(`miniWatch.window.resizeTo(${width},550)`,true); await settle();
      for(const unit of ['credits','usd']) {
        await evaluate(`ReportView.setUnit('${unit}');miniWatch.settings()`);
        const layout = await evaluate(`(()=>{const v=miniWatch.view,w=miniWatch.window,d=w.document,rect=n=>n.getBoundingClientRect();
          const rows=[...v.historyBody.rows];return {outer:w.outerWidth,inner:w.innerWidth,zoom:devicePixelRatio,
            documentOverflow:d.documentElement.scrollWidth>w.innerWidth+1,
            horizontal:v.prompts.scrollWidth>v.prompts.clientWidth+1,
            vertical:d.documentElement.scrollHeight>w.innerHeight+1,
            activityWidth:rect(rows[0].cells[0]).width,sessionWidth:rect(rows[0].cells[1]).width,
            nowrap:rows.every(row=>w.getComputedStyle(row.cells[0]).whiteSpace==='nowrap'),
            alignment:rows.every(row=>Math.abs(rect(row.cells[0]).right-rect(v.historyBody.parentNode.rows[0].cells[0]).right)<1),
            totals:rows.every(row=>{const n=row.querySelector('.mini-cost-value'),c=row.cells[2];return n.scrollWidth<=n.clientWidth+1 && rect(n).right<=rect(c).right+1;}),
            context:rows.every(row=>row.cells[3].textContent!=='')};})()`);
        assert.equal(layout.documentOverflow,false); assert.equal(layout.totals,true); assert.equal(layout.context,true);
        assert.equal(layout.nowrap,true); assert.equal(layout.alignment,true);
        if(layout.inner>=600) {assert.equal(layout.horizontal,false);assert.equal(layout.vertical,false);assert.ok(layout.activityWidth<layout.sessionWidth);}
        // Name-only Session has a smaller minimum than the former split heading;
        // these small values may fit at 280. Oversized paired-cost cases separately
        // require horizontal panning rather than clipping either amount.
        layouts.push({case:`activity-${theme}-${color}-${width}-${unit}`,...layout});
      }
    }
  }
  await evaluate(`ReportView.setUnit('credits');miniWatch.settings();miniWatch.window.resizeTo(650,550)`,true); await settle();
  checks.push('Four-column history retains Activity midnight/DST/unknown tokens; stable live focus/help, delayed hover and real touch; four themes, Credits/USD and nominal/narrow PiP geometry');
};
