// Safe live Duration fragments in the actual Document PiP help lifecycle.
const assert = require('node:assert/strict');
module.exports = async ({evaluate,until,command,pip,ownerSession,checks}) => {
  const key = async key => { for (const type of ['keyDown','keyUp'])
    await command('Input.dispatchKeyEvent',{type,key,code:key,windowsVirtualKeyCode:key==='Tab'?9:27},pip); };
  const panel = `miniWatch.view.doc.getElementById('context-help')`;
  await evaluate(`window.durationPublication=structuredClone(liveValue);
    {const v=durationPublication.view,c=v.active_cards[0],r=c.rows[0];
    v.active_cards=[c];v.history_cards=[];v.history_state='observed';v.history_epoch=1;
    c.state='observed';c.session_id='duration-synthetic';c.focal_id=r.prompt.event_id='duration-prompt';
    Object.assign(r.prompt,{in_progress:true,execution_unverified:false,has_error:false,aborted:false});
    r.display_units={};r.display.watch_duration_ms='11s';r.model='<img src=x onerror=alert(1)>';
    window.durationUpdate=miniWatch.update.bind(miniWatch);miniWatch.update=()=>durationUpdate(durationPublication);
    miniWatch.update(durationPublication);window.durationRow=miniWatch.view.promptRows.get(c.session_id);}`);
  await command('Page.bringToFront',{},pip);
  for (const theme of ['classic','web']) for (const scheme of ['light','dark']) {
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]},ownerSession);
    await evaluate(`(async()=>applySettings(await api('/api/settings/theme',{theme:'${theme}'})))()`);
    for (const unit of ['credits','usd']) for (const column of [2,3]) {
      await key('Escape');await key('Tab');
      await evaluate(`ReportView.setUnit('${unit}');miniWatch.update(durationPublication);durationRow.cells[${column}].firstChild.focus()`);
      await until(`${panel}?.matches(':popover-open')`);
      const before=await evaluate(`(()=>{const p=${panel},s=p.querySelector('.context-help-running-duration'),w=miniWatch.window;
        window.durationSpan=s;return {line:s?.textContent,count:p.querySelectorAll('span').length,
        text:p.textContent,images:p.querySelectorAll('img').length,color:w.getComputedStyle(s).color,
        running:w.getComputedStyle(durationRow).color,normal:w.getComputedStyle(p).color};})()`);
      assert.equal(before.line,'Duration: 11s');assert.equal(before.count,1);assert.equal(before.images,0);
      assert.ok(before.text.includes('Main model: <img src=x onerror=alert(1)>'));
      assert.equal(before.color,before.running);assert.notEqual(before.color,before.normal);
      await evaluate(`{const selection=miniWatch.view.doc.getSelection();selection.selectAllChildren(durationSpan);
        durationPublication.view.active_cards[0].rows[0].display.watch_duration_ms='12s';miniWatch.update(durationPublication);}`);
      assert.equal(await evaluate(`${panel}.querySelector('span')===durationSpan && durationSpan.textContent==='Duration: 12s'`),true);
      assert.equal(await evaluate(`miniWatch.view.doc.activeElement===durationRow.cells[${column}].firstChild`),true);
      assert.equal(await evaluate(`miniWatch.view.doc.getSelection().toString()`),'Duration: 12s');
      await evaluate(`miniWatch.view.doc.getSelection().removeAllRanges()`);
      // Already-open help loses the cue for every non-running/untrusted outcome.
      for (const phase of ['completed','aborted','failed','unverified','historical','replacement']) {
        await evaluate(`{const v=durationPublication.view,c=(v.active_cards[0]||v.history_cards[0]),r=c.rows[0];
          v.active_cards=[c];v.history_cards=[];c.focal_id=r.prompt.event_id;
          Object.assign(r.prompt,{in_progress:true,execution_unverified:false,has_error:false,aborted:false});
          if('${phase}'==='completed')r.prompt.in_progress=false;
          if('${phase}'==='aborted')r.prompt.aborted=true;
          if('${phase}'==='failed')r.prompt.has_error=true;
          if('${phase}'==='unverified')r.prompt.execution_unverified=true;
          if('${phase}'==='historical'){v.active_cards=[];v.history_cards=[c];c.focal_id='';r.prompt.in_progress=false;}
          if('${phase}'==='replacement'){c.focal_id=r.prompt.event_id='replacement';r.prompt.in_progress=false;}
          miniWatch.update(durationPublication);}`);
        const state=await evaluate(`({open:${panel}.matches(':popover-open'),spans:${panel}.querySelectorAll('span').length,
          text:${panel}.textContent,focus:miniWatch.view.doc.activeElement===durationRow.cells[${column}].firstChild})`);
        assert.equal(state.open && !state.spans && state.text.includes('Duration: 12s'),true,phase+' '+JSON.stringify(state));
      }
      await evaluate(`{const c=durationPublication.view.active_cards[0],r=c.rows[0];
        r.prompt.in_progress=true;r.display.watch_duration_ms='11s';miniWatch.update(durationPublication);}`);
    }
  }
  await key('Escape');await evaluate(`miniWatch.update=durationUpdate;delete window.durationUpdate;ReportView.setUnit('credits');miniWatch.update(liveValue)`);
  checks.push('Both independent cost tooltips: only the full running Duration line uses the theme running/yellow role; ticking span/focus retained, open completion/abort/error/unverified/history/replacement removes it; hostile model text stays literal; Classic/Web light/dark and Credits/USD');
};
