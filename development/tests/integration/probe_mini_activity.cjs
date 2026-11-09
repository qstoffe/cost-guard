// Unified Activity time/help acceptance in owned headless PiP, not physical OS proof.
const assert = require('node:assert/strict');
module.exports = async function activity({evaluate,until,fixture,command,pip,ownerSession,layouts,checks}) {
  const input = (method,params) => command(method,params,pip);
  const settle = () => evaluate('new Promise(resolve=>miniWatch.window.requestAnimationFrame(()=>miniWatch.window.requestAnimationFrame(resolve)))');
  const values = () => evaluate(`(()=>{const v=miniWatch.view;return [...v.body.rows].filter(r=>r.dataset.id?.startsWith('earlier-')).map(row=>({
    time:row.cells[0].textContent,help:row.activityHelp,columns:row.cells.length,id:row.dataset.id,
    focus:row.cells[0].firstChild.tabIndex,native:row.cells[0].firstChild.hasAttribute('title')}));})()`);
  const key = async key => {
    for(const type of ['keyDown','keyUp']) await input('Input.dispatchKeyEvent',{type,key,code:key,windowsVirtualKeyCode:key==='Tab'?9:27});
  };
  await fixture('history-times'); await until(`liveValue.view.history_cards[0].rows[0].prompt.display.finished_clock==='23:47'`);
  await until(`miniWatch.view.promptRows.has('earlier-0')`);
  await evaluate(`window.activityRow=miniWatch.view.promptRows.get('earlier-0');window.activityTime=activityRow.cells[0].firstChild`);
  assert.deepEqual((await values()).map(row=>[row.time,row.help]),[
    ['—','Unknown finish time'],['23:47','2026-11-05 23:47 +0100'],['00:08','2026-11-06 00:08 +0100']]);
  assert.ok((await values()).every(row=>row.columns===5 && row.focus===0 && !row.native));
  assert.deepEqual(await evaluate(`[...miniWatch.view.body.parentNode.querySelectorAll('th')].map(n=>n.textContent)`),
    ['Activity','Session','CCost','Total','Ctx']);
  await evaluate('miniWatch.window.resizeTo(650,550)',true); await settle();
  await key('Tab'); await evaluate('activityTime.focus({preventScroll:true})');
  const help = `miniWatch.view.doc.getElementById('context-help')`;
  await until(`${help}?.matches(':popover-open')`);
  assert.equal(await evaluate(`${help}.textContent`),'2026-11-05 23:47 +0100');
  await fixture('history-dst'); await until(`miniWatch.view.promptRows.get('earlier-0').activityHelp==='2026-10-25 02:30 +0200'`);
  assert.deepEqual((await values()).map(row=>[row.time,row.help]),[
    ['02:30','2026-10-25 02:30 +0200'],['02:30','2026-10-25 02:30 +0100'],['00:08','2026-11-06 00:08 +0100']]);
  assert.equal(await evaluate(`miniWatch.view.promptRows.get('earlier-0')===activityRow && activityRow.cells[0].firstChild===activityTime`),true);
  assert.equal(await evaluate(`${help}.textContent`),'2026-10-25 02:30 +0200','focused help refreshes in place');
  for(const locale of ['en-US','sv-SE']) for(const timezoneId of ['America/New_York','Asia/Tokyo']) {
    // Locale is shared by the opener/PiP renderer; a second target override conflicts.
    await command('Emulation.setLocaleOverride',{locale},ownerSession);
    for(const session of [ownerSession,pip]) {
      await command('Emulation.setTimezoneOverride',{timezoneId},session);
    }
    assert.deepEqual((await values()).slice(0,2).map(row=>[row.time,row.help]),[
      ['02:30','2026-10-25 02:30 +0200'],['02:30','2026-10-25 02:30 +0100']]);
    assert.equal(await evaluate(`${help}.textContent`),'2026-10-25 02:30 +0200');
  }
  checks.push('Actual Document PiP configured-local activity/offset help is invariant under en-US/sv-SE and New York/Tokyo browser zones');
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
          const rows=[...v.body.rows].filter(r=>r.dataset.id);return {outer:w.outerWidth,inner:w.innerWidth,zoom:devicePixelRatio,
            documentOverflow:d.documentElement.scrollWidth>w.innerWidth+1,
            horizontal:v.prompts.scrollWidth>v.prompts.clientWidth+1,
            vertical:d.documentElement.scrollHeight>w.innerHeight+1,
            activityWidth:rect(rows[0].cells[0]).width,sessionWidth:rect(rows[0].cells[1]).width,
            nowrap:rows.every(row=>w.getComputedStyle(row.cells[0]).whiteSpace==='nowrap'),
            alignment:rows.every(row=>Math.abs(rect(row.cells[0]).right-rect(v.body.parentNode.rows[0].cells[0]).right)<1),
            totals:rows.every(row=>{const n=row.querySelector('.mini-cost-value'),c=row.cells[2];return n.scrollWidth<=n.clientWidth+1 && rect(n).right<=rect(c).right+1;}),
             context:rows.every(row=>row.cells[4].textContent!=='')};})()`);
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
    checks.push('Unified five-column Activity retains midnight/DST/unknown tokens; stable focus/help, delayed hover and real touch; four themes, Credits/USD and nominal/narrow PiP geometry');
};
